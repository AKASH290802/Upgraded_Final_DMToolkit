import streamlit as st
import pandas as pd
from typing import Dict, List, Optional
import json

from .utils import (
    establish_sf_connection,
    get_salesforce_objects,
    validate_file_upload,
    load_data_file,
    extract_picklist_values_from_file,
    save_picklist_mappings,
    load_picklist_mappings,
    get_all_picklist_mappings,
    update_picklist_mapping,
    delete_picklist_mappings
)

def _salesforce_org_options(credentials: Dict) -> List[str]:
    """Salesforce orgs only (no SQL Server / Oracle / openai_config entries)."""
    from ui_components.connection_manager import classify_credentials
    return list(classify_credentials(credentials or {})['salesforce'].keys())


def _seed_org_selector(key: str, sf_orgs: List[str]) -> None:
    """Default an org selectbox to the sidebar org. Runs BEFORE the widget is drawn."""
    if st.session_state.get(key) not in sf_orgs:
        current = st.session_state.get('current_org')
        st.session_state[key] = current if current in sf_orgs else sf_orgs[0]


def show_picklist_mapping_manager(credentials: Dict):
    """Main UI for Picklist Mapping Manager"""
    st.title("📋 Picklist Mapping Manager")
    st.markdown("""
    Create and manage picklist value mappings between your source data and Salesforce.
    This helps transform your data values to match Salesforce picklist options during validation.
    """)
    
    # Tabs for different operations
    tab1, tab2, tab3 = st.tabs([
        "🆕 Create New Mappings",
        "📂 View/Edit Mappings", 
        "🗑️ Delete Mappings"
    ])
    
    with tab1:
        show_create_mappings(credentials)
    
    with tab2:
        show_view_edit_mappings(credentials)
    
    with tab3:
        show_delete_mappings(credentials)

