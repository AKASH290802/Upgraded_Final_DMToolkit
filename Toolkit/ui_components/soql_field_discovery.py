"""
SOQL Query-Based Field Discovery for Data Loading
Allows users to write custom SOQL queries to discover available fields including relationship fields
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Tuple
import json


def parse_soql_query(query: str) -> Tuple[List[str], str]:
    """
    Parse SOQL query to extract SELECT fields and FROM object
    
    Args:
        query: SOQL query string
    
    Returns:
        Tuple of (fields_list, object_name)
    """
    try:
        # Normalize query
        query = query.strip()
        
        # Extract SELECT clause
        select_start = query.upper().find('SELECT') + 6
        from_start = query.upper().find('FROM')
        
        if select_start < 6 or from_start < 0:
            return None, None
        
        select_clause = query[select_start:from_start].strip()
        
        # Extract FROM object
        from_end = query.upper().find('WHERE')
        if from_end < 0:
            from_end = query.upper().find('LIMIT')
        if from_end < 0:
            from_end = len(query)
        
        from_clause = query[from_start+4:from_end].strip()
        object_name = from_clause.split()[0]
        
        # Parse fields
        fields = [f.strip() for f in select_clause.split(',')]
        fields = [f for f in fields if f]  # Remove empty
        
        return fields, object_name
    
    except Exception as e:
        return None, None


def execute_soql_query(sf_conn, query: str) -> Tuple[pd.DataFrame, List[str], str]:
    """
    Execute SOQL query and extract fields
    
    Args:
        sf_conn: Salesforce connection
        query: SOQL query string
    
    Returns:
        Tuple of (results_df, available_fields, object_name)
    """
    try:
        # Parse query first
        select_fields, object_name = parse_soql_query(query)
        
        if not select_fields or not object_name:
            return None, None, None
        
        # Execute query
        results = sf_conn.query(query)
        
        if results['totalSize'] == 0:
            return pd.DataFrame(), select_fields, object_name
        
        # Convert to DataFrame
        records = results['records']
        
        # Flatten relationship fields
        flattened_data = []
        for record in records:
            flat_record = {}
            flatten_record(record, flat_record)
            flattened_data.append(flat_record)
        
        df = pd.DataFrame(flattened_data)
        
        return df, select_fields, object_name
    
    except Exception as e:
        return None, None, None


def flatten_record(record: dict, flat_record: dict, prefix: str = ''):
    """
    Flatten nested relationship fields in Salesforce record
    
    Args:
        record: Salesforce record (may contain nested relationships)
        flat_record: Dictionary to store flattened data
        prefix: Prefix for nested fields
    """
    for key, value in record.items():
        if key == 'attributes':
            continue
        
        if isinstance(value, dict) and 'attributes' in value:
            # This is a relationship - recurse
            new_prefix = f"{prefix}{key}." if prefix else f"{key}."
            flatten_record(value, flat_record, new_prefix)
        else:
            full_key = f"{prefix}{key}" if prefix else key
            flat_record[full_key] = value


def show_soql_discovery_ui(sf_conn, target_object: str) -> Dict[str, str]:
    """
    Display SOQL query discovery interface
    
    Args:
        sf_conn: Salesforce connection
        target_object: Target object name
    
    Returns:
        Dictionary of CSV column → Salesforce field mappings
    """
    st.markdown("### 🔍 Custom SOQL Query Field Discovery")
    
    # SOQL Query Input
    with st.expander("✏️ Write SOQL Query", expanded=True):
        soql_query = st.text_area(
            "Enter your SOQL query:",
            value=f"SELECT Id, Name FROM {target_object} LIMIT 10",
            height=150,
            key="soql_query_input"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            execute_button = st.button("🔍 Execute Query & Discover Fields")
        
        with col2:
            example_button = st.button("📝 Show Example Query")
        
        if example_button:
            st.code(f"""SELECT Id, Name, 
       Description, 
       Owner.Name,
       CreatedBy.Name
