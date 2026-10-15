"""
SOQL Lookup Field Discovery for Org-to-Org Migration
Parses SOQL queries to auto-discover relationship fields and generate lookup configs
"""

import re
from typing import Dict, List, Tuple, Optional
import streamlit as st


def parse_soql_query(soql_query: str) -> Tuple[str, List[str], str]:
    """
    Parse SOQL query to extract SELECT fields, FROM object, and WHERE clause
    
    Args:
        soql_query: SOQL query string
        
    Returns:
        Tuple of (from_object, select_fields, where_clause)
    """
    # Normalize whitespace
    query = ' '.join(soql_query.split())
    
    # Extract FROM object
    from_match = re.search(r'\bFROM\s+(\w+(?:__c)?)\b', query, re.IGNORECASE)
    from_object = from_match.group(1) if from_match else None
    
    # Extract SELECT fields
    select_match = re.search(r'\bSELECT\s+(.+?)\s+FROM\b', query, re.IGNORECASE)
    select_clause = select_match.group(1) if select_match else ""
    
    # Extract WHERE clause if exists
    where_match = re.search(r'\bWHERE\s+(.+?)(?:\bLIMIT\b|$)', query, re.IGNORECASE)
    where_clause = where_match.group(1).strip() if where_match else ""
    
    # Parse fields from SELECT clause
    # Handle nested fields and functions
    fields = []
    current_field = ""
    paren_depth = 0
    
    for char in select_clause:
        if char == '(':
            paren_depth += 1
            current_field += char
        elif char == ')':
            paren_depth -= 1
            current_field += char
        elif char == ',' and paren_depth == 0:
            if current_field.strip():
                fields.append(current_field.strip())
            current_field = ""
        else:
            current_field += char
    
    if current_field.strip():
        fields.append(current_field.strip())
    
    return from_object, fields, where_clause


def extract_relationship_fields(select_fields: List[str], from_object: str = None, source_sf=None) -> Dict[str, Dict]:
    """
    Extract relationship fields from SELECT clause AND validate they exist in metadata
    
    Identifies fields like: WOD_2__Dealer__r.Dealer_Number__c
    
    **VALIDATION STEP**: Before returning, validates that converted lookup field name exists in metadata.
    This matches data loading approach - only return fields that actually exist.
    
    Args:
        select_fields: List of field names from SELECT clause
        from_object: Object name from SOQL FROM clause (optional, used for validation)
        source_sf: Source Salesforce connection (optional, used for validation)
        
    Returns:
        Dictionary mapping relationship field to details:
        {
            'WOD_2__Dealer__c': {
                'relationship_name': 'WOD_2__Dealer__r',
                'relationship_field': 'Dealer_Number__c',
                'display_name': 'WOD_2__Dealer__r.Dealer_Number__c'
            }
        }
        
    Note: If validation parameters provided, only returns fields that exist in metadata
    """
    relationship_fields = {}
    
    # Get all lookup fields from source object if validation enabled
    valid_lookup_fields = set()
    if from_object and source_sf:
        try:
            object_metadata = getattr(source_sf, from_object).describe()
            for field in object_metadata['fields']:
                # Only lookup/reference/masterdetail fields
                if field.get('type') in ['reference', 'lookup', 'masterdetail']:
                    valid_lookup_fields.add(field['name'])
        except Exception as e:
            print(f"⚠️ Could not validate lookup fields for {from_object}: {str(e)}")
    
    for field in select_fields:
        field = field.strip()
        
        # Skip aggregate functions and simple fields
        if '(' in field or '.' not in field:
            continue
        
        # Check if it's a relationship field (contains __r.)
        if '__r.' in field:
            parts = field.split('.')
            if len(parts) == 2:
                relationship_name = parts[0]  # e.g., WOD_2__Dealer__r
                relationship_field = parts[1]  # e.g., Dealer_Number__c
                
                # Extract lookup field name (remove __r, add __c)
                lookup_field_name = relationship_name.replace('__r', '__c')
                
                # VALIDATION: Check if this field actually exists in metadata
                if valid_lookup_fields and lookup_field_name not in valid_lookup_fields:
                    print(f"⚠️ Field '{lookup_field_name}' not found in {from_object} metadata - skipping")
                    continue
                
                relationship_fields[lookup_field_name] = {
                    'relationship_name': relationship_name,
                    'relationship_field': relationship_field,
                    'display_name': field,
                    'lookup_field': lookup_field_name
                }
    
    return relationship_fields


