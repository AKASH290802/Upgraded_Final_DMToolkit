import streamlit as st
import pandas as pd
import os
import sys
import json
import requests
from typing import Dict, Optional, List
import re
from datetime import datetime

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)

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

def show_validation_operations(credentials: Dict):
    """Display validation operations interface"""
    
    # Initialize session state variables
    if 'current_org' not in st.session_state:
        st.session_state.current_org = None
    if 'current_object' not in st.session_state:
        st.session_state.current_object = None
    if 'show_manual_entry' not in st.session_state:
        st.session_state.show_manual_entry = False
    
    st.title("✅ Data Validation")
    st.markdown("Comprehensive data validation including schema validation and custom business rules")
    
    if not st.session_state.current_org:
        st.warning("⚠️ Please select an organization from the sidebar to continue.")
        return
    
    # Establish connection
    sf_conn = establish_sf_connection(credentials, st.session_state.current_org)
    if not sf_conn:
        st.error("❌ Failed to establish Salesforce connection. Please check your credentials.")
        return
    
    # Main tabs (removed Custom Validation as requested)
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 Schema Validation",
        "🤖 GenAI Validation",
        "📊 Validation Reports",
        "📋 Validation Summary"
    ])
    
    with tab1:
        show_schema_validation(sf_conn)
    
    with tab2:
        show_genai_validation(sf_conn)
    
    with tab3:
        show_validation_reports()
    
    with tab4:
        show_validation_summary()

def show_schema_validation(sf_conn):
    """Schema validation interface"""
    st.subheader("🔍 Schema Validation")
    st.markdown("Validate data against Salesforce object schema - field types, required fields, formats, etc.")
    
    # Object selection
    col1, col2 = st.columns([3, 1])
    
    with col1:
        objects = get_salesforce_objects(sf_conn, filter_custom=True)
        
        if objects:
            selected_object = st.selectbox(
                "Select Salesforce Object for Validation",
                options=[""] + objects,
                key="schema_validation_object",
                help="Choose the object to validate against"
            )
        else:
            st.error("❌ No Salesforce objects found")
            return
    
    with col2:
        if st.button("🔍 Get Schema", disabled=not selected_object):
            if selected_object:
                show_object_schema(sf_conn, selected_object)
    
    if selected_object:
        st.session_state.current_object = selected_object
        
        # Data source selection
        st.write("### Data Source for Validation")
        
        data_source = st.radio(
            "Select Data Source",
            ["Upload File", "Select Existing File", "Use Sample Data"],
            key="schema_validation_source"
        )
        
        validation_data = None
        
        if data_source == "Upload File":
            uploaded_file = st.file_uploader(
                "Upload data file for validation",
                type=['csv', 'xlsx', 'xls', 'psv'],
                help="Upload CSV, Excel, or PSV (Pipe-separated) files",
                key="schema_validation_upload"
            )
            
            if uploaded_file and validate_file_upload(uploaded_file):
                validation_data = load_data_file(uploaded_file)
        
        elif data_source == "Select Existing File":
            existing_files = get_validation_files(selected_object)
            
            if existing_files:
                selected_file = st.selectbox(
                    "Select File",
                    options=[""] + existing_files,
                    key="schema_existing_file"
                )
                
                if selected_file:
                    validation_data = load_existing_validation_file(selected_file)
            else:
                st.info("No existing files found for validation")
        
        else:
            # Use sample data
            validation_data = generate_sample_data(sf_conn, selected_object)
        
        # Validation configuration
        if validation_data is not None:
            st.write("### Validation Configuration")
            
            # Add field mapping interface
            st.write("#### 🔗 CSV Column to Salesforce Field Mapping")
            st.info("📋 Map your CSV columns to Salesforce Object fields for accurate validation")
            
            # Get Salesforce object fields
            try:
                from .utils import get_object_description
                sf_object_info = get_object_description(sf_conn, selected_object)
                
                if sf_object_info and 'fields' in sf_object_info:
                    all_sf_fields = [field for field in sf_object_info['fields'] if field.get('updateable', True)]
                    csv_columns = list(validation_data.columns)
                    
                    # Initialize field mappings in session state
                    if 'schema_field_mappings' not in st.session_state:
                        st.session_state.schema_field_mappings = {}
                    
                    # Auto-suggest mappings based on column names
                    suggested_mappings = {}
                    for csv_col in csv_columns:
                        csv_col_lower = csv_col.lower().replace(' ', '').replace('_', '').replace('.', '').replace('-', '')
                        best_match = None
                        best_score = 0
                        
                        for sf_field in all_sf_fields:
                            sf_field_name = sf_field['name'].lower()
                            sf_field_label = sf_field.get('label', '').lower()
                            
                            # Calculate similarity score
                            score = 0
                            if csv_col_lower == sf_field_name.replace('__c', ''):
                                score = 100  # Perfect match
                            elif csv_col_lower in sf_field_name or sf_field_name in csv_col_lower:
                                score = 80
                            elif csv_col_lower in sf_field_label or sf_field_label in csv_col_lower:
                                score = 60
                            elif any(keyword in csv_col_lower and keyword in sf_field_name 
                                   for keyword in ['name', 'phone', 'email', 'address', 'account', 'contact', 'date', 'status', 'type', 'number']):
                                score = 40
                            
                            if score > best_score:
                                best_score = score
                                best_match = sf_field
                        
                        if best_match and best_score >= 40:
                            suggested_mappings[csv_col] = best_match['name']
                    
                    st.markdown("**🎯 Column Mapping Configuration:**")
                    
                    # Mapping interface
                    field_mappings = {}
                    sf_field_options = ["⚠️ No mapping"] + [f"{field['name']} ({field.get('label', field['name'])})" for field in all_sf_fields]
                    sf_field_names = [""] + [field['name'] for field in all_sf_fields]
                    
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
                            # Get current mapping or suggested mapping
                            current_mapping = st.session_state.schema_field_mappings.get(csv_column, "")
                            if not current_mapping and csv_column in suggested_mappings:
                                current_mapping = suggested_mappings[csv_column]
                            
                            # Find index for current mapping
                            current_index = 0
                            if current_mapping:
                                try:
                                    current_index = sf_field_names.index(current_mapping)
                                except ValueError:
                                    current_index = 0
                            
                            selected_mapping = st.selectbox(
                                f"Field mapping for {csv_column}",
                                options=sf_field_options,
                                index=current_index,
                                key=f"schema_mapping_{i}_{csv_column}",
                                label_visibility="collapsed"
                            )
                            
                            # Store the mapping
                            if selected_mapping != "⚠️ No mapping":
                                field_name = selected_mapping.split(" (")[0]
                                field_mappings[csv_column] = field_name
                                st.session_state.schema_field_mappings[csv_column] = field_name
                            elif csv_column in st.session_state.schema_field_mappings:
                                del st.session_state.schema_field_mappings[csv_column]
                        
                        with col3:
                            # Show sample data
                            sample_value = validation_data[csv_column].iloc[0] if len(validation_data) > 0 else "N/A"
                            st.write(f"`{sample_value}`")
                    
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
                if st.button("🚀 Run Schema Validation", type="primary", use_container_width=True):
                    run_schema_validation(
                        sf_conn, selected_object, validation_data,
                        validate_required, validate_datatypes, validate_formats,
                        validate_lengths, validate_picklists, strict_mode, field_mappings
                    )
            else:
                st.warning("⚠️ Configure at least one field mapping to run validation")
                st.button("🚀 Run Schema Validation", type="primary", use_container_width=True, disabled=True)

