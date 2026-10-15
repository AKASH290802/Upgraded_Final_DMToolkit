import streamlit as st
import pandas as pd
import json
import os
from typing import Dict, Optional
from .utils import (
    establish_sf_connection,
    get_salesforce_objects,
    get_object_description,
    show_processing_status,
    load_mapping_file,
    save_mapping_file,
    validate_file_upload,
    load_data_file
)

def add_next_button(current_tab_index: int, total_tabs: int, session_state_key: str = 'active_tab', selectbox_key: str = 'tab_selector'):
    """Add a JS-based Next button at bottom right to navigate to the next native Streamlit tab."""
    if current_tab_index >= total_tabs - 1:
        return
    import streamlit.components.v1 as components
    components.html(f"""
    <div style="display:flex;justify-content:flex-end;padding:10px 0;">
        <button onclick="
            var tabs=window.parent.document.querySelectorAll('button[data-baseweb=\'tab\']');
            var found=false;
            for(var i=0;i<tabs.length;i++){{
                if(tabs[i].getAttribute('aria-selected')==='true'){{found=true;continue;}}
                if(found){{tabs[i].click();break;}}
            }}
        " style="
            background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;border:none;
            padding:0.55rem 1.4rem;border-radius:8px;cursor:pointer;font-size:0.88rem;font-weight:600;
            box-shadow:0 2px 8px rgba(102,126,234,0.3);transition:all 0.3s ease;
        "
        onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 12px rgba(102,126,234,0.5)'"
        onmouseout="this.style.transform='translateY(0)';this.style.boxShadow='0 2px 8px rgba(102,126,234,0.3)'"
        >Next &#10145;&#65039;</button>
    </div>
    """, height=60)

def show_mapping_operations(credentials: Dict):
    """Display mapping operations interface"""
    
    st.title("🗺️ Mapping Operations")
    st.markdown("Generate and manage field mappings for Salesforce objects")
    
    if not st.session_state.current_org:
        st.warning("⚠️ Please select an organization from the sidebar to continue.")
        return
    
    # Establish connection
    sf_conn = establish_sf_connection(credentials, st.session_state.current_org)
    if not sf_conn:
        st.error("❌ Failed to establish Salesforce connection. Please check your credentials.")
        return
    
    # Initialize session state for tab selection
    if 'mapping_selected_tab' not in st.session_state:
        st.session_state.mapping_selected_tab = 0
    
    # Add tab selector dropdown
    st.markdown("### Select Operation:")
    selected_tab_idx = st.selectbox(
        "Choose a mapping operation",
        options=[0, 1, 2, 3],
        format_func=lambda x: ["🔧 View Field Mapping", "📋 Picklist Mappings", "✏️ Modify Mapping", "📊 Mapping Insights"][x],
        key="mapping_selected_tab",
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔧 View Field Mapping",
        "📋 Picklist Mappings",
        "✏️ Modify Mapping",
        "📊 Mapping Insights"
    ])
    
    total_tabs = 4
    
    with tab1:
        show_generate_mapping(sf_conn)
        add_next_button(0, total_tabs, selectbox_key='mapping_selected_tab')
    
    with tab2:
        from .picklist_mapping import show_picklist_mapping_manager
        show_picklist_mapping_manager(credentials)
        add_next_button(1, total_tabs, selectbox_key='mapping_selected_tab')
    
    with tab3:
        show_edit_mapping(sf_conn)
        add_next_button(2, total_tabs, selectbox_key='mapping_selected_tab')
    
    with tab4:
        show_mapping_analytics()