def show_create_mappings(credentials: Dict):
    """UI for creating new picklist mappings"""
    st.subheader("🆕 Create New Picklist Mappings")
    st.markdown("Upload a sample file to extract picklist values and create mappings.")
    
    # Step 1: Upload File
    st.markdown("### Step 1: Upload Sample Data File")
    uploaded_file = st.file_uploader(
        "Choose a CSV, Excel, or PSV file",
        type=['csv', 'xlsx', 'xls', 'psv'],
        help="Upload CSV, Excel, or PSV (Pipe-separated) files containing data with picklist values you want to map",
        key="picklist_file_upload"
    )
    
    if not uploaded_file:
        st.info("👆 Upload a file to get started")
        return
    
    # Validate file
    if not validate_file_upload(uploaded_file):
        return
    
    # Determine file type
    file_extension = uploaded_file.name.split('.')[-1].lower()
    file_type = f".{file_extension}"
    
    # Load file and store in session state
    df = load_data_file(uploaded_file, file_type)
    if df is None or df.empty:
        st.error("Failed to load file or file is empty")
        return
    
    # Store dataframe in session state for persistence across button clicks
    st.session_state.uploaded_picklist_df = df
    st.session_state.uploaded_file_name = uploaded_file.name
    
    st.success(f"✅ File uploaded: **{uploaded_file.name}** - {len(df)} rows, {len(df.columns)} columns")
    
    with st.expander("📊 Preview Data"):
        st.dataframe(df.head(10), use_container_width=True)
    
    # Step 2: Select Org and Object
    st.markdown("### Step 2: Select Salesforce Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        sf_orgs = _salesforce_org_options(credentials)
        if not sf_orgs:
            st.error("No Salesforce organizations configured")
            return
        
        _seed_org_selector("picklist_org_select", sf_orgs)
        selected_org = st.selectbox(
            "Select Salesforce Organization",
            options=sf_orgs,
            key="picklist_org_select"
        )
    
    with col2:
        # Connect to Salesforce
        sf_conn = establish_sf_connection(credentials, selected_org)
        if not sf_conn:
            return
        
        # Get objects
        sf_objects = get_salesforce_objects(sf_conn)
        if not sf_objects:
            st.error("Could not retrieve Salesforce objects")
            return
        
        selected_object = st.selectbox(
            "Select Salesforce Object",
            options=sf_objects,
            key="picklist_object_select"
        )
    
    # Optional: Field mappings
    st.markdown("### Step 3: Field Mappings (Optional)")
    use_mappings = st.checkbox(
        "Use existing field mappings",
        help="If your CSV columns have different names than Salesforce fields, load existing mappings",
        key="use_field_mappings"
    )
    
    field_mappings = None
    if use_mappings:
        # Try to load existing mappings
        mapping_file_path = f"mapping_logs/{selected_org}/{selected_object}/mapping.json"
        try:
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.join(project_root, mapping_file_path)
            
            if os.path.exists(full_path):
                with open(full_path, 'r') as f:
                    field_mappings = json.load(f)
                st.success(f"✅ Loaded {len(field_mappings)} field mappings")
            else:
                st.warning("No existing field mappings found for this org/object")
        except Exception as e:
            st.warning(f"Could not load field mappings: {str(e)}")
    
    # Step 4: Analyze Picklist Fields
    st.markdown("### Step 4: Analyze Picklist Fields")
    
    # Check if we have the uploaded dataframe
    if 'uploaded_picklist_df' not in st.session_state:
        st.warning("⚠️ Please upload a file first")
        return
    
    df = st.session_state.uploaded_picklist_df
    
    if st.button("🔍 Analyze Picklist Fields", type="primary", key="analyze_picklists"):
        with st.spinner("Analyzing picklist fields..."):
            # Debug: Show what we're analyzing
            st.info(f"🔍 Analyzing {len(df)} rows from **{st.session_state.uploaded_file_name}** for object **{selected_object}**")
            
            picklist_data = extract_picklist_values_from_file(
                df, selected_org, selected_object, sf_conn, field_mappings
            )
        
        if not picklist_data:
            st.warning("⚠️ No picklist fields found in the selected object or data")
            st.info("💡 Possible reasons:")
            st.info("• Your CSV columns don't match Salesforce field names")
            st.info("• The selected object has no picklist fields")
            st.info("• Enable 'Use existing field mappings' if your columns have different names")
            
            # Show debug info
            with st.expander("🔍 Debug Information"):
                st.write(f"**Selected Object:** {selected_object}")
                st.write(f"**Columns in uploaded file:** {list(df.columns)}")
                st.write(f"**Using field mappings:** {'Yes' if field_mappings else 'No'}")
                if field_mappings:
                    st.write(f"**Field mappings:** {field_mappings}")
            return
        
        # Store in session state
        st.session_state.picklist_analysis = picklist_data
        st.session_state.picklist_org = selected_org
        st.session_state.picklist_object = selected_object
        st.session_state.picklist_sf_conn = sf_conn
        
        # Show analysis summary
        show_analysis_summary(picklist_data)
    
    # Step 5: Show Mapping Interface
    if 'picklist_analysis' in st.session_state:
        show_mapping_interface()

def show_analysis_summary(picklist_data: Dict):
    """Display comprehensive analysis summary with download option"""
    st.markdown("---")
    st.markdown("### 📊 Picklist Analysis Results")
    
    # Calculate statistics
    total_fields = len(picklist_data)
    fields_need_mapping = sum(1 for field in picklist_data.values() if len(field['needs_mapping']) > 0)
    fields_all_valid = sum(1 for field in picklist_data.values() if len(field['needs_mapping']) == 0 and field['has_data'])
    fields_no_data = sum(1 for field in picklist_data.values() if not field['has_data'])
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Picklist Fields", total_fields)
    with col2:
        st.metric("✅ All Values Valid", fields_all_valid, delta="No mapping needed")
    with col3:
        st.metric("⚠️ Need Mapping", fields_need_mapping, delta="Action required" if fields_need_mapping > 0 else "")
    with col4:
        st.metric("ℹ️ No Data in File", fields_no_data)
    
    # Download analysis button
    st.markdown("#### 📥 Download Complete Analysis")
    
    col_dl1, col_dl2 = st.columns([3, 1])
    
    with col_dl1:
        st.info("📄 Download a comprehensive Excel report with all picklist fields, values, and mapping requirements")
    
    with col_dl2:
        # Generate Excel report
        excel_data = generate_analysis_excel(picklist_data, st.session_state.picklist_org, st.session_state.picklist_object)
        
        st.download_button(
            label="📥 Download Analysis",
            data=excel_data,
            file_name=f"Picklist_Analysis_{st.session_state.picklist_org}_{st.session_state.picklist_object}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
    
    # Detailed breakdown
    st.markdown("#### 📋 Field-by-Field Breakdown")
    
    for field_name, field_info in picklist_data.items():
        needs_mapping = field_info['needs_mapping']
        already_valid = field_info['already_valid']
        has_data = field_info['has_data']
        
        # Determine status icon
        if not has_data:
            status_icon = "ℹ️"
            status_text = "No data in uploaded file"
            expanded = False
        elif len(needs_mapping) == 0:
            status_icon = "✅"
            status_text = "All values match Salesforce"
            expanded = False
        else:
            status_icon = "⚠️"
            status_text = f"{len(needs_mapping)} value(s) need mapping"
            expanded = True
        
        with st.expander(f"{status_icon} **{field_name}** - {status_text}", expanded=expanded):
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**📊 Your Data:**")
                if has_data:
                    st.write(f"- Total unique values: {len(field_info['source_values'])}")
                    st.write(f"- ✅ Already valid: {len(already_valid)}")
                    st.write(f"- ⚠️ Need mapping: {len(needs_mapping)}")
                else:
                    st.write("- No data found in uploaded file")
            
            with col_b:
                st.markdown("**🎯 Salesforce Info:**")
                st.write(f"- CSV Column: `{field_info['csv_column']}`")
                st.write(f"- Field Type: {field_info['sf_field_type']}")
                st.write(f"- Valid values: {len(field_info['salesforce_values'])}")
            
            # Show values details
            if has_data:
                tab_valid, tab_mapping, tab_sf = st.tabs(["✅ Valid Values", "⚠️ Needs Mapping", "🎯 Salesforce Values"])
                
                with tab_valid:
                    if already_valid:
                        valid_df = pd.DataFrame([
                            {"Value": val, "Record Count": field_info['unique_count'].get(val, 0)}
                            for val in already_valid
                        ])
                        st.dataframe(valid_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No values in your file match Salesforce yet")
                
                with tab_mapping:
                    if needs_mapping:
                        mapping_df = pd.DataFrame([
                            {"Source Value": val, "Record Count": field_info['unique_count'].get(val, 0), "Target Value": "❓ Not mapped yet"}
                            for val in needs_mapping
                        ])
                        st.dataframe(mapping_df, use_container_width=True, hide_index=True)
                        st.warning("⚠️ These values must be mapped to Salesforce valid values")
                    else:
                        st.success("✅ All values in your file already match Salesforce!")
                
                with tab_sf:
                    sf_values = field_info['salesforce_values']
                    if sf_values:
                        # Display in columns for better visibility
                        st.markdown(f"**{len(sf_values)} valid Salesforce values:**")
                        
                        # Create DataFrame for better display
                        sf_df = pd.DataFrame({"Valid Salesforce Values": sf_values})
                        st.dataframe(sf_df, use_container_width=True, hide_index=True)
                    else:
                        st.warning("No active picklist values found in Salesforce")

def generate_analysis_excel(picklist_data: Dict, org_name: str, object_name: str) -> bytes:
    """Generate comprehensive Excel analysis report"""
    from io import BytesIO
    
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Summary
        summary_data = []
        for field_name, field_info in picklist_data.items():
            summary_data.append({
                "Field Name": field_name,
                "CSV Column": field_info['csv_column'],
                "Field Type": field_info['sf_field_type'],
                "Total Unique Values": len(field_info['source_values']),
                "Already Valid": len(field_info['already_valid']),
                "Needs Mapping": len(field_info['needs_mapping']),
                "Has Data": "Yes" if field_info['has_data'] else "No",
                "Salesforce Valid Values Count": len(field_info['salesforce_values'])
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Sheet 2: Detailed Value Analysis
        detail_data = []
        for field_name, field_info in picklist_data.items():
            for value in field_info['source_values']:
                status = "✅ Valid" if value in field_info['already_valid'] else "⚠️ Needs Mapping"
                target = value if value in field_info['already_valid'] else "Not mapped"
                
                detail_data.append({
                    "Field Name": field_name,
                    "CSV Column": field_info['csv_column'],
                    "Source Value": value,
                    "Status": status,
                    "Target Value": target,
                    "Record Count": field_info['unique_count'].get(value, 0)
                })
        
        if detail_data:
            detail_df = pd.DataFrame(detail_data)
            detail_df.to_excel(writer, sheet_name='Value Analysis', index=False)
        
        # Sheet 3: Salesforce Valid Values
        sf_values_data = []
        for field_name, field_info in picklist_data.items():
            for sf_value in field_info['salesforce_values']:
                sf_values_data.append({
                    "Field Name": field_name,
                    "CSV Column": field_info['csv_column'],
                    "Valid Salesforce Value": sf_value
                })
        
        if sf_values_data:
            sf_df = pd.DataFrame(sf_values_data)
            sf_df.to_excel(writer, sheet_name='Salesforce Valid Values', index=False)
        
        # Sheet 4: Mapping Template
        template_data = []
        for field_name, field_info in picklist_data.items():
            if field_info['needs_mapping']:
                for source_val in field_info['needs_mapping']:
                    template_data.append({
                        "Field Name": field_name,
                        "Source Value": source_val,
                        "Target Value (Fill This)": "",
                        "Notes": f"Choose from: {', '.join(field_info['salesforce_values'][:5])}..."
                    })
        
        if template_data:
            template_df = pd.DataFrame(template_data)
            template_df.to_excel(writer, sheet_name='Mapping Template', index=False)
    
    output.seek(0)
    return output.getvalue()

def show_mapping_interface():
    """Display interactive mapping interface for each picklist field"""
    st.markdown("### Step 5: Map Picklist Values")
    st.markdown("Map your source values to Salesforce picklist values for each field below.")
    
    picklist_data = st.session_state.picklist_analysis
    org_name = st.session_state.picklist_org
    object_name = st.session_state.picklist_object
    
    # Initialize mappings storage in session state
    if 'new_picklist_mappings' not in st.session_state:
        st.session_state.new_picklist_mappings = {}
    
    # Filter to show only fields that need mapping
    fields_needing_mapping = {k: v for k, v in picklist_data.items() if len(v['needs_mapping']) > 0}
    
    if not fields_needing_mapping:
        st.success("🎉 All picklist values in your file already match Salesforce! No mapping needed.")
        st.info("💡 You can still save the current state to document which values are valid.")
        return
    
    st.info(f"⚠️ {len(fields_needing_mapping)} field(s) require mapping. Fields with all valid values are already configured.")
    
    # Display mapping interface for each field that needs mapping
    for field_idx, (field_name, field_info) in enumerate(fields_needing_mapping.items()):
        csv_column = field_info['csv_column']
        needs_mapping = field_info['needs_mapping']
        already_valid = field_info['already_valid']
        sf_values = field_info['salesforce_values']
        value_counts = field_info['unique_count']
        existing_mappings = field_info.get('existing_mappings', {})
        
        # Field container
        with st.expander(f"**Field {field_idx + 1}: {field_name}** ({field_info['sf_field_type']})", expanded=True):
            st.markdown(f"**CSV Column:** `{csv_column}`")
            
            # Show statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Needs Mapping", len(needs_mapping))
            with col2:
                st.metric("Already Valid", len(already_valid))
            with col3:
                st.metric("Total Unique", len(value_counts))
            
            # Show already valid values
            if already_valid:
                with st.expander(f"✅ Already Valid Values ({len(already_valid)})", expanded=False):
                    valid_df = pd.DataFrame([
                        {"Value": val, "Count": value_counts.get(val, 0)}
                        for val in already_valid
                    ])
                    st.dataframe(valid_df, use_container_width=True, hide_index=True)
            
            # Mapping interface for values needing mapping
            if needs_mapping:
                st.markdown("#### 🔄 Map Source Values to Salesforce Values")
                
                # Initialize field mappings
                if field_name not in st.session_state.new_picklist_mappings:
                    st.session_state.new_picklist_mappings[field_name] = {
                        "csv_column": csv_column,
                        "mappings": existing_mappings.copy() if existing_mappings else {}
                    }
                
                # Create mapping inputs
                for source_value in needs_mapping:
                    col_source, col_arrow, col_target = st.columns([2, 0.3, 2])
                    
                    with col_source:
                        st.text_input(
                            "Source Value",
                            value=source_value,
                            disabled=True,
                            key=f"source_{field_name}_{source_value}",
                            label_visibility="collapsed"
                        )
                        st.caption(f"📊 {value_counts.get(source_value, 0)} records")
                    
                    with col_arrow:
                        st.markdown("**→**")
                    
                    with col_target:
                        # Get default value if exists in mappings
                        default_idx = 0
                        if source_value in existing_mappings:
                            try:
                                default_idx = sf_values.index(existing_mappings[source_value])
                            except ValueError:
                                default_idx = 0
                        
                        selected_target = st.selectbox(
                            "Target Value",
                            options=sf_values,
                            index=default_idx,
                            key=f"target_{field_name}_{source_value}",
                            label_visibility="collapsed"
                        )
                        
                        # Store mapping
                        st.session_state.new_picklist_mappings[field_name]["mappings"][source_value] = selected_target
                
                # Auto-add already valid values to mappings (they map to themselves)
                for valid_value in already_valid:
                    st.session_state.new_picklist_mappings[field_name]["mappings"][valid_value] = valid_value
            
            else:
                st.info("All values in this field already match Salesforce picklist values")
    
    # Save button
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col2:
        if st.button("💾 Save All Mappings", type="primary", use_container_width=True):
            save_all_mappings()
    
    with col3:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.pop('new_picklist_mappings', None)
            st.rerun()

def save_all_mappings():
    """Save all configured mappings"""
    try:
        org_name = st.session_state.picklist_org
        object_name = st.session_state.picklist_object
        mappings = st.session_state.new_picklist_mappings
        
        if not mappings:
            st.warning("No mappings to save")
            return
        
        # Save mappings
        success = save_picklist_mappings(org_name, object_name, mappings)
        
        if success:
            st.success(f"✅ Successfully saved mappings for {len(mappings)} field(s)!")
            st.balloons()
            
            # Show summary
            with st.expander("📋 Saved Mappings Summary", expanded=True):
                for field_name, field_data in mappings.items():
                    st.markdown(f"**{field_name}**")
                    st.write(f"- CSV Column: `{field_data['csv_column']}`")
                    st.write(f"- Mappings: {len(field_data['mappings'])} value(s)")
            
            # Clear session state
            st.session_state.pop('picklist_analysis', None)
            st.session_state.pop('new_picklist_mappings', None)
        else:
            st.error("Failed to save mappings")
            
    except Exception as e:
        st.error(f"Error saving mappings: {str(e)}")

def show_view_edit_mappings(credentials: Dict):
    """UI for viewing and editing existing mappings"""
    st.subheader("📂 View and Edit Existing Mappings")
    
    # Select org and object
    col1, col2 = st.columns(2)
    
    with col1:
        sf_orgs = _salesforce_org_options(credentials)
        if not sf_orgs:
            st.error("No Salesforce organizations configured")
            return
        
        _seed_org_selector("view_org_select", sf_orgs)
        selected_org = st.selectbox(
            "Select Organization",
            options=sf_orgs,
            key="view_org_select"
        )
    
    with col2:
        sf_conn = establish_sf_connection(credentials, selected_org)
        if not sf_conn:
            return
        
        sf_objects = get_salesforce_objects(sf_conn)
        if not sf_objects:
            return
        
        try:
            from ui_components import step_flow as _flow
            _flow.default_to_flow_object("view_object_select", sf_objects)
        except ImportError:
            pass
        selected_object = st.selectbox(
            "Select Object",
            options=sf_objects,
            key="view_object_select"
        )
    
    # Load existing mappings
    all_mappings = get_all_picklist_mappings(selected_org, selected_object)
    
    if not all_mappings.get('fields'):
        st.info(f"No picklist mappings found for {selected_org} - {selected_object}")
        st.markdown("💡 Go to **Create New Mappings** tab to set up mappings")
        return
    
    # Display mappings
    st.markdown(f"### Mappings for {selected_object}")
    st.caption(f"Last Updated: {all_mappings.get('last_updated', 'Unknown')}")
    
    for field_name, field_data in all_mappings['fields'].items():
        with st.expander(f"**{field_name}**", expanded=False):
            st.markdown(f"**CSV Column:** `{field_data['csv_column']}`")
            st.markdown(f"**Mappings:** {len(field_data['mappings'])} value(s)")
            
            # Display mappings as DataFrame
            mapping_df = pd.DataFrame([
                {"Source Value": k, "Target Value": v}
                for k, v in field_data['mappings'].items()
            ])
            
            st.dataframe(mapping_df, use_container_width=True, hide_index=True)
            
            # Download as CSV
            csv = mapping_df.to_csv(index=False)
            st.download_button(
                label=f"📥 Download {field_name} Mappings",
                data=csv,
                file_name=f"{selected_org}_{selected_object}_{field_name}_mappings.csv",
                mime="text/csv",
                key=f"download_{field_name}"
            )

def show_delete_mappings(credentials: Dict):
    """UI for deleting mappings"""
    st.subheader("🗑️ Delete Picklist Mappings")
    st.warning("⚠️ Deleting mappings will affect validation that relies on these transformations")
    
    # Select org and object
    col1, col2 = st.columns(2)
    
    with col1:
        sf_orgs = _salesforce_org_options(credentials)
        if not sf_orgs:
            st.error("No Salesforce organizations configured")
            return
        
        _seed_org_selector("delete_org_select", sf_orgs)
        selected_org = st.selectbox(
            "Select Organization",
            options=sf_orgs,
            key="delete_org_select"
        )
    
    with col2:
        sf_conn = establish_sf_connection(credentials, selected_org)
        if not sf_conn:
            return
        
        sf_objects = get_salesforce_objects(sf_conn)
        if not sf_objects:
            return
        
        try:
            from ui_components import step_flow as _flow
            _flow.default_to_flow_object("delete_object_select", sf_objects)
        except ImportError:
            pass
        selected_object = st.selectbox(
            "Select Object",
            options=sf_objects,
            key="delete_object_select"
        )
    
    # Load existing mappings
    all_mappings = get_all_picklist_mappings(selected_org, selected_object)
    
    if not all_mappings.get('fields'):
        st.info(f"No picklist mappings found for {selected_org} - {selected_object}")
        return
    
    # Delete options
    st.markdown("### Select What to Delete")
    
    delete_option = st.radio(
        "Delete Option",
        options=["Delete specific field mappings", "Delete all mappings for this object"],
        key="delete_option"
    )
    
    if delete_option == "Delete specific field mappings":
        # Select fields to delete
        field_names = list(all_mappings['fields'].keys())
        selected_fields = st.multiselect(
            "Select fields to delete",
            options=field_names,
            key="fields_to_delete"
        )
        
        if selected_fields:
            st.warning(f"⚠️ You are about to delete mappings for {len(selected_fields)} field(s)")
            
            if st.button("🗑️ Delete Selected Fields", type="primary"):
                success_count = 0
                for field_name in selected_fields:
                    if delete_picklist_mappings(selected_org, selected_object, field_name):
                        success_count += 1
                
                if success_count == len(selected_fields):
                    st.success(f"✅ Successfully deleted {success_count} field mapping(s)")
                    st.rerun()
                else:
                    st.error(f"Partial deletion: {success_count}/{len(selected_fields)} succeeded")
    
    else:
        # Delete entire object mappings
        st.error(f"⚠️ WARNING: This will delete ALL {len(all_mappings['fields'])} field mappings for {selected_object}")
        
        confirm = st.text_input(
            "Type 'DELETE' to confirm",
            key="delete_confirm"
        )
        
        if confirm == "DELETE":
            if st.button("🗑️ Delete All Mappings", type="primary"):
                if delete_picklist_mappings(selected_org, selected_object):
                    st.success(f"✅ Successfully deleted all mappings for {selected_object}")
                    st.rerun()
                else:
                    st.error("Failed to delete mappings")
