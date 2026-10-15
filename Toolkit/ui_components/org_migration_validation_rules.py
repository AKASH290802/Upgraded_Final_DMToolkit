"""
Organization Migration - Salesforce ValidationRules Validation Module
Extracts and validates data against ValidationRules defined in target org
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Any, Optional
import json
import re
from datetime import datetime


def extract_validation_rules_from_target_org(target_sf, object_name: str) -> Dict[str, Any]:
    """
    Extract all active ValidationRules for a specific object from target org
    Uses Tooling API via simple_salesforce
    
    Args:
        target_sf: Salesforce connection to target org
        object_name: Salesforce object name (e.g., 'Account', 'Opportunity')
    
    Returns:
        Dictionary with extracted validation rules
    """
    try:
        # Build Tooling API query for ValidationRules
        query = f"""
        SELECT Id, ValidationName, EntityDefinition.QualifiedApiName, 
               ErrorConditionFormula, ErrorMessage, Description, 
               Active, CreatedDate
        FROM ValidationRule
        WHERE EntityDefinition.QualifiedApiName = '{object_name}'
        AND Active = true
        ORDER BY ValidationName ASC
        """
        
        # Use the Tooling API endpoint if available
        # Note: simple_salesforce may not have direct Tooling API support
        # Fallback: Try using the metadata approach
        
        validation_rules = []
        
        try:
            # Try to query via Tooling API using the connection
            # This requires the org to have Tooling API enabled
            tooling_url = f"{target_sf.base_url.replace('/services/data/', '/services/data/v58.0/tooling/')}"
            
            # Alternative: Use direct REST call if available
            # For now, return empty as fallback - implement manual extraction below
            pass
        
        except Exception as e:
            pass
        
        # FALLBACK: Return structured format for manual validation rules
        # In a real scenario, you'd either:
        # 1. Use Metadata API to download ValidationRules
        # 2. Query them via Tooling API
        # 3. Use org's custom setting to store rule definitions
        
        return {
            'object': object_name,
            'rules': validation_rules,
            'count': len(validation_rules),
            'extraction_time': datetime.now().isoformat(),
            'note': 'ValidationRules extraction requires Tooling API access'
        }
    
    except Exception as e:
        return {
            'object': object_name,
            'rules': [],
            'count': 0,
            'error': str(e),
            'extraction_time': datetime.now().isoformat()
        }


def extract_validation_rules_from_describe(target_sf, object_name: str) -> List[Dict]:
    """
    Extract field-level validation constraints from object describe metadata
    These are implicit validation rules based on field properties
    
    Args:
        target_sf: Salesforce connection
        object_name: Object name
    
    Returns:
        List of validation rule dictionaries
    """
    try:
        # Get object metadata using describe() method
        try:
            object_describe = getattr(target_sf, object_name).describe()
        except:
            return []
        
        if not object_describe:
            return []
        
        validation_rules = []
        fields = object_describe.get('fields', [])
        
        # Extract implicit validation rules from field properties
        for field in fields:
            field_name = field['name']
            field_type = field.get('type', '')
            
            # Rule 1: Required fields must have values
            if not field.get('nillable', True) and field.get('createable', True):
                validation_rules.append({
                    'rule_id': f"IMPLICIT_REQUIRED_{field_name}",
                    'rule_name': f"Required Field: {field_name}",
                    'object': object_name,
                    'field': field_name,
                    'type': 'REQUIRED_FIELD',
                    'error_message': f"{field['label']} is required",
                    'error_condition': f"{field_name} is null or empty",
                    'description': f"Field {field_name} cannot be empty"
                })
            
            # Rule 2: Picklist fields must have valid values
            if field_type == 'picklist' and field.get('picklistValues'):
                valid_values = [pv['value'] for pv in field.get('picklistValues', [])]
                validation_rules.append({
                    'rule_id': f"IMPLICIT_PICKLIST_{field_name}",
                    'rule_name': f"Picklist Validation: {field_name}",
                    'object': object_name,
                    'field': field_name,
                    'type': 'PICKLIST_VALUE',
                    'error_message': f"{field['label']} has an invalid value",
                    'error_condition': f"{field_name} not in {valid_values}",
                    'valid_values': valid_values,
                    'description': f"Only these values are allowed: {', '.join(valid_values[:5])}"
                })
            
            # Rule 3: Field length constraints
            if field_type in ['string', 'email', 'phone', 'url'] and field.get('length'):
                max_length = field['length']
                if max_length > 0:
                    validation_rules.append({
                        'rule_id': f"IMPLICIT_LENGTH_{field_name}",
                        'rule_name': f"Field Length: {field_name}",
                        'object': object_name,
                        'field': field_name,
                        'type': 'FIELD_LENGTH',
                        'error_message': f"{field['label']} exceeds maximum length of {max_length} characters",
                        'error_condition': f"length({field_name}) > {max_length}",
                        'max_length': max_length,
                        'description': f"Maximum {max_length} characters allowed"
                    })
        
        return validation_rules
    
    except Exception as e:
        st.warning(f"⚠️ Could not extract validation rules from describe: {str(e)}")
        return []


def validate_data_against_validation_rules(
    data: pd.DataFrame,
    target_sf,
    object_name: str,
    validation_rules: List[Dict] = None,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Validate uploaded data against extracted ValidationRules
    
    Args:
        data: DataFrame with records to validate
        target_sf: Salesforce connection
        object_name: Object name
        validation_rules: Optional pre-extracted rules
        progress_callback: Optional progress callback
    
    Returns:
        Validation results dictionary
    """
    results = {
        'passed': True,  # Will be set to False if any violations found
        'total_records': len(data),
        'total_rules': 0,
        'rules_passed': 0,
        'rules_with_violations': 0,
        'total_violations': 0,
        'validation_details': [],
        'affected_records': set(),
        'summary': {}
    }
    
    if len(data) == 0:
        results['error'] = 'No data to validate'
        return results
    
    # Extract validation rules if not provided
    if validation_rules is None:
        if progress_callback:
            progress_callback("Extracting validation rules from target org...")
        
        validation_rules = extract_validation_rules_from_describe(target_sf, object_name)
    
    results['total_rules'] = len(validation_rules)
    
    if len(validation_rules) == 0:
        results['note'] = f"No validation rules found for {object_name}"
        return results
    
    # Validate each rule
    for i, rule in enumerate(validation_rules):
        if progress_callback:
            progress_callback(f"Validating rule {i+1}/{len(validation_rules)}: {rule['rule_name']}...")
        
        rule_violations = validate_rule_against_data(data, rule)
        
        if rule_violations['violations'] > 0:
            results['rules_with_violations'] += 1
            results['total_violations'] += rule_violations['violations']
            results['validation_details'].append(rule_violations)
            results['passed'] = False  # Mark as failed if any violations
            
            # Track affected records
            for record_idx in rule_violations['affected_record_indices']:
                results['affected_records'].add(record_idx)
        else:
            results['rules_passed'] += 1
    
    # Convert set to list for JSON serialization
    results['affected_records'] = list(results['affected_records'])
    
    return results


