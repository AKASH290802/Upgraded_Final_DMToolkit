"""
Migration Readiness UI
======================
Streamlit page for the "🎯 Migration Readiness" module.

Flow:
  Sub-tab 1 — SF Schema Sync   : pull object schema from the selected SF org
  Sub-tab 2 — Upload & Map     : upload CSV/Excel, run 5-tool cascade, review
  Sub-tab 3 — Readiness Report : 4-section report + persistent file download

Outputs are saved to file_store/output/migration_readiness/ and registered
in the SQLite-backed File Library so they survive app restarts and are
available to every other DM-Toolkit module (Data Operations, Validation, etc.)
"""
from __future__ import annotations

import io
import csv
import json
import os
import uuid
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# ── project paths ─────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
_OUTPUT_DIR = _PROJECT_ROOT / "file_store" / "output" / "migration_readiness"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── lazy engine imports (only triggered when user visits this tab) ─────────────
def _load_engine():
    """Import toolkit_sales_engine modules lazily to avoid startup overhead."""
    import sys
    sys.path.insert(0, str(_PROJECT_ROOT))

    from toolkit_sales_engine.metadata.registry import MetadataRegistry
    from toolkit_sales_engine.metadata.salesforce_fetcher import SalesforceMetadataFetcher
    from toolkit_sales_engine.mapper.engine import MappingEngine
    from toolkit_sales_engine.quality.validator import DataQualityValidator

    if "ts_registry" not in st.session_state:
        st.session_state.ts_registry = MetadataRegistry()
    if "ts_engine" not in st.session_state:
        st.session_state.ts_engine = MappingEngine(st.session_state.ts_registry)

    # DataQualityValidator is stateless (no registry/connection held across calls),
    # so it's built fresh every time rather than cached in session_state — that way
    # code changes to it take effect immediately instead of a stale cached instance
    # from an old session surviving with an outdated method signature.
    validator = DataQualityValidator()

    return (
        st.session_state.ts_registry,
        st.session_state.ts_engine,
        validator,
        SalesforceMetadataFetcher,
    )


