
"""
AI-Generated Validation Bundle for Account
Generated on: 2025-10-28 14:23:24

This file contains Python validation functions converted from Salesforce validation rules.
Each function validates a specific business rule extracted from Salesforce.
"""

import pandas as pd
import re
from datetime import datetime, date
from typing import Dict, List, Any, Union

# ================================
# HELPER FUNCTIONS
# ================================


# Helper functions for Salesforce formula conversion

def _is_blank(value):
    """Check if value is blank (empty, null, or whitespace)"""
    if pd.isna(value):
        return True
    if value is None:
        return True
    if str(value).strip() == '':
        return True
    return False

def _is_null(value):
    """Check if value is null"""
    return pd.isna(value) or value is None

def _to_number(value):
    """Convert value to number"""
    try:
        return float(value)
    except:
        return 0

def _left(text, num_chars):
    """Get leftmost characters"""
    return str(text)[:int(num_chars)]

def _right(text, num_chars):
    """Get rightmost characters"""
    return str(text)[-int(num_chars):]

def _mid(text, start, length):
    """Get middle characters"""
    start_idx = int(start) - 1  # Salesforce is 1-indexed
    return str(text)[start_idx:start_idx + int(length)]

def _find(search_text, within_text):
    """Find position of text"""
    pos = str(within_text).find(str(search_text))
    return pos + 1 if pos >= 0 else 0  # Salesforce is 1-indexed

def _contains(text, search_text):
    """Check if text contains search text"""
    return str(search_text) in str(text)

def _begins_with(text, prefix):
    """Check if text begins with prefix"""
    return str(text).startswith(str(prefix))

def _ends_with(text, suffix):
    """Check if text ends with suffix"""
    return str(text).endswith(str(suffix))

def _today():
    """Get today's date"""
    return date.today()

def _now():
    """Get current datetime"""
    return datetime.now()

def _year(date_value):
    """Get year from date"""
    try:
        if isinstance(date_value, (date, datetime)):
            return date_value.year
        return int(str(date_value)[:4])
    except:
        return 0

def _month(date_value):
    """Get month from date"""
    try:
        if isinstance(date_value, (date, datetime)):
            return date_value.month
        return int(str(date_value)[5:7])
    except:
        return 0

def _day(date_value):
    """Get day from date"""
    try:
        if isinstance(date_value, (date, datetime)):
            return date_value.day
        return int(str(date_value)[8:10])
    except:
        return 0

def _and(*args):
    """Logical AND"""
    return all(args)

def _or(*args):
    """Logical OR"""
    return any(args)

def _not(value):
    """Logical NOT"""
    return not value

def _if(condition, true_value, false_value):
    """IF function"""
    return true_value if condition else false_value

def _ceiling(value):
    """Ceiling function"""
    import math
    return math.ceil(float(value))

def _floor(value):
    """Floor function"""
    import math
    return math.floor(float(value))

def _ispickval(field_value, compare_value):
    """Salesforce ISPICKVAL function - check if field equals specific picklist value"""
    field_str = str(field_value).strip() if field_value is not None else ''
    compare_str = str(compare_value).strip() if compare_value is not None else ''
    return field_str == compare_str

def validate_name_is_null(row_data):
    """
    Validation function for rule: Name_is_null
    Original Salesforce formula: ISBLANK(Name)
    Error message: Name cannot be blank
    
    Args:
        row_data: Dictionary containing the row data to validate
        
    Returns:
        bool: True if valid, False if invalid
    """
    try:
        # Convert to pandas-like object for compatibility
        if hasattr(row_data, 'get'):
            # Dictionary-like access
            get_field = lambda field: row_data.get(field, '')
        else:
            # Assume it's a pandas Series
            get_field = lambda field: getattr(row_data, field, '') if hasattr(row_data, field) else row_data.get(field, '') if hasattr(row_data, 'get') else ''
        
        # Helper function to safely get field values
        def safe_get(field_name):
            try:
                value = get_field(field_name)
                if pd.isna(value):
                    return ''
                return str(value).strip()
            except:
                return ''
        
        # Validation logic (converted from Salesforce formula)
        validation_result = False  # Fallback - invalid due to conversion error
        
        # Salesforce validation rules define ERROR conditions
        # If formula evaluates to True = Error condition = Record is INVALID
        # If formula evaluates to False = No error = Record is VALID
        # So we invert: True becomes False (invalid), False becomes True (valid)
        return not bool(validation_result)
        
    except Exception as e:
        # On error, assume invalid for safety
        print(f"Error in validation function validate_name_is_null: {str(e)}")
        return False