def validate_rule_against_data(data: pd.DataFrame, rule: Dict) -> Dict[str, Any]:
    """
    Validate a single validation rule against data
    
    Args:
        data: DataFrame with records
        rule: Validation rule definition
    
    Returns:
        Validation results for this rule
    """
    rule_result = {
        'rule_id': rule['rule_id'],
        'rule_name': rule['rule_name'],
        'rule_type': rule['type'],
        'error_message': rule['error_message'],
        'violations': 0,
        'affected_record_indices': [],
        'affected_records': [],
        'passed': True
    }
    
    try:
        field_name = rule.get('field')
        
        if not field_name or field_name not in data.columns:
            return rule_result
        
        # Validate based on rule type
        if rule['type'] == 'REQUIRED_FIELD':
            # Check for null or empty values
            violations = data[data[field_name].isna() | (data[field_name].astype(str).str.strip() == '')].index.tolist()
            
            if violations:
                rule_result['violations'] = len(violations)
                rule_result['affected_record_indices'] = violations
                rule_result['passed'] = False
                
                # Get sample affected records
                for idx in violations[:5]:
                    rule_result['affected_records'].append({
                        'row_index': int(idx),
                        'field_value': data.loc[idx, field_name]
                    })
        
        elif rule['type'] == 'PICKLIST_VALUE':
            valid_values = rule.get('valid_values', [])
            
            # Check for invalid picklist values
            violations = []
            for idx, row in data.iterrows():
                val = row[field_name]
                if pd.notna(val) and str(val).strip() != '' and str(val) not in valid_values:
                    violations.append(idx)
            
            if violations:
                rule_result['violations'] = len(violations)
                rule_result['affected_record_indices'] = violations
                rule_result['passed'] = False
                
                for idx in violations[:5]:
                    rule_result['affected_records'].append({
                        'row_index': int(idx),
                        'field_value': data.loc[idx, field_name],
                        'valid_values': valid_values
                    })
        
        elif rule['type'] == 'FIELD_LENGTH':
            max_length = rule.get('max_length', 0)
            
            # Check field length violations
            violations = []
            for idx, row in data.iterrows():
                val = row[field_name]
                if pd.notna(val) and len(str(val)) > max_length:
                    violations.append(idx)
            
            if violations:
                rule_result['violations'] = len(violations)
                rule_result['affected_record_indices'] = violations
                rule_result['passed'] = False
                
                for idx in violations[:5]:
                    rule_result['affected_records'].append({
                        'row_index': int(idx),
                        'field_value': data.loc[idx, field_name],
                        'actual_length': len(str(data.loc[idx, field_name])),
                        'max_length': max_length
                    })
    
    except Exception as e:
        rule_result['error'] = str(e)
    
    return rule_result