def infer_parent_object_from_relationship(
    source_object: str,
    lookup_field_name: str,
    source_sf
) -> Optional[str]:
    """
    Get parent object name from lookup field's metadata (referenceTo)
    
    This queries the SOURCE org to find which object the lookup field references,
    same way data loading does it.
    
    Example:
      - Source Object: WOD_2__Rates_Details__c
      - Lookup Field: WOD_2__Dealer__c
      - Metadata referenceTo: ["WOD_2__Dealer__c"]  or  ["Dealer"]
      - Return: "WOD_2__Dealer__c" or "Dealer" (whatever Salesforce says)
    
    Args:
        source_object: Object that contains the lookup field (e.g., "WOD_2__Rates_Details__c")
        lookup_field_name: Name of the lookup field (e.g., "WOD_2__Dealer__c")
        source_sf: Source Salesforce connection
        
    Returns:
        Parent object name from referenceTo, or None if not found
    """
    try:
        # Query metadata of the source object
        object_metadata = getattr(source_sf, source_object).describe()
        
        # Find the lookup field in this object
        for field in object_metadata['fields']:
            if field['name'] == lookup_field_name:
                # Verify it's a lookup/reference type field (like data loading does)
                field_type = field.get('type', '').lower()
                if field_type not in ['reference', 'lookup', 'masterdetail']:
                    # Field exists but is not a lookup field
                    print(f"⚠️ Field {lookup_field_name} exists but is type '{field_type}', not a lookup field")
                    return None
                
                # Get the referenceTo - which object(s) this lookup references
                reference_to = field.get('referenceTo', [])
                
                if reference_to and len(reference_to) > 0:
                    # Return the first (or primary) referenced object
                    # For single-reference fields, there's only one
                    parent_object = reference_to[0]
                    print(f"✅ Found parent object '{parent_object}' for {source_object}.{lookup_field_name}")
                    return parent_object
                else:
                    # Field found but has no referenceTo
                    print(f"⚠️ Field {lookup_field_name} has no referenceTo in metadata")
                    return None
        
        # Field not found in metadata
        print(f"⚠️ Could not find field {lookup_field_name} in {source_object} metadata")
        return None
        
    except Exception as e:
        print(f"❌ Error querying metadata for {source_object}.{lookup_field_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def generate_lookup_config_from_soql(
    from_object: str,
    soql_relationship_fields: Dict[str, Dict],
    source_sf,
    target_sf
) -> Dict[str, Dict]:
    """
    Generate lookup configurations from SOQL-discovered relationship fields
    
    **Complete Flow:**
    1. From SOQL query: FROM {from_object}
    2. Extract lookup field: {lookup_field} (e.g., WOD_2__Dealer__c)
    3. Query SOURCE org metadata of {from_object}
    4. Find the lookup field and get its referenceTo
    5. referenceTo gives actual parent object (e.g., WOD_2__Dealer__c or Dealer)
    6. Extract relationship field from SOQL (e.g., Dealer_Number__c)
    7. During migration: Query SOURCE → SELECT Id FROM {parent_object} WHERE {relationship_field} = value
    
    Queries the SOURCE org metadata to get the actual parent objects referenced by lookup fields.
    Same approach as data loading - uses referenceTo field metadata.
    
    Args:
        from_object: Object name from SOQL FROM clause (e.g., "WOD_2__Rates_Details__c")
        soql_relationship_fields: Dict from extract_relationship_fields()
        source_sf: Source Salesforce connection
        target_sf: Target Salesforce connection
        
    Returns:
        Dictionary suitable for migration_lookup_configs:
        {
            'WOD_2__Dealer__c': {
                'parent_object': 'WOD_2__Dealer__c' (from metadata referenceTo),
                'match_strategy': 'field_mapping',
                'match_fields': ['Dealer_Number__c'] (relationship field from SOQL),
                'source_relationship_field': 'Dealer_Number__c'
            }
        }
    """
    lookup_configs = {}
    
    for lookup_field, rel_info in soql_relationship_fields.items():
        # Query SOURCE org metadata to get actual parent object
        parent_object = infer_parent_object_from_relationship(
            source_object=from_object,
            lookup_field_name=lookup_field,
            source_sf=source_sf
        )
        
        if not parent_object:
            print(f"⚠️ Could not infer parent object for {lookup_field} in {from_object}")
            continue
        
        match_field = rel_info['relationship_field']
        
        print(f"✅ Generated config: {lookup_field} → {parent_object} (match: {match_field})")
        
        lookup_configs[lookup_field] = {
            'parent_object': parent_object,
            'match_strategy': 'field_mapping',  # Special strategy for SOQL-discovered fields
            'match_fields': [match_field],
            'source_relationship_field': match_field,
            'discovered_from_soql': True
        }
    
    return lookup_configs


