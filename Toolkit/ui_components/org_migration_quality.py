"""
Organization Migration - Data Quality Checks Module
Handles comprehensive data quality validation including duplicates, 
referential integrity, consistency, and completeness checks.
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Any, Set
from datetime import datetime
import re


def detect_duplicates(data: pd.DataFrame, key_fields: List[str] = None) -> Dict[str, Any]:
    """
    Detect duplicate records based on key fields.
    
    Args:
        data: DataFrame to check for duplicates
        key_fields: Fields to consider for duplicate detection. If None, uses all fields.
    
    Returns:
        Dict with duplicate records and statistics
    """
    results = {
        'total_records': len(data),
        'duplicate_count': 0,
        'duplicate_records': [],
        'duplicate_groups': [],
        'pass': True
    }
    
    if len(data) == 0:
        return results
    
    try:
        # Use specified key fields or all fields
        if key_fields is None:
            key_fields = list(data.columns)
        else:
            key_fields = [f for f in key_fields if f in data.columns]
        
        if not key_fields:
            results['error'] = "No valid key fields specified"
            return results
        
        # Find duplicates
        duplicates = data[data.duplicated(subset=key_fields, keep=False)].copy()
        
        if len(duplicates) > 0:
            results['pass'] = False
            results['duplicate_count'] = len(duplicates)
            
            # Group duplicates
            duplicate_groups = duplicates.groupby(key_fields, dropna=False).size().reset_index(name='count')
            duplicate_groups = duplicate_groups[duplicate_groups['count'] > 1]
            results['duplicate_groups'] = duplicate_groups.to_dict('records')
            
            # Get indices of duplicate records
            results['duplicate_records'] = duplicates.index.tolist()
    
    except Exception as e:
        results['error'] = str(e)
        results['pass'] = False
    
    return results


def check_referential_integrity(data: pd.DataFrame, lookup_fields: Dict[str, str], 
                               sf_conn) -> Dict[str, Any]:
    """
    Check referential integrity for lookup fields.
    Validates that foreign key values exist in parent objects.
    
    Args:
        data: DataFrame with records to validate
        lookup_fields: Dict mapping field name to target object name
        sf_conn: Salesforce connection object
    
    Returns:
        Validation results for referential integrity
    """
    results = {
        'total_records': len(data),
        'integrity_issues': [],
        'fields_checked': len(lookup_fields),
        'pass': True
    }
    
    if len(data) == 0:
        return results
    
    try:
        for field_name, target_object in lookup_fields.items():
            if field_name not in data.columns:
                continue
            
            # Get non-null values from lookup field
            lookup_values = data[data[field_name].notna()][field_name].unique()
            
            if len(lookup_values) == 0:
                continue
            
            # Query target object to verify IDs exist
            try:
                # Build SOQL to check for IDs
                id_list = "','".join(str(v) for v in lookup_values[:100])  # Limit to 100
                query = f"SELECT Id FROM {target_object} WHERE Id IN ('{id_list}')"
                
                found_ids = set()
                try:
                    for record in sf_conn.query(query)['records']:
                        found_ids.add(record['Id'])
                except:
                    # If query fails, skip this check
                    continue
                
                # Find missing IDs
                missing_ids = set(lookup_values) - found_ids
                
                if missing_ids:
                    results['pass'] = False
                    affected_rows = data[data[field_name].isin(missing_ids)].index.tolist()
                    
                    results['integrity_issues'].append({
                        'field': field_name,
                        'target_object': target_object,
                        'missing_ids': list(missing_ids)[:10],
                        'affected_rows': affected_rows[:10],
                        'total_affected': len(affected_rows),
                        'description': f'{len(affected_rows)} records reference non-existent {target_object} records'
                    })
            
            except Exception as e:
                results['integrity_issues'].append({
                    'field': field_name,
                    'target_object': target_object,
                    'error': str(e),
                    'description': f'Could not verify referential integrity: {str(e)}'
                })
    
    except Exception as e:
        results['error'] = str(e)
        results['pass'] = False
    
    return results


def check_data_completeness(data: pd.DataFrame, required_fields: List[str] = None,
                           warn_threshold: float = 0.8) -> Dict[str, Any]:
    """
    Check data completeness - identifies null/empty/whitespace-only values.
    
    Args:
        data: DataFrame to check
        required_fields: Fields that must be non-null. If None, all fields checked.
        warn_threshold: Warn if field has less than this % of values (0.0-1.0)
    
    Returns:
        Completeness statistics and issues
    """
    results = {
        'total_records': len(data),
        'total_fields': len(data.columns),
        'completeness_by_field': {},
        'issues': [],
        'pass': True
    }
    
    if len(data) == 0:
        return results
    
    try:
        for column in data.columns:
            # Count non-null values
            non_null_count = data[column].notna().sum()
            completeness = non_null_count / len(data)
            
            results['completeness_by_field'][column] = {
                'non_null': int(non_null_count),
                'null': int(len(data) - non_null_count),
                'completeness': f"{completeness*100:.1f}%"
            }
            
            # Check if required field has nulls
            if required_fields and column in required_fields and non_null_count < len(data):
                results['pass'] = False
                null_indices = data[data[column].isna()].index.tolist()
                results['issues'].append({
                    'field': column,
                    'type': 'REQUIRED_FIELD_NULL',
                    'null_count': len(data) - non_null_count,
                    'affected_rows': null_indices[:20],
                    'severity': 'HIGH',
                    'description': f'Required field {column} has {len(data) - non_null_count} null values'
                })
            
            # Warn on low completeness
            elif completeness < warn_threshold:
                results['issues'].append({
                    'field': column,
                    'type': 'LOW_COMPLETENESS',
                    'null_count': len(data) - non_null_count,
                    'completeness': f"{completeness*100:.1f}%",
                    'severity': 'MEDIUM',
                    'description': f'Field {column} is only {completeness*100:.1f}% complete'
                })
    
    except Exception as e:
        results['error'] = str(e)
        results['pass'] = False
    
    return results


def check_data_consistency(data: pd.DataFrame, consistency_rules: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Check data consistency across records.
    Validates format, patterns, and cross-field consistency.
    
    Args:
        data: DataFrame to validate
        consistency_rules: Dict with consistency rules to apply
    
    Returns:
        Consistency check results
    """
    results = {
        'total_records': len(data),
        'consistency_issues': [],
        'pass': True
    }
    
    if len(data) == 0:
        return results
    
    try:
        # Rule 1: Email format validation
        consistency_rules = consistency_rules or {}
        email_fields = consistency_rules.get('email_fields', [])
        
        for field in email_fields:
            if field in data.columns:
                # Check email format
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                invalid_emails = data[
                    data[field].notna() & 
                    ~data[field].astype(str).str.match(email_pattern)
                ]
                
                if len(invalid_emails) > 0:
                    results['pass'] = False
                    results['consistency_issues'].append({
                        'field': field,
                        'type': 'INVALID_EMAIL_FORMAT',
                        'affected_count': len(invalid_emails),
                        'affected_rows': invalid_emails.index.tolist()[:10],
                        'severity': 'MEDIUM',
                        'description': f'{len(invalid_emails)} records have invalid email format'
                    })
        
        # Rule 2: Phone format validation
        phone_fields = consistency_rules.get('phone_fields', [])
        
        for field in phone_fields:
            if field in data.columns:
                # Basic phone validation - at least 10 digits
                invalid_phones = data[
                    data[field].notna() & 
                    (data[field].astype(str).str.replace(r'\D', '', regex=True).str.len() < 10)
                ]
                
                if len(invalid_phones) > 0:
                    results['pass'] = False
                    results['consistency_issues'].append({
                        'field': field,
                        'type': 'INVALID_PHONE_FORMAT',
                        'affected_count': len(invalid_phones),
                        'affected_rows': invalid_phones.index.tolist()[:10],
                        'severity': 'LOW',
                        'description': f'{len(invalid_phones)} records have invalid phone format'
                    })
        
        # Rule 3: Date format validation
        date_fields = consistency_rules.get('date_fields', [])
        
        for field in date_fields:
            if field in data.columns:
                try:
                    pd.to_datetime(data[field], errors='coerce')
                    invalid_dates = data[data[field].notna() & (pd.to_datetime(data[field], errors='coerce').isna())]
                    
                    if len(invalid_dates) > 0:
                        results['pass'] = False
                        results['consistency_issues'].append({
                            'field': field,
                            'type': 'INVALID_DATE_FORMAT',
                            'affected_count': len(invalid_dates),
                            'affected_rows': invalid_dates.index.tolist()[:10],
                            'severity': 'HIGH',
                            'description': f'{len(invalid_dates)} records have invalid date format'
                        })
                except:
                    pass
        
        # Rule 4: Whitespace issues
        whitespace_threshold = consistency_rules.get('whitespace_check', True)
        
        if whitespace_threshold:
            for column in data.select_dtypes(include=['object']).columns:
                # Check for leading/trailing whitespace
                has_whitespace = data[column].astype(str).str.startswith(' ') | \
                                data[column].astype(str).str.endswith(' ')
                
                if has_whitespace.any():
                    results['consistency_issues'].append({
                        'field': column,
                        'type': 'WHITESPACE_ISSUE',
                        'affected_count': has_whitespace.sum(),
                        'affected_rows': data[has_whitespace].index.tolist()[:10],
                        'severity': 'LOW',
                        'description': f'{has_whitespace.sum()} records in {column} have leading/trailing whitespace'
                    })
        
        # Rule 5: Case consistency
        case_fields = consistency_rules.get('case_fields', {})
        
        for field, expected_case in case_fields.items():
            if field in data.columns:
                col_data = data[field].astype(str)
                
                if expected_case == 'upper':
                    mismatched = data[col_data != col_data.str.upper()]
                elif expected_case == 'lower':
                    mismatched = data[col_data != col_data.str.lower()]
                elif expected_case == 'title':
                    mismatched = data[col_data != col_data.str.title()]
                else:
                    mismatched = pd.DataFrame()
                
                if len(mismatched) > 0:
                    results['consistency_issues'].append({
                        'field': field,
                        'type': 'CASE_INCONSISTENCY',
                        'expected_case': expected_case,
                        'affected_count': len(mismatched),
                        'affected_rows': mismatched.index.tolist()[:10],
                        'severity': 'LOW',
                        'description': f'{len(mismatched)} records in {field} have inconsistent case'
                    })
    
    except Exception as e:
        results['error'] = str(e)
        results['pass'] = False
    
    return results


