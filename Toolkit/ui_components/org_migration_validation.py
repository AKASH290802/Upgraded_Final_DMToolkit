"""
Org Migration Validation Module
================================
Pre-migration validation checks for Salesforce Org-to-Org migration.
Validates data against target org schema and business rules before insertion.

Functions:
    - validate_required_fields()
    - validate_data_types()
    - validate_picklist_values()
    - validate_field_length()
    - generate_validation_report()
    - run_all_validations()
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Optional, Any


def validate_required_fields(data: pd.DataFrame, target_sf_conn, object_name: str, field_mappings: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Validate that all required fields in target org have values in source data
    
    Args:
        data: DataFrame with source data
        target_sf_conn: Salesforce connection to target org
        object_name: Name of Salesforce object being migrated
        field_mappings: Dict mapping source columns to target fields (only check these fields)
    
    Returns:
        Dictionary with validation results
    """
    try:
        from .utils import get_object_description
        
        # Get field descriptions from target org
        target_object_info = get_object_description(target_sf_conn, object_name)
        
        if not target_object_info or 'fields' not in target_object_info:
            return {
                'passed': False,
                'error': 'Could not retrieve object metadata from target org',
                'total_fields': 0,
                'required_fields': 0,
                'missing_in_data': 0,
                'missing_fields': [],
                'results': []
            }
        
        fields = target_object_info['fields']
        
        # Fields that are auto-populated by Salesforce and should be skipped
        SYSTEM_FIELDS_TO_SKIP = {
            'Id',  # Primary key, assigned by Salesforce
            'OwnerId',  # Auto-assigned to current user if not provided
            'CreatedById',  # Auto-populated
            'CreatedDate',  # Auto-populated
            'LastModifiedById',  # Auto-populated
            'LastModifiedDate',  # Auto-populated
            'SystemModstamp'  # Auto-populated
        }
        
        # Filter for required fields (not nullable, not updateable but required)
        required_fields = [
            f for f in fields 
            if f.get('nillable') == False 
            and f.get('createable') == True
            and not f.get('name', '').startswith('attributes')
            and f.get('name') not in SYSTEM_FIELDS_TO_SKIP  # Skip system fields
        ]
        
        # If field_mappings provided, only check required fields that are being migrated
        if field_mappings:
            target_fields_in_mapping = set(field_mappings.values())
            required_fields = [f for f in required_fields if f['name'] in target_fields_in_mapping]
        
        results = []
        missing_fields_list = []
        missing_count = 0
        target_fields_in_mapping = set(field_mappings.values()) if field_mappings else set()
        
        for field in required_fields:
            field_name = field['name']
            field_label = field.get('label', field_name)
            
            # Find matching source column
            source_col = None
            if field_mappings:
                # Find source column that maps to this field
                for src_col, tgt_field in field_mappings.items():
                    if tgt_field == field_name:
                        source_col = src_col
                        break
            else:
                # Case-insensitive search in data columns
                data_columns_lower = {col.lower(): col for col in data.columns}
                field_name_lower = field_name.lower()
                if field_name_lower in data_columns_lower:
                    source_col = data_columns_lower[field_name_lower]
            
            if source_col and source_col in data.columns:
                # Field found in source data - check for missing values
                missing_in_rows = data[source_col].isna().sum() + (data[source_col] == '').sum()
                
                results.append({
                    'field': field_name,
                    'label': field_label,
                    'required': True,
                    'has_values': missing_in_rows == 0,
                    'missing_count': missing_in_rows,
                    'missing_percent': (missing_in_rows / len(data) * 100) if len(data) > 0 else 0
                })
                
                if missing_in_rows > 0:
                    missing_fields_list.append({
                        'field': field_name,
                        'label': field_label,
                        'missing_count': missing_in_rows
                    })
                    missing_count += missing_in_rows
            elif field_mappings and field_name not in target_fields_in_mapping:
                # Field is NOT being migrated (not in field_mappings) - skip it
                continue
            else:
                # Field is required and should be migrated but not found in source data
                results.append({
                    'field': field_name,
                    'label': field_label,
                    'required': True,
                    'has_values': False,
                    'missing_count': len(data),
                    'missing_percent': 100
                })
                
                missing_fields_list.append({
                    'field': field_name,
                    'label': field_label,
                    'missing_count': len(data)
                })
                missing_count += len(data)
        
        passed = len(missing_fields_list) == 0
        
        return {
            'passed': passed,
            'total_fields': len(fields),
            'required_fields': len(required_fields),
            'missing_in_data': len(missing_fields_list),
            'missing_fields': missing_fields_list,
            'results': results,
            'error': None
        }
    
    except Exception as e:
        return {
            'passed': False,
            'error': f'Error validating required fields: {str(e)}',
            'total_fields': 0,
            'required_fields': 0,
            'missing_in_data': 0,
            'missing_fields': [],
            'results': []
        }


