"""
Organization Migration - Salesforce ValidationRule Extraction and Evaluation
Extracts actual ValidationRules from target org and evaluates data against them
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Any, Optional
import json
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def extract_salesforce_validation_rules(target_sf, object_name: str) -> List[Dict]:
    """
    Extract actual ValidationRules from target org using Metadata API (primary) with Tooling API fallback
    
    Args:
        target_sf: Salesforce connection to target org
        object_name: Salesforce object name (e.g., 'Account', 'Opportunity')
    
    Returns:
        List of ValidationRule dictionaries with formulas
    """
    try:
        validation_rules = []
        
        # ValidationRule is a metadata object, not queryable via SOQL
        # Try Metadata API first (more reliable), then Tooling API as fallback
        
        # ===== ATTEMPT 1: Try Metadata API (Primary Method) =====
        st.write(f"🔍 **Attempting to extract ValidationRules for {object_name} using Metadata API...**")
        metadata_result = _extract_validation_rules_metadata_api(target_sf, object_name)
        
        if metadata_result:
            st.success(f"✅ Found {len(metadata_result)} ValidationRule(s) via Metadata API")
            return metadata_result
        
        # ===== ATTEMPT 2: Fallback to Tooling API =====
        st.write(f"📌 **Metadata API unavailable, trying Tooling API as fallback...**")
        tooling_result = _extract_validation_rules_tooling_api(target_sf, object_name)
        
        if tooling_result:
            st.success(f"✅ Found {len(tooling_result)} ValidationRule(s) via Tooling API")
            return tooling_result
        
        # ===== ATTEMPT 3: Field-level validation fallback =====
        st.info(f"ℹ️ No ValidationRules found for {object_name}. Field-level validation will be used instead.")
        logger.info(f"No ValidationRules found for {object_name} via Metadata or Tooling API")
        return []
    
    except Exception as e:
        st.warning(f"⚠️ Error in ValidationRule extraction: {str(e)}")
        logger.error(f"Error in ValidationRule extraction: {str(e)}")
        return []


def _extract_validation_rules_metadata_api(target_sf, object_name: str) -> List[Dict]:
    """
    Extract ValidationRules using Metadata API
    
    Args:
        target_sf: Salesforce connection
        object_name: Object name to query
    
    Returns:
        List of ValidationRule dicts or empty list if failed
    """
    try:
        import xml.etree.ElementTree as ET
        
        instance_url = target_sf.base_url
        metadata_url = f"{instance_url}/services/data/v59.0/metadata/types/ValidationRule"
        
        # Get auth token
        auth_token = target_sf.session.headers.get('Authorization', '')
        if not auth_token and hasattr(target_sf.session, 'auth'):
            auth_token = f"Bearer {target_sf.session.auth}"
        
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Query to get ValidationRule members
        logger.info(f"Querying Metadata API for ValidationRules on {object_name}")
        response = target_sf.session.get(metadata_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            validation_rules = []
            
            # Filter for the target object
            members = result.get('members', [])
            
            for member in members:
                # Member names are like "ValidationRuleName"
                # We need to retrieve full metadata for each rule
                try:
                    rule_data = _retrieve_validation_rule_metadata(target_sf, member, object_name)
                    if rule_data:
                        validation_rules.append(rule_data)
                        st.caption(f"  • {rule_data['rule_name']}: {rule_data['error_message']}")
                except Exception as e:
                    logger.warning(f"Could not retrieve metadata for rule {member}: {str(e)}")
                    continue
            
            return validation_rules if validation_rules else []
        
        elif response.status_code == 403:
            logger.warning("Metadata API access forbidden - user may lack 'View Setup and Configuration' permission")
            return []
        
        else:
            logger.warning(f"Metadata API error ({response.status_code}): {response.text}")
            return []
    
    except Exception as e:
        logger.warning(f"Error accessing Metadata API: {str(e)}")
        return []


def _retrieve_validation_rule_metadata(target_sf, rule_name: str, object_name: str) -> Optional[Dict]:
    """
    Retrieve full metadata for a specific ValidationRule
    
    Args:
        target_sf: Salesforce connection
        rule_name: Name of the ValidationRule
        object_name: Object the rule belongs to
    
    Returns:
        Rule dictionary or None if failed
    """
    try:
        instance_url = target_sf.base_url
        # Metadata Retrieve endpoint
        retrieve_url = f"{instance_url}/services/data/v59.0/metadata/read/ValidationRule/{rule_name}"
        
        auth_token = target_sf.session.headers.get('Authorization', '')
        if not auth_token and hasattr(target_sf.session, 'auth'):
            auth_token = f"Bearer {target_sf.session.auth}"
        
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = target_sf.session.get(retrieve_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            rule_metadata = response.json()
            
            # Only process if it matches our target object
            if rule_metadata.get('entityName') == object_name or rule_metadata.get('entity') == object_name:
                rule = {
                    'rule_id': rule_metadata.get('id', ''),
                    'rule_name': rule_metadata.get('fullName', rule_name),
                    'object': object_name,
                    'error_message': rule_metadata.get('errorMessage', ''),
                    'error_condition_formula': rule_metadata.get('validationFormula', rule_metadata.get('errorConditionFormula', '')),
                    'description': rule_metadata.get('description', ''),
                    'active': rule_metadata.get('active', True),
                    'created_date': rule_metadata.get('createdDate', '')
                }
                return rule
        
        return None
    
    except Exception as e:
        logger.warning(f"Error retrieving ValidationRule {rule_name} metadata: {str(e)}")
        return None


def _extract_validation_rules_tooling_api(target_sf, object_name: str) -> List[Dict]:
    """
    Extract ValidationRules using Tooling API (fallback method)
    
    Args:
        target_sf: Salesforce connection to target org
        object_name: Salesforce object name
    
    Returns:
        List of ValidationRule dictionaries with formulas, or empty list if failed
    """
    try:
        validation_rules = []
        
        instance_url = target_sf.base_url
        tooling_url = f"{instance_url}/services/data/v59.0/tooling/query"
        
        # Build SOQL query
        query = f"SELECT Id, ValidationName, EntityDefinition.QualifiedApiName, ErrorConditionFormula, ErrorMessage, Description, Active, CreatedDate FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}' AND Active = true"
        
        logger.info(f"Querying ValidationRules via Tooling API for {object_name}")
        
        # Get auth token
        auth_token = target_sf.session.headers.get('Authorization', '')
        if not auth_token and hasattr(target_sf.session, 'auth'):
            auth_token = f"Bearer {target_sf.session.auth}"
        
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = target_sf.session.get(tooling_url, params={'q': query}, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('size', 0) > 0:
                for record in result.get('records', []):
                    rule = {
                        'rule_id': record.get('Id'),
                        'rule_name': record.get('ValidationName'),
                        'object': object_name,
                        'error_message': record.get('ErrorMessage', ''),
                        'error_condition_formula': record.get('ErrorConditionFormula', ''),
                        'description': record.get('Description', ''),
                        'active': record.get('Active', True),
                        'created_date': record.get('CreatedDate')
                    }
                    validation_rules.append(rule)
                    logger.info(f"Extracted ValidationRule via Tooling API: {rule['rule_name']}")
                    st.caption(f"  • {rule['rule_name']}: {rule['error_message']}")
            
            return validation_rules
        
        elif response.status_code == 401:
            st.warning("⚠️ Session expired. ValidationRules access via Tooling API requires 'View Setup and Configuration' permission.")
            logger.warning("Session expired when accessing Tooling API - user may lack 'View Setup and Configuration' permission")
            return []
        
        else:
            try:
                error_content = response.json()
            except:
                error_content = response.text or response.reason
            
            logger.warning(f"Tooling API error ({response.status_code}): {error_content}")
            return []
    
    except Exception as e:
        logger.warning(f"Error accessing Tooling API: {str(e)}")
        return []


def parse_salesforce_formula(formula: str) -> Dict[str, Any]:
    """
    Parse Salesforce formula string into evaluable expression tree
    
    Handles:
    - Functions: AND(), OR(), IF(), NOT()
    - Operators: =, <>, <, >, <=, >=
    - Field references: FieldName, RelatedObject.Field
    - Literals: 'string', 123, true, false, null
    
    Args:
        formula: Salesforce formula string
    
    Returns:
        Parsed formula structure
    """
    try:
        formula = formula.strip()
        
        # Normalize whitespace
        formula = re.sub(r'\s+', ' ', formula)
        
        # Parse formula
        parsed = {
            'original': formula,
            'type': 'unknown',
            'function': None,
            'operator': None,
            'operands': [],
            'value': None
        }
        
        # Check for AND function
        if formula.upper().startswith('AND('):
            parsed['type'] = 'function'
            parsed['function'] = 'AND'
            operands = extract_function_operands(formula, 'AND')
            parsed['operands'] = [parse_salesforce_formula(op) for op in operands]
            return parsed
        
        # Check for OR function
        elif formula.upper().startswith('OR('):
            parsed['type'] = 'function'
            parsed['function'] = 'OR'
            operands = extract_function_operands(formula, 'OR')
            parsed['operands'] = [parse_salesforce_formula(op) for op in operands]
            return parsed
        
        # Check for IF function
        elif formula.upper().startswith('IF('):
            parsed['type'] = 'function'
            parsed['function'] = 'IF'
            operands = extract_function_operands(formula, 'IF')
            if len(operands) >= 3:
                parsed['operands'] = [parse_salesforce_formula(operands[0])]  # Condition
                parsed['value'] = (operands[1], operands[2])  # (true_value, false_value)
            return parsed
        
        # Check for NOT function
        elif formula.upper().startswith('NOT('):
            parsed['type'] = 'function'
            parsed['function'] = 'NOT'
            operands = extract_function_operands(formula, 'NOT')
            parsed['operands'] = [parse_salesforce_formula(op) for op in operands]
            return parsed
        
        # Check for comparison operators
        comparison_operators = ['<>', '<=', '>=', '=', '<', '>']
        for op in comparison_operators:
            if f' {op} ' in formula:
                parts = formula.split(f' {op} ', 1)
                if len(parts) == 2:
                    parsed['type'] = 'comparison'
                    parsed['operator'] = op
                    parsed['operands'] = [
                        parse_operand(parts[0].strip()),
                        parse_operand(parts[1].strip())
                    ]
                    return parsed
        
        # If nothing matched, treat as field reference or literal
        parsed['type'] = 'value'
        parsed['value'] = parse_operand(formula)
        return parsed
    
    except Exception as e:
        logger.error(f"Error parsing formula: {str(e)}")
        return {
            'original': formula,
            'type': 'error',
            'error': str(e)
        }


def extract_function_operands(formula: str, function_name: str) -> List[str]:
    """
    Extract operands from function call
    Handles nested parentheses correctly
    
    Args:
        formula: Formula string like "AND(field1 = 'value', field2 > 10)"
        function_name: Function name (AND, OR, IF, NOT)
    
    Returns:
        List of operand strings
    """
    try:
        # Find opening parenthesis after function name
        pattern = f"{function_name}\\("
        match = re.search(pattern, formula, re.IGNORECASE)
        
        if not match:
            return []
        
        start_idx = match.end()
        
        # Find matching closing parenthesis
        paren_count = 1
        end_idx = start_idx
        
        for i in range(start_idx, len(formula)):
            if formula[i] == '(':
                paren_count += 1
            elif formula[i] == ')':
                paren_count -= 1
                if paren_count == 0:
                    end_idx = i
                    break
        
        # Extract content between parentheses
        content = formula[start_idx:end_idx]
        
        # Split by comma, but respect nested parentheses
        operands = []
        current = ""
        paren_level = 0
        
        for char in content:
            if char == '(':
                paren_level += 1
                current += char
            elif char == ')':
                paren_level -= 1
                current += char
            elif char == ',' and paren_level == 0:
                operands.append(current.strip())
                current = ""
            else:
                current += char
        
        if current:
            operands.append(current.strip())
        
        return operands
    
    except Exception as e:
        logger.error(f"Error extracting function operands: {str(e)}")
        return []


def parse_operand(operand: str) -> Any:
    """
    Parse operand value (field reference, literal, etc.)
    
    Args:
        operand: Operand string like 'Status', "'Active'", "123", etc.
    
    Returns:
        Parsed operand value
    """
    operand = operand.strip()
    
    # String literal (enclosed in single quotes)
    if operand.startswith("'") and operand.endswith("'"):
        return operand[1:-1]  # Remove quotes
    
    # Number
    if re.match(r'^-?\d+(\.\d+)?$', operand):
        if '.' in operand:
            return float(operand)
        else:
            return int(operand)
    
    # Boolean
    if operand.lower() in ['true', 'false']:
        return operand.lower() == 'true'
    
    # Null
    if operand.lower() == 'null':
        return None
    
    # Field reference (assume it's a field name)
    return {'field_reference': operand}


def evaluate_formula(parsed_formula: Dict, row_data: Dict) -> bool:
    """
    Evaluate parsed formula against row data
    
    Args:
        parsed_formula: Parsed formula structure from parse_salesforce_formula()
        row_data: Dictionary of field values for a record
    
    Returns:
        True if formula evaluates to True (violation), False otherwise
    """
    try:
        if parsed_formula.get('type') == 'error':
            logger.warning(f"Cannot evaluate formula with parsing error: {parsed_formula.get('error')}")
            return False
        
        if parsed_formula['type'] == 'function':
            function = parsed_formula['function']
            
            if function == 'AND':
                # ALL operands must be True
                for operand in parsed_formula['operands']:
                    if not evaluate_formula(operand, row_data):
                        return False
                return True
            
            elif function == 'OR':
                # ANY operand must be True
                for operand in parsed_formula['operands']:
                    if evaluate_formula(operand, row_data):
                        return True
                return False
            
            elif function == 'NOT':
                # Negate the operand
                return not evaluate_formula(parsed_formula['operands'][0], row_data)
            
            elif function == 'IF':
                # Evaluate condition, return true_value or false_value
                condition_result = evaluate_formula(parsed_formula['operands'][0], row_data)
                true_val, false_val = parsed_formula['value']
                result = true_val if condition_result else false_val
                return evaluate_formula(parse_salesforce_formula(result), row_data)
        
        elif parsed_formula['type'] == 'comparison':
            operator = parsed_formula['operator']
            operands = parsed_formula['operands']
            
            left_val = get_operand_value(operands[0], row_data)
            right_val = get_operand_value(operands[1], row_data)
            
            if operator == '=':
                return left_val == right_val
            elif operator == '<>':
                return left_val != right_val
            elif operator == '<':
                return left_val < right_val
            elif operator == '>':
                return left_val > right_val
            elif operator == '<=':
                return left_val <= right_val
            elif operator == '>=':
                return left_val >= right_val
        
        elif parsed_formula['type'] == 'value':
            return get_operand_value(parsed_formula['value'], row_data)
        
        return False
    
    except Exception as e:
        logger.error(f"Error evaluating formula: {str(e)}")
        return False


def get_operand_value(operand: Any, row_data: Dict) -> Any:
    """
    Get the actual value of an operand from row data
    
    Args:
        operand: Operand (could be literal, field reference, etc.)
        row_data: Row data dictionary
    
    Returns:
        Actual value
    """
    if isinstance(operand, dict) and 'field_reference' in operand:
        # Field reference - get value from row
        field_name = operand['field_reference']
        value = row_data.get(field_name)
        
        # Handle null/NaN
        if pd.isna(value):
            return None
        
        return value
    
    else:
        # Literal value
        return operand


def validate_data_against_salesforce_rules(
    data: pd.DataFrame,
    target_sf,
    object_name: str,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Validate data against actual Salesforce ValidationRules
    
    Args:
        data: DataFrame with records to validate
        target_sf: Target Salesforce connection
        object_name: Object name
        progress_callback: Optional progress callback
    
    Returns:
        Validation results
    """
    results = {
        'passed': True,
        'total_records': len(data),
        'total_rules': 0,
        'rules_passed': 0,
        'rules_with_violations': 0,
        'total_violations': 0,
        'validation_details': [],
        'affected_records': set(),
        'extraction_method': 'salesforce_validation_rules'
    }
    
    if len(data) == 0:
        results['note'] = 'No data to validate'
        return results
    
    # Extract ValidationRules with progress display
    st.write("🔍 **Extracting ValidationRules from target org...**")
    validation_rules = extract_salesforce_validation_rules(target_sf, object_name)
    results['total_rules'] = len(validation_rules)
    
    if len(validation_rules) == 0:
        st.info(f"ℹ️ No ValidationRules found for {object_name}")
        results['note'] = f"No ValidationRules found for {object_name}"
        return results
    
    st.write(f"✅ **Validating data against {len(validation_rules)} rule(s)...**")
    
    # Validate each rule
    for i, rule in enumerate(validation_rules):
        if progress_callback:
            progress_callback(f"Validating rule {i+1}/{len(validation_rules)}: {rule['rule_name']}...")
        
        formula = rule.get('error_condition_formula', '')
        
        if not formula:
            st.warning(f"⚠️ Rule '{rule['rule_name']}' has no formula, skipping")
            continue
        
        st.write(f"  Rule {i+1}: {rule['rule_name']}")
        
        # Parse formula
        try:
            parsed_formula = parse_salesforce_formula(formula)
            st.caption(f"    Formula: `{formula[:100]}...`" if len(formula) > 100 else f"    Formula: `{formula}`")
        except Exception as e:
            st.warning(f"    ⚠️ Could not parse formula: {str(e)}")
            logger.warning(f"Could not parse formula for {rule['rule_name']}: {str(e)}")
            continue
        
        # Evaluate against each row
        affected_rows = []
        
        for idx, row in data.iterrows():
            try:
                # Convert row to dictionary
                row_dict = row.to_dict()
                
                # Evaluate formula
                is_violation = evaluate_formula(parsed_formula, row_dict)
                
                if is_violation:
                    affected_rows.append(int(idx))
            
            except Exception as e:
                logger.warning(f"Error evaluating formula for row {idx}: {str(e)}")
        
        # Record results
        if affected_rows:
            results['rules_with_violations'] += 1
            results['total_violations'] += len(affected_rows)
            results['passed'] = False
            
            st.warning(f"    ❌ {len(affected_rows)} records violate this rule")
            
            rule_result = {
                'rule_id': rule['rule_id'],
                'rule_name': rule['rule_name'],
                'rule_type': 'SALESFORCE_VALIDATION_RULE',
                'error_message': rule['error_message'],
                'error_condition_formula': formula,
                'violations': len(affected_rows),
                'affected_record_indices': affected_rows,
                'passed': False
            }
            results['validation_details'].append(rule_result)
            
            # Track affected records
            for row_idx in affected_rows:
                results['affected_records'].add(row_idx)
        
        else:
            results['rules_passed'] += 1
            st.success(f"    ✅ All records pass this rule")
    
    results['affected_records'] = list(results['affected_records'])
    
    return results