def show_custom_validation(sf_conn):
    """Custom validation interface"""
    st.subheader("⚙️ Custom Business Rule Validation")
    st.markdown("Extract and validate against Salesforce validation rules and custom business logic")
    
    # Object selection
    objects = get_salesforce_objects(sf_conn, filter_custom=True)
    
    if objects:
        selected_object = st.selectbox(
            "Select Salesforce Object",
            options=["Select an object..."] + objects,
            key="custom_validation_object"
        )
    else:
        st.error("❌ No Salesforce objects found")
        return
    
    if selected_object and selected_object != "Select an object...":
        # Update session state with current object
        st.session_state.current_object = selected_object
        
        # Create SF validation client
        sf_client = create_sf_validation_client(sf_conn)
        
        # Step 2: Fetch Validation Rules for the Selected Object
        with st.spinner("Fetching validation rules..."):
            validation_rules_result = sf_client.fetch_validation_rules(selected_object)

        # Ensure validation_rules is properly extracted
        if isinstance(validation_rules_result, dict):
            if validation_rules_result.get("error"):
                st.error(validation_rules_result["message"])
                validation_rules = []
            else:
                validation_rules = validation_rules_result.get("records", [])
                if validation_rules_result.get("message"):
                    st.info(validation_rules_result["message"])
        else:
            validation_rules = []

        # DEBUG: Show what we actually got from Salesforce
        st.write("🔍 **DEBUG: Validation Rules Source**")
        if validation_rules:
            st.success(f"✅ Successfully fetched {len(validation_rules)} real validation rules from Salesforce")
            for i, rule in enumerate(validation_rules[:3]):  # Show first 3 rules
                st.write(f"Rule {i+1}: {rule.get('FullName', 'Unknown')} - Active: {rule.get('Active', 'Unknown')}")
        else:
            st.error("❌ NO REAL VALIDATION RULES FOUND - This is the problem!")
            st.info("Debug info:")
            st.write(f"- validation_rules_result type: {type(validation_rules_result)}")
            if isinstance(validation_rules_result, dict):
                st.write(f"- Has error: {validation_rules_result.get('error')}")
                st.write(f"- Message: {validation_rules_result.get('message')}")
                st.write(f"- Records count: {len(validation_rules_result.get('records', []))}")

        if not validation_rules:
            st.warning(f"No validation rules found for the object '{selected_object}'.")
            st.info("This could mean:")
            st.info("• No validation rules are configured for this object")
            st.info("• API access restrictions")
            st.info("• The object may not have custom validation rules")
        else:
            # Display validation rules
            st.success(f"✅ Found {len(validation_rules)} validation rule(s) for {selected_object}")
            
            # Display validation rules in expandable sections
            st.write("### 📋 Validation Rules")
            display_validation_rules_table(validation_rules, selected_object)
            
            # Show detailed validation rules
            st.write("### 🔍 Detailed Validation Rules")
            for i, rule in enumerate(validation_rules):
                status_icon = "✅" if rule.get('Active', True) else "❌"
                rule_name = rule.get('FullName', f'Rule {i+1}')
                
                with st.expander(f"{status_icon} {rule_name}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Basic Information:**")
                        st.write(f"**Rule Name:** {rule_name}")
                        st.write(f"**Active:** {'Yes' if rule.get('Active', True) else 'No'}")
                        st.write(f"**Error Field:** {rule.get('ErrorDisplayField', 'N/A')}")
                    
                    with col2:
                        st.write("**Metadata:**")
                        if rule.get('CreatedDate'):
                            st.write(f"**Created:** {rule.get('CreatedDate', 'N/A')[:10]}")
                        if rule.get('LastModifiedDate'):
                            st.write(f"**Last Modified:** {rule.get('LastModifiedDate', 'N/A')[:10]}")
                        st.write(f"**Rule ID:** {rule.get('Id', 'N/A')}")
                    
                    if rule.get('Description'):
                        st.write("**Description:**")
                        st.write(rule.get('Description', 'N/A'))
                    
                    # Display the validation formula (the most important part!)
                    validation_formula = rule.get('ValidationFormula', 'No formula available')
                    st.write("**Validation Formula:**")
                    if validation_formula == 'FORMULA_NOT_ACCESSIBLE_VIA_API':
                        st.warning("⚠️ **Salesforce Limitation**: Validation formulas are not accessible via Tooling API")
                        st.info("**Alternative Solutions:**")
                        st.write("1. **Use GenAI Validation**: Convert rule descriptions to formulas automatically")
                        st.write("2. **Manual Entry**: Enter formulas manually based on Salesforce UI")
                        st.write("3. **Metadata API**: Use advanced Metadata API (requires additional setup)")
                        
                        # Show what we can infer from error message and field
                        error_field = rule.get('ErrorDisplayField', '')
                        error_message = rule.get('ErrorMessage', '')
                        if error_field and error_message:
                            st.write("**Inferred Validation Logic:**")
                            if 'required' in error_message.lower() or 'blank' in error_message.lower():
                                suggested_formula = f"ISBLANK({error_field})"
                                st.code(f"Suggested Formula: {suggested_formula}", language="text")
                                st.caption("💡 This is a guess based on the error message - verify in Salesforce")
                    elif validation_formula != 'No formula available':
                        st.code(validation_formula, language="text")
                        st.info("💡 This formula defines when the validation rule fails (returns TRUE when invalid)")
                    else:
                        st.warning("⚠️ Formula not available - this may cause validation issues")
                    
                    st.write("**Error Message:**")
                    st.code(rule.get('ErrorMessage', 'N/A'), language="text")
            
            # Download options
            st.write("###   Export Options")
            col1, col2 = st.columns(2)
            
            with col1:
                # Download as CSV
                df_rules = pd.DataFrame([{
                    'Rule Name': rule.get('FullName', 'N/A'),
                    'Active': rule.get('Active', True),
                    'Error Field': rule.get('ErrorDisplayField', 'N/A'),
                    'Error Message': rule.get('ErrorMessage', 'N/A'),
                    'Description': rule.get('Description', 'N/A')
                } for rule in validation_rules])
                
                csv_data = df_rules.to_csv(index=False)
                st.download_button(
                    label="📄 Download as CSV",
                    data=csv_data,
                    file_name=f"{selected_object}_validation_rules.csv",
                    mime="text/csv",
                    key="validation_rules_csv"
                )
            
            with col2:
                # Download as JSON
                json_data = json.dumps(validation_rules, indent=2, default=str)
                st.download_button(
                    label="📋 Download as JSON",
                    data=json_data,
                    file_name=f"{selected_object}_validation_rules.json",
                    mime="application/json",
                    key="validation_rules_json"
                )
        
        # Custom validation execution (if rules exist)
        if validation_rules:
            st.divider()
            st.write("### 🔄 Run Custom Validation")
            st.info("Upload data to validate against the extracted validation rules")
            
            # Data source
            data_source = st.radio(
                "Data Source",
                ["Upload File", "Select Existing File"],
                key="custom_validation_source"
            )
            
            validation_data = None
            
            if data_source == "Upload File":
                uploaded_file = st.file_uploader(
                    "Upload data for custom validation",
                    type=['csv', 'xlsx', 'xls'],
                    key="custom_validation_upload"
                )
                
                if uploaded_file:
                    validation_data = load_data_file(uploaded_file)
            
            else:
                existing_files = get_validation_files(selected_object)
                
                if existing_files:
                    selected_file = st.selectbox(
                        "Select File",
                        options=[""] + existing_files,
                        key="custom_existing_file"
                    )
                    
                    if selected_file:
                        validation_data = load_existing_validation_file(selected_file)
            
            if validation_data is not None:
                # Show field mapping interface before validation
                st.write("### 🔗 CSV Column to Salesforce Field Mapping")
                st.info("📋 Map your CSV columns to relevant Salesforce Object fields for validation")
                
                # Analyze CSV columns and get relevant Salesforce fields
                csv_columns = list(validation_data.columns)
                
                # Get Salesforce object fields and filter relevant ones
                try:
                    from .utils import get_object_description
                    sf_object_info = get_object_description(sf_conn, selected_object)
                    if sf_object_info and 'fields' in sf_object_info:
                        all_sf_fields = [field for field in sf_object_info['fields'] if field.get('updateable', True)]
                        
                        # Filter Salesforce fields that are likely relevant to CSV columns
                        relevant_sf_fields = []
                        for csv_col in csv_columns:
                            csv_col_lower = csv_col.lower().replace(' ', '').replace('_', '').replace('.', '').replace('-', '')
                            
                            for sf_field in all_sf_fields:
                                sf_field_name = sf_field['name'].lower()
                                sf_field_label = sf_field.get('label', '').lower()
                                
                                # Check if there's similarity between CSV column and SF field
                                if (csv_col_lower in sf_field_name or sf_field_name in csv_col_lower or
                                    csv_col_lower in sf_field_label or sf_field_label in csv_col_lower or
                                    any(keyword in csv_col_lower and keyword in sf_field_name 
                                        for keyword in ['name', 'phone', 'email', 'address', 'street', 'account', 'contact', 'date', 'status'])):
                                    
                                    if sf_field not in relevant_sf_fields:
                                        relevant_sf_fields.append(sf_field)
                        
                        # Add some common fields that are often needed
                        common_fields = ['Name', 'Phone', 'Email', 'AccountId', 'ContactId', 'Status']
                        for common_field in common_fields:
                            for sf_field in all_sf_fields:
                                if sf_field['name'] == common_field and sf_field not in relevant_sf_fields:
                                    relevant_sf_fields.append(sf_field)
                        
                    else:
                        # Fallback to common fields
                        relevant_sf_fields = [
                            {'name': 'Name', 'label': 'Name', 'type': 'string'},
                            {'name': 'Phone', 'label': 'Phone', 'type': 'string'},
                            {'name': 'Email', 'label': 'Email', 'type': 'email'},
                            {'name': 'AccountId', 'label': 'Account ID', 'type': 'reference'},
                            {'name': 'Status', 'label': 'Status', 'type': 'picklist'}
                        ]
                    
                    st.success(f"✅ Found {len(relevant_sf_fields)} relevant Salesforce fields for your CSV columns")
                    
                except Exception as e:
                    st.warning(f"⚠️ Could not fetch {selected_object} fields. Using common fields.")
                    relevant_sf_fields = [
                        {'name': 'Name', 'label': 'Name', 'type': 'string'},
                        {'name': 'Phone', 'label': 'Phone', 'type': 'string'},
                        {'name': 'Email', 'label': 'Email', 'type': 'email'},
                        {'name': 'AccountId', 'label': 'Account ID', 'type': 'reference'},
                        {'name': 'Status', 'label': 'Status', 'type': 'picklist'}
                    ]
                
                # Create field mappings based on CSV columns
                st.write("### 🎯 Column Mapping Configuration")
                st.info("For each CSV column, select which Salesforce field it represents (if any)")
                
                field_mappings = {}
                sf_field_options = ["⚠️ No mapping"] + [f"{field['name']} ({field['label']})" for field in relevant_sf_fields]
                sf_field_names = [""] + [field['name'] for field in relevant_sf_fields]
                
                # Create simple mapping interface
                st.write("**Map CSV Columns to Salesforce Fields:**")
                
                # Use columns for better layout
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.write("**CSV Column**")
                with col2:
                    st.write("**Maps to Salesforce Field**")
                
                st.divider()
                
                for i, csv_column in enumerate(csv_columns):
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        # Show CSV column name with sample value
                        sample_value = validation_data[csv_column].dropna().iloc[0] if not validation_data[csv_column].dropna().empty else "No data"
                        st.write(f"**{csv_column}**")
                        st.caption(f"Sample: {sample_value}")
                    
                    with col2:
                        # Auto-suggest Salesforce field based on CSV column name
                        suggested_index = 0
                        csv_col_lower = csv_column.lower().replace(' ', '').replace('_', '').replace('.', '').replace('-', '')
                        
                        for idx, sf_field in enumerate(relevant_sf_fields):
                            sf_field_name_lower = sf_field['name'].lower()
                            sf_field_label_lower = sf_field.get('label', '').lower()
                            
                            if (csv_col_lower in sf_field_name_lower or sf_field_name_lower in csv_col_lower or
                                csv_col_lower in sf_field_label_lower or
                                ('name' in csv_col_lower and 'name' in sf_field_name_lower) or
                                ('phone' in csv_col_lower and 'phone' in sf_field_name_lower) or
                                ('email' in csv_col_lower and 'email' in sf_field_name_lower)):
                                suggested_index = idx + 1  # +1 because of "No mapping" option
                                break
                        
                        selected_sf_field = st.selectbox(
                            "Select field:",
                            options=sf_field_options,
                            index=suggested_index,
                            key=f"csv_to_sf_mapping_{i}",
                            label_visibility="collapsed"
                        )
                        
                        if selected_sf_field != "⚠️ No mapping":
                            # Extract field name from selection
                            sf_field_name = sf_field_names[sf_field_options.index(selected_sf_field)]
                            field_mappings[sf_field_name] = csv_column
                
                # Show mapping summary
                st.write("### 📋 Field Mapping Summary")
                if field_mappings:
                    mapping_summary = []
                    for sf_field, csv_column in field_mappings.items():
                        mapping_summary.append({
                            "🏢 Salesforce Field": sf_field,
                            "📊 CSV Column": csv_column,
                            "✅ Status": "Mapped"
                        })
                    
                    mapping_df = pd.DataFrame(mapping_summary)
                    st.dataframe(mapping_df, use_container_width=True)
                    
                    # Show which CSV columns are not mapped
                    unmapped_csv = [col for col in csv_columns if col not in field_mappings.values()]
                    if unmapped_csv:
                        st.info(f"📝 **Unmapped CSV columns:** {unmapped_csv} (these won't be validated)")
                else:
                    st.warning("⚠️ No field mappings configured yet")
                
                # Show validation rules context
                st.write("### 📝 Validation Rules for Reference")
                st.info("These validation rules will be applied to the mapped fields")
                
                for i, rule in enumerate(validation_rules):
                    rule_name = rule.get('FullName', rule.get('name', f'Rule {i+1}'))
                    error_message = rule.get('ErrorMessage', rule.get('error_message', ''))
                    
                    with st.expander(f"Rule {i+1}: {rule_name}"):
                        st.write(f"**Error Message:** {error_message}")
                        
                        # Try to suggest which mapped field this rule might apply to
                        suggested_fields = []
                        for sf_field in field_mappings.keys():
                            if (sf_field.lower() in error_message.lower() or 
                                sf_field.lower() in rule_name.lower() or
                                ('name' in error_message.lower() and 'name' in sf_field.lower()) or
                                ('phone' in error_message.lower() and 'phone' in sf_field.lower()) or
                                ('email' in error_message.lower() and 'email' in sf_field.lower())):
                                suggested_fields.append(f"{sf_field} → {field_mappings[sf_field]}")
                        
                        if suggested_fields:
                            st.write(f"**Will validate:** {', '.join(suggested_fields)}")
                        else:
                            st.write("**Could apply to any mapped field**")
                
                # Store field mappings in validation rules for processing
                for rule in validation_rules:
                    rule['field_mappings'] = field_mappings
                
                # Validation readiness check
                if field_mappings:
                    st.success(f"✅ {len(field_mappings)} field mappings configured")
                    
                    if st.button("🚀 Run Custom Validation", type="primary", use_container_width=True):
                        run_custom_validation(selected_object, validation_data, validation_rules)
                else:
                    st.warning("⚠️ Configure at least one field mapping to run validation")
        
        else:
            st.info("No validation rules found. Extract rules first or create custom validation logic.")
            

