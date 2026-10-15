"""
Data Hub UI Components
======================
Streamlit interface for Data Hub functionality
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any
from .data_hub import DataHub


def show_data_hub_interface(sf_conn=None):
    """
    Display complete Data Hub interface
    
    Args:
        sf_conn: Optional Salesforce connection object for SOQL queries
    """
    st.title("📊 Data Hub - Centralized Data Management")
    
    st.caption("The central place for your data: upload a CSV/Excel file or pick one from the File Library, or "
               "query Salesforce (SOQL), SQL Server or Oracle with the sidebar connections — then reuse it in every "
               "module without uploading it again.")
    
    # Initialize or get Data Hub from session
    if 'data_hub' not in st.session_state:
        st.session_state.data_hub = DataHub()
    
    data_hub = st.session_state.data_hub
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(["📥 Load Data", "💾 Manage Datasets", "📋 Active Dataset", "📊 Operation History"])
    
    # ==================== TAB 1: LOAD DATA ====================
    with tab1:
        st.header("Load Data Into Hub")
        st.caption("💡 The guided migration starts in **1️⃣ Source/Target Information** — load data there to "
                   "validate and load it step by step. This tab only adds datasets to the Hub.")
        from ui_components.step1_data_loading import render_hub_loader
        render_hub_loader(sf_conn)
    
    # ==================== TAB 2: MANAGE DATASETS ====================
    with tab2:
        st.header("Manage Cached Datasets")
        _show_dataset_management(data_hub)
    
    # ==================== TAB 3: ACTIVE DATASET ====================
    with tab3:
        st.header("Active Dataset Preview")
        _show_active_dataset_preview(data_hub)
    
    # ==================== TAB 4: OPERATION HISTORY ====================
    with tab4:
        st.header("📊 Operation History")
        st.markdown("""
        Complete audit trail of ALL operations performed in the toolkit.
        Tracks: Data loads, validations, data quality checks, migrations, and more.
        
        **Operations tracked by:**
        - ✅ Organization (Source & Target)
        - ✅ Object (Account, Opportunity, Custom Objects, etc.)
        - ✅ Operation Type (Load, Validation, Quality Check, Migration, etc.)
        - ✅ Status (Success, Failure, Partial)
        - ✅ Validation Results (Pass/Fail counts)
        - ✅ Timestamp & User Info
        """)
        
        try:
            from .operation_manager import get_operation_manager
            
            op_manager = get_operation_manager()
            
            # Step 1: Show statistics
            st.markdown("### 📈 Operation Statistics")
            
            stats = op_manager.get_operation_stats()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Operations", stats['total_operations'])
            with col2:
                st.metric("Total Records", stats['total_records_processed'])
            with col3:
                st.metric("Validation Passed", stats['total_validation_passed'])
            with col4:
                st.metric("Validation Failed", stats['total_validation_failed'])
            
            st.markdown("---")
            
            # Step 2: Filters with cascading dropdowns
            st.markdown("### 🔍 Filter Operations")
            
            col1, col2, col3, col4 = st.columns(4)
            
            # Salesforce orgs configured in Configuration (same list as the sidebar)
            available_orgs = _get_available_salesforce_orgs()
            
            with col1:
                if len(available_orgs) == 0:
                    st.warning("⚠️ No Salesforce organizations configured in linkedservices.json")
                    org_filter = None
                else:
                    # Default to the sidebar org only (seeded before the widget is
                    # drawn). With no sidebar org the filter starts blank, so no
                    # org is logged into until the user picks one here. When the
                    # sidebar org changes, the filter follows it.
                    sidebar_org = st.session_state.get('current_org')
                    sidebar_default = sidebar_org if sidebar_org in available_orgs else ""
                    org_options = [""] + available_orgs
                    if (st.session_state.get("history_org_filter") not in org_options
                            or st.session_state.get("history_org_seeded_for") != sidebar_org):
                        st.session_state["history_org_filter"] = sidebar_default
                        st.session_state["history_org_seeded_for"] = sidebar_org
                    org_filter = st.selectbox(
                        "Organization:",
                        org_options,
                        key="history_org_filter",
                        format_func=lambda o: o if o else "Select an organization…",
                        help="Defaults to the organization selected in the sidebar"
                    ) or None
            
            # Get objects based on selected org - CASCADING DROPDOWN
            with col2:
                if org_filter is None:
                    st.info("Select an organization first")
                    object_filter = None
                else:
                    # Get objects from the selected org
                    org_objects = _get_objects_for_org(org_filter)
                    
                    if len(org_objects) == 0:
                        st.info(f"No objects found for {org_filter}. Check Salesforce connection.")
                        object_filter = None
                    else:
                        object_filter = st.selectbox(
                            "Object:",
                            org_objects,
                            key="history_object_filter",
                            help=f"Objects available in {org_filter}"
                        )
            
            with col3:
                op_type_filter = st.selectbox(
                    "Operation Type:",
                    ["All", "SOQL_Query", "File_Upload", "Data_Load", "Validation_Check_Business_Rules", "Validation_Check_Data_Quality", "Validation_Check_Schema", "Migration_Execute", "Lookup_Resolution"],
                    key="history_op_type_filter",
                    help="Select operation type or 'All' to see all types"
                )
            with col4:
                status_filter = st.selectbox(
                    "Status:",
                    ["All", "COMPLETE", "FAILED"],
                    key="history_status_filter",
                    help="Filter by operation status"
                )
            
            # Debug info (optional - can remove later)
            with st.expander("🔧 Debug Info", expanded=False):
                st.write(f"**Selected Org:** {org_filter}")
                st.write(f"**Selected Object:** {object_filter}")
                st.write(f"**Selected Operation Type:** {op_type_filter}")
                st.write(f"**Selected Status:** {status_filter}")
                if org_filter:
                    st.write(f"**Available Objects for {org_filter}:** {op_manager.get_unique_objects_for_org(org_filter)}")
            
            # Apply filters - only query if org and object are selected
            if org_filter is None:
                st.warning("📭 Please select an organization to view operations.")
                history = []
            elif object_filter is None:
                st.warning(f"📭 No objects available for {org_filter}. Please select another organization or upload data first.")
                history = []
            else:
                history = op_manager.get_operation_history(
                    org_filter=org_filter,
                    object_filter=object_filter,
                    operation_type_filter=None if op_type_filter == "All" else op_type_filter,
                    status_filter=None if status_filter == "All" else status_filter
                )
            
            st.markdown("---")
            
            # Step 3: Display operations as table
            if history:
                st.markdown(f"### 📋 Operations ({len(history)} found)")
                
                # Convert to display format
                display_data = []
                for op in history:
                    display_data.append({
                        "Operation ID": op['operation_id'],
                        "Date/Time": op['timestamp'][:19],  # Remove seconds
                        "Type": op['operation_type'].replace('_', ' '),
                        "Source Org": op.get('source_org', '-'),
                        "Target Org": op.get('target_org', '-'),
                        "Object": op['object_name'],
                        "Records": op['record_count'],
                        "Validation": op.get('validation_status', '-'),
                        "Status": "✅" if op['status'] == "COMPLETE" else "❌"
                    })
                
                df_display = pd.DataFrame(display_data)
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # Step 4: View operation details
                st.markdown("### 📂 View Operation Details")
                
                selected_op_id = st.selectbox(
                    "Select operation to view:",
                    [op['operation_id'] for op in history],
                    key="selected_operation"
                )
                
                if selected_op_id:
                    try:
                        data, operation = op_manager.retrieve_operation_data(selected_op_id)
                        
                        # Display metadata
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("📋 Operation Metadata")
                            metadata_display = {
                                "Operation ID": operation['operation_id'],
                                "Timestamp": operation['timestamp'],
                                "Type": operation['operation_type'],
                                "Source Org": operation.get('source_org', '-'),
                                "Target Org": operation.get('target_org', '-'),
                                "Object": operation['object_name'],
                                "Total Records": operation['record_count'],
                                "Validation Status": operation.get('validation_status', '-'),
                                "Passed": operation.get('validation_passed', 0),
                                "Failed": operation.get('validation_failed', 0),
                                "Created By": operation.get('created_by', '-'),
                                "Notes": operation.get('notes', '-')
                            }
                            
                            for key, value in metadata_display.items():
                                st.text(f"{key}: {value}")
                            
                            if operation.get('query'):
                                st.subheader("🔍 SOQL Query")
                                st.code(operation['query'], language='sql')
                            
                            if operation.get('file_uploaded'):
                                st.subheader("📁 File Uploaded")
                                st.text(f"File: {operation['file_uploaded']}")
                        
                        with col2:
                            st.subheader("📊 Data Preview")
                            
                            st.write(f"Rows: {len(data)} | Columns: {len(data.columns)}")
                            
                            # Show data statistics
                            if len(data) > 0:
                                st.caption("Column Statistics:")
                                st.dataframe(
                                    data.describe(include='all').T,
                                    use_container_width=True
                                )
                        
                        st.markdown("---")
                        
                        # Display full data
                        st.subheader("📈 Full Data")
                        st.dataframe(data, use_container_width=True)
                        
                        # Download buttons
                        col1, col2, col3 = st.columns(3)
                        
                        # Files are built only when a download button is clicked.
                        with col1:
                            st.download_button(
                                "📥 Download as CSV",
                                lambda df=data: df.to_csv(index=False),
                                f"{selected_op_id}_data.csv",
                                "text/csv",
                                key=f"download_csv_{selected_op_id}",
                                on_click='ignore',
                            )
                        
                        with col2:
                            st.download_button(
                                "📥 Download as Excel",
                                lambda df=data: _excel_bytes(df),
                                f"{selected_op_id}_data.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_xlsx_{selected_op_id}",
                                on_click='ignore',
                            )
                        
                        with col3:
                            if st.button(
                                "🗑️ Delete Operation",
                                key=f"delete_{selected_op_id}"
                            ):
                                if op_manager.delete_operation(selected_op_id):
                                    st.success(f"✅ Deleted operation {selected_op_id}")
                                    st.rerun()
                                else:
                                    st.error("❌ Could not delete operation")
                    
                    except FileNotFoundError as e:
                        st.warning(f"⚠️ Data file not found: {str(e)}")
                    except Exception as e:
                        st.error(f"❌ Error loading operation data: {str(e)}")
            
            else:
                st.info("📭 No operations found matching your filters.")
                st.markdown("""
                **Get Started:**
                1. Use **📥 Load Data** tab to upload a file or query Salesforce
                2. Operations will appear here for future reference
                3. View, filter, and download historical data anytime!
                """)
            
            # Step 5: Export history
            st.markdown("---")
            st.markdown("### 📤 Export History")
            
            if st.button("📥 Export All Operations to CSV", key="export_history"):
                try:
                    csv_file = op_manager.export_history_to_csv("operation_history.csv")
                    with open(csv_file, 'r') as f:
                        st.download_button(
                            "Download History CSV",
                            f.read(),
                            "operation_history.csv",
                            "text/csv"
                        )
                    st.success("✅ History exported!")
                except Exception as e:
                    st.error(f"❌ Error exporting history: {str(e)}")
        
        except ImportError as e:
            st.error(f"❌ Could not load Operation Manager: {str(e)}")
            st.info("💡 Make sure operation_manager.py is properly installed")
        except Exception as e:
            st.error(f"❌ Error in Data Operations tab: {str(e)}")
    
    st.divider()
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📦 Cached Datasets", data_hub.get_dataset_count())
    with col2:
        if data_hub.has_active_dataset():
            active_info = data_hub.get_active_dataset_info()
            st.metric("🎯 Active Dataset", active_info['name'])
        else:
            st.metric("🎯 Active Dataset", "None")
    with col3:
        if data_hub.has_active_dataset():
            active_info = data_hub.get_active_dataset_info()
            st.metric("📊 Rows", active_info['metadata']['row_count'])
        else:
            st.metric("📊 Rows", "0")


def _show_dataset_management(data_hub: DataHub):
    """Dataset management interface"""
    datasets = data_hub.list_datasets()
    
    if not datasets:
        st.info("📭 No datasets cached yet. Load data from the '📥 Load Data' tab.")
        return
    
    st.write(f"**Total Datasets: {len(datasets)}**")
    st.divider()
    
    for dataset_info in datasets:
        dataset_id = dataset_info['id']
        name = dataset_info['name']
        metadata = dataset_info['metadata']
        is_active = dataset_info['is_active']
        
        # Create container for each dataset
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            
            with col1:
                # Dataset name with active indicator
                if is_active:
                    st.markdown(f"**🎯 {name}** (Active)")
                else:
                    st.markdown(f"**📦 {name}**")
            
            with col2:
                # Source info
                source_type = metadata['source_type']
                if source_type == 'file_upload':
                    source_icon = "📄"
                elif source_type == 'salesforce_soql':
                    source_icon = "⚙️"
                else:
                    source_icon = "📋"
                
                st.caption(f"{source_icon} {source_type} | {metadata['row_count']} rows | {metadata['column_count']} cols")
            
            with col3:
                if st.button("✓ Set Active", key=f"active_{dataset_id}", use_container_width=True):
                    data_hub.set_active_dataset(dataset_id)
                    st.rerun()
            
            with col4:
                if st.button("📊 Preview", key=f"preview_{dataset_id}", use_container_width=True):
                    st.session_state[f'show_preview_{dataset_id}'] = not st.session_state.get(f'show_preview_{dataset_id}', False)
                    st.rerun()
            
            with col5:
                if st.button("❌ Delete", key=f"delete_{dataset_id}", use_container_width=True):
                    if st.session_state.get(f'confirm_delete_{dataset_id}', False):
                        data_hub.delete_dataset(dataset_id)
                        st.success(f"✅ Dataset '{name}' deleted")
                        st.rerun()
                    else:
                        st.session_state[f'confirm_delete_{dataset_id}'] = True
                        st.warning("⚠️ Click again to confirm deletion")
                        st.rerun()
            
            # Show preview if requested
            if st.session_state.get(f'show_preview_{dataset_id}', False):
                with st.expander(f"📊 Preview: {name}", expanded=True):
                    df = data_hub.get_dataset(dataset_id)
                    st.dataframe(df.head(10), use_container_width=True)
                    
                    # Show metadata
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Rows", metadata['row_count'])
                    with col2:
                        st.metric("Columns", metadata['column_count'])
                    with col3:
                        st.metric("Size (KB)", f"{metadata['memory_usage_kb']:.2f}")
                    with col4:
                        timestamp = datetime.fromisoformat(metadata['timestamp'])
                        st.metric("Loaded", timestamp.strftime("%H:%M:%S"))
            
            st.divider()


def _show_active_dataset_preview(data_hub: DataHub):
    """Show active dataset preview and details"""
    if not data_hub.has_active_dataset():
        st.info("📭 No active dataset. Select a dataset from 'Manage Datasets' tab or load new data.")
        return
    
    dataset_info = data_hub.get_active_dataset_with_metadata()
    metadata = dataset_info['metadata']
    df = dataset_info['df']
    
    # Header with dataset info
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"🎯 {dataset_info['name']}")
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Rows", metadata['row_count'])
    with col2:
        st.metric("📋 Columns", metadata['column_count'])
    with col3:
        st.metric("💾 Size (KB)", f"{metadata['memory_usage_kb']:.2f}")
    with col4:
        timestamp = datetime.fromisoformat(metadata['timestamp'])
        st.metric("⏰ Loaded", timestamp.strftime("%m/%d %H:%M"))
    
    st.divider()
    
    # Source details
    st.write("**📍 Source Information:**")
    source_col1, source_col2 = st.columns(2)
    
    with source_col1:
        st.write(f"**Source Type:** {metadata['source_type'].replace('_', ' ').title()}")
    with source_col2:
        source_details = metadata['source_details']
        if 'file_name' in source_details:
            st.write(f"**File:** {source_details['file_name']}")
        elif 'object_name' in source_details:
            st.write(f"**Object:** {source_details['object_name']}")
    
    st.divider()
    
    # Columns info
    with st.expander("📋 Column Details", expanded=False):
        col_df = pd.DataFrame({
            'Column Name': metadata['columns'],
            'Data Type': [str(df[col].dtype) for col in metadata['columns']],
            'Non-Null Count': [df[col].notna().sum() for col in metadata['columns']]
        })
        st.dataframe(col_df, use_container_width=True)
    
    st.divider()
    
    # Data preview
    st.write("**📊 Data Preview (first 10 rows):**")
    st.dataframe(df.head(10), use_container_width=True)
    
    st.divider()
    
    # Download options
    st.write("**📥 Download Active Dataset:**")
    col1, col2 = st.columns(2)
    
    # Files are built only when a download button is clicked (an Excel export of a
    # large dataset takes seconds, so it must not run on every rerun).
    with col1:
        st.download_button(
            label="📄 Download as CSV",
            data=lambda frame=df: frame.to_csv(index=False),
            file_name=f"{dataset_info['name']}_exported.csv",
            mime="text/csv",
            use_container_width=True,
            on_click='ignore',
        )
    
    with col2:
        st.download_button(
            label="📊 Download as Excel",
            data=lambda frame=df: _excel_bytes(frame),
            file_name=f"{dataset_info['name']}_exported.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            on_click='ignore',
        )


EXCEL_MAX_ROWS = 1_048_575   # one sheet holds 1,048,576 rows including the header


def _excel_bytes(df: pd.DataFrame) -> bytes:
    """Workbook bytes for a DataFrame (built on download click).

    A sheet holds at most EXCEL_MAX_ROWS data rows, so bigger frames are split over
    several sheets (Data 1, Data 2, ...) instead of failing after writing a million rows.
    """
    import io
    buffer = io.BytesIO()
    if len(df) <= EXCEL_MAX_ROWS:
        df.to_excel(buffer, index=False, engine='openpyxl')
        return buffer.getvalue()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for part, start in enumerate(range(0, len(df), EXCEL_MAX_ROWS), 1):
            df.iloc[start:start + EXCEL_MAX_ROWS].to_excel(writer, sheet_name=f"Data {part}", index=False)
    return buffer.getvalue()


def get_active_dataset() -> Optional[pd.DataFrame]:
    """
    Get active dataset from Data Hub
    
    Utility function for other modules to use active dataset
    
    Returns:
        DataFrame or None if no active dataset
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_active_dataset()
    return None