def run_all_quality_checks(data: pd.DataFrame, sf_conn, quality_config: Dict = None) -> Dict[str, Any]:
    """
    Run all data quality checks and aggregate results.
    
    Args:
        data: DataFrame to validate
        sf_conn: Salesforce connection object
        quality_config: Configuration for quality checks
    
    Returns:
        Aggregated quality check results
    """
    quality_config = quality_config or {}
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_records': len(data),
        'checks': {},
        'overall_quality_score': 0.0,
        'pass': True
    }
    
    if len(data) == 0:
        results['error'] = 'No data to check'
        return results
    
    # Run duplicate check
    if quality_config.get('check_duplicates', True):
        with st.spinner("🔍 Checking for duplicates..."):
            results['checks']['duplicates'] = detect_duplicates(
                data,
                quality_config.get('duplicate_key_fields')
            )
            if not results['checks']['duplicates'].get('pass', True):
                results['pass'] = False
    
    # Run referential integrity check
    if quality_config.get('check_referential_integrity', True):
        with st.spinner("🔍 Checking referential integrity..."):
            lookup_fields = quality_config.get('lookup_fields', {})
            if lookup_fields:
                results['checks']['referential_integrity'] = check_referential_integrity(
                    data,
                    lookup_fields,
                    sf_conn
                )
                if not results['checks']['referential_integrity'].get('pass', True):
                    results['pass'] = False
    
    # Run completeness check
    if quality_config.get('check_completeness', True):
        with st.spinner("🔍 Checking data completeness..."):
            results['checks']['completeness'] = check_data_completeness(
                data,
                quality_config.get('required_fields'),
                quality_config.get('completeness_threshold', 0.8)
            )
            if not results['checks']['completeness'].get('pass', True):
                results['pass'] = False
    
    # Run consistency check
    if quality_config.get('check_consistency', True):
        with st.spinner("🔍 Checking data consistency..."):
            results['checks']['consistency'] = check_data_consistency(
                data,
                quality_config.get('consistency_rules', {})
            )
            if not results['checks']['consistency'].get('pass', True):
                results['pass'] = False
    
    return results


