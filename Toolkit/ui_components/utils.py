import streamlit as st
import simple_salesforce as sf
import pandas as pd
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

def establish_sf_connection(credentials: Dict, org_name: str) -> Optional[sf.Salesforce]:
    """Return the shared Salesforce connection for org_name.

    Kept for existing callers. Connections come from the per-org pool in
    connection_manager, so asking for a different org no longer replaces the
    sidebar org's connection.
    """
    from ui_components.connection_manager import get_sf_connection
    return get_sf_connection(org_name, credentials=credentials)


def _metadata_cache(name: str, sf_conn):
    """(cache dict, org) for per-org Salesforce metadata, or (None, None)."""
    from ui_components.connection_manager import org_for_connection
    org = org_for_connection(sf_conn)
    if not org:
        return None, None
    if name not in st.session_state:
        st.session_state[name] = {}
    return st.session_state[name], org


def get_salesforce_objects(sf_conn: sf.Salesforce, filter_custom: bool = False) -> List[str]:
    """Get list of Salesforce objects (cached per org for the session)"""
    if sf_conn is None:
        st.error("❌ No Salesforce connection available")
        return []

    cache, org = _metadata_cache('_sf_objects_cache', sf_conn)
    if cache is not None and (org, filter_custom) in cache:
        return list(cache[(org, filter_custom)])

    objects = _fetch_salesforce_objects(sf_conn, filter_custom)
    if cache is not None and objects:
        cache[(org, filter_custom)] = list(objects)
    return objects


def _fetch_salesforce_objects(sf_conn: sf.Salesforce, filter_custom: bool = False) -> List[str]:
    try:
        with st.spinner("Fetching Salesforce objects..."):
            # Get all objects from the org
            describe_result = sf_conn.describe()
            
            if not describe_result or 'sobjects' not in describe_result:
                st.error("❌ Failed to retrieve object list from Salesforce")
                return []
            
            objects_data = describe_result['sobjects']
            object_names = [obj['name'] for obj in objects_data if obj.get('name')]
            
            if filter_custom:
                # Filter for Account and custom objects (ending with __c) and some common objects
                filtered_objects = []
                for name in object_names:
                    if (name.lower() == 'account' or 
                        name.endswith('__c') or 
                        'wod' in name.lower() or
                        name in ['Contact', 'Lead', 'Opportunity', 'Case']):
                        filtered_objects.append(name)
                
                st.info(f"Found {len(filtered_objects)} eligible objects (Account, custom objects, and common standard objects)")
                return sorted(filtered_objects)
            
            st.info(f"Found {len(object_names)} total objects in the organization")
            return sorted(object_names)
        
    except Exception as e:
        st.error(f"❌ Error fetching Salesforce objects: {str(e)}")
        st.error("Please check your connection and try again.")
        return []

def get_object_description(sf_conn: sf.Salesforce, object_name: str) -> Optional[Dict]:
    """Get detailed description of a Salesforce object (cached per org + object)"""
    import pickle
    try:
        cache, org = _metadata_cache('_sf_describe_cache', sf_conn)
        if cache is not None and (org, object_name) in cache:
            return pickle.loads(cache[(org, object_name)])
        description = getattr(sf_conn, object_name).describe()
        if cache is not None and description:
            # Stored pickled so callers that modify the dict cannot change the cache.
            cache[(org, object_name)] = pickle.dumps(description)
        return description
    except Exception as e:
        st.error(f"Error getting object description for {object_name}: {str(e)}")
        return None