def get_active_dataset_info() -> Optional[Dict[str, Any]]:
    """
    Get active dataset info including metadata
    
    Returns:
        Dict with 'name' and 'metadata' keys, or None
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_active_dataset_info()
    return None


def has_active_dataset() -> bool:
    """Check if active dataset exists"""
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.has_active_dataset()
    return False


def _get_available_salesforce_orgs() -> list:
    """Salesforce orgs configured in Configuration (same list as the sidebar)."""
    from ui_components.connection_manager import salesforce_orgs
    try:
        return sorted(salesforce_orgs())
    except Exception as e:
        st.error(f"Error loading organizations: {str(e)}")
        return []


def _get_objects_for_org(org_name: str) -> list:
    """Salesforce objects of org_name, using the shared (pooled) connection.

    The object list is cached per org by utils.get_salesforce_objects, so no
    extra login or describe() happens on reruns.
    """
    from ui_components.connection_manager import get_sf_connection
    from ui_components.utils import get_salesforce_objects
    try:
        sf_conn = get_sf_connection(org_name, quiet=True)
        if sf_conn is None:
            return []
        return get_salesforce_objects(sf_conn, filter_custom=False)
    except Exception as e:
        st.warning(f"Could not retrieve objects for {org_name}: {str(e)}")
        return []
