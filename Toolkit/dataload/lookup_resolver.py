"""
Lookup Field Resolver for Data Loading
Resolves lookup/reference field values to Salesforce IDs before data insertion
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
import traceback


def get_lookup_fields_for_object(sf_conn, object_name: str) -> Dict[str, Dict]:
    """
    Identify all lookup/reference fields for an object
    
    Args:
        sf_conn: Salesforce connection
        object_name: Name of the Salesforce object
    
    Returns:
        Dictionary mapping field name to field metadata
        {
            "WOD_2__Dealer__c": {
                "name": "WOD_2__Dealer__c",
                "type": "reference",
                "reference_to": ["Dealer"],
                "label": "Dealer"
            }
        }
    """
    try:
        object_metadata = getattr(sf_conn, object_name).describe()
        lookup_fields = {}
        
        for field in object_metadata['fields']:
            if field.get('type') in ['reference', 'lookup', 'masterdetail']:
                lookup_fields[field['name']] = {
                    'name': field['name'],
                    'type': field['type'],
                    'reference_to': field.get('referenceTo', []),
                    'label': field.get('label', field['name']),
                    'updateable': field.get('updateable', False),
                    'createable': field.get('createable', False)
                }
        
        return lookup_fields
    except Exception as e:
        print(f"❌ Error getting lookup fields for {object_name}: {e}")
        return {}


def get_candidate_fields_for_lookup(sf_conn, parent_object: str, 
                                   source_object: str = None, 
                                   lookup_field_name: str = None) -> List[str]:
    """
    Dynamically determine which fields to search in the parent object
    by querying Salesforce relationship metadata
    
    Args:
        sf_conn: Salesforce connection
        parent_object: Name of the parent object (e.g., "Dealer", "Account")
        source_object: Optional - name of the source object with the lookup field
        lookup_field_name: Optional - name of the lookup field
    
    Returns:
        List of field names to search in order (prioritized by metadata config)
    """
    
    candidate_fields = []
    
    # PRIORITY 1: Check for fields marked as External IDs (metadata-driven)
    try:
        parent_metadata = getattr(sf_conn, parent_object).describe()
        
        # First, find fields marked as External IDs (highest priority for lookup matching)
        for field in parent_metadata['fields']:
            if field.get('externalIdField', False):
                candidate_fields.append(field['name'])
        
        # If we have external ID fields, use those
        if candidate_fields:
            return candidate_fields
        
        # PRIORITY 2: Get all searchable fields from metadata (that could contain lookup codes)
        # Include text fields, unique fields, and fields commonly used for lookups
        searchable_fields = []
        for field in parent_metadata['fields']:
            field_type = field.get('type', '').lower()
            field_name = field['name']
            
            # Prioritize fields by type and naming patterns
            if field_name == 'Id':
                continue  # Skip Id
            elif field.get('idLookup', False):  # Unique/External ID indicator
                searchable_fields.insert(0, field_name)  # High priority
            elif 'code' in field_name.lower() or 'number' in field_name.lower():
                searchable_fields.insert(1, field_name)  # Medium-high priority
            elif field_type in ['string', 'text', 'email', 'phone', 'url', 'picklist']:
                searchable_fields.append(field_name)  # Medium priority
        
        return searchable_fields if searchable_fields else []
        
    except Exception as e:
        pass
    
    # PRIORITY 3: If metadata query failed, use org/object-specific mappings
    LOOKUP_FIELD_MAPPINGS = {
        # Standard Salesforce Objects
        "Account": ["ExternalId__c", "DealerNumber", "DealerNumber__c", "AccountNumber", "Name"],
        "Contact": ["ExternalId__c", "Email", "Name"],
        "Opportunity": ["ExternalId__c", "Name"],
        "Lead": ["ExternalId__c", "Email", "Name"],
        "Product2": ["ExternalId__c", "ProductCode", "Name"],
        "User": ["ExternalId__c", "Email", "Username", "Name"],
        
        # Custom Objects
        "Dealer": ["ExternalId__c", "Code__c", "DealerNumber__c", "Code", "Name"],
        "WOD_2__Claim__c": ["ExternalId__c", "Claim_Number__c", "Claim_ID__c", "Name"],
        "WOD_2__Warranty_Product__c": ["ExternalId__c", "Product_Code__c", "SKU__c", "Name"],
    }
    
    if parent_object in LOOKUP_FIELD_MAPPINGS:
        return LOOKUP_FIELD_MAPPINGS[parent_object]
    
    # PRIORITY 4: Generic pattern for unknown custom objects
    if '__c' in parent_object:
        return [
            "ExternalId__c",
            "External_Id__c",
            "Code__c",
            "Code",
            "Number__c",
            "Number",
            "Name",
            "Description"
        ]
    
    # Generic fallback for unknown standard objects
    return ["ExternalId__c", "Name", "Code"]


def resolve_lookup_value(sf_conn, parent_object: str, value: str, 
                        source_object: str = None, 
                        lookup_field_name: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve a single lookup value to a Salesforce ID
    
    Uses relationship metadata to determine which field in the parent object
    contains the lookup matching field (typically External ID)
    
    Args:
        sf_conn: Salesforce connection
        parent_object: Name of the parent object to query (e.g., "Dealer", "Account")
        value: The value from the data file (e.g., "914021")
        source_object: Optional - name of the source object with the lookup field
        lookup_field_name: Optional - name of the lookup field
    
    Returns:
        Tuple of (salesforce_id, error_message)
        - If successful: (resolved_id, None)
        - If failed: (None, error_message)
        - If NULL: (None, None)
    """
    
    # Handle NULL/empty values
    if not value or str(value).strip() == '':
        return None, None
    
    value_str = str(value).strip()
    
    # Check if value already looks like a Salesforce ID (15 or 18 chars)
    if len(value_str) in [15, 18]:
        # Could be an ID - try to verify it exists
        try:
            query = f"SELECT Id FROM {parent_object} WHERE Id = '{value_str}' LIMIT 1"
            result = sf_conn.query(query)
            if result['totalSize'] > 0:
                # It's a valid ID that exists
                return value_str, None
            # Falls through to search as field value
        except:
            # Falls through to search as field value
            pass
    
    # NOT a valid Salesforce ID format, so search for it in parent object
    candidate_fields = get_candidate_fields_for_lookup(
        sf_conn=sf_conn,
        parent_object=parent_object,
        source_object=source_object,
        lookup_field_name=lookup_field_name
    )
    
    # Try each candidate field
    for field_name_to_search in candidate_fields:
        try:
            # Build SOQL query
            escaped_value = value_str.replace("'", "\\'")
            query = f"SELECT Id FROM {parent_object} WHERE {field_name_to_search} = '{escaped_value}' LIMIT 1"
            
            # Execute query
            result = sf_conn.query(query)
            
            # Check if record found
            if result['totalSize'] > 0:
                resolved_id = result['records'][0]['Id']
                return resolved_id, None
        
        except Exception as e:
            # Try next field
            continue
    
    # NOT found in any candidate field
    searched = ", ".join(candidate_fields)
    error = f"Could not find {parent_object} matching value '{value}'. Searched fields: {searched}"
    return None, error