def show_genai_validation(sf_conn):
    """GenAI validation interface"""
    
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
    
    st.subheader("🤖 GenAI Validation")
    
    # Main description and workflow
    st.markdown("""
    **GenAI Validation** converts your Salesforce validation rules into Python functions that can validate data outside of Salesforce.
    
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
    objects = get_salesforce_objects(sf_conn, filter_custom=True)
    
    if objects:
        selected_object = st.selectbox(
            "Select Salesforce Object",
            options=["Select an object..."] + objects,
            key="genai_validation_object",
            help="Choose the Salesforce object to extract validation rules from"
        )
        
        # Clear previous results when object changes
        if hasattr(st.session_state, 'current_genai_object'):
            if st.session_state.current_genai_object != selected_object:
                # Object changed - clear previous validation results
                if 'genai_validation_results' in st.session_state:
                    del st.session_state.genai_validation_results
                if 'genai_validation_completed' in st.session_state:
                    del st.session_state.genai_validation_completed
                if 'genai_original_data' in st.session_state:
                    del st.session_state.genai_original_data
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
        st.session_state.current_object = selected_object
        
        # NEW GENAI VALIDATION WORKFLOW
        st.markdown("---")
        st.markdown("## 🤖 **GenAI Validation Workflow**")
        st.markdown("*Convert Salesforce validation formulas to Python functions using AI*")
        
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
                # Get the organization name
                if hasattr(st.session_state, 'current_org') and st.session_state.current_org:
                    selected_org = st.session_state.current_org
                else:
                    # Get first org from credentials as fallback
                    try:
                        with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
                            credentials = json.load(f)
                        selected_org = list(credentials.keys())[0]
                        st.session_state.current_org = selected_org
                    except:
                        st.error("❌ Could not determine organization")
                        return
                
                # Extract Validation Rule Formulas (NEW LOGIC)
                st.info("🔍 Extracting validation rule formulas from Salesforce...")
                
                # Debug sf_conn object
                st.info("🔍 **Debug: Checking Salesforce connection...**")
                if sf_conn is None:
                    st.error("❌ sf_conn is None - no Salesforce connection available")
                    return
                
                st.write(f"   • Connection type: {type(sf_conn)}")
                if hasattr(sf_conn, 'session_id'):
                    st.write(f"   • Session ID: {sf_conn.session_id[:10] if sf_conn.session_id else 'None'}...")
                else:
                    st.error("   ❌ sf_conn missing session_id attribute")
                
                if hasattr(sf_conn, 'sf_instance'):
                    st.write(f"   • Instance: {sf_conn.sf_instance}")
                else:
                    st.error("   ❌ sf_conn missing sf_instance attribute")
                
                try:
                    # Use the enhanced extraction function
                    df, file_path = extract_validation_formulas_for_genai(sf_conn, selected_org, selected_object)
                    
                    if df is not None and len(df) > 0:
                        # Store in session state for persistent access
                        st.session_state.formula_extraction_complete = True
                        st.session_state.formula_df = df
                        st.session_state.formula_file_path = file_path
                        st.session_state.current_object = selected_object
                        
                        st.success(f"✅ Successfully extracted {len(df)} validation rule formulas!")
                        st.info(f"📁 Saved to: `{file_path}`")
                        
                        # Show preview of extracted formulas
                        st.markdown("**📋 Preview of Extracted Formulas:**")
                        with st.expander("View Formula Preview", expanded=True):
                            st.dataframe(df.head(), use_container_width=True)
                        
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
                            label="📥 Download Formula CSV",
                            data=csv_content,
                            file_name=f"{selected_object}_GenAI_Formula_validation.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="download_formula_csv"
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
                            file_name=f"{selected_object}_GenAI_Formula_validation.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            key="download_formula_excel"
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
                                                    key="immediate_bundle_download"
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
                                                    key="immediate_validator_download"
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
                                                key="immediate_report_download"
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
                                    key="download_bundle"
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
                                    key="download_validator"
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
                            use_container_width=True
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
                                        use_container_width=True
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
                    uploaded_file = st.file_uploader(
                        "📁 **Choose your data file:**",
                        type=['csv', 'xlsx', 'xls', 'psv'],
                        key="genai_data_upload",
                        help="Upload CSV, Excel, or PSV (Pipe-separated) files containing the data to validate"
                    )
                    
                    if uploaded_file is not None:
                        try:
                            # Read the uploaded file
                            df = load_data_file(uploaded_file)
                            if df is not None:
                                st.success(f"✅ Successfully loaded {len(df)} records from {uploaded_file.name}")
                                
                                # Show data preview
                                with st.expander("📊 Data Preview", expanded=False):
                                    st.markdown(f"**File:** {uploaded_file.name}")
                                    st.markdown(f"**Records:** {len(df)}")
                                    st.markdown(f"**Columns:** {', '.join(df.columns.tolist())}")
                                    st.dataframe(df.head(), use_container_width=True)
                            
                            # Field Mapping Interface
                            st.markdown("---")
                            st.markdown("### 🔗 **Field Mapping Configuration**")
                            st.info("📋 Map your CSV columns to Salesforce Object fields for accurate validation")
                            
                            # Get Salesforce object fields
                            try:
                                from .utils import get_object_description
                                sf_object_info = get_object_description(sf_conn, selected_object)
                                
                                if sf_object_info and 'fields' in sf_object_info:
                                    all_sf_fields = [field for field in sf_object_info['fields'] if field.get('updateable', True)]
                                    
                                    # Create field mapping interface
                                    csv_columns = list(df.columns)
                                    
                                    # Initialize field mappings in session state
                                    if 'genai_field_mappings' not in st.session_state:
                                        st.session_state.genai_field_mappings = {}
                                    
                                    # Auto-suggest mappings based on column names
                                    suggested_mappings = {}
                                    for csv_col in csv_columns:
                                        csv_col_lower = csv_col.lower().replace(' ', '').replace('_', '').replace('.', '').replace('-', '')
                                        best_match = None
                                        best_score = 0
                                        
                                        for sf_field in all_sf_fields:
                                            sf_field_name = sf_field['name'].lower()
                                            sf_field_label = sf_field.get('label', '').lower()
                                            
                                            # Calculate similarity score
                                            score = 0
                                            if csv_col_lower == sf_field_name.replace('__c', ''):
                                                score = 100  # Perfect match
                                            elif csv_col_lower in sf_field_name or sf_field_name in csv_col_lower:
                                                score = 80
                                            elif csv_col_lower in sf_field_label or sf_field_label in csv_col_lower:
                                                score = 60
                                            elif any(keyword in csv_col_lower and keyword in sf_field_name 
                                                   for keyword in ['name', 'phone', 'email', 'address', 'account', 'contact', 'date', 'status', 'type', 'number']):
                                                score = 40
                                            
                                            if score > best_score:
                                                best_score = score
                                                best_match = sf_field
                                        
                                        if best_match and best_score >= 40:
                                            suggested_mappings[csv_col] = best_match['name']
                                    
                                    st.markdown("**🎯 Column Mapping Configuration:**")
                                    
                                    # Mapping interface
                                    field_mappings = {}
                                    sf_field_options = ["⚠️ No mapping"] + [f"{field['name']} ({field.get('label', field['name'])})" for field in all_sf_fields]
                                    sf_field_names = [""] + [field['name'] for field in all_sf_fields]
                                    
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
                                            # Get current mapping or suggested mapping
                                            current_mapping = st.session_state.genai_field_mappings.get(csv_column, "")
                                            if not current_mapping and csv_column in suggested_mappings:
                                                current_mapping = suggested_mappings[csv_column]
                                            
                                            # Find index for current mapping
                                            current_index = 0
                                            if current_mapping:
                                                try:
                                                    current_index = sf_field_names.index(current_mapping)
                                                except ValueError:
                                                    current_index = 0
                                            
                                            selected_field = st.selectbox(
                                                f"Map {csv_column}",
                                                options=sf_field_options,
                                                index=current_index,
                                                key=f"genai_mapping_{i}_{csv_column}",
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
                                    else:
                                        st.warning("⚠️ No field mappings configured yet")
                                        st.info("💡 Configure at least one field mapping to run validation")
                                    
                                    # Store mappings for validation
                                    if mapped_fields:
                                        # Create mapped DataFrame with Salesforce field names
                                        mapped_df = df.copy()
                                        for csv_col, sf_field in mapped_fields.items():
                                            if csv_col != sf_field:
                                                mapped_df[sf_field] = mapped_df[csv_col]
                                        
                                        # Show mapped data preview
                                        st.markdown("### 👁️ **Mapped Data Preview**")
                                        with st.expander("View data with Salesforce field names", expanded=False):
                                            mapped_columns = list(mapped_fields.values())
                                            st.dataframe(mapped_df[mapped_columns].head(), use_container_width=True)
                                        
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
                                st.markdown("---")
                                display_genai_validation_results(st.session_state.genai_validation_results, selected_object)
                            
                        except Exception as e:
                            st.error(f"❌ Error reading file: {str(e)}")
                    
                    else:
                        st.info("📤 Upload a CSV or Excel file to start validation")
                
                else:
                    st.info("🤖 Complete Step 2 (Generate AI Bundle) first before uploading data")
            
            else:
                # No bundle generated - show message to complete Step 2 first
                st.info("🤖 Complete Step 2 (Generate AI Bundle) first before uploading data")
        
        # Step 4: Run Validation
        if validation_data is not None:
            st.write("### 🚀 Step 4: Run AI Validation")
            
            # Validation options
            col_opt1, col_opt2, col_opt3 = st.columns(3)
            
            with col_opt1:
                fail_fast = st.checkbox(
                    "Fail Fast Mode",
                    value=False,
                    help="Stop validation on first error"
                )
            
            with col_opt2:
                detailed_logging = st.checkbox(
                    "Detailed Logging",
                    value=True,
                    help="Include detailed validation logs"
                )
            
            with col_opt3:
                save_results = st.checkbox(
                    "Save Results to Files",
                    value=True,
                    help="Save validation results to CSV files"
                )
            
            # Run validation button
            if st.button("🚀 Run AI Validation", type="primary", use_container_width=True):
                run_genai_validation(
                    selected_object, 
                    validation_data, 
                    fail_fast=fail_fast,
                    detailed_logging=detailed_logging,
                    save_results=save_results
                )
        
        # Note: Step 5 results are now shown inline in Step 3 after validation completion

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
            ["All Validations", "Schema Validation", "Custom Validation", "GenAI Validation"],
            key="validation_report_type"
        )
        
        # Filter results based on report type
        if report_type != "All Validations":
            filtered_results = [r for r in validation_results if report_type.lower().replace(" ", "_") in r.get('type', '')]
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

def show_validation_summary():
    """Validation summary and data quality dashboard"""
    st.subheader("📋 Data Quality Dashboard")
    st.markdown("Comprehensive overview of data quality across all validation processes")
    
    if not st.session_state.current_org:
        st.warning("⚠️ Please select an organization first")
        return
    
    # Get comprehensive validation data
    validation_summary = get_comprehensive_validation_summary()
    
    if validation_summary:
        # Overall quality metrics
        show_quality_metrics(validation_summary)
        
        # Quality trends
        show_quality_trends(validation_summary)
        
        # Issue breakdown
        show_issue_breakdown(validation_summary)
        
        # Recommendations
        show_quality_recommendations(validation_summary)
    
    else:
        st.info("No validation data available for summary. Run validations to see quality metrics.")

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
                
                # Download schema
                csv_data = df_schema.to_csv(index=False)
                st.download_button(
                    label="📥 Download Schema",
                    data=csv_data,
                    file_name=f"{object_name}_schema.csv",
                    mime="text/csv",
                    key="download_schema_csv"
                )
    
    except Exception as e:
        st.error(f"❌ Error getting schema: {str(e)}")

def display_validation_rules_table(validation_rules, object_name):
    """Display validation rules in a clean table format"""
    if not validation_rules:
        st.info("No validation rules found")
        return
    
    # Prepare data for display
    table_data = []
    for rule in validation_rules:
        table_data.append({
            "Rule Name": rule.get('FullName', 'N/A'),
            "Active": "✅ Yes" if rule.get('Active', True) else "❌ No",
            "Error Field": rule.get('ErrorDisplayField', 'N/A'),
            "Error Message": rule.get('ErrorMessage', 'N/A')[:100] + "..." if len(rule.get('ErrorMessage', '')) > 100 else rule.get('ErrorMessage', 'N/A'),
            "Description": rule.get('Description', 'N/A')[:80] + "..." if rule.get('Description') and len(rule.get('Description', '')) > 80 else rule.get('Description', 'N/A')
        })
    
    # Create DataFrame and display
    df = pd.DataFrame(table_data)
    
    # Display with improved formatting
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Rule Name": st.column_config.TextColumn("Rule Name", width="medium"),
            "Active": st.column_config.TextColumn("Status", width="small"),
            "Error Field": st.column_config.TextColumn("Error Field", width="medium"),
            "Error Message": st.column_config.TextColumn("Error Message", width="large"),
            "Description": st.column_config.TextColumn("Description", width="large")
        }
    )



def generate_sample_data(sf_conn, object_name: str) -> Optional[pd.DataFrame]:
    """Generate sample data from Salesforce"""
    try:
        # Query sample records
        query = f"SELECT Id, Name FROM {object_name} LIMIT 10"
        result = sf_conn.query(query)
        
        if result['records']:
            # Remove Salesforce metadata
            clean_records = []
            for record in result['records']:
                clean_record = {k: v for k, v in record.items() if k != 'attributes'}
                clean_records.append(clean_record)
            
            return pd.DataFrame(clean_records)
        
        return None
    
    except Exception as e:
        st.error(f"❌ Error generating sample data: {str(e)}")
        return None

def run_schema_validation(sf_conn, object_name: str, data: pd.DataFrame, 
                         validate_required: bool, validate_datatypes: bool,
                         validate_formats: bool, validate_lengths: bool,
                         validate_picklists: bool, strict_mode: bool, field_mappings: dict):
    """Run comprehensive schema validation with enhanced validation logic and field mapping"""
    
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
                    validate_lengths, validate_picklists, field_mappings
                )
                
                # Update validation results
                if row_errors:
                    validation_results['failed_records'] += 1
                    validation_results['validation_errors'].extend(row_errors)
                    validation_results['record_errors'][str(index)] = row_errors
                    
                    # Categorize errors by field
                    for error in row_errors:
                        # Extract field name from error message
                        if "field '" in error:
                            field_name = error.split("field '")[1].split("'")[0]
                        elif "Required field '" in error:
                            field_name = error.split("Required field '")[1].split("'")[0]
                        elif "Duplicate value" in error and "field '" in error:
                            field_name = error.split("field '")[1].split("'")[0]
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
            # ID fields should be either empty or valid Salesforce ID format (15 or 18 chars)
            if value_str and len(value_str) not in [15, 18]:
                return f"Invalid Salesforce ID format in field '{field_name}': {value} (should be 15 or 18 characters)"
            return None
    
    except Exception as e:
        return f"Error validating field type for '{field_name}': {str(e)}"
    
    return None

def validate_field_length(field_name: str, value, field_info: dict) -> Optional[str]:
    """Validate field length according to Salesforce field definition"""
    if pd.isna(value) or str(value).strip() == "":
        return None
    
    value_str = str(value)
    field_type = field_info.get('type', '').lower()
    
    # Get length from field info if available
    length = field_info.get('length')
    
    if length is not None and len(value_str) > length:
        return f"Field '{field_name}' exceeds maximum length of {length} characters (current: {len(value_str)})"
    
    # Standard Salesforce field length limits for common field types
    type_length_limits = {
        'text': 255,
        'string': 255,
        'textarea': 32768,  # Long text area can be up to 32KB
        'longtextarea': 131072,  # Rich text area up to 128KB
        'email': 80,
        'phone': 40,
        'url': 255
    }
    
    if field_type in type_length_limits:
        max_length = type_length_limits[field_type]
        if len(value_str) > max_length:
            return f"Field '{field_name}' of type '{field_type}' exceeds maximum length of {max_length} characters (current: {len(value_str)})"
    
    return None
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
            # ID fields should be either empty or valid Salesforce ID format (15 or 18 chars)
            if value_str and len(value_str) not in [15, 18]:
                return f"Invalid Salesforce ID format in field '{field_name}': {value} (should be 15 or 18 characters)"
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
    """Validate field length"""
    try:
        max_length = field_info.get('length')
        if max_length and len(str(value)) > max_length:
            return f"Field '{field_name}' exceeds maximum length ({max_length}): {len(str(value))} characters"
    except:
        pass
    
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

def validate_comprehensive_row(df: pd.DataFrame, object_description: Dict, row_index: int, row_data: pd.Series, 
                             validate_required: bool, validate_datatypes: bool, validate_formats: bool,
                             validate_lengths: bool, validate_picklists: bool, field_mappings: dict) -> List[str]:
    """
    Perform comprehensive validation for a single row using field mappings
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
                    picklist_error = validate_picklist_value(sf_field_name, value, field_info)
                    if picklist_error:
                        # Update error message to include CSV column name
                        picklist_error = picklist_error.replace(f"field '{sf_field_name}'", f"field '{csv_column}' (mapped to '{sf_field_name}')")
                        errors.append(f"Row {row_index + 1}: {picklist_error}")
    
    except Exception as e:
        errors.append(f"Row {row_index + 1}: Error during comprehensive validation - {str(e)}")
    
    return errors

def validate_picklist_value(field_name: str, value, field_info: Dict) -> Optional[str]:
    """Validate picklist values"""
    try:
        field_type = field_info.get('type', '')
        if field_type in ['picklist', 'multipicklist']:
            picklist_values = field_info.get('picklistValues', [])
            if picklist_values:
                valid_values = [pv.get('value', '') for pv in picklist_values if pv.get('active', True)]
                if str(value) not in valid_values:
                    return f"Invalid picklist value in field '{field_name}': {value}"
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
        
        # Error type categorization
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
            if 'Required field' in error:
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
                'Field Name': field_name,
                'Error Count': len(field_error_list),
                'Error Rate': f"{(len(field_error_list)/results['total_records']*100):.1f}%"
            })
        
        field_error_df = pd.DataFrame(field_error_data)
        field_error_df = field_error_df.sort_values('Error Count', ascending=False)
        
        st.dataframe(field_error_df, use_container_width=True)
        
        # Detailed field errors
        for field_name, field_error_list in sorted(results['field_errors'].items(), key=lambda x: len(x[1]), reverse=True):
            with st.expander(f"Field: {field_name} ({len(field_error_list)} errors)", expanded=False):
                for error in field_error_list[:15]:  # Show first 15 errors per field
                    st.text(f"• {error}")
                if len(field_error_list) > 15:
                    st.info(f"... and {len(field_error_list) - 15} more errors for this field")

    # Field-wise error summary
    if results['field_errors']:
        with st.expander("📊 Field-wise Error Summary", expanded=False):
            field_error_data = []
            for field, errors in results['field_errors'].items():
                field_error_data.append({
                    "Field": field,
                    "Error Count": len(errors),
                    "Error Rate": f"{(len(errors)/results['total_records']*100):.1f}%"
                })
            
            df_field_errors = pd.DataFrame(field_error_data)
            st.dataframe(df_field_errors, use_container_width=True)
    
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
            
            # Add validation status column
            validated_data_with_results['Validation_Status'] = ['PASSED' if i < results['passed_records'] else 'FAILED' 
                                                               for i in range(len(validated_data_with_results))]
            
            # Add specific errors for each record if available
            record_errors = results.get('record_errors', {})
            validated_data_with_results['Validation_Errors'] = ''
            
            for idx, row in validated_data_with_results.iterrows():
                if str(idx) in record_errors:
                    validated_data_with_results.at[idx, 'Validation_Errors'] = '; '.join(record_errors[str(idx)])
                elif validated_data_with_results.at[idx, 'Validation_Status'] == 'FAILED':
                    validated_data_with_results.at[idx, 'Validation_Errors'] = 'Validation failed (details not specified)'
            
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
        
        st.download_button(
            label="📊 Download Complete Results (CSV)",
            data=csv_data,
            file_name=f"{object_name}_{validation_type.lower().replace(' ', '_')}_complete_results.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
            key="complete_results_csv",
            help="Download complete validation results including original data with validation status"
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
            key="complete_results_json"
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
                display_validation_rules_ui(validation_rules, object_name)
                return validation_rules
            else:
                st.error(f"❌ No validation rules found for {object_name}")
                return None
            
    except Exception as e:
        st.error(f"❌ Error extracting validation rules: {str(e)}")
        return None

def display_validation_rules_ui(validation_rules, object_name):
    """Display validation rules in a comprehensive UI"""
    
    # Summary metrics
    active_rules = [rule for rule in validation_rules if rule.get('Active')]
    inactive_rules = [rule for rule in validation_rules if not rule.get('Active')]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Rules", len(validation_rules))
    with col2:
        st.metric("Active Rules", len(active_rules))
    with col3:
        st.metric("Inactive Rules", len(inactive_rules))
    
    # Display rules in a table
    st.subheader("📋 Validation Rules Details")
    
    # Prepare data for display
    rules_data = []
    for rule in validation_rules:
        rules_data.append({
            "Rule Name": rule.get('FullName', 'N/A'),
            "Status": "✅ Active" if rule.get('Active') else "❌ Inactive",
            "Error Field": rule.get('ErrorDisplayField', 'N/A'),
            "Error Message": (rule.get('ErrorMessage', 'N/A')[:80] + '...') if len(rule.get('ErrorMessage', '')) > 80 else rule.get('ErrorMessage', 'N/A'),
            "Description": (rule.get('Description', 'N/A')[:50] + '...') if len(rule.get('Description', '')) > 50 else rule.get('Description', 'N/A'),
        })
    
    # Display as DataFrame
    df_rules = pd.DataFrame(rules_data)
    st.dataframe(df_rules, use_container_width=True)
    
    # Download options
    st.subheader("💾 Export Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Download as CSV
        csv_data = df_rules.to_csv(index=False)
        st.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f"{object_name}_validation_rules.csv",
            mime="text/csv"
        )
    
    with col2:
        # Download detailed JSON
        json_data = json.dumps(validation_rules, indent=2, default=str)
        st.download_button(
            label="📋 Download as JSON",
            data=json_data,
            file_name=f"{object_name}_validation_rules.json",
            mime="application/json"
        )
    
    # Detailed view with expanders
    st.subheader("🔍 Detailed Rule Information")
    
    for i, rule in enumerate(validation_rules):
        status_icon = "✅" if rule.get('Active') else "❌"
        rule_name = rule.get('FullName', f'Rule {i+1}')
        
        with st.expander(f"{status_icon} {rule_name}"):
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Basic Information:**")
                st.write(f"**Rule Name:** {rule_name}")
                st.write(f"**Active:** {'Yes' if rule.get('Active') else 'No'}")
                st.write(f"**Error Field:** {rule.get('ErrorDisplayField', 'N/A')}")
                st.write(f"**Rule ID:** {rule.get('Id', 'N/A')}")
            
            with col2:
                st.write("**Additional Details:**")
                st.write(f"**Description:** {rule.get('Description', 'N/A')}")
                if rule.get('CreatedDate'):
                    st.write(f"**Created:** {rule.get('CreatedDate', 'N/A')[:10]}")
                if rule.get('LastModifiedDate'):
                    st.write(f"**Last Modified:** {rule.get('LastModifiedDate', 'N/A')[:10]}")
            
            st.write("**Error Message:**")
            st.code(rule.get('ErrorMessage', 'N/A'), language="text")
            
            if rule.get('ValidationRule__c'):
                st.write("**Validation Formula:**")
                st.code(rule.get('ValidationRule__c', 'N/A'), language="text")
def create_sf_validation_client(sf_conn):
    """Create Salesforce validation client"""
    from .sf_validation_client import SalesforceValidationClient
    return SalesforceValidationClient(sf_conn)

def get_salesforce_objects(sf_conn, filter_custom=False) -> List[str]:
    """Get Salesforce objects list"""
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

def run_custom_validation(object_name: str, data: pd.DataFrame, rules: list):
    """Run custom validation against Salesforce validation rules"""
    try:
        if not rules:
            st.error("❌ No validation rules found for this object")
            return
            
        if data.empty:
            st.error("❌ No data to validate")
            return
        
        # Process validation rules silently
        
        # Check source of rules  
        sources = set(rule.get('source', 'sf_validation_client') for rule in rules)
        
        if 'sample_data' in sources:
            st.info("ℹ️ **Using sample validation rules** - these have working formulas for testing")
        
        # Rule details are processed silently (removed from UI display)
        
        # Manual formula configuration
        if st.session_state.get('show_manual_formula_config', False):
            st.subheader("🛠️ Manual Formula Configuration")
            st.info("Enter validation formulas for rules that don't have them accessible via API")
            
            updated_rules = []
            for rule in rules:
                formula = rule.get('ValidationFormula', rule.get('formula', ''))
                if not formula or formula == 'FORMULA_NOT_ACCESSIBLE_VIA_API':
                    rule_name = rule.get('FullName', rule.get('name', 'Unknown Rule'))
                    error_message = rule.get('ErrorMessage', '')
                    
                    st.write(f"**{rule_name}**")
                    st.write(f"Error Message: {error_message}")
                    
                    # Suggest formula based on error message
                    suggested_formula = ""
                    if 'required' in error_message.lower() or 'blank' in error_message.lower():
                        error_field = rule.get('ErrorDisplayField', 'FieldName')
                        suggested_formula = f"ISBLANK({error_field})"
                    
                    new_formula = st.text_input(
                        f"Formula for {rule_name}:",
                        value=suggested_formula,
                        help="Enter Salesforce validation formula (returns TRUE when invalid)"
                    )
                    
                    if new_formula:
                        rule['ValidationFormula'] = new_formula
                        rule['formula'] = new_formula
                
                updated_rules.append(rule)
            
            if st.button("✅ Apply Manual Formulas"):
                rules = updated_rules
                st.session_state.show_manual_formula_config = False
                st.success("✅ Manual formulas applied!")
                st.rerun()
            
        # Add debug mode toggle
        debug_mode = st.checkbox("🔍 Enable Debug Mode", value=True, help="Show detailed validation debugging information")
        
        with st.spinner("🔍 Running custom validation..."):
            
            # Initialize results
            validation_results = []
            valid_records = []
            invalid_records = []
            error_summary = []
            
            st.info(f"📊 Validating {len(data)} records against {len(rules)} validation rules...")
            
            # Quick validation test
            active_rules = [r for r in rules if r.get('Active', True)]
            st.info(f"🔍 Found {len(active_rules)} active validation rules out of {len(rules)} total rules")
            
            # CRITICAL: Check if field mappings are configured
            rules_with_mappings = [r for r in active_rules if r.get('field_mappings', {})]
            rules_without_mappings = [r for r in active_rules if not r.get('field_mappings', {})]
            
            if rules_without_mappings:
                st.error(f"❌ **CRITICAL VALIDATION ISSUE**: {len(rules_without_mappings)} rules have no field mappings!")
                st.warning("**⚠️ Records may be incorrectly classified as VALID because validation rules cannot be applied without field mappings.**")
                st.info("**💡 Solution**: Configure field mappings in the Custom Validation interface before running validation.")
                
                with st.expander("View rules without field mappings"):
                    for rule in rules_without_mappings:
                        rule_name = rule.get('FullName', rule.get('name', 'Unknown Rule'))
                        error_msg = rule.get('ErrorMessage', 'No error message')
                        st.write(f"• **{rule_name}**: {error_msg}")
                
                st.warning("**🚨 RECOMMENDATION**: Fix field mappings before proceeding with validation to ensure accurate results.")
            
            if rules_with_mappings:
                st.success(f"✅ {len(rules_with_mappings)} rules have proper field mappings configured")
                
                # Show which fields are being validated
                all_mapped_fields = set()
                for rule in rules_with_mappings:
                    rule_mappings = rule.get('field_mappings', {})
                    all_mapped_fields.update(rule_mappings.values())
                
                if all_mapped_fields:
                    st.info(f"🎯 **Fields being validated**: {', '.join(sorted(all_mapped_fields))}")
            else:
                st.error("❌ **NO RULES CAN BE APPLIED** - All validation rules are missing field mappings!")
                st.stop()
            
            # Show available CSV columns for field mapping
            if debug_mode:
                st.write("**📋 Available CSV Columns:**")
                st.write(f"`{list(data.columns)}`")
                st.divider()
            
            # Show validation rules being used
            if debug_mode:
                # Show a summary without detailed debug output
                pass
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Process each record
            validation_debug_info = []
            
            for idx, row in data.iterrows():
                status_text.text(f"Validating record {idx + 1}/{len(data)}")
                progress_bar.progress((idx + 1) / len(data))
                
                record_valid = True
                record_errors = []
                record_debug = {"record_index": idx, "rules_applied": [], "field_values": {}}
                
                if debug_mode and idx < 2:  # Show debug for first 2 records
                    record_debug["show_debug"] = True
                
                # Apply each validation rule
                for rule in rules:
                    if not rule.get('Active', True):
                        continue  # Skip inactive rules
                    
                    rule_name = rule.get('FullName', rule.get('name', rule.get('display_name', 'Unknown Rule')))
                    error_message = rule.get('ErrorMessage', rule.get('error_message', f'Validation failed for {rule_name}'))
                    error_field = rule.get('ErrorDisplayField', rule.get('error_field', 'Unknown Field'))
                    field_mappings = rule.get('field_mappings', {})
                    
                    # ENHANCED DEBUG INFO: Track which fields are being validated
                    if field_mappings:
                        for sf_field, csv_column in field_mappings.items():
                            if csv_column in row.index:
                                field_value = row[csv_column]
                                record_debug["field_values"][f"{csv_column} -> {sf_field}"] = field_value
                    
                    # Apply validation rule logic
                    rule_passed = apply_validation_rule(row, rule)
                    
                    rule_debug_info = {
                        "rule_name": rule_name,
                        "rule_passed": rule_passed,
                        "field_mappings": field_mappings,
                        "error_message": error_message
                    }
                    record_debug["rules_applied"].append(rule_debug_info)
                    
                    if debug_mode and idx < 2:
                        # Debug output for first few records
                        pass  # Keep logic but hide output to avoid clutter
                    
                    if not rule_passed:
                        record_valid = False
                        record_errors.append({
                            'rule_name': rule_name,
                            'error_message': error_message,
                            'error_field': error_field,
                            'record_index': idx,
                            'field_mappings': field_mappings
                        })
                
                record_debug["final_result"] = record_valid
                validation_debug_info.append(record_debug)
                
                if debug_mode and idx < 2:
                    # Show detailed debug info for first few records
                    pass  # Debug output handled separately to avoid UI clutter
                
                # Store validation result
                validation_results.append({
                    'index': idx,
                    'is_valid': record_valid,
                    'errors': record_errors
                })
                
                # Categorize record
                if record_valid:
                    valid_records.append(idx)
                else:
                    invalid_records.append(idx)
                    error_summary.extend(record_errors)
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Create result DataFrames
            valid_df = data.iloc[valid_records].copy() if valid_records else pd.DataFrame(columns=data.columns)
            invalid_df = data.iloc[invalid_records].copy() if invalid_records else pd.DataFrame(columns=data.columns)
            
            # Display results with enhanced analysis
            st.success("✅ Custom validation completed!")
            
            # Enhanced summary metrics with validation effectiveness
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Records", len(data))
            
            with col2:
                success_rate = (len(valid_df) / len(data)) * 100 if len(data) > 0 else 0
                st.metric("Valid Records", len(valid_df), delta=f"{success_rate:.1f}%")
            
            with col3:
                failure_rate = (len(invalid_df) / len(data)) * 100 if len(data) > 0 else 0
                st.metric("Invalid Records", len(invalid_df), delta=f"{failure_rate:.1f}%")
            
            with col4:
                st.metric("Success Rate", f"{success_rate:.1f}%")
            
            # ENHANCED VALIDATION EFFECTIVENESS ANALYSIS
            st.subheader("📊 Validation Analysis")
            
            # Show validation effectiveness
            effectiveness_col1, effectiveness_col2 = st.columns(2)
            
            with effectiveness_col1:
                st.write("**🎯 Validation Rule Effectiveness:**")
                rules_applied = len([r for r in active_rules if r.get('field_mappings', {})])
                rules_skipped = len([r for r in active_rules if not r.get('field_mappings', {})])
                
                st.write(f"• Rules applied: {rules_applied}")
                st.write(f"• Rules skipped (no mappings): {rules_skipped}")
                
                if rules_skipped > 0:
                    st.warning(f"⚠️ {rules_skipped} rules were skipped due to missing field mappings")
            
            with effectiveness_col2:
                st.write("**📈 Record Classification:**")
                if len(invalid_df) == 0 and rules_skipped > 0:
                    st.warning("⚠️ All records classified as VALID - this may be due to missing field mappings")
                elif len(invalid_df) > 0:
                    st.success("✅ Validation rules successfully identified invalid records")
                else:
                    st.info("ℹ️ All records passed validation")
            
            st.divider()
            
            # Show validation details
            if len(invalid_df) > 0:
                st.subheader("❌ Validation Errors")
                
                # Group errors by rule
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
                
                # Show detailed invalid records
                st.subheader("📋 Invalid Records Details")
                with st.expander(f"View {len(invalid_df)} invalid records", expanded=False):
                    st.dataframe(invalid_df, use_container_width=True, height=300)
            
            # Show valid records
            if len(valid_df) > 0:
                st.subheader("✅ Valid Records")
                with st.expander(f"View {len(valid_df)} valid records", expanded=False):
                    st.dataframe(valid_df, use_container_width=True, height=300)
            
            # Save results
            st.subheader("💾 Save Results")
            
            col_save1, col_save2 = st.columns(2)
            
            with col_save1:
                if len(valid_df) > 0:
                    csv_valid = valid_df.to_csv(index=False)
                    st.download_button(
                        label=f"⬇️ Download Valid Records ({len(valid_df)})",
                        data=csv_valid,
                        file_name=f"{object_name}_valid_records.csv",
                        mime="text/csv",
                        type="primary"
                    )
            
            with col_save2:
                if len(invalid_df) > 0:
                    csv_invalid = invalid_df.to_csv(index=False)
                    st.download_button(
                        label=f"⬇️ Download Invalid Records ({len(invalid_df)})",
                        data=csv_invalid,
                        file_name=f"{object_name}_invalid_records.csv",
                        mime="text/csv",
                        type="secondary"
                    )
            
            # Save results to session state for other modules
            if 'validation_results' not in st.session_state:
                st.session_state.validation_results = {}
            
            st.session_state.validation_results[object_name] = {
                'valid_df': valid_df,
                'invalid_df': invalid_df,
                'validation_summary': {
                    'total_records': len(data),
                    'valid_records': len(valid_df),
                    'invalid_records': len(invalid_df),
                    'success_rate': success_rate,
                    'error_summary': error_summary
                }
            }
            
            st.success(f"🎉 Validation complete! {len(valid_df)} valid, {len(invalid_df)} invalid out of {len(data)} total records.")
            
            # Show validation analysis summary
            st.markdown("---")
            st.subheader("📊 Validation Analysis Summary")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📋 Total Rules Analyzed", len(rules))
            with col2:
                rules_with_mappings = sum(1 for rule in rules if rule.get('field_mappings'))
                st.metric("🎯 Rules with Field Mappings", rules_with_mappings)
            with col3:
                rules_missing_mappings = len(rules) - rules_with_mappings
                st.metric("⚠️ Rules Missing Mappings", rules_missing_mappings)
            
            st.info("💡 **Smart Error Message Analysis**: The system automatically detects validation types by analyzing error messages, rule descriptions, and field names to provide validation without requiring manual formula configuration. Custom validation only is not enough there might be some other issues to be addressed so proceed with the GenAI validation.")
            
            # ENHANCED: Add validation recommendations
            if rules_missing_mappings > 0:
                st.warning("**📋 Recommendations:**")
                st.write("1. Configure field mappings for all validation rules to ensure accurate results")
                st.write("2. Review which fields are truly required vs optional in your Salesforce org")
                st.write("3. Consider using GenAI validation for additional validation coverage")
            elif len(invalid_df) == 0:
                st.info("**✅ All records are valid!** Consider using GenAI validation to double-check for any missed validation scenarios.")
            else:
                st.success("**🎯 Validation completed successfully!** Review the invalid records and fix the identified issues before data load.")
                
    except Exception as e:
        st.error(f"❌ Error running enhanced custom validation: {str(e)}")
        st.exception(e)

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
            # Load credentials
            with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
                credentials = json.load(f)
            
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
                    use_container_width=True
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
                # Fallback to loading from file
                with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
                    credentials = json.load(f)
                selected_org = list(credentials.keys())[0]
            
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
                        use_container_width=True
                    )
                
                with col2:
                    st.info('**Validator Script**')
                    st.download_button(
                        label="📥 Download Validator.py",
                        data=validator_content,
                        file_name=f"{object_name}_validator.py",
                        mime="text/python",
                        use_container_width=True
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
                key="persistent_bundle_download"
            )
        
        with col2:
            st.info('**Validator Script**')
            st.download_button(
                label="📥 Download Validator.py",
                data=st.session_state.genai_validator_content,
                file_name=f"{object_name}_validator.py",
                mime="text/python",
                use_container_width=True,
                key="persistent_validator_download"
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
            objects = get_salesforce_objects(sf_conn, filter_custom=True)
            
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
                        mime='text/csv' if file_path.endswith('.csv') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
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
            # Fallback to loading from file
            try:
                with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
                    credentials = json.load(f)
                selected_org = list(credentials.keys())[0]
            except:
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
                        with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
                            credentials = json.load(f)
                        selected_org = list(credentials.keys())[0]
                    except:
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
            debug_mode = st.checkbox("🔍 Enable GenAI Validation Debug Mode", value=False)
            
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
                        key="genai_valid_download"
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
                        key="genai_invalid_download"
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
            return pd.read_csv(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            return pd.read_excel(file_path)
        else:
            st.error(f"Unsupported file format: {file_path}")
            return None
    except Exception as e:
        st.error(f"Error loading file {file_path}: {e}")
        return None



def generate_sample_data(sf_conn, object_name: str) -> Optional[pd.DataFrame]:
    """Generate sample data for testing validation"""
    try:
        with st.spinner(f"🎲 Generating sample data for {object_name}..."):
            # Get object description to understand fields
            try:
                obj_description = sf_conn.describe(object_name)
                fields = obj_description.get('fields', [])
                
                # Create sample data based on field types
                sample_data = {}
                num_records = 10  # Generate 10 sample records
                
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
                
            except Exception as e:
                # Fallback to generic sample data
                st.warning(f"Could not fetch object description, creating generic sample data: {e}")
                
                generic_data = {
                    'Name': [f'Sample Record {i+1}' for i in range(10)],
                    'Email': [f'user{i+1}@example.com' for i in range(10)],
                    'Phone': [f'555-000{i:04d}' for i in range(10)],
                    'Status': ['Active' if i % 2 == 0 else 'Inactive' for i in range(10)],
                    'Value': [i * 100 for i in range(10)]
                }
                
                return pd.DataFrame(generic_data)
                
    except Exception as e:
        st.error(f"Error generating sample data: {e}")
        return None

def get_validation_results() -> List[Dict]:
    """Get validation results"""
    return []

def show_validation_results_summary(results: List[Dict]):
    """Show validation results summary"""
    st.write("Validation results summary coming soon...")

def show_validation_result_detail(result: Dict):
    """Show detailed validation result"""
    st.write("Detailed validation result coming soon...")

def get_comprehensive_validation_summary() -> Optional[Dict]:
    """Get comprehensive validation summary"""
    return None

def show_quality_metrics(summary: Dict):
    """Show quality metrics"""
    st.write("Quality metrics coming soon...")

def show_quality_trends(summary: Dict):
    """Show quality trends"""
    st.write("Quality trends coming soon...")

def show_issue_breakdown(summary: Dict):
    """Show issue breakdown"""
    st.write("Issue breakdown coming soon...")

def show_quality_recommendations(summary: Dict):
    """Show quality recommendations"""
    st.write("Quality recommendations coming soon...")

def save_validation_results(results: Dict, object_name: str, validation_type: str):
    """Save validation results to file and return file path"""
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
            
            # Show sample of what we found for debugging
            st.info("🔍 **Debug: Sample of retrieved data:**")
            for i, record in enumerate(records[:2]):  # Show first 2 records
                st.write(f"   Rule {i+1}: {record.get('ValidationName', 'No name')}")
                st.write(f"   Formula: {record.get('ErrorConditionFormula', 'No formula')[:100]}...")
                st.write(f"   Active: {record.get('Active', 'Unknown')}")
                st.write("   ---")
        
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
            
            # Create enhanced file paths for both CSV and Excel
            root_folder = "DataFiles"
            object_folder = os.path.join(root_folder, org_name, object_name)
            os.makedirs(object_folder, exist_ok=True)
            
            # Save as both CSV and Excel for user convenience
            csv_file_path = os.path.join(object_folder, "GenAI_Formula_validation.csv")
            excel_file_path = os.path.join(object_folder, "GenAI_Formula_validation.xlsx")
            
            # Save CSV
            df.to_csv(csv_file_path, index=False)
            
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
                
            return df, csv_file_path
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
        
        # Get the function mappings from the AI bundle result
        function_mappings = ai_bundle_result.get('function_mappings', [])
        bundle_path = ai_bundle_result.get('bundle_path')
        num_functions = ai_bundle_result.get('num_functions', 0)
        
        # Check if we have validation functions either through function_mappings or num_functions
        if not function_mappings and num_functions == 0:
            return {'success': False, 'error': 'No validation functions found in AI bundle'}
        
        if not bundle_path or not os.path.exists(bundle_path):
            return {'success': False, 'error': 'AI bundle file not found'}
        
        # Import the validation bundle dynamically
        # Clean up any existing module to avoid conflicts
        if 'validation_bundle' in sys.modules:
            del sys.modules['validation_bundle']
            
        spec = importlib.util.spec_from_file_location("validation_bundle", bundle_path)
        validation_module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(validation_module)
        except Exception as e:
            return {'success': False, 'error': f'Failed to load validation bundle: {e}. Bundle file may be corrupted or incomplete.'}
        
        # Debug: Check what functions are available in the module
        available_functions = [name for name in dir(validation_module) if callable(getattr(validation_module, name)) and not name.startswith('_')]
        st.info(f"🔍 Debug: Bundle contains {len(available_functions)} functions: {', '.join(available_functions[:10])}{'...' if len(available_functions) > 10 else ''}")
        
        # Check for required functions
        has_validate_dataframe = hasattr(validation_module, 'validate_dataframe')
        has_validate_record = hasattr(validation_module, 'validate_record')
        st.info(f"🔍 Debug: validate_dataframe={has_validate_dataframe}, validate_record={has_validate_record}")
        
        if not has_validate_dataframe:
            return {'success': False, 'error': 'validate_dataframe function missing from bundle. Bundle generation may have failed - please regenerate in Step 2.'}
            
        # Check bundle file size for completeness
        bundle_size = os.path.getsize(bundle_path)
        st.info(f"🔍 Debug: Bundle file size: {bundle_size} bytes")
        
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
            'validation_results': validation_results  # Include raw validation results
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
                csv_data = valid_display_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Valid Records",
                    data=csv_data,
                    file_name=f"{object_name}_valid_records.csv",
                    mime="text/csv"
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
                csv_data = invalid_display_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Invalid Records",
                    data=csv_data,
                    file_name=f"{object_name}_invalid_records.csv",
                    mime="text/csv"
                )
            else:
                st.info("All records are valid!")
        
        with tab3:
            st.markdown(f"**All {validation_results['total_records']} records:**")
            all_display_df = convert_to_original_columns(validation_results['all_df'])
            st.dataframe(all_display_df, use_container_width=True, height=400)
            
            # Download button for all records
            csv_data = all_display_df.to_csv(index=False)
            st.download_button(
                label="📥 Download All Records",
                data=csv_data,
                file_name=f"{object_name}_all_validation_results.csv",
                mime="text/csv"
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