def show_generate_mapping(sf_conn):
    """View and generate field mapping for Salesforce objects"""
    st.subheader("🔧 View Field Mapping")
    st.markdown("View field mappings for Salesforce objects")
    
    # Object selection
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Get filtered objects (Account and custom objects)
        objects = get_salesforce_objects(sf_conn, filter_custom=True)
        
        if objects:
            selected_object = st.selectbox(
                "Select Salesforce Object",
                options=[""] + objects,
                key="mapping_object_select",
                help="Choose the object to generate mapping for"
            )
        else:
            st.error("❌ No eligible Salesforce objects found")
            return
    
    with col2:
        if st.button("🔍 Object Info", disabled=not selected_object):
            if selected_object:
                show_object_details(sf_conn, selected_object)
    
    if selected_object:
        st.session_state.current_object = selected_object
        
        # Mapping configuration
        st.write("### Mapping Configuration")
        
        col_config1, col_config2 = st.columns(2)
        
        with col_config1:
            mapping_type = st.selectbox(
                "Mapping Type",
                ["Standard Mapping", "Custom Mapping", "Auto-detect from Data"],
                help="Choose how to generate the mapping"
            )
            
            include_readonly = st.checkbox(
                "Include Read-only Fields",
                value=False,
                help="Include fields that cannot be updated"
            )
        
        with col_config2:
            include_system = st.checkbox(
                "Include System Fields",
                value=False,
                help="Include system fields like CreatedDate, LastModifiedDate"
            )
            
            field_filter = st.text_input(
                "Field Filter (optional)",
                placeholder="e.g., Name, Email, Phone",
                help="Comma-separated list of specific fields to include"
            )
        
        # Source data options
        if mapping_type == "Auto-detect from Data":
            st.write("### Source Data Configuration")
            
            data_source = st.radio(
                "Data Source for Auto-detection",
                ["Upload File", "Select Existing File"],
                key="mapping_data_source"
            )
            
            source_df = None
            
            if data_source == "Upload File":
                uploaded_file = st.file_uploader(
                    "Upload source data file",
                    type=['csv', 'xlsx', 'xls', 'psv'],
                    help="Upload CSV, Excel, or PSV (Pipe-separated) files to auto-detect field mappings"
                )
                
                if uploaded_file and validate_file_upload(uploaded_file):
                    try:
                        source_df = load_data_file(uploaded_file)
                        
                        st.success(f"✅ Loaded {len(source_df)} rows with {len(source_df.columns)} columns")
                        
                        with st.expander("📊 Data Preview", expanded=False):
                            st.dataframe(source_df.head(), use_container_width=True)
                            
                    except Exception as e:
                        st.error(f"❌ Error reading file: {str(e)}")
            
            else:
                # Show existing files
                existing_files = get_existing_data_files()
                
                if existing_files:
                    selected_file = st.selectbox(
                        "Select Existing File",
                        options=[""] + existing_files,
                        key="mapping_existing_file"
                    )
                    
                    if selected_file:
                        source_df = load_existing_file(selected_file)
                        
                        if source_df is not None:
                            st.success(f"✅ Loaded {len(source_df)} rows with {len(source_df.columns)} columns")
                else:
                    st.info("No existing data files found")
        
        # View mapping button
        st.divider()
        
        if st.button("🚀 View Mapping", type="primary", use_container_width=True):
            generate_field_mapping(
                sf_conn, 
                selected_object, 
                mapping_type,
                include_readonly,
                include_system,
                field_filter,
                source_df if mapping_type == "Auto-detect from Data" else None
            )

def show_view_mappings():
    """View existing mappings - Primary tab for browsing saved field mappings"""
    st.subheader("👁 View Existing Mappings")
    st.markdown("Browse and review saved field mappings for your organization")
    
    if not st.session_state.current_org:
        st.warning("⚠️ Please select an organization first")
        return
    
    # Get all mappings for current org
    mappings = get_org_mappings(st.session_state.current_org)
    
    if mappings:
        st.write(f"### Mappings for {st.session_state.current_org}")
        
        # Create mapping overview table
        mapping_overview = []
        for obj_name, mapping_data in mappings.items():
            field_count = len(mapping_data.get('fields', {}))
            created_date = mapping_data.get('metadata', {}).get('created_date', 'Unknown')
            
            mapping_overview.append({
                "Object": obj_name,
                "Field Count": field_count,
                "Created": created_date[:10] if created_date != 'Unknown' else created_date,
                "Mapping Type": mapping_data.get('metadata', {}).get('mapping_type', 'Standard')
            })
        
        df_mappings = pd.DataFrame(mapping_overview)
        
        # Display with selection
        selected_mapping = st.selectbox(
            "Select Mapping to View",
            options=[""] + list(mappings.keys()),
            key="view_mapping_select"
        )
        
        # Show overview table
        st.dataframe(df_mappings, use_container_width=True)
        
        if selected_mapping:
            show_mapping_details(mappings[selected_mapping], selected_mapping)
    
    else:
        st.info(f"No mappings found for organization: {st.session_state.current_org}")
        st.write("Use the 'Generate Mapping' tab to create new mappings.")