# ── File Library registration ─────────────────────────────────────────────────
def _register_output(file_path: str, original_name: str, org_name: str,
                     object_name: str, operation_type: str,
                     row_count: int = 0, status: str = "") -> None:
    """Register a produced file in the SQLite-backed File Library."""
    try:
        from ui_components.file_store_manager import initialize_db, _get_connection
        initialize_db()
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        with _get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO output_files
                   (original_name, stored_path, org_name, object_name,
                    operation_type, file_size, row_count, status, generated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (original_name, file_path, org_name, object_name,
                 operation_type, file_size, row_count, status,
                 datetime.now().isoformat()),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not register output file: %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def show_migration_readiness(credentials: dict) -> None:
    st.title("🎯 Migration Readiness")
    st.markdown(
        "Upload a client CSV/Excel, auto-map columns to Salesforce fields, "
        "validate data quality, then hand off the clean file to any other module."
    )

    if not st.session_state.get("current_org"):
        st.warning("⚠️ Please select a Salesforce organisation from the sidebar first.")
        return

    org_name = st.session_state.current_org

    try:
        registry, engine, validator, SFetcher = _load_engine()
    except Exception as exc:
        st.error(f"❌ Failed to load mapping engine: {exc}")
        st.code(traceback.format_exc())
        return

    tab1, tab2, tab3 = st.tabs([
        "1️⃣ SF Schema Sync",
        "2️⃣ Upload & Map",
        "3️⃣ Readiness Report",
    ])

    with tab1:
        _show_schema_sync(credentials, org_name, registry, engine, SFetcher)

    with tab2:
        _show_upload_and_map(org_name, registry, engine)

    with tab3:
        _show_readiness_report(credentials, org_name, registry, engine, validator)


def _flow_object_or_current():
    """The guided flow's object (Step 1 target), else the sidebar 'current object'."""
    try:
        from ui_components import step_flow
        return step_flow.get_flow_object() or st.session_state.get('current_object')
    except ImportError:
        return st.session_state.get('current_object')


def _get_sf_connection(credentials, org_name):
    """Return an active Salesforce connection for the selected org (shared, pooled per org)."""
    from ui_components.connection_manager import get_sf_connection
    return get_sf_connection(org_name, credentials=credentials)


def _get_org_object_names(credentials, org_name) -> list[str]:
    """Fetch and cache all Salesforce object API names for the selected org."""
    cache = st.session_state.get("ts_org_objects_cache", {})
    if org_name in cache and cache[org_name]:
        return cache[org_name]

    sf_conn = _get_sf_connection(credentials, org_name)
    if not sf_conn:
        return []

    try:
        describe_result = sf_conn.describe()
        objects = [obj.get("name") for obj in describe_result.get("sobjects", []) if obj.get("name")]
        objects = sorted(set(objects))

        cache[org_name] = objects
        st.session_state["ts_org_objects_cache"] = cache
        return objects
    except Exception as exc:
        st.warning(f"Could not fetch object list for {org_name}: {exc}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SF SCHEMA SYNC
# ══════════════════════════════════════════════════════════════════════════════

def _show_schema_sync(credentials, org_name, registry, engine, SFetcher) -> None:
    st.subheader("1️⃣ Sync Salesforce Object Schema")
    st.markdown(
        "Fetch real field metadata from your Salesforce org. "
        "This caches field names, labels, types, required flags, and picklist values "
        "into `toolkit_sales_engine/registry.json` for use in field mapping."
    )

    org_objects = _get_org_object_names(credentials, org_name)

    col1, col2 = st.columns([2, 1])
    with col1:
        if org_objects:
            default_object = st.session_state.get("ts_object_name") or _flow_object_or_current()
            default_index = org_objects.index(default_object) if default_object in org_objects else 0
            object_name = st.selectbox(
                "Salesforce Object API Name",
                options=org_objects,
                index=default_index,
                key="ts_sync_object_select",
                help="All objects from the selected Salesforce org",
            )
            st.session_state["ts_object_name"] = object_name
        else:
            object_name = st.text_input(
                "Salesforce Object API Name",
                value=st.session_state.get("ts_object_name", ""),
                placeholder="e.g. Account, WOD_2__Claim__c",
                key="ts_sync_object",
            )
            if object_name.strip():
                st.session_state["ts_object_name"] = object_name.strip()
    with col2:
        build_embeddings = st.checkbox(
            "Build Embedding Index",
            value=False,
            help="Requires Azure OpenAI embed key in linkedservices.json → openai_config",
        )

    selected_object = object_name.strip()
    selected_fields = registry.get_all_fields(selected_object) if selected_object else []

    # Show field details only after an explicit sync/load button click.
    if st.session_state.get("ts_schema_last_selected_object") != selected_object:
        st.session_state["ts_schema_last_selected_object"] = selected_object
        st.session_state["ts_schema_show_details_for_object"] = None

    show_details = (
        st.session_state.get("ts_schema_show_details_for_object") == selected_object
        and st.session_state.get("ts_schema_show_details_for_org") == org_name
    )

    if selected_object and selected_fields and show_details:
        st.success(f"✅ Schema cached for **{selected_object}** — {len(selected_fields)} fields")

        field_rows = []
        for f in selected_fields:
            field_rows.append({
                "Field API Name": f.field_name,
                "Label": f.label,
                "Type": str(f.data_type),
                "Required": "Yes" if f.required else "No",
                "Max Length": f.max_length if f.max_length is not None else "",
                "Picklist Values": len(f.picklist_values) if f.picklist_values else 0,
                "Synonyms": len(f.synonyms) if f.synonyms else 0,
            })

        st.markdown("#### Field Details")
        st.dataframe(pd.DataFrame(field_rows), use_container_width=True, hide_index=True, height=360)

        with st.expander("🔍 View field descriptions and values", expanded=False):
            detail_rows = []
            for f in selected_fields:
                detail_rows.append({
                    "Field API Name": f.field_name,
                    "Description": f.description or "",
                    "Picklist Values": ", ".join(f.picklist_values[:10]) if f.picklist_values else "",
                    "Synonyms": ", ".join(f.synonyms[:10]) if f.synonyms else "",
                })
            st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True, height=320)
    else:
        if selected_object:
            if selected_fields:
                st.info("Schema is cached. Click Sync from Salesforce or Load Selected Object Schema to view field details.")
            else:
                st.info(f"No cached schema for **{selected_object}** yet. Click Sync from Salesforce.")
        else:
            st.info("No object selected. Choose an object to view or sync schema.")

    st.divider()
    col_sync, col_seed = st.columns(2)

    with col_sync:
        if st.button("🔄 Sync from Salesforce", use_container_width=True,
                     disabled=not object_name.strip()):
            _do_sync(credentials, org_name, object_name.strip(),
                     build_embeddings, registry, engine, SFetcher)

    with col_seed:
        if st.button("📦 Load Selected Object Schema", use_container_width=True,
                     disabled=not object_name.strip()):
            # Keep this as a user-friendly action that also respects selected org/object.
            _do_sync(credentials, org_name, object_name.strip(),
                     False, registry, engine, SFetcher)


def _do_sync(credentials, org_name, object_name, build_embeddings, registry, engine, SFetcher):
    # Connection of THIS org (never another org's cached connection)
    sf_conn = _get_sf_connection(credentials, org_name)
    if not sf_conn:
        st.error("❌ No active Salesforce connection. Connect via Config tab first.")
        return
    with st.spinner(f"Fetching schema for {object_name}…"):
        try:
            fetcher = SFetcher(sf_conn=sf_conn)
            obj_meta = fetcher.fetch_object(object_name)
            registry.register_object(obj_meta)
            registry.save()
            # Rebuild engine tools to pick up new fields
            engine._exact.refresh()
            engine._synonym.refresh()
            st.session_state["ts_object_name"] = object_name
            st.session_state["ts_schema_show_details_for_object"] = object_name
            st.session_state["ts_schema_show_details_for_org"] = org_name
            st.success(f"✅ Synced **{len(obj_meta.fields)}** fields for **{object_name}**. Field details are shown above.")
        except Exception as exc:
            st.error(f"❌ Sync failed: {exc}")
            return

    if build_embeddings:
        with st.spinner("Building embedding index…"):
            try:
                count = engine._embedding.build_index(object_name)
                if count:
                    st.success(f"✅ Embedding index built for {count} fields.")
                else:
                    st.warning("Embedding index not built — check OpenAI config in linkedservices.json.")
            except Exception as exc:
                st.warning(f"Embedding index failed (non-critical): {exc}")


def _load_sample_claims(registry, engine):
    """Seed with sample Claims object schema (no SF connection needed)."""
    from toolkit_sales_engine.metadata.models import FieldMeta, DataType, ObjectMeta
    sample_fields = [
        FieldMeta(object_name="Claim__c", field_name="Claim_Number__c", label="Claim Number",
                  description="Unique claim identifier", data_type=DataType.STRING,
                  required=True, max_length=50,
                  synonyms=["claim_id","clm_id","clm_no","claim_no","claim_ref","ref_no"]),
        FieldMeta(object_name="Claim__c", field_name="Claim_Date__c", label="Claim Date",
                  description="Date the claim was filed", data_type=DataType.DATE,
                  required=True, synonyms=["clm_dt","claim_filed_date","date_of_claim","loss_date","dol"]),
        FieldMeta(object_name="Claim__c", field_name="Claimant_Name__c", label="Claimant Name",
                  description="Full name of claimant", data_type=DataType.STRING,
                  required=True, max_length=255,
                  synonyms=["claimant","member_name","insured_name","client_name","full_name","name"]),
        FieldMeta(object_name="Claim__c", field_name="Policy_Number__c", label="Policy Number",
                  description="Insurance policy number", data_type=DataType.STRING,
                  required=True, max_length=50, synonyms=["pol_no","policy_id","policy_num"]),
        FieldMeta(object_name="Claim__c", field_name="Claim_Amount__c", label="Claim Amount",
                  description="Total claim amount", data_type=DataType.CURRENCY,
                  synonyms=["clm_amt","claim_value","amount","total_claim","settlement_amt"]),
        FieldMeta(object_name="Claim__c", field_name="Status__c", label="Status",
                  description="Current status", data_type=DataType.PICKLIST,
                  required=True,
                  picklist_values=["Open","In Review","Approved","Denied","Closed","Pending"],
                  synonyms=["claim_status","status","state"]),
    ]
    obj_meta = ObjectMeta(object_name="Claim__c", label="Claim", fields=sample_fields)
    registry.register_object(obj_meta)
    registry.save()
    engine._exact.refresh()
    engine._synonym.refresh()
    st.session_state["ts_object_name"] = "Claim__c"
    st.success("✅ Sample Claims schema loaded (6 fields). Now go to Upload & Map tab.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — UPLOAD & MAP
# ══════════════════════════════════════════════════════════════════════════════

def _apply_pending_overrides(plan, engine, obj: str, overrides: Optional[dict] = None) -> int:
    """
    Persist the mapping table's current dropdown selections into plan.mappings.

    `overrides` (source_column -> chosen target field, or None for unmapped) is
    normally handed in by the caller since it's already built while rendering
    the table. When called from the "Done Editing" toggle there is no such
    dict available — that button reruns the script before the table (and its
    local `overrides`) is rebuilt — so it's reconstructed here from the
    `override_{source_column}` selectbox widget state, which Streamlit keeps
    around across reruns.
    """
    if overrides is None:
        overrides = {}
        for m in plan.mappings:
            widget_key = f"override_{m.source_column}"
            if widget_key in st.session_state:
                chosen = st.session_state[widget_key]
                overrides[m.source_column] = chosen if chosen != "(unmapped)" else None

    saved = 0
    for src_col, tgt_field in overrides.items():
        if tgt_field:
            original = next((m.target_field for m in plan.mappings if m.source_column == src_col), None)
            if tgt_field != original:
                try:
                    engine.apply_override(obj, src_col, tgt_field, auto_add_synonym=True)
                    saved += 1
                except Exception:
                    pass

    for m in plan.mappings:
        if m.source_column not in overrides:
            continue
        new_target = overrides[m.source_column]
        if new_target:
            m.target_field = new_target
            m.confidence_level = "HIGH"
            m.score = 1.0
        else:
            m.target_field = None
            m.confidence_level = "UNMAPPED"
            m.score = 0.0
        m.method = "manual_override"
        m.human_reviewed = True
    return saved


def _parse_data_dictionary_sheet(file_bytes: bytes, sheet_name: str) -> dict:
    """
    Best-effort extraction of {column short-name: description} pairs from a
    "data dictionary" / "data key" style sheet (e.g. column A = "HIN", column B =
    "Boat Serial#", optional column C = extra legend text). These sheets aren't a
    standardized format, so this is heuristic, not exact -- the caller shows the
    result in an editable table so the user can correct it before it's used.
    """
    raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=None, dtype=str)
    result: dict[str, str] = {}
    for _, row in raw.iterrows():
        cells = row.tolist()
        non_null = [(i, c.strip()) for i, c in enumerate(cells) if isinstance(c, str) and c.strip()]
        if len(non_null) < 2:
            continue
        (_, key), (_, desc) = non_null[0], non_null[1]
        # Skip title/section-heading rows (e.g. "Claims - warranty claim header
        # records"), which read as one long cell rather than a short field name.
        if len(key) > 25 or len(key.split()) > 4:
            continue
        if len(non_null) > 2:
            desc = f"{desc} ({non_null[2][1]})"
        result[key] = desc
    return result


def _show_upload_and_map(org_name, registry, engine) -> None:
    st.subheader("2️⃣ Upload Source File & Run Field Mapping")

    # Prefer full org object list so users can pick any object in the selected org.
    org_objects = _get_org_object_names(st.session_state.get("credentials", {}), org_name)
    cached_objects = registry.get_all_objects()
    object_options = org_objects if org_objects else cached_objects

    if not object_options:
        st.warning("⚠️ Could not load object list for this org. Try reconnecting Salesforce in the sidebar.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        default_object = st.session_state.get("ts_object_name") or _flow_object_or_current()
        default_index = object_options.index(default_object) if default_object in object_options else 0
        object_name = st.selectbox(
            "Target Salesforce Object",
            options=object_options,
            index=default_index,
            key="ts_map_object",
            help="All objects from the selected Salesforce org",
        )
        st.session_state["ts_object_name"] = object_name
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        dup_keys = st.text_input(
            "Duplicate Key Fields",
            placeholder="e.g. Policy Number, Claim Number",
            help="Comma-separated source column names for duplicate detection",
            key="ts_dup_keys",
        )

    uploaded = st.file_uploader(
        "Upload Source File (CSV, Excel, or JSON)",
        type=["csv", "xlsx", "xls", "json"],
        key="ts_file_upload",
    )

    if not uploaded:
        st.info("👆 Upload a CSV, Excel, or JSON file to begin field mapping.")
        return

    # For a multi-sheet Excel workbook, let the user pick which sheet to map —
    # otherwise pd.read_excel silently only reads the first one.
    is_excel = uploaded.name.endswith((".xlsx", ".xls"))
    selected_sheet = None
    if is_excel:
        try:
            sheet_names = pd.ExcelFile(io.BytesIO(uploaded.getvalue())).sheet_names
        except Exception as exc:
            st.error(f"❌ Could not read Excel workbook: {exc}")
            return

        if st.session_state.get("ts_upload_file_id") != uploaded.file_id:
            st.session_state["ts_upload_file_id"] = uploaded.file_id
            st.session_state.pop("ts_excel_sheet", None)

        if len(sheet_names) > 1:
            selected_sheet = st.selectbox(
                "Select Sheet",
                options=sheet_names,
                key="ts_excel_sheet",
                help="This workbook has multiple sheets — choose which one to map.",
            )
        else:
            selected_sheet = sheet_names[0]

    # Optional: a separate "data dictionary" / "data key" sheet documenting what each
    # column means (e.g. "HIN" -> "Boat Serial#"). If picked, its descriptions are fed
    # into the mapping engine (embedding context + LLM prompt) alongside each field's
    # own Salesforce Description/Help Text.
    dict_sheet_options = ["None"] + [s for s in sheet_names if s != selected_sheet] if is_excel else ["None"]
    column_descriptions: dict = {}
    if is_excel and len(dict_sheet_options) > 1:
        dict_sheet = st.selectbox(
            "Data Dictionary Sheet (optional)",
            options=dict_sheet_options,
            key="ts_dict_sheet",
            help="If this workbook has a sheet explaining what each column means, "
                 "pick it here so the mapping engine can use those descriptions too.",
        )
        if dict_sheet != "None":
            try:
                parsed = _parse_data_dictionary_sheet(uploaded.getvalue(), dict_sheet)
            except Exception as exc:
                st.warning(f"⚠️ Could not parse data dictionary sheet: {exc}")
                parsed = {}
            if parsed:
                st.caption(f"📖 Extracted {len(parsed)} column descriptions from **'{dict_sheet}'** "
                           "— review/edit below before mapping. Rows that don't match a real column are ignored.")
                dict_df = pd.DataFrame(
                    [{"Source Column": k, "Description": v} for k, v in parsed.items()]
                )
                edited_dict_df = st.data_editor(
                    dict_df, use_container_width=True, hide_index=True,
                    num_rows="dynamic", key="ts_dict_editor",
                )
                column_descriptions = {
                    str(row["Source Column"]).strip(): str(row["Description"]).strip()
                    for _, row in edited_dict_df.iterrows()
                    if row.get("Source Column") and row.get("Description")
                }
            else:
                st.info("No key/description pairs could be parsed from that sheet.")

    # Register source file in File Library
    try:
        from ui_components.file_store_manager import register_source_file
        register_source_file(
            source=uploaded.getvalue(),
            original_name=uploaded.name,
            org_name=org_name,
            object_name=object_name,
        )
    except Exception:
        pass

    # Read file
    with st.spinner("Reading file…"):
        try:
            if is_excel:
                df = pd.read_excel(io.BytesIO(uploaded.getvalue()), sheet_name=selected_sheet, dtype=str)
            elif uploaded.name.endswith(".json"):
                json_data = json.load(io.BytesIO(uploaded.getvalue()))
                if isinstance(json_data, list):
                    # Array of objects — convert to DataFrame
                    df = pd.DataFrame(json_data).astype(str)
                elif isinstance(json_data, dict):
                    # Single object or nested structure — try to extract records
                    if "records" in json_data and isinstance(json_data["records"], list):
                        df = pd.DataFrame(json_data["records"]).astype(str)
                    elif "data" in json_data and isinstance(json_data["data"], list):
                        df = pd.DataFrame(json_data["data"]).astype(str)
                    else:
                        # Treat single object as single row
                        df = pd.DataFrame([json_data]).astype(str)
                else:
                    st.error(f"❌ JSON must be an array of objects or dict with 'records'/'data' key.")
                    return
            else:
                try:
                    df = pd.read_csv(io.BytesIO(uploaded.getvalue()), dtype=str, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(io.BytesIO(uploaded.getvalue()), dtype=str, encoding="latin-1")
            df = df.where(pd.notnull(df), None)
        except Exception as exc:
            st.error(f"❌ Could not read file: {exc}")
            return

    sheet_suffix = f" from sheet **'{selected_sheet}'**" if is_excel else ""
    st.success(f"✅ Loaded **{len(df):,} rows × {len(df.columns)} columns**{sheet_suffix}")

    with st.expander("👁️ Preview source data (first 5 rows)", expanded=False):
        st.dataframe(df.head(5), use_container_width=True)

    if not registry.get_all_fields(object_name):
        st.info("ℹ️ Selected object schema is not cached yet. It will be synced automatically when mapping starts.")

    # Run mapping cascade
    if st.button("🚀 Run Field Mapping Cascade", use_container_width=True):
        # Ensure selected object schema exists in registry before running mapping tools.
        if not registry.get_all_fields(object_name):
            try:
                from ui_components.connection_manager import get_sf_connection as _get_org_conn
                sf_conn = _get_org_conn(org_name)
                if sf_conn:
                    from toolkit_sales_engine.metadata.salesforce_fetcher import SalesforceMetadataFetcher as _SFetcher
                    fetcher = _SFetcher(sf_conn=sf_conn)
                    obj_meta = fetcher.fetch_object(object_name)
                    registry.register_object(obj_meta)
                    registry.save()
                    engine._exact.refresh()
                    engine._synonym.refresh()
                else:
                    st.error("❌ No active Salesforce connection to sync selected object schema. Use SF Schema Sync first.")
                    return
            except Exception as exc:
                st.error(f"❌ Could not sync schema for {object_name}: {exc}")
                return

        with st.spinner("Running 5-tool mapping cascade (Exact → Synonym → Fuzzy → Embedding → LLM)…"):
            try:
                plan = engine.map_dataframe(df, object_name, column_descriptions=column_descriptions)
                st.session_state["ts_mapping_plan"] = plan
                st.session_state["ts_source_df"] = df
                st.session_state["ts_dup_keys_val"] = dup_keys
                st.session_state["ts_map_object_val"] = object_name
                st.success(f"✅ Mapped **{plan.mapped_count}/{plan.total_columns}** columns. "
                           f"Needs review: **{len(plan.needs_review)}**")
            except Exception as exc:
                st.error(f"❌ Mapping failed: {exc}")
                st.code(traceback.format_exc())
                return

    # Show mapping table if plan exists
    plan = st.session_state.get("ts_mapping_plan")
    if not plan:
        return

    st.divider()

    col_title, col_edit = st.columns([5, 1])
    with col_title:
        st.subheader("📋 Mapping Results")
    with col_edit:
        edit_mode = st.session_state.get("ts_mapping_edit_mode", False)
        st.markdown("<div style='padding-top:1.6rem'></div>", unsafe_allow_html=True)
        if st.button("✅ Done Editing" if edit_mode else "✏️ Edit Mapping",
                     use_container_width=True, key="ts_toggle_edit_mapping"):
            if edit_mode:
                # Leaving edit mode — persist whatever is currently selected in the
                # per-column dropdowns, otherwise the choices the user just made are
                # silently dropped and the stale pre-edit mapping is what survives.
                obj = st.session_state.get("ts_map_object_val", plan.object_name)
                saved = _apply_pending_overrides(plan, engine, obj)
                st.session_state["ts_mapping_plan"] = plan
                if saved:
                    st.toast(f"✅ Saved {saved} mapping change(s).")
            st.session_state["ts_mapping_edit_mode"] = not edit_mode
            st.rerun()

    edit_mode = st.session_state.get("ts_mapping_edit_mode", False)

    # Build editable table
    all_sf_fields = ["(unmapped)"] + [f.field_name for f in registry.get_all_fields(
        st.session_state.get("ts_map_object_val", plan.object_name)
    )]

    if edit_mode:
        st.info("✏️ **Edit mode is on** — every mapping below is editable, including high-confidence ones. "
                "Click **Save Overrides & Learn Synonyms** to keep your changes.")
    else:
        st.markdown("**Review and correct mappings below. "
                    "Changes to MEDIUM/LOW/UNMAPPED columns are auto-saved as synonyms. "
                    "Click ✏️ Edit Mapping to change any mapping, including high-confidence ones.**")

    overrides: dict[str, str] = {}
    confidences: dict[str, str] = {}
    for m in plan.mappings:
        # Determine display confidence and score based on original plan
        display_confidence = m.confidence_level
        display_score = m.score
        display_field = m.target_field

        with st.container():
            col_src, col_arrow, col_tgt, col_conf, col_score = st.columns([3, 0.5, 3, 1.5, 1])
            with col_src:
                st.markdown(f"**{m.source_column}**")
                st.caption(f"*{m.profile.semantic_type}* | {m.profile.null_pct}% null")
            with col_arrow:
                st.markdown("<div style='padding-top:8px'>→</div>", unsafe_allow_html=True)
            with col_tgt:
                if not edit_mode and m.confidence_level in ("HIGH",) and m.target_field:
                    st.markdown(f"`{m.target_field}`")
                    overrides[m.source_column] = m.target_field
                    display_field = m.target_field
                else:
                    default_idx = (all_sf_fields.index(m.target_field)
                                   if m.target_field and m.target_field in all_sf_fields else 0)
                    chosen = st.selectbox(
                        f"map_{m.source_column}",
                        options=all_sf_fields,
                        index=default_idx,
                        label_visibility="collapsed",
                        key=f"override_{m.source_column}",
                    )
                    overrides[m.source_column] = chosen if chosen != "(unmapped)" else None
                    display_field = chosen
                    # Reflect the dropdown's current selection whenever it's a saved
                    # manual review (m.human_reviewed) or a not-yet-saved pending
                    # change (chosen differs from the last-saved target_field).
                    # Otherwise keep showing the cascade tool's real match score.
                    if m.human_reviewed or chosen != m.target_field:
                        if chosen != "(unmapped)":
                            display_confidence = "HIGH"  # User manually selected = high confidence
                            display_score = 1.0
                        else:
                            display_confidence = "UNMAPPED"
                            display_score = 0.0
            confidences[m.source_column] = display_confidence
            with col_conf:
                conf_color = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴", "UNMAPPED": "⬜"}.get(display_confidence, "⬜")
                st.markdown(f"{conf_color} {display_confidence}")
            with col_score:
                st.markdown(f"`{display_score:.2f}`")

    # Display dynamic summary metrics based on current selections
    st.divider()
    updated_mapped = sum(1 for v in overrides.values() if v)
    updated_unmapped = sum(1 for v in overrides.values() if not v)
    updated_needs_review = sum(1 for c in confidences.values() if c in ("MEDIUM", "LOW"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Columns", plan.total_columns)
    c2.metric("✅ Mapped", updated_mapped)
    c3.metric("⚠️ Needs Review", updated_needs_review)
    c4.metric("❌ Unmapped", updated_unmapped)

    # Save overrides as synonyms
    if st.button("💾 Save Overrides & Learn Synonyms"):
        obj = st.session_state.get("ts_map_object_val", plan.object_name)
        saved = _apply_pending_overrides(plan, engine, obj, overrides=overrides)
        st.session_state["ts_mapping_plan"] = plan
        st.success(f"✅ Saved {saved} overrides as synonyms for future runs.")

    st.info("👉 Go to **Readiness Report** tab to run quality validation and download files.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — READINESS REPORT
# ══════════════════════════════════════════════════════════════════════════════

def _show_readiness_report(credentials, org_name, registry, engine, validator) -> None:
    st.subheader("3️⃣ Migration Readiness Report")

    plan = st.session_state.get("ts_mapping_plan")
    df: Optional[pd.DataFrame] = st.session_state.get("ts_source_df")

    if plan is None or df is None:
        st.info("Complete the **Upload & Map** step first.")
        return

    object_name = st.session_state.get("ts_map_object_val", plan.object_name)
    dup_keys_str = st.session_state.get("ts_dup_keys_val", "")
    dup_keys = [k.strip() for k in dup_keys_str.split(",") if k.strip()]

    sf_conn = _get_sf_connection(credentials, org_name)
    if not sf_conn:
        st.caption("ℹ️ No active Salesforce connection — lookup/reference fields will only get a "
                   "basic Id-format check instead of a real existence lookup. Connect via the sidebar "
                   "for a full check.")

    if st.button("▶ Run Quality Validation & Build Report", use_container_width=True):
        _run_and_render_report(df, plan, object_name, org_name, dup_keys, registry, validator, sf_conn)
    elif st.session_state.get("ts_report_data"):
        _render_report_from_state(org_name, object_name)


def _run_and_render_report(df, plan, object_name, org_name, dup_keys, registry, validator, sf_conn=None):
    with st.spinner("Running quality checks…"):
        try:
            # Build field mapping dict for validator
            field_map: dict = {}
            for m in plan.mappings:
                if m.target_field:
                    fmeta = registry.get_field(object_name, m.target_field)
                    if fmeta:
                        field_map[m.source_column] = fmeta

            quality_report = None
            if field_map:
                quality_report = validator.validate(
                    df=df, mapping=field_map,
                    upload_id=plan.upload_id, object_name=object_name,
                    sf_conn=sf_conn,
                )

            # Build row-violation index
            row_violations: dict[int, list[str]] = {}
            if quality_report:
                for fr in quality_report.field_results:
                    for v in fr.violations:
                        row_violations.setdefault(v.row_index, []).append(
                            f"[{fr.source_column}] {v.rule}: {v.message}"
                        )

            # Duplicate check
            if not dup_keys:
                mapped_cols = [m.source_column for m in plan.mappings if m.target_field]
                dup_keys = mapped_cols[:1] if mapped_cols else []
            dup_result = (validator.check_duplicates(df, dup_keys)
                          if dup_keys else {"duplicate_group_count": 0, "total_duplicate_rows": 0,
                                            "key_fields_used": [], "sample_duplicate_keys": [],
                                            "duplicate_row_indices": []})

            # Missing required fields
            all_sf_fields = registry.get_all_fields(object_name)
            mapped_sf_fields = [m.target_field for m in plan.mappings if m.target_field]
            missing_required = validator.check_coverage(
                source_columns=list(df.columns),
                mapped_columns=mapped_sf_fields,
                all_sf_fields=all_sf_fields,
            )

            # Gap analysis (unmapped columns)
            gap_specs = _build_gap_specs(plan, df)

            # Store for re-render
            st.session_state["ts_report_data"] = {
                "plan": plan, "quality_report": quality_report,
                "row_violations": row_violations, "dup_result": dup_result,
                "missing_required": missing_required, "gap_specs": gap_specs,
                "object_name": object_name, "df": df,
            }

        except Exception as exc:
            st.error(f"❌ Validation failed: {exc}")
            st.code(traceback.format_exc())
            return

    _render_report_from_state(org_name, object_name)


def _render_report_from_state(org_name, object_name):
    data = st.session_state.get("ts_report_data")
    if not data:
        return

    plan = data["plan"]
    quality_report = data["quality_report"]
    row_violations = data["row_violations"]
    dup_result = data["dup_result"]
    missing_required = data["missing_required"]
    gap_specs = data["gap_specs"]
    df = data["df"]

    # ── Summary Metrics ───────────────────────────────────────────────────────
    section1 = [m for m in plan.mappings if m.target_field and
                not any(v.row_index >= 0 for fr in (quality_report.field_results if quality_report else [])
                        for v in fr.violations if fr.source_column == m.source_column)]
    section2 = []
    if quality_report:
        for fr in quality_report.field_results:
            if fr.violations:
                mapping = next((m for m in plan.mappings if m.source_column == fr.source_column), None)
                if mapping:
                    section2.append((mapping, fr))
    # refined: section1 = mapped and NO violations
    mapped_with_violations = {fr.source_column for fr in (quality_report.field_results if quality_report else []) if fr.violations}
    section1 = [m for m in plan.mappings if m.target_field and m.source_column not in mapped_with_violations]
    section3 = [m for m in plan.mappings if not m.target_field]

    total_violations = quality_report.total_violations if quality_report else 0
    dup_count = dup_result.get("total_duplicate_rows", 0)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Columns", plan.total_columns)
    c2.metric("✅ Ready", len(section1))
    c3.metric("⚠️ Issues", len(section2))
    c4.metric("🆕 Gaps", len(section3))
    c5.metric("🔍 Dup Rows", dup_count)
    c6.metric("⚡ Violations", total_violations)

    # ── Download Bar ──────────────────────────────────────────────────────────
    st.divider()
    _show_download_bar(df, row_violations, plan, object_name, org_name)

    # ── Section 1: Ready ──────────────────────────────────────────────────────
    with st.expander(f"✅ Section 1 — Mapped & Valid ({len(section1)} columns)", expanded=True):
        st.caption("These columns are correctly mapped and pass all data quality checks.")
        if section1:
            rows = [{"Source Column": m.source_column, "SF Field": m.target_field,
                     "Method": m.method, "Score": f"{m.score:.2f}", "Confidence": m.confidence_level}
                    for m in section1]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No columns in this section.")

    # ── Section 2: Issues ─────────────────────────────────────────────────────
    with st.expander(f"⚠️ Section 2 — Mapped but Has Data Issues ({len(section2)} columns)", expanded=bool(section2)):
        st.caption("Columns mapped to SF fields but with data violations. Fix source data before loading.")
        for mapping, fr in section2:
            st.markdown(f"**{mapping.source_column}** → `{mapping.target_field}`")
            viol_rows = [{"Row": v.row_index, "Rule": v.rule,
                          "Value": v.value[:80], "Message": v.message[:120]}
                         for v in fr.violations[:20]]
            st.dataframe(pd.DataFrame(viol_rows), use_container_width=True, hide_index=True)
            if len(fr.violations) > 20:
                st.caption(f"… and {len(fr.violations)-20} more violations")
            st.divider()

    # ── Section 3: Gaps ───────────────────────────────────────────────────────
    with st.expander(f"🆕 Section 3 — Gap Analysis ({len(section3)} columns)", expanded=bool(section3)):
        st.caption("Source columns with no matching SF field — create these fields before migrating.")
        if section3:
            rows = []
            for m in section3:
                spec = gap_specs.get(m.source_column, {})
                rows.append({
                    "Source Column": m.source_column,
                    "Recommended SF Type": spec.get("recommended_sf_type", "Text"),
                    "Sample Values": str(spec.get("sample_values", [])[:3]),
                    "Suggested API Name": spec.get("suggested_api_name", ""),
                    "Required?": "Yes" if spec.get("required_recommendation") else "No",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Section 4: Pre-load ───────────────────────────────────────────────────
    with st.expander("🛡 Section 4 — Pre-Load Validation", expanded=True):
        col_dup, col_req = st.columns(2)
        with col_dup:
            st.markdown("#### 🔍 Duplicate Detection")
            st.write(f"**Key Fields:** {', '.join(dup_result.get('key_fields_used', []))}")
            st.write(f"**Duplicate Groups:** {dup_result.get('duplicate_group_count', 0)}")
            st.write(f"**Duplicate Rows:** {dup_result.get('total_duplicate_rows', 0)}")
            if dup_result.get("sample_duplicate_keys"):
                st.write("**Sample Duplicate Keys:**", dup_result["sample_duplicate_keys"][:5])
        with col_req:
            st.markdown("#### ❗ Missing Required SF Fields")
            if missing_required:
                for f in missing_required[:10]:
                    st.warning(f"• **{f['field_name']}** ({f['label']}) — {f['data_type']}")
            else:
                st.success("✅ All required SF fields are covered.")


def _show_download_bar(df, row_violations, plan, object_name, org_name):
    success_rows = [i for i in df.index if i not in row_violations]
    error_rows = list(row_violations.keys())
    st.markdown(f"**📥 Download validated files:** "
                f"✅ `{len(success_rows)}` success rows | ❌ `{len(error_rows)}` error rows")

    col_dl1, col_dl2, col_dl3 = st.columns(3)

    with col_dl1:
        # Success CSV — original columns/records only, no extra status column
        success_df = df.loc[success_rows].copy()
        buf = io.StringIO()
        success_df.to_csv(buf, index=False)
        fname_success = f"success_{plan.upload_id[:8]}.csv"
        st.download_button(
            "⬇ Download success.csv",
            data=buf.getvalue().encode("utf-8"),
            file_name=fname_success,
            mime="text/csv",
            use_container_width=True,
            on_click=lambda: _save_and_register(
                success_df, fname_success, org_name, object_name,
                "Migration Readiness — Success", len(success_rows), "success"
            ),
        )

    with col_dl2:
        # Error CSV
        error_df = df.loc[error_rows].copy()
        error_df["sf__Error"] = [" | ".join(row_violations[i]) for i in error_rows]
        buf2 = io.StringIO()
        error_df.to_csv(buf2, index=False)
        fname_error = f"error_{plan.upload_id[:8]}.csv"
        st.download_button(
            "⬇ Download error.csv",
            data=buf2.getvalue().encode("utf-8"),
            file_name=fname_error,
            mime="text/csv",
            use_container_width=True,
            on_click=lambda: _save_and_register(
                error_df, fname_error, org_name, object_name,
                "Migration Readiness — Errors", len(error_rows), "error"
            ),
        )

    with col_dl3:
        # JSON report
        report_dict = {
            "upload_id": plan.upload_id,
            "object_name": object_name,
            "org_name": org_name,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_columns": plan.total_columns,
                "mapped_count": plan.mapped_count,
                "total_rows": len(df),
                "success_rows": len(success_rows),
                "error_rows": len(error_rows),
            },
            "mappings": plan.to_dict()["mappings"],
        }
        fname_json = f"readiness_report_{plan.upload_id[:8]}.json"
        st.download_button(
            "⬇ Download JSON Report",
            data=json.dumps(report_dict, indent=2, default=str).encode("utf-8"),
            file_name=fname_json,
            mime="application/json",
            use_container_width=True,
        )

    # Auto-persist success file to file_store so other tabs can use it
    _auto_persist_success(df, success_rows, row_violations, plan, object_name, org_name)


def _auto_persist_success(df, success_rows, row_violations, plan, object_name, org_name):
    """Silently save success.csv to disk and register in File Library."""
    persist_key = f"ts_persisted_{plan.upload_id}"
    if st.session_state.get(persist_key):
        return  # already persisted this run
    try:
        success_df = df.loc[success_rows].copy()
        fname = f"success_{plan.upload_id[:8]}.csv"
        fpath = str(_OUTPUT_DIR / fname)
        success_df.to_csv(fpath, index=False)
        _register_output(fpath, fname, org_name, object_name,
                         "Migration Readiness", len(success_rows), "success")

        # Also save error file
        error_rows = list(row_violations.keys())
        if error_rows:
            error_df = df.loc[error_rows].copy()
            error_df["sf__Error"] = [" | ".join(row_violations[i]) for i in error_rows]
            efname = f"error_{plan.upload_id[:8]}.csv"
            efpath = str(_OUTPUT_DIR / efname)
            error_df.to_csv(efpath, index=False)
            _register_output(efpath, efname, org_name, object_name,
                             "Migration Readiness", len(error_rows), "error")

        st.session_state[persist_key] = True
        st.success(
            f"💾 **Files saved permanently** to File Library. "
            f"Go to **Data Operations** to load `{fname}` into Salesforce."
        )
    except Exception as exc:
        logger.warning("Auto-persist failed: %s", exc)


def _save_and_register(df_out, fname, org_name, object_name, op_type, row_count, status):
    try:
        fpath = str(_OUTPUT_DIR / fname)
        df_out.to_csv(fpath, index=False)
        _register_output(fpath, fname, org_name, object_name, op_type, row_count, status)
    except Exception as exc:
        logger.warning("Save & register failed: %s", exc)


def _build_gap_specs(plan, df) -> dict:
    """Infer new-field specs for unmapped columns."""
    from toolkit_sales_engine.profiler.type_detector import detect_semantic_type, SemanticType
    sf_type_map = {
        "date": "Date", "datetime": "DateTime", "email": "Email", "phone": "Phone",
        "currency": "Currency", "percent": "Percent", "integer": "Number (integer)",
        "float": "Number (decimal)", "boolean": "Checkbox", "picklist": "Picklist",
        "identifier": "Text", "name": "Text", "address": "TextArea", "text": "TextArea(Long)",
        "unknown": "Text",
    }
    specs = {}
    for m in plan.mappings:
        if m.target_field is None and m.source_column in df.columns:
            series = df[m.source_column].dropna().astype(str)
            sem = detect_semantic_type(m.source_column, df[m.source_column])
            distinct = sorted(series.unique().tolist())[:10]
            max_len = int(series.str.len().max()) if len(series) > 0 else 0
            is_picklist = len(distinct) <= 20 and len(distinct) > 0
            api_name = m.source_column.strip().replace(" ", "_").replace("-", "_") + "__c"
            specs[m.source_column] = {
                "recommended_sf_type": "Picklist" if is_picklist else sf_type_map.get(sem, "Text"),
                "sample_values": distinct[:5],
                "suggested_api_name": api_name,
                "max_length": max_len,
                "required_recommendation": False,
            }
    return specs