def resolve_dataframe_lookups(sf_conn, df: pd.DataFrame, object_name: str, 
                             field_mappings: Dict[str, str],
                             skip_on_error: bool = False) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Resolve all lookup fields in a DataFrame
    
    **OPTIMIZED FOR SPEED**: Uses batch SOQL queries with IN clause instead of
    querying one value at a time. Reduces API calls from N to N/200.
    
    Args:
        sf_conn: Salesforce connection
        df: DataFrame with data (CSV columns as keys)
        object_name: Salesforce object name
        field_mappings: Dictionary mapping CSV column name → Salesforce field name
                       e.g., {"Dealer Code": "WOD_2__Dealer__c", ...}
        skip_on_error: If True, skip rows with resolution errors; if False, raise exception
    
    Returns:
        Tuple of (resolved_df, resolution_report) where:
        - resolved_df: DataFrame with resolved IDs
        - resolution_report: List of dicts with resolution status for each row/field
    
    Raises:
        ValueError: If skip_on_error=False and any resolutions fail
    """
    
    df_resolved = df.copy()
    resolution_report = []
    
    print(f"\n{'='*80}")
    print(f"LOOKUP FIELD RESOLUTION: {object_name}")
    print(f"{'='*80}")
    
    # Step 1: Identify lookup fields in this object
    lookup_fields = get_lookup_fields_for_object(sf_conn, object_name)
    
    if not lookup_fields:
        print(f"✅ No lookup fields found in {object_name}")
        return df_resolved, []
    
    print(f"🔗 Found {len(lookup_fields)} lookup field(s) in {object_name}")
    
    # Step 2: For each CSV column, check if it maps to a lookup field
    failed_resolutions = []
    successful_resolutions = 0
    
    for csv_column, sf_field_name in field_mappings.items():
        # Skip if not a lookup field
        if sf_field_name not in lookup_fields:
            continue
        
        # Skip if column doesn't exist in DataFrame
        if csv_column not in df_resolved.columns:
            continue
        
        lookup_info = lookup_fields[sf_field_name]
        parent_object = lookup_info['reference_to'][0]
        
        print(f"\n📌 Processing: {csv_column} (SF Field: {sf_field_name})")
        print(f"   Parent Object: {parent_object}")
        print(f"   Type: {lookup_info['type']}")
        
        # Get candidate fields for this lookup
        candidate_fields = get_candidate_fields_for_lookup(
            sf_conn=sf_conn,
            parent_object=parent_object,
            source_object=object_name,
            lookup_field_name=sf_field_name
        )
        
        # Step 3: Collect unique non-null, non-ID values
        rows_with_values = 0
        values_needing_resolution = {}  # value -> list of row indices
        already_valid_ids = {}  # value -> list of row indices (already SF IDs)
        null_rows = []
        
        for row_idx, row_value in df_resolved[csv_column].items():
            if pd.isna(row_value) or str(row_value).strip() == '':
                null_rows.append(row_idx)
                continue
            
            rows_with_values += 1
            value_str = str(row_value).strip()
            
            # Check if already a Salesforce ID
            if len(value_str) in [15, 18]:
                already_valid_ids.setdefault(value_str, []).append(row_idx)
            else:
                values_needing_resolution.setdefault(value_str, []).append(row_idx)
        
        # Step 4: Batch verify existing Salesforce IDs
        valid_sf_ids = set()
        if already_valid_ids:
            unique_ids = list(already_valid_ids.keys())
            for i in range(0, len(unique_ids), 200):
                chunk = unique_ids[i:i + 200]
                id_list = ', '.join([f"'{sid}'" for sid in chunk])
                try:
                    result = sf_conn.query(f"SELECT Id FROM {parent_object} WHERE Id IN ({id_list})")
                    for record in result['records']:
                        valid_sf_ids.add(record['Id'])
                except:
                    pass
        
        # Step 5: Batch resolve non-ID values using candidate fields
        value_to_id = {}  # resolved: value -> sf_id
        unresolved_values = set(values_needing_resolution.keys())
        
        for field_name_to_search in candidate_fields:
            if not unresolved_values:
                break  # All values resolved
            
            # Batch query: use IN clause with chunks of 200
            remaining = list(unresolved_values)
            for i in range(0, len(remaining), 200):
                chunk = remaining[i:i + 200]
                in_values = ', '.join([f"'{str(v).replace(chr(39), chr(39)*2)}'" for v in chunk])
                
                try:
                    soql = f"SELECT Id, {field_name_to_search} FROM {parent_object} WHERE {field_name_to_search} IN ({in_values})"
                    result = sf_conn.query(soql)
                    records = result['records']
                    while not result['done']:
                        result = sf_conn.query_more(result['nextRecordsUrl'], identifier_is_url=True)
                        records.extend(result['records'])
                    
                    for record in records:
                        field_val = record.get(field_name_to_search)
                        if field_val is not None and str(field_val) in unresolved_values:
                            value_to_id[str(field_val)] = record['Id']
                            unresolved_values.discard(str(field_val))
                except:
                    continue  # Try next candidate field
        
        # Step 6: Apply resolutions to DataFrame
        rows_resolved = 0
        
        # Apply resolved values
        for value_str, row_indices in values_needing_resolution.items():
            resolved_id = value_to_id.get(value_str)
            if resolved_id:
                for row_idx in row_indices:
                    df_resolved.at[row_idx, csv_column] = resolved_id
                    successful_resolutions += 1
                    rows_resolved += 1
                    resolution_report.append({
                        'row': row_idx + 1,
                        'csv_column': csv_column,
                        'sf_field': sf_field_name,
                        'parent_object': parent_object,
                        'original_value': value_str,
                        'resolved_id': resolved_id,
                        'status': 'SUCCESS',
                        'error': None
                    })
                print(f"   ✅ '{value_str}' → {resolved_id} ({len(row_indices)} row(s))")
            else:
                # Resolution FAILED
                searched = ", ".join(candidate_fields)
                error = f"Could not find {parent_object} matching value '{value_str}'. Searched fields: {searched}"
                for row_idx in row_indices:
                    failed_resolutions.append({
                        'row': row_idx + 1,
                        'csv_column': csv_column,
                        'sf_field': sf_field_name,
                        'parent_object': parent_object,
                        'original_value': value_str,
                        'resolved_id': None,
                        'status': 'FAILED',
                        'error': error
                    })
                print(f"   ❌ '{value_str}' → NOT FOUND ({len(row_indices)} row(s))")
        
        # Count valid IDs
        for value_str, row_indices in already_valid_ids.items():
            if value_str in valid_sf_ids:
                rows_resolved += len(row_indices)
                successful_resolutions += len(row_indices)
        
        print(f"   Summary: {rows_resolved}/{rows_with_values} values resolved")
    
    # Step 4: Handle resolution failures
    if failed_resolutions:
        print(f"\n{'='*80}")
        print(f"❌ RESOLUTION FAILURES: {len(failed_resolutions)}")
        print(f"{'='*80}")
        
        for fail in failed_resolutions:
            print(f"Row {fail['row']}: {fail['error']}")
            resolution_report.append(fail)
        
        if not skip_on_error:
            raise ValueError(f"{len(failed_resolutions)} lookup field(s) could not be resolved")
    else:
        print(f"\n{'='*80}")
        print(f"✅ ALL LOOKUPS RESOLVED: {successful_resolutions} resolutions")
        print(f"{'='*80}")
    
    return df_resolved, resolution_report


def validate_lookup_fields_exist(sf_conn, object_name: str, field_mappings: Dict[str, str]) -> List[str]:
    """
    Validate that all mapped fields with lookup relationships have valid parent objects
    
    Args:
        sf_conn: Salesforce connection
        object_name: Salesforce object name
        field_mappings: CSV column → Salesforce field name mappings
    
    Returns:
        List of error messages (empty if all valid)
    """
    errors = []
    lookup_fields = get_lookup_fields_for_object(sf_conn, object_name)
    
    for csv_column, sf_field_name in field_mappings.items():
        if sf_field_name in lookup_fields:
            lookup_info = lookup_fields[sf_field_name]
            if not lookup_info['reference_to'] or len(lookup_info['reference_to']) == 0:
                errors.append(f"Lookup field '{sf_field_name}' has no parent object defined")
            else:
                parent_obj = lookup_info['reference_to'][0]
                try:
                    # Test if parent object is accessible
                    getattr(sf_conn, parent_obj).describe()
                except:
                    errors.append(f"Parent object '{parent_obj}' for lookup field '{sf_field_name}' is not accessible")
    
    return errors


# EXAMPLE USAGE
if __name__ == "__main__":
    """
    Example of how to use the lookup resolver
    """
    
    # This would be called from DataLoader.py or transformed.py:
    
    # 1. Load data
    # df = pd.read_csv("mydata.csv")
    
    # 2. Define field mappings (CSV column → Salesforce field)
    # field_mappings = {
    #     "Dealer Code": "WOD_2__Dealer__c",
    #     "Account Name": "Account__c",
    #     "Product Code": "WOD_2__Warranty_Product__c"
    # }
    
    # 3. BEFORE inserting records, resolve lookups
    # df_resolved, report = resolve_dataframe_lookups(
    #     sf_conn=sf_conn,
    #     df=df,
    #     object_name="WOD_2__Rates_Details__c",
    #     field_mappings=field_mappings,
    #     skip_on_error=False  # Raise error if any resolutions fail
    # )
    
    # 4. Now df_resolved has actual Salesforce IDs instead of codes/names
    # 5. Proceed with insert/update operations
    
    print("✅ lookup_resolver.py loaded successfully")