def display_dataframe_with_download(df: pd.DataFrame, filename: str, title: str = "Data Preview"):
    """Display dataframe with download option"""
    if df is not None and not df.empty:
        st.subheader(title)
        
        # Display basic info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rows", len(df))
        with col2:
            st.metric("Total Columns", len(df.columns))
        with col3:
            st.metric("Memory Usage", f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB")
        
        # Display dataframe
        st.dataframe(df, use_container_width=True, height=400)
        
        # Download button
        csv_data = df.to_csv(index=False)
        st.download_button(
            label=f"📥 Download {filename}",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.warning("No data to display")

def show_processing_status(status_key: str, message: str, status_type: str = "info"):
    """Show processing status with color coding"""
    if status_type == "success":
        st.success(f"✅ {message}")
    elif status_type == "error":
        st.error(f"❌ {message}")
    elif status_type == "warning":
        st.warning(f"⚠️ {message}")
    else:
        st.info(f"ℹ️ {message}")
    
    # Store in session state
    st.session_state.processing_status[status_key] = {
        'message': message,
        'type': status_type,
        'timestamp': pd.Timestamp.now()
    }

def create_progress_tracker(steps: List[str], current_step: int = 0):
    """Create a visual progress tracker"""
    st.subheader("📊 Process Progress")
    
    progress_percentage = (current_step / len(steps)) * 100 if steps else 0
    st.progress(progress_percentage / 100)
    
    for i, step in enumerate(steps):
        if i < current_step:
            st.success(f"✅ {step}")
        elif i == current_step:
            st.info(f"🔄 {step} (Current)")
        else:
            st.write(f"⏳ {step}")

def validate_file_upload(uploaded_file, allowed_extensions: List[str] = ['.csv', '.xlsx', '.xls', '.psv']) -> bool:
    """Validate uploaded file"""
    if uploaded_file is None:
        return False
    
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    if file_extension not in allowed_extensions:
        st.error(f"Invalid file type. Allowed: {', '.join(allowed_extensions)}")
        return False
    
    return True

def load_data_file(file_path_or_uploaded_file, file_type: str = None) -> Optional[pd.DataFrame]:
    """
    Load data from CSV, Excel, or PSV file
    
    Args:
        file_path_or_uploaded_file: Either file path string or Streamlit uploaded file object
        file_type: Optional file type override ('.csv', '.xlsx', '.xls', '.psv')
    
    Returns:
        pandas.DataFrame or None if error
    """
    try:
        import pandas as pd
        
        # Determine if it's a file path or uploaded file
        if hasattr(file_path_or_uploaded_file, 'name'):
            # It's an uploaded file object
            uploaded_file = file_path_or_uploaded_file
            file_ext = file_type or os.path.splitext(uploaded_file.name)[1].lower()
            
            if file_ext in ['.csv']:
                return pd.read_csv(uploaded_file, dtype=str)
            elif file_ext in ['.xlsx', '.xls']:
                return pd.read_excel(uploaded_file, dtype=str)
            elif file_ext in ['.psv']:
                return pd.read_csv(uploaded_file, sep='|', dtype=str)
            else:
                st.error(f"Unsupported file format: {file_ext}")
                return None
                
        else:
            # It's a file path
            file_path = file_path_or_uploaded_file
            file_ext = file_type or os.path.splitext(file_path)[1].lower()
            
            if file_ext in ['.csv']:
                return pd.read_csv(file_path, dtype=str)
            elif file_ext in ['.xlsx', '.xls']:
                return pd.read_excel(file_path, dtype=str)
            elif file_ext in ['.psv']:
                return pd.read_csv(file_path, sep='|', dtype=str)
            else:
                st.error(f"Unsupported file format: {file_ext}")
                return None
                
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return None

def save_uploaded_file(uploaded_file, directory: str) -> str:
    """Save uploaded file to specified directory"""
    try:
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, uploaded_file.name)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return file_path
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return ""

def load_mapping_file(org_name: str, object_name: str) -> Optional[Dict]:
    """Load mapping file for specific org and object"""
    try:
        mapping_path = os.path.join(
            project_root, 'mapping_logs', org_name, object_name, 'mapping.json'
        )
        
        if os.path.exists(mapping_path):
            with open(mapping_path, 'r') as f:
                return json.load(f)
        else:
            return None
    except Exception as e:
        st.error(f"Error loading mapping file: {str(e)}")
        return None

def save_mapping_file(mapping_data: Dict, org_name: str, object_name: str) -> bool:
    """Save mapping file for specific org and object"""
    try:
        mapping_dir = os.path.join(project_root, 'mapping_logs', org_name, object_name)
        os.makedirs(mapping_dir, exist_ok=True)
        
        mapping_path = os.path.join(mapping_dir, 'mapping.json')
        with open(mapping_path, 'w') as f:
            json.dump(mapping_data, f, indent=2)
        
        return True
    except Exception as e:
        st.error(f"Error saving mapping file: {str(e)}")
        return False

@st.cache_data(ttl=60, show_spinner=False)  # folder scan: at most once a minute
def get_recent_logs(log_type: str = "all", limit: int = 100) -> List[Dict]:
    """Get recent log entries"""
    logs = []
    try:
        logs_base_path = os.path.join(project_root, 'DataLoader_Logs')
        
        if os.path.exists(logs_base_path):
            for root, dirs, files in os.walk(logs_base_path):
                for file in files:
                    if file.endswith('.csv') and 'log' in file.lower():
                        file_path = os.path.join(root, file)
                        try:
                            df = pd.read_csv(file_path)
                            if not df.empty:
                                logs.extend(df.to_dict('records')[-limit:])
                        except:
                            continue
    except Exception as e:
        st.error(f"Error loading logs: {str(e)}")
    
    return logs[-limit:] if logs else []

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def show_error_summary(errors: List[str]):
    """Display error summary in an expandable section"""
    if errors:
        with st.expander(f"❌ Errors ({len(errors)})", expanded=False):
            for i, error in enumerate(errors, 1):
                st.error(f"{i}. {error}")

def create_download_zip(files: Dict[str, pd.DataFrame], zip_name: str):
    """Create downloadable zip file with multiple CSV files"""
    import zipfile
    import io
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, df in files.items():
            csv_data = df.to_csv(index=False)
            zip_file.writestr(filename, csv_data)
    
    zip_buffer.seek(0)
    
    st.download_button(
        label=f"📦 Download {zip_name}",
        data=zip_buffer.getvalue(),
        file_name=zip_name,
        mime="application/zip",
        use_container_width=True
    )

def query_bulk_data(object_name: str, query: str, sf_conn) -> pd.DataFrame:
    """
    Query Salesforce data in bulk - used by ETL engine
    This function matches the Utils.query_bulk_data from the provided script
    """
    try:
        if not sf_conn:
            st.error("No Salesforce connection available")
            return pd.DataFrame()
        
        result = sf_conn.query_all(query)
        records = result['records']
        
        if records:
            df = pd.DataFrame(records)
            # Remove attributes column if it exists
            if 'attributes' in df.columns:
                df = df.drop('attributes', axis=1)
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Salesforce bulk query failed: {str(e)}")
        return pd.DataFrame()

# ============================================================================
# PICKLIST MAPPING FUNCTIONS
# ============================================================================

def get_picklist_mapping_path(org_name: str, object_name: str, create: bool = True) -> str:
    """Get the path for picklist mapping file (create=False for reads: no folder is made)"""
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'picklist_mappings')
    org_dir = os.path.join(base_dir, org_name)
    object_dir = os.path.join(org_dir, object_name)
    
    if create:
        os.makedirs(object_dir, exist_ok=True)
    
    return os.path.join(object_dir, 'picklist_mappings.json')