def show_edit_mapping(sf_conn):
    """Edit existing mappings"""
    st.subheader("✏️ Edit Field Mapping")
    
    if not st.session_state.current_org:
        st.warning("⚠️ Please select an organization first")
        return
    
    # Get existing mappings
    mappings = get_org_mappings(st.session_state.current_org)
    
    if mappings:
        selected_mapping = st.selectbox(
            "Select the object for which you would like to edit the field mapping",
            options=[""] + list(mappings.keys()),
            key="edit_mapping_select"
        )
        
        if selected_mapping:
            mapping_data = mappings[selected_mapping]
            
            st.write(f"### Editing Mapping for {selected_mapping}")
            
            # Show current mapping in editable form
            fields_mapping = mapping_data.get('fields', {})
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.write("**Field Name**")
            with col2:
                st.write("**Target Field (Salesforce)**")
            
            st.divider()
            
            # Create editable mapping
            updated_mapping = {}
            
            # Get object description for field validation
            if sf_conn:
                obj_desc = get_object_description(sf_conn, selected_mapping)
                sf_fields = [field['name'] for field in obj_desc.get('fields', [])] if obj_desc else []
            else:
                sf_fields = []
            
            for i, (source_field, target_field) in enumerate(fields_mapping.items()):
                col_source, col_target, col_action = st.columns([2, 2, 1])
                
                with col_source:
                    new_source = st.text_input(
                        f"Source {i+1}",
                        value=source_field,
                        key=f"source_{i}",
                        label_visibility="collapsed"
                    )
                
                with col_target:
                    if sf_fields:
                        # Dropdown with SF fields
                        try:
                            default_index = sf_fields.index(target_field) if target_field in sf_fields else 0
                        except:
                            default_index = 0
                            
                        new_target = st.selectbox(
                            f"Target {i+1}",
                            options=[""] + sf_fields,
                            index=default_index + 1 if target_field in sf_fields else 0,
                            key=f"target_{i}",
                            label_visibility="collapsed"
                        )
                    else:
                        new_target = st.text_input(
                            f"Target {i+1}",
                            value=target_field,
                            key=f"target_{i}",
                            label_visibility="collapsed"
                        )
                
                with col_action:
                    if st.button("🗑️", key=f"delete_{i}", help="Delete this mapping"):
                        # Mark for deletion
                        continue
                
                if new_source and new_target:
                    updated_mapping[new_source] = new_target
            
            # Add new mapping row
            st.write("### Add New Field Mapping")
            col_new1, col_new2, col_new3 = st.columns([2, 2, 1])
            
            with col_new1:
                new_source_field = st.text_input("New Field Name", key="new_source")
            
            with col_new2:
                if sf_fields:
                    new_target_field = st.selectbox(
                        "New Target Field",
                        options=[""] + sf_fields,
                        key="new_target"
                    )
                else:
                    new_target_field = st.text_input("New Target Field", key="new_target")
            
            with col_new3:
                if st.button("➕ Add"):
                    if new_source_field and new_target_field:
                        updated_mapping[new_source_field] = new_target_field
                        st.rerun()
            
            # Save changes
            st.divider()
            
            col_save1, col_save2 = st.columns(2)
            
            with col_save1:
                if st.button("💾 Save Changes", type="primary", use_container_width=True):
                    # Update mapping data
                    mapping_data['fields'] = updated_mapping
                    mapping_data['metadata']['last_modified'] = pd.Timestamp.now().isoformat()
                    
                    if save_mapping_file(mapping_data, st.session_state.current_org, selected_mapping):
                        st.success("✅ Mapping saved successfully!")
                        show_processing_status("mapping_edit", f"Updated mapping for {selected_mapping}", "success")
                        st.rerun()
                    else:
                        st.error("❌ Failed to save mapping")
            
            with col_save2:
                if st.button("🔄 Reset Changes", use_container_width=True):
                    st.rerun()
    
    else:
        st.info("No mappings found. Create a mapping first using the 'Generate Mapping' tab.")

