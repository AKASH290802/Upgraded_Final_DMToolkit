# Auto-generated validation bundle
import pandas as pd
import numpy as np
from typing import List, Dict


def _is_blank(value):
    """Salesforce ISBLANK function"""
    if hasattr(value, 'isna'):
        return value.isna() | (value == '')
    return pd.isna(value) or value == ''

def _is_null(value):
    """Salesforce ISNULL function"""
    if hasattr(value, 'isna'):
        return value.isna()
    return pd.isna(value)

def _to_number(value):
    """Salesforce VALUE function"""
    if hasattr(value, 'astype'):
        return pd.to_numeric(value, errors='coerce')
    try:
        return float(value)
    except:
        return 0

def _trim(text):
    """Salesforce TRIM function"""
    if hasattr(text, 'str'):
        return text.str.strip()
    return str(text).strip() if text else ''

def _left(text, num_chars):
    """Salesforce LEFT function"""
    if hasattr(text, 'str'):
        return text.str[:num_chars]
    return str(text)[:num_chars] if text else ''

def _right(text, num_chars):
    """Salesforce RIGHT function"""
    if hasattr(text, 'str'):
        return text.str[-num_chars:]
    return str(text)[-num_chars:] if text else ''

def _mid(text, start_pos, num_chars):
    """Salesforce MID function"""
    if hasattr(text, 'str'):
        return text.str[start_pos-1:start_pos-1+num_chars]
    return str(text)[start_pos-1:start_pos-1+num_chars] if text else ''

def _find(search_text, text):
    """Salesforce FIND function"""
    if hasattr(text, 'str'):
        return text.str.find(search_text) + 1  # Salesforce is 1-indexed
    return str(text).find(str(search_text)) + 1 if text else 0

def _contains(text, search_text):
    """Salesforce CONTAINS function"""
    if hasattr(text, 'str'):
        return text.str.contains(search_text, na=False)
    return str(search_text) in str(text) if text else False

def _today():
    """Salesforce TODAY function"""
    from datetime import date
    return date.today()

def _now():
    """Salesforce NOW function"""
    from datetime import datetime
    return datetime.now()

def _year(date_value):
    """Salesforce YEAR function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.year
    return pd.to_datetime(date_value).year if date_value else None

def _month(date_value):
    """Salesforce MONTH function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.month
    return pd.to_datetime(date_value).month if date_value else None