def validate_data_types(data: pd.DataFrame, target_sf_conn, object_name: str, field_mappings: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Validate that source data types are compatible with target field types
    
    Args:
        data: DataFrame with source data
        target_sf_conn: Salesforce connection to target org
        object_name: Name of Salesforce object
        field_mappings: Dict mapping source columns to target fields
    
    Returns:
        Dictionary with validation results
    """
    try:
        from .utils import get_object_description
        
        target_object_info = get_object_description(target_sf_conn, object_name)
        
        if not target_object_info or 'fields' not in target_object_info:
            return {
                'passed': False,
                'error': 'Could not retrieve object metadata',
                'results': []
            }
        
        # Create field type lookup
        field_types = {f['name']: f.get('type', 'string') for f in target_object_info['fields']}
        
        results = []
        issues = 0
        
        # If field mappings provided, use those; otherwise check all columns
        if field_mappings:
            columns_to_check = field_mappings.items()
        else:
            columns_to_check = [(col, col) for col in data.columns]
        
        for source_col, target_field in columns_to_check:
            if source_col not in data.columns:
                continue
            
            target_type = field_types.get(target_field, 'unknown')
            source_values = data[source_col].dropna().astype(str).unique()
            
            # Simple type compatibility check
            type_compatible = True
            warnings = []
            
            if target_type == 'int' or target_type == 'long':
                # Check if source data can be converted to integer
                try:
                    for val in source_values[:10]:  # Sample check
                        if val and val.strip() and str(val) != 'nan':
                            int(float(val))
                except (ValueError, TypeError):
                    type_compatible = False
                    warnings.append(f"Non-numeric values found in {source_col} but target is {target_type}")
            
            elif target_type == 'double' or target_type == 'currency':
                # Check if source data can be converted to float
                try:
                    for val in source_values[:10]:
                        if val and val.strip() and str(val) != 'nan':
                            float(val)
                except (ValueError, TypeError):
                    type_compatible = False
                    warnings.append(f"Non-numeric values in {source_col} but target is {target_type}")
            
            elif target_type == 'date' or target_type == 'datetime':
                # Check date format
                import re
                date_pattern = r'^\d{4}-\d{2}-\d{2}'
                for val in source_values[:10]:
                    if val and val.strip() and not re.match(date_pattern, str(val)):
                        type_compatible = False
                        warnings.append(f"Invalid date format in {source_col}")
                        break
            
            result = {
                'source_field': source_col,
                'target_field': target_field,
                'target_type': target_type,
                'compatible': type_compatible,
                'warnings': warnings
            }
            results.append(result)
            
            if not type_compatible:
                issues += 1
        
        return {
            'passed': issues == 0,
            'issues': issues,
            'results': results,
            'error': None
        }
    
    except Exception as e:
        return {
            'passed': False,
            'error': f'Error validating data types: {str(e)}',
            'results': []
        }


def validate_picklist_values(data: pd.DataFrame, target_sf_conn, object_name: str, field_mappings: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Validate that picklist values in source data are valid in target org
    
    Args:
        data: DataFrame with source data
        target_sf_conn: Salesforce connection to target org
        object_name: Name of Salesforce object
        field_mappings: Dict mapping source columns to target fields
    
    Returns:
        Dictionary with validation results
    """
    try:
        from .utils import get_object_description
        
        target_object_info = get_object_description(target_sf_conn, object_name)
        
        if not target_object_info or 'fields' not in target_object_info:
            return {
                'passed': False,
                'error': 'Could not retrieve object metadata',
                'picklist_fields': []
            }
        
        fields = target_object_info['fields']
        picklist_fields = {f['name']: f.get('picklistValues', []) for f in fields if f.get('type') == 'picklist'}
        
        results = []
        invalid_count = 0
        
        # If field mappings provided, use those; otherwise check all columns
        if field_mappings:
            columns_to_check = field_mappings.items()
        else:
            columns_to_check = [(col, col) for col in data.columns]
        
        for source_col, target_field in columns_to_check:
            if source_col not in data.columns or target_field not in picklist_fields:
                continue
            
            valid_values = {pv['value'] for pv in picklist_fields[target_field]}
            source_values = set(data[source_col].dropna().astype(str).unique())
            
            invalid_values = source_values - valid_values
            invalid_values = {v for v in invalid_values if v and v != 'nan'}
            
            result = {
                'field': target_field,
                'source_column': source_col,
                'valid_values': list(valid_values),
                'invalid_values': list(invalid_values),
                'invalid_count': len(data[data[source_col].isin(invalid_values)]) if invalid_values else 0
            }
            results.append(result)
            
            if invalid_values:
                invalid_count += len(result['invalid_count'])
        
        return {
            'passed': invalid_count == 0,
            'invalid_values_count': invalid_count,
            'picklist_fields': results,
            'error': None
        }
    
    except Exception as e:
        return {
            'passed': False,
            'error': f'Error validating picklist values: {str(e)}',
            'picklist_fields': []
        }


def validate_field_length(data: pd.DataFrame, target_sf_conn, object_name: str, field_mappings: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Validate that field values don't exceed max length in target org
    
    Args:
        data: DataFrame with source data
        target_sf_conn: Salesforce connection to target org
        object_name: Name of Salesforce object
        field_mappings: Dict mapping source columns to target fields
    
    Returns:
        Dictionary with validation results
    """
    try:
        from .utils import get_object_description
        
        target_object_info = get_object_description(target_sf_conn, object_name)
        
        if not target_object_info or 'fields' not in target_object_info:
            return {
                'passed': False,
                'error': 'Could not retrieve object metadata',
                'results': []
            }
        
        fields = target_object_info['fields']
        field_lengths = {f['name']: f.get('length', None) for f in fields}
        
        results = []
        violations = 0
        
        # If field mappings provided, use those; otherwise check all columns
        if field_mappings:
            columns_to_check = field_mappings.items()
        else:
            columns_to_check = [(col, col) for col in data.columns]
        
        for source_col, target_field in columns_to_check:
            if source_col not in data.columns or target_field not in field_lengths:
                continue
            
            max_length = field_lengths[target_field]
            
            # SKIP fields with max_length = 0 (read-only, formula, system fields)
            # These cannot be populated during insert/update
            if max_length is None or max_length == 0:
                continue
            
            # Check field values
            data_copy = data.copy()
            data_copy[source_col] = data_copy[source_col].astype(str)
            exceeds_length = data_copy[data_copy[source_col].str.len() > max_length]
            exceed_count = len(exceeds_length)
            
            if exceed_count > 0:
                result = {
                    'field': target_field,
                    'source_column': source_col,
                    'max_length': max_length,
                    'exceed_count': exceed_count,
                    'exceed_percent': (exceed_count / len(data) * 100) if len(data) > 0 else 0
                }
                results.append(result)
                violations += exceed_count
        
        return {
            'passed': violations == 0,
            'violations': violations,
            'results': results,
            'error': None
        }
    
    except Exception as e:
        return {
            'passed': False,
            'error': f'Error validating field length: {str(e)}',
            'results': []
        }


def run_all_validations(data: pd.DataFrame, target_sf_conn, object_name: str, field_mappings: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Run all schema validations and generate comprehensive report
    
    Args:
        data: DataFrame with source data
        target_sf_conn: Salesforce connection to target org
        object_name: Name of Salesforce object
        field_mappings: Dict mapping source columns to target fields
    
    Returns:
        Comprehensive validation report
    """
    import time
    
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'object': object_name,
        'total_records': len(data),
        'total_fields': len(data.columns),
        'validations': {}
    }
    
    # Run all validations
    st.info("🔍 Running schema validations...")
    
    with st.spinner("Checking required fields..."):
        report['validations']['required_fields'] = validate_required_fields(data, target_sf_conn, object_name)
    
    with st.spinner("Checking data types..."):
        report['validations']['data_types'] = validate_data_types(data, target_sf_conn, object_name, field_mappings)
    
    with st.spinner("Checking picklist values..."):
        report['validations']['picklist_values'] = validate_picklist_values(data, target_sf_conn, object_name, field_mappings)
    
    with st.spinner("Checking field lengths..."):
        report['validations']['field_length'] = validate_field_length(data, target_sf_conn, object_name, field_mappings)
    
    # Calculate overall result
    all_passed = all(v.get('passed', False) for v in report['validations'].values())
    report['all_passed'] = all_passed
    
    # Count issues
    report['total_issues'] = sum(
        len(v.get('missing_fields', [])) +
        v.get('issues', 0) +
        len(v.get('picklist_fields', [])) +
        len(v.get('results', []))
        for v in report['validations'].values()
    )
    
    return report


def display_validation_report(report: Dict[str, Any]):
    """
    Display validation report in Streamlit UI
    
    Args:
        report: Validation report from run_all_validations()
    """
    if not report:
        st.error("No validation report available")
        return
    
    # Overall status
    if report.get('all_passed'):
        st.success(f"✅ **Schema Validation PASSED** - All {report['total_records']} records ready to migrate")
    else:
        st.warning(f"⚠️ **Schema Validation FOUND ISSUES** - {report['total_issues']} issues detected")
    
    st.divider()
    
    # Required Fields Validation
    rf_result = report['validations'].get('required_fields', {})
    with st.expander("🔍 Required Fields Check", expanded=True):
        if rf_result.get('error'):
            st.error(f"Error: {rf_result['error']}")
        else:
            if rf_result.get('passed'):
                st.success(f"✅ All {rf_result['required_fields']} required fields present")
            else:
                st.error(f"❌ {rf_result['missing_in_data']} required fields have missing values")
                
                # Show missing fields
                if rf_result.get('missing_fields'):
                    st.write("**Missing fields:**")
                    for field in rf_result['missing_fields']:
                        st.write(f"  • `{field['field']}` ({field['label']}) - {field['missing_count']} missing")
    
    # Data Types Validation
    dt_result = report['validations'].get('data_types', {})
    with st.expander("📊 Data Type Compatibility Check", expanded=False):
        if dt_result.get('error'):
            st.error(f"Error: {dt_result['error']}")
        else:
            if dt_result.get('passed'):
                st.success("✅ All data types are compatible")
            else:
                st.warning(f"⚠️ {dt_result['issues']} type compatibility issues found")
                
                # Show issues
                for result in dt_result.get('results', []):
                    if not result['compatible'] and result.get('warnings'):
                        st.write(f"  • `{result['source_field']}` → `{result['target_field']}` ({result['target_type']})")
                        for warning in result['warnings']:
                            st.write(f"    ⚠️ {warning}")
    
    # Picklist Validation
    pv_result = report['validations'].get('picklist_values', {})
    with st.expander("🎯 Picklist Values Check", expanded=False):
        if pv_result.get('error'):
            st.error(f"Error: {pv_result['error']}")
        else:
            if pv_result.get('passed'):
                st.success("✅ All picklist values are valid")
            else:
                st.warning(f"⚠️ Invalid picklist values found")
                
                for result in pv_result.get('picklist_fields', []):
                    if result['invalid_values']:
                        st.write(f"  • `{result['field']}` - {len(result['invalid_values'])} invalid values:")
                        st.write(f"    Invalid: {', '.join(result['invalid_values'][:5])}")
                        st.write(f"    Valid: {', '.join(list(result['valid_values'])[:5])}")
    
    # Field Length Validation
    fl_result = report['validations'].get('field_length', {})
    with st.expander("📏 Field Length Check", expanded=False):
        if fl_result.get('error'):
            st.error(f"Error: {fl_result['error']}")
        else:
            if fl_result.get('passed'):
                st.success("✅ All field values are within length limits")
            else:
                st.warning(f"⚠️ {fl_result['violations']} field length violations found")
                
                for result in fl_result.get('results', []):
                    st.write(f"  • `{result['field']}` (max: {result['max_length']}) - {result['exceed_count']} exceeding")