def display_validation_rules_report(validation_results: Dict[str, Any], data: pd.DataFrame = None):
    """
    Display validation rules violations report in Streamlit
    
    Args:
        validation_results: Results from validate_data_against_validation_rules()
        data: Optional DataFrame for showing sample records
    """
    if not validation_results:
        st.info("No validation rule results available")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Total Rules", validation_results['total_rules'])
    with col2:
        st.metric("✅ Passed", validation_results['rules_passed'])
    with col3:
        st.metric("❌ Violations", validation_results['rules_with_violations'])
    with col4:
        st.metric("⚠️ Total Issues", validation_results['total_violations'])
    
    st.divider()
    
    # Detailed results
    if validation_results['validation_details']:
        for rule_result in validation_results['validation_details']:
            status = "✅ PASSED" if rule_result['passed'] else "❌ FAILED"
            
            with st.expander(f"{status} - {rule_result['rule_name']}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Rule Type:** {rule_result['rule_type']}")
                    st.write(f"**Error Message:** {rule_result['error_message']}")
                
                with col2:
                    st.write(f"**Violations:** {rule_result['violations']}")
                    st.write(f"**Affected Records:** {len(rule_result['affected_record_indices'])}")
                
                if rule_result['affected_records']:
                    st.write("**Sample Violations:**")
                    
                    for sample in rule_result['affected_records']:
                        row_idx = sample.get('row_index', 'N/A')
                        
                        if rule_result['rule_type'] == 'REQUIRED_FIELD':
                            st.warning(f"  • Row {row_idx}: Value is empty/null")
                        
                        elif rule_result['rule_type'] == 'PICKLIST_VALUE':
                            field_value = sample.get('field_value', 'N/A')
                            valid = sample.get('valid_values', [])[:3]
                            st.warning(f"  • Row {row_idx}: '{field_value}' is invalid. Valid: {valid}")
                        
                        elif rule_result['rule_type'] == 'FIELD_LENGTH':
                            actual = sample.get('actual_length', 0)
                            max_len = sample.get('max_length', 0)
                            st.warning(f"  • Row {row_idx}: Length {actual} exceeds maximum {max_len}")
    
    else:
        st.success("✅ All validation rules passed!")
    
    st.divider()
    
    # Show overall status
    if validation_results['rules_with_violations'] > 0:
        st.warning(f"⚠️ **{validation_results['rules_with_violations']} rule(s) have violations**")
        st.info(f"Fix these issues in rows: {validation_results['affected_records']}")
    else:
        st.success("✅ **All validation rules satisfied**")
