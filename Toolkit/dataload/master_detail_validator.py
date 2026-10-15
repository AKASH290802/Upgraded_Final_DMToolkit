"""
Master-Detail Relationship Validator for Data Loading
Ensures parent records exist before attempting to load child records with Master-Detail relationships
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional
from simple_salesforce import Salesforce


def identify_master_detail_fields(sf_conn: Salesforce, object_name: str) -> Dict[str, Dict]:
    """
    Identify Master-Detail fields in a Salesforce object
    
    Master-Detail fields are CRITICAL:
    - ALWAYS Required (cannot be NULL)
    - Cascading Delete: deleting parent deletes all children
    - Child inherits parent's Record Type
    - Migration FAILS if parent doesn't exist
    
    Args:
        sf_conn: Salesforce connection
        object_name: Salesforce object name (e.g., 'Claim__c')
    
    Returns:
        Dictionary mapping field_name -> field_info with special properties
    """
    master_detail_fields = {}
    
    try:
        object_metadata = getattr(sf_conn, object_name).describe()
        
        for field in object_metadata['fields']:
            if field['type'] == 'masterdetail' and field.get('referenceTo'):
                master_detail_fields[field['name']] = {
                    'field_name': field['name'],
                    'label': field.get('label', field['name']),
                    'parent_object': field['referenceTo'][0],
                    'field_type': 'masterdetail',
                    'is_required': True,  # Master-Detail ALWAYS required
                    'is_nillable': False,  # Cannot be NULL
                    'cascading_delete': True,
                    'inherits_record_type': True,
                    'can_be_external_id': False
                }
    except Exception as e:
        raise RuntimeError(f"Failed to identify Master-Detail fields for {object_name}: {str(e)}")
    
    return master_detail_fields


def validate_master_detail_parents_exist(
    sf_conn: Salesforce,
    data_df: pd.DataFrame,
    master_detail_field: str,
    parent_object: str,
    match_field: str = 'Id'
) -> Tuple[bool, Dict]:
    """
    Validate that all parent records referenced by Master-Detail fields exist in Salesforce
    
    CRITICAL: If ANY parent is missing, data load will FAIL with cascading delete implications.
    
    Args:
        sf_conn: Salesforce connection
        data_df: DataFrame containing data to be loaded
        master_detail_field: Name of Master-Detail field in the data
        parent_object: Parent object name
        match_field: Field to use for matching (default: 'Id')
    
    Returns:
        Tuple of (is_valid: bool, validation_report: dict)
        validation_report contains:
        - 'status': 'PASS' | 'FAIL'
        - 'total_parents': Number of unique parent references
        - 'found': Count of parents found
        - 'missing': Count of missing parents
        - 'missing_ids': List of missing parent IDs
        - 'blocking': Whether this issue blocks the load
    """
    validation_report = {
        'master_detail_field': master_detail_field,
        'parent_object': parent_object,
        'match_field': match_field,
        'total_parents': 0,
        'found': 0,
        'missing': 0,
        'missing_ids': [],
        'status': 'PASS',
        'blocking': True,  # Master-Detail issues are ALWAYS blocking
        'errors': []
    }
    
    # Get unique parent values
    if master_detail_field not in data_df.columns:
        validation_report['errors'].append(f"Master-Detail field '{master_detail_field}' not found in data")
        validation_report['status'] = 'FAIL'
        return False, validation_report
    
    parent_values = data_df[master_detail_field].dropna().unique()
    validation_report['total_parents'] = len(parent_values)
    
    if len(parent_values) == 0:
        validation_report['errors'].append(f"No values found for Master-Detail field '{master_detail_field}'")
        validation_report['status'] = 'FAIL'
        return False, validation_report
    
    # Check each parent
    found_count = 0
    missing_parents = []
    
    for parent_value in parent_values:
        try:
            # Query Salesforce for parent
            query = f"SELECT Id FROM {parent_object} WHERE {match_field} = '{parent_value}' LIMIT 1"
            result = sf_conn.query(query)
            
            if result['totalSize'] > 0:
                found_count += 1
            else:
                missing_parents.append(str(parent_value))
        except Exception as e:
            validation_report['errors'].append(
                f"Error querying {parent_object} for {match_field}='{parent_value}': {str(e)}"
            )
            missing_parents.append(str(parent_value))
    
    validation_report['found'] = found_count
    validation_report['missing'] = len(missing_parents)
    validation_report['missing_ids'] = missing_parents
    
    if len(missing_parents) > 0:
        validation_report['status'] = 'FAIL'
        return False, validation_report
    
    return True, validation_report


def validate_all_master_detail_relationships(
    sf_conn: Salesforce,
    data_df: pd.DataFrame,
    object_name: str
) -> Tuple[bool, Dict]:
    """
    Validate ALL Master-Detail relationships for an object before data load
    
    CRITICAL VALIDATION: Run this BEFORE attempting any data upload.
    If ANY Master-Detail parent is missing, the entire load will fail.
    
    Args:
        sf_conn: Salesforce connection
        data_df: DataFrame containing data to be loaded
        object_name: Salesforce object name
    
    Returns:
        Tuple of (all_valid: bool, validation_summary: dict)
        validation_summary contains results for each Master-Detail field
    """
    validation_summary = {
        'object': object_name,
        'overall_status': 'PASS',
        'total_md_fields': 0,
        'valid_md_fields': 0,
        'invalid_md_fields': 0,
        'blocking_issues': 0,
        'details': {},
        'warnings': [],
        'errors': []
    }
    
    # Identify Master-Detail fields
    try:
        md_fields = identify_master_detail_fields(sf_conn, object_name)
        validation_summary['total_md_fields'] = len(md_fields)
        
        if len(md_fields) == 0:
            validation_summary['warnings'].append(f"No Master-Detail fields found in {object_name}")
            return True, validation_summary
    except Exception as e:
        validation_summary['overall_status'] = 'FAIL'
        validation_summary['errors'].append(f"Failed to identify Master-Detail fields: {str(e)}")
        return False, validation_summary
    
    # Validate each Master-Detail field
    for md_field_name, md_field_info in md_fields.items():
        parent_object = md_field_info['parent_object']
        
        # Check if this field exists in the data
        if md_field_name not in data_df.columns:
            validation_summary['warnings'].append(
                f"Master-Detail field '{md_field_name}' not found in data (will be skipped or default value used)"
            )
            continue
        
        # Validate parent existence
        is_valid, report = validate_master_detail_parents_exist(
            sf_conn=sf_conn,
            data_df=data_df,
            master_detail_field=md_field_name,
            parent_object=parent_object,
            match_field='Id'  # Default to ID matching
        )
        
        validation_summary['details'][md_field_name] = report
        
        if is_valid:
            validation_summary['valid_md_fields'] += 1
        else:
            validation_summary['invalid_md_fields'] += 1
            validation_summary['blocking_issues'] += report['missing']
            validation_summary['overall_status'] = 'FAIL'
    
    return validation_summary['overall_status'] == 'PASS', validation_summary


def generate_master_detail_validation_report(validation_summary: Dict) -> str:
    """
    Generate a human-readable validation report for Master-Detail relationships
    
    Args:
        validation_summary: Summary from validate_all_master_detail_relationships()
    
    Returns:
        Formatted report string
    """
    report_lines = [
        "\n" + "="*80,
        "MASTER-DETAIL RELATIONSHIP VALIDATION REPORT",
        "="*80,
        f"Object: {validation_summary['object']}",
        f"Overall Status: {'✅ PASS' if validation_summary['overall_status'] == 'PASS' else '❌ FAIL'}",
        f"Total Master-Detail Fields: {validation_summary['total_md_fields']}",
        f"Valid Fields: {validation_summary['valid_md_fields']}",
        f"Invalid Fields: {validation_summary['invalid_md_fields']}",
        f"Blocking Issues: {validation_summary['blocking_issues']}",
    ]
    
    if validation_summary['warnings']:
        report_lines.append("\n⚠️  WARNINGS:")
        for warning in validation_summary['warnings']:
            report_lines.append(f"  • {warning}")
    
    if validation_summary['details']:
        report_lines.append("\n📋 VALIDATION DETAILS:")
        for md_field, details in validation_summary['details'].items():
            status_icon = "✅" if details['status'] == 'PASS' else "❌"
            report_lines.append(f"\n  {status_icon} {md_field} → {details['parent_object']}")
            report_lines.append(f"     Total Parents: {details['total_parents']}")
            report_lines.append(f"     Found: {details['found']}")
            report_lines.append(f"     Missing: {details['missing']}")
            
            if details['missing_ids']:
                report_lines.append(f"     Missing Parent IDs: {', '.join(details['missing_ids'][:5])}")
                if len(details['missing_ids']) > 5:
                    report_lines.append(f"     ... and {len(details['missing_ids']) - 5} more")
            
            if details['errors']:
                report_lines.append(f"     Errors:")
                for error in details['errors'][:3]:
                    report_lines.append(f"       • {error}")
    
    if validation_summary['errors']:
        report_lines.append("\n❌ ERRORS:")
        for error in validation_summary['errors']:
            report_lines.append(f"  • {error}")
    
    if validation_summary['overall_status'] == 'FAIL':
        report_lines.append("\n" + "!"*80)
        report_lines.append("🚫 CANNOT PROCEED WITH DATA LOAD")
        report_lines.append("Master-Detail relationships are MANDATORY and blocking.")
        report_lines.append("All parent records must exist in Salesforce before loading child records.")
        report_lines.append("!"*80 + "\n")
    else:
        report_lines.append("\n" + "✓"*80)
        report_lines.append("✅ ALL MASTER-DETAIL VALIDATIONS PASSED")
        report_lines.append("Safe to proceed with data load.")
        report_lines.append("✓"*80 + "\n")
    
    return "\n".join(report_lines)


def check_cascading_delete_warnings(
    sf_conn: Salesforce,
    object_name: str,
    md_fields: Dict
) -> List[str]:
    """
    Generate warnings about cascading delete implications of Master-Detail relationships
    
    Args:
        sf_conn: Salesforce connection
        object_name: Object being loaded
        md_fields: Master-Detail fields dictionary
    
    Returns:
        List of warning messages
    """
    warnings = []
    
    if not md_fields:
        return warnings
    
    warnings.append("⚠️  IMPORTANT: Cascading Delete Implications")
    warnings.append(f"   {object_name} has {len(md_fields)} Master-Detail relationship(s):")
    
    for md_field_name, md_info in md_fields.items():
        parent_obj = md_info['parent_object']
        warnings.append(
            f"   • If a parent record in {parent_obj} is deleted, "
            f"ALL child records with {md_field_name} = that parent will be DELETED"
        )
    
    warnings.append("   Plan your data management strategy accordingly!")
    
    return warnings


def suggest_migration_order(
    sf_conn: Salesforce,
    object_names: List[str]
) -> Tuple[List[str], Dict]:
    """
    Suggest the order in which objects should be migrated based on Master-Detail dependencies
    
    Objects with no Master-Detail relationships should be loaded FIRST.
    Objects with Master-Detail relationships should be loaded AFTER their parents.
    
    Args:
        sf_conn: Salesforce connection
        object_names: List of objects to be migrated
    
    Returns:
        Tuple of (suggested_order: list, dependency_map: dict)
    """
    dependency_map = {}
    
    # Build dependency map
    for obj_name in object_names:
        md_fields = identify_master_detail_fields(sf_conn, obj_name)
        dependencies = []
        
        for md_field_name, md_info in md_fields.items():
            parent_obj = md_info['parent_object']
            if parent_obj in object_names:
                dependencies.append(parent_obj)
        
        dependency_map[obj_name] = list(set(dependencies))  # Remove duplicates
    
    # Topological sort: objects with no dependencies first
    suggested_order = []
    remaining = set(object_names)
    
    while remaining:
        # Find objects with no dependencies in remaining
        ready = [obj for obj in remaining if not any(dep in remaining for dep in dependency_map.get(obj, []))]
        
        if not ready:
            # Circular dependency or all remaining have dependencies
            remaining_list = list(remaining)
            suggested_order.extend(remaining_list)
            break
        
        # Sort ready objects by name for consistent ordering
        ready.sort()
        suggested_order.extend(ready)
        remaining -= set(ready)
    
    return suggested_order, dependency_map
