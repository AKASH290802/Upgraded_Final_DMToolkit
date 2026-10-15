"""
Relationship Field Handler for Data Loading
Processes data mapped to relationship fields (e.g., WOD_2__Dealer__r.DealerCode)
"""

import pandas as pd
from typing import Dict, List, Tuple
import re


def parse_relationship_field(field_path: str) -> Tuple[str, str]:
    """
    Parse a relationship field path into object and field
    
    Args:
        field_path: e.g., "WOD_2__Dealer__r.Dealer_Code__c"
    
    Returns:
        Tuple of (relationship_name, field_name)
    """
    if '.' not in field_path:
        return None, field_path
    
    parts = field_path.split('.')
    return parts[0], parts[1]


def get_relationship_object_from_field(sf_conn, source_object: str, relationship_name: str) -> str:
    """
    Get the actual object name from relationship name
    
    Args:
        sf_conn: Salesforce connection
        source_object: Source object name
        relationship_name: Relationship name (e.g., "WOD_2__Dealer__r")
    
    Returns:
        Parent object name (e.g., "Account")
    """
    try:
        source_metadata = getattr(sf_conn, source_object).describe()
        
        # Find the lookup field that matches this relationship
        for field in source_metadata['fields']:
            if field.get('relationshipName') == relationship_name:
                # Found it - get the referenced object
                reference_to = field.get('referenceTo', [])
                if reference_to:
                    return reference_to[0]
    
    except Exception as e:
        pass
    
    return None


def identify_relationship_fields(field_mappings: Dict[str, str]) -> Dict[str, str]:
    """
    Identify which mapped fields are relationship fields
    
    Args:
        field_mappings: CSV column → SF field mappings
    
    Returns:
        Dictionary of relationship field mappings
    """
    relationship_mappings = {}
    
    for csv_col, sf_field in field_mappings.items():
        if '.' in sf_field:
            relationship_mappings[csv_col] = sf_field
    
    return relationship_mappings


def extract_relationship_data(df: pd.DataFrame, relationship_fields: Dict[str, str], 
                            sf_conn, source_object: str) -> Tuple[pd.DataFrame, Dict]:
    """
    Extract relationship data and convert to lookup IDs
    
    Args:
        df: DataFrame with relationship field paths as columns
        relationship_fields: Mapping of CSV columns to relationship field paths
        sf_conn: Salesforce connection
        source_object: Source object being loaded
    
    Returns:
        Tuple of (transformed_df, relationship_config)
    """
    df_transformed = df.copy()
    relationship_config = {}
    
    for csv_col, field_path in relationship_fields.items():
        # Parse the relationship field path
        rel_name, rel_field = parse_relationship_field(field_path)
        
        # Get the parent object
        parent_object = get_relationship_object_from_field(sf_conn, source_object, rel_name)
        
        if not parent_object:
            continue
        
        # Get the lookup field name (remove __r and add __c)
        lookup_field = rel_name.replace('__r', '__c')
        
        # Store configuration
        relationship_config[csv_col] = {
            'lookup_field': lookup_field,
            'parent_object': parent_object,
            'search_field': rel_field,
            'csv_column': csv_col,
            'relationship_path': field_path
        }
        
        # Import lookup resolver
        from dataload.lookup_resolver import resolve_lookup_value
        
        # For each value in this column, resolve to ID
        for idx, value in enumerate(df_transformed[csv_col]):
            if pd.isna(value) or str(value).strip() == '':
                continue
            
            # Resolve using the relationship field as search field
            resolved_id, error = resolve_lookup_value(
                sf_conn=sf_conn,
                parent_object=parent_object,
                value=str(value),
                source_object=source_object,
                lookup_field_name=lookup_field
            )
            
            if error:
                df_transformed.at[idx, csv_col] = None  # Set to null if can't resolve
            else:
                df_transformed.at[idx, csv_col] = resolved_id
        
        # Rename column from CSV column name to lookup field name
        if csv_col in df_transformed.columns:
            df_transformed.rename(columns={csv_col: lookup_field}, inplace=True)
    
    return df_transformed, relationship_config


def display_relationship_field_info(relationship_config: Dict) -> None:
    """
    Display information about relationship fields being loaded
    
    Args:
        relationship_config: Configuration dictionary for relationship fields
    """
    import streamlit as st
    
    if not relationship_config:
        return
    
    st.write("### 🔗 Relationship Field Mappings")
    
    for csv_col, config in relationship_config.items():
        with st.expander(f"📄 {csv_col} → {config['lookup_field']}"):
            st.write(f"**Relationship Path:** `{config['relationship_path']}`")
            st.write(f"**Parent Object:** {config['parent_object']}")
            st.write(f"**Search Field:** {config['search_field']}")
            st.write(f"**Target Lookup Field:** {config['lookup_field']}")
            st.write("""
            **How it works:**
            1. Values from your CSV column are read
            2. System searches in: `{parent_object}.{search_field}`
            3. Finds matching record and extracts its Salesforce ID
            4. ID is stored in: `{lookup_field}`
            """.format(**config))