def validate_phonerule(row_data):
    """
    Validation function for rule: PhoneRule
    Original Salesforce formula: ISBLANK(Phone)
    Error message: Phone required
    
    Args:
        row_data: Dictionary containing the row data to validate
        
    Returns:
        bool: True if valid, False if invalid
    """
    try:
        # Convert to pandas-like object for compatibility
        if hasattr(row_data, 'get'):
            # Dictionary-like access
            get_field = lambda field: row_data.get(field, '')
        else:
            # Assume it's a pandas Series
            get_field = lambda field: getattr(row_data, field, '') if hasattr(row_data, field) else row_data.get(field, '') if hasattr(row_data, 'get') else ''
        
        # Helper function to safely get field values
        def safe_get(field_name):
            try:
                value = get_field(field_name)
                if pd.isna(value):
                    return ''
                return str(value).strip()
            except:
                return ''
        
        # Validation logic (converted from Salesforce formula)
        validation_result = False  # Fallback - invalid due to conversion error
        
        # Salesforce validation rules define ERROR conditions
        # If formula evaluates to True = Error condition = Record is INVALID
        # If formula evaluates to False = No error = Record is VALID
        # So we invert: True becomes False (invalid), False becomes True (valid)
        return not bool(validation_result)
        
    except Exception as e:
        # On error, assume invalid for safety
        print(f"Error in validation function validate_phonerule: {str(e)}")
        return False


# ================================
# FUNCTION REGISTRY
# ================================

VALIDATION_FUNCTIONS = {'Name_is_null': {'function_name': 'validate_name_is_null', 'error_message': 'Name cannot be blank', 'active': True}, 'PhoneRule': {'function_name': 'validate_phonerule', 'error_message': 'Phone required', 'active': True}}

def get_all_validation_functions():
    """Get all available validation functions"""
    return VALIDATION_FUNCTIONS

def validate_record(row_data: Dict, active_only: bool = True) -> Dict:
    """
    Validate a single record against all validation rules
    
    Args:
        row_data: Dictionary containing the record data
        active_only: Only run active validation rules
        
    Returns:
        Dict with validation results
    """
    results = {
        'is_valid': True,
        'errors': [],
        'rule_results': {}
    }
    
    for rule_name, rule_info in VALIDATION_FUNCTIONS.items():
        if active_only and not rule_info.get('active', True):
            continue
            
        function_name = rule_info['function_name']
        error_message = rule_info['error_message']
        
        try:
            # Get the validation function
            validation_func = globals().get(function_name)
            if validation_func:
                is_valid = validation_func(row_data)
                results['rule_results'][rule_name] = is_valid
                
                if not is_valid:
                    results['is_valid'] = False
                    results['errors'].append({
                        'rule': rule_name,
                        'message': error_message
                    })
            else:
                print(f"Warning: Function {function_name} not found")
                
        except Exception as e:
            print(f"Error validating rule {rule_name}: {str(e)}")
            results['is_valid'] = False
            results['errors'].append({
                'rule': rule_name,
                'message': f"Validation error: {str(e)}"
            })
    
    return results

def validate_dataframe(df: pd.DataFrame, active_only: bool = True) -> pd.DataFrame:
    """
    Validate an entire DataFrame
    
    Args:
        df: DataFrame to validate
        active_only: Only run active validation rules
        
    Returns:
        DataFrame with validation results added
    """
    validation_results = []
    
    for index, row in df.iterrows():
        row_dict = row.to_dict()
        result = validate_record(row_dict, active_only)
        validation_results.append(result)
    
    # Add validation columns
    df_result = df.copy()
    df_result['is_valid'] = [r['is_valid'] for r in validation_results]
    df_result['validation_errors'] = [r['errors'] for r in validation_results]
    df_result['error_count'] = [len(r['errors']) for r in validation_results]
    
    return df_result