# Parsed picklist mapping files, keyed by path; an entry is reused while the file's
# modification time is unchanged. Validation looks mappings up once per cell, so
# re-reading the JSON each time made a 20k-row Schema validation take minutes.
_PICKLIST_FILE_CACHE: Dict[str, Tuple[float, Dict]] = {}


def _read_picklist_file(file_path: str) -> Optional[Dict]:
    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        return None
    cached = _PICKLIST_FILE_CACHE.get(file_path)
    if cached and cached[0] == mtime:
        return cached[1]
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    _PICKLIST_FILE_CACHE[file_path] = (mtime, data)
    return data

def save_picklist_mappings(org_name: str, object_name: str, mappings: Dict) -> bool:
    """
    Save picklist mappings to JSON file
    
    Args:
        org_name: Salesforce org name
        object_name: Salesforce object name
        mappings: Dictionary with structure:
            {
                "field_name": {
                    "csv_column": "column_name",
                    "mappings": {"source": "target", ...}
                }
            }
    
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path = get_picklist_mapping_path(org_name, object_name)
        
        # Prepare data structure
        data = {
            "org_name": org_name,
            "object_name": object_name,
            "last_updated": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            "fields": mappings
        }
        
        # Save to JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Error saving picklist mappings: {str(e)}")
        return False

def load_picklist_mappings(org_name: str, object_name: str, field_name: Optional[str] = None) -> Optional[Dict]:
    """
    Load picklist mappings from JSON file
    
    Args:
        org_name: Salesforce org name
        object_name: Salesforce object name
        field_name: Optional - specific field name to load mappings for
    
    Returns:
        Dictionary of mappings or None if not found
        If field_name provided: {"source": "target", ...}
        If field_name not provided: Full structure with all fields
    """
    try:
        data = _read_picklist_file(get_picklist_mapping_path(org_name, object_name, create=False))
        if data is None:
            return None
        
        if field_name:
            # Return mappings for specific field
            field_data = data.get('fields', {}).get(field_name, {})
            return dict(field_data.get('mappings', {}))
        else:
            # Return all fields
            return dict(data.get('fields', {}))
            
    except Exception as e:
        st.error(f"Error loading picklist mappings: {str(e)}")
        return None

def get_all_picklist_mappings(org_name: str, object_name: str) -> Dict:
    """
    Get all picklist mappings for an object
    
    Returns:
        Dictionary with full structure including metadata
    """
    try:
        file_path = get_picklist_mapping_path(org_name, object_name, create=False)
        
        if not os.path.exists(file_path):
            return {
                "org_name": org_name,
                "object_name": object_name,
                "fields": {}
            }
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        st.error(f"Error loading picklist mappings: {str(e)}")
        return {"org_name": org_name, "object_name": object_name, "fields": {}}

def update_picklist_mapping(org_name: str, object_name: str, field_name: str, 
                            csv_column: str, field_mappings: Dict) -> bool:
    """
    Update or add mappings for a specific field
    
    Args:
        org_name: Salesforce org name
        object_name: Salesforce object name
        field_name: Salesforce field name
        csv_column: CSV column name
        field_mappings: Dictionary of source->target mappings
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load existing mappings
        all_mappings = get_all_picklist_mappings(org_name, object_name)
        
        # Update or add field mappings
        if 'fields' not in all_mappings:
            all_mappings['fields'] = {}
        
        all_mappings['fields'][field_name] = {
            "csv_column": csv_column,
            "mappings": field_mappings
        }
        
        # Save updated mappings
        return save_picklist_mappings(org_name, object_name, all_mappings['fields'])
        
    except Exception as e:
        st.error(f"Error updating picklist mapping: {str(e)}")
        return False