def display_salesforce_validation_rules_report(validation_results: Dict, data: pd.DataFrame = None):
    """
    Display Salesforce ValidationRules validation report
    
    Args:
        validation_results: Results from validate_data_against_salesforce_rules()
        data: Optional DataFrame for context
    """
    if not validation_results:
        st.info("No validation results available")
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
    
    # Extraction method info
    if validation_results.get('total_rules', 0) == 0:
        st.warning("⚠️ **No ValidationRules found for this object**")
        st.info("""
        **Possible reasons:**
        1. The target org has no ValidationRules defined for this object
        2. ValidationRule SOQL queries are not available in this org
        3. The ValidationRules are disabled
        
        **Note:** To validate against custom ValidationRules, you may need to:
        - Ensure the ValidationRules are Active in the target org
        - Use the "Custom Business Rules" section above to manually define validation logic
        - Or contact your Salesforce admin to check ValidationRule setup
        """)
        return
    
    if validation_results.get('extraction_method') == 'salesforce_validation_rules':
        st.success("✅ **Data validated against actual Salesforce ValidationRules from target org**")
    
    # Detailed results
    if validation_results['validation_details']:
        for rule_result in validation_results['validation_details']:
            status = "❌ FAILED" if not rule_result['passed'] else "✅ PASSED"
            
            with st.expander(f"{status} - {rule_result['rule_name']}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Error Message:** {rule_result['error_message']}")
                    st.write(f"**Rule Type:** {rule_result['rule_type']}")
                
                with col2:
                    st.write(f"**Violations:** {rule_result['violations']}")
                    st.write(f"**Affected Records:** {len(rule_result['affected_record_indices'])}")
                
                # Show formula
                with st.expander("View Formula", expanded=False):
                    st.code(rule_result['error_condition_formula'], language='formula')
                
                # Show affected rows
                if rule_result['affected_record_indices']:
                    st.write("**Affected Rows:**")
                    affected_idx = rule_result['affected_record_indices'][:10]
                    st.write(f"Rows: {affected_idx}")
                    
                    if len(rule_result['affected_record_indices']) > 10:
                        st.caption(f"... and {len(rule_result['affected_record_indices']) - 10} more rows")
    
    else:
        st.success("✅ All validation rules satisfied!")
    
    st.divider()
    
    # Show overall status
    if validation_results['rules_with_violations'] > 0:
        st.warning(f"⚠️ **{validation_results['rules_with_violations']} ValidationRule(s) have violations**")
        st.error(f"Data will FAIL during migration to Salesforce. Fix {validation_results['total_violations']} record(s).")
    else:
        st.success("✅ **All ValidationRules satisfied - data will migrate successfully**")