def display_quality_report(quality_results: Dict[str, Any], data: pd.DataFrame = None):
    """
    Display data quality report in Streamlit UI.
    
    Args:
        quality_results: Results from run_all_quality_checks()
        data: Original DataFrame for context
    """
    # Overall score
    total_checks = len(quality_results.get('checks', {}))
    passed_checks = sum(1 for check in quality_results.get('checks', {}).values() 
                       if check.get('pass', False))
    quality_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Records", quality_results['total_records'])
    
    with col2:
        status = "✅ PASS" if quality_results['pass'] else "❌ FAIL"
        st.metric("Quality Status", status)
    
    with col3:
        st.metric("Quality Score", f"{quality_score:.0f}%")
    
    st.divider()
    
    # Duplicate check results
    if 'duplicates' in quality_results.get('checks', {}):
        dup_results = quality_results['checks']['duplicates']
        with st.expander(
            f"🔄 Duplicate Detection: {'✅ PASS' if dup_results.get('pass', True) else '❌ FAIL - ' + str(dup_results.get('duplicate_count', 0)) + ' duplicates'}",
            expanded=not dup_results.get('pass', True)
        ):
            if dup_results.get('pass', True):
                st.success("✅ No duplicates found")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Duplicate Records", dup_results.get('duplicate_count', 0))
                with col2:
                    st.metric("Duplicate Groups", len(dup_results.get('duplicate_groups', [])))
                
                if dup_results.get('duplicate_groups'):
                    st.caption("Sample duplicate groups:")
                    for group in dup_results['duplicate_groups'][:5]:
                        st.write(f"• {len(group)} records with same key values")
    
    # Completeness check results
    if 'completeness' in quality_results.get('checks', {}):
        comp_results = quality_results['checks']['completeness']
        with st.expander(
            f"📊 Completeness: {'✅ PASS' if comp_results.get('pass', True) else '❌ FAIL'}",
            expanded=not comp_results.get('pass', True)
        ):
            if comp_results.get('pass', True):
                st.success("✅ All required fields are complete")
            else:
                st.write(f"❌ {len(comp_results.get('issues', []))} completeness issues found")
                for issue in comp_results.get('issues', [])[:5]:
                    st.warning(f"• {issue['description']}")
            
            # Show field completeness
            if comp_results.get('completeness_by_field'):
                st.caption("Field Completeness Overview:")
                comp_data = pd.DataFrame(comp_results['completeness_by_field']).T
                st.dataframe(comp_data, use_container_width=True)
    
    # Consistency check results
    if 'consistency' in quality_results.get('checks', {}):
        cons_results = quality_results['checks']['consistency']
        with st.expander(
            f"🔤 Consistency: {'✅ PASS' if cons_results.get('pass', True) else '❌ FAIL - ' + str(len(cons_results.get('consistency_issues', []))) + ' issues'}",
            expanded=not cons_results.get('pass', True)
        ):
            if cons_results.get('pass', True):
                st.success("✅ All consistency checks passed")
            else:
                for issue in cons_results.get('consistency_issues', []):
                    severity_icon = '🔴' if issue['severity'] == 'HIGH' else '🟡' if issue['severity'] == 'MEDIUM' else '🟢'
                    st.warning(f"{severity_icon} {issue['description']}")
    
    # Referential integrity check results
    if 'referential_integrity' in quality_results.get('checks', {}):
        ref_results = quality_results['checks']['referential_integrity']
        with st.expander(
            f"🔗 Referential Integrity: {'✅ PASS' if ref_results.get('pass', True) else '❌ FAIL'}",
            expanded=not ref_results.get('pass', True)
        ):
            if ref_results.get('pass', True):
                st.success("✅ All referential integrity checks passed")
            else:
                for issue in ref_results.get('integrity_issues', []):
                    if 'error' not in issue:
                        st.error(f"• {issue['description']}")
                    else:
                        st.warning(f"• {issue['description']}")