def show_mapping_analytics():
    """Show mapping analytics and insights"""
    st.subheader("📊 Mapping Analytics")
    
    if not st.session_state.current_org:
        st.warning("⚠️ Please select an organization first")
        return
    
    mappings = get_org_mappings(st.session_state.current_org)
    
    if mappings:
        # Analytics overview
        total_mappings = len(mappings)
        total_fields = sum(len(mapping.get('fields', {})) for mapping in mappings.values())
        avg_fields = total_fields / total_mappings if total_mappings > 0 else 0
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Mappings", total_mappings)
        with col2:
            st.metric("Total Fields Mapped", total_fields)
        with col3:
            st.metric("Avg Fields per Object", f"{avg_fields:.1f}")
        
        st.divider()
        
        # Mapping details chart
        st.write("### Field Count by Object")
        
        chart_data = []
        for obj_name, mapping in mappings.items():
            field_count = len(mapping.get('fields', {}))
            chart_data.append({"Object": obj_name, "Field Count": field_count})
        
        if chart_data:
            df_chart = pd.DataFrame(chart_data)
            st.bar_chart(df_chart.set_index("Object"))
        
        # Field type analysis
        st.write("### Common Field Patterns")
        
        all_source_fields = []
        all_target_fields = []
        
        for mapping in mappings.values():
            fields = mapping.get('fields', {})
            all_source_fields.extend(fields.keys())
            all_target_fields.extend(fields.values())
        
        # Most common source fields
        col_source, col_target = st.columns(2)
        
        with col_source:
            st.write("**Most Common Field Names**")
            source_counts = pd.Series(all_source_fields).value_counts().head(10)
            
            if not source_counts.empty:
                for field, count in source_counts.items():
                    st.write(f"• {field}: {count} mappings")
            else:
                st.write("No data available")
        
        with col_target:
            st.write("**Most Common Target Fields**")
            target_counts = pd.Series(all_target_fields).value_counts().head(10)
            
            if not target_counts.empty:
                for field, count in target_counts.items():
                    st.write(f"• {field}: {count} mappings")
            else:
                st.write("No data available")
        
        # Mapping quality insights
        st.write("### Mapping Quality Insights")
        
        quality_issues = []
        
        for obj_name, mapping in mappings.items():
            fields = mapping.get('fields', {})
            
            # Check for duplicate mappings
            target_values = list(fields.values())
            duplicates = [field for field in set(target_values) if target_values.count(field) > 1]
            
            if duplicates:
                quality_issues.append({
                    "Object": obj_name,
                    "Issue": "Duplicate Target Fields",
                    "Details": f"Fields mapped multiple times: {', '.join(duplicates)}"
                })
            
            # Check for empty mappings
            empty_mappings = [source for source, target in fields.items() if not target]
            
            if empty_mappings:
                quality_issues.append({
                    "Object": obj_name,
                    "Issue": "Empty Target Fields",
                    "Details": f"Source fields without targets: {', '.join(empty_mappings)}"
                })
        
        if quality_issues:
            st.warning("⚠️ Quality Issues Found")
            df_issues = pd.DataFrame(quality_issues)
            st.dataframe(df_issues, use_container_width=True)
        else:
            st.success("✅ No quality issues detected")
    
    else:
        st.info("No mappings available for analysis")

