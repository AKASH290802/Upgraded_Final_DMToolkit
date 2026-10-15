import streamlit as st
import pandas as pd
import os
import sys
import json
import requests
from typing import Dict, Optional, List
import re
from datetime import datetime
import shutil
from io import BytesIO
import streamlit.components.v1 as components

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)

# File Library integration (graceful — does not break if module unavailable)
try:
    from ui_components.file_library_ui import show_file_picker_inline
    from ui_components.file_store_manager import register_source_file, register_output_file
except ImportError:
    try:
        from file_library_ui import show_file_picker_inline
        from file_store_manager import register_source_file, register_output_file
    except ImportError:
        show_file_picker_inline = None
        register_source_file = None
        register_output_file = None

# Lookup resolution functions are imported locally from data_operations when needed

# Import lookup resolution validator for enhanced reference field validation
try:
    from validation_script.lookup_resolution_validator import (
        resolve_lookup_value_to_salesforce_id,
        get_lookup_resolution_candidates,
        validate_lookup_field_with_resolution
    )
except ImportError:
    # Fallback if module not available
    pass

# File Management Utilities
def get_validation_folder_path(validation_type: str, org_name: str = None, object_name: str = None) -> str:
    """Get standardized folder path for validation results"""
    timestamp = datetime.now().strftime('%Y%m%d')
    
    if org_name and object_name:
        folder_path = os.path.join('Validation', validation_type, org_name, object_name, timestamp)
    elif org_name:
        folder_path = os.path.join('Validation', validation_type, org_name, timestamp)
    else:
        folder_path = os.path.join('Validation', validation_type, timestamp)
    
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def get_timestamped_filename(base_name: str, file_extension: str = 'csv') -> str:
    """Generate filename with timestamp"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{base_name}_{timestamp}.{file_extension}"

def _bump_validation_results_version() -> None:
    """Tell the cached Validation Summary that a new result exists."""
    st.session_state['_validation_results_version'] = st.session_state.get('_validation_results_version', 0) + 1


def save_validation_results_to_file(df: pd.DataFrame, folder_path: str, filename: str, file_type: str = 'csv') -> str:
    """Save validation results to file and return full path"""
    _bump_validation_results_version()
    full_path = os.path.join(folder_path, filename)

    if file_type.lower() == 'csv':
        df.to_csv(full_path, index=False)
    elif file_type.lower() == 'xlsx':
        df.to_excel(full_path, index=False)

    # Register in File Library
    if register_output_file:
        try:
            abs_path = os.path.abspath(full_path)
            # Infer operation type from folder path
            op_type = 'Validation'
            if 'genai' in folder_path.lower():
                op_type = 'GenAI Validation'
            elif 'schema' in folder_path.lower():
                op_type = 'Schema Validation'
            elif 'enhanced' in folder_path.lower():
                op_type = 'Enhanced Validation'
            register_output_file(
                abs_path,
                original_name=filename,
                org_name=st.session_state.get('current_org', 'unknown'),
                object_name=st.session_state.get('current_object', ''),
                operation_type=op_type,
                row_count=len(df),
                status='generated',
            )
        except Exception:
            pass

    return full_path

def display_file_location_info(folder_path: str, saved_files: list = None):
    """Display file location information in UI"""
    st.success("🎉 **Files saved successfully!**")
    
    with st.expander("📁 File Locations", expanded=True):
        st.write(f"**📂 Folder Location:**")
        st.code(os.path.abspath(folder_path))

# Import GenAI validation functions
try:
    from validation_script.GenAI_Validation import (
        extract_validation_rules_to_csv,
        generate_validation_bundle_from_dataframe
    )
except ImportError:
    # Fallback if import fails
    extract_validation_rules_to_csv = None
    generate_validation_bundle_from_dataframe = None

from .utils import (
    establish_sf_connection,
    get_salesforce_objects,
    get_object_description,
    show_processing_status,
    display_dataframe_with_download,
    validate_file_upload,
    load_data_file,
    create_progress_tracker
)

from .sf_validation_client import create_sf_validation_client

# Guided flow: Step 2 reads the Step 1 dataset and publishes its result for Step 3.
from ui_components import step_flow
from ui_components import connection_manager
from ui_components.navigation import STEP3_PAGE, request_page


def _suggest_validation_field_mappings(csv_columns: list, sf_fields: list[dict]) -> dict:
    """Suggest mappings using the same conservative rules as Enhanced Validation."""
    def normalize(value: str) -> str:
        return ''.join(ch for ch in str(value).lower() if ch.isalnum())

    suggestions = {}
    for csv_col in csv_columns:
        csv_col_clean = normalize(csv_col)
        best_match = None
        best_score = 0
        # 'Owner.Name' / 'Parent.Name' are fields of a RELATED record (from a SOQL
        # relationship query): never map them onto this object's Name by similarity.
        if '.' in str(csv_col):
            continue

        for sf_field in sf_fields:
            sf_name = sf_field['name']
            sf_name_clean = normalize(sf_name)
            sf_label_clean = normalize(sf_field.get('label', ''))

            score = 0
            # Exact normalized matches must win before any containment rule.
            if csv_col_clean == sf_name_clean:
                score = 100
            elif csv_col_clean == sf_label_clean and csv_col_clean:
                score = 90
            elif csv_col_clean in sf_name_clean and len(csv_col_clean) >= 4:
                score = 3
            elif sf_name_clean in csv_col_clean and len(sf_name_clean) >= 4:
                score = 3
            elif csv_col_clean in sf_label_clean and len(csv_col_clean) >= 4:
                score += 2
            elif sf_label_clean in csv_col_clean and len(sf_label_clean) >= 4:
                score += 2
            elif any(word in sf_name_clean for word in str(csv_col).lower().replace('_', ' ').replace('-', ' ').split() if len(word) > 2):
                score += 1

            if score > best_score:
                best_score = score
                best_match = sf_field

        # Common source labels for Salesforce's RecordTypeId system field.
        if csv_col_clean in {'recordtype', 'recordtypeid'}:
            record_type_field = next(
                (field for field in sf_fields if normalize(field['name']) == 'recordtypeid'),
                None,
            )
            if record_type_field:
                best_match = record_type_field

        if best_match and best_score > 0 or best_match and csv_col_clean in {'recordtype', 'recordtypeid'}:
            suggestions[csv_col] = best_match['name']
    return suggestions


def _correct_known_validation_mappings(mappings: dict, sf_fields: list[dict]) -> dict:
    """Repair the known RecordTypeId-to-Id collision in existing mappings."""
    if not mappings:
        return mappings
    field_by_normalized = {
        ''.join(ch for ch in field['name'].lower() if ch.isalnum()): field['name']
        for field in sf_fields
    }
    record_type_field = field_by_normalized.get('recordtypeid')
    if not record_type_field:
        return mappings
    for source_column, target_field in list(mappings.items()):
        source_normalized = ''.join(ch for ch in str(source_column).lower() if ch.isalnum())
        if source_normalized in {'recordtype', 'recordtypeid'} and target_field == 'Id':
            mappings[source_column] = record_type_field
    return mappings


# ---------------------------------------------------------------------------
# Guided flow (Step 2) helpers
# ---------------------------------------------------------------------------

FLOW_SOURCE_OPTION = "📦 Step 1 dataset"
FLOW_OTHER_SOURCE_CAPTION = (
    "ℹ️ Results from this source will not unlock Step 3 — only a validation of the "
    "Step 1 dataset does. To use this data in the guided flow, load it in Step 1."
)
_SF_ID_RE = re.compile(r'^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$')


def _flow_dataset_id() -> Optional[str]:
    """Id of the confirmed Step 1 dataset, or None."""
    dataset = step_flow.get_flow_dataset() if step_flow.step1_done() else None
    return dataset['id'] if dataset else None


def _flow_origin() -> Optional[str]:
    """Origin tag stored next to a tab's data when that data IS the Step 1 dataset."""
    dataset_id = _flow_dataset_id()
    return f"flow:{dataset_id}" if dataset_id else None


def _is_flow_origin(origin) -> bool:
    return bool(origin) and origin == _flow_origin()


def _is_any_flow_origin(origin) -> bool:
    """Data came from a Step 1 dataset (the current one or an earlier one)."""
    return isinstance(origin, str) and origin.startswith("flow:")


def _flow_df() -> Optional[pd.DataFrame]:
    """The Step 1 DataFrame with a clean RangeIndex (the validators address rows by position)."""
    df = step_flow.get_flow_df()
    return df.reset_index(drop=True) if df is not None else None


def _seed_flow_widget(key: str, options: list, flow_value=None) -> None:
    """Seed a radio/selectbox value BEFORE the widget is drawn.

    - flow_value is applied once per Step 1 dataset, so a later choice by the user sticks;
    - otherwise the user's last choice is restored (Streamlit drops widget state when the
      page is not drawn, so it is mirrored in a plain session key);
    - a stale value that is no longer among the options is dropped.
    """
    ss = st.session_state
    mirror_key = f"_flowseed_{key}"
    dataset_id = _flow_dataset_id()
    mirror = dict(ss.get(mirror_key) or {})
    if flow_value is not None and dataset_id and flow_value in options and mirror.get('ds') != dataset_id:
        ss[key] = flow_value
    elif key not in ss and mirror.get('value') in options:
        ss[key] = mirror['value']
    if key in ss and ss[key] not in options:
        del ss[key]
    mirror['ds'] = dataset_id
    ss[mirror_key] = mirror


def _remember_flow_widget(key: str, value) -> None:
    """Store the value a seeded widget returned (see _seed_flow_widget)."""
    mirror = dict(st.session_state.get(f"_flowseed_{key}") or {})
    mirror['value'] = value
    st.session_state[f"_flowseed_{key}"] = mirror


def _flow_source_radio(label: str, base_options: list, key: str, **kwargs) -> str:
    """Data source of a validation tab.

    In the guided flow the data ALWAYS comes from Step 1: once a Step 1 dataset is
    confirmed no source picker is drawn (nothing is loaded or queried again here).
    The picker is only drawn when there is no Step 1 dataset.
    """
    if step_flow.step1_done():
        st.session_state[key] = FLOW_SOURCE_OPTION   # plain value; the radio is not drawn
        _remember_flow_widget(key, FLOW_SOURCE_OPTION)
        return FLOW_SOURCE_OPTION
    options = list(base_options)
    _seed_flow_widget(key, options)
    choice = st.radio(label, options, key=key, **kwargs)
    _remember_flow_widget(key, choice)
    return choice


def _show_flow_dataset_in_use() -> None:
    dataset = step_flow.get_flow_dataset()
    if dataset:
        st.success(f"📦 Validating the Step 1 dataset **{dataset['name']}** — {dataset['rows']:,} rows × "
                   f"{dataset['cols']} columns from {dataset['source_label']}")
        st.caption("To validate different data or another object, go back to Step 1 (⬅️ Back at the bottom).")


def _flow_object_locked(options: list) -> bool:
    """True when the Step 1 target object fixes this tab's object selectbox."""
    return bool(step_flow.step1_done() and step_flow.get_flow_object() in options)


def _seed_flow_object(key: str, options: list) -> None:
    """Pre-select the Step 1 target object in a tab's object selectbox (locked while it applies)."""
    if _flow_object_locked(options):
        st.session_state[key] = step_flow.get_flow_object()
        return
    _seed_flow_widget(key, options, step_flow.get_flow_object())


def _set_current_object(object_name: Optional[str]) -> None:
    """Tabs keep the sidebar 'current object' in sync, except while a Step 1 dataset defines it."""
    if object_name and not step_flow.get_flow_dataset():
        st.session_state.current_object = object_name


def _clear_session_keys(prefix: str) -> None:
    """Forget widget state for keys starting with prefix (call before those widgets are drawn)."""
    for state_key in [k for k in st.session_state.keys() if isinstance(k, str) and k.startswith(prefix)]:
        del st.session_state[state_key]


_SF_ID_SUFFIX_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"


def _is_salesforce_id(value: str, key_prefixes: Optional[set] = None) -> bool:
    """Structural Salesforce ID check.

    15 or 18 alphanumeric characters; an 18-character ID must carry the correct
    case-safe checksum suffix; a 15-character ID must have the reserved character
    (position 6) '0'. When the key prefixes of the referenced objects are known, the
    first 3 characters must be one of them. A 15/18-character code or name therefore
    does not pass just because of its length.
    """
    value = str(value).strip()
    if not _SF_ID_RE.match(value):
        return False
    base = value[:15]
    if len(value) == 18:
        suffix = ''
        for chunk in (base[0:5], base[5:10], base[10:15]):
            bits = sum(1 << i for i, ch in enumerate(chunk) if 'A' <= ch <= 'Z')
            suffix += _SF_ID_SUFFIX_CHARS[bits]
        if value[15:].upper() != suffix:
            return False
    elif base[5] != '0':
        return False
    if key_prefixes and base[:3] not in key_prefixes:
        return False
    return True


def _reference_key_prefixes(sf_conn, reference_to: Optional[List[str]]) -> set:
    """keyPrefix of each referenced object (quietly skips objects that cannot be described)."""
    prefixes = set()
    if sf_conn is None:
        return prefixes
    for object_name in reference_to or []:
        try:
            prefix = (get_object_description(sf_conn, object_name) or {}).get('keyPrefix')
        except Exception:
            prefix = None
        if prefix:
            prefixes.add(str(prefix))
    return prefixes


def _lookups_resolved(df: pd.DataFrame, field_mappings: Optional[Dict], sf_fields: Optional[List[Dict]],
                      sf_conn=None) -> bool:
    """True when every mapped reference (lookup) column of df holds Salesforce IDs only.

    With no mapped reference fields there is nothing to resolve, so the answer is True.
    With sf_conn the ID prefix must also match the referenced object(s).
    """
    if df is None or df.empty:
        return True
    fields_by_name = {f.get('name'): f for f in (sf_fields or [])}
    for column, sf_field in (field_mappings or {}).items():
        field = fields_by_name.get(sf_field) or {}
        if field.get('type') != 'reference' or column not in df.columns:
            continue
        values = df[column].dropna().astype(str).str.strip()
        values = values[values != '']
        if values.empty:
            continue
        prefixes = _reference_key_prefixes(sf_conn, field.get('referenceTo'))
        if not values.map(lambda value: _is_salesforce_id(value, prefixes)).all():
            return False
    return True


def _apply_picklist_value_mappings(df: pd.DataFrame, object_description: Optional[Dict],
                                   field_mappings: Optional[Dict], org_name: Optional[str],
                                   object_name: Optional[str]) -> pd.DataFrame:
    """Copy of df with the saved picklist value mappings applied to the columns mapped to
    picklist / multipicklist fields - the same transformation validate_picklist_value
    checks, so the published valid rows hold the values that were actually validated."""
    if df is None or df.empty or not (org_name and object_name and object_description):
        return df
    from .utils import transform_picklist_value
    field_types = {f.get('name'): f.get('type') for f in object_description.get('fields', [])}
    result = df.copy()
    for column, sf_field in (field_mappings or {}).items():
        if column not in result.columns or field_types.get(sf_field) not in ('picklist', 'multipicklist'):
            continue
        cache = {}

        def _transform(value, _field=sf_field, _cache=cache):
            if pd.isna(value) or str(value).strip() == "":
                return value
            key = str(value)
            if key not in _cache:
                _cache[key] = transform_picklist_value(org_name, object_name, _field, key)
            return _cache[key]

        result[column] = result[column].map(_transform)
    return result


def _record_validation_run(method, object_name, valid_df, invalid_df, field_mappings, summary,
                           used_flow_dataset) -> None:
    """One row in the Validation Summary history for every run (never stops the run)."""
    try:
        from ui_components.file_store_manager import save_validation_run
        valid = len(valid_df) if valid_df is not None else 0
        invalid = len(invalid_df) if invalid_df is not None else 0
        if summary and summary.get('total') is not None:
            valid, invalid = summary.get('valid', valid), summary.get('invalid', invalid)
        dataset = step_flow.get_flow_dataset() or {}
        source = (f"Step 1 dataset: {dataset.get('name', '')}" if used_flow_dataset and dataset
                  else "Other source")
        save_validation_run(org_name=st.session_state.get('current_org'), object_name=object_name,
                            method=method, total=valid + invalid, valid=valid, invalid=invalid,
                            mapped_fields=len([v for v in (field_mappings or {}).values() if v]),
                            source=source)
    except Exception:
        pass


def _publish_step2_result(method: str, object_name: str, valid_df: pd.DataFrame,
                          invalid_df: Optional[pd.DataFrame], field_mappings: Optional[Dict],
                          used_flow_dataset: bool, sf_conn=None, lookups_resolved: Optional[bool] = None,
                          lookup_configs: Optional[Dict] = None, summary: Optional[Dict] = None,
                          match: Optional[Dict] = None):
    """Record a validation run for the guided flow (this is what unlocks Step 3).

    - A Step 1 dataset validated against another object than the Step 1 target does not
      count for the flow (Step 3 would load into the validated object, while the flow
      shows the Step 1 target).
    - A run on another source does not replace an existing result for the Step 1 dataset
      (it would silently re-lock Step 3 and drop the Step 3 load result).
    - Mappings are limited to the columns of the published rows (no stale entries).
    """
    try:
        flow_object = step_flow.get_flow_object()
        if used_flow_dataset and flow_object and object_name != flow_object:
            st.warning(f"⚠️ The Step 1 target object is **{flow_object}**, but this run validated "
                       f"**{object_name}**, so it does not unlock Step 3. Validate against "
                       f"{flow_object}, or change the target object in Step 1.")
            used_flow_dataset = False
        _record_validation_run(method, object_name, valid_df, invalid_df, field_mappings, summary,
                               used_flow_dataset)
        if not used_flow_dataset and step_flow.step2_done():
            st.info("ℹ️ This run used a different source (or object) than the Step 1 dataset. Its results "
                    "are shown below, but the Step 2 result of the Step 1 dataset is kept, so Step 3 "
                    "stays as it was.")
            return None
        present_columns = set()
        for frame in (valid_df, invalid_df):
            if frame is not None:
                present_columns.update(frame.columns)
        mappings = {k: v for k, v in (field_mappings or {}).items()
                    if v and (not present_columns or k in present_columns)}
        if lookups_resolved is None:
            description = get_object_description(sf_conn, object_name) if sf_conn is not None else None
            lookups_resolved = _lookups_resolved(valid_df, mappings, (description or {}).get('fields'), sf_conn)
        result = step_flow.publish_validation_result(
            method=method, object_name=object_name, valid_df=valid_df, invalid_df=invalid_df,
            field_mappings=mappings, lookups_resolved=lookups_resolved,
            lookup_configs=lookup_configs, used_flow_dataset=bool(used_flow_dataset), summary=summary,
            match=match,
        )
    except Exception as exc:
        st.warning(f"⚠️ Could not record this result for the guided flow: {exc}")
        return None
    if result.get('dataset_id'):
        if result['summary']['valid'] > 0:
            st.success(f"✅ Step 2 result recorded: {result['summary']['valid']:,} valid rows are ready for "
                       f"Step 3 (Data Operations).")
        else:
            st.warning("⚠️ Step 2 result recorded, but no row is valid, so Step 3 stays locked.")
    else:
        st.info("ℹ️ Result recorded, but it validated a different source than the Step 1 dataset, "
                "so it does not unlock Step 3.")
    return result


def _load_validation_data_from_oracle(state_prefix: str) -> Optional[pd.DataFrame]:
    """Render Oracle query UI and return query results as a DataFrame.

    Runs on the sidebar Oracle connection (connection_manager), like every other screen.
    """
    st.write("**🔶 Oracle Query**")
    conn_key, config = connection_manager.oracle_connection_picker(state_prefix)
    if not config:
        return None

    query = st.text_area(
        "Oracle SQL Query",
        value=st.session_state.get(f"{state_prefix}_oracle_query", ""),
        placeholder="SELECT * FROM your_schema.your_table FETCH FIRST 1000 ROWS ONLY",
        height=110,
        key=f"{state_prefix}_oracle_query"
    )

    if st.button("🔍 Run Oracle Query", key=f"{state_prefix}_run_oracle_query", use_container_width=True):
        if not query or not query.strip():
            st.error("❌ Please enter an Oracle SQL query")
        else:
            try:
                with st.spinner("🔄 Executing Oracle query..."):
                    oracle_df = connection_manager.run_oracle_query(query.strip())

                if oracle_df is None or oracle_df.empty:
                    st.warning("⚠️ Query executed but returned no rows")
                    st.session_state[f"{state_prefix}_oracle_df"] = None
                else:
                    st.session_state[f"{state_prefix}_oracle_df"] = oracle_df
                    st.success(f"✅ Oracle query loaded {len(oracle_df)} rows and {len(oracle_df.columns)} columns")
            except ImportError:
                st.error("❌ The `oracledb` package is not installed in the active Python environment.")
            except Exception as exc:
                st.session_state[f"{state_prefix}_oracle_df"] = None
                st.error(f"❌ Oracle query failed: {exc}")

    oracle_df = st.session_state.get(f"{state_prefix}_oracle_df")
    if oracle_df is not None:
        with st.expander("📊 Oracle Query Result Preview", expanded=False):
            st.dataframe(oracle_df.head(10), use_container_width=True)
    return oracle_df


def _load_validation_data_from_sql(state_prefix: str) -> Optional[pd.DataFrame]:
    """Render SQL query UI and return query results as a DataFrame for validation.

    Runs on the sidebar SQL Server connection (connection_manager), like every other screen.
    """
    st.write("**🗄️ SQL Server Query**")
    conn_key, config = connection_manager.sql_connection_picker(state_prefix)
    if not config:
        return None

    query = st.text_area(
        "SQL Query",
        value=st.session_state.get(f"{state_prefix}_sql_query", ""),
        placeholder="SELECT TOP 1000 * FROM [dbo].[YourTable]",
        height=110,
        key=f"{state_prefix}_sql_query"
    )
    query_timeout = st.number_input(
        "Query timeout (seconds)", min_value=10, max_value=300, value=60,
        key=f"{state_prefix}_sql_timeout",
        help="The complete result must be returned within this time or the query is cancelled by the driver."
    )

    if st.button("🔍 Run SQL Query", key=f"{state_prefix}_run_sql_query", use_container_width=True):
        if not query or not query.strip():
            st.error("❌ Please enter a SQL query")
        else:
            try:
                with st.spinner("🔄 Executing SQL query..."):
                    sql_df = connection_manager.run_sql_query(
                        query.strip(), command_timeout=int(query_timeout), chunk_size=5000,
                    )

                if sql_df is None or sql_df.empty:
                    st.warning("⚠️ Query executed but returned no rows")
                    st.session_state[f"{state_prefix}_sql_df"] = None
                else:
                    st.session_state[f"{state_prefix}_sql_df"] = sql_df
                    st.success(f"✅ Query loaded {len(sql_df)} rows and {len(sql_df.columns)} columns")
            except Exception as e:
                st.session_state[f"{state_prefix}_sql_df"] = None
                st.error(f"❌ SQL query failed: {str(e)}")

    sql_df = st.session_state.get(f"{state_prefix}_sql_df")
    if sql_df is not None:
        with st.expander("📊 SQL Query Result Preview", expanded=False):
            st.dataframe(sql_df.head(10), use_container_width=True)
    return sql_df

def generate_transformation_template(object_name: str, field_names: List[str], field_mappings: Dict = None) -> str:
    """Generate Python transformation template for the specified object"""
    
    # Get current timestamp for template
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Create field list for reference
    field_list = ', '.join([f'"{field}"' for field in field_names])
    
    # Generate field mapping information
    mapping_info = ""
    if field_mappings:
        mapping_info = "\n# Field Mappings from DM Toolkit:\n"
        for csv_col, sf_field in field_mappings.items():
            mapping_info += f"# {csv_col} -> {sf_field}\n"
    
    template = f'''"""
{object_name} Data Transformation Template
Generated by DM Toolkit on {timestamp}

This template provides a framework for transforming {object_name} data.
Customize the transformation logic in the transform_{object_name.lower()}_data function.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re
import sys
import os

# Configuration
INPUT_FILE = "{object_name.lower()}_mapped_for_transformation.csv"
OUTPUT_FILE = "{object_name.lower()}_transformed_data.csv"
LOG_FILE = "{object_name.lower()}_transformation_log.txt"

# Field Information
FIELD_NAMES = [{field_list}]{mapping_info}

def log_message(message: str):
    """Log transformation messages"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{{timestamp}}] {{message}}\\n"
    
    # Print to console
    print(log_entry.strip())
    
    # Write to log file
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry)

def clean_text_field(value):
    """Clean and standardize text fields"""
    if pd.isna(value) or value is None:
        return None
    
    # Convert to string and strip whitespace
    value = str(value).strip()
    
    # Remove extra spaces
    value = re.sub(r'\\s+', ' ', value)
    
    return value if value else None

def format_phone_number(phone):
    """Format phone number to standard format"""
    if pd.isna(phone) or phone is None:
        return None
    
    # Remove all non-numeric characters
    phone = re.sub(r'[^0-9]', '', str(phone))
    
    # Format based on length
    if len(phone) == 10:
        return f"({{phone[:3]}}) {{phone[3:6]}}-{{phone[6:]}}"
    elif len(phone) == 11 and phone[0] == '1':
        return f"1-{{phone[1:4]}}-{{phone[4:7]}}-{{phone[7:]}}"
    else:
        return phone  # Return as-is if format unclear

def format_date_field(date_value, target_format='%Y-%m-%d'):
    """Format date fields to Salesforce format"""
    if pd.isna(date_value) or date_value is None:
        return None
    
    try:
        # Try parsing common date formats
        date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%m-%d-%Y']
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(str(date_value), fmt)
                return parsed_date.strftime(target_format)
            except ValueError:
                continue
        
        # If no format works, return original
        return str(date_value)
        
    except Exception as e:
        log_message(f"Date formatting error for value '{{date_value}}': {{e}}")
        return None

def combine_fields(row, fields: List[str], separator: str = ' '):
    """Combine multiple fields into one"""
    values = []
    for field in fields:
        value = row.get(field)
        if pd.notna(value) and value is not None and str(value).strip():
            values.append(str(value).strip())
    
    return separator.join(values) if values else None

def calculate_priority(row):
    """Example: Calculate priority based on multiple factors"""
    # Customize this logic based on your business rules
    
    # Example logic - modify as needed
    priority_score = 0
    
    # Add score based on amount (if applicable)
    amount = row.get('Amount', 0)
    if pd.notna(amount) and amount > 0:
        if amount > 100000:
            priority_score += 3
        elif amount > 50000:
            priority_score += 2
        elif amount > 10000:
            priority_score += 1
    
    # Add score based on type (if applicable)
    record_type = str(row.get('Type', '')).upper()
    if 'ENTERPRISE' in record_type:
        priority_score += 2
    elif 'PREMIUM' in record_type:
        priority_score += 1
    
    # Convert score to priority
    if priority_score >= 4:
        return 'High'
    elif priority_score >= 2:
        return 'Medium'
    else:
        return 'Low'

def transform_{object_name.lower()}_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main transformation function for {object_name} data
    
    Args:
        df: Input dataframe with mapped field names
    
    Returns:
        Transformed dataframe ready for Salesforce
    """
    
    log_message(f"Starting transformation for {{len(df)}} {object_name} records")
    
    # Create a copy to avoid modifying original data
    df_transformed = df.copy()
    
    # ===== ADD YOUR TRANSFORMATION LOGIC BELOW =====
    
    # Example 1: Clean text fields
    text_fields = ['Name', 'Description']  # Modify based on your fields
    for field in text_fields:
        if field in df_transformed.columns:
            df_transformed[field] = df_transformed[field].apply(clean_text_field)
            log_message(f"Cleaned text field: {{field}}")
    
    # Example 2: Format phone numbers
    phone_fields = ['Phone', 'Mobile']  # Modify based on your fields
    for field in phone_fields:
        if field in df_transformed.columns:
            df_transformed[field] = df_transformed[field].apply(format_phone_number)
            log_message(f"Formatted phone field: {{field}}")
    
    # Example 3: Format date fields
    date_fields = ['CreatedDate', 'LastModifiedDate']  # Modify based on your fields
    for field in date_fields:
        if field in df_transformed.columns:
            df_transformed[field] = df_transformed[field].apply(format_date_field)
            log_message(f"Formatted date field: {{field}}")
    
    # Example 4: Combine fields
    # Uncomment and modify as needed
    # if 'FirstName' in df_transformed.columns and 'LastName' in df_transformed.columns:
    #     df_transformed['FullName'] = df_transformed.apply(
    #         lambda row: combine_fields(row, ['FirstName', 'LastName'], ' '), axis=1
    #     )
    #     log_message("Created FullName field")
    
    # Example 5: Calculate derived fields
    # Uncomment and modify as needed
    # df_transformed['Priority'] = df_transformed.apply(calculate_priority, axis=1)
    # log_message("Calculated Priority field")
    
    # Example 6: Handle null values
    # Replace empty strings with None for proper Salesforce handling
    df_transformed = df_transformed.replace(['', 'NULL', 'null'], None)
    
    # ===== ADD YOUR TRANSFORMATION LOGIC ABOVE =====
    
    log_message(f"Transformation completed for {{len(df_transformed)}} {object_name} records")
    
    return df_transformed

def validate_transformed_data(df: pd.DataFrame) -> dict:
    """
    Validate the transformed data before export
    
    Args:
        df: Transformed dataframe
    
    Returns:
        Dictionary with validation results
    """
    
    validation_results = {{
        'is_valid': True,
        'warnings': [],
        'errors': []
    }}
    
    # Check for completely empty records
    empty_rows = df.isnull().all(axis=1).sum()
    if empty_rows > 0:
        validation_results['warnings'].append(f"Found {{empty_rows}} completely empty rows")
    
    # Check for missing required fields (customize based on your requirements)
    required_fields = ['Name']  # Modify based on your object requirements
    for field in required_fields:
        if field in df.columns:
            null_count = df[field].isnull().sum()
            if null_count > 0:
                validation_results['errors'].append(f"Required field '{{field}}' has {{null_count}} null values")
                validation_results['is_valid'] = False
    
    # Check data quality
    if len(df) == 0:
        validation_results['errors'].append("No data to process")
        validation_results['is_valid'] = False
    
    return validation_results

def main():
    """Main execution function"""
    
    print(f"="*60)
    print(f"{object_name} Data Transformation")
    print(f"="*60)
    
    # Initialize logging
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    
    log_message("Starting {object_name} transformation process")
    
    # Load input data
    if not os.path.exists(INPUT_FILE):
        log_message(f"ERROR: Input file '{{INPUT_FILE}}' not found")
        print(f"Please ensure '{{INPUT_FILE}}' exists in the current directory")
        return False
    
    try:
        log_message(f"Loading data from {{INPUT_FILE}}")
        df = pd.read_csv(INPUT_FILE, dtype=str)
        log_message(f"Loaded {{len(df)}} records with {{len(df.columns)}} fields")
        
        # Display sample data
        print(f"\\nSample of input data:")
        print(df.head().to_string())
        
    except Exception as e:
        log_message(f"ERROR loading input file: {{e}}")
        return False
    
    # Transform data
    try:
        df_transformed = transform_{object_name.lower()}_data(df)
        
        # Validate transformed data
        validation_results = validate_transformed_data(df_transformed)
        
        if validation_results['warnings']:
            log_message("WARNINGS:")
            for warning in validation_results['warnings']:
                log_message(f"  - {{warning}}")
        
        if validation_results['errors']:
            log_message("ERRORS:")
            for error in validation_results['errors']:
                log_message(f"  - {{error}}")
        
        if not validation_results['is_valid']:
            log_message("Transformation failed validation. Please fix errors and try again.")
            return False
        
        # Save transformed data
        df_transformed.to_csv(OUTPUT_FILE, index=False)
        log_message(f"Transformed data saved to {{OUTPUT_FILE}}")
        
        # Display summary
        print(f"\\n" + "="*60)
        print(f"TRANSFORMATION SUMMARY")
        print(f"="*60)
        print(f"Input records:     {{len(df)}}")
        print(f"Output records:    {{len(df_transformed)}}")
        print(f"Fields processed:  {{len(df_transformed.columns)}}")
        print(f"Output file:       {{OUTPUT_FILE}}")
        print(f"Log file:          {{LOG_FILE}}")
        
        if validation_results['warnings']:
            print(f"\\nWarnings: {{len(validation_results['warnings'])}}")
            for warning in validation_results['warnings']:
                print(f"  - {{warning}}")
        
        log_message("Transformation completed successfully")
        print(f"\\n✅ Transformation completed successfully!")
        
        return True
        
    except Exception as e:
        log_message(f"ERROR during transformation: {{e}}")
        print(f"❌ Transformation failed: {{e}}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\\n🎉 Your {object_name} data is ready for Salesforce loading!")
    else:
        print(f"\\n❌ Transformation failed. Check the log file for details.")
'''
    
    return template

def validate_transformed_data(df: pd.DataFrame, object_name: str, field_mappings: Dict = None) -> dict:
    """Validate transformed data for Salesforce compatibility"""
    
    validation_results = {
        'is_valid': True,
        'issues': [],
        'checks': {
            'Non-empty data': len(df) > 0,
            'Valid field names': True,
            'No completely empty rows': True,
            'Date format consistency': True,
            'Text field lengths': True
        }
    }
    
    # Check if data is empty
    if len(df) == 0:
        validation_results['is_valid'] = False
        validation_results['issues'].append("No data to validate")
        validation_results['checks']['Non-empty data'] = False
        return validation_results
    
    # Check for completely empty rows
    empty_rows = df.isnull().all(axis=1).sum()
    if empty_rows > 0:
        validation_results['checks']['No completely empty rows'] = False
        validation_results['issues'].append(f"Found {empty_rows} completely empty rows")
    
    # Check field names (basic validation)
    invalid_fields = []
    for col in df.columns:
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*__?[a-zA-Z]$|^[a-zA-Z][a-zA-Z0-9_]*$', col):
            invalid_fields.append(col)
    
    if invalid_fields:
        validation_results['checks']['Valid field names'] = False
        validation_results['issues'].append(f"Invalid field names: {', '.join(invalid_fields[:5])}")
    
    # Check for potential date fields and format issues
    date_issues = []
    for col in df.columns:
        if 'date' in col.lower() or 'created' in col.lower() or 'modified' in col.lower():
            # Check for date format consistency
            non_null_values = df[col].dropna()
            if len(non_null_values) > 0:
                # Simple date format check
                date_patterns = [
                    r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
                    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO format
                    r'^\d{2}/\d{2}/\d{4}$',  # MM/DD/YYYY
                ]
                
                sample_values = non_null_values.astype(str).head(10)
                format_matches = any(
                    all(re.match(pattern, str(val)) for val in sample_values)
                    for pattern in date_patterns
                )
                
                if not format_matches and len(sample_values) > 0:
                    date_issues.append(col)
    
    if date_issues:
        validation_results['checks']['Date format consistency'] = False
        validation_results['issues'].append(f"Date format issues in fields: {', '.join(date_issues[:3])}")
    
    # Check text field lengths (basic check for overly long values)
    long_text_issues = []
    for col in df.columns:
        if df[col].dtype == 'object':  # Text fields
            max_length = df[col].astype(str).str.len().max()
            if max_length > 255:  # Salesforce standard field limit
                long_text_issues.append(f"{col} (max: {max_length})")
    
    if long_text_issues:
        validation_results['checks']['Text field lengths'] = False
        validation_results['issues'].append(f"Fields with very long text: {', '.join(long_text_issues[:3])}")
    
    # Overall validation status
    if validation_results['issues']:
        validation_results['is_valid'] = False
    
    return validation_results


def _mark_val_tab(idx):
    """No-op. Tabs used to be restored with injected JavaScript after a rerun; the page now
    keeps the number of elements above st.tabs constant, so Streamlit keeps the open tab.
    Kept because many on_change handlers still reference it."""
    return None


STEP2_TABS_KEY = 'step2_tabs'


def _seed_grid_from_flow(dict_key: str, widget_prefix: str, grid_id: str, csv_columns) -> None:
    """Before a mapping grid is drawn: adopt the shared Step 2 mapping if another tab changed it.

    All Step 2 tabs share one mapping (step_flow.get_flow_mappings), so a column mapped in
    Schema is mapped the same way in Enhanced and SF Validation Rules, and in Step 3.
    """
    if not step_flow.step1_done():
        return
    version = step_flow.flow_mappings_version()
    seen_key = f"_grid_seen_mapping_version_{grid_id}"
    if not version or st.session_state.get(seen_key) == version:
        return
    shared = step_flow.get_flow_mappings()
    st.session_state[dict_key] = {col: shared.get(col, '') for col in csv_columns}   # '' = no mapping
    _clear_session_keys(widget_prefix)          # the grid re-seeds its selectboxes from the dict
    st.session_state[seen_key] = version


def _publish_grid_to_flow(dict_key: str, grid_id: str) -> None:
    """After a mapping grid is drawn: its mapping becomes the shared Step 2 mapping."""
    if not step_flow.step1_done():
        return
    step_flow.set_flow_mappings({k: v for k, v in (st.session_state.get(dict_key) or {}).items() if v})
    st.session_state[f"_grid_seen_mapping_version_{grid_id}"] = step_flow.flow_mappings_version()


def _lookup_resolution_signature(df, object_name, lookup_configs, field_mappings) -> str:
    """Identity of one lookup-resolution input (data + object + settings + mapping)."""
    import hashlib
    # The tab's DataFrame stays the same object in session until other data is loaded,
    # so its identity (plus source tag and shape) stands in for its content cheaply.
    data_id = [st.session_state.get('enhanced_validation_source'), id(df), list(df.shape)]
    payload = json.dumps([data_id, object_name, lookup_configs, field_mappings], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _step2_tabs(labels):
    """st.tabs that tracks the open tab (Streamlit >= 1.63) and remembers it across page switches.

    Returns (containers, open_flags). With older Streamlit every tab counts as open.
    """
    return step_flow.keyed_tabs(labels, STEP2_TABS_KEY)


def show_validation_operations(credentials: Dict):
    """Step 2 of the guided flow: Mapping & Validation."""

    if 'current_object' not in st.session_state:
        st.session_state.current_object = None
    if 'show_manual_entry' not in st.session_state:
        st.session_state.show_manual_entry = False

    current_org = st.session_state.get('current_org')

    # Everything above the tabs lives in ONE container, so the number of elements above
    # st.tabs stays constant and Streamlit keeps the open tab across reruns.
    sf_conn = None
    header_subtitle = ("Map the Step 1 columns to Salesforce fields and validate the rows. "
                       "A validation of the Step 1 dataset with at least one valid row unlocks Step 3.")
    step2_done_before = step_flow.step2_done()
    with st.container():
        # The header (title + stepper, no widgets) sits in a placeholder so it can be redrawn
        # after the tabs when a run in a tab changes the Step 2 status.
        header_slot = st.empty()
        with header_slot.container():
            step_flow.render_step_header(2, header_subtitle)
        if current_org:
            sf_conn = connection_manager.get_sf_connection(credentials=credentials)
            if not sf_conn:
                st.error("❌ Failed to establish Salesforce connection. Please check your credentials.")
        step_flow.render_dataset_card()
        # The latest result goes here, ABOVE the tabs, so it is the first thing seen after a run.
        # It is filled after the tabs have run, so a run made in this rerun is already in it.
        result_slot = st.empty()

    tab_labels = [
        "🔍 Schema Validation",
        "⚡ Enhanced Validation",
        "✏️ Custom Validation",
        "🔧 SF Validation Rules",
        "📋 Validation Summary",
        "💾 Saved Mappings",
    ]
    (tab1, tab2, tab3, tab4, tab5, tab6), tab_open = _step2_tabs(tab_labels)

    no_org_message = "⚠️ Please select an organization from the sidebar to continue."
    validation_tabs = [
        (tab1, 'schema', show_schema_validation),
        (tab2, 'enhanced', show_enhanced_validation),
        (tab3, 'custom', show_custom_validation),
        (tab4, 'sf_rules', show_genai_validation),
    ]
    for tab, suffix, render in validation_tabs:
        with tab:
            if not step_flow.step_unlocked(2):
                step_flow.render_step_gate(2, key_suffix=suffix)
            elif not sf_conn:
                st.warning(no_org_message)
            else:
                render(sf_conn)

    # Summary and saved mappings work without Step 1; they only need the org. They are
    # read-only views that scan result files, so they only run while their tab is open.
    with tab5:
        if not current_org:
            st.warning(no_org_message)
        elif tab_open[4]:
            show_validation_summary()

    with tab6:
        if not current_org:
            st.warning(no_org_message)
        elif tab_open[5]:
            show_saved_mappings_manager(current_org)

    if step_flow.step2_done() != step2_done_before:
        with header_slot.container():
            step_flow.render_step_header(2, header_subtitle)

    with result_slot.container():
        step_flow.render_validation_result_card('step2')
    step_flow.render_step_footer(2, tab_nav=dict(
        labels=tab_labels, current=step_flow.open_tab_index(tab_labels, STEP2_TABS_KEY),
        state_key=STEP2_TABS_KEY, key='step2_tabnav'))

def show_schema_validation(sf_conn):
    """Schema validation interface"""
    
    st.subheader("🔍 Schema Validation")
    st.markdown("Validate data against Salesforce object schema - field types, required fields, formats, etc.")
    
    # Object selection
    col1, col2 = st.columns([3, 1])
    
    with col1:
        objects = get_salesforce_objects(sf_conn, filter_custom=False)

        if objects:
            object_options = [""] + objects
            _seed_flow_object("schema_validation_object", object_options)
            selected_object = st.selectbox(
                "Select Salesforce Object for Validation",
                options=object_options,
                key="schema_validation_object",
                on_change=lambda: _mark_val_tab(0),
                disabled=_flow_object_locked(object_options),
                help="The Step 1 target object (change it in Step 1)"
            )
            _remember_flow_widget("schema_validation_object", selected_object)
        else:
            st.error("❌ No Salesforce objects found")
            return

    with col2:
        if st.button("🔍 Get Schema", disabled=not selected_object, key="schema_get_schema"):
            if selected_object:
                show_object_schema(sf_conn, selected_object)

    if selected_object:
        _set_current_object(selected_object)

        # Data source selection
        st.write("### Data for Validation")

        # Import Data Hub integration functions
        try:
            from ui_components.data_hub.integration import has_data, select_dataset_from_hub
            data_hub_available = has_data()
        except ImportError:
            data_hub_available = False

        source_options = ["Use Data Hub", "Upload File", "SQL Server", "Oracle"]

        data_source = _flow_source_radio(
            "Select Data Source",
            source_options,
            key="schema_validation_source"
        )

        # Initialize session state for schema validation data (PERSISTENCE FIX)
        if 'schema_validation_data' not in st.session_state:
            st.session_state.schema_validation_data = None

        # Reset data if data source changed. The tracker is a separate plain key: the radio's own
        # key already holds the new value, so it cannot be used to detect the change.
        source_tag = f"{data_source}|{_flow_dataset_id() or ''}" if data_source == FLOW_SOURCE_OPTION else data_source
        if st.session_state.get('schema_validation_source_tracker') != source_tag:
            st.session_state.schema_validation_data = None
            st.session_state.schema_validation_data_origin = None
            st.session_state.schema_field_mappings = {}
            _clear_session_keys("schema_mapping_")  # the mapping grid is drawn further down
            st.session_state.schema_validation_source_tracker = source_tag

        if data_source == FLOW_SOURCE_OPTION:
            if not _is_flow_origin(st.session_state.get('schema_validation_data_origin')) \
                    or st.session_state.schema_validation_data is None:
                st.session_state.schema_validation_data = _flow_df()
                st.session_state.schema_validation_data_origin = _flow_origin()
            _show_flow_dataset_in_use()

        validation_data = st.session_state.schema_validation_data

        if data_source == FLOW_SOURCE_OPTION:
            pass
        elif data_source == "Use Data Hub":
            hub_df = select_dataset_from_hub("schema_validation")
            if hub_df is not None:
                if st.button("✅ Load Selected Dataset", use_container_width=True, key="schema_load_from_hub"):
                    st.session_state.schema_validation_data = hub_df
                    validation_data = hub_df
                    st.success(f"✅ Data loaded from Hub: {len(hub_df)} rows, {len(hub_df.columns)} columns")
                    with st.expander("📊 Data Preview", expanded=False):
                        st.dataframe(hub_df.head(10), use_container_width=True)

        elif data_source == "Upload File":
            uploaded_file = st.file_uploader(
                "Upload data file for validation",
                type=['csv', 'xlsx', 'xls', 'psv'],
                help="Upload CSV, Excel, or PSV (Pipe-separated) files",
                key="schema_validation_upload"
            )

            if uploaded_file and validate_file_upload(uploaded_file):
                loaded_data = load_data_file(uploaded_file)
                st.session_state.schema_validation_data = loaded_data
                validation_data = loaded_data
                if loaded_data is not None and register_source_file:
                    register_source_file(
                        uploaded_file, uploaded_file.name,
                        org_name=st.session_state.get('current_org', 'unknown'),
                        object_name=selected_object,
                        row_count=len(loaded_data), col_count=len(loaded_data.columns),
                    )

        elif data_source == "SQL Server":
            sql_data = _load_validation_data_from_sql("schema_validation")
            if sql_data is not None:
                st.session_state.schema_validation_data = sql_data
                validation_data = sql_data

        elif data_source == "Oracle":
            oracle_data = _load_validation_data_from_oracle("schema_validation")
            if oracle_data is not None:
                st.session_state.schema_validation_data = oracle_data
                validation_data = oracle_data

        elif data_source == "📁 File Library":
            picked_df, picked_name = (show_file_picker_inline(
                "schema_validation",
                org_name=st.session_state.get('current_org'),
                object_name=selected_object,
            ) if show_file_picker_inline else (None, None))
            if picked_df is not None:
                st.session_state.schema_validation_data = picked_df
                validation_data = picked_df

        elif data_source == "Select Existing File":
            existing_files = get_validation_files(selected_object)
            
            if existing_files:
                selected_file = st.selectbox(
                    "Select File",
                    options=[""] + existing_files,
                    key="schema_existing_file"
                )
                
                if selected_file:
                    loaded_data = load_existing_validation_file(selected_file)
                    st.session_state.schema_validation_data = loaded_data
                    validation_data = loaded_data
            else:
                st.info("No existing files found for validation")
        
        else:
            # Use sample data
            if validation_data is None:
                loaded_data = generate_sample_data(sf_conn, selected_object)
                st.session_state.schema_validation_data = loaded_data
                validation_data = loaded_data

        if data_source != FLOW_SOURCE_OPTION and validation_data is not None:
            st.session_state.schema_validation_data_origin = data_source

        # Validation configuration
        if validation_data is not None:
            st.write("### Validation Configuration")
            
            # Add field mapping interface
            st.write("#### 🔗 CSV Column to Salesforce Field Mapping")
            st.info("📋 Map your CSV columns to Salesforce Object fields for accurate validation")
            
            # Get Salesforce object fields
            try:
                from .utils import get_object_description
                from ui_components.field_mapping_ui import auto_load_mapping, show_mapping_load_options
                
                sf_object_info = get_object_description(sf_conn, selected_object)

                if sf_object_info and 'fields' in sf_object_info:
                    # Include all fields for validation (not just updateable ones)
                    # We're validating data, not updating, so we should see all fields
                    all_sf_fields = [field for field in sf_object_info['fields']
                                    if not field.get('name', '').startswith('attributes')]

                    csv_columns = list(validation_data.columns)
                    
                    # Try to auto-load saved mappings
                    auto_loaded_mappings = auto_load_mapping(
                        org_name=st.session_state.get('current_org', 'unknown'),
                        object_name=selected_object,
                        csv_columns=csv_columns,
                        auto_apply=False,
                        key_suffix='_schema_val'
                    )
                    
                    if 'schema_field_mappings' not in st.session_state:
                        st.session_state.schema_field_mappings = {}
                    _seed_grid_from_flow('schema_field_mappings', 'schema_mapping_', 'schema', csv_columns)
                    if auto_loaded_mappings:
                        # 'Use Saved Mappings' / 'Partially Apply' was clicked in this run. The
                        # grid's selectbox keys still hold the old choices, so drop them and let
                        # the grid re-seed from the applied mapping.
                        # Only the saved columns: the suggestion merge below fills the others.
                        st.session_state.schema_field_mappings = {
                            col: sf_field for col, sf_field in auto_loaded_mappings.items() if col in csv_columns
                        }
                        _clear_session_keys("schema_mapping_")
                    _correct_known_validation_mappings(st.session_state.schema_field_mappings, all_sf_fields)
                    
                    # Use the same conservative suggestions as Enhanced Validation.
                    suggested_mappings = _suggest_validation_field_mappings(
                        csv_columns, all_sf_fields
                    )
                    
                    # Initialize field mappings in session state with suggested mappings
                    if 'schema_field_mappings' not in st.session_state:
                        st.session_state.schema_field_mappings = suggested_mappings.copy()
                    else:
                        # Apply suggested mappings only for unmapped columns
                        for csv_col, sf_field in suggested_mappings.items():
                            if csv_col not in st.session_state.schema_field_mappings:
                                st.session_state.schema_field_mappings[csv_col] = sf_field
                    
                    # Show auto-mapping summary
                    if suggested_mappings:
                        col_auto1, col_auto2 = st.columns([3, 1])
                        with col_auto1:
                            st.success(f"✅ Auto-mapped {len(suggested_mappings)} out of {len(csv_columns)} CSV columns to Salesforce fields")
                        with col_auto2:
                            if st.button("🔄 Reset Mappings", help="Clear all mappings and re-apply auto-mapping",
                                         key="schema_reset_mappings"):
                                st.session_state.schema_field_mappings = suggested_mappings.copy()
                                _clear_session_keys("schema_mapping_")
                                _mark_val_tab(0)
                                st.rerun()
                    else:
                        st.info("ℹ️ No automatic mappings found. Please map columns manually.")
                    
                    st.markdown("**🎯 Column Mapping Configuration:**")
                    st.caption(f"{len(all_sf_fields)} fields available on {selected_object}")

                    # Mapping interface
                    field_mappings = {}
                    sf_field_options = ["⚠️ No mapping"] + [f"{field['name']} ({field.get('label', field['name'])})" for field in all_sf_fields]
                    sf_field_names = [""] + [field['name'] for field in all_sf_fields]
                    option_by_field = dict(zip(sf_field_names[1:], sf_field_options[1:]))

                    # Create mapping table
                    col1, col2, col3 = st.columns([2, 3, 2])
                    
                    with col1:
                        st.markdown("**CSV Column**")
                    with col2:
                        st.markdown("**Maps to Salesforce Field**")
                    with col3:
                        st.markdown("**Sample Data**")
                    
                    st.divider()
                    
                    for i, csv_column in enumerate(csv_columns):
                        col1, col2, col3 = st.columns([2, 3, 2])
                        
                        with col1:
                            st.write(f"**{csv_column}**")
                        
                        with col2:
                            # Get current mapping or suggested mapping ("" = user chose no mapping)
                            if csv_column in st.session_state.schema_field_mappings:
                                current_mapping = st.session_state.schema_field_mappings[csv_column]
                            else:
                                current_mapping = suggested_mappings.get(csv_column, "")
                            if current_mapping and current_mapping not in option_by_field:
                                st.warning(f"⚠️ Mapped field '{current_mapping}' not found in available fields for '{csv_column}'. Resetting mapping.")
                                current_mapping = ""
                                st.session_state.schema_field_mappings.pop(csv_column, None)

                            # Seed the widget before it is drawn (passing index= is ignored once the
                            # key has state, which silently undid saved/auto/reset mappings).
                            mapping_widget_key = f"schema_mapping_{i}_{csv_column}"
                            if st.session_state.get(mapping_widget_key) not in sf_field_options:
                                st.session_state[mapping_widget_key] = option_by_field.get(current_mapping, "⚠️ No mapping")
                            selected_mapping = st.selectbox(
                                f"Field mapping for {csv_column}",
                                options=sf_field_options,
                                key=mapping_widget_key,
                                label_visibility="collapsed"
                            )

                            # Store the mapping
                            if selected_mapping != "⚠️ No mapping":
                                field_name = selected_mapping.split(" (")[0]
                                field_mappings[csv_column] = field_name
                                st.session_state.schema_field_mappings[csv_column] = field_name
                            else:
                                st.session_state.schema_field_mappings[csv_column] = ""
                        
                        with col3:
                            # Show sample data
                            sample_value = validation_data[csv_column].iloc[0] if len(validation_data) > 0 else "N/A"
                            st.write(f"`{sample_value}`")

                    _publish_grid_to_flow('schema_field_mappings', 'schema')
                    
                    # Show mapping summary
                    st.markdown("---")
                    st.markdown("### 📋 Field Mapping Summary")
                    
                    if field_mappings:
                        st.success(f"✅ {len(field_mappings)} field mappings configured")
                        
                        # Display mapped fields
                        mapping_df = pd.DataFrame([
                            {"CSV Column": csv_col, "Salesforce Field": sf_field}
                            for csv_col, sf_field in field_mappings.items()
                        ])
                        st.dataframe(mapping_df, use_container_width=True, hide_index=True)
                        
                        # Add save mapping option
                        from ui_components.field_mapping_ui import show_mapping_save_options
                        show_mapping_save_options(
                            org_name=st.session_state.get('current_org', 'unknown'),
                            object_name=selected_object,
                            field_mappings=field_mappings,
                            csv_columns=csv_columns,
                            validation_type='schema'
                        )
                    else:
                        st.warning("⚠️ No field mappings configured yet")
                        st.info("💡 Configure at least one field mapping to run validation")

                
                else:
                    st.error("❌ Could not retrieve Salesforce object fields")
                    field_mappings = {}
                    
            except Exception as e:
                st.error(f"❌ Error setting up field mapping: {str(e)}")
                field_mappings = {}
            
            # Validation Configuration
            st.write("#### ⚙️ Validation Configuration")
            
            col_config1, col_config2, col_config3 = st.columns(3)
            
            with col_config1:
                validate_required = st.checkbox(
                    "Validate Required Fields",
                    value=True,
                    help="Check for missing required fields"
                )
                
                validate_datatypes = st.checkbox(
                    "Validate Data Types",
                    value=True,
                    help="Validate field data types"
                )
            
            with col_config2:
                validate_formats = st.checkbox(
                    "Validate Formats",
                    value=True,
                    help="Validate email, phone, date formats"
                )
                
                validate_lengths = st.checkbox(
                    "Validate Field Lengths",
                    value=True,
                    help="Check field length limits"
                )
            
            with col_config3:
                validate_picklists = st.checkbox(
                    "Validate Picklist Values",
                    value=True,
                    help="Validate picklist/multi-select values"
                )
                
                strict_mode = st.checkbox(
                    "Strict Mode",
                    value=False,
                    help="Fail validation on any error"
                )
            
            # Show data preview
            with st.expander("📊 Data Preview", expanded=False):
                st.dataframe(validation_data.head(10), use_container_width=True)
            
            # Run schema validation
            if field_mappings:
                if st.button("🚀 Run Schema Validation", type="primary", use_container_width=True,
                             key="schema_run_validation"):
                    # Ensure we have the latest data from session state (PERSISTENCE FIX)
                    validation_data_to_run = st.session_state.schema_validation_data
                    if validation_data_to_run is not None:
                        run_schema_validation(
                            sf_conn, selected_object, validation_data_to_run,
                            validate_required, validate_datatypes, validate_formats,
                            validate_lengths, validate_picklists, strict_mode, field_mappings,
                            st.session_state.get('current_org'),
                            used_flow_dataset=_is_flow_origin(
                                st.session_state.get('schema_validation_data_origin')),
                        )
                    else:
                        st.error("❌ No validation data available. Please load or upload data first.")
            else:
                st.warning("⚠️ Configure at least one field mapping to run validation")
                st.button("🚀 Run Schema Validation", type="primary", use_container_width=True, disabled=True,
                          key="schema_run_validation_disabled")

def show_custom_validation(sf_conn):
    """Custom validation interface - allows users to define custom validation rules"""
    
    # Track that we're in the Custom Validation tab (prevent accidental tab switches on rerun)
    st.subheader("✏️ Custom Validation")
    st.markdown("Define custom validation rules for Salesforce objects - choose fields and write formulas to validate data")
    
    # Object selection
    objects = get_salesforce_objects(sf_conn, filter_custom=False)
    
    if not objects:
        st.error("❌ No Salesforce objects found")
        return
    
    object_options = [""] + objects
    _seed_flow_object("custom_validation_object", object_options)
    selected_object = st.selectbox(
        "Select Salesforce Object",
        options=object_options,
        key="custom_validation_object",
        on_change=lambda: _mark_val_tab(2),
        disabled=_flow_object_locked(object_options),
        help="The Step 1 target object (change it in Step 1)"
    )
    _remember_flow_widget("custom_validation_object", selected_object)

    if not selected_object:
        st.info("👆 Please select a Salesforce object to continue")
        return

    _set_current_object(selected_object)
    
    # Initialize session state for custom rules
    if 'custom_validation_rules' not in st.session_state:
        st.session_state.custom_validation_rules = []
    
    # Get object fields
    try:
        from .utils import get_object_description
        sf_object_info = get_object_description(sf_conn, selected_object)
        
        if not sf_object_info or 'fields' not in sf_object_info:
            st.error(f"❌ Could not retrieve fields for {selected_object}")
            return
        
        all_fields = [f['name'] for f in sf_object_info['fields']]
        
        # Rule creation section
        st.write("### 📋 Create Validation Rules")
        st.markdown("Define custom rules to validate your data against specific conditions")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            rule_name = st.text_input(
                "Rule Name",
                placeholder="e.g., Valid Phone Format, Required Email",
                help="Give your rule a descriptive name",
                key="custom_rule_name"
            )

        with col2:
            rule_severity = st.selectbox(
                "Severity",
                options=["⚠️ Warning", "❌ Error"],
                help="Set the severity level for violations",
                key="custom_rule_severity"
            )

        # Field selection for the rule
        target_field = st.selectbox(
            "Target Field",
            options=[""] + all_fields,
            help="Select the field this rule applies to",
            key="custom_rule_field"
        )

        # Rule type selection
        rule_type = st.radio(
            "Rule Type",
            options=[
                "Custom Formula",
                "Field Comparison",
                "Pattern Match",
                "Required Field"
            ],
            help="Choose the type of validation rule",
            key="custom_rule_type"
        )
        
        # Rule definition based on type
        if rule_type == "Custom Formula":
            formula = st.text_area(
                "Validation Formula",
                placeholder="e.g., LEN({Phone}) >= 10\nor {Email} LIKE '%@%.%'\nor {Amount} > 0",
                height=100,
                help="Enter a formula to validate. Use {FieldName} for field references. Return TRUE if valid."
            )
            rule_description = f"Custom: {formula[:50]}..."
        
        elif rule_type == "Field Comparison":
            compare_field = st.selectbox(
                "Compare With Field",
                options=[""] + all_fields,
                help="Select the field to compare with"
            )
            comparison = st.selectbox(
                "Comparison Type",
                options=["Equals", "Not Equals", "Greater Than", "Less Than", "Contains"]
            )
            formula = f"{{Field: {target_field}}} {comparison} {{Field: {compare_field}}}"
            rule_description = f"Compare {target_field} {comparison} {compare_field}"
        
        elif rule_type == "Pattern Match":
            pattern = st.text_input(
                "Regex Pattern",
                placeholder="e.g., ^[A-Z][0-9]{3}$ for format like A123",
                help="Enter a regular expression pattern",
                key="custom_rule_pattern"
            )
            formula = f"REGEX({{Field: {target_field}}}, '{pattern}')"
            rule_description = f"Pattern: {pattern}"
        
        elif rule_type == "Required Field":
            formula = f"NOT_EMPTY({{Field: {target_field}}})"
            rule_description = f"Field '{target_field}' is required (not empty)"
        
        # Error message for the rule
        error_message = st.text_input(
            "Error Message",
            placeholder="e.g., Phone number must be at least 10 digits",
            help="Message to display when this rule is violated"
        )
        
        # Add rule button
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("➕ Add Rule", use_container_width=True, key="custom_add_rule"):
                if not rule_name:
                    st.error("❌ Please enter a rule name")
                elif not target_field:
                    st.error("❌ Please select a target field")
                elif not formula:
                    st.error("❌ Please define a formula")
                else:
                    new_rule = {
                        # max+1, not len+1: ids must stay unique after a rule is deleted
                        'id': max([r.get('id', 0) for r in st.session_state.custom_validation_rules] or [0]) + 1,
                        'name': rule_name,
                        'severity': rule_severity,
                        'field': target_field,
                        'type': rule_type,
                        'formula': formula,
                        'description': rule_description,
                        'error_message': error_message or f"Validation failed for {target_field}"
                    }
                    st.session_state.custom_validation_rules.append(new_rule)
                    st.success(f"✅ Rule '{rule_name}' added successfully!")
                    _mark_val_tab(2)
                    st.rerun()
        
        with col2:
            if st.button("🗑️ Clear Form", use_container_width=True):
                _mark_val_tab(2)
                st.rerun()
        
        with col3:
            if st.button("💾 Save All Rules", use_container_width=True):
                if st.session_state.custom_validation_rules:
                    rules_save_path = os.path.join(
                        project_root, 'Validation', 'CustomRules',
                        st.session_state.get('current_org', 'unknown'),
                        selected_object
                    )
                    os.makedirs(rules_save_path, exist_ok=True)
                    
                    save_file = os.path.join(rules_save_path, f"custom_rules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                    with open(save_file, 'w') as f:
                        json.dump(st.session_state.custom_validation_rules, f, indent=2)
                    
                    st.success(f"✅ Rules saved to {save_file}")
                else:
                    st.warning("⚠️ No rules to save")
        
        # Display existing rules
        if st.session_state.custom_validation_rules:
            st.write("### 📝 Defined Rules")
            
            for rule in st.session_state.custom_validation_rules:
                with st.expander(f"{rule['severity']} {rule['name']} ({rule['field']})", expanded=False):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"**Type:** {rule['type']}")
                        st.write(f"**Formula:** `{rule['formula']}`")
                        st.write(f"**Error Message:** {rule['error_message']}")
                    
                    with col2:
                        if st.button("✏️ Edit", key=f"custom_rule_edit_{rule['id']}"):
                            st.info("Edit functionality coming soon")
                    
                    with col3:
                        # 'custom_rule_' prefix: the Saved Mappings tab (drawn in the same run)
                        # uses delete_{idx} keys too.
                        if st.button("🗑️ Delete", key=f"custom_rule_delete_{rule['id']}"):
                            st.session_state.custom_validation_rules = [r for r in st.session_state.custom_validation_rules if r['id'] != rule['id']]
                            st.success("Rule deleted")
                            _mark_val_tab(2)
                            st.rerun()
            
            # Apply rules to data
            st.divider()
            st.write("### 🚀 Validate Data Against Rules")
            
            # Data source selection
            try:
                from ui_components.data_hub.integration import has_data, select_dataset_from_hub
                data_hub_available = has_data()
            except ImportError:
                data_hub_available = False
            
            source_options = ["Use Data Hub", "Upload File", "SQL Server", "Oracle"]
            
            data_source = _flow_source_radio(
                "Select Data Source",
                source_options,
                key="custom_validation_source",
                horizontal=True
            )

            validation_data = None
            uses_flow_dataset = False

            if data_source == FLOW_SOURCE_OPTION:
                validation_data = _flow_df()
                uses_flow_dataset = validation_data is not None
                _show_flow_dataset_in_use()

            elif data_source == "Upload File":
                uploaded_file = st.file_uploader(
                    "Upload data to validate",
                    type=['csv', 'xlsx', 'xls', 'psv'],
                    help="CSV, Excel, or PSV files",
                    key="custom_validation_upload"
                )
                
                if uploaded_file:
                    try:
                        if uploaded_file.name.endswith('.csv'):
                            validation_data = pd.read_csv(uploaded_file, dtype=str)
                        elif uploaded_file.name.endswith('.psv'):
                            validation_data = pd.read_csv(uploaded_file, sep='|', dtype=str)
                        else:
                            validation_data = pd.read_excel(uploaded_file, dtype=str)
                        
                        st.success(f"✅ Loaded {len(validation_data)} rows with {len(validation_data.columns)} columns")
                    except Exception as e:
                        st.error(f"❌ Error loading file: {str(e)}")
            
            elif data_source == "Use Data Hub":
                hub_df = select_dataset_from_hub("custom_validation")
                if hub_df is not None:
                    validation_data = hub_df
                    st.success(f"✅ Loaded {len(validation_data)} rows from Data Hub")

            elif data_source == "SQL Server":
                sql_data = _load_validation_data_from_sql("custom_validation")
                if sql_data is not None:
                    validation_data = sql_data
                    st.success(f"✅ Loaded {len(validation_data)} rows from SQL Server query")

            elif data_source == "Oracle":
                oracle_data = _load_validation_data_from_oracle("custom_validation")
                if oracle_data is not None:
                    validation_data = oracle_data
                    st.success(f"✅ Loaded {len(validation_data)} rows from Oracle query")
            
            # Run validation
            if validation_data is not None:
                if st.button("✅ Run Validation", type="primary", use_container_width=True,
                             key="custom_run_validation"):
                    with st.spinner("🔄 Validating data..."):
                        # Rows are addressed by position (the results display expects 0..n-1).
                        data_to_check = validation_data.reset_index(drop=True)
                        # Rules name Salesforce fields: evaluate them on the data renamed with the
                        # shared Step 2 mapping (source column -> field), keep rows in source names.
                        shared_mapping = step_flow.get_flow_mappings() if uses_flow_dataset else {}
                        rename, used_targets = {}, set()
                        for source_col, sf_field in shared_mapping.items():
                            if source_col in data_to_check.columns and sf_field not in used_targets:
                                rename[source_col] = sf_field
                                used_targets.add(sf_field)
                        rule_frame = data_to_check.rename(columns=rename)
                        if uses_flow_dataset and not shared_mapping:
                            st.caption("ℹ️ Map the columns in the Schema or Enhanced tab first, so rules on "
                                       "Salesforce fields check the right source columns.")
                        # Initialize results (same shape as schema validation, so the shared
                        # results display works: field_errors present, record_errors are lists)
                        validation_results = {
                            'total_records': len(data_to_check),
                            'passed_records': 0,
                            'failed_records': 0,
                            'validation_errors': [],
                            'field_errors': {},
                            'record_errors': {},
                            'validated_data': data_to_check.copy()
                        }

                        rules = st.session_state.custom_validation_rules
                        # Warn once per rule, not once per row.
                        active_rules = []
                        for rule in rules:
                            if rule['type'] not in ('Required Field', 'Pattern Match'):
                                st.warning(f"⚠️ Rule '{rule['name']}' skipped: evaluation of "
                                           f"'{rule['type']}' rules is not implemented yet")
                                continue
                            if rule['field'] not in rule_frame.columns:
                                st.warning(f"⚠️ Rule '{rule['name']}': field '{rule['field']}' is not a column "
                                           f"of the data, so every row is checked against an empty value")
                            active_rules.append(rule)
                        rule_failures = {}

                        # Run each rule against the data
                        for position, (_, row) in enumerate(rule_frame.iterrows()):
                            row_errors = []

                            for rule in active_rules:
                                try:
                                    # Simple rule evaluation
                                    field_value = row.get(rule['field'], '')
                                    if pd.isna(field_value):
                                        field_value = ''

                                    # Check rule type
                                    if rule['type'] == 'Required Field':
                                        violated = str(field_value).strip() == ''
                                    else:  # Pattern Match
                                        pattern = rule['formula'].split("'")[1] if "'" in rule['formula'] else ''
                                        violated = bool(pattern) and not re.match(pattern, str(field_value))

                                    if violated:
                                        message = f"Row {position + 1}: {rule['error_message']}"
                                        row_errors.append(message)
                                        validation_results['validation_errors'].append(message)
                                        validation_results['field_errors'].setdefault(rule['field'], []).append(message)

                                except Exception as e:
                                    rule_failures.setdefault(rule['name'], str(e))

                            if row_errors:
                                validation_results['failed_records'] += 1
                                validation_results['record_errors'][str(position)] = row_errors
                            else:
                                validation_results['passed_records'] += 1

                        for rule_name_failed, error_text in rule_failures.items():
                            st.warning(f"⚠️ Could not evaluate rule '{rule_name_failed}': {error_text}")

                        # Guided flow: publish the valid/invalid split. The rules name Salesforce
                        # fields directly, so the mapping is the identity for columns that are
                        # fields of the object.
                        invalid_positions = [int(key) for key in validation_results['record_errors']]
                        valid_rows = data_to_check.drop(index=invalid_positions)
                        invalid_rows = data_to_check.loc[invalid_positions].copy()
                        invalid_rows['Validation_Errors'] = [
                            '; '.join(validation_results['record_errors'][str(p)]) for p in invalid_positions
                        ]
                        object_fields = set(all_fields)
                        published_mappings = dict(rename) if rename else {
                            col: col for col in data_to_check.columns if col in object_fields}
                        _publish_step2_result(
                            'Custom Validation', selected_object, valid_rows, invalid_rows, published_mappings,
                            used_flow_dataset=uses_flow_dataset, sf_conn=sf_conn,
                            summary={'rules': len(active_rules)},
                        )

                        # Display results
                        display_enhanced_validation_results(validation_results, selected_object, "Custom Validation")

    except Exception as e:
        st.error(f"❌ Error in custom validation: {str(e)}")

def show_genai_validation(sf_conn):
    """SF Validation Rules interface - Extracts Salesforce validation rules and converts to Python"""
    
    # Initialize validation_data to prevent UnboundLocalError
    validation_data = None
    
    # Initialize session state variables to prevent AttributeError
    if 'genai_bundle_generated' not in st.session_state:
        st.session_state.genai_bundle_generated = False
    if 'genai_bundle_content' not in st.session_state:
        st.session_state.genai_bundle_content = None
    if 'genai_validator_content' not in st.session_state:
        st.session_state.genai_validator_content = None
    if 'formula_csv_generated' not in st.session_state:
        st.session_state.formula_csv_generated = False
    if 'formula_csv_content' not in st.session_state:
        st.session_state.formula_csv_content = None
    if 'formula_df' not in st.session_state:
        st.session_state.formula_df = None
    if 'genai_bundle_path' not in st.session_state:
        st.session_state.genai_bundle_path = None
    if 'genai_validator_path' not in st.session_state:
        st.session_state.genai_validator_path = None
    if 'genai_num_functions' not in st.session_state:
        st.session_state.genai_num_functions = 0
    
    st.subheader("🔧 SF Validation Rules")
    # This tab's latest result is drawn HERE, at the top (it is filled at the end of the
    # function, after Steps 1-3), so it is not buried below the steps that produced it.
    genai_results_slot = st.empty()

    # Main description and workflow
    st.markdown("""
    **SF Validation Rules** extracts validation rules from your Salesforce organization and converts them into Python functions that can validate data outside of Salesforce.
    
    ### How it works:
    1. **Extract Rules**: Get validation rules from Salesforce or enter them manually
    2. **Generate Bundle**: AI converts Salesforce formulas to Python functions  
    3. **Validate Data**: Run validation on your CSV/Excel data files
    4. **Get Results**: Receive validated data split into success/failure files
    
    ### Benefits:
    - ✅ Validate data before loading to Salesforce
    - 🎯 Catch data quality issues early
    - ⚡ Reduce failed data load attempts  
    - 📊 Get detailed validation reports
    """)
    
    # Object selection
    objects = get_salesforce_objects(sf_conn, filter_custom=False)
    
    if objects:
        object_options = ["Select an object..."] + objects
        _seed_flow_object("genai_validation_object", object_options)
        selected_object = st.selectbox(
            "Select Salesforce Object",
            options=object_options,
            key="genai_validation_object",
            on_change=lambda: _mark_val_tab(3),
            disabled=_flow_object_locked(object_options),
            help="The Step 1 target object (change it in Step 1)"
        )
        _remember_flow_widget("genai_validation_object", selected_object)
        
        # Clear previous results when object changes
        if hasattr(st.session_state, 'current_genai_object'):
            if st.session_state.current_genai_object != selected_object:
                # Object changed - clear previous validation results and data
                if 'genai_validation_results' in st.session_state:
                    del st.session_state.genai_validation_results
                if 'genai_validation_completed' in st.session_state:
                    del st.session_state.genai_validation_completed
                if 'genai_original_data' in st.session_state:
                    del st.session_state.genai_original_data
                if 'genai_validation_data' in st.session_state:
                    st.session_state.genai_validation_data = None
                if 'genai_bundle_generated' in st.session_state:
                    st.session_state.genai_bundle_generated = False
                if 'genai_bundle_content' in st.session_state:
                    st.session_state.genai_bundle_content = None
                if 'genai_validator_content' in st.session_state:
                    st.session_state.genai_validator_content = None
                if 'ai_bundle_generated' in st.session_state:
                    st.session_state.ai_bundle_generated = False
                if 'ai_bundle_result' in st.session_state:
                    st.session_state.ai_bundle_result = None
                if 'formula_csv_generated' in st.session_state:
                    st.session_state.formula_csv_generated = False
                if 'formula_csv_content' in st.session_state:
                    st.session_state.formula_csv_content = None
                if 'formula_df' in st.session_state:
                    st.session_state.formula_df = None
                
        # Store current object for change detection
        st.session_state.current_genai_object = selected_object
    else:
        st.error("❌ No Salesforce objects found")
        return
    
    if selected_object and selected_object != "Select an object...":
        _set_current_object(selected_object)

        # SF VALIDATION RULES WORKFLOW
        st.markdown("---")
        st.markdown("## 🔧 **SF Validation Rules Workflow**")
        st.markdown("*Extract and convert Salesforce validation formulas to Python functions*")
        
        # Step 1: Extract Validation Rule Formulas
        st.markdown("### 📋 **Step 1: Extract Validation Rule Formulas**")
        st.markdown("""
        **Extract all validation rule formulas for the selected Salesforce object.**
        
        ✨ **What this step does:**
        - Retrieves all validation rules defined for the selected object
        - Extracts the **ErrorConditionFormula** (Apex code) from each rule
        - Generates a downloadable Formula CSV/Excel file
        - Includes rule names, formulas, error messages, and status
        """)
        
        # Check for existing Formula file
        root_folder = "DataFiles"
        current_org = st.session_state.current_org if hasattr(st.session_state, 'current_org') else 'default'
        object_folder = os.path.join(root_folder, current_org, selected_object)
        csv_file_path = os.path.join(object_folder, "Formula_validation.csv")
        excel_file_path = os.path.join(object_folder, "Formula_validation.xlsx")
        formula_file_exists = os.path.exists(csv_file_path) or os.path.exists(excel_file_path)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🔗 Extract Formulas from Salesforce:**")
            if st.button("📥 Extract Validation Formulas", type="primary", use_container_width=True, key="extract_formulas"):
                # The organization is always the sidebar org (connection_manager); this screen
                # never chooses or changes it.
                selected_org = st.session_state.get('current_org')
                if not selected_org or selected_org not in connection_manager.salesforce_orgs():
                    st.error("❌ Select a Salesforce org in the sidebar first")
                    return
                if sf_conn is None:
                    st.error("❌ No Salesforce connection available for the sidebar org")
                    return

                # Extract Validation Rule Formulas (NEW LOGIC)
                st.info("🔍 Extracting validation rule formulas from Salesforce...")

                try:
                    # Use the enhanced extraction function
                    df, folder_path = extract_validation_formulas_for_genai(sf_conn, selected_org, selected_object)
                    
                    if df is not None and len(df) > 0:
                        # Store in session state for persistent access
                        st.session_state.formula_extraction_complete = True
                        st.session_state.formula_df = df
                        st.session_state.formula_folder_path = folder_path
                        _set_current_object(selected_object)
                        
                        st.success(f"✅ Successfully extracted {len(df)} validation rule formulas!")
                        
                        # Display file location info
                        display_file_location_info(folder_path)
                        
                        # Show preview of extracted formulas
                        st.markdown("**📋 Preview of Extracted Formulas:**")
                        with st.expander("View Formula Preview", expanded=True):
                            st.dataframe(df.head(), use_container_width=True)
                        
                        _mark_val_tab(3)
                        st.rerun()  # Refresh to show download option
                    else:
                        st.warning("⚠️ No validation rules with formulas found for this object")
                        
                except Exception as e:
                    st.error(f"❌ Error extracting validation formulas: {str(e)}")
                    st.exception(e)
        
        with col2:
            if formula_file_exists or (hasattr(st.session_state, 'formula_extraction_complete') and st.session_state.formula_extraction_complete):
                st.markdown("**📁 Download Formula Files:**")
                
                # Get current file paths
                csv_file_path = os.path.join(object_folder, "GenAI_Formula_validation.csv")
                excel_file_path = os.path.join(object_folder, "GenAI_Formula_validation.xlsx")
                
                # Download CSV
                if os.path.exists(csv_file_path):
                    try:
                        with open(csv_file_path, 'r', encoding='utf-8') as f:
                            csv_content = f.read()
                        
                        st.download_button(
                            label="📥 Quick Download CSV",
                            data=csv_content,
                            file_name=get_timestamped_filename(f"{selected_object}_formula_validation"),
                            mime="text/csv",
                            use_container_width=True,
                            key="download_formula_csv", on_click='ignore'
                        )
                    except Exception as e:
                        st.error(f"Error reading CSV file: {str(e)}")
                
                # Download Excel
                if os.path.exists(excel_file_path):
                    try:
                        with open(excel_file_path, 'rb') as f:
                            excel_content = f.read()
                        
                        st.download_button(
                            label="  Download Formula Excel",
                            data=excel_content,
                            file_name=get_timestamped_filename(f"{selected_object}_formula_validation", "xlsx"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            key="download_formula_excel", on_click='ignore'
                        )
                    except Exception as e:
                        st.error(f"Error reading Excel file: {str(e)}")
            else:
                st.info("📊 Extract validation formulas first to enable downloads")
        
        # Show preview if available
        if hasattr(st.session_state, 'formula_df') and st.session_state.formula_df is not None:
            with st.expander("📋 Extracted Formulas Preview", expanded=False):
                st.write(f"**Preview of {len(st.session_state.formula_df)} validation rule formulas:**")
                st.dataframe(st.session_state.formula_df.head(10), use_container_width=True)
                if len(st.session_state.formula_df) > 10:
                    st.info(f"Showing first 10 rules. Download files to see all {len(st.session_state.formula_df)} rules.")
        
        # Only proceed to Step 2 if formulas are extracted
        if (hasattr(st.session_state, 'formula_extraction_complete') and st.session_state.formula_extraction_complete) and hasattr(st.session_state, 'formula_df'):
            
            validation_rules_df = st.session_state.formula_df
            
            if validation_rules_df is not None and len(validation_rules_df) > 0:
                st.markdown("---")
                
                # Step 2: Generate AI Validation Bundle
                st.markdown("### 🤖 **Step 2: Generate AI Validation Bundle**")
                st.markdown("""
                **Convert each Salesforce formula (Apex code) to individual Python validation functions.**
                
                ✨ **What this step does:**
                - Analyzes each **ErrorConditionFormula** from Step 1
                - Uses AI to convert Apex code to Python functions
                - Creates individual validation functions for each formula
                - Generates a complete validation bundle with helper functions
                """)
                
                # Show formula analysis
                st.markdown("**📊 Formula Analysis:**")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    total_formulas = len(validation_rules_df)
                    st.metric("Total Formulas", total_formulas)
                
                with col2:
                    if 'ErrorConditionFormula' in validation_rules_df.columns:
                        valid_formulas = validation_rules_df['ErrorConditionFormula'].dropna().count()
                        st.metric("Valid Formulas", valid_formulas)
                    else:
                        st.metric("Valid Formulas", "N/A")
                
                with col3:
                    if 'Active' in validation_rules_df.columns:
                        active_formulas = validation_rules_df[validation_rules_df['Active'] == True].shape[0] if 'Active' in validation_rules_df.columns else total_formulas
                        st.metric("Active Formulas", active_formulas)
                    else:
                        st.metric("Active Formulas", total_formulas)
                
                # Show detailed workflow
                with st.expander("🔍 **AI Conversion Process**", expanded=False):
                    st.markdown("""
                    **For each validation rule formula:**
                    
                    1. **Extract Formula**: Get the `ErrorConditionFormula` (Apex code)
                    2. **AI Analysis**: Analyze the Apex logic and syntax
                    3. **Convert to Python**: Generate equivalent Python validation function
                    4. **Function Naming**: Create descriptive function names based on rule names
                    5. **Bundle Integration**: Combine all functions into a cohesive validation bundle
                    
                    **Example Conversion:**
                    ```apex
                    // Salesforce Formula
                    ISBLANK(Email) && ISBLANK(Phone)
                    ```
                    
                    ```python
                    # Generated Python Function
                    def validate_contact_info(row):
                        return not (is_blank(row.get('Email')) and is_blank(row.get('Phone')))
                    ```
                    """)
                
                # Show existing results if available
                if hasattr(st.session_state, 'ai_bundle_generated') and st.session_state.ai_bundle_generated:
                    st.info("🎉 AI Validation Bundle already generated! Download files below or generate new bundle.")
                
                if hasattr(st.session_state, 'conversion_logs') and st.session_state.conversion_logs:
                    total_logs = len(st.session_state.conversion_logs)
                    success_logs = sum(1 for log in st.session_state.conversion_logs if log['status'] == 'success')
                    st.info(f"📊 Previous conversion: {success_logs}/{total_logs} rules converted successfully")
                
                # AI Bundle Generation
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**🚀 Generate AI Bundle:**")
                    if st.button("🤖 Generate Python Validation Bundle", type="primary", use_container_width=True, key="generate_ai_bundle"):
                        # Initialize session state for conversion logs
                        if 'conversion_logs' not in st.session_state:
                            st.session_state.conversion_logs = []
                        
                        # Clear previous logs
                        st.session_state.conversion_logs = []
                        
                        # Generate AI bundle from the extracted formulas
                        with st.spinner("🔄 Converting Salesforce formulas to Python functions..."):
                            try:
                                # Use the enhanced AI conversion function with output capture
                                # Use the updated bundle generation that creates proper coordination functions
                                try:
                                    bundle_path, validator_path, num_functions, function_mappings = generate_validation_bundle_from_dataframe(
                                        validation_df=validation_rules_df,
                                        selected_org=st.session_state.current_org or 'default',
                                        object_name=selected_object
                                    )
                                    
                                    bundle_result = {
                                        'success': True,
                                        'bundle_path': bundle_path,
                                        'validator_path': validator_path,
                                        'num_functions': num_functions,
                                        'function_mappings': function_mappings  # Now populated with actual data
                                    }
                                    
                                except Exception as e:
                                    st.error(f"❌ Bundle generation failed: {str(e)}")
                                    bundle_result = {'success': False, 'error': str(e)}
                                
                                if bundle_result and bundle_result.get('success', False):
                                    st.session_state.ai_bundle_generated = True
                                    st.session_state.ai_bundle_result = bundle_result
                                    st.session_state.bundle_file_path = bundle_result.get('bundle_path')
                                    st.session_state.validator_file_path = bundle_result.get('validator_path')
                                    
                                    st.success("✅ AI Validation Bundle generated successfully!")
                                    st.info(f"📁 Bundle saved to: `{bundle_result.get('bundle_path')}`")
                                    
                                    # Show immediate download options
                                    st.markdown("**📥 Immediate Downloads:**")
                                    download_col1, download_col2, download_col3 = st.columns(3)
                                    
                                    with download_col1:
                                        # Bundle download
                                        if bundle_result.get('bundle_path') and os.path.exists(bundle_result.get('bundle_path')):
                                            try:
                                                with open(bundle_result.get('bundle_path'), 'r', encoding='utf-8') as f:
                                                    bundle_content = f.read()
                                                st.download_button(
                                                    label="📦 Validation Bundle",
                                                    data=bundle_content,
                                                    file_name=f"{selected_object}_validation_bundle.py",
                                                    mime="text/x-python",
                                                    use_container_width=True,
                                                    key="immediate_bundle_download", on_click='ignore'
                                                )
                                            except Exception as e:
                                                st.error(f"Error: {str(e)}")
                                    
                                    with download_col2:
                                        # Validator download
                                        if bundle_result.get('validator_path') and os.path.exists(bundle_result.get('validator_path')):
                                            try:
                                                with open(bundle_result.get('validator_path'), 'r', encoding='utf-8') as f:
                                                    validator_content = f.read()
                                                st.download_button(
                                                    label="🔧 Standalone Validator",
                                                    data=validator_content,
                                                    file_name=f"{selected_object}_validator.py",
                                                    mime="text/x-python",
                                                    use_container_width=True,
                                                    key="immediate_validator_download", on_click='ignore'
                                                )
                                            except Exception as e:
                                                st.error(f"Error: {str(e)}")
                                    
                                    with download_col3:
                                        # Conversion summary download
                                        if hasattr(st.session_state, 'conversion_logs') and st.session_state.conversion_logs:
                                            summary_report = create_conversion_summary_report(st.session_state.conversion_logs)
                                            st.download_button(
                                                label="📊 Conversion Report",
                                                data=summary_report,
                                                file_name=f"{selected_object}_conversion_report.txt",
                                                mime="text/plain",
                                                use_container_width=True,
                                                key="immediate_report_download", on_click='ignore'
                                            )
                                    
                                    # Show conversion summary
                                    st.markdown("**📋 Conversion Summary:**")
                                    conversion_stats = bundle_result.get('conversion_stats', {})
                                    col_a, col_b, col_c = st.columns(3)
                                    
                                    with col_a:
                                        st.metric("Functions Created", conversion_stats.get('functions_created', 0))
                                    with col_b:
                                        st.metric("Successful Conversions", conversion_stats.get('successful_conversions', 0))
                                    with col_c:
                                        st.metric("Conversion Rate", f"{conversion_stats.get('success_rate', 0):.1f}%")
                                    
                                    # Show immediate Step 2 summary
                                    if hasattr(st.session_state, 'conversion_logs') and st.session_state.conversion_logs:
                                        st.markdown("**🔍 Conversion Results Summary:**")
                                        total_logs = len(st.session_state.conversion_logs)
                                        success_logs = sum(1 for log in st.session_state.conversion_logs if log['status'] == 'success')
                                        fail_logs = total_logs - success_logs
                                        
                                        if success_logs > 0:
                                            st.success(f"✅ {success_logs} validation rules converted successfully")
                                        if fail_logs > 0:
                                            st.warning(f"⚠️ {fail_logs} validation rules failed to convert")
                                        
                                        st.info("📋 Detailed conversion logs are available below in Step 2 section")
                                    
                                    _mark_val_tab(3)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to generate AI validation bundle")
                                    if bundle_result and bundle_result.get('error'):
                                        st.error(f"Error: {bundle_result.get('error')}")
                                    
                                    # Show conversion logs to help debug the issue
                                    conversion_logs = None
                                    if bundle_result and bundle_result.get('conversion_logs'):
                                        conversion_logs = bundle_result['conversion_logs']
                                    elif hasattr(st.session_state, 'conversion_logs'):
                                        conversion_logs = st.session_state.conversion_logs
                                    
                                    if conversion_logs:
                                        st.markdown("### 🔍 Detailed Conversion Logs")
                                        st.markdown("The following shows what happened during the conversion process:")
                                        
                                        failed_logs = [log for log in conversion_logs if log.get('status') == 'failed']
                                        
                                        if failed_logs:
                                            st.error(f"❌ {len(failed_logs)} validation rules failed to convert")
                                            
                                            with st.expander("📋 View Conversion Details", expanded=True):
                                                for i, log in enumerate(failed_logs[:5]):  # Show first 5 failed conversions
                                                    st.markdown(f"**Rule {i+1}: {log.get('rule_name', 'Unknown')}**")
                                                    if log.get('error'):
                                                        st.error(f"Error: {log['error']}")
                                                    if log.get('conversion_steps'):
                                                        for step in log['conversion_steps']:
                                                            st.text(f"  {step}")
                                                    st.markdown("---")
                                                
                                                if len(failed_logs) > 5:
                                                    st.info(f"... and {len(failed_logs) - 5} more failed conversions")
                                        else:
                                            st.warning("No detailed logs available")
                                    else:
                                        st.warning("⚠️ No conversion logs available. This might indicate an issue with the formula extraction or processing.")
                                    
                                    # Add a test conversion section for debugging
                                    if st.button("🧪 Test Conversion with Sample Formula"):
                                        st.markdown("### 🧪 Formula Conversion Test")
                                        
                                        # Get the first formula for testing
                                        if hasattr(st.session_state, 'formula_df') and not st.session_state.formula_df.empty:
                                            test_formula = st.session_state.formula_df.iloc[0]['ErrorConditionFormula']
                                            st.write(f"**Testing with first formula:** {str(test_formula)[:200]}...")
                                            
                                            try:
                                                from validation_script.GenAI_Validation import SalesforceFormulaConverter
                                                converter = SalesforceFormulaConverter()
                                                
                                                # Capture the test output
                                                import io
                                                import contextlib
                                                
                                                output_buffer = io.StringIO()
                                                with contextlib.redirect_stdout(output_buffer):
                                                    result = converter.test_basic_conversion(str(test_formula))
                                                
                                                # Display the captured output
                                                output_text = output_buffer.getvalue()
                                                if output_text:
                                                    st.text_area("Conversion Debug Output:", value=output_text, height=400)
                                                
                                                if result:
                                                    st.success(f"✅ Conversion result: {result}")
                                                else:
                                                    st.error("❌ Conversion failed")
                                                    
                                            except Exception as e:
                                                st.error(f"Test failed: {str(e)}")
                                        else:
                                            st.warning("No formulas available for testing")
                                    
                                    # Show conversion statistics if available
                                    if bundle_result and bundle_result.get('conversion_stats'):
                                        stats = bundle_result['conversion_stats']
                                        st.markdown("### 📊 Conversion Statistics")
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            st.metric("Total Rules", stats.get('total_formulas', 0))
                                        with col2:
                                            st.metric("Failed", stats.get('failed_conversions', 0))
                                        with col3:
                                            st.metric("Success Rate", f"{stats.get('success_rate', 0):.1f}%")
                                        
                            except Exception as e:
                                st.error(f"❌ Error generating AI bundle: {str(e)}")
                                st.exception(e)
                
                with col2:
                    if hasattr(st.session_state, 'ai_bundle_generated') and st.session_state.ai_bundle_generated:
                        st.markdown("**📁 Download AI Bundle:**")
                        
                        # Get file paths
                        bundle_path = st.session_state.get('bundle_file_path')
                        validator_path = st.session_state.get('validator_file_path')
                        
                        # Download validation bundle
                        if bundle_path and os.path.exists(bundle_path):
                            try:
                                with open(bundle_path, 'r', encoding='utf-8') as f:
                                    bundle_content = f.read()
                                
                                st.download_button(
                                    label="📦 Download Validation Bundle",
                                    data=bundle_content,
                                    file_name=f"{selected_object}_validation_bundle.py",
                                    mime="text/x-python",
                                    use_container_width=True,
                                    key="download_bundle", on_click='ignore'
                                )
                            except Exception as e:
                                st.error(f"Error reading bundle file: {str(e)}")
                        
                        # Download standalone validator
                        if validator_path and os.path.exists(validator_path):
                            try:
                                with open(validator_path, 'r', encoding='utf-8') as f:
                                    validator_content = f.read()
                                
                                st.download_button(
                                    label="🔧 Download Standalone Validator",
                                    data=validator_content,
                                    file_name=f"{selected_object}_validator.py",
                                    mime="text/x-python",
                                    use_container_width=True,
                                    key="download_validator", on_click='ignore'
                                )
                            except Exception as e:
                                st.error(f"Error reading validator file: {str(e)}")
                    else:
                        st.info("🤖 Generate AI bundle first to enable downloads")
                
                # Show AI bundle preview
                if hasattr(st.session_state, 'ai_bundle_result') and st.session_state.ai_bundle_result:
                    bundle_result = st.session_state.ai_bundle_result
                    
                    with st.expander("📋 AI Bundle Preview", expanded=False):
                        st.markdown("**🎯 Generated Functions:**")
                        
                        if 'function_mappings' in bundle_result and bundle_result['function_mappings']:
                            function_mappings = bundle_result['function_mappings']
                            for i, mapping in enumerate(function_mappings[:5]):  # Show first 5
                                st.code(f"""
# Rule: {mapping.get('rule_name', 'Unknown')}
# Function: {mapping.get('function_name', 'Unknown')}
# Object: {mapping.get('object', 'Unknown')}
# Field: {mapping.get('field', 'Unknown')}
# Formula: {mapping.get('formula', 'Unknown')[:100]}{'...' if len(str(mapping.get('formula', ''))) > 100 else ''}
""", language="python")
                            
                            if len(function_mappings) > 5:
                                st.info(f"Showing first 5 functions. Download bundle to see all {len(function_mappings)} functions.")
                        else:
                            st.info("No function mappings available in bundle preview.")
                
                # Display Step 2 Conversion Results (always show if available)
                if hasattr(st.session_state, 'conversion_logs') and st.session_state.conversion_logs:
                    st.markdown("---")
                    st.markdown("### 🔍 **Step 2: AI Conversion Results**")
                    
                    # Summary stats
                    total_rules = len(st.session_state.conversion_logs)
                    successful_rules = sum(1 for log in st.session_state.conversion_logs if log['status'] == 'success')
                    failed_rules = total_rules - successful_rules
                    success_rate = (successful_rules / total_rules * 100) if total_rules > 0 else 0
                    
                    # Display summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Rules", total_rules)
                    with col2:
                        st.metric("✅ Successful", successful_rules)
                    with col3:
                        st.metric("❌ Failed", failed_rules)
                    with col4:
                        st.metric("Success Rate", f"{success_rate:.1f}%")
                    
                    # Download options for conversion results
                    st.markdown("**📥 Download Conversion Results:**")
                    download_col1, download_col2 = st.columns(2)
                    
                    with download_col1:
                        # Create conversion summary report
                        summary_report = create_conversion_summary_report(st.session_state.conversion_logs)
                        st.download_button(
                            label="📊 Download Conversion Summary",
                            data=summary_report,
                            file_name=f"{selected_object}_conversion_summary.txt",
                            mime="text/plain",
                            use_container_width=True, on_click='ignore'
                        )
                    
                    with download_col2:
                        # Bundle download (if available)
                        if hasattr(st.session_state, 'bundle_file_path') and st.session_state.bundle_file_path:
                            bundle_path = st.session_state.bundle_file_path
                            if os.path.exists(bundle_path):
                                try:
                                    with open(bundle_path, 'r', encoding='utf-8') as f:
                                        bundle_content = f.read()
                                    
                                    st.download_button(
                                        label="📦 Download Validation Bundle",
                                        data=bundle_content,
                                        file_name=f"{selected_object}_validation_bundle.py",
                                        mime="text/x-python",
                                        use_container_width=True, on_click='ignore'
                                    )
                                except Exception as e:
                                    st.error(f"Error reading bundle file: {str(e)}")
                    

                
                # Only proceed to Step 3 if AI bundle is generated
                if hasattr(st.session_state, 'ai_bundle_generated') and st.session_state.ai_bundle_generated:
                    st.markdown("---")
                    
                    # Step 3: Upload Data for Validation
                    st.markdown("### 📊 **Step 3: Upload Data for Validation**")
                    st.markdown("""
                    **Upload your CSV or Excel data to validate against the generated Python functions.**
                    
                    ✨ **What this step does:**
                    - Accept CSV or Excel file uploads
                    - Apply all generated Python validation functions to each record
                    - Classify records as valid or invalid based on validation results
                    - Provide detailed error information for invalid records
                    """)
                    
                    # File upload
                    # Import Data Hub integration functions
                    try:
                        from ui_components.data_hub.integration import has_data, select_dataset_from_hub
                        data_hub_available = has_data()
                    except ImportError:
                        data_hub_available = False
                    
                    data_source_option = _flow_source_radio(
                        "📊 **Data Source:**",
                        ["Use Data Hub", "Upload File", "SQL Server", "Oracle"],
                        key="genai_data_source"
                    )

                    # Initialize session state for SF Validation Rules data
                    if 'genai_validation_data' not in st.session_state:
                        st.session_state.genai_validation_data = None
                    if (data_source_option != FLOW_SOURCE_OPTION
                            and _is_any_flow_origin(st.session_state.get('genai_validation_data_origin'))):
                        # Another source was picked: stop validating the Step 1 dataset.
                        st.session_state.genai_validation_data = None
                        st.session_state.genai_validation_data_origin = None
                        _clear_session_keys("genai_mapping_")

                    df = st.session_state.genai_validation_data

                    if data_source_option == FLOW_SOURCE_OPTION:
                        if not _is_flow_origin(st.session_state.get('genai_validation_data_origin')) or df is None:
                            df = _flow_df()
                            st.session_state.genai_validation_data = df
                            st.session_state.genai_validation_data_origin = _flow_origin()
                            _clear_session_keys("genai_mapping_")  # new columns: re-seed the grid
                        _show_flow_dataset_in_use()

                    elif data_source_option == "Use Data Hub" and data_hub_available:
                        hub_df = select_dataset_from_hub("genai_validation")
                        if hub_df is not None:
                            if st.button("✅ Load Selected Dataset", use_container_width=True, key="genai_load_from_hub"):
                                df = hub_df
                                st.session_state.genai_validation_data = df
                                st.session_state.genai_validation_data_origin = "hub"
                                st.success(f"✅ Data loaded from Hub: {len(df)} rows, {len(df.columns)} columns")
                                with st.expander("📊 Data Preview", expanded=False):
                                    st.dataframe(df.head(10), use_container_width=True)

                    elif data_source_option == "SQL Server":
                        sql_data = _load_validation_data_from_sql("genai_validation")
                        if sql_data is not None:
                            df = sql_data
                            st.session_state.genai_validation_data = df
                            st.session_state.genai_validation_data_origin = "sql"

                    elif data_source_option == "Oracle":
                        oracle_data = _load_validation_data_from_oracle("genai_validation")
                        if oracle_data is not None:
                            df = oracle_data
                            st.session_state.genai_validation_data = df
                            st.session_state.genai_validation_data_origin = "oracle"

                    elif data_source_option == "📁 File Library":
                        picked_df, picked_name = (show_file_picker_inline(
                            "genai_validation",
                            org_name=st.session_state.get('current_org'),
                            object_name=selected_object,
                        ) if show_file_picker_inline else (None, None))
                        if picked_df is not None:
                            df = picked_df
                            st.session_state.genai_validation_data = df
                            st.session_state.genai_validation_data_origin = "file_library"

                    else:
                        uploaded_file = st.file_uploader(
                            "📁 **Choose your data file:**",
                            type=['csv', 'xlsx', 'xls', 'psv'],
                            key="genai_data_upload",
                            help="Upload CSV, Excel, or PSV (Pipe-separated) files containing the data to validate"
                        )

                        if uploaded_file is not None:
                            df = load_data_file(uploaded_file)
                            if df is not None:
                                st.session_state.genai_validation_data = df
                                st.session_state.genai_validation_data_origin = "upload"
                                if register_source_file:
                                    register_source_file(
                                        uploaded_file, uploaded_file.name,
                                        org_name=st.session_state.get('current_org', 'unknown'),
                                        object_name=selected_object,
                                        row_count=len(df), col_count=len(df.columns),
                                    )
                                st.success(f"✅ Successfully loaded {len(df)} records from {uploaded_file.name}")

                                # Show data preview
                                with st.expander("📊 Data Preview", expanded=False):
                                    st.markdown(f"**File:** {uploaded_file.name}")
                                    st.markdown(f"**Records:** {len(df)}")
                                    st.markdown(f"**Columns:** {', '.join(df.columns.tolist())}")
                                    st.dataframe(df.head(), use_container_width=True)
                    
                    # Field Mapping Interface (show only if df is loaded)
                    if df is not None:
                        try:
                            # Read the uploaded file
                            st.markdown("---")
                            st.markdown("### 🔗 **Field Mapping Configuration**")
                            st.info("📋 Map your CSV columns to Salesforce Object fields for accurate validation")
                            
                            # Get Salesforce object fields
                            try:
                                from .utils import get_object_description
                                from ui_components.field_mapping_ui import auto_load_mapping
                                sf_object_info = get_object_description(sf_conn, selected_object)

                                if sf_object_info and 'fields' in sf_object_info:
                                    # Include all fields for validation (not just updateable ones)
                                    # We're validating data, not updating, so we should see all fields
                                    all_sf_fields = [field for field in sf_object_info['fields']
                                                    if not field.get('name', '').startswith('attributes')]

                                    # Create field mapping interface
                                    csv_columns = list(df.columns)
                                    
                                    # Try to auto-load saved mappings
                                    auto_loaded_mappings = auto_load_mapping(
                                        org_name=st.session_state.get('current_org', 'unknown'),
                                        object_name=selected_object,
                                        csv_columns=csv_columns,
                                        auto_apply=False,
                                        key_suffix='_genai_val'
                                    )
                                    
                                    if 'genai_field_mappings' not in st.session_state:
                                        st.session_state.genai_field_mappings = {}
                                    _seed_grid_from_flow('genai_field_mappings', 'genai_mapping_', 'sf_rules', csv_columns)
                                    if auto_loaded_mappings:
                                        # A saved mapping was applied in this run: drop the grid's
                                        # widget state so it re-seeds from the applied mapping.
                                        # Only the saved columns: the suggestion merge below fills the others.
                                        st.session_state.genai_field_mappings = {
                                            col: sf_field for col, sf_field in auto_loaded_mappings.items()
                                            if col in csv_columns
                                        }
                                        _clear_session_keys("genai_mapping_")
                                    _correct_known_validation_mappings(st.session_state.genai_field_mappings, all_sf_fields)
                                    
                                    # Use the same conservative suggestions as Enhanced Validation.
                                    suggested_mappings = _suggest_validation_field_mappings(
                                        csv_columns, all_sf_fields
                                    )
                                    
                                    # Initialize field mappings in session state with suggested mappings
                                    if 'genai_field_mappings' not in st.session_state:
                                        st.session_state.genai_field_mappings = suggested_mappings.copy()
                                    else:
                                        # Apply suggested mappings only for unmapped columns
                                        for csv_col, sf_field in suggested_mappings.items():
                                            if csv_col not in st.session_state.genai_field_mappings:
                                                st.session_state.genai_field_mappings[csv_col] = sf_field
                                    
                                    # Show auto-mapping summary
                                    if suggested_mappings:
                                        col_auto1, col_auto2 = st.columns([3, 1])
                                        with col_auto1:
                                            st.success(f"✅ Auto-mapped {len(suggested_mappings)} out of {len(csv_columns)} CSV columns to Salesforce fields")
                                        with col_auto2:
                                            if st.button("🔄 Reset Mappings", help="Clear all mappings and re-apply auto-mapping", key="genai_reset_mapping"):
                                                st.session_state.genai_field_mappings = suggested_mappings.copy()
                                                _clear_session_keys("genai_mapping_")
                                                _mark_val_tab(3)
                                                st.rerun()
                                    else:
                                        st.info("ℹ️ No automatic mappings found. Please map columns manually.")
                                    
                                    st.markdown("**🎯 Column Mapping Configuration:**")
                                    st.caption(f"{len(all_sf_fields)} fields available on {selected_object}")

                                    # Mapping interface
                                    field_mappings = {}
                                    sf_field_options = ["⚠️ No mapping"] + [f"{field['name']} ({field.get('label', field['name'])})" for field in all_sf_fields]
                                    sf_field_names = [""] + [field['name'] for field in all_sf_fields]
                                    option_by_field = dict(zip(sf_field_names[1:], sf_field_options[1:]))

                                    # Create mapping table
                                    col1, col2, col3 = st.columns([2, 3, 2])
                                    
                                    with col1:
                                        st.markdown("**CSV Column**")
                                    with col2:
                                        st.markdown("**Maps to Salesforce Field**")
                                    with col3:
                                        st.markdown("**Sample Data**")
                                    
                                    st.divider()
                                    
                                    for i, csv_column in enumerate(csv_columns):
                                        col1, col2, col3 = st.columns([2, 3, 2])
                                        
                                        with col1:
                                            st.write(f"**{csv_column}**")
                                        
                                        with col2:
                                            # Get current mapping or suggested mapping ("" = no mapping chosen)
                                            if csv_column in st.session_state.genai_field_mappings:
                                                current_mapping = st.session_state.genai_field_mappings[csv_column]
                                            else:
                                                current_mapping = suggested_mappings.get(csv_column, "")
                                            if current_mapping and current_mapping not in option_by_field:
                                                st.warning(f"⚠️ Mapped field '{current_mapping}' not found in available fields for '{csv_column}'. Resetting mapping.")
                                                current_mapping = ""
                                                st.session_state.genai_field_mappings.pop(csv_column, None)

                                            # Seed the widget before it is drawn (index= is ignored once
                                            # the key has state, which silently undid applied mappings).
                                            mapping_widget_key = f"genai_mapping_{i}_{csv_column}"
                                            if st.session_state.get(mapping_widget_key) not in sf_field_options:
                                                st.session_state[mapping_widget_key] = option_by_field.get(current_mapping, "⚠️ No mapping")
                                            selected_field = st.selectbox(
                                                f"Map {csv_column}",
                                                options=sf_field_options,
                                                key=mapping_widget_key,
                                                label_visibility="collapsed"
                                            )
                                            
                                            # Extract field name from selection
                                            if selected_field != "⚠️ No mapping":
                                                field_name = selected_field.split(' (')[0]
                                                field_mappings[csv_column] = field_name
                                                st.session_state.genai_field_mappings[csv_column] = field_name
                                            else:
                                                field_mappings[csv_column] = ""
                                                st.session_state.genai_field_mappings[csv_column] = ""
                                        
                                        with col3:
                                            # Show sample value
                                            sample_value = df[csv_column].dropna().iloc[0] if not df[csv_column].dropna().empty else "No data"
                                            st.caption(str(sample_value))

                                    _publish_grid_to_flow('genai_field_mappings', 'sf_rules')
                                    
                                    # Show mapping summary
                                    st.markdown("---")
                                    st.markdown("### 📋 **Field Mapping Summary**")
                                    
                                    mapped_fields = {k: v for k, v in field_mappings.items() if v}
                                    unmapped_fields = [k for k, v in field_mappings.items() if not v]
                                    
                                    if mapped_fields:
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.success(f"✅ **{len(mapped_fields)} columns mapped:**")
                                            for csv_col, sf_field in mapped_fields.items():
                                                st.write(f"  • `{csv_col}` → `{sf_field}`")
                                        
                                        with col2:
                                            if unmapped_fields:
                                                st.warning(f"⚠️ **{len(unmapped_fields)} columns not mapped:**")
                                                for csv_col in unmapped_fields:
                                                    st.write(f"  • `{csv_col}` (will be ignored)")
                                        
                                        # Add save mapping option
                                        from ui_components.field_mapping_ui import show_mapping_save_options
                                        show_mapping_save_options(
                                            org_name=st.session_state.get('current_org', 'unknown'),
                                            object_name=selected_object,
                                            field_mappings=mapped_fields,
                                            csv_columns=csv_columns,
                                            validation_type='genai'
                                        )
                                    else:
                                        st.warning("⚠️ No field mappings configured yet")
                                        st.info("💡 Configure at least one field mapping to run validation")
                                    
                                    # Store mappings for validation
                                    if mapped_fields:
                                        # Check for duplicate target mappings (multiple CSV columns → same SF field)
                                        target_fields = list(mapped_fields.values())
                                        unique_targets = list(set(target_fields))
                                        
                                        if len(unique_targets) < len(target_fields):
                                            # There are duplicate mappings
                                            duplicates_dict = {}
                                            for csv_col, sf_field in mapped_fields.items():
                                                if sf_field not in duplicates_dict:
                                                    duplicates_dict[sf_field] = []
                                                duplicates_dict[sf_field].append(csv_col)
                                            
                                            duplicate_mappings = {k: v for k, v in duplicates_dict.items() if len(v) > 1}
                                            st.warning(f"⚠️ **Multiple columns mapped to the same field:**")
                                            for sf_field, csv_cols in duplicate_mappings.items():
                                                st.write(f"  • `{sf_field}`: {', '.join(csv_cols)}")
                                            st.info("💡 **Resolution:** Only the last column mapping will be used for `{sf_field}`. Consider adjusting your mappings to avoid conflicts.")
                                        
                                        # Create mapped DataFrame with Salesforce field names
                                        mapped_df = df.copy()
                                        for csv_col, sf_field in mapped_fields.items():
                                            if csv_col != sf_field:
                                                mapped_df[sf_field] = mapped_df[csv_col]
                                        
                                        # Show mapped data preview
                                        st.markdown("### 👁️ **Mapped Data Preview**")
                                        with st.expander("View data with Salesforce field names", expanded=False):
                                            # Use unique mapped columns to avoid duplicate column names
                                            mapped_columns = list(dict.fromkeys(mapped_fields.values()))  # Remove duplicates while preserving order
                                            try:
                                                st.dataframe(mapped_df[mapped_columns].head(), use_container_width=True)
                                            except Exception as e:
                                                if "duplicate" in str(e).lower():
                                                    st.error("❌ Error displaying mapped data: Duplicate column names detected")
                                                    st.info("This occurs when multiple CSV columns map to the same Salesforce field. Adjust your mappings above.")
                                                else:
                                                    raise
                                        
                                        # Enable validation if mappings exist
                                        validation_enabled = True
                                        mapped_data = mapped_df
                                    else:
                                        validation_enabled = False
                                        mapped_data = None
                                
                                else:
                                    st.error("❌ Could not retrieve Salesforce object fields")
                                    validation_enabled = False
                                    mapped_data = None
                                    
                            except Exception as e:
                                st.error(f"❌ Error setting up field mapping: {str(e)}")
                                validation_enabled = False
                                mapped_data = None
                            
                            # Validation button
                            st.markdown("---")
                            st.markdown("### 🚀 **Run Validation**")
                            
                            if validation_enabled and mapped_data is not None:
                                if st.button("⚡ Validate Data", type="primary", use_container_width=True, key="run_genai_validation"):
                                    # Run GenAI validation with mapped data
                                    st.info("🔄 Running AI-powered validation...")
                                    
                                    try:
                                        # Store field mappings for validation function
                                        st.session_state.current_field_mappings = field_mappings
                                        
                                        # Load the validation bundle and run validation
                                        validation_results = run_genai_validation_on_data(mapped_data, st.session_state.ai_bundle_result)
                                        
                                        if validation_results and validation_results.get('success', False):
                                            st.session_state.genai_validation_results = validation_results
                                            st.session_state.genai_validation_completed = True
                                            st.session_state.genai_original_data = df  # Store original data for results
                                            # Guided flow: the bundle validated mapped_data = df plus
                                            # Salesforce-named copies of the mapped columns (same index).
                                            # Publish the SOURCE rows of df so the result follows the
                                            # contract (source columns + source->Salesforce mappings).
                                            valid_index = [i for i in validation_results['valid_df'].index if i in df.index]
                                            invalid_index = [i for i in validation_results['invalid_df'].index if i in df.index]
                                            genai_invalid = df.loc[invalid_index].copy()
                                            all_results_df = validation_results.get('all_df')
                                            if all_results_df is not None and 'validation_errors' in all_results_df.columns:
                                                genai_invalid['Validation_Errors'] = [
                                                    str(all_results_df.at[i, 'validation_errors']) if i in all_results_df.index else ''
                                                    for i in invalid_index
                                                ]
                                            _publish_step2_result(
                                                'SF Validation Rules', selected_object, df.loc[valid_index],
                                                genai_invalid, {k: v for k, v in field_mappings.items() if v},
                                                used_flow_dataset=_is_flow_origin(
                                                    st.session_state.get('genai_validation_data_origin')),
                                                sf_conn=sf_conn,
                                            )
                                            _mark_val_tab(3)
                                            st.rerun()
                                        else:
                                            st.error("❌ Validation failed")
                                            if validation_results and validation_results.get('error'):
                                                st.error(f"Error: {validation_results.get('error')}")
                                                
                                    except Exception as e:
                                        st.error(f"❌ Error during validation: {str(e)}")
                                        st.exception(e)
                            else:
                                st.warning("⚠️ Configure at least one field mapping to enable validation")
                                st.button("⚡ Validate Data", type="primary", use_container_width=True, disabled=True, key="run_genai_validation_disabled")
                            
                            # Show validation results if available
                            if hasattr(st.session_state, 'genai_validation_completed') and st.session_state.genai_validation_completed:
                                with genai_results_slot.container():
                                    st.markdown(f"### ✅ Latest SF Validation Rules result — {selected_object}")
                                    display_genai_validation_results(st.session_state.genai_validation_results, selected_object)
                                    st.caption("Steps 1–3 below produced this result; change them and validate "
                                               "again to update it.")
                                    st.markdown("---")
                                st.info("✅ Validation finished — the result is shown at the top of this tab.")
                            
                        except Exception as e:
                            st.error(f"❌ Error setting up validation: {str(e)}")
                    
                    else:
                        st.info("📤 Upload a CSV or Excel file or select from Data Hub to start validation")
                
                else:
                    st.info("🤖 Complete Step 2 (Generate AI Bundle) first before uploading data")
            
            else:
                # No bundle generated - show message to complete Step 2 first
                st.info("🤖 Complete Step 2 (Generate AI Bundle) first before uploading data")

def get_available_orgs():
    """Get list of available Salesforce organizations from linkedservices.json"""
    try:
        services_path = os.path.join(os.getcwd(), 'Services', 'linkedservices.json')
        if os.path.exists(services_path):
            with open(services_path, 'r') as f:
                services = json.load(f)
                return list(services.keys())
        return []
    except Exception as e:
        st.error(f"Error loading organizations: {str(e)}")
        return []

def get_salesforce_connection(org_name):
    """Get Salesforce connection for the specified organization"""
    try:
        from dataset.Connections import get_salesforce_connection as get_conn
        return get_conn(org_name=org_name)
    except Exception as e:
        st.error(f"Error connecting to {org_name}: {str(e)}")
        return None

def show_object_comparison():
    """Object Comparison interface - Compare objects between two Salesforce orgs"""
    st.subheader("🔄 Object Comparison")
    st.markdown("Compare Salesforce objects between two organizations to identify schema differences")
    
    # Initialize session state for object comparison
    if 'comparison_source_org' not in st.session_state:
        st.session_state.comparison_source_org = None
    if 'comparison_target_org' not in st.session_state:
        st.session_state.comparison_target_org = None
    if 'comparison_source_conn' not in st.session_state:
        st.session_state.comparison_source_conn = None
    if 'comparison_target_conn' not in st.session_state:
        st.session_state.comparison_target_conn = None
    
    # Step 1: Select Source and Target Orgs
    st.markdown("### 📍 Step 1: Select Organizations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔵 Source Organization")
        source_orgs = get_available_orgs()
        
        if source_orgs:
            source_org = st.selectbox(
                "Select Source Org",
                options=[""] + source_orgs,
                key="comparison_source_org_select",
                help="Select the source organization to compare from"
            )
            
            if source_org and source_org != "":
                # Connect to source org
                with st.spinner(f"Connecting to {source_org}..."):
                    source_conn = get_salesforce_connection(source_org)
                    if source_conn:
                        st.session_state.comparison_source_org = source_org
                        st.session_state.comparison_source_conn = source_conn
                        st.success(f"✅ Connected to {source_org}")
                    else:
                        st.error(f"❌ Failed to connect to {source_org}")
        else:
            st.warning("⚠️ No organizations configured")
    
    with col2:
        st.markdown("#### 🟢 Target Organization")
        target_orgs = get_available_orgs()
        
        if target_orgs:
            target_org = st.selectbox(
                "Select Target Org",
                options=[""] + target_orgs,
                key="comparison_target_org_select",
                help="Select the target organization to compare to"
            )
            
            if target_org and target_org != "":
                # Connect to target org
                with st.spinner(f"Connecting to {target_org}..."):
                    target_conn = get_salesforce_connection(target_org)
                    if target_conn:
                        st.session_state.comparison_target_org = target_org
                        st.session_state.comparison_target_conn = target_conn
                        st.success(f"✅ Connected to {target_org}")
                    else:
                        st.error(f"❌ Failed to connect to {target_org}")
        else:
            st.warning("⚠️ No organizations configured")
    
    # Check if both orgs are connected
    if not (st.session_state.comparison_source_conn and st.session_state.comparison_target_conn):
        st.info("👆 Please select and connect to both source and target organizations to proceed")
        return
    
    if st.session_state.comparison_source_org == st.session_state.comparison_target_org:
        st.warning("⚠️ Source and target organizations are the same. Please select different orgs for comparison.")
        return
    
    st.markdown("---")
    
    # Step 2: Select Objects to Compare
    st.markdown("### 📦 Step 2: Select Objects to Compare")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔵 Source Object")
        source_objects = get_salesforce_objects(st.session_state.comparison_source_conn, filter_custom=False)
        
        if source_objects:
            source_object = st.selectbox(
                "Select Source Object",
                options=[""] + source_objects,
                key="comparison_source_object",
                help="Select the source object to compare"
            )
        else:
            st.error("❌ Could not retrieve objects from source org")
            source_object = None
    
    with col2:
        st.markdown("#### 🟢 Target Object")
        target_objects = get_salesforce_objects(st.session_state.comparison_target_conn, filter_custom=False)
        
        if target_objects:
            target_object = st.selectbox(
                "Select Target Object",
                options=[""] + target_objects,
                key="comparison_target_object",
                help="Select the target object to compare"
            )
        else:
            st.error("❌ Could not retrieve objects from target org")
            target_object = None
    
    if not (source_object and target_object):
        st.info("👆 Please select objects from both organizations to compare")
        return
    
    st.markdown("---")
    
    # Step 3: Comparison Options
    st.markdown("### ⚙️ Step 3: Comparison Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        compare_fields = st.checkbox("Compare Fields", value=True, help="Compare field definitions")
        compare_record_types = st.checkbox("Compare Record Types", value=True, help="Compare record type configurations")
    
    with col2:
        compare_picklists = st.checkbox("Compare Picklist Values", value=True, help="Compare picklist/multi-select values")
        compare_layouts = st.checkbox("Compare Page Layouts", value=False, help="Compare page layout configurations")
    
    with col3:
        compare_validation_rules = st.checkbox("Compare Validation Rules", value=True, help="Compare validation rule formulas")
        compare_workflows = st.checkbox("Compare Workflow Rules", value=False, help="Compare workflow configurations")
    
    st.markdown("---")
    
    # Step 4: Run Comparison
    st.markdown("### 🚀 Step 4: Run Comparison")
    
    if st.button("🔍 Compare Objects", type="primary", use_container_width=True):
        with st.spinner("🔄 Comparing objects..."):
            comparison_result = compare_salesforce_objects(
                source_conn=st.session_state.comparison_source_conn,
                target_conn=st.session_state.comparison_target_conn,
                source_org=st.session_state.comparison_source_org,
                target_org=st.session_state.comparison_target_org,
                source_object=source_object,
                target_object=target_object,
                options={
                    'compare_fields': compare_fields,
                    'compare_record_types': compare_record_types,
                    'compare_picklists': compare_picklists,
                    'compare_layouts': compare_layouts,
                    'compare_validation_rules': compare_validation_rules,
                    'compare_workflows': compare_workflows
                }
            )
            
            if comparison_result and comparison_result.get('success'):
                st.session_state.comparison_result = comparison_result
                st.success("✅ Comparison completed successfully!")
                _mark_val_tab(4)
                st.rerun()
            else:
                st.error(f"❌ Comparison failed: {comparison_result.get('error', 'Unknown error')}")
    
    # Display comparison results
    if hasattr(st.session_state, 'comparison_result') and st.session_state.comparison_result:
        st.markdown("---")
        display_comparison_results(st.session_state.comparison_result)

def show_validation_reports():
    """Validation reports interface"""
    st.subheader("📊 Validation Reports")
    st.markdown("View and analyze validation results across different validation types")
    
    if not st.session_state.current_org:
        st.warning("⚠️ Please select an organization first")
        return
    
    # Get validation results
    validation_results = get_validation_results()
    
    if validation_results:
        # Report type selection
        report_type = st.selectbox(
            "Select Report Type",
            ["All Validations", "Schema Validation", "Custom Validation", "SF Validation Rules"],
            key="validation_report_type"
        )
        
        # Filter results based on report type
        if report_type != "All Validations":
            report_key = report_type.lower().replace(" ", "_")
            filtered_results = [
                r for r in validation_results
                if report_key in str(r.get('validation_type', '')).lower().replace(" ", "_")
            ]
        else:
            filtered_results = validation_results
        
        if filtered_results:
            # Display results summary
            show_validation_results_summary(filtered_results)
            
            # Detailed results
            st.write("### Detailed Results")
            
            for result in filtered_results:
                show_validation_result_detail(result)
        
        else:
            st.info(f"No {report_type.lower()} results found")
    
    else:
        st.info("No validation results found. Run some validations first.")

ALL_OBJECTS = "All objects"
ALL_METHODS = "All validation types"


def _run_when(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return str(iso or '')


def _run_pass_rate(run: Dict) -> float:
    return (run['valid'] / run['total'] * 100) if run.get('total') else 0.0


def _init_choice(key: str, options: list, preferred) -> None:
    """Default a history filter without passing a default to the widget (no Session State warning)."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = preferred if preferred in options else options[0]


def show_validation_summary():
    """Validation history: every run, newest first, for the sidebar org (and by default the current object).

    The latest result is also shown at the top of the Step 2 page; this tab is where the
    earlier runs are, one row each, instead of a scan of every result file on disk.
    """
    from ui_components.file_store_manager import list_output_files, list_validation_runs

    st.subheader("📋 Validation History")
    org = st.session_state.get('current_org')
    if not org:
        st.warning("⚠️ Please select an organization first")
        return
    st.caption("Every validation run is listed here, newest first. The latest result is also shown at the top "
               "of this page.")

    runs_all = list_validation_runs(org_name=org)
    current_object = step_flow.get_flow_object() or st.session_state.get('current_object')
    objects = sorted({r['object_name'] for r in runs_all if r['object_name']} | ({current_object} if current_object else set()))
    object_options = [ALL_OBJECTS] + objects
    method_options = [ALL_METHODS] + sorted({r['method'] for r in runs_all if r['method']})
    _init_choice('val_hist_object', object_options, current_object)
    _init_choice('val_hist_method', method_options, ALL_METHODS)

    col_obj, col_method = st.columns(2)
    with col_obj:
        chosen_object = st.selectbox("Object", object_options, key='val_hist_object')
    with col_method:
        chosen_method = st.selectbox("Validation type", method_options, key='val_hist_method')
    runs = [r for r in runs_all
            if chosen_object in (ALL_OBJECTS, r['object_name']) and chosen_method in (ALL_METHODS, r['method'])]

    if not runs:
        where = f" for **{chosen_object}**" if chosen_object != ALL_OBJECTS else ""
        st.info(f"No validation runs recorded yet{where}. Run a validation in one of the tabs — every run is "
                f"listed here, newest first.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Runs", len(runs))
        m2.metric("Last run", _run_when(runs[0]['created_at']))
        m3.metric("Average pass rate", f"{sum(_run_pass_rate(r) for r in runs) / len(runs):.1f}%")
        st.dataframe(pd.DataFrame([{
            '': '🟢 Latest' if i == 0 else '',
            'When': _run_when(r['created_at']), 'Type': r['method'], 'Object': r['object_name'],
            'Rows': r['total'], '✅ Valid': r['valid'], '❌ Invalid': r['invalid'],
            'Pass rate': f"{_run_pass_rate(r):.1f}%", 'Source': r['source'],
        } for i, r in enumerate(runs)]), hide_index=True, use_container_width=True)

        by_id = {r['id']: r for r in runs}
        _init_choice('val_hist_run', list(by_id), runs[0]['id'])
        run_id = st.selectbox(
            "🔎 Run details", list(by_id), key='val_hist_run',
            format_func=lambda i: (f"{_run_when(by_id[i]['created_at'])} · {by_id[i]['method']} · "
                                   f"{by_id[i]['object_name']} · {_run_pass_rate(by_id[i]):.0f}% valid"
                                   + ("  (latest)" if i == runs[0]['id'] else "")))
        _show_validation_run_detail(by_id[run_id], org)

    with st.expander("📁 Saved result files (also runs from before this history existed)", expanded=False):
        files = [f for f in list_output_files(org_name=org,
                                              object_name=None if chosen_object == ALL_OBJECTS else chosen_object)
                 if 'validation' in (f.get('operation_type') or '').lower()]
        if not files:
            st.caption("No saved validation result files for this selection.")
        else:
            st.dataframe(pd.DataFrame([{'When': _run_when(f['generated_at']), 'File': f['original_name'],
                                        'Type': f['operation_type'], 'Object': f['object_name'],
                                        'Rows': f['row_count']} for f in files]),
                         hide_index=True, use_container_width=True)
            st.caption("Newest first. Preview or download them in 📁 File Library.")


def _show_validation_run_detail(run: Dict, org: str) -> None:
    """One run: its numbers, and the result files saved with it (downloads do not rerun the page)."""
    from ui_components.file_store_manager import list_output_files
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", f"{run['total']:,}")
        c2.metric("✅ Valid", f"{run['valid']:,}")
        c3.metric("❌ Invalid", f"{run['invalid']:,}")
        c4.metric("Pass rate", f"{_run_pass_rate(run):.1f}%")
        st.caption(f"{run['method']} on {run['object_name']} · {_run_when(run['created_at'])} · "
                   f"{run['mapped_fields']} mapped fields · {run['source']}")
        try:
            started = datetime.fromisoformat(run['created_at'])
        except (TypeError, ValueError):
            return
        files = []
        for f in list_output_files(org_name=org, object_name=run['object_name'], limit=500):
            try:
                gap = abs((datetime.fromisoformat(f['generated_at']) - started).total_seconds())
            except (TypeError, ValueError):
                continue
            if gap <= 180 and os.path.exists(f['stored_path']):
                files.append(f)
        for f in files:
            st.download_button(f"📥 {f['original_name']}", on_click='ignore',
                               data=lambda path=f['stored_path']: open(path, 'rb').read(),
                               file_name=f['original_name'], key=f"val_hist_dl_{run['id']}_{f['id']}",
                               use_container_width=True)

# Helper functions
def show_object_schema(sf_conn, object_name: str):
    """Display object schema information"""
    try:
        obj_desc = get_object_description(sf_conn, object_name)
        
        if obj_desc:
            with st.expander(f"📋 {object_name} Schema", expanded=True):
                fields = obj_desc.get('fields', [])
                
                # Create schema DataFrame
                schema_data = []
                for field in fields:
                    schema_data.append({
                        "Field Name": field.get('name', ''),
                        "Label": field.get('label', ''),
                        "Type": field.get('type', ''),
                        "Length": field.get('length', '') or '',
                        "Required": not field.get('nillable', True),
                        "Updateable": field.get('updateable', False),
                        "Custom": field.get('custom', False)
                    })
                
                df_schema = pd.DataFrame(schema_data)
                st.dataframe(df_schema, use_container_width=True, height=400)
                
                # Get org name for folder organization
                try:
                    org_info = sf_conn.query("SELECT Name FROM Organization LIMIT 1")
                    org_name = org_info['records'][0]['Name'].replace(' ', '_') if org_info['records'] else 'Unknown_Org'
                except:
                    org_name = 'Unknown_Org'
                
                # Save to file with timestamp
                folder_path = get_validation_folder_path('Schema_Validation', org_name, object_name)
                schema_filename = get_timestamped_filename(f"{object_name}_schema")
                schema_file_path = save_validation_results_to_file(df_schema, folder_path, schema_filename)
                
                # Display file location info
                display_file_location_info(folder_path)
                
                # Download button (keep for immediate download option)
                csv_data = df_schema.to_csv(index=False)
                st.download_button(
                    label="📥 Quick Download Schema",
                    data=csv_data,
                    file_name=get_timestamped_filename(f"{object_name}_schema"),
                    mime="text/csv",
                    key="download_schema_csv",
                    help="Quick download - File also saved to folder above", on_click='ignore'
                )
    
    except Exception as e:
        st.error(f"❌ Error getting schema: {str(e)}")

def generate_sample_data(sf_conn, object_name: str) -> Optional[pd.DataFrame]:
    """Generate sample data for schema validation.

    Prefers real records queried from Salesforce so validation exercises actual
    data quality; falls back to field-type-based synthetic data if the object
    has no records yet or the query fails (e.g. insufficient field permissions).
    """
    try:
        with st.spinner(f"🎲 Generating sample data for {object_name}..."):
            fields = []
            try:
                obj_description = sf_conn.describe(object_name)
                fields = obj_description.get('fields', [])
                field_names = [f.get('name') for f in fields if f.get('name')][:15]

                if field_names:
                    query = f"SELECT {', '.join(field_names)} FROM {object_name} LIMIT 10"
                    result = sf_conn.query(query)
                    if result.get('records'):
                        clean_records = [
                            {k: v for k, v in record.items() if k != 'attributes'}
                            for record in result['records']
                        ]
                        df = pd.DataFrame(clean_records)
                        if not df.empty:
                            return df
                    st.info(f"No existing records found for {object_name}; generating synthetic sample data instead.")
            except Exception as e:
                st.warning(f"Could not query real records for {object_name}, generating synthetic sample data instead: {e}")

            # Fallback: synthesize data matching the object's field types
            if fields:
                num_records = 10
                sample_data = {}
                for field in fields[:10]:  # Limit to first 10 fields to keep manageable
                    field_name = field.get('name', '')
                    field_type = field.get('type', 'string')

                    if field_type == 'string':
                        sample_data[field_name] = [f"Sample {field_name} {i+1}" for i in range(num_records)]
                    elif field_type == 'int':
                        sample_data[field_name] = list(range(1, num_records + 1))
                    elif field_type == 'double':
                        sample_data[field_name] = [i * 1.5 for i in range(1, num_records + 1)]
                    elif field_type == 'boolean':
                        sample_data[field_name] = [i % 2 == 0 for i in range(num_records)]
                    elif field_type == 'date':
                        sample_data[field_name] = [f"2024-01-{i+1:02d}" for i in range(num_records)]
                    else:
                        sample_data[field_name] = [f"Value {i+1}" for i in range(num_records)]

                return pd.DataFrame(sample_data)

            # Last resort: describe() itself failed, so fall back to a generic shape
            generic_data = {
                'Name': [f'Sample Record {i+1}' for i in range(10)],
                'Email': [f'user{i+1}@example.com' for i in range(10)],
                'Phone': [f'555-000{i:04d}' for i in range(10)],
                'Status': ['Active' if i % 2 == 0 else 'Inactive' for i in range(10)],
                'Value': [i * 100 for i in range(10)]
            }
            return pd.DataFrame(generic_data)

    except Exception as e:
        st.error(f"❌ Error generating sample data: {str(e)}")
        return None

def run_schema_validation(sf_conn, object_name: str, data: pd.DataFrame, 
                         validate_required: bool, validate_datatypes: bool,
                         validate_formats: bool, validate_lengths: bool,
                         validate_picklists: bool, strict_mode: bool, field_mappings: dict,
                         org_name: str = None, used_flow_dataset: bool = False):
    """Run comprehensive schema validation with enhanced validation logic and field mapping

    Args:
        org_name: Optional - Salesforce org name for picklist mapping transformation
        used_flow_dataset: True when data is the guided-flow Step 1 dataset; the published
            result then unlocks Step 3.
    """
    
    # NOTE: Lookup resolution is NOT performed here
    # It's handled separately in the Lookup Resolution tab (TAB 6 in Org Migration)
    # Validation focuses only on: schema compliance, data types, field lengths, picklists, etc.
    
    # Show progress tracker immediately when validation starts
    progress_steps = [
        "Analyzing data structure",
        "Validating unique field constraints", 
        "Processing validation rules",
        "Generating validation report"
    ]
    
    # Create progress placeholder and show initial state immediately
    progress_placeholder = st.empty()
    with progress_placeholder.container():
        create_progress_tracker(progress_steps, 1)
    
    try:
        # Get object schema
        obj_desc = get_object_description(sf_conn, object_name)
        
        if not obj_desc:
            # Show error state in progress tracker instead of clearing
            with progress_placeholder.container():
                st.error("❌ **Schema Validation Failed**")
                st.write("**Could not retrieve object schema from Salesforce**")
            st.error("❌ Failed to get object schema")
            return
        
        # Initialize validation results
        validation_results = {
            'total_records': len(data),
            'validation_errors': [],
            'field_errors': {},
            'record_errors': {},
            'passed_records': 0,
            'failed_records': 0,
            'validated_data': data.copy()
        }
        
        # Step 2: Validate unique field constraints (dataset-wide)
        unique_errors = validate_unique_fields(data, obj_desc)
        validation_results['validation_errors'].extend(unique_errors)
        
        # Step 2.5: Master-Detail Relationship Validation (NEW)
        try:
            from validation_script.master_detail_validation_helper import (
                validate_master_detail_relationships_in_data
            )
            md_validation = validate_master_detail_relationships_in_data(obj_desc['fields'], data)
            
            # Store Master-Detail validation results
            validation_results['master_detail_validation'] = md_validation
            
            # Add Master-Detail errors to main validation results
            if md_validation['invalid_md_fields'] > 0:
                for field_name, field_report in md_validation['field_validations'].items():
                    if field_report['status'] == 'FAIL':
                        error_msg = field_report['message']
                        validation_results['validation_errors'].append(error_msg)
                        
                        # Mark affected rows
                        for row_idx in field_report['null_rows']:
                            if str(row_idx) not in validation_results['record_errors']:
                                validation_results['record_errors'][str(row_idx)] = []
                            validation_results['record_errors'][str(row_idx)].append(
                                f"Master-Detail field '{field_name}' is NULL"
                            )
        except ImportError:
            # Master-Detail validator not available in this installation
            pass
        except Exception as e:
            st.warning(f"⚠️ Could not run Master-Detail validation: {str(e)}")
        
        # Check for complete duplicate rows (all fields identical)
        # Returns dict: {row_index: error_message}
        duplicate_row_errors_dict = validate_complete_duplicate_rows(data)
        
        # Mark duplicate rows in record_errors and add to validation errors
        if duplicate_row_errors_dict:
            for row_idx, error_msg in duplicate_row_errors_dict.items():
                if row_idx >= 0:  # Skip general errors (row_idx = -1)
                    # Add to record_errors
                    if str(row_idx) not in validation_results['record_errors']:
                        validation_results['record_errors'][str(row_idx)] = []
                    validation_results['record_errors'][str(row_idx)].append(error_msg)
                    
                    # Add to overall validation errors
                    validation_results['validation_errors'].append(error_msg)
                else:
                    # General error
                    validation_results['validation_errors'].append(error_msg)
        
        with progress_placeholder.container():
            create_progress_tracker(progress_steps, 2)
        
        # Step 3: Validate each record comprehensively
        with progress_placeholder.container():
            create_progress_tracker(progress_steps, 3)
        
        for index, row in data.iterrows():
                # Use comprehensive row validation with field mappings
                row_errors = validate_comprehensive_row(
                    data, obj_desc, index, row,
                    validate_required, validate_datatypes, validate_formats,
                    validate_lengths, validate_picklists, field_mappings,
                    org_name, object_name
                )
                
                # Check if this row has duplicate row errors from Step 2
                if str(index) in validation_results['record_errors']:
                    # Add duplicate row errors to this row's errors
                    row_errors.extend(validation_results['record_errors'][str(index)])
                
                # Update validation results
                if row_errors:
                    validation_results['failed_records'] += 1
                    validation_results['validation_errors'].extend(row_errors)
                    validation_results['record_errors'][str(index)] = row_errors
                    
                    # Categorize errors by field
                    for error in row_errors:
                        # Extract field name from error message
                        if "Duplicate record found" in error and "all field values are identical" in error:
                            field_name = "Duplicate Records"
                        elif "Required field '" in error:
                            field_name = error.split("Required field '")[1].split("'")[0]
                        elif "field '" in error and "'" in error.split("field '")[1]:
                            field_name = error.split("field '")[1].split("'")[0]
                        elif "Duplicate value" in error and "field '" in error:
                            field_name = error.split("field '")[1].split("'")[0]
                        elif "Complete duplicate record" in error:
                            field_name = "Duplicate Records"
                        else:
                            field_name = "General"
                        
                        if field_name not in validation_results['field_errors']:
                            validation_results['field_errors'][field_name] = []
                        validation_results['field_errors'][field_name].append(error)
                else:
                    validation_results['passed_records'] += 1
            
        # Final progress update - show completion
        with progress_placeholder.container():
            create_progress_tracker(progress_steps, 4)
        
        # Keep the progress tracker visible (don't clear it)
        # Users can see the completed validation steps

        # Guided flow: valid rows (no errors) keep the SOURCE column names; field_mappings maps
        # them to Salesforce fields. Invalid rows carry their errors.
        record_errors = validation_results['record_errors']
        invalid_labels = [label for label in data.index if str(label) in record_errors]
        # Picklist validation checked the values AFTER the saved picklist value mappings;
        # publish those values (Step 3 does not apply picklist mappings).
        valid_rows = data.drop(index=invalid_labels)
        if validate_picklists:
            valid_rows = _apply_picklist_value_mappings(
                valid_rows, obj_desc, field_mappings, org_name, object_name)
        invalid_rows = data.loc[invalid_labels].copy()
        invalid_rows['Validation_Errors'] = [
            '; '.join(record_errors[str(label)]) if isinstance(record_errors[str(label)], list)
            else str(record_errors[str(label)])
            for label in invalid_labels
        ]
        _publish_step2_result(
            'Schema Validation', object_name, valid_rows, invalid_rows, field_mappings,
            used_flow_dataset=used_flow_dataset, sf_conn=sf_conn,
            summary={'errors': len(validation_results['validation_errors'])},
        )

        # Display comprehensive results
        display_enhanced_validation_results(validation_results, object_name, "Schema Validation")
        
        show_processing_status("schema_validation", 
                             f"Schema validation completed for {object_name} - {validation_results['passed_records']}/{validation_results['total_records']} records passed", 
                             "success" if validation_results['failed_records'] == 0 else "warning")

    except Exception as e:
        # Show failed state in progress tracker instead of clearing it
        try:
            with progress_placeholder.container():
                st.error("❌ **Schema Validation Failed**")
                st.write("**Error occurred during validation process**")
        except:
            pass  # If progress_placeholder doesn't exist, just continue
        
        st.error(f"❌ Schema validation failed: {str(e)}")
        show_processing_status("schema_validation", f"Schema validation failed: {str(e)}", "error")

def is_valid_email(email):
    """
    Validate email format using regex
    """
    if pd.isna(email) or email == "":
        return False
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, str(email)) is not None

def is_valid_phone(phone):
    """
    Validate phone number format according to Salesforce standards
    """
    if pd.isna(phone):
        return True  # Allow empty for non-required fields
    
    phone_str = str(phone).strip()
    if not phone_str:
        return True  # Allow empty string
    
    # Remove common phone formatting characters
    cleaned_phone = re.sub(r'[\s\-\(\)\+\.]', '', phone_str)
    
    # Salesforce phone validation:
    # - Must contain only digits (after cleaning)
    # - Length should be between 7-15 digits (international format consideration)
    if not cleaned_phone.isdigit():
        return False
    
    # Check length (7-15 digits is reasonable for most phone formats)
    # 7 digits: local numbers, 10 digits: US numbers, up to 15: international
    if len(cleaned_phone) < 7 or len(cleaned_phone) > 15:
        return False
    
    return True

def is_valid_date(date_value):
    """
    Validate date format
    """
    if pd.isna(date_value) or date_value == "":
        return False
    
    try:
        pd.to_datetime(date_value)
        return True
    except:
        return False

def validate_field_type(field_name: str, value, field_type: str) -> Optional[str]:
    """Validate field data type based on Salesforce field type"""
    try:
        # Skip validation for empty values unless it's a required field
        if pd.isna(value) or str(value).strip() == "":
            return None
            
        # Convert value to string for validation
        value_str = str(value).strip()
            
        if field_type == 'email':
            if not is_valid_email(value):
                return f"Invalid email format in field '{field_name}': {value}"
        
        elif field_type == 'phone':
            if not is_valid_phone(value):
                return f"Invalid phone format in field '{field_name}': {value}"
        
        elif field_type in ['int', 'integer']:
            try:
                # Check if it's a valid integer (can be decimal like 5.0 but must convert to int)
                float_val = float(value)
                if float_val != int(float_val):
                    return f"Invalid integer value in field '{field_name}': {value} (decimal values not allowed)"
                int(float_val)
            except (ValueError, TypeError):
                return f"Invalid integer value in field '{field_name}': {value}"
        
        elif field_type in ['double', 'currency', 'percent', 'number']:
            try:
                float(value)
            except (ValueError, TypeError):
                return f"Invalid numeric value in field '{field_name}': {value}"
        
        elif field_type == 'boolean':
            if str(value).lower() not in ['true', 'false', '1', '0', 'yes', 'no', 't', 'f']:
                return f"Invalid boolean value in field '{field_name}': {value}"
        
        elif field_type in ['date', 'datetime']:
            if not is_valid_date(value):
                return f"Invalid date format in field '{field_name}': {value}"
        
        elif field_type == 'url':
            url_pattern = r'^https?://.+'
            if not re.match(url_pattern, str(value)):
                return f"Invalid URL format in field '{field_name}': {value}"
                
        elif field_type in ['string', 'textarea', 'text']:
            # Enhanced string validation
            # Check if the value looks like it should be a number but is in a text field
            if value_str.replace('.', '').replace('-', '').replace('+', '').isdigit():
                # This is a number in a text field - might be intentional (like ID, postal code)
                # Be smarter about when to warn based on field name and value
                try:
                    num_val = float(value_str)
                    
                    # Don't warn for fields that commonly contain numbers
                    field_name_lower = field_name.lower()
                    if any(keyword in field_name_lower for keyword in ['postal', 'zip', 'code', 'id', 'number']):
                        return None  # These fields are expected to contain numbers
                    
                    # For address/street fields, warn if it's a large number without text
                    if any(keyword in field_name_lower for keyword in ['street', 'address', 'billing', 'shipping']):
                        if num_val > 9999:  # Large number in address field
                            return f"Warning: Numeric value '{value}' in text field '{field_name}' - verify this is appropriate for an address field"
                    
                    # For other text fields, warn about large numbers
                    elif num_val > 99999:  # Very large numbers in general text fields
                        return f"Warning: Large numeric value '{value}' in text field '{field_name}' - verify this is appropriate"
                        
                except:
                    pass
            
            # Text fields should generally contain text content
            # No error, just validation passed
            return None
            
        elif field_type == 'picklist':
            # Note: Actual picklist validation would require fetching picklist values from Salesforce
            # For now, we accept any value but could enhance this
            return None
            
        elif field_type in ['reference', 'id']:
            # ENHANCED: Lookup resolution - allows external IDs/codes to be resolved to Salesforce IDs
            # Don't reject non-ID format values - they'll be resolved during data load
            return None
    
    except Exception as e:
        return f"Error validating field type for '{field_name}': {str(e)}"
    
    return None

def validate_field_format(field_name: str, value, field_info: Dict) -> Optional[str]:
    """
    Validate field format based on field type and additional format requirements
    """
    if pd.isna(value) or str(value).strip() == "":
        return None
    
    try:
        field_type = field_info.get('type', '').lower()
        
        # Email format validation
        if field_type == 'email':
            if not is_valid_email(value):
                return f"Invalid email format in field '{field_name}': {value}"
        
        # Phone format validation  
        elif field_type == 'phone':
            if not is_valid_phone(value):
                return f"Invalid phone format in field '{field_name}': {value}"
        
        # Date format validation
        elif field_type in ['date', 'datetime']:
            if not is_valid_date(value):
                return f"Invalid date format in field '{field_name}': {value}"
        
        # URL format validation
        elif field_type == 'url':
            url_pattern = r'^https?://.+'
            if not re.match(url_pattern, str(value)):
                return f"Invalid URL format in field '{field_name}': {value}"
        
        # Currency format validation
        elif field_type == 'currency':
            currency_str = str(value).replace('$', '').replace(',', '').strip()
            try:
                float(currency_str)
            except ValueError:
                return f"Invalid currency format in field '{field_name}': {value}"
        
        # Percent format validation
        elif field_type == 'percent':
            percent_str = str(value).replace('%', '').strip()
            try:
                percent_val = float(percent_str)
                if percent_val < 0 or percent_val > 100:
                    return f"Percent value out of range (0-100) in field '{field_name}': {value}"
            except ValueError:
                return f"Invalid percent format in field '{field_name}': {value}"
        
    except Exception as e:
        return f"Error validating field format for '{field_name}': {str(e)}"
    
    return None

def validate_field_length(field_name: str, value, field_info: Dict) -> Optional[str]:
    """Validate field length according to Salesforce field definition"""
    if pd.isna(value) or str(value).strip() == "":
        return None

    value_str = str(value)
    field_type = field_info.get('type', '').lower()

    # Prefer the explicit length from field metadata when available
    length = field_info.get('length')
    if length is not None and len(value_str) > length:
        return f"Field '{field_name}' exceeds maximum length of {length} characters (current: {len(value_str)})"

    # Fall back to standard Salesforce field length limits when metadata has no explicit length
    # (common for email/phone/textarea fields)
    type_length_limits = {
        'text': 255,
        'string': 255,
        'textarea': 32768,  # Long text area can be up to 32KB
        'longtextarea': 131072,  # Rich text area up to 128KB
        'email': 80,
        'phone': 40,
        'url': 255
    }

    if length is None and field_type in type_length_limits:
        max_length = type_length_limits[field_type]
        if len(value_str) > max_length:
            return f"Field '{field_name}' of type '{field_type}' exceeds maximum length of {max_length} characters (current: {len(value_str)})"

    return None

def validate_required_fields_with_mapping(df: pd.DataFrame, object_description: Dict, row_index: int, row_data: pd.Series, field_mappings: dict) -> List[str]:
    """
    Validate required fields for a specific row using field mappings
    """
    errors = []
    
    try:
        fields = object_description.get('fields', [])
        required_fields = [field['name'] for field in fields if not field.get('nillable', True)]
        
        # Create reverse mapping (Salesforce field -> CSV column)
        reverse_mapping = {sf_field: csv_col for csv_col, sf_field in field_mappings.items()}
        
        for sf_field_name in required_fields:
            # Check if this required Salesforce field is mapped to a CSV column
            if sf_field_name in reverse_mapping:
                csv_column = reverse_mapping[sf_field_name]
                value = row_data[csv_column]
                if pd.isna(value) or str(value).strip() == "":
                    errors.append(f"Row {row_index + 1}: Required field '{csv_column}' (mapped to '{sf_field_name}') is empty")
    
    except Exception as e:
        errors.append(f"Row {row_index + 1}: Error validating required fields - {str(e)}")
    
    return errors

def validate_required_fields(df: pd.DataFrame, object_description: Dict, row_index: int, row_data: pd.Series) -> List[str]:
    """
    Validate required fields for a specific row
    """
    errors = []
    
    try:
        fields = object_description.get('fields', [])
        required_fields = [field['name'] for field in fields if not field.get('nillable', True)]
        
        for field_name in required_fields:
            if field_name in df.columns:
                value = row_data[field_name]
                if pd.isna(value) or str(value).strip() == "":
                    errors.append(f"Row {row_index + 1}: Required field '{field_name}' is empty")
    
    except Exception as e:
        errors.append(f"Row {row_index + 1}: Error validating required fields - {str(e)}")
    
    return errors

def validate_unique_fields(df: pd.DataFrame, object_description: Dict) -> List[str]:
    """
    Validate unique field constraints across the dataset
    """
    errors = []
    
    try:
        fields = object_description.get('fields', [])
        unique_fields = [field['name'] for field in fields if field.get('unique', False)]
        
        for field_name in unique_fields:
            if field_name in df.columns:
                # Check for duplicates in this field
                duplicates = df[df.duplicated(subset=[field_name], keep=False)]
                if not duplicates.empty:
                    duplicate_values = duplicates[field_name].unique()
                    for value in duplicate_values:
                        if not pd.isna(value) and str(value).strip() != "":
                            duplicate_rows = df[df[field_name] == value].index.tolist()
                            row_numbers = [str(i + 1) for i in duplicate_rows]
                            errors.append(f"Duplicate value '{value}' found in unique field '{field_name}' (rows: {', '.join(row_numbers)})")
    
    except Exception as e:
        errors.append(f"Error validating unique fields: {str(e)}")
    
    return errors

def validate_complete_duplicate_rows(df: pd.DataFrame) -> Dict[int, str]:
    """
    Validate for complete duplicate rows where all field values are identical
    Returns a dictionary mapping row index to error message for each duplicate row
    """
    duplicate_row_errors = {}
    
    try:
        # Find duplicate rows (all columns have same values)
        # duplicated(keep=False) marks all duplicates including the first occurrence
        duplicate_mask = df.duplicated(keep=False)
        
        if duplicate_mask.any():
            # For each duplicate row, add an error
            for idx in df[duplicate_mask].index:
                row_number = idx + 1  # Convert to 1-based for user display
                duplicate_row_errors[idx] = f"Duplicate record found at row {row_number} - all field values are identical to another row in the dataset"
    
    except Exception as e:
        # Add general error if something goes wrong
        duplicate_row_errors[-1] = f"Error validating complete duplicate rows: {str(e)}"
    
    return duplicate_row_errors

def validate_comprehensive_row(df: pd.DataFrame, object_description: Dict, row_index: int, row_data: pd.Series, 
                             validate_required: bool, validate_datatypes: bool, validate_formats: bool,
                             validate_lengths: bool, validate_picklists: bool, field_mappings: dict,
                             org_name: str = None, object_name: str = None) -> List[str]:
    """
    Perform comprehensive validation for a single row using field mappings
    
    Args:
        org_name: Optional - Salesforce org name for picklist mapping transformation
        object_name: Optional - Salesforce object name for picklist mapping transformation
    """
    errors = []
    
    try:
        # Required fields validation
        if validate_required:
            required_errors = validate_required_fields_with_mapping(df, object_description, row_index, row_data, field_mappings)
            errors.extend(required_errors)
        
        # Field-by-field validation using mappings
        fields = object_description.get('fields', [])
        field_info_map = {field['name']: field for field in fields}
        
        # Iterate through CSV columns and their mapped Salesforce fields
        for csv_column, sf_field_name in field_mappings.items():
            if sf_field_name in field_info_map:
                field_info = field_info_map[sf_field_name]
                value = row_data[csv_column]
                
                # Skip validation for empty values unless it's a required field check (already done above)
                if pd.isna(value) or str(value).strip() == "":
                    continue
                
                # Data type validation
                if validate_datatypes:
                    field_type = field_info.get('type', '').lower()
                    type_error = validate_field_type(sf_field_name, value, field_type)
                    if type_error:
                        # Update error message to include CSV column name
                        type_error = type_error.replace(f"field '{sf_field_name}'", f"field '{csv_column}' (mapped to '{sf_field_name}')")
                        errors.append(f"Row {row_index + 1}: {type_error}")
                
                # Format validation
                if validate_formats:
                    format_error = validate_field_format(sf_field_name, value, field_info)
                    if format_error:
                        # Update error message to include CSV column name
                        format_error = format_error.replace(f"field '{sf_field_name}'", f"field '{csv_column}' (mapped to '{sf_field_name}')")
                        errors.append(f"Row {row_index + 1}: {format_error}")
                
                # Length validation
                if validate_lengths:
                    length_error = validate_field_length(sf_field_name, value, field_info)
                    if length_error:
                        # Update error message to include CSV column name
                        length_error = length_error.replace(f"field '{sf_field_name}'", f"field '{csv_column}' (mapped to '{sf_field_name}')")
                        errors.append(f"Row {row_index + 1}: {length_error}")
                
                # Picklist validation
                if validate_picklists:
                    picklist_error = validate_picklist_value(sf_field_name, value, field_info, org_name, object_name)
                    if picklist_error:
                        # Update error message to include CSV column name
                        picklist_error = picklist_error.replace(f"field '{sf_field_name}'", f"field '{csv_column}' (mapped to '{sf_field_name}')")
                        errors.append(f"Row {row_index + 1}: {picklist_error}")
    
    except Exception as e:
        errors.append(f"Row {row_index + 1}: Error during comprehensive validation - {str(e)}")
    
    return errors

def validate_picklist_value(field_name: str, value, field_info: Dict, org_name: str = None, 
                           object_name: str = None) -> Optional[str]:
    """
    Validate picklist values with mapping transformation support
    
    Args:
        field_name: Salesforce field name
        value: Value to validate
        field_info: Field metadata from Salesforce
        org_name: Optional - Salesforce org name for loading mappings
        object_name: Optional - Salesforce object name for loading mappings
    
    Returns:
        Error message if invalid, None if valid
    """
    try:
        field_type = field_info.get('type', '')
        if field_type in ['picklist', 'multipicklist']:
            picklist_values = field_info.get('picklistValues', [])
            if picklist_values:
                valid_values = [pv.get('value', '') for pv in picklist_values if pv.get('active', True)]
                
                # Try to transform value using mappings if org/object provided
                original_value = value
                transformation_note = ""
                
                if org_name and object_name:
                    from .utils import transform_picklist_value
                    transformed_value = transform_picklist_value(org_name, object_name, field_name, str(value))
                    
                    if transformed_value != str(value):
                        value = transformed_value
                        transformation_note = f" (transformed from '{original_value}')"
                
                # Validate the (possibly transformed) value
                if str(value) not in valid_values:
                    # Build error message
                    sample_values = ', '.join(valid_values[:3])
                    if len(valid_values) > 3:
                        sample_values += f", ... ({len(valid_values)} total)"
                    
                    if transformation_note:
                        return f"Invalid picklist value in field '{field_name}': '{original_value}'{transformation_note}. Expected: {sample_values}"
                    else:
                        if org_name and object_name:
                            return f"Invalid picklist value in field '{field_name}': '{original_value}'. No mapping defined. Expected: {sample_values}"
                        else:
                            return f"Invalid picklist value in field '{field_name}': '{original_value}'. Expected: {sample_values}"
    except:
        pass
    
    return None

def display_validation_results(results: Dict, object_name: str, validation_type: str):
    """Display validation results"""
    st.success(f"✅ {validation_type} completed for {object_name}")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", results['total_records'])
    with col2:
        st.metric("Passed", results['passed_records'], 
                 delta=f"{(results['passed_records']/results['total_records']*100):.1f}%")
    with col3:
        st.metric("Failed", results['failed_records'],
                 delta=f"{(results['failed_records']/results['total_records']*100):.1f}%",
                 delta_color="inverse")
    with col4:
        st.metric("Total Errors", len(results['validation_errors']))
    
    # Error details
    if results['validation_errors']:
        with st.expander(f"❌ Validation Errors ({len(results['validation_errors'])})", expanded=False):
            for error in results['validation_errors'][:50]:  # Show first 50 errors
                st.error(error)
            
            if len(results['validation_errors']) > 50:
                st.info(f"... and {len(results['validation_errors']) - 50} more errors")
    
    # Field-wise error summary
    if results.get('field_errors'):
        with st.expander("📊 Field-wise Error Summary", expanded=False):
            for field_name, field_error_list in results['field_errors'].items():
                st.subheader(f"Field: {field_name}")
                for error in field_error_list[:10]:  # Show first 10 errors per field
                    st.text(f"• {error}")
                if len(field_error_list) > 10:
                    st.info(f"... and {len(field_error_list) - 10} more errors for this field")

def display_enhanced_validation_results(results: Dict, object_name: str, validation_type: str):
    """Display enhanced validation results with comprehensive reporting"""
    
    # Header with success/failure status
    if results['failed_records'] == 0:
        st.success(f"✅ {validation_type} completed successfully for {object_name} - All records passed!")
    elif results['passed_records'] == 0:
        st.error(f"❌ {validation_type} completed for {object_name} - All records failed validation!")
    else:
        st.warning(f"⚠️ {validation_type} completed for {object_name} - {results['failed_records']} records failed validation")
    
    # Display Master-Detail Validation Results if available (NEW)
    if 'master_detail_validation' in results:
        md_results = results['master_detail_validation']
        if md_results['total_md_fields'] > 0:
            st.subheader("🔗 Master-Detail Relationship Validation")
            
            md_col1, md_col2, md_col3 = st.columns(3)
            with md_col1:
                st.metric("Master-Detail Fields", md_results['total_md_fields'])
            with md_col2:
                st.metric("Valid ✅", md_results['valid_md_fields'])
            with md_col3:
                st.metric("Invalid ❌", md_results['invalid_md_fields'])
            
            if md_results['invalid_md_fields'] > 0:
                st.error(
                    f"🚫 **CRITICAL**: {md_results['critical_issues']} records have missing Master-Detail values. "
                    f"Master-Detail relationships are MANDATORY and cannot be NULL."
                )
                
                with st.expander("📋 Master-Detail Issues", expanded=True):
                    for field_name, field_report in md_results['field_validations'].items():
                        if field_report['status'] != 'PASS':
                            st.write(f"**{field_name}**")
                            st.write(f"- Status: {field_report['message']}")
                            if field_report['missing_count'] > 0:
                                st.write(f"- Missing Count: {field_report['missing_count']}")
            else:
                st.success("✅ All Master-Detail fields are valid (no missing values)")
            
            # Cascading delete warning
            st.warning(
                "⚠️ **Cascading Delete Warning**: "
                f"This object has Master-Detail relationships. "
                "If parent records are deleted, all child records will be automatically deleted."
            )
            st.markdown("---")
    
    # Enhanced Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Records", results['total_records'])
    with col2:
        success_rate = (results['passed_records']/results['total_records']*100) if results['total_records'] > 0 else 0
        st.metric("Passed", results['passed_records'], 
                 delta=f"{success_rate:.1f}%")
    with col3:
        failure_rate = (results['failed_records']/results['total_records']*100) if results['total_records'] > 0 else 0
        st.metric("Failed", results['failed_records'],
                 delta=f"{failure_rate:.1f}%",
                 delta_color="inverse")
    with col4:
        st.metric("Total Errors", len(results['validation_errors']))
    with col5:
        unique_fields_with_errors = len(results.get('field_errors', {}))
        st.metric("Fields with Issues", unique_fields_with_errors)
    
    # Validation Quality Assessment
    st.subheader("📈 Validation Quality Assessment")
    
    quality_cols = st.columns(3)
    with quality_cols[0]:
        if success_rate >= 95:
            st.success("🟢 Excellent Data Quality")
        elif success_rate >= 80:
            st.warning("🟡 Good Data Quality")
        elif success_rate >= 60:
            st.warning("🟠 Fair Data Quality")
        else:
            st.error("🔴 Poor Data Quality")
    
    with quality_cols[1]:
        avg_errors_per_record = len(results['validation_errors']) / results['total_records'] if results['total_records'] > 0 else 0
        st.metric("Avg Errors per Record", f"{avg_errors_per_record:.2f}")
    
    with quality_cols[2]:
        if results.get('field_errors'):
            most_problematic_field = max(results['field_errors'].items(), key=lambda x: len(x[1]))
            st.metric("Most Problematic Field", most_problematic_field[0])
            st.caption(f"{len(most_problematic_field[1])} errors")
    
    # Detailed Error Analysis
    if results['validation_errors']:
        st.subheader("🔍 Detailed Error Analysis")
        
        # Error type categorization (excluding duplicate records as they're shown separately)
        error_categories = {
            'Required Field Errors': [],
            'Data Type Errors': [], 
            'Format Errors': [],
            'Length Errors': [],
            'Picklist Errors': [],
            'Unique Constraint Errors': [],
            'Other Errors': []
        }
        
        for error in results['validation_errors']:
            # Skip duplicate record errors - they're shown in Failed Records section
            if 'Duplicate record found' in error and 'all field values are identical' in error:
                continue
            elif 'Complete duplicate record' in error:
                continue
            elif 'Required field' in error:
                error_categories['Required Field Errors'].append(error)
            elif 'Invalid email' in error or 'Invalid phone' in error or 'Invalid date' in error or 'Invalid URL' in error:
                error_categories['Format Errors'].append(error)
            elif 'Invalid' in error and ('numeric' in error or 'boolean' in error or 'integer' in error):
                error_categories['Data Type Errors'].append(error)
            elif 'exceeds maximum length' in error:
                error_categories['Length Errors'].append(error)
            elif 'Invalid picklist value' in error:
                error_categories['Picklist Errors'].append(error)
            elif 'Duplicate value' in error:
                error_categories['Unique Constraint Errors'].append(error)
            else:
                error_categories['Other Errors'].append(error)
        
        # Display error categories with counts
        for category, errors in error_categories.items():
            if errors:
                with st.expander(f"❌ {category} ({len(errors)})", expanded=False):
                    for error in errors[:20]:  # Show first 20 errors
                        st.error(error)
                    if len(errors) > 20:
                        st.info(f"... and {len(errors) - 20} more {category.lower()}")
    
    # Field-wise error summary with enhanced details
    if results.get('field_errors'):
        st.subheader("📊 Field-wise Error Summary")
        
        field_error_data = []
        for field_name, field_error_list in results['field_errors'].items():
            field_error_data.append({
                'Issue': field_name,
                'Error Count': len(field_error_list),
                'Error Rate': f"{(len(field_error_list)/results['total_records']*100):.1f}%"
            })
        
        field_error_df = pd.DataFrame(field_error_data)
        field_error_df = field_error_df.sort_values('Error Count', ascending=False)
        
        st.dataframe(field_error_df, use_container_width=True)
        
        # Detailed field errors
        for field_name, field_error_list in sorted(results['field_errors'].items(), key=lambda x: len(x[1]), reverse=True):
            with st.expander(f"Issue: {field_name} ({len(field_error_list)} errors)", expanded=False):
                for error in field_error_list[:15]:  # Show first 15 errors per field
                    st.text(f"• {error}")
                if len(field_error_list) > 15:
                    st.info(f"... and {len(field_error_list) - 15} more errors for this field")

    # Show Failed Records with Details
    if results.get('record_errors'):
        st.subheader("❌ Failed Records Details")
        
        failed_records_data = []
        for record_idx, record_error_list in results['record_errors'].items():
            failed_records_data.append({
                'Row Number': int(record_idx) + 1,  # Convert to 1-based for display
                'Error Count': len(record_error_list),
                'Errors': '; '.join(record_error_list)
            })
        
        failed_records_df = pd.DataFrame(failed_records_data)
        failed_records_df = failed_records_df.sort_values('Row Number')
        
        st.info(f"📊 Showing {len(failed_records_df)} failed records out of {results['total_records']} total records")
        
        # Show failed records in a table
        with st.expander(f"📋 View All Failed Records ({len(failed_records_df)} records)", expanded=True):
            st.dataframe(failed_records_df, use_container_width=True)
    
    # Show validated data preview
    if 'validated_data' in results and not results['validated_data'].empty:
        with st.expander("📊 Validated Data Preview", expanded=False):
            # Add validation status to preview
            preview_data = results['validated_data'].copy()
            
            # Add validation status column for preview
            validation_status = []
            for idx in range(len(preview_data)):
                if str(idx) in results.get('record_errors', {}):
                    validation_status.append('❌ FAILED')
                else:
                    validation_status.append('✅ PASSED')
            
            preview_data.insert(0, 'Validation Status', validation_status)
            
            # Show first 10 records
            st.dataframe(preview_data.head(10), use_container_width=True)
            
            if len(preview_data) > 10:
                st.info(f"Showing first 10 records. Complete dataset ({len(preview_data)} records) available in download.")
    
    # Download options for validation results
    st.subheader("📥 Download Validation Results")
    
    col_download1, col_download2 = st.columns(2)
    
    with col_download1:
        # Prepare comprehensive data for CSV download including original data
        
        # Get the original validated data if available
        validated_data = results.get('validated_data', pd.DataFrame())
        
        if not validated_data.empty:
            # Add validation results to the original data
            validated_data_with_results = validated_data.copy()
            
            # Get record errors for proper status assignment
            record_errors = results.get('record_errors', {})
            
            # Add validation status and errors columns
            validated_data_with_results['Validation_Status'] = ''
            validated_data_with_results['Validation_Errors'] = ''
            
            for idx in range(len(validated_data_with_results)):
                if str(idx) in record_errors:
                    # Record has errors - mark as FAILED
                    validated_data_with_results.at[idx, 'Validation_Status'] = 'FAILED'
                    validated_data_with_results.at[idx, 'Validation_Errors'] = '; '.join(record_errors[str(idx)])
                else:
                    # Record has no errors - mark as PASSED
                    validated_data_with_results.at[idx, 'Validation_Status'] = 'PASSED'
                    validated_data_with_results.at[idx, 'Validation_Errors'] = ''
            
            # Create comprehensive CSV with multiple sheets equivalent
            csv_data = "=== VALIDATION SUMMARY ===\n"
            summary_data = {
                'Metric': ['Total Records', 'Passed Records', 'Failed Records', 'Total Errors', 'Success Rate'],
                'Value': [
                    results['total_records'],
                    results['passed_records'], 
                    results['failed_records'],
                    len(results['validation_errors']),
                    f"{(results['passed_records']/results['total_records']*100):.2f}%" if results['total_records'] > 0 else "0%"
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            csv_data += summary_df.to_csv(index=False)
            
            csv_data += "\n\n=== VALIDATED DATASET WITH RESULTS ===\n"
            csv_data += validated_data_with_results.to_csv(index=False)
            
            csv_data += "\n\n=== DETAILED VALIDATION ERRORS ===\n"
            if results['validation_errors']:
                validation_errors_df = pd.DataFrame(results['validation_errors'], columns=['Error_Description'])
                csv_data += validation_errors_df.to_csv(index=False)
            else:
                csv_data += "No validation errors found.\n"
            
            csv_data += "\n\n=== FIELD-WISE ERROR SUMMARY ===\n"
            if results['field_errors']:
                field_error_data = []
                for field, errors in results['field_errors'].items():
                    field_error_data.append({
                        "Field_Name": field,
                        "Error_Count": len(errors),
                        "Error_Rate_Percent": f"{(len(errors)/results['total_records']*100):.2f}",
                        "Sample_Errors": '; '.join(errors[:3]) + ('...' if len(errors) > 3 else '')
                    })
                field_errors_df = pd.DataFrame(field_error_data)
                csv_data += field_errors_df.to_csv(index=False)
            else:
                csv_data += "No field-specific errors found.\n"
        else:
            # Fallback if no validated data available
            csv_data = "=== VALIDATION SUMMARY ===\n"
            summary_data = {
                'Metric': ['Total Records', 'Passed Records', 'Failed Records', 'Total Errors'],
                'Value': [
                    results['total_records'],
                    results['passed_records'], 
                    results['failed_records'],
                    len(results['validation_errors'])
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            csv_data += summary_df.to_csv(index=False)
            
            csv_data += "\n\n=== VALIDATION ERRORS ===\n"
            if results['validation_errors']:
                validation_errors_df = pd.DataFrame(results['validation_errors'], columns=['Error_Description'])
                csv_data += validation_errors_df.to_csv(index=False)
            else:
                csv_data += "No validation errors found.\n"
        
        # Get org name for folder organization (fallback to session state or default)
        try:
            if hasattr(st.session_state, 'current_org') and st.session_state.current_org:
                org_name = st.session_state.current_org.replace(' ', '_')
            else:
                org_name = 'Unknown_Org'
        except:
            org_name = 'Unknown_Org'
        
        # Save complete results to file
        folder_path = get_validation_folder_path('GenAI_Validation', org_name, object_name)
        complete_results_filename = get_timestamped_filename(f"{object_name}_{validation_type.lower().replace(' ', '_')}_complete_results")
        complete_results_path = os.path.join(folder_path, complete_results_filename)
        
        with open(complete_results_path, 'w', encoding='utf-8') as f:
            f.write(csv_data)
        # ...and list it in the File Library / Validation Summary like every other result file
        _bump_validation_results_version()
        if register_output_file:
            try:
                register_output_file(os.path.abspath(complete_results_path), original_name=complete_results_filename,
                                     org_name=st.session_state.get('current_org', 'unknown'),
                                     object_name=object_name, operation_type=validation_type,
                                     row_count=results.get('total_records', 0) or 0, status='generated')
            except Exception:
                pass

        # Save individual result files separately if validation was run
        if results.get('validated_data_with_results') is not None:
            success_data = results['validated_data_with_results'][results['validated_data_with_results']['Validation_Status'] == 'Valid']
            failure_data = results['validated_data_with_results'][results['validated_data_with_results']['Validation_Status'] == 'Invalid']
            
            if not success_data.empty:
                success_filename = get_timestamped_filename(f"{object_name}_genai_validation_success")
                save_validation_results_to_file(success_data, folder_path, success_filename)
            
            if not failure_data.empty:
                failure_filename = get_timestamped_filename(f"{object_name}_genai_validation_failure")
                save_validation_results_to_file(failure_data, folder_path, failure_filename)
        
        # Display file location info
        display_file_location_info(folder_path)
        
        st.download_button(
            label="📊 Quick Download Complete Results",
            data=csv_data,
            file_name=get_timestamped_filename(f"{object_name}_{validation_type.lower().replace(' ', '_')}_complete_results"),
            mime="text/csv",
            type="primary",
            use_container_width=True,
            key="complete_results_csv",
            help="Quick download - Files also saved to folder above", on_click='ignore'
        )
    
    with col_download2:
        # Enhanced JSON download with complete validation details and original data
        enhanced_results = results.copy()
        
        # Add metadata about the validation
        enhanced_results['validation_metadata'] = {
            'object_name': object_name,
            'validation_type': validation_type,
            'validation_timestamp': datetime.now().isoformat(),
            'org_name': st.session_state.get('current_org', 'Unknown')
        }
        
        # Include the validated data in JSON if available
        validated_data = results.get('validated_data', pd.DataFrame())
        if not validated_data.empty:
            enhanced_results['validated_dataset'] = validated_data.to_dict('records')
        
        json_data = json.dumps(enhanced_results, indent=2, default=str, ensure_ascii=False)
        
        st.download_button(
            label="📄 Download Complete Results (JSON)", 
            data=json_data,
            file_name=f"{object_name}_{validation_type.lower().replace(' ', '_')}_complete_results.json",
            mime="application/json",
            type="secondary",
            use_container_width=True,
            help="Download complete validation results including original data in JSON format",
            key="complete_results_json", on_click='ignore'
        )

# Placeholder functions for other validation types
def extract_validation_rules(sf_conn, object_name: str):
    """Extract validation rules from Salesforce"""
    
    try:
        with st.spinner(f"Extracting validation rules for {object_name}..."):
            validation_rules = []
            
            # Method 1: Try Tooling API
            try:
                # Construct Tooling API URL
                base_url = sf_conn.base_url
                if '/services/data/' in base_url:
                    # Extract version and construct tooling URL
                    parts = base_url.split('/services/data/')
                    if len(parts) > 1:
                        version_part = parts[1].rstrip('/')
                        tooling_url = f"{parts[0]}/services/data/{version_part}/tooling/query/"
                    else:
                        tooling_url = f"{base_url.rstrip('/')}/tooling/query/"
                else:
                    tooling_url = f"{base_url.rstrip('/')}/services/data/v58.0/tooling/query/"
                
                # Simple query for validation rules - REMOVED ValidationFormula (doesn't exist in API)
                query = f"""
                SELECT Id, FullName, Active, ErrorDisplayField, ErrorMessage, Description
                FROM ValidationRule 
                WHERE EntityDefinition.QualifiedApiName = '{object_name}'
                ORDER BY FullName
                """
                
                import requests
                headers = {
                    'Authorization': f'Bearer {sf_conn.session_id}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.get(tooling_url, headers=headers, params={'q': query})
                
                if response.status_code == 200:
                    tooling_data = response.json()
                    validation_rules = tooling_data.get('records', [])
                    if validation_rules:
                        st.success(f"✅ Found {len(validation_rules)} validation rules via Tooling API")
                    else:
                        st.info("No validation rules found for this object")
                else:
                    st.warning(f"Tooling API returned status {response.status_code}")
                    raise Exception(f"Tooling API failed with status {response.status_code}")
                    
            except Exception as tooling_error:
                st.warning(f"⚠️ Tooling API failed: {str(tooling_error)}")
                
                # Method 2: Create sample rules for demonstration
                st.info("Creating sample validation rule structure...")
                validation_rules = [
                    {
                        'Id': f'sample_rule_1',
                        'FullName': f'{object_name}_Required_Name',
                        'ValidationFormula': 'ISBLANK(Name)',  # This will fail if Name is blank
                        'Active': True,
                        'ErrorDisplayField': 'Name',
                        'ErrorMessage': f'Name field is required for {object_name}.',
                        'Description': f'Sample validation rule for {object_name} - Name field required'
                    },
                    {
                        'Id': f'sample_rule_2',
                        'FullName': f'{object_name}_Email_Format',
                        'ValidationFormula': 'AND(NOT(ISBLANK(Email)), NOT(REGEX(Email, "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")))',  # This will fail for invalid emails
                        'Active': True,
                        'ErrorDisplayField': 'Email',
                        'ErrorMessage': f'Please enter a valid email address for {object_name}.',
                        'Description': 'Sample email validation rule with actual formula'
                    },
                    {
                        'Id': f'sample_rule_3',
                        'FullName': f'{object_name}_Phone_Length',
                        'ValidationFormula': 'AND(NOT(ISBLANK(Phone)), LEN(Phone) < 10)',  # This will fail for short phone numbers
                        'Active': True,
                        'ErrorDisplayField': 'Phone',
                        'ErrorMessage': f'Phone number must be at least 10 digits for {object_name}.',
                        'Description': 'Sample phone validation rule with length check'
                    }
                ]
                st.warning("⚠️ Showing sample validation rules with actual validation formulas")
            
            # Display the rules
            if validation_rules:
                # Basic display of validation rules
                st.info(f"Found {len(validation_rules)} validation rules for {object_name}")
                for i, rule in enumerate(validation_rules):
                    rule_name = rule.get('FullName', f'Rule {i+1}')
                    status = "✅ Active" if rule.get('Active') else "❌ Inactive"
                    st.write(f"**{status} {rule_name}**")
                return validation_rules
            else:
                st.error(f"❌ No validation rules found for {object_name}")
                return None
            
    except Exception as e:
        st.error(f"❌ Error extracting validation rules: {str(e)}")
        return None


def create_sf_validation_client(sf_conn):
    """Create Salesforce validation client"""
    from .sf_validation_client import SalesforceValidationClient
    return SalesforceValidationClient(sf_conn)

def get_salesforce_objects(sf_conn, filter_custom=False) -> List[str]:
    """Get Salesforce objects list (queryable + createable; cached per org for the session)"""
    from ui_components.connection_manager import org_for_connection
    org = org_for_connection(sf_conn)
    cache = st.session_state.setdefault('_sf_objects_cache', {})
    cache_key = ('validation', org, filter_custom)
    if org and cache_key in cache:
        return list(cache[cache_key])
    objects = _fetch_validation_objects(sf_conn, filter_custom)
    if org and objects:
        cache[cache_key] = list(objects)
    return objects


def _fetch_validation_objects(sf_conn, filter_custom=False) -> List[str]:
    try:
        # Get org info and available objects
        objects_desc = sf_conn.describe()
        objects = []
        
        for obj in objects_desc['sobjects']:
            # Filter based on criteria
            if obj['queryable'] and obj['createable']:
                if filter_custom:
                    # Include both standard and custom objects that are commonly used
                    if obj['custom'] or obj['name'] in ['Account', 'Contact', 'Lead', 'Opportunity', 'Case']:
                        objects.append(obj['name'])
                else:
                    objects.append(obj['name'])
        
        return sorted(objects)
    
    except Exception as e:
        st.error(f"Error retrieving objects: {str(e)}")
        return []

def get_existing_validation_rules(object_name: str) -> Optional[List]:
    """Get existing validation rules from local files or previous extractions"""
    try:
        validation_dir = os.path.join(project_root, 'Validation')
        
        if not os.path.exists(validation_dir):
            return None
        
        # Look for validation rules files for this object
        found_rules = []
        
        for root, dirs, files in os.walk(validation_dir):
            for file in files:
                # Check if file name contains the object name and validation-related keywords
                if (object_name.lower() in file.lower() and 
                    any(keyword in file.lower() for keyword in ['validation', 'rules', 'rule'])):
                    
                    file_path = os.path.join(root, file)
                    
                    try:
                        if file.endswith('.json'):
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                                if isinstance(data, list):
                                    found_rules.extend(data)
                                elif isinstance(data, dict):
                                    found_rules.append(data)
                                    
                        elif file.endswith('.csv'):
                            df = pd.read_csv(file_path)
                            found_rules.extend(df.to_dict('records'))
                            
                    except Exception as file_error:
                        st.warning(f"Error reading file {file}: {str(file_error)}")
                        continue
        
        return found_rules if found_rules else None
        
    except Exception as e:
        st.warning(f"Error searching for existing validation rules: {str(e)}")
        return None

def display_validation_rules(rules: List):
    """Display validation rules in a user-friendly format"""
    if not rules:
        st.info("No validation rules found in local files")
        return
    
    st.success(f"Found {len(rules)} validation rule(s) in local files")
    
    # Convert rules to a consistent format for display
    formatted_rules = []
    for i, rule in enumerate(rules):
        if isinstance(rule, dict):
            # Extract rule name from various possible fields
            rule_name = (rule.get('FullName') or 
                        rule.get('ruleName') or 
                        rule.get('Rule Name') or 
                        f'Rule {i+1}')
            
            # Extract status from various possible fields  
            status = (rule.get('Active') or 
                     rule.get('active') or 
                     True)
            
            # Extract error field from various possible fields
            error_field = (rule.get('ErrorDisplayField') or 
                          rule.get('errorDisplayField') or 
                          rule.get('Error Field') or 
                          'N/A')
            
            # Extract error message from various possible fields
            error_message = (rule.get('ErrorMessage') or 
                           rule.get('errorMessage') or 
                           rule.get('Error Message') or 
                           'N/A')
            
            # Extract description from various possible fields
            description = (rule.get('Description') or 
                         rule.get('description') or 
                         'N/A')
            
            formatted_rule = {
                'Rule Name': rule_name,
                'Status': status,
                'Error Field': error_field,
                'Error Message': error_message,
                'Description': description
            }
        else:
            # Handle string or other formats
            formatted_rule = {
                'Rule Name': f'Rule {i+1}',
                'Status': True,
                'Error Field': 'N/A',
                'Error Message': str(rule),
                'Description': 'Imported rule'
            }
        
        formatted_rules.append(formatted_rule)
    
    # Display summary
    active_count = sum(1 for rule in formatted_rules if rule.get('Status'))
    inactive_count = len(formatted_rules) - active_count
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Rules", len(formatted_rules))
    with col2:
        st.metric("Active Rules", active_count)
    with col3:
        st.metric("Inactive Rules", inactive_count)
    
    # Display rules table
    display_data = []
    for rule in formatted_rules:
        display_data.append({
            'Rule Name': rule['Rule Name'],
            'Status': '✅ Active' if rule['Status'] else '❌ Inactive',
            'Error Field': rule['Error Field'],
            'Error Message': (rule['Error Message'][:60] + '...') if len(str(rule['Error Message'])) > 60 else rule['Error Message'],
            'Description': (rule['Description'][:40] + '...') if len(str(rule['Description'])) > 40 else rule['Description']
        })
    
    df_display = pd.DataFrame(display_data)
    st.dataframe(df_display, use_container_width=True)
    
    # Detailed view
    st.write("**Detailed Rule Information:**")
    for i, rule in enumerate(formatted_rules):
        status_icon = "✅" if rule['Status'] else "❌"
        with st.expander(f"{status_icon} {rule['Rule Name']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Rule Name:** {rule['Rule Name']}")
                st.write(f"**Status:** {'Active' if rule['Status'] else 'Inactive'}")
                st.write(f"**Error Field:** {rule['Error Field']}")
            
            with col2:
                st.write(f"**Description:** {rule['Description']}")
            
            st.write("**Error Message:**")
            st.code(rule['Error Message'], language="text")



def apply_validation_rule(row: pd.Series, rule: dict) -> bool:
    """Apply a single validation rule to a data row"""
    try:
        # Get rule information
        rule_name = rule.get('FullName', rule.get('name', rule.get('display_name', 'Unknown Rule')))
        formula = rule.get('ValidationFormula', rule.get('formula', ''))
        error_field = rule.get('ErrorDisplayField', rule.get('error_field', ''))
        error_message = rule.get('ErrorMessage', rule.get('error_message', ''))
        field_mappings = rule.get('field_mappings', {})
        
        # CRITICAL FIX 1: Check if field mappings are configured
        if not field_mappings:
            # No field mappings means we cannot apply this rule
            # Log this as a configuration issue but don't fail the record
            # Return True to avoid false negatives due to configuration issues
            # NOTE: The UI should warn users about this before validation
            return True
        
        # CRITICAL FIX 2: More strict validation for active rules
        # If we have field mappings, we should be able to validate properly
        
        # If no formula is available or formula is not accessible, use enhanced basic validation
        if not formula or formula in ['', 'No formula available', 'Formula not available', 'FORMULA_NOT_ACCESSIBLE_VIA_API']:
            result = apply_basic_validation(row, rule)
            return result
        
        # Try to apply Salesforce formula logic if formula is available
        result = apply_salesforce_formula(row, formula, error_field, field_mappings)
        return result
        
    except Exception as e:
        # CRITICAL FIX 3: More conservative exception handling
        rule_name = rule.get('FullName', rule.get('name', rule.get('display_name', 'Unknown Rule')))
        error_message = rule.get('ErrorMessage', rule.get('error_message', '')).lower()
        field_mappings = rule.get('field_mappings', {})
        
        # If we have field mappings but still failed, this is more serious
        if field_mappings:
            # If there's an error message suggesting this is a critical validation,
            # we should be strict
            if any(keyword in error_message for keyword in ['required', 'mandatory', 'cannot be blank', 'must not be empty']):
                # For critical validations with field mappings, if we can't process them, mark as invalid for safety
                return False
            else:
                # For non-critical validations with field mappings, try to be more conservative
                # If we can't process the rule but have mappings, assume it might be invalid
                return False  # Changed from True to False for better safety
        else:
            # No field mappings - configuration issue, assume valid to avoid false negatives
            return True

def apply_basic_validation(row: pd.Series, rule: dict) -> bool:
    """Apply enhanced intelligent validation based on comprehensive error message analysis"""
    try:
        # Get rule information with proper null checking
        rule_name = rule.get('FullName', rule.get('name', rule.get('display_name', ''))) or ''
        error_field = rule.get('ErrorDisplayField', rule.get('error_field', '')) or ''
        error_message = rule.get('ErrorMessage', rule.get('error_message', '')) or ''
        description = rule.get('Description', '') or ''
        
        # Get field mappings configured by user
        field_mappings = rule.get('field_mappings', {})
        
        # CRITICAL FIX 4: If no field mappings, cannot apply validation properly
        if not field_mappings:
            # Cannot validate without field mappings - return True to avoid false negatives
            # This should be caught earlier in apply_validation_rule
            return True
        
        # ENHANCED ERROR MESSAGE ANALYSIS
        # Combine all text for comprehensive analysis
        all_text = f"{rule_name} {error_message} {description}".lower()
        
        # CRITICAL FIX: DETERMINE IF THIS IS A REQUIRED FIELD VALIDATION
        is_required_field_rule = any(keyword in all_text for keyword in [
            'required', 'mandatory', 'cannot be blank', 'must not be empty',
            'must not be null', 'is required', 'should not be empty',
            'must be filled', 'cannot be empty', 'must have a value',
            'field is required', 'please enter', 'please provide'
        ])
        
        # INTELLIGENT FIELD IDENTIFICATION FROM ERROR MESSAGES
        # Enhanced field detection using multiple strategies
        target_sf_field = None
        target_csv_column = None
        
        # Strategy 1: Direct field mapping based on ErrorDisplayField
        if error_field and error_field in field_mappings:
            target_sf_field = error_field
            target_csv_column = field_mappings[error_field]
        
        # Strategy 2: Intelligent field detection from error message content
        elif field_mappings:
            
            # Enhanced field detection patterns
            field_detection_patterns = {
                'name': ['name', 'full name', 'first name', 'last name', 'company name', 'account name'],
                'email': ['email', 'e-mail', 'email address', '@', 'electronic mail'],
                'phone': ['phone', 'telephone', 'mobile', 'contact number', 'phone number', 'cell'],
                'address': ['address', 'street', 'city', 'state', 'zip', 'postal', 'country'],
                'date': ['date', 'birth date', 'start date', 'end date', 'created date'],
                'amount': ['amount', 'price', 'cost', 'value', 'total', 'sum'],
                'status': ['status', 'state', 'stage', 'phase'],
                'type': ['type', 'category', 'classification', 'kind'],
                'id': ['id', 'identifier', 'reference', 'number', 'code']
            }
            
            # Try to match field patterns with available mappings
            for field_type, patterns in field_detection_patterns.items():
                if not target_csv_column:  # Only if we haven't found a match yet
                    for pattern in patterns:
                        if pattern in all_text:
                            # Look for a mapped field that contains this pattern
                            for sf_field, csv_column in field_mappings.items():
                                if field_type in sf_field.lower() or pattern in sf_field.lower():
                                    target_sf_field = sf_field
                                    target_csv_column = csv_column
                                    break
                            if target_csv_column:
                                break
            
            # Strategy 3: ENHANCED Field name extraction from error message
            if not target_csv_column:
                # ENHANCED FIELD EXTRACTION PATTERNS
                enhanced_field_patterns = [
                    # Fields in single or double quotes
                    r"'([^']+)'\s+(?:field|must|cannot|should|is|are)",
                    r'"([^"]+)"\s+(?:field|must|cannot|should|is|are)',
                    
                    # Field names at sentence beginning
                    r"^([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:must|cannot|should|is required|is mandatory|field)",
                    
                    # Field names with specific validation keywords
                    r"([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:must be|cannot be|should be|is required|is mandatory)",
                    
                    # Fields mentioned with actions
                    r"(?:enter|provide|fill|specify|input|select)\s+(?:a\s+|an\s+|the\s+|valid\s+)?([A-Za-z][A-Za-z0-9_\s]*?)(?:\s|$|\.)",
                    
                    # Fields with error context
                    r"(?:invalid|missing|empty|blank|incorrect|wrong)\s+([A-Za-z][A-Za-z0-9_\s]*?)(?:\s|$|\.)",
                    
                    # Fields in "for" context
                    r"for\s+(?:the\s+)?([A-Za-z][A-Za-z0-9_\s]*?)(?:\s|$|\.)",
                    
                    # Field names before "field" keyword
                    r"([A-Za-z][A-Za-z0-9_\s]*?)\s+field",
                    
                    # Possessive field references
                    r"([A-Za-z][A-Za-z0-9_\s]*?)(?:'s|'s)\s+(?:value|format|length)",
                    
                    # Original patterns for backward compatibility
                    r"'([^']+)'\s+(?:field|is|must|cannot|should)",
                    r"(?:field|the)\s+'([^']+)'",
                    r"([A-Za-z_][A-Za-z0-9_]*)\s+(?:is|must|cannot|should)",
                    r"please\s+(?:enter|provide|fill)\s+(?:a\s+)?([A-Za-z_][A-Za-z0-9_]*)"
                ]
                
                extracted_field_candidates = []
                
                for pattern in enhanced_field_patterns:
                    matches = re.findall(pattern, error_message, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]  # Take first group if tuple
                        
                        # Clean and validate field name
                        field_name = match.strip()
                        
                        # Skip if too short, too long, or contains only common words
                        if (len(field_name) < 2 or len(field_name) > 50 or 
                            field_name.lower() in ['a', 'an', 'the', 'is', 'are', 'be', 'and', 'or', 'not', 'for', 'to', 'in', 'on', 'at', 'by', 'with']):
                            continue
                        
                        # Skip if it's a common validation word
                        validation_words = ['required', 'mandatory', 'optional', 'valid', 'invalid', 'format', 'pattern', 'value', 'number', 'text']
                        if field_name.lower() in validation_words:
                            continue
                        
                        extracted_field_candidates.append(field_name)
                
                # Try to match extracted field candidates with available mappings
                for field_candidate in extracted_field_candidates:
                    if target_csv_column:  # Stop if we found a match
                        break
                    
                    # Check if this field name exists in our mappings
                    for sf_field, csv_column in field_mappings.items():
                        # More flexible matching
                        if (field_candidate.lower() in sf_field.lower() or 
                            sf_field.lower() in field_candidate.lower() or
                            # Check for partial word matches
                            any(word in sf_field.lower() for word in field_candidate.lower().split()) or
                            any(word in field_candidate.lower() for word in sf_field.lower().split())):
                            target_sf_field = sf_field
                            target_csv_column = csv_column
                            break
            
        # ENHANCED CONSTRAINT EXTRACTION AND VALIDATION 
        if target_csv_column and target_csv_column in row.index:
            field_value = row[target_csv_column]
            
            # EXTRACT CONSTRAINTS FROM ERROR MESSAGE
            extracted_constraints = {}
            constraint_types = []
            
            # 1. LENGTH CONSTRAINTS (Check first since they often use numbers)
            length_patterns = [
                # Exact length
                r'(?:must\s+be\s+|exactly\s+|should\s+be\s+)?(\d+)\s+characters?\s+(?:long|in\s+length)',
                r'length\s+(?:of\s+|must\s+be\s+|should\s+be\s+)?(\d+)',
                # Minimum length
                r'(?:minimum|min|at\s+least)\s+(\d+)\s+characters?',
                r'(?:must\s+be\s+at\s+least|should\s+be\s+at\s+least)\s+(\d+)\s+characters?',
                # Maximum length  
                r'(?:maximum|max|at\s+most|no\s+more\s+than)\s+(\d+)\s+characters?',
                r'(?:must\s+not\s+exceed|cannot\s+exceed)\s+(\d+)\s+characters?',
                # Range length
                r'between\s+(\d+)\s+and\s+(\d+)\s+characters?',
                r'(\d+)\s*(?:to|-)\s*(\d+)\s+characters?',
            ]
            
            for pattern in length_patterns:
                matches = re.findall(pattern, error_message, re.IGNORECASE)
                if matches:
                    value_str = str(field_value) if not pd.isna(field_value) else ''
                    length = len(value_str)
                    
                    if 'minimum' in pattern or 'at least' in pattern:
                        min_length = int(matches[0])
                        extracted_constraints['min_length'] = min_length
                        constraint_types.append('min_length')
                        validation_result = length >= min_length
                        return validation_result
                    elif 'maximum' in pattern or 'at most' in pattern or 'exceed' in pattern:
                        max_length = int(matches[0])
                        extracted_constraints['max_length'] = max_length
                        constraint_types.append('max_length')
                        validation_result = length <= max_length
                        return validation_result
                    elif 'between' in pattern or 'to' in pattern or '-' in pattern:
                        if isinstance(matches[0], tuple) and len(matches[0]) == 2:
                            min_length = int(matches[0][0])
                            max_length = int(matches[0][1])
                            extracted_constraints['min_length'] = min_length
                            extracted_constraints['max_length'] = max_length
                            constraint_types.append('length_range')
                            validation_result = min_length <= length <= max_length
                            return validation_result
                    else:
                        exact_length = int(matches[0])
                        extracted_constraints['exact_length'] = exact_length
                        constraint_types.append('exact_length')
                        validation_result = length == exact_length
                        return validation_result
            
            # 2. RANGE CONSTRAINTS (For numeric values)
            range_patterns = [
                r'between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)\s+(?:years?|dollars?|units?|points?|$|%)?(?:\s+old)?',
                r'from\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s+(?:years?|dollars?|range)',
                r'(?:in\s+the\s+)?range\s+(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)',
            ]
            
            for pattern in range_patterns:
                # Skip if this is clearly a length constraint (has "characters")
                if 'characters' in error_message.lower():
                    continue
                    
                matches = re.findall(pattern, error_message, re.IGNORECASE)
                if matches:
                    min_val, max_val = float(matches[0][0]), float(matches[0][1])
                    extracted_constraints['min_value'] = min_val
                    extracted_constraints['max_value'] = max_val
                    constraint_types.append('range')
                    
                    # Apply range validation
                    try:
                        if pd.isna(field_value) or str(field_value).strip() == '':
                            return True  # Empty might be valid
                        num_value = float(str(field_value))
                        validation_result = min_val <= num_value <= max_val
                        return validation_result
                    except:
                        return False
            
            # 3. MINIMUM/MAXIMUM CONSTRAINTS (For numeric values)
            min_patterns = [
                r'(?:minimum|min|at\s+least|greater\s+than\s+or\s+equal\s+to|>=)\s+(\d+(?:\.\d+)?)\s+(?:dollars?|years?|units?|points?|for\s+this|$)?',
                r'must\s+be\s+(\d+(?:\.\d+)?)\s+or\s+(?:more|greater|higher)',
                r'(?:no\s+less\s+than|not\s+less\s+than)\s+(\d+(?:\.\d+)?)',
            ]
            
            max_patterns = [
                r'(?:maximum|max|at\s+most|no\s+more\s+than|less\s+than\s+or\s+equal\s+to|<=)\s+(\d+(?:\.\d+)?)',
                r'must\s+be\s+(\d+(?:\.\d+)?)\s+or\s+(?:less|fewer|lower)',
                r'(?:cannot\s+exceed|should\s+not\s+exceed|must\s+not\s+exceed)\s+(\d+(?:\.\d+)?)',
            ]
            
            # Check for minimum constraints (but not if already handled as length)
            for pattern in min_patterns:
                # Skip if this is clearly a length constraint
                if 'characters' in error_message.lower():
                    continue
                    
                matches = re.findall(pattern, error_message, re.IGNORECASE)
                if matches:
                    min_val = float(matches[0])
                    extracted_constraints['min_value'] = min_val
                    constraint_types.append('minimum')
                    
                    try:
                        if pd.isna(field_value) or str(field_value).strip() == '':
                            return True  # Empty might be valid
                        num_value = float(str(field_value))
                        validation_result = num_value >= min_val
                        return validation_result
                    except:
                        return False
            
            # Check for maximum constraints (but not if already handled as length)
            for pattern in max_patterns:
                # Skip if this is clearly a length constraint
                if 'characters' in error_message.lower():
                    continue
                    
                matches = re.findall(pattern, error_message, re.IGNORECASE)
                if matches:
                    max_val = float(matches[0])
                    extracted_constraints['max_value'] = max_val
                    constraint_types.append('maximum')
                    
                    try:
                        if pd.isna(field_value) or str(field_value).strip() == '':
                            return True  # Empty might be valid
                        num_value = float(str(field_value))
                        validation_result = num_value <= max_val
                        return validation_result
                    except:
                        return False
            
            # 4. VALUE CONSTRAINTS (Enhanced)
            # Allowed values
            allowed_value_patterns = [
                r'must\s+be\s+(?:one\s+of\s+)?(?:the\s+following:?\s*)?["\']([^"\']+)["\']',
                r'(?:only\s+|should\s+be\s+)?(?:one\s+of\s+)?["\']([^"\']+)["\'](?:\s+(?:or|,)\s+["\']([^"\']+)["\'])*',
                r'valid\s+values?\s+(?:are|include)?\s*:?\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in allowed_value_patterns:
                matches = re.findall(pattern, error_message, re.IGNORECASE)
                if matches:
                    allowed_values = []
                    for match in matches:
                        if isinstance(match, tuple):
                            allowed_values.extend([v for v in match if v])
                        else:
                            allowed_values.append(match)
                    
                    if allowed_values:
                        extracted_constraints['allowed_values'] = allowed_values
                        constraint_types.append('allowed_values')
                        value_str = str(field_value).strip() if not pd.isna(field_value) else ''
                        validation_result = value_str in allowed_values
                        return validation_result
            
            # 5. FORMAT CONSTRAINTS (Check before fallback patterns)
            # EMAIL FORMAT VALIDATION (ENHANCED)
            email_patterns = [
                'email', 'e-mail', '@', 'email format', 'valid email',
                'email address', 'electronic mail', 'mail format',
                'invalid email', 'email pattern'
            ]
            if any(pattern in all_text for pattern in email_patterns):
                validation_type_detected = "Email Format"
                field_value = row[target_csv_column] if target_csv_column in row.index else None
                is_empty = pd.isna(field_value) or str(field_value).strip() == ''
                
                # CRITICAL FIX: Handle missing email values properly
                if is_empty:
                    # If this is a required field rule, empty email should fail
                    if is_required_field_rule:
                        return False  # Required email field is empty
                    else:
                        # Email is optional, empty value is acceptable
                        return True
                else:
                    # Email has a value, validate the format
                    validation_result = validate_email_field(row, target_csv_column)
                    return validation_result
            
            # PHONE FORMAT VALIDATION (ENHANCED)
            phone_patterns = [
                'phone', 'telephone', 'mobile', 'contact number', 'phone number',
                'cell', 'cellular', 'phone format', 'invalid phone',
                'telephone number', 'contact info'
            ]
            if any(pattern in all_text for pattern in phone_patterns):
                validation_type_detected = "Phone Format"
                field_value = row[target_csv_column] if target_csv_column in row.index else None
                is_empty = pd.isna(field_value) or str(field_value).strip() == ''
                
                # CRITICAL FIX: Handle missing phone values properly
                if is_empty:
                    # If this is a required field rule, empty phone should fail
                    if is_required_field_rule:
                        return False  # Required phone field is empty
                    else:
                        # Phone is optional, empty value is acceptable
                        return True
                else:
                    # Phone has a value, validate the format
                    validation_result = validate_phone_field(row, target_csv_column)
                    return validation_result
            
            # FALL BACK TO ORIGINAL VALIDATION PATTERNS IF NO CONSTRAINTS EXTRACTED
            validation_type_detected = None
            validation_result = True
            
            # 1. REQUIRED/MANDATORY FIELD VALIDATION (ENHANCED)
            required_patterns = [
                'required', 'mandatory', 'cannot be blank', 'must not be empty', 
                'must not be null', 'is required', 'should not be empty',
                'must be filled', 'cannot be empty', 'must have a value',
                'field is required', 'please enter', 'please provide',
                'fill in', 'must specify', 'needs to be provided'
            ]
            if any(pattern in all_text for pattern in required_patterns):
                validation_type_detected = "Required Field"
                # ENHANCED REQUIRED FIELD VALIDATION
                field_value = row[target_csv_column] if target_csv_column in row.index else None
                is_empty = pd.isna(field_value) or str(field_value).strip() == ''
                
                # CRITICAL FIX: For required field rules, empty values should FAIL validation
                if is_empty:
                    # This is a required field and it's empty - validation fails
                    return False
                else:
                    # Field has a value - check if it meets other criteria
                    # For required field rules, having a non-empty value usually means it passes
                    # unless there are additional format/pattern requirements
                    
                    # Check for additional validation requirements in the same rule
                    has_format_requirement = any(fmt_pattern in all_text for fmt_pattern in [
                        'format', 'pattern', 'valid format', 'email format', 'phone format',
                        'must match', 'invalid format', 'format should be'
                    ])
                    
                    if has_format_requirement:
                        # This rule has both required and format requirements
                        # Continue to format validation below
                        pass
                    else:
                        # This is purely a required field rule - field has value, so it passes
                        return True
            
            # 4. DATE VALIDATION
            date_patterns = [
                'date', 'invalid date', 'date format', 'date range',
                'future date', 'past date', 'before today', 'after today',
                'date field', 'birth date', 'start date', 'end date'
            ]
            if any(pattern in all_text for pattern in date_patterns):
                validation_type_detected = "Date Format/Range"
                validation_result = validate_date_field(row, target_csv_column, all_text)
                return validation_result
            
            # 5. NUMERIC VALIDATION
            number_patterns = [
                'number', 'numeric', 'integer', 'decimal', 'amount',
                'must be a number', 'invalid number', 'positive number',
                'negative number', 'greater than', 'less than', 'price',
                'cost', 'value', 'total', 'sum', 'quantity'
            ]
            if any(pattern in all_text for pattern in number_patterns):
                validation_type_detected = "Numeric Value"
                validation_result = validate_number_field(row, target_csv_column, all_text)
                return validation_result
            
            # 6. LENGTH VALIDATION
            length_patterns = [
                'length', 'characters', 'minimum length', 'maximum length',
                'too long', 'too short', 'character limit', 'exceed',
                'min length', 'max length', 'char count'
            ]
            if any(pattern in all_text for pattern in length_patterns):
                validation_type_detected = "Length Constraint"
                validation_result = validate_length_field(row, target_csv_column, all_text)
                return validation_result
            
            # 7. FORMAT/PATTERN VALIDATION
            format_patterns = [
                'format', 'pattern', 'invalid format', 'valid format',
                'alphanumeric', 'special characters', 'contains',
                'must match', 'format should be', 'pattern must be'
            ]
            if any(pattern in all_text for pattern in format_patterns):
                validation_type_detected = "Format Pattern"
                validation_result = validate_format_field(row, target_csv_column, all_text)
                return validation_result
            
            # 8. DUPLICATE/UNIQUENESS VALIDATION
            unique_patterns = [
                'duplicate', 'already exists', 'unique', 'must be unique',
                'uniqueness', 'cannot duplicate', 'existing record'
            ]
            if any(pattern in all_text for pattern in unique_patterns):
                validation_type_detected = "Uniqueness Check"
                # For duplicate validation, we can't check without the full dataset
                return True
            
            # 9. BUSINESS LOGIC VALIDATION
            business_patterns = [
                'status', 'state', 'condition', 'relationship', 'dependency',
                'business rule', 'policy', 'must be', 'cannot be when',
                'if then', 'only when', 'except when'
            ]
            if any(pattern in all_text for pattern in business_patterns):
                validation_type_detected = "Business Logic"
                # Basic business logic validation
                if pd.isna(field_value) or str(field_value).strip() == '':
                    validation_result = False
                else:
                    validation_result = True
                return validation_result
            
            # 10. DEFAULT: UNKNOWN VALIDATION TYPE
            validation_type_detected = "Unknown/Custom"
            
            # Default validation: check if field is not empty for critical-sounding rules
            critical_keywords = ['error', 'invalid', 'wrong', 'incorrect', 'not allowed', 'forbidden']
            if any(keyword in all_text for keyword in critical_keywords):
                validation_result = not (pd.isna(field_value) or str(field_value).strip() == '')
            else:
                validation_result = True
            
            return validation_result
            
        # CRITICAL FIX 5: HANDLE CASES WHERE NO FIELD MAPPING IS FOUND
        else:
            # CRITICAL: If we have field mappings but couldn't identify the target field,
            # this indicates a validation rule that we cannot properly apply
            
            # For critical validations, be more conservative
            critical_keywords = ['required', 'mandatory', 'cannot be blank', 'must not be empty', 'error', 'invalid']
            if any(keyword in all_text for keyword in critical_keywords):
                # If this seems like a critical rule but we can't identify the field,
                # we should be conservative and mark as invalid to ensure data quality
                return False
            else:
                # For non-critical rules where we can't identify the field,
                # assume valid to avoid false negatives
                return True
            
    except Exception as e:
        st.warning(f"⚠️ Error in enhanced validation analysis: {str(e)}")
        st.exception(e)
        return True

def apply_salesforce_formula(row: pd.Series, formula: str, error_field: str, field_mappings: dict = None) -> bool:
    """Apply Salesforce formula logic to validate a row"""
    try:
        # Basic Salesforce formula conversions
        if 'ISBLANK' in formula or 'ISNULL' in formula:
            # Extract field name from formula
            field_match = re.search(r'(?:ISBLANK|ISNULL)\(([^)]+)\)', formula)
            if field_match:
                field_name = field_match.group(1).strip()
                if field_name in row.index:
                    value = row[field_name]
                    # Formula checks if blank, so we return False if it IS blank
                    return not (pd.isna(value) or str(value).strip() == '')
        
        elif 'LEN(' in formula:
            # Handle length validations
            length_match = re.search(r'LEN\(([^)]+)\)\s*([<>=!]+)\s*(\d+)', formula)
            if length_match:
                field_name = length_match.group(1).strip()
                operator = length_match.group(2).strip()
                threshold = int(length_match.group(3))
                
                if field_name in row.index:
                    value = str(row[field_name]) if not pd.isna(row[field_name]) else ''
                    length = len(value)
                    
                    if operator == '<':
                        # Formula condition is true when invalid, so we return opposite
                        return not (length < threshold)
                    elif operator == '>':
                        return not (length > threshold)
                    elif operator == '<=':
                        return not (length <= threshold)
                    elif operator == '>=':
                        return not (length >= threshold)
                    elif operator == '=' or operator == '==':
                        return not (length == threshold)
                    elif operator == '!=' or operator == '<>':
                        return not (length != threshold)
        
        elif 'REGEX(' in formula:
            # Handle regex validations
            regex_match = re.search(r'REGEX\(([^,]+),\s*"([^"]+)"\)', formula)
            if regex_match:
                field_name = regex_match.group(1).strip()
                pattern = regex_match.group(2)
                
                if field_name in row.index:
                    value = str(row[field_name]) if not pd.isna(row[field_name]) else ''
                    import re
                    # If formula starts with NOT, then valid when regex doesn't match
                    if formula.strip().startswith('NOT('):
                        return not bool(re.match(pattern, value))
                    else:
                        return bool(re.match(pattern, value))
        
        # If we can't parse the formula, assume valid
        return True
        
    except Exception:
        # If formula evaluation fails, assume valid to be safe
        return True

def validate_email_field(row: pd.Series, field_name: str) -> bool:
    """Validate email format"""
    if not field_name or field_name not in row.index:
        return True
    
    value = row[field_name]
    if pd.isna(value) or str(value).strip() == '':
        return True  # Empty email might be valid depending on requirement
    
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, str(value)))

def validate_phone_field(row: pd.Series, field_name: str) -> bool:
    """Validate phone format"""
    if not field_name or field_name not in row.index:
        return True
    
    value = row[field_name]
    if pd.isna(value) or str(value).strip() == '':
        return True  # Empty phone might be valid
    
    # Basic phone validation - contains digits and basic formatting
    import re
    phone_clean = re.sub(r'[^\d]', '', str(value))
    return len(phone_clean) >= 10  # At least 10 digits

def validate_not_null_field(row: pd.Series, field_name: str) -> bool:
    """Validate field is not null/empty"""
    if not field_name or field_name not in row.index:
        return True  # Field doesn't exist, assume valid
    
    value = row[field_name]
    is_empty = pd.isna(value) or str(value).strip() == ''
    
    # Return False if the field IS empty (validation fails)
    return not is_empty

def validate_date_field(row: pd.Series, field_name: str, all_text: str) -> bool:
    """Validate date field based on context"""
    if not field_name or field_name not in row.index:
        return True
    
    value = row[field_name]
    if pd.isna(value) or str(value).strip() == '':
        return True  # Empty date might be valid
    
    try:
        from datetime import datetime
        import dateutil.parser
        
        # Try to parse the date
        parsed_date = dateutil.parser.parse(str(value))
        
        # Additional date validation based on context
        if 'future date' in all_text or 'after today' in all_text:
            return parsed_date.date() > datetime.now().date()
        elif 'past date' in all_text or 'before today' in all_text:
            return parsed_date.date() < datetime.now().date()
        else:
            return True  # Valid date format
            
    except:
        return False  # Invalid date format

def validate_number_field(row: pd.Series, field_name: str, all_text: str) -> bool:
    """Validate number field based on context"""
    if not field_name or field_name not in row.index:
        return True
    
    value = row[field_name]
    if pd.isna(value) or str(value).strip() == '':
        return True  # Empty number might be valid
    
    try:
        num_value = float(str(value))
        
        # Additional number validation based on context
        if 'positive number' in all_text:
            return num_value > 0
        elif 'negative number' in all_text:
            return num_value < 0
        elif 'greater than zero' in all_text:
            return num_value > 0
        elif 'integer' in all_text:
            return num_value == int(num_value)
        else:
            return True  # Valid number
            
    except:
        return False  # Invalid number format

def validate_length_field(row: pd.Series, field_name: str, all_text: str) -> bool:
    """Validate field length based on context"""
    if not field_name or field_name not in row.index:
        return True
    
    value = str(row[field_name]) if not pd.isna(row[field_name]) else ''
    length = len(value)
    
    # Extract length requirements from context
    import re
    
    # Look for patterns like "minimum 5 characters", "maximum 10 characters", etc.
    min_match = re.search(r'(?:minimum|min|at least)\s+(\d+)', all_text)
    max_match = re.search(r'(?:maximum|max|no more than|up to)\s+(\d+)', all_text)
    exact_match = re.search(r'(?:exactly|must be)\s+(\d+)\s+characters?', all_text)
    
    if exact_match:
        required_length = int(exact_match.group(1))
        return length == required_length
    
    if min_match:
        min_length = int(min_match.group(1))
        if length < min_length:
            return False
    
    if max_match:
        max_length = int(max_match.group(1))
        if length > max_length:
            return False
    
    # Default length validations
    if 'too long' in all_text and length > 255:
        return False
    elif 'too short' in all_text and length < 1:
        return False
    
    return True

def validate_format_field(row: pd.Series, field_name: str, all_text: str) -> bool:
    """Validate field format based on context"""
    if not field_name or field_name not in row.index:
        return True
    
    value = str(row[field_name]) if not pd.isna(row[field_name]) else ''
    
    import re
    
    # Common format validations
    if 'alphanumeric' in all_text:
        return bool(re.match(r'^[a-zA-Z0-9]*$', value))
    elif 'no special characters' in all_text:
        return bool(re.match(r'^[a-zA-Z0-9\s]*$', value))
    elif 'uppercase' in all_text:
        return value.isupper()
    elif 'lowercase' in all_text:
        return value.islower()
    elif 'zip code' in all_text or 'postal code' in all_text:
        return bool(re.match(r'^\d{5}(-\d{4})?$', value))  # US zip code format
    
    return True  # Default to valid for unknown formats

def validate_business_logic(row: pd.Series, error_field: str, all_text: str, rule: dict) -> bool:
    """Validate business logic based on context"""
    if not error_field or error_field not in row.index:
        return True
    
    value = row[error_field]
    
    # Business logic validation based on context
    if 'status' in all_text:
        # Common status validations
        valid_statuses = ['active', 'inactive', 'pending', 'approved', 'rejected', 'draft']
        if not pd.isna(value):
            return str(value).lower() in valid_statuses
    
    elif 'stage' in all_text:
        # Common stage validations
        valid_stages = ['new', 'qualified', 'proposal', 'negotiation', 'closed won', 'closed lost']
        if not pd.isna(value):
            return str(value).lower() in valid_stages
    
    # Default business logic - ensure field has a value if mentioned in error
    return not (pd.isna(value) or str(value).strip() == '')

def get_validation_formula_file(object_name: str) -> Optional[str]:
    """Get validation formula file path"""
    return None

def display_validation_formulas(formula_file: str):
    """Display validation formulas"""
    st.write("Validation formulas display coming soon...")

def generate_formula_csv_for_ui(sf_conn, selected_org: str, object_name: str):
    """
    Generate Formula CSV file from Salesforce validation rules and make it available for UI download
    Based on Step2_validation_rules.py logic but integrated for UI
    
    Args:
        sf_conn: Salesforce connection object
        selected_org: Name of the selected organization  
        object_name: Name of the Salesforce object
        
    Returns:
        tuple: (dataframe, csv_content, file_path) or (None, None, None) on error
    """
    try:
        # Validate inputs
        if not sf_conn:
            st.error("❌ Invalid Salesforce connection")
            return None, None, None
        
        if not hasattr(sf_conn, 'session_id'):
            st.error("❌ Invalid Salesforce connection - missing session_id")
            return None, None, None
        
        session_id = sf_conn.session_id
        instance_url = sf_conn.sf_instance
        
        st.info(f"🔍 Extracting validation rules from {object_name}...")
        
        headers = {
            'Authorization': f'Bearer {session_id}',
            'Content-Type': 'application/json'
        }
        
        # Step 1: Get all validation rule Ids for the object
        val_url = f"https://{instance_url}/services/data/v59.0/tooling/query"
        id_query = (
            f"SELECT Id, ValidationName, ErrorMessage, Active, EntityDefinition.QualifiedApiName "
            f"FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}'"
        )
        
        with st.spinner("Fetching validation rule metadata..."):
            id_resp = requests.get(val_url, headers=headers, params={'q': id_query})
            id_json = id_resp.json()
            
            if not isinstance(id_json, dict):
                st.error("❌ Unexpected response from Salesforce Tooling API")
                return None, None, None
                
            val_rules = id_json.get('records', [])
            st.success(f"✅ Found {len(val_rules)} validation rule(s)")
        
        if not val_rules:
            st.warning(f"⚠️ No validation rules found for object '{object_name}'")
            return None, None, None
        
        validation_data = []
        
        # Step 2: For each Id, fetch Metadata (and formula)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, v in enumerate(val_rules):
            rule_name = v['ValidationName']
            status_text.text(f"Processing rule {i+1}/{len(val_rules)}: {rule_name}")
            progress_bar.progress((i + 1) / len(val_rules))
            
            rule_id = v['Id']
            meta_url = f"https://{instance_url}/services/data/v59.0/tooling/sobjects/ValidationRule/{rule_id}"
            
            try:
                meta_resp = requests.get(meta_url, headers=headers)
                meta_json = meta_resp.json()
                metadata = meta_json.get('Metadata', {})
                formula = metadata.get('errorConditionFormula', '') if isinstance(metadata, dict) else ''
                
                validation_data.append({
                    'ValidationName': v['ValidationName'],
                    'ErrorConditionFormula': formula,
                    'FieldName': '',  # Field parsing can be added later if needed
                    'ObjectName': object_name,
                    'Active': v['Active'],
                    'ErrorMessage': v['ErrorMessage'],
                    'Description': metadata.get('description', '') if isinstance(metadata, dict) else ''
                })
                
            except Exception as e:
                st.warning(f"⚠️ Could not fetch formula for rule '{rule_name}': {str(e)}")
                # Add rule without formula
                validation_data.append({
                    'ValidationName': v['ValidationName'],
                    'ErrorConditionFormula': 'FORMULA_NOT_ACCESSIBLE_VIA_API',
                    'FieldName': '',
                    'ObjectName': object_name,
                    'Active': v['Active'],
                    'ErrorMessage': v['ErrorMessage'],
                    'Description': 'Formula could not be retrieved'
                })
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Create DataFrame
        df = pd.DataFrame(validation_data)
        
        # Generate CSV content for download
        csv_content = df.to_csv(index=False)
        
        # Save to file system (following Step2 pattern)
        root_folder = "DataFiles"
        object_folder = os.path.join(root_folder, selected_org, object_name)
        os.makedirs(object_folder, exist_ok=True)
        csv_file_path = os.path.join(object_folder, "Formula_validation.csv")
        df.to_csv(csv_file_path, index=False)
        
        st.success(f"✅ Formula CSV generated successfully! ({len(df)} rules processed)")
        
        return df, csv_content, csv_file_path
        
    except Exception as e:
        st.error(f"❌ Error generating Formula CSV: {str(e)}")
        return None, None, None

def extract_validation_formulas_enhanced(selected_org: str, object_name: str):
    """Extract validation formulas from Salesforce and display in UI"""
    try:
        from validation_script.GenAI_Validation import extract_validation_rules_to_csv
        import json
        
        with st.spinner("🔍 Extracting validation rules from Salesforce..."):
            # Load credentials (the app's, via connection_manager - not a hard-coded file)
            credentials = connection_manager.get_credentials()
            
            # Extract validation rules to CSV
            validation_df, csv_file_path = extract_validation_rules_to_csv(
                credentials, selected_org, object_name
            )
            
            if validation_df is not None and len(validation_df) > 0:
                st.success(f"✅ Successfully extracted {len(validation_df)} validation rules!")
                
                # Display extracted rules in UI
                with st.expander("📋 Extracted Validation Rules", expanded=True):
                    st.write(f"**Total Rules Found:** {len(validation_df)}")
                    
                    # Show summary of rules
                    for i, rule in validation_df.iterrows():
                        rule_name = rule.get('ValidationName', f'Rule_{i+1}')
                        is_active = rule.get('Active', True)
                        formula = rule.get('ErrorConditionFormula', 'No formula')
                        error_msg = rule.get('ErrorMessage', 'No error message')
                        
                        status = "✅ Active" if is_active else "⚠️ Inactive"
                        st.write(f"**{i+1}. {rule_name}** - {status}")
                        
                        with st.expander(f"View Details: {rule_name}", expanded=False):
                            st.write("**Error Message:**")
                            st.write(error_msg)
                            st.write("**Apex Formula:**")
                            st.code(formula, language='sql')
                
                # Provide download button for CSV file
                csv_content = validation_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Validation Rules CSV",
                    data=csv_content,
                    file_name=f"{object_name}_validation_rules.csv",
                    mime="text/csv",
                    use_container_width=True, on_click='ignore'
                )
                
                # Store in session state for bundle generation
                st.session_state.extracted_validation_rules = validation_df.to_dict('records')
                st.session_state.validation_csv_path = csv_file_path
                
                return validation_df.to_dict('records')
                
            else:
                st.warning(f"⚠️ No validation rules found for {object_name}")
                return []
                
    except Exception as e:
        st.error(f"❌ Error extracting validation rules: {e}")
        if st.checkbox("🔍 Show error details"):
            st.exception(e)
        return []

def generate_ai_validation_bundle_step2(sf_conn, object_name: str, force_regenerate: bool = False):
    """
    Generate AI validation bundle from Formula CSV (Step 2 of GenAI workflow)
    Using enhanced AI conversion from GenAI_Validation.py
    
    Args:
        sf_conn: Salesforce connection object
        object_name: Name of the Salesforce object
        force_regenerate: Whether to regenerate even if bundle exists
    """
    try:
        # Check if we have formula CSV data
        if not (hasattr(st.session_state, 'formula_df') and 
                st.session_state.formula_df is not None and 
                not st.session_state.formula_df.empty):
            st.error("❌ No Formula CSV data available. Please complete Step 1 first.")
            return
        
        validation_df = st.session_state.formula_df
        selected_org = st.session_state.current_org
        
        progress_placeholder = st.empty()
        with progress_placeholder.container():
            st.info("🤖 Generating AI validation bundle...")
        
        # Create output directory structure
        root_dir = os.path.join("Validation", selected_org, object_name, "GenAIValidation")
        output_dir = os.path.join(root_dir, "validation_bundle")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(root_dir, "ValidatedData"), exist_ok=True)
        
        # Check if bundle already exists and force_regenerate is False
        bundle_path = os.path.join(output_dir, "bundle.py")
        validator_path = os.path.join(output_dir, "validator.py")
        
        if not force_regenerate and os.path.exists(bundle_path) and os.path.exists(validator_path):
            # Load existing bundle content into session state
            try:
                with open(bundle_path, 'r', encoding='utf-8') as f:
                    bundle_content = f.read()
                with open(validator_path, 'r', encoding='utf-8') as f:
                    validator_content = f.read()
                
                # Store in session state for persistent display
                st.session_state.genai_bundle_generated = True
                st.session_state.genai_bundle_content = bundle_content
                st.session_state.genai_validator_content = validator_content
                st.session_state.genai_bundle_path = bundle_path
                st.session_state.genai_validator_path = validator_path
                
                progress_placeholder.success("✅ AI bundle already exists and loaded into session. Use 'Force Regenerate' to recreate.")
            except Exception as e:
                progress_placeholder.error(f"❌ Bundle exists but could not load content: {str(e)}")
            return
        
        # Progress update
        with progress_placeholder.container():
            st.info("🧠 Converting Salesforce formulas to Python using AI...")
        
        # Use the enhanced bundle generation from GenAI_Validation.py
        try:
            bundle_path, validator_path, num_functions, function_mappings = generate_validation_bundle_from_dataframe(
                validation_df, selected_org, object_name, output_dir
            )
            
            # Read the generated files for UI display
            with open(bundle_path, 'r', encoding='utf-8') as f:
                bundle_content = f.read()
            
            with open(validator_path, 'r', encoding='utf-8') as f:
                validator_content = f.read()
            
            # Store in session state for persistent display
            st.session_state.genai_bundle_generated = True
            st.session_state.genai_bundle_content = bundle_content
            st.session_state.genai_validator_content = validator_content
            st.session_state.genai_bundle_path = bundle_path
            st.session_state.genai_validator_path = validator_path
            st.session_state.genai_num_functions = num_functions
            
            # Success message with details
            with progress_placeholder.container():
                st.success(f"✅ AI validation bundle generated successfully!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Validation Functions", num_functions)
                with col2:
                    st.metric("Bundle Size", f"{len(bundle_content):,} chars")
                with col3:
                    st.metric("Status", "Ready", "✅")
                
                st.info("  Bundle details and download options are displayed below in the persistent section.")
            
        except Exception as e:
            progress_placeholder.error(f"❌ Error generating AI bundle: {str(e)}")
            st.exception(e)
            
    except Exception as e:
        st.error(f"❌ Error in AI bundle generation: {str(e)}")
        st.exception(e)

def generate_ai_validation_bundle(object_name: str, validation_rules: list, force_regenerate: bool = False):
    """Generate AI validation bundle from Salesforce formulas using enhanced GenAI approach"""
    try:
        from validation_script.GenAI_Validation import generate_validation_bundle_from_dataframe
        import pandas as pd
        
        with st.spinner("🤖 Generating AI validation bundle..."):
            
            # Check if we have extracted validation rules in session state (preferred)
            if hasattr(st.session_state, 'extracted_validation_rules') and st.session_state.extracted_validation_rules:
                # Use the extracted rules directly (they're already in the right format)
                validation_df = pd.DataFrame(st.session_state.extracted_validation_rules)
                st.info("✅ Using extracted validation rules from Salesforce")
            else:
                # Convert validation rules list to DataFrame format (fallback for manual rules)
                validation_data = []
                for rule in validation_rules:
                    # Handle both old format (name, formula, etc.) and new format (ValidationName, ErrorConditionFormula, etc.)
                    validation_data.append({
                        'ValidationName': rule.get('ValidationName') or rule.get('name', ''),
                        'ErrorConditionFormula': rule.get('ErrorConditionFormula') or rule.get('formula', ''),
                        'FieldName': rule.get('FieldName', ''),  # Field parsing can be added later
                        'ObjectName': object_name,
                        'Active': rule.get('Active', rule.get('active', True)),
                        'ErrorMessage': rule.get('ErrorMessage') or rule.get('error_message', ''),
                        'Description': rule.get('Description') or rule.get('description', '')
                    })
                
                validation_df = pd.DataFrame(validation_data)
                st.info("✅ Using validation rules from manual entry")
            
            # Load org info from session state or linkedservices.json
            if hasattr(st.session_state, 'selected_org') and st.session_state.selected_org:
                selected_org = st.session_state.selected_org
            else:
                # Fallback: the sidebar org, else the first configured Salesforce org
                selected_org = st.session_state.get('current_org') or list(connection_manager.salesforce_orgs())[0]

            # Generate validation bundle using new function
            bundle_path, validator_path, num_functions, function_mappings = generate_validation_bundle_from_dataframe(
                validation_df, selected_org, object_name
            )
            
            if bundle_path and validator_path:
                st.success(f"✅ Successfully generated AI validation bundle with {num_functions} validation functions!")
                
                # Display bundle information with download options
                col1, col2 = st.columns(2)
                
                # Read bundle content for display and download
                try:
                    with open(bundle_path, 'r', encoding='utf-8') as f:
                        bundle_content = f.read()
                    
                    with open(validator_path, 'r', encoding='utf-8') as f:
                        validator_content = f.read()
                except Exception as e:
                    st.error(f"Error reading generated files: {e}")
                    bundle_content = ""
                    validator_content = ""
                
                with col1:
                    st.info('**AI Validation Bundle**')
                    st.download_button(
                        label="📥 Download Bundle.py",
                        data=bundle_content,
                        file_name=f"{object_name}_validation_bundle.py",
                        mime="text/python",
                        use_container_width=True, on_click='ignore'
                    )
                
                with col2:
                    st.info('**Validator Script**')
                    st.download_button(
                        label="📥 Download Validator.py",
                        data=validator_content,
                        file_name=f"{object_name}_validator.py",
                        mime="text/python",
                        use_container_width=True, on_click='ignore'
                    )
                
                # Show generated bundle content in the UI
                with st.expander("🔍 View Generated Bundle Code", expanded=False):
                    st.code(bundle_content, language='python')
                
                # Show validator content in the UI
                with st.expander("🔍 View Validator Script", expanded=False):
                    st.code(validator_content, language='python')
                
                # Show generated functions summary
                with st.expander("📋 Generated Validation Functions", expanded=True):
                    st.write(f"**Total Functions Generated:** {num_functions}")
                    for i, rule in enumerate(validation_rules):
                        rule_name = rule.get('name', f'Rule_{i+1}')
                        formula = rule.get('formula', 'No formula')
                        status = "✅ Active" if rule.get('active', True) else "⚠️ Inactive"
                        st.write(f"**{i+1}. {rule_name}** - {status}")
                        st.code(formula[:100] + ("..." if len(formula) > 100 else ""), language='text')
                
                # Enable step 3 (data upload) by setting session state
                st.session_state.genai_bundle_generated = True
                st.session_state.genai_bundle_path = bundle_path
                st.session_state.genai_validator_path = validator_path
                st.session_state.genai_object_name = object_name
                st.session_state.genai_bundle_content = bundle_content
                st.session_state.genai_validator_content = validator_content
                
                # Don't rerun immediately, let the UI update naturally
                
            else:
                st.error("❌ Failed to generate validation bundle")
                
    except Exception as e:
        st.error(f"❌ Error generating AI validation bundle: {str(e)}")
        st.exception(e)
    
    # Display existing bundle if it exists in session state (persistent display)
    if (hasattr(st.session_state, 'genai_bundle_generated') and 
        st.session_state.genai_bundle_generated and
        hasattr(st.session_state, 'genai_bundle_content') and
        hasattr(st.session_state, 'genai_validator_content')):
        
        st.success(f"✅ AI validation bundle is ready!")
        
        # Display bundle information with download options
        col1, col2 = st.columns(2)
        
        with col1:
            st.info('**AI Validation Bundle**')
            st.download_button(
                label="📥 Download Bundle.py",
                data=st.session_state.genai_bundle_content,
                file_name=f"{object_name}_validation_bundle.py",
                mime="text/python",
                use_container_width=True,
                key="persistent_bundle_download", on_click='ignore'
            )
        
        with col2:
            st.info('**Validator Script**')
            st.download_button(
                label="📥 Download Validator.py",
                data=st.session_state.genai_validator_content,
                file_name=f"{object_name}_validator.py",
                mime="text/python",
                use_container_width=True,
                key="persistent_validator_download", on_click='ignore'
            )
        
        # Show generated bundle content in the UI
        with st.expander("🔍 View Generated Bundle Code", expanded=False):
            st.code(st.session_state.genai_bundle_content, language='python')
        
        # Show validator content in the UI
        with st.expander("🔍 View Validator Script", expanded=False):
            st.code(st.session_state.genai_validator_content, language='python')

def generate_python_validation_code(object_name: str, validation_rules: list) -> str:
    """Convert Salesforce validation formulas to Python validation functions"""
    
    # Header with imports and utility functions
    code_template = f'''"""
Generated AI Validation Bundle for {object_name}
Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

This module contains Python validation functions converted from Salesforce validation rules.
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional

class ValidationResult:
    """Class to hold validation results"""
    def __init__(self, is_valid: bool, errors: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []

def safe_len(value) -> int:
    """Safe length function that handles None values"""
    if pd.isna(value) or value is None:
        return 0
    return len(str(value).strip())

def safe_regex(pattern: str, value) -> bool:
    """Safe regex function that handles None values"""
    if pd.isna(value) or value is None:
        return False
    try:
        import re
        return bool(re.match(pattern, str(value)))
    except:
        return False

def is_blank(value) -> bool:
    """Check if value is blank (None, NaN, or empty string)"""
    if pd.isna(value) or value is None:
        return True
    return str(value).strip() == ""

def not_blank(value) -> bool:
    """Check if value is not blank"""
    return not is_blank(value)

'''
    
    # Generate validation functions for each rule
    for i, rule in enumerate(validation_rules):
        # Handle different field name formats (GenAI vs Custom validation)
        rule_name = (rule.get('name') or 
                    rule.get('display_name') or 
                    rule.get('FullName') or 
                    f'rule_{i}')
        
        function_name = f"validate_{rule_name.replace(' ', '_').replace('-', '_').lower()}"
        
        # Get formula from different possible field names
        formula = (rule.get('formula') or 
                  rule.get('ValidationFormula') or 
                  rule.get('expression') or 
                  '')
        
        # Get error message from different possible field names  
        error_message = (rule.get('error_message') or 
                        rule.get('ErrorMessage') or 
                        rule.get('message') or 
                        f'Validation failed for {rule_name}')
        
        # Get active status
        is_active = rule.get('active', rule.get('Active', True))
        
        # Skip inactive rules
        if not is_active:
            continue
        
        # Convert Salesforce formula to Python
        python_formula = convert_salesforce_formula_to_python(formula)
        
        # Enhanced debug information
        formula_status = "✅ Has Formula" if formula and formula.strip() and formula != "FORMULA_NOT_ACCESSIBLE_VIA_API" else "❌ No Formula"
        st.write(f"🔄 Converting rule: **{rule_name}** - {formula_status}")
        
        if formula and formula.strip() and formula != "FORMULA_NOT_ACCESSIBLE_VIA_API":
            st.write(f"   📋 Original formula: `{formula}`")
            st.write(f"   🐍 Python formula: `{python_formula}`")
        else:
            st.write(f"   ⚠️ No formula available - creating placeholder validation")
            st.write(f"   🐍 Python formula: `{python_formula}` (always passes)")
        
        # Create validation function with enhanced logic
        if formula and formula.strip() and formula != "FORMULA_NOT_ACCESSIBLE_VIA_API":
            # Real validation function
            function_code = f'''
def {function_name}(row: pd.Series) -> ValidationResult:
    """
    Validation function for: {rule_name}
    Original Salesforce formula: {formula}
    Python formula: {python_formula}
    Error message: {error_message}
    Status: Active validation with real formula
    """
    try:
        # Converted Python logic - validation FAILS when this returns True
        validation_failed = {python_formula}
        
        if validation_failed:
            return ValidationResult(False, ["{error_message}"])
        else:
            return ValidationResult(True)
            
    except Exception as e:
        return ValidationResult(False, [f"Validation error in {rule_name}: {{str(e)}}"])
'''
        else:
            # Placeholder function for missing formulas
            function_code = f'''
def {function_name}(row: pd.Series) -> ValidationResult:
    """
    Placeholder validation function for: {rule_name}
    Original Salesforce formula: NOT AVAILABLE (API limitation)
    Error message: {error_message}
    Status: Placeholder - always passes due to missing formula
    """
    # No formula available - always pass validation
    # In real scenarios, this rule would need manual implementation
    return ValidationResult(True, [])  # Always pass
'''
        
        code_template += function_code
    
    # Add main validation function - only include active rules
    active_validation_functions = []
    for i, rule in enumerate(validation_rules):
        rule_name = (rule.get('name') or 
                    rule.get('display_name') or 
                    rule.get('FullName') or 
                    f'rule_{i}')
        is_active = rule.get('active', rule.get('Active', True))
        
        if is_active:
            function_name = f"validate_{rule_name.replace(' ', '_').replace('-', '_').lower()}"
            active_validation_functions.append(function_name)
    
    if not active_validation_functions:
        st.warning("⚠️ No active validation rules found - all records will be marked as valid")
        active_validation_functions = ['lambda row: ValidationResult(True)']  # Dummy function
    
    st.success(f"✅ Generated {len(active_validation_functions)} active validation functions")
    
    main_function = f'''
def validate_record(row: pd.Series) -> Dict[str, Any]:
    """
    Main validation function that runs all validation rules
    Returns dictionary with validation results
    """
    results = {{
        'is_valid': True,
        'errors': [],
        'rule_results': {{}}
    }}
    
    validation_functions = [{', '.join(active_validation_functions)}]
    
    for func in validation_functions:
        try:
            result = func(row)
            rule_name = func.__name__.replace('validate_', '') if hasattr(func, '__name__') else 'unknown'
            results['rule_results'][rule_name] = result.is_valid
            
            if not result.is_valid:
                results['is_valid'] = False
                results['errors'].extend(result.errors)
                
        except Exception as e:
            rule_name = func.__name__ if hasattr(func, '__name__') else 'unknown'
            results['is_valid'] = False
            results['errors'].append(f"Error in {{rule_name}}: {{str(e)}}")
    
    return results

def validate_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict]]:
    """
    Validate entire dataframe
    Returns: (valid_records, invalid_records, error_summary)
    """
    validation_results = []
    valid_indices = []
    invalid_indices = []
    
    for idx, row in df.iterrows():
        result = validate_record(row)
        validation_results.append({{
            'index': idx,
            'is_valid': result['is_valid'],
            'errors': result['errors'],
            'rule_results': result['rule_results']
        }})
        
        if result['is_valid']:
            valid_indices.append(idx)
        else:
            invalid_indices.append(idx)
    
    valid_df = df.loc[valid_indices] if valid_indices else pd.DataFrame(columns=df.columns)
    invalid_df = df.loc[invalid_indices] if invalid_indices else pd.DataFrame(columns=df.columns)
    
    return valid_df, invalid_df, validation_results
'''
    
    code_template += main_function
    return code_template

def convert_salesforce_formula_to_python(formula: str) -> str:
    """Convert Salesforce formula syntax to Python"""
    if not formula or formula == "FORMULA_NOT_ACCESSIBLE_VIA_API" or formula.strip() == "":
        return "False"  # If no formula, default to always pass validation (never fail)
    
    # Handle sample formulas and real formulas
    python_formula = formula.strip()
    
    # Basic conversions from Salesforce to Python
    conversions = {
        'ISBLANK(': 'is_blank(',
        'NOT(': 'not (',
        'LEN(': 'safe_len(',
        'REGEX(': 'safe_regex(',
        'AND(': '(',
        '&&': ' and ',
        '||': ' or ',
        '!': ' not ',
        '=': '==',
        '<>': '!=',
    }
    
    for sf_syntax, py_syntax in conversions.items():
        python_formula = python_formula.replace(sf_syntax, py_syntax)
    
    # Handle field references - convert to row access
    # Match field names that aren't Python keywords
    python_formula = re.sub(
        r'\b([A-Za-z_][A-Za-z0-9_]*)\b(?![(\'])', 
        lambda m: f"row.get('{m.group(1)}', '')" if m.group(1) not in ['not', 'and', 'or', 'True', 'False', 'None', 'is_blank', 'safe_len', 'safe_regex'] else m.group(1), 
        python_formula
    )
    
    # Fix some common patterns
    python_formula = python_formula.replace("row.get('not', '')", "not")
    python_formula = python_formula.replace("row.get('and', '')", "and") 
    python_formula = python_formula.replace("row.get('or', '')", "or")
    
    # Handle AND() function - close the parenthesis properly
    if python_formula.startswith('(') and not python_formula.endswith(')'):
        # Count open vs closed parentheses
        open_count = python_formula.count('(')
        close_count = python_formula.count(')')
        if open_count > close_count:
            python_formula += ')' * (open_count - close_count)
    
    return python_formula

def extract_validation_formulas(sf_conn, object_name: str):
    """Extract validation rules and formulas from Salesforce using same approach as Custom Validation"""
    try:
        with st.spinner(f"🔍 Extracting validation rules for {object_name}..."):
            
            # Use the EXACT SAME approach as Custom Validation
            # Create SF validation client (same as Custom Validation uses)
            sf_client = create_sf_validation_client(sf_conn)
            
            # Fetch validation rules using the working client
            validation_rules_result = sf_client.fetch_validation_rules(object_name)
            
            # Handle result same way as Custom Validation
            validation_rules = []
            if isinstance(validation_rules_result, dict):
                if validation_rules_result.get("error"):
                    st.error(f"❌ {validation_rules_result['message']}")
                else:
                    sf_validation_rules = validation_rules_result.get("records", [])
                    if validation_rules_result.get("message"):
                        st.info(validation_rules_result["message"])
            else:
                sf_validation_rules = []
            
            # Convert to GenAI format if we found rules
            if sf_validation_rules:
                st.info(f"🔄 Converting {len(sf_validation_rules)} rules to GenAI format...")
                
                # Create progress bar for formula extraction
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, rule in enumerate(sf_validation_rules):
                    status_text.text(f"Processing rule {idx + 1}/{len(sf_validation_rules)}: {rule.get('FullName', 'Unknown')}")
                    progress_bar.progress((idx + 1) / len(sf_validation_rules))
                    
                    # Try to extract the actual formula from the API response
                    # The sf_client returns ValidationFormula field even if limited
                    formula = rule.get('ValidationFormula', '')
                    
                    # If we got the API limitation message, we need to inform the user
                    if formula == "FORMULA_NOT_ACCESSIBLE_VIA_API":
                        formula = ""  # We'll need to create a fallback or get formula another way
                    
                    # Convert to GenAI format
                    validation_rules.append({
                        'id': rule.get('Id', ''),
                        'name': rule.get('FullName', ''),
                        'display_name': rule.get('FullName', ''),
                        'formula': formula,  # Now properly extracted from API response
                        'error_message': rule.get('ErrorMessage', ''),
                        'active': rule.get('Active', False),
                        'description': rule.get('Description', ''),
                        'error_field': rule.get('ErrorDisplayField', ''),
                        'extracted_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'source': 'sf_validation_client'  # Using same client as Custom Validation
                    })
                
                # Clear progress indicators  
                progress_bar.empty()
                status_text.empty()
                st.success(f"✅ Successfully extracted {len(validation_rules)} real validation rules!")
            
            # If no real rules found, show appropriate message
            if not validation_rules:
                st.warning(f"  No validation rules found for {object_name} in Salesforce")
                st.info("""
                **Why might this happen?**
                - The selected object doesn't have any validation rules configured
                - The validation rules exist but are inactive
                - You may not have permission to view validation rules
                
                **What you can do:**
                - Select a different object that has validation rules
                - Create validation rules in Salesforce for this object
                - Use Custom Validation instead for manual rule creation
                """)
                
                # Show available objects with validation rules
                if st.button("🔍 Check Other Objects", help="Find objects that have validation rules"):
                    check_objects_with_validation_rules(sf_conn)
                
                return None  # Return None when no real rules found
            
            # Process and save validation rules (only when we have real rules)
            # Save to object-specific file
            validation_dir = os.path.join(os.getcwd(), "validation_formulas")
            os.makedirs(validation_dir, exist_ok=True)
            
            formula_file = os.path.join(validation_dir, f"{object_name}_validation_formulas.json")
            
            with open(formula_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'object_name': object_name,
                    'extracted_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'total_rules': len(validation_rules),
                    'active_rules': len([r for r in validation_rules if r['active']]),
                    'validation_rules': validation_rules,
                    'source': 'real_salesforce_rules'  # Indicate these are real rules
                }, f, indent=2, ensure_ascii=False)
            
            st.success(f"✅ Successfully extracted {len(validation_rules)} real validation rules for {object_name}")
            
            # Display summary
            active_rules = [r for r in validation_rules if r['active']]
            inactive_rules = [r for r in validation_rules if not r['active']]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Rules", len(validation_rules))
            with col2:
                st.metric("Active Rules", len(active_rules))
            with col3:
                st.metric("Inactive Rules", len(inactive_rules))
            
            # Show extracted rules in expandable section
            with st.expander("📋 View Extracted Validation Rules", expanded=True):
                for rule in validation_rules:
                    status_icon = "🟢" if rule['active'] else "🔴"
                    source_icon = "🌩️" if rule['source'] == 'sf_validation_client' else "📝"
                    st.write(f"**{status_icon} {source_icon} {rule['display_name'] or rule['name']}**")
                    
                    col_rule1, col_rule2 = st.columns([2, 1])
                    with col_rule1:
                        if rule['formula']:
                            st.code(rule['formula'], language='text')
                        else:
                            st.caption("Formula not available - will be converted by AI")
                    with col_rule2:
                        if rule['error_message']:
                            st.caption(f"Error: {rule['error_message']}")
                        if rule['description']:
                            st.caption(f"Description: {rule['description']}")
            
            return validation_rules
            
    except Exception as e:
        st.error(f"❌ Error extracting validation rules: {str(e)}")
        return None

def check_objects_with_validation_rules(sf_conn):
    """Check which objects have validation rules"""
    try:
        with st.spinner("🔍 Checking objects for validation rules..."):
            sf_client = create_sf_validation_client(sf_conn)
            objects = get_salesforce_objects(sf_conn, filter_custom=False)
            
            objects_with_rules = []
            
            # Check a subset of common objects to avoid long loading
            common_objects = ['Account', 'Contact', 'Lead', 'Opportunity', 'Case']
            check_objects = [obj for obj in objects if obj in common_objects][:10]
            
            progress_bar = st.progress(0)
            for idx, obj in enumerate(check_objects):
                try:
                    rules_result = sf_client.fetch_validation_rules(obj)
                    if isinstance(rules_result, dict) and rules_result.get("records"):
                        rule_count = len(rules_result["records"])
                        if rule_count > 0:
                            objects_with_rules.append({
                                'object': obj,
                                'rule_count': rule_count
                            })
                except:
                    pass  # Skip objects that error
                
                progress_bar.progress((idx + 1) / len(check_objects))
            
            progress_bar.empty()
            
            if objects_with_rules:
                st.success(f"✅ Found {len(objects_with_rules)} objects with validation rules:")
                
                for obj_info in objects_with_rules:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{obj_info['object']}** - {obj_info['rule_count']} rule(s)")
                    with col2:
                        if st.button(f"Select {obj_info['object']}", key=f"select_{obj_info['object']}"):
                            st.session_state.genai_validation_object = obj_info['object']
                            _mark_val_tab(3)
                            st.rerun()
            else:
                st.warning("⚠️ No validation rules found in the checked objects")
                st.info("Try checking other objects manually or create validation rules in Salesforce")
                
    except Exception as e:
        st.error(f"❌ Error checking objects: {str(e)}")

def get_existing_validation_rules(object_name):
    """Get existing validation rules for object"""
    try:
        # First check session state for recently extracted rules
        if 'genai_validation_rules' in st.session_state:
            session_rules = st.session_state.genai_validation_rules.get(object_name, [])
            if session_rules:
                st.info("🔄 Using recently extracted validation rules from current session")
                return session_rules
        
        # Check for saved rules file
        validation_dir = os.path.join(os.getcwd(), "validation_formulas")
        formula_file = os.path.join(validation_dir, f"{object_name}_validation_formulas.json")
        
        if os.path.exists(formula_file):
            with open(formula_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                rules = data.get('validation_rules', [])
                if rules:
                    st.info("📁 Using validation rules from saved file")
                    return rules
        
        return []
        
    except Exception as e:
        st.error(f"Error loading validation rules: {e}")
        return []

def display_validation_rules_summary(rules):
    """Display summary of validation rules"""
    if not rules:
        st.info("No validation rules to display")
        return
    
    for i, rule in enumerate(rules):
        status_icon = "🟢" if rule.get('active', True) else "🔴"
        rule_name = rule.get('display_name') or rule.get('name', f'Rule {i+1}')
        
        with st.container():
            st.write(f"**{status_icon} {rule_name}**")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Show formula
                formula = rule.get('formula', 'No formula available')
                st.code(formula, language='text')
            
            with col2:
                # Show error message and other details
                error_msg = rule.get('error_message', '')
                if error_msg:
                    st.caption(f"**Error:** {error_msg}")
                
                description = rule.get('description', '')
                if description:
                    st.caption(f"**Description:** {description}")
                
                # Show extracted date if available
                extracted_date = rule.get('extracted_date', '')
                if extracted_date:
                    st.caption(f"**Extracted:** {extracted_date}")
            
            st.divider()

def save_manual_formula(object_name: str, rule_data: dict):
    """Save manual validation formula"""
    try:
        validation_dir = os.path.join(os.getcwd(), "validation_formulas")
        os.makedirs(validation_dir, exist_ok=True)
        
        formula_file = os.path.join(validation_dir, f"{object_name}_validation_formulas.json")
        
        # Load existing rules or create new structure
        existing_data = {}
        if os.path.exists(formula_file):
            with open(formula_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        
        # Prepare the new rule
        new_rule = {
            'id': f'manual_{len(existing_data.get("validation_rules", []))}',
            'name': rule_data.get('name', ''),
            'display_name': rule_data.get('name', ''),
            'formula': rule_data.get('formula', ''),
            'error_message': rule_data.get('error_message', ''),
            'active': True,
            'description': 'Manually entered rule',
            'extracted_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'source': 'manual'
        }
        
        # Add to existing rules
        if 'validation_rules' not in existing_data:
            existing_data = {
                'object_name': object_name,
                'extracted_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_rules': 1,
                'active_rules': 1,
                'validation_rules': [new_rule]
            }
        else:
            existing_data['validation_rules'].append(new_rule)
            existing_data['total_rules'] = len(existing_data['validation_rules'])
            existing_data['active_rules'] = len([r for r in existing_data['validation_rules'] if r.get('active', True)])
        
        # Save updated data
        with open(formula_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        # Update session state
        if 'extracted_validation_rules' not in st.session_state:
            st.session_state.extracted_validation_rules = {}
        st.session_state.extracted_validation_rules[object_name] = existing_data['validation_rules']
        
        st.success(f"✅ Manual rule '{rule_data['name']}' saved successfully")
        
    except Exception as e:
        st.error(f"❌ Error saving manual formula: {e}")

def get_genai_validation_results(object_name):
    """Get GenAI validation results if available"""
    try:
        results_dir = os.path.join(os.getcwd(), "genai_validation_results")
        results_file = os.path.join(results_dir, f"{object_name}_validation_results.json")
        
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
    except Exception as e:
        st.error(f"Error loading validation results: {e}")
        return None

def display_genai_validation_results(results):
    """Display GenAI validation results"""
    if not results:
        st.info("No validation results to display")
        return
    
    # Summary metrics
    st.subheader("📊 Validation Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", results.get('total_records', 0))
    
    with col2:
        st.metric("Valid Records", results.get('valid_records', 0))
    
    with col3:
        st.metric("Invalid Records", results.get('invalid_records', 0))
    
    with col4:
        success_rate = 0
        if results.get('total_records', 0) > 0:
            success_rate = (results.get('valid_records', 0) / results.get('total_records', 1)) * 100
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    # Validation details
    if 'validation_errors' in results and results['validation_errors']:
        st.subheader("❌ Validation Errors")
        
        error_df = pd.DataFrame(results['validation_errors'])
        st.dataframe(error_df, use_container_width=True)
    
    # Download links for result files
    if 'result_files' in results:
        st.subheader("📁 Result Files")
        
        for file_type, file_path in results['result_files'].items():
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    st.download_button(
                        label=f"⬇️ Download {file_type} File",
                        data=f.read(),
                        file_name=os.path.basename(file_path),
                        mime='text/csv' if file_path.endswith('.csv') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', on_click='ignore'
                    )

def check_validation_bundle_exists(object_name: str) -> bool:
    """Check if validation bundle exists in the new GenAI structure"""
    try:
        # Check if we have bundle info in session state
        if hasattr(st.session_state, 'genai_bundle_generated') and st.session_state.genai_bundle_generated:
            return True
            
        # Check for org info to build correct path
        if hasattr(st.session_state, 'selected_org') and st.session_state.selected_org:
            selected_org = st.session_state.selected_org
        else:
            # Fallback: the sidebar org, else the first configured Salesforce org
            try:
                selected_org = st.session_state.get('current_org') or list(connection_manager.salesforce_orgs())[0]
            except Exception:
                return False
        
        # Check for files in the new GenAI structure
        bundle_dir = os.path.join("Validation", selected_org, object_name, "GenAIValidation", "validation_bundle")
        bundle_file = os.path.join(bundle_dir, "bundle.py")
        validator_file = os.path.join(bundle_dir, "validator.py")
        
        return os.path.exists(bundle_file) and os.path.exists(validator_file)
    except Exception:
        return False

def run_genai_validation(object_name: str, data: pd.DataFrame, fail_fast: bool = False, detailed_logging: bool = True, save_results: bool = True):
    """Run GenAI validation on the provided data"""
    try:
        # Initialize variables to prevent UnboundLocalError
        error_summary = []
        validation_results = []
        valid_df = pd.DataFrame()
        invalid_df = pd.DataFrame()
        
        with st.spinner("🚀 Running AI validation..."):
            # Check if we have bundle info in session state first
            if (hasattr(st.session_state, 'genai_bundle_generated') and 
                st.session_state.genai_bundle_generated and
                hasattr(st.session_state, 'genai_bundle_path')):
                
                bundle_file = st.session_state.genai_bundle_path
                validator_file = getattr(st.session_state, 'genai_validator_path', None)
                
            else:
                # Fallback: try to find bundle using the correct path structure
                # Load org info from session state or linkedservices.json
                if hasattr(st.session_state, 'current_org') and st.session_state.current_org:
                    selected_org = st.session_state.current_org
                else:
                    try:
                        selected_org = list(connection_manager.salesforce_orgs())[0]
                    except Exception:
                        st.error("❌ Could not determine organization")
                        return
                
                # Build correct path structure
                bundle_dir = os.path.join("Validation", selected_org, object_name, "GenAIValidation", "validation_bundle")
                bundle_file = os.path.join(bundle_dir, "bundle.py")
                validator_file = os.path.join(bundle_dir, "validator.py")
            
            if not os.path.exists(validator_file):
                st.error(f"❌ Validation script not found for {object_name}")
                st.info("Please generate the AI bundle first in Step 2.")
                
                # Show debug information
                st.warning("**Debug Information:**")
                st.write(f"Looking for validator at: `{validator_file}`")
                if hasattr(st.session_state, 'genai_bundle_generated'):
                    st.write(f"Session state bundle_generated: {st.session_state.genai_bundle_generated}")
                if hasattr(st.session_state, 'genai_validator_path'):
                    st.write(f"Session state validator_path: {st.session_state.genai_validator_path}")
                return
            
            # Add debugging toggle
            debug_mode = st.checkbox("🔍 Enable SF Validation Rules Debug Mode", value=False)
            
            if debug_mode:
                st.subheader("🔍 Debug: AI Validation Information")
                st.write(f"Validator file: `{validator_file}`")
                st.write(f"Bundle file: `{bundle_file}`")
                
                # Show validator file content preview
                with open(validator_file, 'r', encoding='utf-8') as f:
                    validator_content = f.read()
                
                st.write("**Validator Script Preview:**")
                st.code(validator_content[:500] + "..." if len(validator_content) > 500 else validator_content, language='python')
                
                # Show bundle file content preview
                with open(bundle_file, 'r', encoding='utf-8') as f:
                    bundle_content = f.read()
                
                st.write("**Generated validation functions found in bundle:**")
                import re
                function_matches = re.findall(r'def (validate_\w+)', bundle_content)
                for func_name in function_matches:
                    st.write(f"• {func_name}")
                
                if not function_matches:
                    st.error("❌ No validation functions found in bundle!")
                    return
            
            # Use the validator script for validation (not the bundle directly)
            # The validator script imports from bundle and provides complete workflow
            import importlib.util
            import sys
            
            # Import the bundle module first (contains validation functions)
            bundle_spec = importlib.util.spec_from_file_location("bundle", bundle_file)
            bundle_module = importlib.util.module_from_spec(bundle_spec)
            
            try:
                # Load the bundle module and add it to sys.modules so validator can import it
                bundle_spec.loader.exec_module(bundle_module)
                sys.modules['bundle'] = bundle_module
                
                # Check if the bundle has the new validate_dataframe function
                if hasattr(bundle_module, 'validate_dataframe'):
                    validate_func = bundle_module.validate_dataframe
                    st.success("✅ Successfully loaded AI validation modules (new format)!")
                else:
                    # Handle old format bundles - create validate_dataframe function dynamically
                    st.warning("⚠️ Using legacy bundle format - creating validate_dataframe function...")
                    
                    # Get all validation functions from the bundle
                    validation_functions = [name for name in dir(bundle_module) 
                                          if name.startswith('validate_') and callable(getattr(bundle_module, name))]
                    
                    if not validation_functions:
                        st.error("❌ No validation functions found in bundle!")
                        return
                    
                    # Create a dynamic validate_dataframe function
                    def validate_dataframe(df):
                        """Dynamic validation function for legacy bundles"""
                        valid_idx = []
                        invalid_idx = []
                        validation_results = []
                        
                        for idx, row in df.iterrows():
                            row_df = pd.DataFrame([row])
                            errors = []
                            rule_results = {}
                            is_valid = True
                            
                            for func_name in validation_functions:
                                try:
                                    func = getattr(bundle_module, func_name)
                                    result = bool(func(row_df).iloc[0])
                                    rule_results[func_name] = result
                                    if not result:
                                        errors.append(func_name)
                                        is_valid = False
                                except Exception as e:
                                    rule_results[func_name] = False
                                    errors.append(f"{func_name} (error: {e})")
                                    is_valid = False
                            
                            validation_results.append({
                                'index': idx,
                                'is_valid': is_valid,
                                'errors': errors,
                                'rule_results': rule_results
                            })
                            
                            if is_valid:
                                valid_idx.append(idx)
                            else:
                                invalid_idx.append(idx)
                        
                        valid_df = df.loc[valid_idx].copy() if valid_idx else pd.DataFrame()
                        invalid_df = df.loc[invalid_idx].copy() if invalid_idx else pd.DataFrame()
                        return valid_df, invalid_df, validation_results
                    
                    validate_func = validate_dataframe
                    st.info(f"Created dynamic validation function using {len(validation_functions)} rules")
                
                # Now try to import the validator module (it can now import 'bundle')
                validator_spec = importlib.util.spec_from_file_location("validation_module", validator_file)
                validator_module = importlib.util.module_from_spec(validator_spec)
                validator_spec.loader.exec_module(validator_module)
                    
            except SyntaxError as syntax_error:
                st.error(f"❌ Validation failed")
                st.error(f"**Syntax Error in Generated Code**: {syntax_error}")
                
                # Extract line information if available
                if hasattr(syntax_error, 'lineno') and syntax_error.lineno:
                    st.error(f"**Error at line {syntax_error.lineno}**: {syntax_error.text if syntax_error.text else 'Unknown'}")
                
                # Provide specific guidance for syntax errors
                st.markdown("""
                ### 🔧 **IMMEDIATE ACTION REQUIRED**
                
                **The validation bundle contains syntax errors and must be regenerated.**
                
                ### **Step-by-Step Solution:**
                
                1. **📍 Go to Step 2: Generate Python Validation Bundle**
                2. **🔄 Click "Generate Python Validation Bundle" again**
                3. **✅ The updated conversion logic will fix these issues:**
                   - ✅ TRIM function support added
                   - ✅ Fixed ISPICKVAL with quoted strings  
                   - ✅ Corrected operator conversion (= → ==)
                   - ✅ Function vs field reference detection
                   - ✅ Syntax validation during generation
                
                ### **Why regeneration is needed:**
                The current bundle was created with old conversion logic. The fixes are only applied when you regenerate the bundle.
                
                **⚠️ Important**: You MUST regenerate the bundle for the fixes to take effect!
                """)
                
                # Add a prominent call-to-action
                st.info("👆 **Please go back to Step 2 and regenerate the validation bundle before proceeding.**")
                
                if debug_mode:
                    st.exception(syntax_error)
                return
                
            except Exception as import_error:
                st.error(f"❌ Error importing validation modules: {import_error}")
                if debug_mode:
                    st.exception(import_error)
                return
            
            # Test validation with a sample record first
            if debug_mode and len(data) > 0:
                st.subheader("🧪 Debug: Sample Record Validation")
                sample_row = data.iloc[0]
                st.write("**Sample record:**")
                st.write(sample_row.to_dict())
                
                try:
                    # Check if validate_record function exists in bundle
                    if hasattr(bundle_module, 'validate_record'):
                        sample_result = bundle_module.validate_record(sample_row)
                        st.write("**Sample validation result:**")
                        st.json(sample_result)
                    else:
                        st.info("validate_record function not found, using validate_dataframe for sample")
                        sample_df = pd.DataFrame([sample_row])
                        valid_sample, invalid_sample, sample_results = validate_func(sample_df)
                        st.write("**Sample validation result:**")
                        st.write(f"Valid: {len(valid_sample) > 0}, Results: {sample_results}")
                except Exception as sample_error:
                    st.error(f"❌ Sample validation failed: {sample_error}")
                    if debug_mode:
                        st.exception(sample_error)
            
            # Run validation on full dataset using the validate_dataframe function
            st.info(f"🔄 Validating {len(data)} records using AI validation script from Step 2...")
            valid_df, invalid_df, validation_results = validate_func(data)
            
            if debug_mode:
                st.subheader("🔍 Debug: Validation Results Summary")
                st.write(f"Valid records: {len(valid_df)}")
                st.write(f"Invalid records: {len(invalid_df)}")
                st.write(f"Total validation results: {len(validation_results)}")
                
                # Show first few validation results
                if validation_results:
                    st.write("**Sample validation results:**")
                    for i, result in enumerate(validation_results[:3]):
                        st.write(f"Record {result['index']}: Valid={result['is_valid']}, Errors={result['errors']}")
            
            # Display results
            st.success("✅ Validation completed using AI validator script from Step 2!")
            
            # Show which script was used
            with st.expander("📄 Validation Script Details", expanded=False):
                st.write(f"**Validator Script Used:** `{validator_file}`")
                st.write(f"**Bundle Functions Used:** `{bundle_file}`")
                st.write("The validation was performed using the AI-generated validator script from Step 2, which imports and uses the validation functions from the bundle.")
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Records", len(data))
            
            with col2:
                st.metric("Valid Records", len(valid_df), delta=f"{(len(valid_df)/len(data)*100):.1f}%")
            
            with col3:
                st.metric("Invalid Records", len(invalid_df), delta=f"{(len(invalid_df)/len(data)*100):.1f}%")
            
            with col4:
                success_rate = (len(valid_df) / len(data)) * 100 if len(data) > 0 else 0
                st.metric("Success Rate", f"{success_rate:.1f}%")
            
            # Show validation details and create error summary
            if detailed_logging and len(invalid_df) > 0:
                st.subheader("❌ Validation Errors")
                
                # Create error summary for detailed logging
                for result in validation_results:
                    if not result['is_valid']:
                        for error in result['errors']:
                            error_summary.append({
                                'Record Index': result['index'],
                                'Error': error,
                                'Rule Results': str(result['rule_results'])
                            })
                
                if error_summary:
                    error_df = pd.DataFrame(error_summary)
                    st.dataframe(error_df, use_container_width=True, height=300)
            
            # Save results if requested
            result_files = {}
            if save_results:
                results_dir = os.path.join(os.getcwd(), "genai_validation_results")
                os.makedirs(results_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Save valid records
                if len(valid_df) > 0:
                    valid_file = os.path.join(results_dir, f"{object_name}_valid_records_{timestamp}.csv")
                    valid_df.to_csv(valid_file, index=False)
                    result_files['valid'] = valid_file
                
                # Save invalid records
                if len(invalid_df) > 0:
                    invalid_file = os.path.join(results_dir, f"{object_name}_invalid_records_{timestamp}.csv")
                    invalid_df.to_csv(invalid_file, index=False)
                    result_files['invalid'] = invalid_file
                
                # Save detailed results
                results_summary = {
                    'object_name': object_name,
                    'validation_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'total_records': len(data),
                    'valid_records': len(valid_df),
                    'invalid_records': len(invalid_df),
                    'success_rate': success_rate,
                    'validation_errors': error_summary if detailed_logging else [],
                    'result_files': result_files
                }
                
                summary_file = os.path.join(results_dir, f"{object_name}_validation_results.json")
                with open(summary_file, 'w', encoding='utf-8') as f:
                    json.dump(results_summary, f, indent=2, ensure_ascii=False)
                
                st.success(f"📁 Results saved to {results_dir}")
            
            # Provide download buttons
            st.subheader("⬇️ Download Results")
            
            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                if len(valid_df) > 0:
                    csv_valid = valid_df.to_csv(index=False)
                    st.download_button(
                        label=f"⬇️ Valid Records ({len(valid_df)})",
                        data=csv_valid,
                        file_name=f"{object_name}_valid_records.csv",
                        mime="text/csv",
                        type="primary",
                        key="genai_valid_download", on_click='ignore'
                    )
            
            with col_dl2:
                if len(invalid_df) > 0:
                    csv_invalid = invalid_df.to_csv(index=False)
                    st.download_button(
                        label=f"⬇️ Invalid Records ({len(invalid_df)})",
                        data=csv_invalid,
                        file_name=f"{object_name}_invalid_records.csv",
                        mime="text/csv",
                        type="secondary",
                        key="genai_invalid_download", on_click='ignore'
                    )
            
            # Show data previews
            if len(valid_df) > 0:
                with st.expander(f"✅ Valid Records Preview ({len(valid_df)} records)", expanded=False):
                    st.dataframe(valid_df.head(10), use_container_width=True)
            
            if len(invalid_df) > 0:
                with st.expander(f"❌ Invalid Records Preview ({len(invalid_df)} records)", expanded=False):
                    st.dataframe(invalid_df.head(10), use_container_width=True)
            
    except Exception as e:
        st.error(f"❌ Error running GenAI validation: {e}")
        st.exception(e)
    finally:
        # Clean up sys.modules to avoid conflicts
        if 'bundle' in sys.modules:
            del sys.modules['bundle']

def get_validation_files(object_name: str) -> List[str]:
    """Get validation files for object"""
    try:
        # Look in DataFiles directory structure
        data_files_dir = os.path.join(os.getcwd(), "DataFiles")
        validation_files = []
        
        # Search for CSV/Excel files in object-specific directories
        for root, dirs, files in os.walk(data_files_dir):
            if object_name.lower() in root.lower():
                for file in files:
                    if file.endswith(('.csv', '.xlsx', '.xls', '.psv')) and not file.startswith('~$'):
                        validation_files.append(os.path.join(root, file))
        
        # Also check for uploaded files in session state
        if 'uploaded_validation_files' in st.session_state:
            session_files = st.session_state.uploaded_validation_files.get(object_name, [])
            validation_files.extend(session_files)
        
        return validation_files
    except Exception as e:
        st.error(f"Error finding validation files: {e}")
        return []

def load_existing_validation_file(file_path: str) -> Optional[pd.DataFrame]:
    """Load existing validation file"""
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path, dtype=str)
        elif file_path.endswith(('.xlsx', '.xls')):
            return pd.read_excel(file_path, dtype=str)
        else:
            st.error(f"Unsupported file format: {file_path}")
            return None
    except Exception as e:
        st.error(f"Error loading file {file_path}: {e}")
        return None



def get_validation_results() -> List[Dict]:
    """Get validation results from Validation folder structure
    
    Scans the Validation folder and loads all saved validation results.
    Returns a list of validation result dictionaries with metadata.
    """
    results = []
    validation_root = os.path.join(project_root, 'Validation')
    
    if not os.path.exists(validation_root):
        return results
    
    try:
        def _normalize_validation_type(value: str) -> str:
            raw = str(value or '').strip().lower()
            collapsed = re.sub(r'[^a-z0-9]+', '', raw)
            mapping = {
                'schemavalidation': 'schema_validation',
                'schema_validation': 'schema_validation',
                'customvalidation': 'custom_validation',
                'custom_validation': 'custom_validation',
                'enhancedvalidation': 'enhanced_validation',
                'enhanced_validation': 'enhanced_validation',
                'genaivalidation': 'genai_validation',
                'genai_validation': 'genai_validation',
                'sfvalidationrules': 'sf_validation_rules',
                'sf_validation_rules': 'sf_validation_rules',
                'validationreports': 'validation_reports',
                'validationsummary': 'validation_summary'
            }
            return mapping.get(collapsed, raw.replace(' ', '_'))

        def _infer_validation_type_from_filename(file_name: str) -> str:
            lower_name = str(file_name or '').lower()
            if 'schema_validation' in lower_name or 'schemavalidation' in lower_name:
                return 'schema_validation'
            if 'enhanced_validation' in lower_name or 'enhancedvalidation' in lower_name:
                return 'enhanced_validation'
            if 'custom_validation' in lower_name or 'customvalidation' in lower_name:
                return 'custom_validation'
            if 'sf_validation_rules' in lower_name or 'sfvalidationrules' in lower_name or 'validation_rules' in lower_name:
                return 'sf_validation_rules'
            if 'genai_validation' in lower_name or 'genaivalidation' in lower_name:
                return 'genai_validation'
            return ''
        
        # Scan through Validation folder structure.
        # Current writer format is mostly: Validation/[validation_type]/[org_name]/[object_name]/[date]/[files]
        # Keep backward compatibility with older layouts.
        for root, dirs, files in os.walk(validation_root):
            for file in files:
                lower_file = file.lower()
                if (
                    (
                        lower_file.endswith('.json') and
                        ('_results' in lower_file or '_complete_results' in lower_file)
                    ) or
                    (
                        lower_file.endswith('.csv') and
                        ('_results' in lower_file or '_complete_results' in lower_file)
                    )
                ):
                    file_path = os.path.join(root, file)
                    try:
                        # Extract metadata from file path
                        path_parts = root.replace(validation_root, '').strip(os.sep).split(os.sep)
                        
                        result_dict = {
                            'file_path': file_path,
                            'file_name': file,
                            'file_type': 'json' if file.endswith('.json') else 'csv',
                            'timestamp': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                        }
                        
                        # Parse path to extract org, object, type
                        known_types = {
                            'schema_validation', 'custom_validation', 'genai_validation',
                            'enhanced_validation', 'sf_validation_rules', 'validation_reports',
                            'validation_summary'
                        }

                        inferred_validation_type = _infer_validation_type_from_filename(file)
                        if inferred_validation_type:
                            result_dict['validation_type'] = inferred_validation_type

                        if len(path_parts) >= 4 and path_parts[0].lower() in known_types:
                            # Validation/[type]/[org]/[object]/[date]
                            if 'validation_type' not in result_dict:
                                result_dict['validation_type'] = _normalize_validation_type(path_parts[0])
                            result_dict['org'] = path_parts[1]
                            result_dict['object'] = path_parts[2]
                        elif len(path_parts) >= 3:
                            # Backward compatibility: Validation/[org]/[object]/[type]
                            result_dict['org'] = path_parts[0]
                            result_dict['object'] = path_parts[1]
                            if 'validation_type' not in result_dict:
                                result_dict['validation_type'] = _normalize_validation_type(path_parts[2])
                        elif len(path_parts) >= 1:
                            if 'validation_type' not in result_dict:
                                result_dict['validation_type'] = _normalize_validation_type(path_parts[0])
                        
                        # Load actual results
                        if file.endswith('.json'):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                result_dict['total_records'] = data.get('total_records', 0)
                                result_dict['passed_records'] = data.get('passed_records', 0)
                                result_dict['failed_records'] = data.get('failed_records', 0)
                                result_dict['total_errors'] = len(data.get('validation_errors', []))
                        elif file.endswith('.csv'):
                            # For CSV results, try to infer from content
                            df = pd.read_csv(file_path)
                            result_dict['total_records'] = len(df)
                            # Try to find relevant columns
                            if 'Validation_Status' in df.columns:
                                status_col = df['Validation_Status'].astype(str).str.upper().str.strip()
                                result_dict['passed_records'] = len(df[status_col.isin(['PASSED', 'VALID'])])
                                result_dict['failed_records'] = len(df[status_col.isin(['FAILED', 'INVALID'])])
                                result_dict['total_errors'] = result_dict['failed_records']
                            else:
                                result_dict['passed_records'] = 0
                                result_dict['failed_records'] = 0
                                result_dict['total_errors'] = 0
                        
                        results.append(result_dict)
                    except Exception as e:
                        # Skip files that can't be parsed
                        continue
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
    except Exception as e:
        st.warning(f"⚠️ Error reading validation results: {str(e)}")
    
    return results

def show_validation_results_summary(results: List[Dict]):
    """Show validation results summary in table format"""
    if not results:
        st.info("No validation results to display")
        return
    
    # Create summary dataframe
    summary_data = []
    for result in results:
        summary_data.append({
            'Date': result.get('timestamp', '')[:10],
            'Time': result.get('timestamp', '')[11:19] if len(result.get('timestamp', '')) > 11 else '',
            'Organization': result.get('org', 'Unknown'),
            'Object': result.get('object', 'Unknown'),
            'Validation Type': result.get('validation_type', 'Unknown'),
            'Total Records': result.get('total_records', 0),
            'Passed': result.get('passed_records', 0),
            'Failed': result.get('failed_records', 0),
            'Success Rate': f"{(result.get('passed_records', 0) / result.get('total_records', 1) * 100):.1f}%" if result.get('total_records', 0) > 0 else '0%'
        })
    
    summary_df = pd.DataFrame(summary_data)
    
    # Display with color coding
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

def show_validation_result_detail(result: Dict):
    """Show detailed validation result with expandable details"""
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown(f"**{result.get('object', 'Unknown')}** - {result.get('validation_type', 'Unknown')}")
    
    with col2:
        status = '✅ All Passed' if result.get('failed_records', 0) == 0 else f"❌ {result.get('failed_records', 0)} Failed"
        st.write(status)
    
    with col3:
        st.caption(result.get('timestamp', 'Unknown')[:19])
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total", result.get('total_records', 0))
    with col2:
        st.metric("Passed", result.get('passed_records', 0))
    with col3:
        st.metric("Failed", result.get('failed_records', 0))
    with col4:
        success_rate = (result.get('passed_records', 0) / result.get('total_records', 1) * 100) if result.get('total_records', 0) > 0 else 0
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    # Download option
    if os.path.exists(result.get('file_path', '')):
        with open(result['file_path'], 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        st.download_button(
            label="📥 Download Results",
            data=file_content,
            file_name=result.get('file_name', 'results.json'),
            mime='application/json' if result.get('file_type') == 'json' else 'text/csv',
            key=f"download_{result.get('file_path', '')}", on_click='ignore'
        )
    
    st.divider()

def get_comprehensive_validation_summary() -> Optional[Dict]:
    """Get comprehensive validation summary aggregating all validation results
    
    Returns dictionary with:
    - total_validations
    - total_records_processed
    - overall_pass_rate
    - failed_records_total
    - validation_types
    - objects_validated
    - quality_score
    - top_issues
    """
    results = get_validation_results()
    
    if not results:
        return None
    
    # Aggregate metrics
    summary = {
        'total_validations': len(results),
        'total_records_processed': sum(r.get('total_records', 0) for r in results),
        'total_passed_records': sum(r.get('passed_records', 0) for r in results),
        'total_failed_records': sum(r.get('failed_records', 0) for r in results),
        'total_errors': sum(r.get('total_errors', 0) for r in results),
        'validation_types': {},
        'objects_validated': set(),
        'results': results
    }
    
    # Calculate overall pass rate
    if summary['total_records_processed'] > 0:
        summary['overall_pass_rate'] = (summary['total_passed_records'] / summary['total_records_processed']) * 100
    else:
        summary['overall_pass_rate'] = 0
    
    # Aggregate by validation type
    for result in results:
        val_type = result.get('validation_type', 'Unknown')
        if val_type not in summary['validation_types']:
            summary['validation_types'][val_type] = {
                'count': 0,
                'passed': 0,
                'failed': 0,
                'total_records': 0
            }
        summary['validation_types'][val_type]['count'] += 1
        summary['validation_types'][val_type]['passed'] += result.get('passed_records', 0)
        summary['validation_types'][val_type]['failed'] += result.get('failed_records', 0)
        summary['validation_types'][val_type]['total_records'] += result.get('total_records', 0)
        
        # Collect unique objects
        summary['objects_validated'].add(result.get('object', 'Unknown'))
    
    # Convert set to list for JSON serialization
    summary['objects_validated'] = list(summary['objects_validated'])
    
    # Calculate quality score (0-100)
    # Based on: pass rate (60%), error count (20%), consistency (20%)
    if summary['total_records_processed'] > 0:
        pass_rate_score = summary['overall_pass_rate']
        error_score = max(0, 100 - (summary['total_errors'] / summary['total_records_processed'] * 100))
        consistency_score = min(100, len(summary['objects_validated']) * 10)  # Encourage validating multiple objects
        summary['quality_score'] = (pass_rate_score * 0.6 + error_score * 0.2 + consistency_score * 0.2)
    else:
        summary['quality_score'] = 0
    
    return summary

def show_quality_metrics(summary: Dict):
    """Show quality metrics dashboard"""
    if not summary:
        st.info("No validation data available")
        return
    
    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📊 Total Validations", summary['total_validations'])
    
    with col2:
        st.metric("📈 Total Records", summary['total_records_processed'])
    
    with col3:
        pass_rate = summary['overall_pass_rate']
        if pass_rate >= 95:
            color = '🟢'
        elif pass_rate >= 80:
            color = '🟡'
        else:
            color = '🔴'
        st.metric(f"{color} Pass Rate", f"{pass_rate:.1f}%")
    
    with col4:
        st.metric("❌ Total Failed", summary['total_failed_records'])
    
    with col5:
        quality = summary.get('quality_score', 0)
        st.metric("⭐ Quality Score", f"{quality:.1f}/100")
    
    st.divider()
    
    # Quality assessment
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Validation Summary by Type")
        
        val_types_data = []
        for val_type, stats in summary['validation_types'].items():
            if stats['total_records'] > 0:
                success_rate = (stats['passed'] / stats['total_records']) * 100
            else:
                success_rate = 0
            
            val_types_data.append({
                'Validation Type': val_type,
                'Runs': stats['count'],
                'Passed': stats['passed'],
                'Failed': stats['failed'],
                'Success Rate': f"{success_rate:.1f}%"
            })
        
        if val_types_data:
            val_types_df = pd.DataFrame(val_types_data)
            st.dataframe(val_types_df, use_container_width=True, hide_index=True)
    
    with col2:
        st.subheader("🎯 Objects Validated")
        
        if summary['objects_validated']:
            st.write(f"**Total Unique Objects:** {len(summary['objects_validated'])}")
            for obj in sorted(summary['objects_validated']):
                st.write(f"• {obj}")
        else:
            st.info("No objects validated yet")

def show_quality_trends(summary: Dict):
    """Show quality trends over time"""
    st.subheader("📈 Validation Trends")
    
    results = summary.get('results', [])
    if not results or len(results) < 2:
        st.info("Not enough data to show trends. Run more validations to see trends.")
        return
    
    # Create trend data (group by date)
    trend_data = {}
    for result in results:
        date = result.get('timestamp', '')[:10]
        if date not in trend_data:
            trend_data[date] = {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'validations': 0
            }
        trend_data[date]['total'] += result.get('total_records', 0)
        trend_data[date]['passed'] += result.get('passed_records', 0)
        trend_data[date]['failed'] += result.get('failed_records', 0)
        trend_data[date]['validations'] += 1
    
    # Sort by date
    sorted_dates = sorted(trend_data.keys())
    
    # Create dataframe for visualization
    trend_df = pd.DataFrame([
        {
            'Date': date,
            'Pass Rate %': (trend_data[date]['passed'] / trend_data[date]['total'] * 100) if trend_data[date]['total'] > 0 else 0,
            'Validations': trend_data[date]['validations'],
            'Records': trend_data[date]['total']
        }
        for date in sorted_dates
    ])
    
    # Display chart
    if not trend_df.empty:
        st.line_chart(trend_df.set_index('Date')['Pass Rate %'])
        st.dataframe(trend_df, use_container_width=True, hide_index=True)
    else:
        st.info("No trend data available")

def show_issue_breakdown(summary: Dict):
    """Show breakdown of issues and problem areas"""
    st.subheader("⚠️ Issue Breakdown")
    
    results = summary.get('results', [])
    if not results:
        st.info("No issue data available")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Validation Type Performance**")
        
        # Group failures by validation type
        val_type_failures = {}
        for result in results:
            val_type = result.get('validation_type', 'Unknown')
            failed = result.get('failed_records', 0)
            if val_type not in val_type_failures:
                val_type_failures[val_type] = 0
            val_type_failures[val_type] += failed
        
        if val_type_failures:
            failure_df = pd.DataFrame([
                {
                    'Validation Type': val_type,
                    'Failed Records': count
                }
                for val_type, count in sorted(val_type_failures.items(), key=lambda x: x[1], reverse=True)
            ])
            st.bar_chart(failure_df.set_index('Validation Type'))
            st.dataframe(failure_df, use_container_width=True, hide_index=True)
    
    with col2:
        st.write("**Object-wise Failures**")
        
        # Group failures by object
        object_failures = {}
        for result in results:
            obj = result.get('object', 'Unknown')
            failed = result.get('failed_records', 0)
            if obj not in object_failures:
                object_failures[obj] = 0
            object_failures[obj] += failed
        
        if object_failures:
            obj_failure_df = pd.DataFrame([
                {
                    'Object': obj,
                    'Failed Records': count
                }
                for obj, count in sorted(object_failures.items(), key=lambda x: x[1], reverse=True)
            ])
            st.bar_chart(obj_failure_df.set_index('Object'))
            st.dataframe(obj_failure_df, use_container_width=True, hide_index=True)

def show_quality_recommendations(summary: Dict):
    """Show quality recommendations based on validation data"""
    st.subheader("💡 Data Quality Recommendations")
    
    if not summary:
        return
    
    recommendations = []
    
    pass_rate = summary.get('overall_pass_rate', 0)
    
    # Recommendation 1: Overall pass rate
    if pass_rate < 70:
        recommendations.append({
            'severity': '🔴 Critical',
            'title': 'Low Overall Pass Rate',
            'suggestion': f'Your data has a {pass_rate:.1f}% pass rate. Consider implementing stricter data validation rules before importing data to Salesforce.',
            'action': 'Review failed records and fix data quality issues'
        })
    elif pass_rate < 85:
        recommendations.append({
            'severity': '🟡 Warning',
            'title': 'Pass Rate Below Target',
            'suggestion': f'Your pass rate is {pass_rate:.1f}%. Aim for 95%+ before data load.',
            'action': 'Identify common failure patterns and address them'
        })
    else:
        recommendations.append({
            'severity': '🟢 Good',
            'title': 'Excellent Data Quality',
            'suggestion': f'Your data quality is excellent with a {pass_rate:.1f}% pass rate.',
            'action': 'Continue monitoring data quality'
        })
    
    # Recommendation 2: Validation coverage
    validations = summary.get('total_validations', 0)
    if validations < 3:
        recommendations.append({
            'severity': '🟡 Info',
            'title': 'Limited Validation Coverage',
            'suggestion': f'You have only run {validations} validation(s). Run more validation types to improve data quality assurance.',
            'action': 'Run Schema, GenAI, and Custom validations'
        })
    
    # Recommendation 3: Objects validated
    objects = len(summary.get('objects_validated', []))
    if objects < 2:
        recommendations.append({
            'severity': '🟡 Info',
            'title': 'Limited Object Coverage',
            'suggestion': f'You have validated only {objects} object(s). Consider validating more objects.',
            'action': 'Expand validation to other critical objects'
        })
    
    # Recommendation 4: Error trends
    results = summary.get('results', [])
    if len(results) > 2:
        # Check if errors are increasing
        recent_errors = sum(r.get('failed_records', 0) for r in results[:2])
        older_errors = sum(r.get('failed_records', 0) for r in results[2:4]) if len(results) > 3 else recent_errors
        
        if older_errors > 0 and recent_errors > older_errors * 1.2:
            recommendations.append({
                'severity': '🔴 Alert',
                'title': 'Increasing Error Trend',
                'suggestion': 'Error rates are increasing. Investigate root causes immediately.',
                'action': 'Review recent changes to data or validation rules'
            })
    
    # Display recommendations
    if recommendations:
        for rec in recommendations:
            with st.expander(f"{rec['severity']} {rec['title']}", expanded=len(recommendations) == 1):
                st.write(f"**Suggestion:** {rec['suggestion']}")
                st.write(f"**Action:** {rec['action']}")
    else:
        st.info("No specific recommendations at this time")

def save_validation_results(results: Dict, object_name: str, validation_type: str):
    """Save validation results to file and return file path"""
    _bump_validation_results_version()
    try:
        # Create validation directory
        validation_dir = os.path.join(
            project_root, 'Validation', 
            st.session_state.current_org, 
            object_name, 
            'SchemaValidation'
        )
        
        os.makedirs(validation_dir, exist_ok=True)
        
        # Save results as JSON
        results_file = os.path.join(validation_dir, f'{validation_type}_results.json')
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        show_processing_status("save_validation", f"Validation results saved to {results_file}", "success")
        
        return results_file
        
    except Exception as e:
        st.error(f"❌ Error saving validation results: {str(e)}")
        return None

def extract_validation_formulas_for_genai(sf_conn, org_name: str, object_name: str):
    """
    NEW: Extract validation rule formulas specifically for GenAI conversion
    
    Focuses on:
    - ValidationRuleName
    - ErrorConditionFormula (Apex code)
    - ErrorMessage
    - Active status
    
    Returns structured data for AI conversion to Python functions
    """
    try:
        # Import the extraction function from GenAI_Validation module
        from validation_script.GenAI_Validation import fetch_validation_rules_with_formula
        
        # Call the extraction function directly with sf_conn
        st.info(f"🔍 Querying validation rules for object: {object_name}")
        records = fetch_validation_rules_with_formula(sf_conn, object_name)
        
        st.info(f"📊 Retrieved {len(records) if records else 0} validation rules from Salesforce")
        
        if records and len(records) > 0:
            # Convert to DataFrame
            df = pd.DataFrame(records)
            st.success(f"✅ Found {len(df)} validation rules")

        if records and len(records) > 0:
            # Convert to DataFrame
            df = pd.DataFrame(records)
            
            # Ensure we have the key columns for GenAI processing
            required_columns = ['ValidationName', 'ErrorConditionFormula', 'ErrorMessage', 'Active']
            
            # Map column names if needed
            column_mapping = {
                'ValidationName': 'ValidationRuleName',
                'FullName': 'ValidationRuleName',
                'ValidationFormula': 'ErrorConditionFormula',
                'ValidationRuleFormula': 'ErrorConditionFormula',
                'ErrorCondition': 'ErrorConditionFormula'
            }
            
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns and new_col not in df.columns:
                    df[new_col] = df[old_col]
            
            # Filter out rules without formulas
            if 'ErrorConditionFormula' in df.columns:
                # Remove rows where ErrorConditionFormula is empty or null
                initial_count = len(df)
                df = df.dropna(subset=['ErrorConditionFormula'])
                df = df[df['ErrorConditionFormula'].str.strip() != '']
                df = df[df['ErrorConditionFormula'] != 'FORMULA_NOT_ACCESSIBLE_VIA_API']
                
                if len(df) < initial_count:
                    st.info(f"ℹ️ Filtered {initial_count - len(df)} rules without accessible formulas")
            
            # Create enhanced file paths using new file management system
            folder_path = get_validation_folder_path('Formula_Extraction', org_name, object_name)
            
            # Save as both CSV and Excel with timestamps
            csv_filename = get_timestamped_filename(f"{object_name}_formula_validation", "csv")
            excel_filename = get_timestamped_filename(f"{object_name}_formula_validation", "xlsx")
            
            csv_file_path = save_validation_results_to_file(df, folder_path, csv_filename, "csv")
            excel_file_path = save_validation_results_to_file(df, folder_path, excel_filename, "xlsx")
            
            # Save Excel with better formatting
            try:
                with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Validation_Formulas', index=False)
                    # Auto-adjust column widths
                    worksheet = writer.sheets['Validation_Formulas']
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
            except Exception as e:
                st.warning(f"⚠️ Could not create Excel file: {str(e)}")
                
            saved_files = [
                {'type': 'Formula CSV', 'filename': csv_filename},
                {'type': 'Formula Excel', 'filename': excel_filename}
            ]
                
            return df, folder_path
        else:
            # No validation rules found - provide better debugging info
            st.warning(f"⚠️ No validation rules found for object '{object_name}'")
            st.info(f"🔍 This could mean:")
            st.info(f"   • The object has no validation rules defined")
            st.info(f"   • The validation rules exist but have no accessible formulas")
            st.info(f"   • There might be a connection or permission issue")
            return None, None
            
    except Exception as e:
        st.error(f"❌ Error extracting validation formulas: {str(e)}")
        st.info("🔍 **Debug Information:**")
        st.write(f"   • Object Name: {object_name}")
        st.write(f"   • Organization: {org_name}")
        st.write(f"   • Error Type: {type(e).__name__}")
        st.write(f"   • Error Details: {str(e)}")
        
        # Show traceback for debugging
        import traceback
        st.code(traceback.format_exc(), language="python")
        
        return None, None

def generate_ai_bundle_from_formulas(formulas_df: pd.DataFrame, object_name: str):
    """
    NEW: Generate AI validation bundle from extracted formulas
    
    Converts each ErrorConditionFormula to a Python validation function
    Creates individual functions for each validation rule
    """
    try:
        from validation_script.GenAI_Validation import SalesforceFormulaConverter
        
        # Initialize the AI converter
        converter = SalesforceFormulaConverter()
        
        # Prepare results tracking
        conversion_stats = {
            'total_formulas': len(formulas_df),
            'functions_created': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'success_rate': 0
        }
        
        python_functions = []
        function_mappings = []
        
        # Process each formula
        for index, row in formulas_df.iterrows():
            rule_name = row.get('ValidationRuleName', f'Rule_{index+1}')
            formula = row.get('ErrorConditionFormula', '')
            error_message = row.get('ErrorMessage', f'Validation failed for {rule_name}')
            active = row.get('Active', True)
            
            if pd.isna(formula) or str(formula).strip() == '':
                st.warning(f"⚠️ Skipping rule '{rule_name}' - no formula available")
                conversion_stats['failed_conversions'] += 1
                continue
            
            try:
                # Generate Python function for this specific formula
                python_function = converter.convert_formula_to_python_function(
                    formula=str(formula),
                    function_name=f"validate_{rule_name.lower().replace(' ', '_').replace('-', '_')}",
                    rule_name=rule_name,
                    error_message=error_message
                )
                
                if python_function:
                    python_functions.append(python_function)
                    function_mappings.append({
                        'rule_name': rule_name,
                        'function_name': f"validate_{rule_name.lower().replace(' ', '_').replace('-', '_')}",
                        'original_formula': formula,
                        'error_message': error_message,
                        'active': active
                    })
                    conversion_stats['functions_created'] += 1
                    conversion_stats['successful_conversions'] += 1
                else:
                    st.warning(f"⚠️ Failed to convert formula for rule '{rule_name}'")
                    conversion_stats['failed_conversions'] += 1
                    
            except Exception as e:
                st.warning(f"⚠️ Error converting rule '{rule_name}': {str(e)}")
                conversion_stats['failed_conversions'] += 1
        
        # Calculate success rate
        if conversion_stats['total_formulas'] > 0:
            conversion_stats['success_rate'] = (conversion_stats['successful_conversions'] / conversion_stats['total_formulas']) * 100
        
        # Generate the complete validation bundle
        if python_functions:
            bundle_content = converter.generate_complete_validation_bundle(
                python_functions=python_functions,
                function_mappings=function_mappings,
                object_name=object_name
            )
            
            # Save the bundle to file
            current_org = st.session_state.current_org if hasattr(st.session_state, 'current_org') else 'default'
            bundle_folder = os.path.join("DataFiles", current_org, object_name, "AI_Bundle")
            os.makedirs(bundle_folder, exist_ok=True)
            
            bundle_file_path = os.path.join(bundle_folder, f"{object_name}_validation_bundle.py")
            validator_file_path = os.path.join(bundle_folder, f"{object_name}_validator.py")
            
            # Save main bundle file
            with open(bundle_file_path, 'w', encoding='utf-8') as f:
                f.write(bundle_content)
            
            # Generate standalone validator file
            validator_content = converter.generate_standalone_validator(
                bundle_file_path=bundle_file_path,
                object_name=object_name,
                function_mappings=function_mappings
            )
            
            with open(validator_file_path, 'w', encoding='utf-8') as f:
                f.write(validator_content)
            
            return {
                'success': True,
                'bundle_path': bundle_file_path,
                'validator_path': validator_file_path,
                'conversion_stats': conversion_stats,
                'function_mappings': function_mappings,
                'python_functions': python_functions
            }
        else:
            return {
                'success': False,
                'error': 'No functions could be generated from the provided formulas',
                'conversion_stats': conversion_stats
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'conversion_stats': conversion_stats
        }

def generate_ai_bundle_from_formulas_with_output(formulas_df: pd.DataFrame, object_name: str, 
                                               conversion_output, detailed_output):
    """
    Generate AI validation bundle from extracted formulas with real-time UI output
    
    Args:
        formulas_df: DataFrame containing validation rules with formulas
        object_name: Name of the Salesforce object
        conversion_output: Streamlit container for status updates
        detailed_output: Streamlit expander for detailed logging
    """
    import io
    import contextlib
    import sys
    
    try:
        from validation_script.GenAI_Validation import SalesforceFormulaConverter
        
        # Initialize the AI converter
        converter = SalesforceFormulaConverter()
        
        # Prepare results tracking
        conversion_stats = {
            'total_formulas': len(formulas_df),
            'functions_created': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'success_rate': 0
        }
        
        python_functions = []
        function_mappings = []
        
        conversion_output.info(f"🔍 Processing {len(formulas_df)} validation rules...")
        
        # Process each formula with detailed output
        for index, row in formulas_df.iterrows():
            rule_name = row.get('ValidationRuleName', f'Rule_{index+1}')
            formula = row.get('ErrorConditionFormula', '')
            error_message = row.get('ErrorMessage', f'Validation failed for {rule_name}')
            active = row.get('Active', True)
            
            # Update progress
            progress = (index + 1) / len(formulas_df)
            conversion_output.progress(progress, text=f"Processing rule {index + 1}/{len(formulas_df)}: {rule_name}")
            
            with detailed_output:
                st.markdown(f"### 🔧 Processing Rule: `{rule_name}`")
                
                if pd.isna(formula) or str(formula).strip() == '':
                    st.warning(f"⚠️ Skipping rule '{rule_name}' - no formula available")
                    conversion_stats['failed_conversions'] += 1
                    continue
                
                st.markdown("**Original Formula:**")
                st.code(str(formula), language="text")
                
                try:
                    # Capture the debug output from the conversion process
                    debug_output = io.StringIO()
                    
                    # Temporarily redirect stdout to capture print statements
                    with contextlib.redirect_stdout(debug_output):
                        # Generate Python function for this specific formula
                        python_function = converter.convert_formula_to_python_function(
                            formula=str(formula),
                            function_name=f"validate_{rule_name.lower().replace(' ', '_').replace('-', '_')}",
                            rule_name=rule_name,
                            error_message=error_message
                        )
                    
                    # Get the captured debug output
                    debug_text = debug_output.getvalue()
                    
                    # Display the conversion process
                    if debug_text:
                        st.markdown("**Conversion Process:**")
                        st.text(debug_text)
                    
                    if python_function:
                        python_functions.append(python_function)
                        function_mappings.append({
                            'rule_name': rule_name,
                            'function_name': f"validate_{rule_name.lower().replace(' ', '_').replace('-', '_')}",
                            'original_formula': formula,
                            'error_message': error_message,
                            'active': active
                        })
                        conversion_stats['functions_created'] += 1
                        conversion_stats['successful_conversions'] += 1
                        
                        st.success(f"✅ Successfully converted rule '{rule_name}'")
                        
                        # Show a preview of the generated function
                        st.markdown("**Generated Python Function:**")
                        st.code(python_function[:500] + "..." if len(python_function) > 500 else python_function, 
                               language="python")
                    else:
                        st.error(f"❌ Failed to convert formula for rule '{rule_name}'")
                        conversion_stats['failed_conversions'] += 1
                        
                except Exception as e:
                    st.error(f"❌ Error converting rule '{rule_name}': {str(e)}")
                    st.exception(e)
                    conversion_stats['failed_conversions'] += 1
                
                st.markdown("---")
        
        # Calculate success rate
        if conversion_stats['total_formulas'] > 0:
            conversion_stats['success_rate'] = (conversion_stats['successful_conversions'] / conversion_stats['total_formulas']) * 100
        
        # Update final status
        conversion_output.info(f"🔄 Generating final validation bundle with {len(python_functions)} functions...")
        
        # Generate the complete validation bundle
        if python_functions:
            bundle_content = converter.generate_complete_validation_bundle(
                python_functions=python_functions,
                function_mappings=function_mappings,
                object_name=object_name
            )
            
            # Save the bundle to file
            current_org = st.session_state.current_org if hasattr(st.session_state, 'current_org') else 'default'
            bundle_folder = os.path.join("DataFiles", current_org, object_name, "AI_Bundle")
            os.makedirs(bundle_folder, exist_ok=True)
            
            bundle_file_path = os.path.join(bundle_folder, f"{object_name}_validation_bundle.py")
            validator_file_path = os.path.join(bundle_folder, f"{object_name}_validator.py")
            
            # Save main bundle file
            with open(bundle_file_path, 'w', encoding='utf-8') as f:
                f.write(bundle_content)
            
            # Generate standalone validator file
            validator_content = converter.generate_standalone_validator(
                bundle_file_path=bundle_file_path,
                object_name=object_name,
                function_mappings=function_mappings
            )
            
            with open(validator_file_path, 'w', encoding='utf-8') as f:
                f.write(validator_content)
            
            return {
                'success': True,
                'bundle_path': bundle_file_path,
                'validator_path': validator_file_path,
                'conversion_stats': conversion_stats,
                'function_mappings': function_mappings,
                'python_functions': python_functions
            }
        else:
            return {
                'success': False,
                'error': 'No functions could be generated from the provided formulas',
                'conversion_stats': conversion_stats
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'conversion_stats': conversion_stats if 'conversion_stats' in locals() else {}
        }

def generate_ai_bundle_from_formulas_with_logging(formulas_df: pd.DataFrame, object_name: str):
    """
    Generate AI validation bundle from extracted formulas with detailed logging to session state
    
    Args:
        formulas_df: DataFrame containing validation rules with formulas
        object_name: Name of the Salesforce object
    """
    import io
    import contextlib
    import sys
    
    try:
        from validation_script.GenAI_Validation import SalesforceFormulaConverter
        
        # Initialize the AI converter
        converter = SalesforceFormulaConverter()
        
        # Prepare results tracking
        conversion_stats = {
            'total_formulas': len(formulas_df),
            'functions_created': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'success_rate': 0
        }
        
        python_functions = []
        function_mappings = []
        
        # Initialize conversion logs in session state if not exists
        if 'conversion_logs' not in st.session_state:
            st.session_state.conversion_logs = []
        
        # Clear previous logs
        st.session_state.conversion_logs = []
        
        # Process each formula with detailed logging
        for index, row in formulas_df.iterrows():
            rule_name = row.get('ValidationRuleName', f'Rule_{index+1}')
            formula = row.get('ErrorConditionFormula', '')
            error_message = row.get('ErrorMessage', f'Validation failed for {rule_name}')
            active = row.get('Active', True)
            
            # Initialize log entry for this rule
            log_entry = {
                'rule_name': rule_name,
                'formula': str(formula),
                'error_message': error_message,
                'status': 'failed',
                'conversion_steps': [],
                'generated_function': None,
                'error': None
            }
            
            if pd.isna(formula) or str(formula).strip() == '':
                log_entry['error'] = "No formula available"
                log_entry['conversion_steps'].append("⚠️ Skipped - no formula available")
                st.session_state.conversion_logs.append(log_entry)
                conversion_stats['failed_conversions'] += 1
                continue
            
            try:
                log_entry['conversion_steps'].append(f"🔍 Starting conversion for rule: {rule_name}")
                log_entry['conversion_steps'].append(f"📝 Original formula: {str(formula)[:100]}...")
                
                # Capture the debug output from the conversion process
                debug_output = io.StringIO()
                
                # Temporarily redirect stdout to capture print statements
                with contextlib.redirect_stdout(debug_output):
                    # Generate Python function for this specific formula
                    python_function = converter.convert_formula_to_python_function(
                        formula=str(formula),
                        function_name=f"validate_{rule_name.lower().replace(' ', '_').replace('-', '_')}",
                        rule_name=rule_name,
                        error_message=error_message
                    )
                
                # Get the captured debug output
                debug_text = debug_output.getvalue()
                
                # Add debug steps to log
                if debug_text:
                    debug_lines = debug_text.strip().split('\n')
                    for line in debug_lines:
                        if line.strip():
                            log_entry['conversion_steps'].append(f"🔧 {line.strip()}")
                
                if python_function:
                    # Validate syntax of generated function before including it
                    try:
                        import ast
                        ast.parse(python_function)
                        log_entry['conversion_steps'].append("✅ Syntax validation passed")
                        
                        python_functions.append(python_function)
                        function_mappings.append({
                            'rule_name': rule_name,
                            'function_name': f"validate_{rule_name.lower().replace(' ', '_').replace('-', '_')}",
                            'original_formula': formula,
                            'error_message': error_message,
                            'active': active
                        })
                        conversion_stats['functions_created'] += 1
                        conversion_stats['successful_conversions'] += 1
                        
                        log_entry['status'] = 'success'
                        log_entry['generated_function'] = python_function
                        log_entry['conversion_steps'].append("✅ Conversion successful")
                        
                    except SyntaxError as syntax_err:
                        log_entry['error'] = f"Syntax error in generated function: {syntax_err}"
                        log_entry['conversion_steps'].append(f"❌ Syntax validation failed: {syntax_err}")
                        log_entry['conversion_steps'].append("⚠️ Function excluded from bundle due to syntax error")
                        conversion_stats['failed_conversions'] += 1
                        
                else:
                    log_entry['error'] = "Conversion returned None"
                    log_entry['conversion_steps'].append("❌ Conversion failed - no function generated")
                    conversion_stats['failed_conversions'] += 1
                    
            except Exception as e:
                log_entry['error'] = str(e)
                log_entry['conversion_steps'].append(f"❌ Error during conversion: {str(e)}")
                conversion_stats['failed_conversions'] += 1
            
            # Add log entry to session state
            st.session_state.conversion_logs.append(log_entry)
        
        # Calculate success rate
        if conversion_stats['total_formulas'] > 0:
            conversion_stats['success_rate'] = (conversion_stats['successful_conversions'] / conversion_stats['total_formulas']) * 100
        
        # Generate the complete validation bundle
        if python_functions:
            bundle_content = converter.generate_complete_validation_bundle(
                python_functions=python_functions,
                function_mappings=function_mappings,
                object_name=object_name
            )
            
            # Save the bundle to file
            current_org = st.session_state.current_org if hasattr(st.session_state, 'current_org') else 'default'
            bundle_folder = os.path.join("DataFiles", current_org, object_name, "AI_Bundle")
            os.makedirs(bundle_folder, exist_ok=True)
            
            bundle_file_path = os.path.join(bundle_folder, f"{object_name}_validation_bundle.py")
            validator_file_path = os.path.join(bundle_folder, f"{object_name}_validator.py")
            
            # Save main bundle file
            with open(bundle_file_path, 'w', encoding='utf-8') as f:
                f.write(bundle_content)
            
            # Generate standalone validator file
            validator_content = converter.generate_standalone_validator(
                bundle_file_path=bundle_file_path,
                object_name=object_name,
                function_mappings=function_mappings
            )
            
            with open(validator_file_path, 'w', encoding='utf-8') as f:
                f.write(validator_content)
            
            return {
                'success': True,
                'bundle_path': bundle_file_path,
                'validator_path': validator_file_path,
                'conversion_stats': conversion_stats,
                'function_mappings': function_mappings,
                'python_functions': python_functions
            }
        else:
            return {
                'success': False,
                'error': 'No functions could be generated from the provided formulas',
                'conversion_stats': conversion_stats
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'conversion_stats': conversion_stats if 'conversion_stats' in locals() else {}
        }

def run_genai_validation_on_data(df: pd.DataFrame, ai_bundle_result: dict):
    """
    Run GenAI validation on the uploaded data using the generated validation bundle
    """
    try:
        # Import required modules at the top
        import os
        import importlib.util
        import sys
        import pandas as pd
        
        # Check for duplicate column names and handle them
        if df.columns.duplicated().any():
            duplicate_cols = df.columns[df.columns.duplicated(keep=False)].unique()
            return {
                'success': False, 
                'error': f'Duplicate column names detected: {list(duplicate_cols)}. This typically happens when multiple CSV columns are mapped to the same Salesforce field. Please adjust your field mappings to ensure each Salesforce field is mapped to only one CSV column.'
            }
        
        # Get the function mappings from the AI bundle result
        function_mappings = ai_bundle_result.get('function_mappings', [])
        bundle_path = ai_bundle_result.get('bundle_path')
        num_functions = ai_bundle_result.get('num_functions', 0)
        
        # Check if we have validation functions either through function_mappings or num_functions
        if not function_mappings and num_functions == 0:
            return {'success': False, 'error': 'No validation functions found in AI bundle'}
        
        if not bundle_path or not os.path.exists(bundle_path):
            return {'success': False, 'error': 'AI bundle file not found'}
        
        # Validate Python syntax before attempting to load
        syntax_messages = []  # Store messages to display later
        
        try:
            with open(bundle_path, 'r', encoding='utf-8') as f:
                bundle_code = f.read()
            
            # Auto-fix common AI conversion errors before validation
            original_code = bundle_code
            fixed_code = bundle_code
            fixes_applied = []
            
            # Fix 1: Remove invalid $ symbols (Salesforce syntax not converted)
            if '$df[' in fixed_code or '$ df[' in fixed_code:
                fixed_code = fixed_code.replace('$df[', 'df[')
                fixed_code = fixed_code.replace('$ df[', 'df[')
                fixes_applied.append("Removed invalid '$' symbols")
            
            # Fix 1b: Remove stray $ before safe_get / function calls (from unhandled $-globals)
            if '$safe_get(' in fixed_code or '$_' in fixed_code:
                fixed_code = re.sub(r'\$safe_get\(', 'safe_get(', fixed_code)
                fixed_code = re.sub(r'\$(_[a-z])', r'\1', fixed_code)
                fixes_applied.append("Removed stray '$' from global merge field references")
            
            # Fix 2: Fix incorrect .df[] patterns
            # (uses the module-level `re`; a local `import re` here made `re` local to the
            # whole function, so Fix 1b above raised UnboundLocalError)
            # Pattern: df['something'].df['field'] -> df['something']['field']
            _before_fix2 = fixed_code
            fixed_code = re.sub(r"df\['([^']+)'\]\.df\['([^']+)'\]", r"df['\2']", fixed_code)
            if _before_fix2 != fixed_code:
                fixes_applied.append("Fixed cross-object reference syntax")
            
            # Fix 3: Remove $Permission, $User references (unsupported)
            # Strip docstrings and comments to avoid false positives on original formula text
            _exec_code = re.sub(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', '', fixed_code)
            _exec_code = re.sub(r'#[^\n]*', '', _exec_code)
            if '$Permission' in _exec_code or '$User' in _exec_code:
                _before_fix3 = fixed_code
                fixed_code = re.sub(r"\$Permission\.df\['[^']+'\]", "False", fixed_code)
                fixed_code = re.sub(r"\$Permission\.\w+", "False", fixed_code)
                fixed_code = re.sub(r"\$User\.df\['[^']+'\]", "''", fixed_code)
                fixed_code = re.sub(r"\$User\.\w+", "''", fixed_code)
                if _before_fix3 != fixed_code:
                    fixes_applied.append("Replaced unsupported Permission/User references with default values")
                    syntax_messages.append(("warning", "⚠️ **Note:** This validation rule uses $Permission or $User references which are not supported in offline validation. These have been replaced with default values."))
            
            # Fix 4: Correct old _ischanged/_isnew helper logic in previously generated bundles
            # Old _ischanged returned True for non-blank fields (caused all records to fail)
            # Old _isnew returned True always (caused all records to fail)
            if 'return not _is_blank(field_value)' in fixed_code:
                _before_fix4 = fixed_code
                # Replace old _ischanged body: "return not _is_blank(field_value)" → "return False"
                fixed_code = fixed_code.replace(
                    '    return not _is_blank(field_value)',
                    '    return False  # Cannot detect changes offline - safe default'
                )
                if _before_fix4 != fixed_code:
                    fixes_applied.append("Fixed _ischanged() to return False (cannot detect field changes in offline validation)")
            
            if re.search(r'def _isnew\(\):\s*\n(?:\s*"""[\s\S]*?"""\s*\n|\s*#[^\n]*\n)*\s*return True', fixed_code):
                fixed_code = re.sub(
                    r'(def _isnew\(\):\s*\n(?:\s*"""[\s\S]*?"""\s*\n|\s*#[^\n]*\n)*\s*)return True',
                    r'\1return False  # Cannot detect record creation context offline - safe default',
                    fixed_code
                )
                fixes_applied.append("Fixed _isnew() to return False (cannot detect creation context in offline validation)")
            
            # Fix 5: Inject field-presence skip into old validation functions that lack it
            # Old bundles evaluate rules even when their required fields aren't in the data
            if '_required_fields' not in fixed_code and 'def validate_' in fixed_code:
                # Pattern: match each validate_ function's safe_get helper block
                # and inject the field-presence guard just before it
                _fix5_pattern = re.compile(
                    r'(    # Helper to safely retrieve field values from row data\n'
                    r'    def safe_get\(field_name\):)'
                )
                if _fix5_pattern.search(fixed_code):
                    _inject = (
                        '    # Skip this rule if none of its required fields are present in the data\n'
                        '    # (auto-injected by toolkit)\n'
                        '    if hasattr(row_data, "keys"):\n'
                        '        _available = set(row_data.keys())\n'
                        '    elif hasattr(row_data, "index"):\n'
                        '        _available = set(row_data.index)\n'
                        '    else:\n'
                        '        _available = set()\n'
                        '\n'
                        r'\1'
                    )
                    _before_fix5 = fixed_code
                    fixed_code = _fix5_pattern.sub(_inject, fixed_code)
                    if _before_fix5 != fixed_code:
                        fixes_applied.append("Added field-presence check to skip rules whose fields are not in the data")
            
            # Fix 6: Context-dependent rules with hardcoded True from $Permission/$User
            # In old bundles, $Permission.X was replaced with True, causing rules to always
            # fire their error condition. Replace entire error_condition with False for these.
            import re as _re6
            _ctx_pattern = _re6.compile(
                r'(        error_condition = .*)(?:_or\(\s*True\s*,\s*_not\(True\)\s*\)|_and\(\s*True\s*,|_or\(\s*True\s*,\s*True\s*\))(.*)\n'
            )
            if _ctx_pattern.search(fixed_code):
                _before_fix6 = fixed_code
                # Replace the entire error_condition line with False for context-dependent rules
                fixed_code = _re6.sub(
                    r'        error_condition = False  # Context-dependent rule (uses $Permission/$User) - skipped in offline validation\n',
                    _ctx_pattern,
                    fixed_code
                )
                if _before_fix6 != fixed_code:
                    fixes_applied.append("Skipped context-dependent rules that use $Permission/$User (cannot evaluate offline)")
            
            # If fixes were applied, save the corrected version
            if fixes_applied:
                syntax_messages.append(("info", "### ⚠️ Auto-Correction Applied"))
                syntax_messages.append(("warning", f"**Fixed {len(fixes_applied)} syntax issue(s):**"))
                for idx, fix in enumerate(fixes_applied, 1):
                    syntax_messages.append(("text", f"  {idx}. {fix}"))
                
                # Save corrected bundle
                with open(bundle_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_code)
                syntax_messages.append(("success", "✅ Bundle has been auto-corrected and saved"))
                bundle_code = fixed_code
            
            # Try to compile the code to check for syntax errors
            compile(bundle_code, bundle_path, 'exec')
            syntax_messages.append(("success", "✅ Bundle syntax validation passed"))
            
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            st.error(f"❌ Bundle file has invalid Python syntax: {error_msg}")
            st.error("💡 **Solution:** Regenerate the AI validation bundle (Step 2) to fix syntax errors")
            
            # Show the problematic line if possible
            try:
                with open(bundle_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if e.lineno and e.lineno <= len(lines):
                        st.code(f"Line {e.lineno}: {lines[e.lineno-1].strip()}", language="python")
                        # Show context (2 lines before and after)
                        start = max(0, e.lineno - 3)
                        end = min(len(lines), e.lineno + 2)
                        with st.expander("📄 View Context", expanded=False):
                            st.code(''.join(lines[start:end]), language="python")
            except:
                pass
                
            return {'success': False, 'error': f'Invalid Python syntax in bundle: {error_msg}. Please regenerate the validation bundle.'}
        
        except Exception as e:
            return {'success': False, 'error': f'Error reading bundle file: {str(e)}'}
        
        # Import the validation bundle dynamically
        # Clean up any existing module to avoid conflicts
        if 'validation_bundle' in sys.modules:
            del sys.modules['validation_bundle']
            
        spec = importlib.util.spec_from_file_location("validation_bundle", bundle_path)
        validation_module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(validation_module)
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            st.error(f"❌ Failed to load bundle: {error_msg}")
            st.error("💡 **Solution:** The AI-generated bundle has syntax errors. Please regenerate it in Step 2.")
            return {'success': False, 'error': f'Bundle syntax error: {error_msg}. Please regenerate the validation bundle in Step 2.'}
        except Exception as e:
            st.error(f"❌ Failed to load validation bundle: {str(e)}")
            st.error("💡 **Possible solutions:**")
            st.markdown("""
            1. **Regenerate the bundle** - Go back to Step 2 and click "Generate Python Validation Bundle" again
            2. **Check formula complexity** - Very complex formulas may cause generation issues
            3. **Verify file integrity** - Ensure the bundle file wasn't manually edited
            """)
            return {'success': False, 'error': f'Failed to load validation bundle: {e}. Bundle file may be corrupted or incomplete. Please regenerate in Step 2.'}
        
        # Check for required functions
        has_validate_dataframe = hasattr(validation_module, 'validate_dataframe')

        if not has_validate_dataframe:
            return {'success': False, 'error': 'validate_dataframe function missing from bundle. Bundle generation may have failed - please regenerate in Step 2.'}

        # Use the validate_dataframe function from the bundle
        # There are two possible function signatures:
        # 1. validate_dataframe(df) -> (valid_df, invalid_df, validation_results) [new format]
        # 2. validate_dataframe(df, active_only=True) -> validated_df [old format]
        
        if hasattr(validation_module, 'validate_dataframe'):
            try:
                # First try the new format (returns 3 values)
                result = validation_module.validate_dataframe(df)
                
                # Check if result is a tuple with 3 elements
                if isinstance(result, tuple) and len(result) == 3:
                    valid_df, invalid_df, validation_results = result
                    st.info("✅ Using new bundle format with tuple return")
                else:
                    # Handle old format or single DataFrame return
                    st.warning("⚠️ Using legacy bundle format - converting results")
                    validated_df = result
                    
                    # Extract valid/invalid records from the validated DataFrame
                    if 'is_valid' in validated_df.columns:
                        valid_df = validated_df[validated_df['is_valid'] == True].copy()
                        invalid_df = validated_df[validated_df['is_valid'] == False].copy()
                        
                        # Create validation_results from the DataFrame
                        validation_results = []
                        for idx, row in validated_df.iterrows():
                            errors = []
                            if 'validation_errors' in row:
                                if isinstance(row['validation_errors'], list):
                                    errors = row['validation_errors']
                                elif isinstance(row['validation_errors'], str) and row['validation_errors']:
                                    errors = [row['validation_errors']]
                            
                            validation_results.append({
                                'index': idx,
                                'is_valid': row.get('is_valid', True),
                                'errors': errors,
                                'rule_results': {}
                            })
                    else:
                        # If no validation columns, treat all as valid
                        valid_df = validated_df.copy()
                        invalid_df = pd.DataFrame()
                        validation_results = [{'index': idx, 'is_valid': True, 'errors': [], 'rule_results': {}} 
                                            for idx in validated_df.index]
                        st.warning("⚠️ No validation status found - treating all records as valid")
                        
            except ValueError as ve:
                if "too many values to unpack" in str(ve):
                    return {'success': False, 'error': f'Bundle function signature mismatch. Expected validate_dataframe to return 3 values, but got different return format. Bundle may be incomplete or corrupted. Error: {ve}'}
                else:
                    return {'success': False, 'error': f'Error calling validate_dataframe: {ve}'}
            except Exception as e:
                return {'success': False, 'error': f'Validation function error: {e}'}
        else:
            return {'success': False, 'error': 'validate_dataframe function not found in bundle. Bundle may be incomplete - please regenerate in Step 2.'}
        
        # Create all_df by combining original data with validation results
        all_df = df.copy()
        all_df['is_valid'] = False  # Default to invalid
        all_df['validation_errors'] = ''
        
        # Update validation status based on results
        valid_indices = valid_df.index.tolist() if len(valid_df) > 0 else []
        invalid_indices = invalid_df.index.tolist() if len(invalid_df) > 0 else []
        
        # Mark valid records
        if valid_indices:
            all_df.loc[valid_indices, 'is_valid'] = True
            
        # Add error details for invalid records
        for result in validation_results:
            if not result['is_valid'] and result['index'] in all_df.index:
                error_messages = [error for error in result['errors']]
                all_df.loc[result['index'], 'validation_errors'] = '; '.join(error_messages)
        
        # Calculate summary statistics
        total_records = len(df)
        valid_records = len(valid_df)
        invalid_records = len(invalid_df)
        success_rate = (valid_records / total_records * 100) if total_records > 0 else 0
        
        # Collect error details for display
        error_summary = []
        for result in validation_results:
            if not result['is_valid']:
                for error in result['errors']:
                    error_summary.append({
                        'record_index': result['index'],
                        'rule_name': 'Validation Rule',  # Could be enhanced to show specific rule
                        'error_message': error
                    })
        
        return {
            'success': True,
            'total_records': total_records,
            'valid_records': valid_records,
            'invalid_records': invalid_records,
            'success_rate': success_rate,
            'valid_df': valid_df,
            'invalid_df': invalid_df,
            'all_df': all_df,  # Add the missing all_df key with validation status
            'validated_df': all_df,
            'error_summary': error_summary,
            'function_mappings': function_mappings,
            'validation_results': validation_results,  # Include raw validation results
            'syntax_messages': syntax_messages  # Include syntax validation messages
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def display_genai_validation_results(validation_results: dict, object_name: str):
    """
    Display the results of GenAI validation with field mapping support
    """
    try:
        # Display syntax validation messages if available
        if 'syntax_messages' in validation_results and validation_results['syntax_messages']:
            st.markdown("### 🔍 **Bundle Validation**")
            for msg_type, message in validation_results['syntax_messages']:
                if msg_type == "success":
                    st.success(message)
                elif msg_type == "warning":
                    st.warning(message)
                elif msg_type == "info":
                    st.info(message)
                elif msg_type == "error":
                    st.error(message)
                else:  # text
                    st.markdown(message)
            st.markdown("---")
        
        st.markdown("### 📊 **Validation Results**")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Records", validation_results['total_records'])
        
        with col2:
            st.metric("Valid Records", validation_results['valid_records'], 
                     delta=f"{validation_results['success_rate']:.1f}%")
        
        with col3:
            st.metric("Invalid Records", validation_results['invalid_records'])
        
        with col4:
            st.metric("Success Rate", f"{validation_results['success_rate']:.1f}%")
        
        # Show field mapping info if available
        if hasattr(st.session_state, 'current_field_mappings') and st.session_state.current_field_mappings:
            st.markdown("### 🔗 **Field Mappings Used**")
            with st.expander("View field mappings used in validation", expanded=False):
                mapping_data = []
                for csv_col, sf_field in st.session_state.current_field_mappings.items():
                    if sf_field:  # Only show mapped fields
                        mapping_data.append({
                            "CSV Column": csv_col,
                            "Salesforce Field": sf_field
                        })
                
                if mapping_data:
                    mapping_df = pd.DataFrame(mapping_data)
                    st.dataframe(mapping_df, use_container_width=True)
        
        # Show error details if there are invalid records
        if validation_results['invalid_records'] > 0:
            st.markdown("### ❌ **Validation Errors**")
            
            # Group errors by rule
            error_summary = validation_results['error_summary']
            error_by_rule = {}
            for error in error_summary:
                rule_name = error['rule_name']
                if rule_name not in error_by_rule:
                    error_by_rule[rule_name] = []
                error_by_rule[rule_name].append(error)
            
            # Display error summary
            for rule_name, errors in error_by_rule.items():
                with st.expander(f"🚫 {rule_name} ({len(errors)} errors)"):
                    error_df = pd.DataFrame(errors)
                    st.dataframe(error_df, use_container_width=True)
        
        # Show data tables with original CSV column names if available
        st.markdown("### 📋 **Data Tables**")
        
        # Get original data if available
        original_data = getattr(st.session_state, 'genai_original_data', None)
        field_mappings = getattr(st.session_state, 'current_field_mappings', {})
        
        # Get field mappings and original data from session state if available
        field_mappings = getattr(st.session_state, 'current_field_mappings', {})
        original_data = getattr(st.session_state, 'genai_original_data', None)
        
        # Only show field mapping conversion if we have both mappings and original data
        if original_data is not None and field_mappings:
            # Create reverse mapping (Salesforce field -> CSV column)
            reverse_mapping = {v: k for k, v in field_mappings.items() if v}
            
            # Function to convert dataframe back to original column names
            def convert_to_original_columns(df):
                if df is None or df.empty:
                    return df
                
                converted_df = df.copy()
                columns_to_rename = {}
                
                # First, prepare column renaming without duplicates
                for sf_field, csv_col in reverse_mapping.items():
                    if sf_field in df.columns and sf_field != csv_col:
                        # Check if target column name already exists
                        if csv_col not in df.columns and csv_col not in columns_to_rename.values():
                            columns_to_rename[sf_field] = csv_col
                
                # Apply column renaming
                if columns_to_rename:
                    converted_df = converted_df.rename(columns=columns_to_rename)
                
                # Add any additional columns from original data that weren't mapped
                if hasattr(converted_df, 'index') and len(converted_df) > 0:
                    for csv_col in original_data.columns:
                        if (csv_col not in converted_df.columns and 
                            csv_col not in field_mappings and 
                            len(original_data) >= len(converted_df)):
                            # Add unmapped columns from original data
                            converted_df[csv_col] = original_data[csv_col].iloc[:len(converted_df)].values
                
                return converted_df
        else:
            # If no field mappings available, use data as-is
            def convert_to_original_columns(df):
                return df if df is not None else pd.DataFrame()
            
        tab1, tab2, tab3 = st.tabs(["✅ Valid Records", "❌ Invalid Records", "📊 All Records"])
        
        with tab1:
            if validation_results['valid_records'] > 0:
                st.markdown(f"**{validation_results['valid_records']} valid records:**")
                valid_display_df = convert_to_original_columns(validation_results['valid_df'])
                st.dataframe(valid_display_df, use_container_width=True, height=400)
                
                # Download button for valid records
                # The CSV is built only when the button is clicked (not on every rerun).
                st.download_button(
                    label="📥 Download Valid Records",
                    data=lambda frame=valid_display_df: frame.to_csv(index=False),
                    file_name=f"{object_name}_valid_records.csv",
                    mime="text/csv", on_click='ignore'
                )
            else:
                st.info("No valid records found")
        
        with tab2:
            if validation_results['invalid_records'] > 0:
                st.markdown(f"**{validation_results['invalid_records']} invalid records:**")
                invalid_display_df = convert_to_original_columns(validation_results['invalid_df'])
                
                # Add validation error information
                if 'validation_errors' in invalid_display_df.columns:
                    st.dataframe(invalid_display_df, use_container_width=True, height=400)
                else:
                    st.dataframe(invalid_display_df, use_container_width=True, height=400)
                
                # Download button for invalid records
                st.download_button(
                    label="📥 Download Invalid Records",
                    data=lambda frame=invalid_display_df: frame.to_csv(index=False),
                    file_name=f"{object_name}_invalid_records.csv",
                    mime="text/csv", on_click='ignore'
                )
            else:
                st.info("All records are valid!")
        
        with tab3:
            st.markdown(f"**All {validation_results['total_records']} records:**")
            all_display_df = convert_to_original_columns(validation_results['all_df'])
            st.dataframe(all_display_df, use_container_width=True, height=400)
            
            # Download button for all records
            st.download_button(
                label="📥 Download All Records",
                data=lambda frame=all_display_df: frame.to_csv(index=False),
                file_name=f"{object_name}_all_validation_results.csv",
                mime="text/csv", on_click='ignore'
            )
    
    except Exception as e:
        st.error(f"Error displaying validation results: {str(e)}")
        st.exception(e)
        
        # Fallback display without field mapping
        try:
            tab1, tab2, tab3 = st.tabs(["✅ Valid Records", "❌ Invalid Records", "📊 All Records"])
            
            with tab1:
                if validation_results['valid_records'] > 0:
                    st.markdown(f"**{validation_results['valid_records']} valid records:**")
                    st.dataframe(validation_results['valid_df'], use_container_width=True, height=400)
                else:
                    st.info("No valid records found")
            
            with tab2:
                if validation_results['invalid_records'] > 0:
                    st.markdown(f"**{validation_results['invalid_records']} invalid records:**")
                    st.dataframe(validation_results['invalid_df'], use_container_width=True, height=400)
                else:
                    st.info("All records are valid!")
            
            with tab3:
                st.markdown(f"**All {validation_results['total_records']} records:**")
                st.dataframe(validation_results.get('all_df', pd.DataFrame()), use_container_width=True, height=400)
        except Exception as fallback_error:
            st.error(f"Error in fallback display: {str(fallback_error)}")
        st.error(f"❌ Error displaying validation results: {str(e)}")
        st.exception(e)

def create_conversion_summary_report(conversion_logs):
    """Create a detailed text summary of the conversion process"""
    from datetime import datetime
    
    report_lines = []
    report_lines.append("="*80)
    report_lines.append("GENAI VALIDATION - CONVERSION SUMMARY REPORT")
    report_lines.append("="*80)
    report_lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Total Rules Processed: {len(conversion_logs)}")
    report_lines.append("")
    
    # Summary statistics
    successful = sum(1 for log in conversion_logs if log['status'] == 'success')
    failed = len(conversion_logs) - successful
    success_rate = (successful / len(conversion_logs) * 100) if conversion_logs else 0
    
    report_lines.append("SUMMARY STATISTICS:")
    report_lines.append("-" * 20)
    report_lines.append(f"✅ Successful Conversions: {successful}")
    report_lines.append(f"❌ Failed Conversions: {failed}")
    report_lines.append(f"📊 Success Rate: {success_rate:.1f}%")
    report_lines.append("")
    
    # Detailed results for each rule
    report_lines.append("DETAILED CONVERSION RESULTS:")
    report_lines.append("-" * 30)
    
    for i, log in enumerate(conversion_logs, 1):
        report_lines.append(f"\n{i}. RULE: {log['rule_name']}")
        report_lines.append("   " + "="*50)
        report_lines.append(f"   Status: {'✅ SUCCESS' if log['status'] == 'success' else '❌ FAILED'}")
        report_lines.append(f"   Original Formula: {log['formula'][:100]}{'...' if len(log['formula']) > 100 else ''}")
        
        if log['status'] == 'success':
            report_lines.append("   ✅ Conversion completed successfully")
            if log.get('generated_function'):
                func_preview = log['generated_function'][:200]
                report_lines.append(f"   Generated Function Preview: {func_preview}...")
        else:
            report_lines.append(f"   ❌ Error: {log.get('error', 'Unknown error')}")
        
        # Add conversion steps
        if log.get('conversion_steps'):
            report_lines.append("   Conversion Steps:")
            for step in log['conversion_steps']:
                report_lines.append(f"     • {step}")
        
        report_lines.append("")
    
    # Summary recommendations
    report_lines.append("RECOMMENDATIONS:")
    report_lines.append("-" * 15)
    if failed > 0:
        report_lines.append("❗ Some validation rules failed to convert. Review the detailed logs above.")
        report_lines.append("   Common issues:")
        report_lines.append("   • Complex Salesforce-specific functions not yet supported")
        report_lines.append("   • Invalid or malformed formulas")
        report_lines.append("   • Missing field references")
    
    if successful > 0:
        report_lines.append("✅ Successfully converted rules can be used for data validation.")
        report_lines.append("   Download the validation bundle to use these functions.")
    
    report_lines.append("")
    report_lines.append("="*80)
    report_lines.append("END OF REPORT")
    report_lines.append("="*80)
    
    return "\n".join(report_lines)

def display_conversion_logs(logs):
    """Helper function to display conversion logs in a formatted way"""
    for log_entry in logs:
        st.markdown(f"#### 🔧 Rule: `{log_entry['rule_name']}`")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**Original Formula:**")
            st.code(log_entry['formula'], language="text")
            
            if log_entry['status'] == 'success':
                st.success("✅ Conversion Successful")
            else:
                st.error("❌ Conversion Failed")
                if log_entry.get('error'):
                    st.error(f"Error: {log_entry['error']}")
        
        with col2:
            if log_entry['status'] == 'success' and log_entry.get('generated_function'):
                st.markdown("**Generated Python Function:**")
                # Show first 300 characters of the function
                function_preview = log_entry['generated_function']
                if len(function_preview) > 300:
                    function_preview = function_preview[:300] + "..."
                st.code(function_preview, language="python")
        
        # Show conversion process steps if available
        if log_entry.get('conversion_steps'):
            st.markdown("**Conversion Steps:**")
            with st.expander("View Steps", expanded=False):
                for step in log_entry['conversion_steps']:
                    st.text(f"• {step}")
        
        st.markdown("---")


def show_saved_mappings_manager(org_name: str):
    """Display and manage saved field mappings for all objects"""
    from ui_components.field_mapping_manager import list_saved_mappings, delete_field_mapping, load_field_mapping, display_mapping_info
    from ui_components.field_mapping_ui import show_managed_mappings
    
    st.subheader("💾 Saved Field Mappings Manager")
    st.markdown("View, manage, and reuse field mappings saved from previous validations")
    
    # Get organization-specific mappings
    saved_mappings = list_saved_mappings(org_name)
    
    if not saved_mappings:
        st.info(f"📭 No saved field mappings found for {org_name}")
        st.markdown("---")
        st.info("💡 **Tip:** Save field mappings while performing validations (Schema, Enhanced, or GenAI) to reuse them later!")
        return
    
    # Display statistics
    st.markdown("### 📊 Mapping Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    validation_types = {}
    objects = set()
    total_fields = 0
    
    for mapping in saved_mappings:
        vtype = mapping.get('validation_type', 'unknown')
        validation_types[vtype] = validation_types.get(vtype, 0) + 1
        objects.add(mapping.get('object_name'))
        total_fields += mapping.get('mapping_count', 0)
    
    with col1:
        st.metric("Total Mappings", len(saved_mappings))
    with col2:
        st.metric("Objects", len(objects))
    with col3:
        st.metric("Total Fields Mapped", total_fields)
    with col4:
        st.metric("Validation Types", len(validation_types))
    
    # Show validation type breakdown
    if validation_types:
        st.markdown("**Validation Types:**")
        for vtype, count in validation_types.items():
            st.write(f"• {vtype.title()}: {count} mapping(s)")
    
    st.markdown("---")
    
    # Show individual mappings
    st.markdown("### 📋 Saved Mappings")
    
    # Filter options
    col1, col2 = st.columns(2)
    
    with col1:
        filter_validation_type = st.selectbox(
            "Filter by Validation Type",
            ["All"] + list(validation_types.keys()),
            key="filter_vtype"
        )
    
    with col2:
        filter_object = st.selectbox(
            "Filter by Object",
            ["All"] + sorted(list(objects)),
            key="filter_object"
        )
    
    # Filter mappings
    filtered_mappings = saved_mappings
    if filter_validation_type != "All":
        filtered_mappings = [m for m in filtered_mappings if m.get('validation_type') == filter_validation_type]
    if filter_object != "All":
        filtered_mappings = [m for m in filtered_mappings if m.get('object_name') == filter_object]
    
    if not filtered_mappings:
        st.warning("No mappings match the selected filters")
        return
    
    st.markdown(f"**Showing {len(filtered_mappings)} mapping(s):**")
    st.markdown("---")
    
    # Display each mapping
    for idx, mapping in enumerate(filtered_mappings):
        col1, col2, col3 = st.columns([2, 3, 1])
        
        with col1:
            st.markdown(f"**Object:** `{mapping['object_name']}`")
            st.markdown(f"**Type:** {mapping['validation_type'].title()}")
        
        with col2:
            st.markdown(f"**Fields:** {mapping['mapping_count']}")
            st.markdown(f"**Saved:** {mapping['saved_at'].split('T')[0]}")
        
        with col3:
            if st.button("👁️ View", key=f"view_{idx}"):
                st.session_state[f"show_mapping_{idx}"] = True
        
        # Show detailed mapping if requested
        if st.session_state.get(f"show_mapping_{idx}", False):
            mapping_data, _, _ = load_field_mapping(org_name, mapping['object_name'])
            
            if mapping_data:
                with st.expander(f"📄 Field Mappings for {mapping['object_name']}", expanded=True):
                    field_mappings = mapping_data.get('field_mappings', {})
                    
                    # Create a nice table view
                    mapping_list = [
                        {"CSV Column": csv_col, "Salesforce Field": sf_field}
                        for csv_col, sf_field in field_mappings.items()
                    ]
                    
                    mapping_df = pd.DataFrame(mapping_list)
                    st.dataframe(mapping_df, use_container_width=True, hide_index=True)
                    
                    # Action buttons
                    col_action1, col_action2, col_action3 = st.columns(3)
                    
                    with col_action1:
                        if st.button("📋 Copy Mapping Details", key=f"copy_{idx}"):
                            st.success("Mapping details copied to clipboard")
                    
                    with col_action2:
                        if st.button("🗑️ Delete Mapping", key=f"delete_{idx}"):
                            success, message = delete_field_mapping(org_name, mapping['object_name'])
                            if success:
                                st.success(message)
                                _mark_val_tab(5)
                                st.rerun()
                            else:
                                st.error(message)
                    
                    with col_action3:
                        if st.button("✅ Mark for Reuse", key=f"mark_reuse_{idx}"):
                            st.success(f"✅ Marked {mapping['object_name']} for reuse in next validation")
        
        st.markdown("---")


def _reset_enhanced_validation_state():
    """on_click callback of 'Start New Transformation': forget the Enhanced tab's data,
    object, mappings and lookup settings (the published Step 2 result is kept)."""
    ss = st.session_state
    for key in ('enhanced_validation_data', 'enhanced_validation_source', 'enhanced_validation_object',
                'enhanced_unresolved_lookup_indices', 'enhanced_validation_object_selectbox',
                'enhanced_validation_source_choice', 'enhanced_validation_upload',
                '_flowseed_enhanced_validation_object_selectbox', '_flowseed_enhanced_validation_source_choice'):
        ss.pop(key, None)
    mapped_objects = [k[len('enhanced_field_mappings_'):] for k in list(ss.keys())
                      if isinstance(k, str) and k.startswith('enhanced_field_mappings_')]
    for object_name in mapped_objects:
        _clear_session_keys(f"mapping_{object_name}_")
    for prefix in ('enhanced_field_mappings_', 'enhanced_lookup_configs_',
                   'enhanced_validation_sql', 'enhanced_validation_oracle'):
        _clear_session_keys(prefix)


def show_enhanced_validation(sf_conn):
    """Enhanced validation interface with transform validation and comprehensive reporting"""
    
    st.subheader("⚡ Enhanced Transform Validation")
    st.markdown("Advanced data transformation validation with success/failure categorization, lookup validation, and comprehensive reporting")
    
    # Import the enhanced validation functions
    try:
        from ui_components.transform_operations import (
            categorize_transform_results,
            display_transform_results_preview,
            save_transform_results,
            clean_dataframe_for_salesforce,
            validate_json_compliance
        )
    except ImportError as e:
        st.error(f"❌ Could not import enhanced validation functions: {e}")
        st.info("Please ensure transform_operations.py is properly installed.")
        return
    
    # Import Data Hub integration functions
    try:
        from ui_components.data_hub.integration import (
            has_data,
            select_dataset_from_hub
        )
    except ImportError as e:
        st.error(f"❌ Could not import Data Hub integration functions: {e}")
        st.info("Please ensure the Data Hub module is properly installed.")
        return
    
    # Step 1: Data Source Selection
    st.write("#### 📁 Step 1: Data Source")
    
    # Initialize session state for enhanced validation data (PERSISTENCE FIX)
    if 'enhanced_validation_data' not in st.session_state:
        st.session_state.enhanced_validation_data = None
    if 'enhanced_validation_source' not in st.session_state:
        st.session_state.enhanced_validation_source = None
    if 'enhanced_validation_object' not in st.session_state:
        st.session_state.enhanced_validation_object = None
    
    data_source = "none"
    data_hub_available = has_data()
    
    source_choice = _flow_source_radio(
        "📊 **Data Source:**",
        ["Use Data Hub", "Upload File", "SQL Server", "Oracle"],
        key="enhanced_validation_source_choice",
        horizontal=True
    )

    if source_choice != FLOW_SOURCE_OPTION and _is_any_flow_origin(st.session_state.enhanced_validation_source):
        # Another source was picked: stop validating the Step 1 dataset (the branches below
        # fall back to previously loaded data, which must not be the Step 1 data).
        st.session_state.enhanced_validation_data = None
        st.session_state.enhanced_validation_source = None
        st.session_state.enhanced_validation_object = None

    if source_choice == FLOW_SOURCE_OPTION:
        # The Step 1 dataset is loaded automatically (no extra Load click).
        if (not _is_flow_origin(st.session_state.enhanced_validation_source)
                or st.session_state.enhanced_validation_data is None):
            st.session_state.enhanced_validation_data = _flow_df()
            st.session_state.enhanced_validation_source = _flow_origin()
            st.session_state.enhanced_validation_object = step_flow.get_flow_object()
        _show_flow_dataset_in_use()
        data_source = st.session_state.enhanced_validation_source
        df_original = st.session_state.enhanced_validation_data
        if df_original is None:
            return

    elif source_choice == "Use Data Hub":
        hub_df = select_dataset_from_hub("enhanced_validation")
        if hub_df is not None:
            if st.button("✅ Load Selected Dataset", use_container_width=True, key="enhanced_load_from_hub"):
                st.session_state.enhanced_validation_data = hub_df
                st.session_state.enhanced_validation_source = "hub"
                st.session_state.enhanced_validation_object = None
                st.success(f"✅ **Data loaded from Hub!** {len(hub_df)} rows, {len(hub_df.columns)} columns")
                with st.expander("📊 Data Preview", expanded=False):
                    st.dataframe(hub_df.head(10), use_container_width=True)

        # Use data from session state if previously loaded
        if st.session_state.enhanced_validation_data is not None:
            data_source = st.session_state.enhanced_validation_source
            df_original = st.session_state.enhanced_validation_data
        else:
            return

    elif source_choice == "📁 File Library":
        picked_df, picked_name = (show_file_picker_inline(
            "enhanced_validation",
            org_name=st.session_state.get('current_org'),
        ) if show_file_picker_inline else (None, None))
        if picked_df is not None:
            st.session_state.enhanced_validation_data = picked_df
            st.session_state.enhanced_validation_source = "upload"
            st.session_state.enhanced_validation_object = None
            df_original = picked_df
            data_source = "upload"
        elif st.session_state.enhanced_validation_data is not None:
            data_source = st.session_state.enhanced_validation_source
            df_original = st.session_state.enhanced_validation_data
        else:
            return

    elif source_choice == "SQL Server":
        sql_data = _load_validation_data_from_sql("enhanced_validation")
        if sql_data is not None:
            st.session_state.enhanced_validation_data = sql_data
            st.session_state.enhanced_validation_source = "sql"
            st.session_state.enhanced_validation_object = None
            df_original = sql_data
            data_source = "sql"
        elif st.session_state.enhanced_validation_data is not None and st.session_state.enhanced_validation_source == "sql":
            data_source = "sql"
            df_original = st.session_state.enhanced_validation_data
        else:
            return

    elif source_choice == "Oracle":
        oracle_data = _load_validation_data_from_oracle("enhanced_validation")
        if oracle_data is not None:
            st.session_state.enhanced_validation_data = oracle_data
            st.session_state.enhanced_validation_source = "oracle"
            st.session_state.enhanced_validation_object = None
            df_original = oracle_data
            data_source = "oracle"
        elif st.session_state.enhanced_validation_data is not None and st.session_state.enhanced_validation_source == "oracle":
            data_source = "oracle"
            df_original = st.session_state.enhanced_validation_data
        else:
            return

    else:
        data_source = "upload"
        if st.session_state.enhanced_validation_data is not None and st.session_state.enhanced_validation_source == "upload":
            data_source = "upload"
            df_original = st.session_state.enhanced_validation_data

    # File upload (if user chooses Upload File and no data yet)
    if source_choice == "Upload File" and (data_source == "upload" or st.session_state.enhanced_validation_data is None):
        st.write("**Upload a File:**")
        uploaded_file = st.file_uploader(
            "Choose a CSV, Excel, or PSV file",
            type=['csv', 'xlsx', 'xls', 'psv'],
            key="enhanced_validation_upload",
            help="Upload the data you want to validate and transform. Supported formats: CSV, Excel, PSV (Pipe-Separated Values)"
        )
        
        if not uploaded_file:
            if data_source == "upload":
                st.info("👆 Please upload a data file to begin enhanced validation or use Data Hub")
            return
        
        # Load data
        try:
            if uploaded_file.name.endswith('.csv'):
                loaded_data = pd.read_csv(uploaded_file, dtype=str)
            elif uploaded_file.name.endswith('.psv'):
                loaded_data = pd.read_csv(uploaded_file, sep='|', dtype=str)
            else:
                loaded_data = pd.read_excel(uploaded_file, dtype=str)
            
            if loaded_data.empty:
                st.error("❌ The uploaded file is empty. Please upload a file with data.")
                return

            # Store in session state (PERSISTENCE FIX)
            st.session_state.enhanced_validation_data = loaded_data
            st.session_state.enhanced_validation_source = "upload"
            st.session_state.enhanced_validation_object = None  # Reset object selection
            df_original = loaded_data
            data_source = "upload"

            # Auto-register in File Library
            if register_source_file:
                register_source_file(
                    uploaded_file, uploaded_file.name,
                    org_name=st.session_state.get('current_org', 'unknown'),
                    object_name='',
                    row_count=len(loaded_data), col_count=len(loaded_data.columns),
                )

            st.success(f"✅ **Data loaded successfully!** {len(loaded_data)} rows, {len(loaded_data.columns)} columns")

            # Show data preview
            with st.expander("📊 Data Preview", expanded=False):
                st.dataframe(loaded_data.head(10), use_container_width=True)
                
        except Exception as e:
            st.error(f"❌ Error loading file: {str(e)}")
            return
    
    # Retrieve data from session state
    df_original = st.session_state.enhanced_validation_data
    
    # If we don't have data at this point, stop
    if df_original is None:
        st.error("❌ No data available to validate")
        return
    
    # Step 2: Object Selection
    st.write("#### 🎯 Step 2: Select Target Salesforce Object")
    
    # Get Salesforce objects
    try:
        from ui_components.utils import get_salesforce_objects
        objects = get_salesforce_objects(sf_conn, filter_custom=False)
        
        if not objects:
            st.error("❌ No Salesforce objects found")
            return
        
        # Retrieve selected object from session state if available. The widget is seeded
        # before it is drawn (index= is ignored once the key has state).
        object_options = [""] + objects
        _seed_flow_object("enhanced_validation_object_selectbox", object_options)
        current_selected = st.session_state.enhanced_validation_object
        if "enhanced_validation_object_selectbox" not in st.session_state and current_selected in objects:
            st.session_state.enhanced_validation_object_selectbox = current_selected

        selected_object = st.selectbox(
            "Select Salesforce Object",
            options=object_options,
            key="enhanced_validation_object_selectbox",
            on_change=lambda: _mark_val_tab(1),
            disabled=_flow_object_locked(object_options),
            help="The Step 1 target object (change it in Step 1)"
        )
        _remember_flow_widget("enhanced_validation_object_selectbox", selected_object)
        
        # Store in session state (PERSISTENCE FIX)
        if selected_object:
            st.session_state.enhanced_validation_object = selected_object
        else:
            st.session_state.enhanced_validation_object = None
        
        if not selected_object:
            st.info("👆 Please select a Salesforce object to continue")
            return
            
    except Exception as e:
        st.error(f"❌ Error retrieving Salesforce objects: {str(e)}")
        return
    
    # Step 3: Field Mapping Configuration
    st.write("#### 🔗 Step 3: Field Mapping Configuration")
    st.info("📋 Map your CSV columns to Salesforce fields for accurate validation and lookup resolution")
    
    # Get Salesforce object fields
    field_mappings = {}
    try:
        from ui_components.utils import get_object_description
        from ui_components.field_mapping_ui import auto_load_mapping
        sf_object_info = get_object_description(sf_conn, selected_object)

        if sf_object_info and 'fields' in sf_object_info:
            # Get ALL relevant Salesforce fields (not just updateable ones)
            # Include all fields for validation - we're checking data, not updating
            # Exclude only system attributes fields
            all_sf_fields = [field for field in sf_object_info['fields']
                            if not field.get('name', '').startswith('attributes')]

            csv_columns = list(df_original.columns)
            
            # Initialize field mappings in session state
            mapping_key = f"enhanced_field_mappings_{selected_object}"
            if mapping_key not in st.session_state:
                st.session_state[mapping_key] = {}
            
            # Try to auto-load saved mappings
            auto_loaded_mappings = auto_load_mapping(
                org_name=st.session_state.get('current_org', 'unknown'),
                object_name=selected_object,
                csv_columns=csv_columns,
                auto_apply=False,
                key_suffix='_enhanced_val'
            )
            
            # Selectbox keys of the grid below (one per column)
            mapping_widget_prefix = f"mapping_{selected_object}_"
            _seed_grid_from_flow(mapping_key, mapping_widget_prefix, 'enhanced', csv_columns)
            if auto_loaded_mappings:
                # 'Use Saved Mappings' / 'Partially Apply' was clicked in this run: apply it and drop
                # the grid's widget state so the grid shows the applied mapping.
                st.session_state[mapping_key] = {
                    col: sf_field for col, sf_field in auto_loaded_mappings.items() if col in csv_columns
                }
                _clear_session_keys(mapping_widget_prefix)

            _correct_known_validation_mappings(st.session_state[mapping_key], all_sf_fields)

            # Use the shared conservative mapper for the same behavior as other validation tabs.
            auto_suggestions = _suggest_validation_field_mappings(csv_columns, all_sf_fields)

            # Display field mapping interface
            st.write("**Configure Field Mappings:**")
            st.caption(f"{len(all_sf_fields)} fields available on {selected_object}")

            # Option to use auto-suggestions
            if auto_suggestions:
                if st.button("🤖 Apply Auto-Suggestions", help="Apply automatically detected field mappings",
                             key="enhanced_apply_suggestions"):
                    st.session_state[mapping_key].update(auto_suggestions)
                    _clear_session_keys(mapping_widget_prefix)
                    st.success(f"✅ Applied {len(auto_suggestions)} auto-suggestions")
            
            # Manual mapping interface
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.write("**CSV Columns**")
            with col2:
                st.write("**Salesforce Fields**")
            
            sf_field_options = [""] + [f['name'] for f in all_sf_fields]
            
            for i, csv_column in enumerate(csv_columns):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    # Show CSV column with sample data
                    sample_values = df_original[csv_column].dropna().head(3).tolist()
                    sample_display = ", ".join([str(v)[:20] + "..." if len(str(v)) > 20 else str(v) for v in sample_values])
                    st.write(f"**{csv_column}**")
                    if sample_display:
                        st.caption(f"Sample: {sample_display}")
                
                with col2:
                    # Salesforce field selection with auto-suggestion as default
                    current_mapping = st.session_state[mapping_key].get(csv_column, "")
                    if csv_column not in st.session_state[mapping_key] and csv_column in auto_suggestions:
                        current_mapping = auto_suggestions[csv_column]

                    # The key includes the column so another dataset's choice is not reused; the
                    # widget is seeded before it is drawn (index= is ignored once the key has state).
                    mapping_widget_key = f"{mapping_widget_prefix}{i}_{csv_column}"
                    if st.session_state.get(mapping_widget_key) not in sf_field_options:
                        st.session_state[mapping_widget_key] = current_mapping if current_mapping in sf_field_options else ""
                    selected_sf_field = st.selectbox(
                        "Map to Salesforce Field",
                        options=sf_field_options,
                        key=mapping_widget_key,
                        label_visibility="collapsed",
                        help=f"Select Salesforce field for {csv_column}"
                    )
                    
                    if selected_sf_field:
                        st.session_state[mapping_key][csv_column] = selected_sf_field
                        # Show field type info
                        sf_field_info = next((f for f in all_sf_fields if f['name'] == selected_sf_field), None)
                        if sf_field_info:
                            field_type = sf_field_info.get('type', 'unknown')
                            if field_type == 'reference':
                                st.success("🔗 Lookup Field")
                            elif field_type in ['picklist', 'multipicklist']:
                                st.success("📋 Picklist Field")
                            else:
                                st.info(f"📝 {field_type.title()}")
                    else:
                        st.session_state[mapping_key][csv_column] = ""   # explicitly not mapped

            _publish_grid_to_flow(mapping_key, 'enhanced')
            
            # Store final mappings (without the explicitly unmapped columns)
            field_mappings = {k: v for k, v in st.session_state.get(mapping_key, {}).items() if v}
            
            # Show mapping summary
            if field_mappings:
                with st.expander("📊 Field Mapping Summary", expanded=False):
                    mapping_df = pd.DataFrame([
                        {"CSV Column": csv_col, "Salesforce Field": sf_field}
                        for csv_col, sf_field in field_mappings.items()
                    ])
                    st.dataframe(mapping_df, use_container_width=True)
                    
                    # Count different field types
                    lookup_count = 0
                    picklist_count = 0
                    for csv_col, sf_field in field_mappings.items():
                        sf_field_info = next((f for f in all_sf_fields if f['name'] == sf_field), None)
                        if sf_field_info:
                            if sf_field_info.get('type') == 'reference':
                                lookup_count += 1
                            elif sf_field_info.get('type') in ['picklist', 'multipicklist']:
                                picklist_count += 1
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Mappings", len(field_mappings))
                    with col2:
                        st.metric("Lookup Fields", lookup_count)
                    with col3:
                        st.metric("Picklist Fields", picklist_count)
                
                # Add save mapping option
                from ui_components.field_mapping_ui import show_mapping_save_options
                show_mapping_save_options(
                    org_name=st.session_state.get('current_org', 'unknown'),
                    object_name=selected_object,
                    field_mappings=field_mappings,
                    csv_columns=csv_columns,
                    validation_type='enhanced'
                )
            
            else:
                st.warning("⚠️ No field mappings configured. Lookup resolution may not work properly.")
                st.info("💡 Configure at least one field mapping for lookup/picklist validation")
        
        else:
            st.error(f"❌ Could not retrieve field information for {selected_object}")
            return
            
    except Exception as e:
        st.error(f"❌ Error setting up field mapping: {str(e)}")
        st.info("Proceeding without field mapping...")
        field_mappings = {}
    
    # Step 4: Matching Strategy Selection
    st.write("#### 🎯 Step 4: External ID Matching Strategy")
    st.info("""
    Select how to identify records for validation:
    - **External ID**: Use a single external ID field
    - **Unique Field**: Use a unique field as identifier  
    - **Field Combination**: Combine multiple fields (AND condition)
    - **Field Concatenation**: Concatenate fields with separator
    """)
    
    # Get object metadata for strategy selection
    try:
        object_metadata = get_object_description(sf_conn, selected_object) or {'fields': []}
        all_fields_meta = {f['name']: f for f in object_metadata['fields']}
        
        # Identify External ID fields
        external_id_fields = [f['name'] for f in object_metadata['fields'] if f.get('externalId', False)]
        # Identify Unique fields
        unique_fields = [f['name'] for f in object_metadata['fields'] if f.get('unique', False)]
        # All field names
        all_field_names = [f['name'] for f in object_metadata['fields']]
        
        # Strategy selection
        matching_strategy = st.radio(
            "Select Matching Strategy:",
            options=[
                "external_id - External ID Field",
                "unique_field - Unique Field",
                "field_combination - Multiple Fields (AND)",
                "field_concatenation - Concatenated Fields"
            ],
            key="enhanced_validation_strategy",
            help="Choose how to identify records for duplicate validation"
        )
        
        strategy_key = matching_strategy.split(" - ")[0]
        selected_match_fields = []
        match_separator = "_"
        
        if strategy_key == "external_id":
            if external_id_fields:
                selected_field = st.selectbox(
                    "Select External ID Field:",
                    options=external_id_fields,
                    key="enhanced_external_id_field"
                )
                selected_match_fields = [selected_field]
                st.success(f"✅ Using External ID: **{selected_field}**")
            else:
                st.warning("⚠️ No External ID fields found in this object")
                selected_match_fields = []
        
        elif strategy_key == "unique_field":
            if unique_fields:
                selected_field = st.selectbox(
                    "Select Unique Field:",
                    options=unique_fields,
                    key="enhanced_unique_field"
                )
                selected_match_fields = [selected_field]
                st.success(f"✅ Using Unique Field: **{selected_field}**")
            else:
                st.warning("⚠️ No Unique fields found in this object")
                selected_match_fields = []
        
        elif strategy_key == "field_combination":
            selected_fields = st.multiselect(
                "Select Fields to Combine (AND condition):",
                options=all_field_names,
                key="enhanced_combo_fields",
                help="All selected fields must match to identify a record"
            )
            selected_match_fields = selected_fields
            if selected_fields:
                st.success(f"✅ Using combination: **{', '.join(selected_fields)}**")
            else:
                st.info("💡 Select at least one field for combination matching")
        
        elif strategy_key == "field_concatenation":
            selected_fields = st.multiselect(
                "Select Fields to Concatenate:",
                options=all_field_names,
                key="enhanced_concat_fields"
            )
            
            if selected_fields:
                match_separator = st.text_input(
                    "Concatenation Separator:",
                    value="_",
                    key="enhanced_concat_sep",
                    max_chars=5
                )
                selected_match_fields = selected_fields
                concat_example = match_separator.join([f"<{f}>" for f in selected_fields])
                st.success(f"✅ Using concatenation: **{concat_example}**")
            else:
                st.info("💡 Select at least one field for concatenation")
        
        # Store strategy in session state for use in lookup resolution
        st.session_state.enhanced_match_strategy = strategy_key
        st.session_state.enhanced_match_fields = selected_match_fields
        st.session_state.enhanced_match_separator = match_separator
        
    except Exception as e:
        st.warning(f"⚠️ Could not load matching strategy options: {str(e)}")
        st.session_state.enhanced_match_strategy = "external_id"
        st.session_state.enhanced_match_fields = []
        st.session_state.enhanced_match_separator = "_"
    
    st.divider()
    
    # Step 5: Lookup Resolution (Optimized with Bulk Caching)
    st.write("#### 🔗 Step 5: Lookup Field Resolution (Optimized)")
    
    if 'enhanced_enable_lookup_resolution' not in st.session_state:
        st.session_state.enhanced_enable_lookup_resolution = st.session_state.get(
            '_enhanced_enable_lookup_resolution_saved', True)
    enable_lookup_resolution = st.checkbox(
        "Enable Lookup Field Resolution",
        key="enhanced_enable_lookup_resolution",
        help="Automatically resolve lookup fields to Salesforce record IDs using optimized bulk caching"
    )
    st.session_state._enhanced_enable_lookup_resolution_saved = enable_lookup_resolution
    
    df_transformed = df_original.copy()
    lookup_fields = {}
    lookup_count_summary = {}
    unresolved_records_summary = {}
    
    if enable_lookup_resolution:
        try:
            from ui_components.data_operations import (
                resolve_lookup_fields_with_config,
                resolve_lookup_fields_with_mapping,
                resolve_lookup_fields
            )
            
            # Detect lookup fields for configuration UI
            sf_object_desc = get_object_description(sf_conn, selected_object) or {'fields': []}
            
            # Build reverse mapping: SF field name → CSV column name
            active_mappings = {}
            if field_mappings:
                active_mappings = {v: k for k, v in field_mappings.items()
                                  if v and v != "-- Skip Field --" and v != "RecordTypeId"}
            
            detected_lookup_fields = {}
            system_lookups = {'OwnerId', 'CreatedById', 'LastModifiedById', 'RecordTypeId', 'MasterRecordId'}
            
            for field in sf_object_desc['fields']:
                field_name = field['name']
                if field['type'] != 'reference' or field_name in system_lookups:
                    continue
                referenced_objects = field.get('referenceTo', [])
                if not referenced_objects:
                    continue
                
                csv_col = None
                if field_name in df_original.columns:
                    csv_col = field_name
                elif field_name in active_mappings:
                    csv_col = active_mappings[field_name]
                    if csv_col not in df_original.columns:
                        csv_col = None
                
                if csv_col is None:
                    continue
                
                # Skip columns that already look like Salesforce IDs
                sample_vals = df_original[csv_col].dropna().head(5).astype(str).tolist()
                all_look_like_ids = all(
                    (len(v) in [15, 18] and v[:3].isalnum())
                    for v in sample_vals if v.strip()
                ) if sample_vals else False
                
                if all_look_like_ids:
                    continue
                
                detected_lookup_fields[field_name] = {
                    'csv_column': csv_col,
                    'referenced_object': referenced_objects[0],
                    'label': field.get('label', field_name)
                }
            
            if detected_lookup_fields:
                st.success(f"✅ Found {len(detected_lookup_fields)} lookup field(s) that need resolution")
                st.session_state['enhanced_unresolved_lookup_indices'] = []
                
                # Lookup configuration UI — same as Data Loading
                lookup_configs = {}
                config_key = f"enhanced_lookup_configs_{selected_object}"
                if config_key not in st.session_state:
                    st.session_state[config_key] = {}
                
                for sf_field_name, info in detected_lookup_fields.items():
                    parent_obj = info['referenced_object']
                    csv_col = info['csv_column']
                    
                    with st.expander(f"🔗 {csv_col} → {parent_obj} ({info['label']})", expanded=False):
                        # Get parent object fields for strategy selection
                        try:
                            parent_desc = get_object_description(sf_conn, parent_obj) or {'fields': []}
                            parent_field_names = [f['name'] for f in parent_desc['fields']]
                            external_id_fields = [f['name'] for f in parent_desc['fields'] if f.get('externalId', False)]
                            name_fields = [f['name'] for f in parent_desc['fields'] if f['name'] == 'Name' or f.get('nameField', False)]
                        except Exception:
                            parent_field_names = ['Name', 'Id']
                            external_id_fields = []
                            name_fields = ['Name']
                        
                        strategy = st.radio(
                            f"Matching strategy for {csv_col}:",
                            options=["external_id", "unique_field", "field_combination"],
                            format_func=lambda x: {"external_id": "External ID Field", "unique_field": "Unique/Name Field", "field_combination": "Field Combination"}[x],
                            key=f"enhanced_lookup_strategy_{sf_field_name}",
                            horizontal=True
                        )
                        
                        match_fields = []
                        if strategy == "external_id":
                            if external_id_fields:
                                sel = st.selectbox(f"External ID field on {parent_obj}:", external_id_fields, key=f"enhanced_ext_id_{sf_field_name}")
                                match_fields = [sel]
                            else:
                                st.warning(f"No External ID fields found on {parent_obj}. Use 'Unique/Name Field' instead.")
                        elif strategy == "unique_field":
                            default_opts = name_fields + [f for f in parent_field_names if f not in name_fields]
                            sel = st.selectbox(f"Match field on {parent_obj}:", default_opts, key=f"enhanced_uniq_{sf_field_name}")
                            match_fields = [sel]
                        elif strategy == "field_combination":
                            sel = st.multiselect(f"Match fields on {parent_obj}:", parent_field_names, default=name_fields[:1], key=f"enhanced_combo_{sf_field_name}")
                            match_fields = sel
                        
                        if match_fields:
                            lookup_configs[sf_field_name] = {
                                'parent_object': parent_obj,
                                'csv_column': csv_col,
                                'match_strategy': strategy,
                                'match_fields': match_fields
                            }
                            st.success(f"✅ Will match on: {', '.join(match_fields)}")
                
                st.session_state[config_key] = lookup_configs
                
                # Run resolution
                if lookup_configs:
                    # Resolution queries Salesforce: reuse the last result while the data,
                    # object, lookup settings and mapping are unchanged (it used to run on
                    # every rerun of the Step 2 page, whatever widget was touched).
                    signature = _lookup_resolution_signature(df_original, selected_object,
                                                             lookup_configs, field_mappings)
                    cached = st.session_state.get('_enhanced_lookup_cache')
                    if cached and cached.get('signature') == signature:
                        df_transformed = cached['df'].copy()
                        lookup_fields = dict(cached['lookup_fields'])
                        lookup_count_summary = dict(cached['lookup_count_summary'])
                        st.session_state.enhanced_unresolved_lookup_indices = list(cached['unresolved'])
                        st.caption(f"✅ Lookups resolved for {len(lookup_fields)} field(s) "
                                   "(re-runs when the data, mapping or lookup settings change).")
                    else:
                        with st.spinner("🔄 Resolving lookup fields..."):
                            lookup_result = resolve_lookup_fields_with_config(
                                sf_conn, df_transformed, selected_object, lookup_configs, field_mappings,
                                return_stats=True,
                                unresolved_indices_session_key='enhanced_unresolved_lookup_indices'
                            )

                            if isinstance(lookup_result, tuple):
                                df_transformed, lookup_fields, lookup_count_summary = lookup_result
                            else:
                                df_transformed = lookup_result
                        st.session_state._enhanced_lookup_cache = {
                            'signature': signature, 'df': df_transformed,
                            'lookup_fields': dict(lookup_fields or {}),
                            'lookup_count_summary': dict(lookup_count_summary or {}),
                            'unresolved': list(st.session_state.get('enhanced_unresolved_lookup_indices') or []),
                        }
                else:
                    st.info("💡 Configure at least one lookup field above to enable resolution")
            
            elif field_mappings:
                st.info("📝 No lookup fields detected in your field mappings — skipping resolution")
            else:
                st.info("📝 No field mappings configured — skipping lookup resolution")
                
        except ImportError as ie:
            st.warning(f"⚠️ Could not import lookup resolution functions: {str(ie)}")
            st.info("📝 Continuing with original data...")
        except Exception as e:
            st.warning(f"⚠️ Lookup resolution encountered an error: {str(e)}")
            st.info("📝 Continuing with original data...")
            df_transformed = df_original.copy()
            lookup_fields = {}
            lookup_count_summary = {}
    else:
        st.info("📝 Lookup resolution skipped — using original data")
    
    # Step 6: Enhanced Transform Validation
    st.write("#### ⚡ Step 6: Enhanced Transform Validation")
    
    if st.button("🚀 Start Enhanced Validation", type="primary", use_container_width=True,
                 key="enhanced_start_validation"):
        try:
            with st.spinner("🔍 Analyzing data with enhanced validation..."):
                # Categorize transform results
                df_success, df_failure, transform_summary = categorize_transform_results(
                    df_original, df_transformed, lookup_fields, selected_object, sf_conn,
                    field_mappings=st.session_state.get(f"enhanced_field_mappings_{selected_object}", {}) or {}
                )
                
                # Add unresolved lookup records to failure category
                unresolved_indices = st.session_state.get('enhanced_unresolved_lookup_indices', [])
                if unresolved_indices:
                    valid_unresolved_indices = [idx for idx in unresolved_indices if idx in df_original.index]
                    df_unresolved = df_original.loc[valid_unresolved_indices].copy()
                    df_unresolved['_validation_failure_reason'] = 'Unresolved Lookup - No matching parent record found'
                    df_failure = pd.concat([df_failure, df_unresolved], ignore_index=False)
                    
                    # Update summary to include unresolved records
                    total_records = len(df_original)
                    total_success = len(df_success)
                    total_failure = len(df_failure)
                    transform_summary['total_count'] = total_records
                    transform_summary['success_count'] = total_success
                    transform_summary['failure_count'] = total_failure
                    transform_summary['success_percentage'] = (total_success / total_records * 100) if total_records > 0 else 0
                    transform_summary['failure_percentage'] = (total_failure / total_records * 100) if total_records > 0 else 0

            # Guided flow: publish the result (this is what unlocks Step 3). df_success keeps the
            # source column names, with configured lookup columns replaced by Salesforce IDs.
            enhanced_mappings = st.session_state.get(f"enhanced_field_mappings_{selected_object}", {}) or {}
            enhanced_lookup_configs = st.session_state.get(f"enhanced_lookup_configs_{selected_object}", {}) or {}
            # Lookups count as resolved only if every mapped reference field of the valid rows
            # really holds Salesforce IDs (resolution may be disabled, unconfigured, or skipped
            # for system lookups such as OwnerId / RecordTypeId).
            enhanced_description = get_object_description(sf_conn, selected_object)
            enhanced_lookups_resolved = _lookups_resolved(
                df_success, enhanced_mappings, (enhanced_description or {}).get('fields'), sf_conn)
            _publish_step2_result(
                'Enhanced Validation', selected_object, df_success, df_failure, enhanced_mappings,
                used_flow_dataset=_is_flow_origin(st.session_state.get('enhanced_validation_source')),
                sf_conn=sf_conn, lookups_resolved=enhanced_lookups_resolved,
                lookup_configs=enhanced_lookup_configs,
                match={'strategy': st.session_state.get('enhanced_match_strategy'),
                       'fields': list(st.session_state.get('enhanced_match_fields') or []),
                       'separator': st.session_state.get('enhanced_match_separator', '_')},
                summary={k: v for k, v in transform_summary.items()
                         if k in ('success_count', 'failure_count', 'total_count', 'success_percentage',
                                  'failure_percentage', 'lookup_failures', 'picklist_failures',
                                  'unique_failures', 'required_failures')},
            )

            # Display results preview
            display_transform_results_preview(df_success, df_failure, selected_object, transform_summary)
            
            # === ENHANCED DOWNLOAD SECTION FOR VALID/INVALID RECORDS ===
            st.write("#### 📊 Step 7: Validation Results Summary")
            
            # Display key metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("✅ Valid Records", len(df_success), delta=f"{transform_summary['success_percentage']:.1f}%")
            with col2:
                st.metric("❌ Invalid Records", len(df_failure), delta=f"{transform_summary['failure_percentage']:.1f}%")
            with col3:
                st.metric("📊 Total Processed", transform_summary['total_count'])
            with col4:
                st.metric("💾 Data Quality", f"{transform_summary['success_percentage']:.1f}%")
            
            st.divider()
            
            # IMPORTANT: Download Valid Records for Data Loading
            st.write("#### 📥 Download Records (optional)")
            st.info("""
            ✅ **Valid Records (Ready for Upload)**
            - These records have passed all validation checks
            - Step 3 (Data Operations) loads the valid rows directly; the files are for your records
            - Lookup resolution has already been completed
            """)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if not df_success.empty:
                    success_csv = df_success.to_csv(index=False)
                    st.download_button(
                        "✅ Download Valid Records (CSV)",
                        success_csv,
                        get_timestamped_filename(f"{selected_object}_VALID_RECORDS"),
                        "text/csv",
                        key="download_valid_csv",
                        help="Download only records that passed validation - ready for data loading", on_click='ignore'
                    )
                else:
                    st.warning("No valid records to download")
            
            with col2:
                if not df_success.empty:
                    try:
                        from io import BytesIO
                        excel_buffer = BytesIO()
                        df_success.to_excel(excel_buffer, index=False, engine='openpyxl')
                        excel_buffer.seek(0)
                        st.download_button(
                            "✅ Download Valid Records (Excel)",
                            excel_buffer.getvalue(),
                            get_timestamped_filename(f"{selected_object}_VALID_RECORDS", "xlsx"),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_valid_excel",
                            help="Excel format for valid records", on_click='ignore'
                        )
                    except Exception as e:
                        st.warning(f"⚠️ Excel export not available: {str(e)}")
            
            with col3:
                st.info(f"📈 **{len(df_success)} valid records ready**")
            
            st.divider()
            
            # Invalid Records for Review
            if not df_failure.empty:
                st.write("#### ❌ Download Invalid Records (For Review/Correction)")
                st.warning("""
                **Invalid Records (Failed Validation)**
                - Review these records to understand why validation failed
                - Fix the issues and re-upload in Enhanced Validation
                - Or fix them and load them again in Step 1 (Source/Target Information)
                """)
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    failure_csv = df_failure.to_csv(index=False)
                    st.download_button(
                        "❌ Download Invalid Records (CSV)",
                        failure_csv,
                        get_timestamped_filename(f"{selected_object}_INVALID_RECORDS"),
                        "text/csv",
                        key="download_invalid_csv",
                        help="Download records that failed validation for review and correction", on_click='ignore'
                    )
                
                with col2:
                    # Show failure reasons
                    if 'validation_error' in df_failure.columns:
                        error_summary = df_failure['validation_error'].value_counts()
                        st.subheader("🔍 Top Failure Reasons")
                        for error, count in error_summary.head(5).items():
                            st.write(f"• {error}: **{count}** records")
                
                with col3:
                    st.info(f"📉 **{len(df_failure)} invalid records**")
            
            st.divider()
            
            # Get organization name for folder organization
            try:
                org_info = sf_conn.query("SELECT Name, Id FROM Organization LIMIT 1")
                if org_info['records']:
                    org_name = org_info['records'][0]['Name'].replace(' ', '_')
                else:
                    org_name = 'Unknown_Org'
            except:
                org_name = 'Unknown_Org'
            
            # Auto-save results with new file management system
            with st.spinner("Saving enhanced validation results..."):
                folder_path = get_validation_folder_path('Enhanced_Validation', org_name, selected_object)
                
                # Save success data
                if not df_success.empty:
                    success_filename = get_timestamped_filename(f"{selected_object}_enhanced_validation_success")
                    save_validation_results_to_file(df_success, folder_path, success_filename)
                
                # Save failure data
                if not df_failure.empty:
                    failure_filename = get_timestamped_filename(f"{selected_object}_enhanced_validation_failure")
                    save_validation_results_to_file(df_failure, folder_path, failure_filename)
                
                # Save all transformed data
                all_data_filename = get_timestamped_filename(f"{selected_object}_all_transformed_data")
                df_clean = clean_dataframe_for_salesforce(df_transformed)
                save_validation_results_to_file(df_clean, folder_path, all_data_filename)
                
                # Save summary report
                summary_filename = get_timestamped_filename(f"{selected_object}_validation_summary", "txt")
                summary_path = os.path.join(folder_path, summary_filename)
                
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write("ENHANCED VALIDATION SUMMARY REPORT\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Salesforce Org: {org_name}\n")
                    f.write(f"Target Object: {selected_object}\n\n")
                    
                    f.write("OVERALL STATISTICS:\n")
                    f.write(f"Total Records Processed: {transform_summary['total_count']}\n")
                    f.write(f"Transform Success: {transform_summary['success_count']} ({transform_summary['success_percentage']:.1f}%)\n")
                    f.write(f"Transform Failure: {transform_summary['failure_count']} ({transform_summary['failure_percentage']:.1f}%)\n\n")
                    
                    if transform_summary['failure_count'] > 0:
                        f.write("FAILURE BREAKDOWN:\n")
                        f.write(f"- Lookup transformation failures: {transform_summary.get('lookup_failures', 0)}\n")
                        f.write(f"- Picklist validation failures: {transform_summary.get('picklist_failures', 0)}\n")
                        f.write(f"- Unique field constraint failures: {transform_summary.get('unique_failures', 0)}\n\n")
                    
                    if lookup_fields:
                        f.write("LOOKUP FIELDS PROCESSED:\n")
                        for lookup_field, related_object in lookup_fields.items():
                            lookup_count = lookup_count_summary.get(lookup_field, 0) if lookup_count_summary else 0
                            f.write(f"- {lookup_field} -> {related_object} ({lookup_count} values resolved)\n")
                
                # Display file location info
                st.balloons()
                display_file_location_info(folder_path)
            
            # Quick download options
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if not df_success.empty:
                    success_csv = df_success.to_csv(index=False)
                    st.download_button(
                        "📥 Quick Download Success",
                        success_csv,
                        get_timestamped_filename(f"{selected_object}_validation_success"),
                        "text/csv",
                        help="Quick download - Also saved to folder above", on_click='ignore'
                    )
            
            with col2:
                if not df_failure.empty:
                    failure_csv = df_failure.to_csv(index=False)
                    st.download_button(
                        "📥 Quick Download Failure",
                        failure_csv,
                        get_timestamped_filename(f"{selected_object}_validation_failure"),
                        "text/csv",
                        help="Quick download - Also saved to folder above", on_click='ignore'
                    )
            
            with col3:
                # Download all transformed data
                if not df_transformed.empty:
                    all_data_csv = df_clean.to_csv(index=False)
                    st.download_button(
                        "📥 Quick Download All Data",
                        all_data_csv,
                        get_timestamped_filename(f"{selected_object}_all_transformed"),
                        "text/csv",
                        help="Quick download - Also saved to folder above", on_click='ignore'
                    )
            
        except Exception as e:
            st.error(f"❌ Enhanced validation failed: {str(e)}")
            st.exception(e)

        
        # Quick action buttons. They are drawn inside the Start button's branch, which is False on
        # the rerun their click causes, so they only work as on_click callbacks.
        col1, col2 = st.columns([1, 1])
        with col1:
            st.button("🚀 Go to Step 3: Data Operations", key="goto_data_loading",
                      on_click=request_page, args=(STEP3_PAGE,),
                      disabled=not step_flow.step2_done(),
                      help="Available once this validation of the Step 1 dataset has valid rows")

        with col2:
            st.button("🔄 Start New Transformation", key="restart_transformation",
                      on_click=_reset_enhanced_validation_state)
    
    # Help section
    with st.expander("❓ Help - Enhanced Validation Features", expanded=False):
        st.markdown("""
        ### 🎯 **Enhanced Validation Features**
        
        **🗂️ Field Mapping Configuration:**
        - Map CSV columns to Salesforce fields for accurate validation
        - Auto-suggestion based on field name similarity
        - Support for lookup, picklist, and standard fields
        - Real-time field type detection and validation
        
        **⚡ Transform Success/Failure Analysis:**
        - Categorizes records based on transformation quality
        - Identifies lookup field resolution issues using field mappings
        - Validates picklist API names against Salesforce metadata
        - Checks unique field constraints within dataset
        
        **🔍 Enhanced Validation Workflow:**
        1. **Data Upload:** Upload CSV/Excel/PSV files
        2. **Object Selection:** Choose target Salesforce object
        3. **Field Mapping:** Map CSV columns to Salesforce fields
        4. **Lookup Resolution:** Resolve lookup fields using mappings
        5. **Transform Validation:** Comprehensive data quality analysis
        6. **Transformation Export:** Export mapped data with Python template
        7. **Import Transformed Data:** Upload and validate transformed data
        8. **Results Export:** Organized success/failure file output
        
        **🔍 Validation Criteria:**
        - Field data types matching Salesforce schema
        - Required field completeness
        - Field length constraints
        - Picklist value validity
        - Lookup field resolution
        - Email and phone format validation
        - Date/datetime format validation
        - Unique field constraints
        """)

def compare_salesforce_objects(source_conn, target_conn, source_org, target_org, source_object, target_object, options):
    """
    Compare two Salesforce objects and generate a detailed comparison report
    """
    try:
        from .utils import get_object_description
        
        # Get object descriptions
        source_desc = get_object_description(source_conn, source_object)
        target_desc = get_object_description(target_conn, target_object)
        
        if not source_desc or not target_desc:
            return {'success': False, 'error': 'Failed to retrieve object descriptions'}
        
        comparison_result = {
            'success': True,
            'source_org': source_org,
            'target_org': target_org,
            'source_object': source_object,
            'target_object': target_object,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'comparisons': {}
        }
        
        # Compare Fields
        if options.get('compare_fields', True):
            field_comparison = compare_fields(source_desc, target_desc)
            comparison_result['comparisons']['fields'] = field_comparison
        
        # Compare Record Types
        if options.get('compare_record_types', True):
            recordtype_comparison = compare_record_types(source_conn, target_conn, source_object, target_object)
            comparison_result['comparisons']['record_types'] = recordtype_comparison
        
        # Compare Picklist Values
        if options.get('compare_picklists', True):
            picklist_comparison = compare_picklist_values(source_desc, target_desc)
            comparison_result['comparisons']['picklists'] = picklist_comparison
        
        # Compare Validation Rules
        if options.get('compare_validation_rules', True):
            validation_comparison = compare_validation_rules(source_conn, target_conn, source_object, target_object)
            comparison_result['comparisons']['validation_rules'] = validation_comparison
        
        # Generate summary statistics
        comparison_result['summary'] = generate_comparison_summary(comparison_result['comparisons'])
        
        return comparison_result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def compare_fields(source_desc, target_desc):
    """Compare field definitions between two objects"""
    source_fields = {f['name']: f for f in source_desc.get('fields', [])}
    target_fields = {f['name']: f for f in target_desc.get('fields', [])}
    
    only_in_source = []
    only_in_target = []
    common_fields = []
    differences = []
    
    # Fields only in source
    for field_name in source_fields:
        if field_name not in target_fields:
            only_in_source.append({
                'name': field_name,
                'type': source_fields[field_name].get('type'),
                'label': source_fields[field_name].get('label')
            })
    
    # Fields only in target
    for field_name in target_fields:
        if field_name not in source_fields:
            only_in_target.append({
                'name': field_name,
                'type': target_fields[field_name].get('type'),
                'label': target_fields[field_name].get('label')
            })
    
    # Common fields - check for differences
    for field_name in source_fields:
        if field_name in target_fields:
            source_field = source_fields[field_name]
            target_field = target_fields[field_name]
            
            field_diff = {
                'name': field_name,
                'label': source_field.get('label'),
                'differences': []
            }
            
            # Compare attributes
            if source_field.get('type') != target_field.get('type'):
                field_diff['differences'].append(f"Type: {source_field.get('type')} → {target_field.get('type')}")
            
            if source_field.get('length') != target_field.get('length'):
                field_diff['differences'].append(f"Length: {source_field.get('length')} → {target_field.get('length')}")
            
            if source_field.get('precision') != target_field.get('precision'):
                field_diff['differences'].append(f"Precision: {source_field.get('precision')} → {target_field.get('precision')}")
            
            if source_field.get('required', False) != target_field.get('required', False):
                field_diff['differences'].append(f"Required: {source_field.get('required')} → {target_field.get('required')}")
            
            if field_diff['differences']:
                differences.append(field_diff)
            else:
                common_fields.append(field_name)
    
    return {
        'only_in_source': only_in_source,
        'only_in_target': only_in_target,
        'common_fields': common_fields,
        'differences': differences,
        'total_source': len(source_fields),
        'total_target': len(target_fields),
        'total_common': len(common_fields),
        'total_differences': len(differences)
    }

def compare_picklist_values(source_desc, target_desc):
    """Compare picklist values between two objects"""
    source_fields = {f['name']: f for f in source_desc.get('fields', []) if f.get('type') in ['picklist', 'multipicklist']}
    target_fields = {f['name']: f for f in target_desc.get('fields', []) if f.get('type') in ['picklist', 'multipicklist']}
    
    picklist_differences = []
    
    for field_name in source_fields:
        if field_name in target_fields:
            source_values = set([v['value'] for v in source_fields[field_name].get('picklistValues', [])])
            target_values = set([v['value'] for v in target_fields[field_name].get('picklistValues', [])])
            
            only_in_source = list(source_values - target_values)
            only_in_target = list(target_values - source_values)
            
            if only_in_source or only_in_target:
                picklist_differences.append({
                    'field': field_name,
                    'label': source_fields[field_name].get('label'),
                    'only_in_source': only_in_source,
                    'only_in_target': only_in_target,
                    'total_source': len(source_values),
                    'total_target': len(target_values)
                })
    
    return {
        'differences': picklist_differences,
        'total_compared': len([f for f in source_fields if f in target_fields])
    }

def compare_record_types(source_conn, target_conn, source_object, target_object):
    """Compare record types between two objects"""
    try:
        # Query record types from source
        source_rt_query = f"SELECT Id, Name, DeveloperName, IsActive FROM RecordType WHERE SObjectType = '{source_object}'"
        source_rts = source_conn.query(source_rt_query).get('records', [])
        
        # Query record types from target
        target_rt_query = f"SELECT Id, Name, DeveloperName, IsActive FROM RecordType WHERE SObjectType = '{target_object}'"
        target_rts = target_conn.query(target_rt_query).get('records', [])
        
        source_rt_names = {rt['DeveloperName']: rt for rt in source_rts}
        target_rt_names = {rt['DeveloperName']: rt for rt in target_rts}
        
        only_in_source = [name for name in source_rt_names if name not in target_rt_names]
        only_in_target = [name for name in target_rt_names if name not in source_rt_names]
        common = [name for name in source_rt_names if name in target_rt_names]
        
        return {
            'only_in_source': only_in_source,
            'only_in_target': only_in_target,
            'common': common,
            'total_source': len(source_rts),
            'total_target': len(target_rts)
        }
    except Exception as e:
        return {'error': str(e)}

def compare_validation_rules(source_conn, target_conn, source_object, target_object):
    """Compare validation rules between two objects"""
    try:
        # Query validation rules from source
        source_vr_query = f"SELECT ValidationName, Active, ErrorDisplayField, ErrorMessage FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{source_object}'"
        source_vrs = source_conn.toolingapi.query(source_vr_query).get('records', [])
        
        # Query validation rules from target
        target_vr_query = f"SELECT ValidationName, Active, ErrorDisplayField, ErrorMessage FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{target_object}'"
        target_vrs = target_conn.toolingapi.query(target_vr_query).get('records', [])
        
        source_vr_names = {vr['ValidationName']: vr for vr in source_vrs}
        target_vr_names = {vr['ValidationName']: vr for vr in target_vrs}
        
        only_in_source = [name for name in source_vr_names if name not in target_vr_names]
        only_in_target = [name for name in target_vr_names if name not in source_vr_names]
        common = [name for name in source_vr_names if name in target_vr_names]
        
        return {
            'only_in_source': only_in_source,
            'only_in_target': only_in_target,
            'common': common,
            'total_source': len(source_vrs),
            'total_target': len(target_vrs)
        }
    except Exception as e:
        return {'error': str(e)}

def generate_comparison_summary(comparisons):
    """Generate summary statistics for the comparison"""
    summary = {
        'total_differences': 0,
        'categories_compared': len(comparisons)
    }
    
    for category, data in comparisons.items():
        if 'differences' in data:
            if isinstance(data['differences'], list):
                summary['total_differences'] += len(data['differences'])
        if 'only_in_source' in data:
            summary['total_differences'] += len(data.get('only_in_source', []))
        if 'only_in_target' in data:
            summary['total_differences'] += len(data.get('only_in_target', []))
    
    return summary

def display_comparison_results(comparison_result):
    """Display object comparison results"""
    st.markdown("## 📊 Comparison Report")
    
    # Header info
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**🔵 Source:** {comparison_result['source_org']} / {comparison_result['source_object']}")
    with col2:
        st.info(f"**🟢 Target:** {comparison_result['target_org']} / {comparison_result['target_object']}")
    
    st.caption(f"Generated: {comparison_result['timestamp']}")
    
    # Summary metrics
    st.markdown("### 📈 Summary")
    summary = comparison_result.get('summary', {})
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Categories Compared", summary.get('categories_compared', 0))
    with col2:
        st.metric("Total Differences", summary.get('total_differences', 0))
    with col3:
        match_percentage = 100 - (summary.get('total_differences', 0) * 10)  # Simplified calculation
        st.metric("Match Score", f"{max(0, match_percentage):.1f}%")
    
    st.markdown("---")
    
    # Field Comparison
    if 'fields' in comparison_result['comparisons']:
        display_field_comparison(comparison_result['comparisons']['fields'])
    
    # Picklist Comparison
    if 'picklists' in comparison_result['comparisons']:
        display_picklist_comparison(comparison_result['comparisons']['picklists'])
    
    # Record Type Comparison
    if 'record_types' in comparison_result['comparisons']:
        display_recordtype_comparison(comparison_result['comparisons']['record_types'])
    
    # Validation Rules Comparison
    if 'validation_rules' in comparison_result['comparisons']:
        display_validation_comparison(comparison_result['comparisons']['validation_rules'])
    
    # Export Report
    st.markdown("---")
    st.markdown("### 📥 Export Report")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Export as JSON
        report_json = json.dumps(comparison_result, indent=2, default=str)
        st.download_button(
            "📄 Download JSON Report",
            report_json,
            f"comparison_{comparison_result['source_object']}_{comparison_result['target_object']}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json", on_click='ignore'
        )
    
    with col2:
        # Export as Excel
        report_excel = generate_comparison_excel(comparison_result)
        if report_excel:
            st.download_button(
                "📊 Download Excel Report",
                report_excel,
                f"comparison_{comparison_result['source_object']}_{comparison_result['target_object']}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", on_click='ignore'
            )

def display_field_comparison(field_data):
    """Display field comparison results"""
    st.markdown("### 📋 Field Comparison")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Source Fields", field_data.get('total_source', 0))
    with col2:
        st.metric("Target Fields", field_data.get('total_target', 0))
    with col3:
        st.metric("Common Fields", field_data.get('total_common', 0))
    with col4:
        st.metric("Differences", field_data.get('total_differences', 0))
    
    # Only in Source
    if field_data.get('only_in_source'):
        with st.expander(f"🔵 Fields Only in Source ({len(field_data['only_in_source'])})", expanded=False):
            df_source = pd.DataFrame(field_data['only_in_source'])
            st.dataframe(df_source, use_container_width=True)
    
    # Only in Target
    if field_data.get('only_in_target'):
        with st.expander(f"🟢 Fields Only in Target ({len(field_data['only_in_target'])})", expanded=False):
            df_target = pd.DataFrame(field_data['only_in_target'])
            st.dataframe(df_target, use_container_width=True)
    
    # Field Differences
    if field_data.get('differences'):
        with st.expander(f"⚠️ Field Attribute Differences ({len(field_data['differences'])})", expanded=True):
            for diff in field_data['differences']:
                st.write(f"**{diff['name']}** ({diff['label']})")
                for change in diff['differences']:
                    st.write(f"  • {change}")
                st.write("")

def display_picklist_comparison(picklist_data):
    """Display picklist comparison results"""
    st.markdown("### 🎨 Picklist Value Comparison")
    
    if picklist_data.get('differences'):
        for diff in picklist_data['differences']:
            with st.expander(f"📋 {diff['field']} ({diff['label']})", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    if diff['only_in_source']:
                        st.warning(f"**Only in Source ({len(diff['only_in_source'])}):**")
                        for val in diff['only_in_source']:
                            st.write(f"• {val}")
                
                with col2:
                    if diff['only_in_target']:
                        st.info(f"**Only in Target ({len(diff['only_in_target'])}):**")
                        for val in diff['only_in_target']:
                            st.write(f"• {val}")
    else:
        st.success("✅ All picklist values match!")

def display_recordtype_comparison(rt_data):
    """Display record type comparison results"""
    st.markdown("### 📑 Record Type Comparison")
    
    if 'error' in rt_data:
        st.warning(f"⚠️ Could not compare record types: {rt_data['error']}")
        return
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Source Record Types", rt_data.get('total_source', 0))
    with col2:
        st.metric("Target Record Types", rt_data.get('total_target', 0))
    with col3:
        st.metric("Common", len(rt_data.get('common', [])))
    
    if rt_data.get('only_in_source'):
        st.warning(f"**Only in Source:** {', '.join(rt_data['only_in_source'])}")
    
    if rt_data.get('only_in_target'):
        st.info(f"**Only in Target:** {', '.join(rt_data['only_in_target'])}")
    
    if not rt_data.get('only_in_source') and not rt_data.get('only_in_target'):
        st.success("✅ All record types match!")

def display_validation_comparison(vr_data):
    """Display validation rule comparison results"""
    st.markdown("### ✅ Validation Rule Comparison")
    
    if 'error' in vr_data:
        st.warning(f"⚠️ Could not compare validation rules: {vr_data['error']}")
        return
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Source Rules", vr_data.get('total_source', 0))
    with col2:
        st.metric("Target Rules", vr_data.get('total_target', 0))
    with col3:
        st.metric("Common", len(vr_data.get('common', [])))
    
    if vr_data.get('only_in_source'):
        st.warning(f"**Only in Source:** {', '.join(vr_data['only_in_source'])}")
    
    if vr_data.get('only_in_target'):
        st.info(f"**Only in Target:** {', '.join(vr_data['only_in_target'])}")
    
    if not vr_data.get('only_in_source') and not vr_data.get('only_in_target'):
        st.success("✅ All validation rules match!")

def generate_comparison_excel(comparison_result):
    """Generate Excel report for comparison"""
    try:
        from io import BytesIO
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metric': ['Source Org', 'Target Org', 'Source Object', 'Target Object', 'Timestamp'],
                'Value': [
                    comparison_result['source_org'],
                    comparison_result['target_org'],
                    comparison_result['source_object'],
                    comparison_result['target_object'],
                    comparison_result['timestamp']
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            # Field comparison sheet
            if 'fields' in comparison_result['comparisons']:
                fields = comparison_result['comparisons']['fields']
                if fields.get('only_in_source'):
                    pd.DataFrame(fields['only_in_source']).to_excel(writer, sheet_name='Fields - Source Only', index=False)
                if fields.get('only_in_target'):
                    pd.DataFrame(fields['only_in_target']).to_excel(writer, sheet_name='Fields - Target Only', index=False)
                if fields.get('differences'):
                    diff_data = []
                    for diff in fields['differences']:
                        for change in diff['differences']:
                            diff_data.append({
                                'Field': diff['name'],
                                'Label': diff['label'],
                                'Difference': change
                            })
                    if diff_data:
                        pd.DataFrame(diff_data).to_excel(writer, sheet_name='Field Differences', index=False)
        
        return output.getvalue()
    except Exception as e:
        st.error(f"Error generating Excel: {str(e)}")
        return None