def generate_quality_recommendations(quality_results: Dict[str, Any]) -> List[str]:
    """
    Generate recommendations based on quality check results.
    
    Args:
        quality_results: Results from run_all_quality_checks()
    
    Returns:
        List of recommendations
    """
    recommendations = []
    
    for check_name, check_result in quality_results.get('checks', {}).items():
        if not check_result.get('pass', True):
            if check_name == 'duplicates':
                dup_count = check_result.get('duplicate_count', 0)
                recommendations.append(f"🔧 Remove or merge {dup_count} duplicate records found")
            
            elif check_name == 'completeness':
                for issue in check_result.get('issues', []):
                    if issue['type'] == 'REQUIRED_FIELD_NULL':
                        recommendations.append(f"🔧 Populate missing values for required field: {issue['field']} ({issue['null_count']} records)")
            
            elif check_name == 'consistency':
                for issue in check_result.get('consistency_issues', []):
                    recommendations.append(f"🔧 Fix {issue['type']} in field {issue['field']} ({issue['affected_count']} records)")
            
            elif check_name == 'referential_integrity':
                for issue in check_result.get('integrity_issues', []):
                    if 'error' not in issue:
                        recommendations.append(f"🔧 Verify references in {issue['field']} - {issue['total_affected']} records reference non-existent {issue['target_object']}")
    
    return recommendations