FROM {target_object}
LIMIT 100""", language="sql")
    
    # Execute Query
    if execute_button:
        with st.spinner("Executing query..."):
            df, select_fields, found_object = execute_soql_query(sf_conn, soql_query)
            
            if df is not None and not df.empty:
                st.success(f"✅ Query executed successfully - Found {len(df)} records")
                
                # Show discovered fields
                st.write("**📊 Discovered Fields:**")
                available_fields = df.columns.tolist()
                
                # Display in columns
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("**Standard Fields:**")
                    for field in available_fields:
                        if '.' not in field:
                            st.write(f"  • `{field}`")
                
                with col2:
                    st.write("**Related Fields:**")
                    for field in available_fields:
                        if '.' in field:
                            st.write(f"  • `{field}`")
                
                with col3:
                    st.write("**Sample Data:**")
                    st.dataframe(df.head(3), use_container_width=True)
                
                # Store in session for mapping
                st.session_state['soql_fields'] = available_fields
                st.session_state['soql_results'] = df
                
                return available_fields
            
            elif df is not None and df.empty:
                st.warning("⚠️ Query executed but returned no records")
                available_fields = select_fields
                st.write("**📊 Fields in query:**")
                for field in available_fields:
                    st.write(f"  • `{field}`")
                st.session_state['soql_fields'] = available_fields
                return available_fields
            
            else:
                st.error("❌ Error executing query. Check syntax and try again.")
                return []


def create_mapping_from_soql_fields(csv_columns: List[str], soql_fields: List[str]) -> Dict[str, str]:
    """
    Create field mapping interface for SOQL-discovered fields
    
    Args:
        csv_columns: List of CSV column names
        soql_fields: List of Salesforce fields (including relationship fields)
    
    Returns:
        Dictionary of CSV column → Salesforce field mappings
    """
    st.markdown("### 🔗 Map CSV Columns to Discovered Fields")
    
    field_mappings = {}
    soql_options = ["-- Skip Field --"] + soql_fields
    
    # Create mapping table
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col1:
        st.write("**CSV Column**")
    with col2:
        st.write("**Maps to Salesforce Field**")
    with col3:
        st.write("**Field Type**")
    
    st.divider()
    
    for csv_col in csv_columns:
        col1, col2, col3 = st.columns([2, 3, 2])
        
        with col1:
            st.write(f"**{csv_col}**")
        
        with col2:
            # Try to auto-suggest
            suggested_field = suggest_field_for_column(csv_col, soql_fields)
            default_index = 0
            
            if suggested_field in soql_options:
                default_index = soql_options.index(suggested_field)
            
            selected_field = st.selectbox(
                f"Map {csv_col}",
                options=soql_options,
                index=default_index,
                key=f"soql_map_{csv_col}",
                label_visibility="collapsed"
            )
            
            field_mappings[csv_col] = selected_field
        
        with col3:
            if selected_field != "-- Skip Field --":
                # Show field type indicator
                if '.' in selected_field:
                    st.caption("🔗 Related Field")
                else:
                    st.caption("📄 Field")
    
    return field_mappings


def suggest_field_for_column(csv_col: str, soql_fields: List[str]) -> str:
    """
    Suggest a SOQL field for a CSV column
    
    Args:
        csv_col: CSV column name
        soql_fields: List of available SOQL fields
    
    Returns:
        Suggested field name
    """
    csv_lower = csv_col.lower().replace('_', '').replace(' ', '')
    
    # Exact match first
    for field in soql_fields:
        field_lower = field.lower().replace('_', '').replace(' ', '').replace('.', '')
        if csv_lower == field_lower:
            return field
    
    # Partial match
    for field in soql_fields:
        field_lower = field.lower().replace('_', '').replace(' ', '').replace('.', '')
        if csv_lower in field_lower or field_lower in csv_lower:
            return field
    
    return "-- Skip Field --"


def validate_soql_field_mapping(field_mappings: Dict[str, str], df: pd.DataFrame = None) -> Tuple[bool, str]:
    """
    Validate that field mappings are valid
    
    Args:
        field_mappings: Mapping dictionary
        df: Optional DataFrame with sample data
    
    Returns:
        Tuple of (is_valid, message)
    """
    # Check if any fields are mapped
    mapped_count = sum(1 for v in field_mappings.values() if v != "-- Skip Field --")
    
    if mapped_count == 0:
        return False, "❌ No fields mapped. Please select at least one field to load."
    
    # Check if relationship fields are used
    relationship_fields = [f for f in field_mappings.values() if '.' in f]
    
    if relationship_fields:
        msg = f"✅ Mapping valid with {mapped_count} fields ({len(relationship_fields)} relationship fields)"
        return True, msg
    else:
        msg = f"✅ Mapping valid with {mapped_count} fields"
        return True, msg