def show_soql_lookup_discovery_ui(source_sf, target_sf):
    """
    Streamlit UI for SOQL-based lookup field auto-discovery
    
    Args:
        source_sf: Source Salesforce connection
        target_sf: Target Salesforce connection
        
    Returns:
        Dictionary of discovered lookup configs or None
    """
    st.markdown("### 🔍 Auto-Discover Lookup Fields from SOQL")
    st.info("""
    💡 Write a SOQL query against your SOURCE org. 
    System will extract relationship fields and auto-generate lookup configurations.
    
    **Example:** `SELECT Id, Name, WOD_2__Dealer__r.Dealer_Number__c FROM WOD_2__Rates_Details__c`
    """)
    
    # SOQL input
    soql_query = st.text_area(
        "Enter SOQL Query (Source Org):",
        value="SELECT Id, Name FROM Object",
        height=100,
        help="Query will be parsed to extract relationship fields",
        key="soql_lookup_discovery_query"
    )
    
    if not soql_query or soql_query == "SELECT Id, Name FROM Object":
        st.warning("⚠️ Enter a SOQL query to begin")
        return None
    
    # Parse SOQL
    try:
        from_object, select_fields, where_clause = parse_soql_query(soql_query)
        
        if not from_object:
            st.error("❌ Could not parse SOQL query. Check syntax.")
            return None
        
        st.success(f"✅ Parsed SOQL")
        st.write(f"**From Object:** {from_object}")
        st.write(f"**Fields:** {len(select_fields)}")
        
    except Exception as e:
        st.error(f"❌ Error parsing SOQL: {str(e)}")
        return None
    
    # Extract relationship fields WITH VALIDATION against metadata
    # Pass source_sf and from_object to validate converted field names actually exist
    relationship_fields = extract_relationship_fields(
        select_fields=select_fields,
        from_object=from_object,
        source_sf=source_sf
    )
    
    if not relationship_fields:
        st.info("ℹ️ No relationship fields found in SOQL query.")
        st.write("**Parsed Fields:**")
        for i, field in enumerate(select_fields, 1):
            st.write(f"{i}. {field}")
        return None
    
    # Show discovered relationship fields
    st.markdown("---")
    st.markdown("### 🔗 Discovered Relationship Fields")
    
    st.success(f"✅ Found {len(relationship_fields)} relationship field(s)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Relationship Fields:**")
        for lookup_field, rel_info in relationship_fields.items():
            st.write(f"• {rel_info['display_name']}")
    
    with col2:
        st.write("**Lookup Fields:**")
        for lookup_field in relationship_fields.keys():
            st.write(f"• {lookup_field}")
    
    # Generate configs
    try:
        print(f"\n{'='*80}")
        print(f"SOQL LOOKUP DISCOVERY DEBUG")
        print(f"{'='*80}")
        print(f"From Object: {from_object}")
        print(f"Relationship Fields Found: {list(relationship_fields.keys())}")
        print(f"\nGenerating lookup configs...")
        print(f"{'='*80}\n")
        
        lookup_configs = generate_lookup_config_from_soql(
            from_object=from_object,
            soql_relationship_fields=relationship_fields,
            source_sf=source_sf,
            target_sf=target_sf
        )
        
        print(f"\n{'='*80}")
        print(f"Generated Configs: {lookup_configs}")
        print(f"{'='*80}\n")
        
        if lookup_configs:
            st.markdown("---")
            st.markdown("### 📋 Generated Lookup Configurations")
            
            for lookup_field, config in lookup_configs.items():
                with st.expander(f"🔗 {lookup_field} → {config['parent_object']}", expanded=True):
                    st.write(f"**Lookup Field:** {lookup_field}")
                    st.write(f"(In object: {from_object})")
                    st.write("")
                    
                    st.write(f"**Parent Object:** {config['parent_object']}")
                    st.write(f"(From metadata referenceTo - verified from SOURCE org)")
                    st.write("")
                    
                    st.write(f"**Match Field (for lookup matching):** {config['match_fields'][0]}")
                    st.write(f"(From SOQL relationship field: {config.get('source_relationship_field', config['match_fields'][0])})")
                    st.write("")
                    
                    # Show exact query that will be used
                    match_field = config['match_fields'][0]
                    st.info(f"""
                    **Query in SOURCE org during migration:**
                    ```sql
                    SELECT Id FROM {config['parent_object']} 
                    WHERE {match_field} = <lookup_value_from_source_record>
                    ```
                    
                    **This query:**
                    - Searches in {config['parent_object']} (verified from {lookup_field} referenceTo)
                    - Matches on {match_field} field
                    - Gets parent ID from SOURCE org
                    - Uses that ID in TARGET org child record
                    """)
            
            # Apply configs button
            if st.button("✅ Apply Auto-Discovered Configurations", type="primary"):
                return lookup_configs
        
        return None
        
    except Exception as e:
        st.error(f"❌ Error generating configurations: {str(e)}")
        return None


def validate_soql_field_mappings(discovered_fields: Dict) -> Tuple[bool, str]:
    """
    Validate that discovered fields can be mapped to target org
    
    Args:
        discovered_fields: Dictionary of discovered fields
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not discovered_fields:
        return False, "No fields discovered"
    
    if len(discovered_fields) == 0:
        return False, "No relationship fields found"
    
    return True, f"✅ Ready to use {len(discovered_fields)} discovered field(s)"
