"""
Lookup Resolution Validator for Validation Operations
Intelligently resolves lookup/reference field values to Salesforce IDs
instead of just checking if they look like IDs
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from simple_salesforce import Salesforce


def get_lookup_resolution_candidates(parent_object: str) -> List[str]:
    """
    Determine which fields to search in the parent object for lookup resolution
    
    Different objects have different identifying fields:
    - Account: Name, AccountNumber, ExternalIdField__c
    - Contact: Name, Email, Phone
    - Opportunity: Name, StageName
    - Custom objects: Usually have Name, Code, ExternalID fields
    
    Args:
        parent_object: Name of the parent object
    
    Returns:
        List of field names to search in order of priority
    """
    # Common lookup resolution fields for standard objects
    standard_candidates = {
        'Account': ['Name', 'AccountNumber', 'BillingCity'],
        'Contact': ['Name', 'Email', 'Phone', 'MailingCity'],
        'Opportunity': ['Name', 'StageName'],
        'Lead': ['Name', 'Email', 'Phone'],
        'Case': ['CaseNumber', 'Subject'],
        'Product2': ['Name', 'ProductCode'],
        'PricebookEntry': ['Name'],
        'Contract': ['ContractNumber', 'AccountId'],
    }
    
    # If standard object, use predefined candidates
    if parent_object in standard_candidates:
        return standard_candidates[parent_object]
    
    # For custom objects, these are typical identifying fields
    # Order: specific external IDs → Name/Code fields → generic
    generic_candidates = [
        f'{parent_object.replace("__c", "")}__c',  # ExternalId__c
        f'{parent_object.replace("__c", "")}_ExternalId__c',
        'ExternalId__c',
        'External_Id__c',
        'ExtId__c',
        'Name',
        'Code',
        f'{parent_object.replace("__c", "")}_Code__c',
        'Number',
        'Description'
    ]
    
    return generic_candidates


def resolve_lookup_value_to_salesforce_id(
    sf_conn: Salesforce,
    parent_object: str,
    lookup_value: str,
    field_name: str = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve a lookup value to its Salesforce ID
    
    This is the CORE lookup resolution logic:
    1. Try to find the value in the parent object
    2. Search across multiple candidate fields
    3. Return the Salesforce ID if found
    4. Return error message if not found
    
    Args:
        sf_conn: Salesforce connection
        parent_object: Name of parent object (e.g., 'Account', 'Dealer__c')
        lookup_value: The value to search for (e.g., '914021', 'John Doe')
        field_name: Optional - the lookup field name for error messages
    
    Returns:
        Tuple of (salesforce_id, error_message)
        - If found: (actual_id, None)
        - If not found: (None, error_message)
    """
    # Handle empty values
    if not lookup_value or str(lookup_value).strip() == '':
        return None, None  # NULL is allowed for optional lookup fields
    
    lookup_value_str = str(lookup_value).strip()
    
    # Check if it already looks like a Salesforce ID (15 or 18 chars)
    if len(lookup_value_str) == 15 or len(lookup_value_str) == 18:
        # Verify it's a valid ID format (alphanumeric only)
        if lookup_value_str.replace('_', '').replace('-', '').isalnum():
            # Likely already a Salesforce ID
            try:
                # Verify it exists in the parent object
                query = f"SELECT Id FROM {parent_object} WHERE Id = '{lookup_value_str}' LIMIT 1"
                result = sf_conn.query(query)
                if result['totalSize'] > 0:
                    return lookup_value_str, None  # Already correct ID
                else:
                    # ID format but doesn't exist
                    parent_display = field_name or parent_object
                    return None, f"Salesforce ID '{lookup_value_str}' not found in {parent_object}"
            except Exception as e:
                parent_display = field_name or parent_object
                return None, f"Error verifying ID in {parent_object}: {str(e)}"
    
    # NOT a Salesforce ID format, so it must be a field value
    # Get candidate fields to search
    candidate_fields = get_lookup_resolution_candidates(parent_object)
    
    # Try each candidate field
    for candidate_field in candidate_fields:
        try:
            # Build SOQL query
            # Escape single quotes in the value
            escaped_value = lookup_value_str.replace("'", "\\'")
            query = f"SELECT Id FROM {parent_object} WHERE {candidate_field} = '{escaped_value}' LIMIT 1"
            
            result = sf_conn.query(query)
            
            if result['totalSize'] > 0:
                # Found!
                found_id = result['records'][0]['Id']
                return found_id, None
        except Exception as e:
            # This candidate field might not exist or might have caused an error
            # Continue to next candidate
            continue
    
    # Not found in any candidate field
    field_display = field_name or parent_object
    return None, (
        f"Could not find {parent_object} record with value '{lookup_value_str}'. "
        f"Searched in: {', '.join(candidate_fields[:3])} (and more). "
        f"Please verify the value exists in the {parent_object} object."
    )