# Helper functions
def show_object_details(sf_conn, object_name: str):
    """Show detailed object information"""
    try:
        obj_desc = get_object_description(sf_conn, object_name)
        
        if obj_desc:
            with st.expander(f"📋 {object_name} Details", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Label:** {obj_desc.get('label', 'N/A')}")
                    st.write(f"**API Name:** {obj_desc.get('name', 'N/A')}")
                    st.write(f"**Custom Object:** {'Yes' if obj_desc.get('custom') else 'No'}")
                
                with col2:
                    st.write(f"**Creatable:** {'Yes' if obj_desc.get('createable') else 'No'}")
                    st.write(f"**Updateable:** {'Yes' if obj_desc.get('updateable') else 'No'}")
                    st.write(f"**Total Fields:** {len(obj_desc.get('fields', []))}")
                
                # Show field summary
                if st.checkbox("Show Field Summary", key="field_summary"):
                    fields = obj_desc.get('fields', [])
                    
                    # Categorize fields
                    required_fields = [f for f in fields if not f.get('nillable', True)]
                    updateable_fields = [f for f in fields if f.get('updateable', False)]
                    custom_fields = [f for f in fields if f.get('custom', False)]
                    
                    col_req, col_upd, col_cus = st.columns(3)
                    
                    with col_req:
                        st.metric("Required Fields", len(required_fields))
                    with col_upd:
                        st.metric("Updateable Fields", len(updateable_fields))
                    with col_cus:
                        st.metric("Custom Fields", len(custom_fields))
    
    except Exception as e:
        st.error(f"❌ Error getting object details: {str(e)}")

def generate_field_mapping(sf_conn, object_name: str, mapping_type: str, include_readonly: bool, 
                          include_system: bool, field_filter: str, source_df: Optional[pd.DataFrame] = None):
    """Generate field mapping for the selected object"""
    try:
        with st.spinner("Generating field mapping..."):
            
            # Get object description
            obj_desc = get_object_description(sf_conn, object_name)
            
            if not obj_desc:
                st.error("❌ Failed to get object description")
                return
            
            # Get fields based on configuration
            fields = obj_desc.get('fields', [])
            
            # Filter fields
            filtered_fields = []
            
            for field in fields:
                # Skip system fields if not included
                if not include_system and field.get('name', '').startswith(('Created', 'LastModified', 'System')):
                    continue
                
                # Skip readonly fields if not included
                if not include_readonly and not field.get('updateable', False) and field.get('name') != 'Id':
                    continue
                
                # Apply field filter if specified
                if field_filter:
                    filter_terms = [term.strip() for term in field_filter.split(',')]
                    if not any(term.lower() in field.get('name', '').lower() for term in filter_terms):
                        continue
                
                filtered_fields.append(field)
            
            # Generate mapping based on type
            mapping = {}
            
            if mapping_type == "Auto-detect from Data" and source_df is not None:
                # Auto-detect mapping from source data
                source_columns = source_df.columns.tolist()
                
                for source_col in source_columns:
                    # Find best match in Salesforce fields
                    best_match = find_best_field_match(source_col, filtered_fields)
                    if best_match:
                        mapping[source_col] = best_match['name']
            
            else:
                # Standard or custom mapping
                for field in filtered_fields:
                    field_name = field.get('name', '')
                    
                    if mapping_type == "Standard Mapping":
                        # Use field name as both source and target
                        mapping[field_name] = field_name
                    else:
                        # Custom mapping - use field label as source
                        field_label = field.get('label', field_name)
                        mapping[field_label] = field_name
            
            # Create mapping structure
            mapping_data = {
                "object_name": object_name,
                "fields": mapping,
                "metadata": {
                    "created_date": pd.Timestamp.now().isoformat(),
                    "mapping_type": mapping_type,
                    "include_readonly": include_readonly,
                    "include_system": include_system,
                    "field_filter": field_filter,
                    "total_fields": len(mapping),
                    "org_name": st.session_state.current_org
                }
            }
            
            # Save mapping
            if save_mapping_file(mapping_data, st.session_state.current_org, object_name):
                st.success(f"✅ Mapping generated successfully for {object_name}!")
                st.success(f"📊 Generated {len(mapping)} field mappings")
                
                # Show preview
                show_mapping_preview(mapping_data)
                
                show_processing_status("mapping_generate", 
                                     f"Generated mapping for {object_name} with {len(mapping)} fields", 
                                     "success")
            else:
                st.error("❌ Failed to save mapping file")
    
    except Exception as e:
        st.error(f"❌ Error generating mapping: {str(e)}")
        show_processing_status("mapping_generate", f"Failed to generate mapping for {object_name}: {str(e)}", "error")

def show_mapping_preview(mapping_data: Dict):
    """Show preview of generated mapping"""
    with st.expander("📋 Mapping Preview", expanded=True):
        fields_mapping = mapping_data.get('fields', {})
        
        if fields_mapping:
            # Convert to DataFrame for better display
            mapping_df = pd.DataFrame([
                {"Field Name": source, "Target Field (Salesforce)": target}
                for source, target in fields_mapping.items()
            ])
            
            st.dataframe(mapping_df, use_container_width=True, height=300)
            
            # Download option
            csv_data = mapping_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Mapping as CSV",
                data=csv_data,
                file_name=f"{mapping_data['object_name']}_mapping.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("No field mappings generated")

def show_mapping_details(mapping_data: Dict, object_name: str):
    """Show detailed view of a mapping"""
    with st.expander(f"📋 {object_name} Mapping Details", expanded=True):
        
        # Metadata
        metadata = mapping_data.get('metadata', {})
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write(f"**Created:** {metadata.get('created_date', 'Unknown')[:10]}")
            st.write(f"**Type:** {metadata.get('mapping_type', 'Unknown')}")
        
        with col2:
            st.write(f"**Total Fields:** {metadata.get('total_fields', 0)}")
            st.write(f"**Include System:** {'Yes' if metadata.get('include_system') else 'No'}")
        
        with col3:
            st.write(f"**Include Readonly:** {'Yes' if metadata.get('include_readonly') else 'No'}")
            filter_text = metadata.get('field_filter', '')
            st.write(f"**Field Filter:** {filter_text if filter_text else 'None'}")
        
        # Fields mapping
        fields = mapping_data.get('fields', {})
        
        if fields:
            mapping_df = pd.DataFrame([
                {"Field Name": source, "Target Field": target}
                for source, target in fields.items()
            ])
            
            st.dataframe(mapping_df, use_container_width=True)
        else:
            st.warning("No field mappings found")

def get_org_mappings(org_name: str) -> Dict:
    """Get all mappings for an organization"""
    mappings = {}
    
    try:
        mapping_logs_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'mapping_logs', 
            org_name
        )
        
        if os.path.exists(mapping_logs_path):
            for item in os.listdir(mapping_logs_path):
                item_path = os.path.join(mapping_logs_path, item)
                
                if os.path.isdir(item_path):
                    mapping_file = os.path.join(item_path, 'mapping.json')
                    
                    if os.path.exists(mapping_file):
                        try:
                            with open(mapping_file, 'r') as f:
                                mapping_data = json.load(f)
                            mappings[item] = mapping_data
                        except Exception:
                            continue
    
    except Exception:
        pass
    
    return mappings