def _day(date_value):
    """Salesforce DAY function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.day
    return pd.to_datetime(date_value).day if date_value else None

def _and(*conditions):
    """Salesforce AND function"""
    result = conditions[0]
    for condition in conditions[1:]:
        result = result & condition
    return result

def _or(*conditions):
    """Salesforce OR function"""
    result = conditions[0]
    for condition in conditions[1:]:
        result = result | condition
    return result

def _not(condition):
    """Salesforce NOT function"""
    return ~condition

def _if(condition, true_value, false_value):
    """Salesforce IF function"""
    if hasattr(condition, '__len__') and len(condition) > 1:
        return pd.where(condition, true_value, false_value)
    return true_value if condition else false_value

def _begins_with(text, prefix):
    """Salesforce BEGINS function"""
    if hasattr(text, 'str'):
        return text.str.startswith(prefix)
    return str(text).startswith(str(prefix)) if text else False

def _ends_with(text, suffix):
    """Salesforce ENDS function"""
    if hasattr(text, 'str'):
        return text.str.endswith(suffix)
    return str(text).endswith(str(suffix)) if text else False

def _ceiling(number):
    """Salesforce CEILING function"""
    import math
    if hasattr(number, 'apply'):
        return number.apply(math.ceil)
    return math.ceil(number) if number else 0

def _floor(number):
    """Salesforce FLOOR function"""
    import math
    if hasattr(number, 'apply'):
        return number.apply(math.floor)
    return math.floor(number) if number else 0


def validate_Name_Not_Empty(df):
    """
    Validation Rule: Name_Not_Empty
    Salesforce Object: Account
    Primary Field: Name
    
    
    Original Apex Formula:
    ISBLANK(Name)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    # Primary Field: Name
    
    # Import required modules
    import pandas as pd
    import numpy as np
    from datetime import datetime, date
    import math
    
    try:
        # Ensure all required columns exist
        required_columns = ['Name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Warning: Missing columns for validation rule 'Name_Not_Empty': {missing_columns}")
            return pd.Series([False] * len(df))  # Mark all as invalid if columns missing
        
        # Fill NaN values to avoid errors
        df_clean = df.fillna('')
        
        # Apply validation logic
        validation_result = _is_blank(df['Name'])
        
        # Ensure result is a boolean Series
        if not isinstance(validation_result, pd.Series):
            validation_result = pd.Series([bool(validation_result)] * len(df))
        
        # Salesforce validation rules define ERROR conditions (when validation should FAIL)
        # If the formula evaluates to True = Error condition = Record is INVALID
        # If the formula evaluates to False = No error = Record is VALID
        # So we need to invert: True becomes False (invalid), False becomes True (valid)
        
        # Debug: Print sample of validation logic for troubleshooting
        if len(df) > 0:
            sample_value = validation_result.iloc[0] if hasattr(validation_result, 'iloc') else validation_result
            print(f"DEBUG - Rule 'Name_Not_Empty': Formula result for first record = {sample_value} (True=Error/Invalid, False=NoError/Valid)")
            
            # Additional debugging for ISBLANK scenarios
            if '_is_blank' in str(validation_result):
                sample_field_value = df_clean.iloc[0].get('Name', 'COLUMN_NOT_FOUND') if len(df_clean) > 0 else 'NO_DATA'
                print(f"DEBUG - Rule 'Name_Not_Empty': Field 'Name' value for first record = '{sample_field_value}'")
                print(f"DEBUG - Rule 'Name_Not_Empty': Available columns = {list(df.columns)}")
                if 'Name' not in df.columns:
                    print(f"WARNING - Rule 'Name_Not_Empty': Column 'Name' not found in data! This will cause validation to fail.")
        
        return ~validation_result
        
    except KeyError as e:
        print(f"Warning: Column {e} not found in DataFrame for validation rule 'Name_Not_Empty'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
    except Exception as e:
        print(f"Warning: Error in validation rule 'Name_Not_Empty': {e}")
        return pd.Series([False] * len(df))  # Mark all as invalid on error

def validate_record(row):
    '''Validate a single record (row) and return result dict'''
    import pandas as pd
    df = pd.DataFrame([row])
    rule_results = {}
    errors = []
    is_valid = True
    try:
        print(f"DEBUG validate_record: Calling validate_Name_Not_Empty on row data")
        func_result = validate_Name_Not_Empty(df)
        if hasattr(func_result, 'iloc'):
            rule_results['validate_Name_Not_Empty'] = bool(func_result.iloc[0])
        else:
            rule_results['validate_Name_Not_Empty'] = bool(func_result)
        print(f"DEBUG validate_record: validate_Name_Not_Empty returned {rule_results['validate_Name_Not_Empty']}")
        if not rule_results['validate_Name_Not_Empty']:
            errors.append('validate_Name_Not_Empty')
            print(f"DEBUG validate_record: Added validate_Name_Not_Empty to errors list")
    except Exception as e:
        print(f"ERROR validate_record: validate_Name_Not_Empty failed with error: {str(e)}")
        rule_results['validate_Name_Not_Empty'] = False
        errors.append(f'validate_Name_Not_Empty (error: {str(e)})')
    if errors:
        is_valid = False
        print(f"DEBUG validate_record: Record INVALID due to errors: {errors}")
    else:
        print(f"DEBUG validate_record: Record VALID - all rules passed")
    print(f"DEBUG validate_record: Final result - is_valid: {is_valid}, errors: {errors}")
    return {'is_valid': is_valid, 'errors': errors, 'rule_results': rule_results}

def validate_dataframe(df):
    '''Validate all records in a DataFrame'''
    valid_idx = []
    invalid_idx = []
    validation_results = []
    for idx, row in df.iterrows():
        result = validate_record(row)
        result['index'] = idx
        validation_results.append(result)
        if result['is_valid']:
            valid_idx.append(idx)
        else:
            invalid_idx.append(idx)
    valid_df = df.loc[valid_idx].copy()
    invalid_df = df.loc[invalid_idx].copy()
    return valid_df, invalid_df, validation_results