def validate_lookup_field_with_resolution(
    sf_conn: Salesforce,
    field_name: str,
    value,
    field_info: dict,
    sf_object_fields: List[dict] = None
) -> Optional[str]:
    """
    Enhanced validation for lookup/reference fields WITH lookup resolution
    
    Instead of just checking if value is 15-18 chars,
    this actually queries the parent object to resolve the value.
    
    Args:
        sf_conn: Salesforce connection
        field_name: Name of the lookup field
        value: The value from the data file
        field_info: Field metadata from Salesforce
        sf_object_fields: Optional - all fields for the object
    
    Returns:
        Error message if validation fails, None if passes
        Also returns resolved ID for downstream use (side effect)
    """
    # Handle NULL values (optional fields)
    if pd.isna(value) or str(value).strip() == '':
        return None
    
    field_type = field_info.get('type', '').lower()
    
    # Only handle reference/lookup/masterdetail types
    if field_type not in ['reference', 'lookup', 'masterdetail']:
        return None
    
    # Get parent object info
    reference_to = field_info.get('referenceTo')
    if not reference_to or len(reference_to) == 0:
        return None  # No parent object defined
    
    parent_object = reference_to[0]
    
    try:
        # Attempt to resolve the lookup value to a Salesforce ID
        resolved_id, error_message = resolve_lookup_value_to_salesforce_id(
            sf_conn=sf_conn,
            parent_object=parent_object,
            lookup_value=value,
            field_name=field_name
        )
        
        if error_message:
            # Return descriptive error
            return f"Lookup Resolution Error in field '{field_name}': {error_message}"
        
        # Success! The value was resolved
        return None
    
    except Exception as e:
        return f"Error resolving lookup for field '{field_name}': {str(e)}"


def batch_resolve_lookup_values(
    sf_conn: Salesforce,
    field_name: str,
    values: pd.Series,
    field_info: dict,
    progress_callback=None
) -> pd.Series:
    """
    Resolve multiple lookup values to Salesforce IDs efficiently
    
    Args:
        sf_conn: Salesforce connection
        field_name: Name of the lookup field
        values: Series of values to resolve
        field_info: Field metadata
        progress_callback: Optional callback for progress updates
    
    Returns:
        Series with resolved Salesforce IDs (or original value if already ID or NULL)
    """
    resolved_values = []
    errors = []
    
    field_type = field_info.get('type', '').lower()
    if field_type not in ['reference', 'lookup', 'masterdetail']:
        return values
    
    reference_to = field_info.get('referenceTo')
    if not reference_to or len(reference_to) == 0:
        return values
    
    parent_object = reference_to[0]
    
    for idx, value in enumerate(values):
        if progress_callback and idx % 10 == 0:
            progress_callback(f"Resolving {field_name}: {idx}/{len(values)}")
        
        # Handle NULL
        if pd.isna(value) or str(value).strip() == '':
            resolved_values.append(None)
            continue
        
        try:
            resolved_id, error = resolve_lookup_value_to_salesforce_id(
                sf_conn=sf_conn,
                parent_object=parent_object,
                lookup_value=value,
                field_name=field_name
            )
            
            if error:
                resolved_values.append(None)  # Mark as error
                errors.append(f"Row {idx}: {error}")
            else:
                resolved_values.append(resolved_id)
        
        except Exception as e:
            resolved_values.append(None)
            errors.append(f"Row {idx}: Error resolving '{value}': {str(e)}")
    
    return pd.Series(resolved_values), errors


def get_lookup_resolution_report(
    sf_conn: Salesforce,
    object_name: str,
    data_df: pd.DataFrame,
    sf_fields_metadata: List[dict]
) -> Dict:
    """
    Generate a comprehensive lookup resolution report for all reference fields
    
    Args:
        sf_conn: Salesforce connection
        object_name: Name of the object being validated
        data_df: DataFrame with data to validate
        sf_fields_metadata: Field metadata from Salesforce
    
    Returns:
        Report dictionary with resolution results
    """
    report = {
        'object': object_name,
        'total_lookup_fields': 0,
        'resolvable_lookup_fields': 0,
        'unresolvable_lookup_fields': 0,
        'total_values_to_resolve': 0,
        'successfully_resolved': 0,
        'failed_resolutions': 0,
        'field_reports': {},
        'errors': []
    }
    
    # Identify all lookup fields
    for field_info in sf_fields_metadata:
        field_type = field_info.get('type', '').lower()
        if field_type not in ['reference', 'lookup', 'masterdetail']:
            continue
        
        field_name = field_info['name']
        report['total_lookup_fields'] += 1
        
        # Check if field exists in data
        if field_name not in data_df.columns:
            report['field_reports'][field_name] = {
                'status': 'SKIP',
                'reason': 'Field not in data'
            }
            continue
        
        # Get non-null values
        values = data_df[field_name].dropna()
        if len(values) == 0:
            report['field_reports'][field_name] = {
                'status': 'SKIP',
                'reason': 'All values are NULL'
            }
            continue
        
        report['resolvable_lookup_fields'] += 1
        report['total_values_to_resolve'] += len(values)
        
        # Resolve values
        resolved, errors = batch_resolve_lookup_values(
            sf_conn, field_name, values, field_info
        )
        
        successful = len([v for v in resolved if v is not None])
        report['successfully_resolved'] += successful
        report['failed_resolutions'] += len(errors)
        
        report['field_reports'][field_name] = {
            'status': 'RESOLVED' if len(errors) == 0 else 'PARTIAL',
            'total': len(values),
            'resolved': successful,
            'failed': len(errors),
            'parent_object': field_info['referenceTo'][0],
            'errors': errors[:5]  # First 5 errors
        }
        
        report['errors'].extend(errors)
    
    return report