def get_existing_data_files() -> list:
    """Get list of existing data files"""
    files = []
    
    try:
        data_files_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'DataFiles'
        )
        
        if os.path.exists(data_files_path):
            for root, dirs, filenames in os.walk(data_files_path):
                for filename in filenames:
                    if filename.endswith(('.csv', '.xlsx', '.xls')):
                        rel_path = os.path.relpath(os.path.join(root, filename), data_files_path)
                        files.append(rel_path)
    
    except Exception:
        pass
    
    return sorted(files)

def load_existing_file(file_path: str) -> Optional[pd.DataFrame]:
    """Load existing data file"""
    try:
        full_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'DataFiles', 
            file_path
        )
        
        if file_path.endswith('.csv'):
            return pd.read_csv(full_path, dtype=str)
        elif file_path.endswith('.psv'):
            return pd.read_csv(full_path, sep='|', dtype=str)
        else:
            return pd.read_excel(full_path, dtype=str)
    
    except Exception as e:
        st.error(f"❌ Error loading file: {str(e)}")
        return None

def find_best_field_match(source_field: str, sf_fields: list) -> Optional[Dict]:
    """Find best matching Salesforce field for source field"""
    
    source_lower = source_field.lower().replace('_', '').replace(' ', '')
    
    # Direct name match
    for field in sf_fields:
        field_name = field.get('name', '').lower()
        if field_name == source_lower:
            return field
    
    # Label match
    for field in sf_fields:
        field_label = field.get('label', '').lower().replace('_', '').replace(' ', '')
        if field_label == source_lower:
            return field
    
    # Partial match
    for field in sf_fields:
        field_name = field.get('name', '').lower()
        field_label = field.get('label', '').lower()
        
        if (source_lower in field_name or 
            source_lower in field_label or 
            field_name in source_lower or 
            field_label.replace(' ', '') in source_lower):
            return field
    
    return None