def delete_picklist_mappings(org_name: str, object_name: str, field_name: Optional[str] = None) -> bool:
    """
    Delete picklist mappings
    
    Args:
        org_name: Salesforce org name
        object_name: Salesforce object name
        field_name: Optional - if provided, delete only this field's mappings
                    if not provided, delete entire file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path = get_picklist_mapping_path(org_name, object_name)
        
        if not os.path.exists(file_path):
            return True  # Already doesn't exist
        
        if field_name:
            # Delete specific field
            all_mappings = get_all_picklist_mappings(org_name, object_name)
            if 'fields' in all_mappings and field_name in all_mappings['fields']:
                del all_mappings['fields'][field_name]
                return save_picklist_mappings(org_name, object_name, all_mappings['fields'])
            return True
        else:
            # Delete entire file
            os.remove(file_path)
            return True
            
    except Exception as e:
        st.error(f"Error deleting picklist mappings: {str(e)}")
        return False

def transform_picklist_value(org_name: str, object_name: str, field_name: str, source_value: str) -> str:
    """
    Transform source value to target value using saved mappings
    
    Args:
        org_name: Salesforce org name
        object_name: Salesforce object name
        field_name: Salesforce field name
        source_value: Source value from file
    
    Returns:
        Target value if mapping exists, otherwise original source_value
    """
    try:
        mappings = load_picklist_mappings(org_name, object_name, field_name)
        
        if mappings and str(source_value) in mappings:
            return mappings[str(source_value)]
        
        return source_value
        
    except Exception as e:
        return source_value

def extract_picklist_values_from_file(df: pd.DataFrame, org_name: str, object_name: str, 
                                      sf_conn: sf.Salesforce, field_mappings: Dict = None) -> Dict:
    """
    Extract unique values from picklist fields in uploaded file and compare with Salesforce
    
    Args:
        df: DataFrame with uploaded data
        org_name: Salesforce org name
        object_name: Salesforce object name
        sf_conn: Salesforce connection
        field_mappings: Optional CSV to Salesforce field mappings
    
    Returns:
        Dictionary with structure:
        {
            "Status__c": {
                "csv_column": "Status_CSV",
                "sf_field_type": "picklist",
                "source_values": ["Act", "Inact", "Pend", "Active"],
                "unique_count": {"Act": 12, "Inact": 8, "Pend": 15, "Active": 45},
                "salesforce_values": ["Active", "Inactive", "Pending"],
                "needs_mapping": ["Act", "Inact", "Pend"],
                "already_valid": ["Active"],
                "existing_mappings": {"Act": "Active", ...}  # If mappings exist
            }
        }
    """
    try:
        result = {}
        
        # Verify DataFrame is valid
        if df is None or df.empty:
            st.warning("⚠️ DataFrame is empty or None")
            return result
        
        # Get Salesforce object description
        obj_desc = get_object_description(sf_conn, object_name)
        if not obj_desc:
            st.error(f"❌ Could not get Salesforce object description for {object_name}")
            return result
        
        fields = obj_desc.get('fields', [])
        
        # Create field info map
        field_info_map = {field['name']: field for field in fields}
        
        # Get picklist fields count for debugging
        picklist_fields_in_sf = [f['name'] for f in fields if f.get('type', '').lower() in ['picklist', 'multipicklist']]
        
        # Load existing mappings if any
        existing_mappings = load_picklist_mappings(org_name, object_name)
        
        # Track matched columns for debugging
        matched_columns = []
        
        # Iterate through DataFrame columns
        for csv_column in df.columns:
            # Determine Salesforce field name
            if field_mappings and csv_column in field_mappings:
                sf_field_name = field_mappings[csv_column]
            else:
                sf_field_name = csv_column
            
            # Check if this is a picklist field in Salesforce
            if sf_field_name in field_info_map:
                field_info = field_info_map[sf_field_name]
                field_type = field_info.get('type', '').lower()
                
                if field_type in ['picklist', 'multipicklist']:
                    # Get Salesforce valid values (active only)
                    picklist_values = field_info.get('picklistValues', [])
                    sf_valid_values = [pv.get('value', '') for pv in picklist_values if pv.get('active', True)]
                    
                    # Get unique values from file (excluding null/empty)
                    file_values = df[csv_column].dropna()
                    file_values = file_values[file_values.astype(str).str.strip() != '']
                    
                    unique_values = file_values.unique().tolist()
                    unique_values = [str(v) for v in unique_values]
                    
                    # Count occurrences
                    value_counts = df[csv_column].value_counts().to_dict()
                    value_counts = {str(k): int(v) for k, v in value_counts.items() if pd.notna(k) and str(k).strip() != ''}
                    
                    # Determine which values need mapping
                    needs_mapping = []
                    already_valid = []
                    
                    for value in unique_values:
                        if value in sf_valid_values:
                            already_valid.append(value)
                        else:
                            needs_mapping.append(value)
                    
                    # Get existing mappings for this field
                    field_existing_mappings = {}
                    if existing_mappings and sf_field_name in existing_mappings:
                        field_existing_mappings = existing_mappings[sf_field_name].get('mappings', {})
                    
                    # Include ALL picklist fields found (not just those needing mapping)
                    if unique_values or sf_valid_values:  # If there are any values in file or Salesforce
                        result[sf_field_name] = {
                            "csv_column": csv_column,
                            "sf_field_type": field_type,
                            "source_values": unique_values,
                            "unique_count": value_counts,
                            "salesforce_values": sf_valid_values,
                            "needs_mapping": needs_mapping,
                            "already_valid": already_valid,
                            "existing_mappings": field_existing_mappings,
                            "has_data": len(unique_values) > 0
                        }
                        matched_columns.append(csv_column)
        
        # Debug logging
        if not result:
            st.warning(f"🔍 Analysis Details:")
            st.info(f"• DataFrame has {len(df)} rows and {len(df.columns)} columns")
            st.info(f"• Columns in file: {', '.join(list(df.columns)[:10])}")
            st.info(f"• Picklist fields in Salesforce {object_name}: {len(picklist_fields_in_sf)}")
            if picklist_fields_in_sf:
                st.info(f"• Salesforce picklist fields: {', '.join(picklist_fields_in_sf[:10])}")
            st.info(f"• Matched columns: {len(matched_columns)}")
        
        return result
        
    except Exception as e:
        st.error(f"Error extracting picklist values: {str(e)}")
        return {}