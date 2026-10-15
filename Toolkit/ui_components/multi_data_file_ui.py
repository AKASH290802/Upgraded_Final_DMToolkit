"""
Multi Data File
===============
Standalone tab: upload one client file containing rows/columns for multiple
Salesforce objects, assign fields to objects (auto + drag-and-drop/manual),
set validation priority (parent -> child), and validate each object
independently.

Does not modify or import any other tab's Streamlit page module. Reuses:
- toolkit_sales_engine (metadata registry + 5-tool mapping cascade)
- ui_components.utils (SF connection/object helpers)

This tab is validation-only in this phase — no Salesforce load is performed.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from ui_components.utils import establish_sf_connection, get_salesforce_objects

logger = logging.getLogger(__name__)

try:
    from streamlit_sortables import sort_items
    _SORTABLES_AVAILABLE = True
except ImportError:
    _SORTABLES_AVAILABLE = False


def _load_engine():
    """Lazy-import the shared metadata registry + mapping engine."""
    import sys
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    from toolkit_sales_engine.metadata.registry import MetadataRegistry
    from toolkit_sales_engine.metadata.salesforce_fetcher import SalesforceMetadataFetcher
    from toolkit_sales_engine.mapper.engine import MappingEngine

    if "ts_registry" not in st.session_state:
        st.session_state.ts_registry = MetadataRegistry()
    if "ts_engine" not in st.session_state:
        st.session_state.ts_engine = MappingEngine(st.session_state.ts_registry)

    return st.session_state.ts_registry, st.session_state.ts_engine, SalesforceMetadataFetcher


def show_multi_data_file(credentials: dict) -> None:
    st.title("🧩 Multi Data File")
    st.markdown(
        "Upload one client file that contains data for **multiple Salesforce objects**. "
        "Select the objects present, assign fields to each object, set a validation "
        "priority, then validate each object independently. **This tab is validation-only** — "
        "no data is loaded to Salesforce here."
    )

    if not st.session_state.get("current_org"):
        st.warning("⚠️ Please select a Salesforce organisation from the sidebar first.")
        return

    org_name = st.session_state.current_org
    sf_conn = establish_sf_connection(credentials, org_name)
    if not sf_conn:
        return

    try:
        registry, engine, SFetcher = _load_engine()
    except Exception as exc:
        st.error(f"❌ Failed to load mapping engine: {exc}")
        return

    _step1_upload()
    if st.session_state.get("mdf_source_df") is None:
        return

    st.divider()
    _step2_select_objects(sf_conn)
    if not st.session_state.get("mdf_selected_objects"):
        return

    st.divider()
    _step3_set_priority(sf_conn)

    st.divider()
    _step4_field_assignment(sf_conn, registry, engine, SFetcher)
    if not st.session_state.get("mdf_field_plan"):
        return

    st.divider()
    _step5_validate(sf_conn)


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — UPLOAD
# ══════════════════════════════════════════════════════════════════════════

def _reset_downstream_state(from_step: int) -> None:
    keys_by_step = {
        2: ["mdf_selected_objects", "mdf_object_priority", "mdf_field_plan", "mdf_validation_results"],
        3: ["mdf_field_plan", "mdf_validation_results"],
        4: ["mdf_validation_results"],
    }
    for step in range(from_step, 5):
        for key in keys_by_step.get(step, []):
            st.session_state.pop(key, None)


def _step1_upload() -> None:
    st.subheader("1️⃣ Upload Client File")
    uploaded = st.file_uploader(
        "Upload CSV, Excel, or PSV file containing data for multiple objects",
        type=["csv", "xlsx", "xls", "psv"],
        key="mdf_uploaded_file",
    )
    if not uploaded:
        return

    if st.session_state.get("mdf_uploaded_file_name") != uploaded.name:
        try:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded, dtype=str)
            elif uploaded.name.endswith(".psv"):
                df = pd.read_csv(uploaded, sep="|", dtype=str)
            else:
                df = pd.read_excel(uploaded, dtype=str)  # first sheet only in this phase

            st.session_state.mdf_source_df = df
            st.session_state.mdf_uploaded_file_name = uploaded.name
            _reset_downstream_state(from_step=2)
            st.success(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
        except Exception as exc:
            st.error(f"❌ Could not read file: {exc}")
            return

    df = st.session_state.get("mdf_source_df")
    if df is not None:
        with st.expander("📊 Preview uploaded data", expanded=False):
            st.dataframe(df.head(10), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# STEP 2 — SELECT OBJECTS
# ══════════════════════════════════════════════════════════════════════════

def _step2_select_objects(sf_conn) -> None:
    st.subheader("2️⃣ Select Salesforce Objects Present in This File")
    all_objects = get_salesforce_objects(sf_conn, filter_custom=False)
    if not all_objects:
        st.error("❌ Could not fetch Salesforce objects for this org.")
        return

    selected = st.multiselect(
        "Select the objects whose data appears in the uploaded file",
        options=all_objects,
        default=st.session_state.get("mdf_selected_objects", []),
        key="mdf_object_multiselect",
        help="Example: Inventory, Warranty Registration, Warranty Coverage, Claim",
    )

    if selected != st.session_state.get("mdf_selected_objects"):
        st.session_state.mdf_selected_objects = selected
        st.session_state.mdf_object_priority = list(selected)  # default order = selection order
        _reset_downstream_state(from_step=3)


# ══════════════════════════════════════════════════════════════════════════
# STEP 3 — SET PRIORITY
# ══════════════════════════════════════════════════════════════════════════

def _step3_set_priority(sf_conn) -> None:
    st.subheader("3️⃣ Set Validation Priority (Parent → Child)")
    st.caption("Reorder so parent objects come before the children that reference them.")

    order = st.session_state.get("mdf_object_priority") or list(st.session_state.mdf_selected_objects)

    for idx, obj_name in enumerate(order):
        col_pos, col_name, col_up, col_down = st.columns([0.6, 3, 0.5, 0.5])
        with col_pos:
            st.write(f"**{idx + 1}.**")
        with col_name:
            st.write(obj_name)
        with col_up:
            if idx > 0 and st.button("▲", key=f"mdf_up_{obj_name}"):
                order[idx - 1], order[idx] = order[idx], order[idx - 1]
                st.session_state.mdf_object_priority = order
                _reset_downstream_state(from_step=4)
                st.rerun()
        with col_down:
            if idx < len(order) - 1 and st.button("▼", key=f"mdf_down_{obj_name}"):
                order[idx + 1], order[idx] = order[idx], order[idx + 1]
                st.session_state.mdf_object_priority = order
                _reset_downstream_state(from_step=4)
                st.rerun()

    st.session_state.mdf_object_priority = order

    from toolkit_sales_engine.multi_object.dependency_planner import validate_priority
    warnings = validate_priority(sf_conn, order)
    if warnings:
        for w in warnings:
            st.warning(w)
    else:
        st.success("✅ Priority order respects detected lookup/master-detail relationships.")


# ══════════════════════════════════════════════════════════════════════════
# STEP 4 — FIELD ASSIGNMENT (DRAG-AND-DROP / DROPDOWN FALLBACK)
# ══════════════════════════════════════════════════════════════════════════

def _item_label(a) -> str:
    if a.assigned_object is None:
        return f"{a.source_column} · unassigned"
    flag = " ⚠️ review" if a.needs_review else ""
    return f"{a.source_column} · {a.confidence * 100:.0f}% ({a.method}){flag}"


def _label_to_column(label: str) -> str:
    return label.split(" · ")[0]


def _render_coverage_summary(plan) -> None:
    stats = plan.coverage_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mapped", f"{stats['mapped']}/{stats['mappable']}", f"{stats['coverage_pct']}%")
    col2.metric("Needs Review", stats['needs_review'])
    col3.metric("Excluded (system columns)", stats['excluded'])
    col4.metric("Total Columns", stats['total'])

    excluded = plan.excluded_columns()
    if excluded:
        with st.expander(f"🚫 {len(excluded)} column(s) excluded as source-export artifacts", expanded=False):
            for a in excluded:
                st.caption(f"{a.source_column} — {a.reasoning}")


def _step4_field_assignment(sf_conn, registry, engine, SFetcher) -> None:
    st.subheader("4️⃣ Assign Fields to Objects")
    st.caption(
        "Fields are auto-assigned using exact/synonym/fuzzy/embedding/LLM matching. "
        "Drag a field into a different object's box to reassign it "
        "(or use the dropdown fallback below if drag-and-drop is unavailable)."
    )

    df = st.session_state.mdf_source_df
    object_names = st.session_state.mdf_object_priority

    if st.button("🤖 Run Auto-Mapping", use_container_width=True) or "mdf_field_plan" not in st.session_state:
        from toolkit_sales_engine.multi_object.field_assignment_engine import (
            ensure_objects_synced, assign_fields,
        )
        from toolkit_sales_engine.multi_object.models import MultiObjectPlan, ObjectSelection

        with st.spinner("Fetching schema and running mapping cascade for all selected objects…"):
            ensure_objects_synced(sf_conn, registry, object_names, SFetcher)
            assignments = assign_fields(df, registry, engine, object_names)

        st.session_state.mdf_field_plan = MultiObjectPlan(
            upload_id=str(uuid.uuid4()),
            selected_objects=[ObjectSelection(name, i + 1) for i, name in enumerate(object_names)],
            field_assignments=assignments,
        )
        st.session_state.pop("mdf_validation_results", None)

    plan = st.session_state.mdf_field_plan
    _render_coverage_summary(plan)

    if _SORTABLES_AVAILABLE:
        _render_dragdrop_workbench(plan, object_names, registry, engine, df)
    else:
        _render_dropdown_workbench(plan, object_names, registry)

    _render_needs_review_section(plan, registry)


def _render_dragdrop_workbench(plan, object_names, registry, engine, df) -> None:
    by_column = {a.source_column: a for a in plan.field_assignments}

    containers = []
    for obj_name in object_names:
        items = [_item_label(a) for a in plan.assignments_for(obj_name)]
        containers.append({"header": obj_name, "items": items})
    containers.append({"header": "Unassigned", "items": [_item_label(a) for a in plan.unassigned()]})

    result = sort_items(containers, multi_containers=True, key="mdf_field_dragdrop")

    from toolkit_sales_engine.multi_object.field_assignment_engine import suggest_field_for_column

    moved = []
    for container in result:
        new_object = None if container["header"] == "Unassigned" else container["header"]
        for label in container["items"]:
            col = _label_to_column(label)
            if by_column[col].assigned_object != new_object:
                moved.append((col, new_object))

    if moved:
        for col, new_object in moved:
            a = by_column[col]
            a.assigned_object = new_object
            a.method = "manual"
            a.user_overridden = True
            a.confidence = 0.0
            a.assigned_field = suggest_field_for_column(engine, df, col, new_object) if new_object else None
            a.reasoning = ("Manually moved by user; confirm/adjust the target field below."
                           if new_object else "Manually unassigned by user.")
        st.session_state.mdf_field_plan.field_assignments = list(by_column.values())
        st.session_state.pop("mdf_validation_results", None)
        st.rerun()

    _render_manual_field_confirmations(plan, registry)


def _render_manual_field_confirmations(plan, registry) -> None:
    manual = [a for a in plan.field_assignments if a.user_overridden and a.assigned_object]
    if not manual:
        return
    st.markdown("##### 🔧 Confirm Fields for Manually Reassigned Columns")
    for a in manual:
        field_names = [f.field_name for f in registry.get_all_fields(a.assigned_object)]
        options = ["-- Select field --"] + field_names
        current_idx = options.index(a.assigned_field) if a.assigned_field in options else 0
        chosen = st.selectbox(
            f"'{a.source_column}' → {a.assigned_object}",
            options=options,
            index=current_idx,
            key=f"mdf_manual_field_{a.source_column}",
        )
        a.assigned_field = None if chosen == "-- Select field --" else chosen


def _render_needs_review_section(plan, registry) -> None:
    """Low-confidence or tied auto-mappings: already counted toward coverage,
    but surfaced here so the user can confirm or correct them explicitly."""
    review_items = [a for a in plan.needs_review_items() if not a.user_overridden]
    if not review_items:
        return

    st.markdown("##### ⚠️ Needs Review — Low Confidence or Ambiguous Matches")
    st.caption("These are already assigned (counted toward coverage) but should be confirmed or corrected.")

    for a in review_items:
        col_info, col_action = st.columns([3, 2])
        with col_info:
            alt_note = (f" · alternate: {a.alternate_object}.{a.alternate_field} ({a.alternate_confidence*100:.0f}%)"
                        if a.alternate_object else "")
            st.write(f"**{a.source_column}** → `{a.assigned_object}.{a.assigned_field}` "
                     f"({a.confidence*100:.0f}% {a.method}){alt_note}")
        with col_action:
            if st.button("✅ Confirm as-is", key=f"mdf_review_confirm_{a.source_column}"):
                a.needs_review = False
                st.rerun()


def _render_dropdown_workbench(plan, object_names, registry) -> None:
    st.info("ℹ️ Drag-and-drop component not installed — using dropdown-based reassignment instead.")
    options_objects = ["Unassigned"] + object_names

    for a in plan.field_assignments:
        if a.excluded:
            continue
        original_object, original_field = a.assigned_object, a.assigned_field

        col_src, col_obj, col_field, col_conf = st.columns([2, 2, 2, 1.5])
        with col_src:
            st.write(f"**{a.source_column}**")
        with col_obj:
            current_obj = original_object or "Unassigned"
            chosen_obj = st.selectbox(
                "Object", options_objects,
                index=options_objects.index(current_obj) if current_obj in options_objects else 0,
                key=f"mdf_dd_obj_{a.source_column}",
                label_visibility="collapsed",
            )
        new_object = None if chosen_obj == "Unassigned" else chosen_obj

        with col_field:
            new_field = None
            if new_object:
                field_names = [f.field_name for f in registry.get_all_fields(new_object)]
                options_fields = ["-- Select --"] + field_names
                current_field = original_field if original_field in options_fields else "-- Select --"
                chosen_field = st.selectbox(
                    "Field", options_fields,
                    index=options_fields.index(current_field),
                    key=f"mdf_dd_field_{a.source_column}",
                    label_visibility="collapsed",
                )
                new_field = None if chosen_field == "-- Select --" else chosen_field
            else:
                st.write("—")
        with col_conf:
            if original_object:
                flag = " ⚠️" if a.needs_review else ""
                st.caption(f"{a.confidence * 100:.0f}% {a.method}{flag}")
                if a.needs_review and a.alternate_object:
                    st.caption(f"alt: {a.alternate_object}.{a.alternate_field} ({a.alternate_confidence * 100:.0f}%)")
            else:
                st.caption("unassigned")

        if new_object != original_object or new_field != original_field:
            a.assigned_object = new_object
            a.assigned_field = new_field
            a.method = "manual"
            a.user_overridden = True
            a.needs_review = False
            a.confidence = 0.0


# ══════════════════════════════════════════════════════════════════════════
# STEP 5 — VALIDATE (PER OBJECT, IN PRIORITY ORDER)
# ══════════════════════════════════════════════════════════════════════════

def _step5_validate(sf_conn) -> None:
    st.subheader("5️⃣ Validate Each Object (in Priority Order)")

    plan = st.session_state.mdf_field_plan
    unassigned = plan.unassigned()
    if unassigned:
        with st.expander(f"⚠️ {len(unassigned)} unassigned column(s) — excluded from validation", expanded=False):
            st.write(", ".join(a.source_column for a in unassigned))

    run_clicked = st.button("✅ Build Datasets & Validate", type="primary", use_container_width=True)

    if not run_clicked:
        results = st.session_state.get("mdf_validation_results")
        if results:
            _render_validation_results(results)
        return

    from toolkit_sales_engine.multi_object.object_dataset_builder import build_all_object_datasets
    from toolkit_sales_engine.multi_object.multi_object_validator import validate_object_dataset

    df = st.session_state.mdf_source_df
    object_datasets = build_all_object_datasets(df, plan)

    results = {}
    for obj_name in st.session_state.mdf_object_priority:
        with st.spinner(f"Validating {obj_name}…"):
            results[obj_name] = validate_object_dataset(sf_conn, obj_name, object_datasets.get(obj_name))

    st.session_state.mdf_validation_results = results
    _render_validation_results(results)


def _render_validation_results(results: dict) -> None:
    st.markdown("#### 📋 Validation Summary")
    cols = st.columns(len(results)) if results else []
    for col, (obj_name, res) in zip(cols, results.items()):
        with col:
            st.metric(obj_name, f"{res.passed}/{res.total_records} passed")

    for obj_name, res in results.items():
        header = f"{'✅' if res.failed == 0 else '❌'} {obj_name} — {res.passed} passed, {res.failed} failed"
        with st.expander(header, expanded=res.failed > 0):
            if res.validated_df is not None and not res.validated_df.empty:
                st.dataframe(res.validated_df.head(20), use_container_width=True)

            if res.error_rows:
                err_df = pd.DataFrame(res.error_rows)
                st.dataframe(err_df, use_container_width=True)
                st.download_button(
                    f"📥 Download {obj_name} error report",
                    data=err_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{obj_name}_validation_errors.csv",
                    mime="text/csv",
                    key=f"mdf_dl_err_{obj_name}",
                )

            if res.validated_df is not None and not res.validated_df.empty:
                st.download_button(
                    f"📥 Download {obj_name} validated dataset",
                    data=res.validated_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{obj_name}_validated.csv",
                    mime="text/csv",
                    key=f"mdf_dl_data_{obj_name}",
                )
