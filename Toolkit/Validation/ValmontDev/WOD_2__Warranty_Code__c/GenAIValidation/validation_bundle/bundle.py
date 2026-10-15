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

def _mod(dividend, divisor):
    """Salesforce MOD function"""
    if hasattr(dividend, 'apply'):
        return dividend.apply(lambda x: x % divisor if divisor else 0)
    return int(dividend) % int(divisor) if dividend and divisor else 0

def _regex(text, pattern):
    """Salesforce REGEX function - checks if text matches pattern"""
    import re as regex_module
    if hasattr(text, 'str'):
        return text.str.contains(pattern, regex=True, na=False)
    return bool(regex_module.search(pattern, str(text))) if text else False

def _substitute(text, search_text, replace_text):
    """Salesforce SUBSTITUTE function - replaces text"""
    if hasattr(text, 'str'):
        return text.str.replace(search_text, replace_text)
    return str(text).replace(search_text, replace_text) if text else ''

def _concatenate(*args):
    """Salesforce CONCATENATE function - joins strings"""
    return ''.join(str(arg) for arg in args if arg is not None)

def _datevalue(date_string):
    """Salesforce DATEVALUE function - converts string to date"""
    try:
        return pd.to_datetime(date_string)
    except:
        return None

def _includes(field_value, search_value):
    """Salesforce INCLUDES function for multi-select picklists"""
    if hasattr(field_value, 'str'):
        return field_value.str.contains(search_value, na=False)
    return search_value in str(field_value) if field_value else False

def _excludes(field_value, search_value):
    """Salesforce EXCLUDES function for multi-select picklists"""
    if hasattr(field_value, 'str'):
        return ~field_value.str.contains(search_value, na=True)
    return search_value not in str(field_value) if field_value else True

def _ispickval(field_value, compare_value):
    """Salesforce ISPICKVAL function - check if field equals specific picklist value"""
    if hasattr(field_value, 'str'):
        # DataFrame Series - element-wise comparison
        return field_value.astype(str).str.strip() == str(compare_value).strip()
    # Scalar comparison
    field_str = str(field_value).strip() if field_value is not None and not pd.isna(field_value) else ''
    compare_str = str(compare_value).strip() if compare_value is not None else ''
    return field_str == compare_str

def _case(expression, *args):
    """Salesforce CASE function - CASE(expr, val1, result1, val2, result2, ..., else_result)"""
    if hasattr(expression, 'map'):
        # DataFrame Series - build mapping
        mapping = {}
        i = 0
        while i < len(args) - 1:
            mapping[args[i]] = args[i + 1]
            i += 2
        default = args[-1] if len(args) % 2 == 1 else None
        return expression.map(mapping).fillna(default)
    # Scalar
    i = 0
    while i < len(args) - 1:
        if expression == args[i]:
            return args[i + 1]
        i += 2
    return args[-1] if len(args) % 2 == 1 else None

def _trim(text):
    """Salesforce TRIM function"""
    if hasattr(text, 'str'):
        return text.str.strip()
    return str(text).strip() if text is not None and not pd.isna(text) else ''


def validate_Fault_Location_Level(row_data):
    """
    Validation Rule: Fault_Location_Level
    Salesforce Object: WOD_2__Warranty_Code__c
    Primary Field: WOD_2__Fault_Location_Level__c
    Additional Fields: WOD_2__Parent_Warranty_Code__r
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),
    IF(ISPICKVAL( WOD_2__Fault_Location_Level__c , 'Level 4'),
   ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 4') ,
        IF(ISPICKVAL( WOD_2__Fault_Location_Level__c , 'Level 3'),
              OR(
                   ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 3'),
                   ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 4')
                ),
             IF( ISPICKVAL( WOD_2__Fault_Location_Level__c , 'Level 2'),
                   OR(
                       ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 2'),
                       ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 3'),
                       ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 4')
                     ),
			       IF( ISPICKVAL( WOD_2__Fault_Location_Level__c , 'Level 1'),
                         OR(
                            ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 1'),
                            ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 2'),
                            ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 3'),
                            ISPICKVAL( WOD_2__Parent_Warranty_Code__r.WOD_2__Fault_Location_Level__c , 'Level 4')
                           ),
			            false
                    )
            )
    )
)
    )
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['WOD_2__Fault_Location_Level__c', 'WOD_2__Parent_Warranty_Code__r']
    if hasattr(row_data, 'keys'):
        _available = set(row_data.keys())
    elif hasattr(row_data, 'index'):
        _available = set(row_data.index)
    else:
        _available = set()
    if _required_fields and not _available.intersection(_required_fields):
        return True  # Skip: none of the rule fields are in the data
    
    # Helper to safely retrieve field values from row data
    def safe_get(field_name):
        try:
            if hasattr(row_data, 'get'):
                value = row_data.get(field_name, '')
            elif hasattr(row_data, '__getitem__'):
                try:
                    value = row_data[field_name]
                except (KeyError, IndexError):
                    value = ''
            else:
                value = ''
            if pd.isna(value):
                return ''
            return value
        except:
            return ''
    
    try:
        # Evaluate the error condition (converted from Salesforce formula)
        # Salesforce: formula True = Error condition = Record is INVALID
        # Salesforce: formula False = No error = Record is VALID
        error_condition = False  # Context-dependent rule — skipped in offline validation
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'Fault_Location_Level\': {e}")
        return False  # Mark as invalid on error

def validate_Standard_Labor_Time(row_data):
    """
    Validation Rule: Standard_Labor_Time
    Salesforce Object: WOD_2__Warranty_Code__c
    Primary Field: WOD_2__Standard_Labor_Minutes__c
    Additional Fields: WOD_2__Standard_Labor_Hour__c
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),AND(NOT(ISBLANK(WOD_2__Standard_Labor_Minutes__c)),
(WOD_2__Standard_Labor_Minutes__c >0),
NOT(ISBLANK(WOD_2__Standard_Labor_Hour__c)),
(WOD_2__Standard_Labor_Hour__c >0)))
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['WOD_2__Standard_Labor_Minutes__c', 'WOD_2__Standard_Labor_Hour__c']
    if hasattr(row_data, 'keys'):
        _available = set(row_data.keys())
    elif hasattr(row_data, 'index'):
        _available = set(row_data.index)
    else:
        _available = set()
    if _required_fields and not _available.intersection(_required_fields):
        return True  # Skip: none of the rule fields are in the data
    
    # Helper to safely retrieve field values from row data
    def safe_get(field_name):
        try:
            if hasattr(row_data, 'get'):
                value = row_data.get(field_name, '')
            elif hasattr(row_data, '__getitem__'):
                try:
                    value = row_data[field_name]
                except (KeyError, IndexError):
                    value = ''
            else:
                value = ''
            if pd.isna(value):
                return ''
            return value
        except:
            return ''
    
    try:
        # Evaluate the error condition (converted from Salesforce formula)
        # Salesforce: formula True = Error condition = Record is INVALID
        # Salesforce: formula False = No error = Record is VALID
        error_condition = False  # Context-dependent rule — skipped in offline validation
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'Standard_Labor_Time\': {e}")
        return False  # Mark as invalid on error

def validate_VRM_Cannot_Change_Owner(row_data):
    """
    Validation Rule: VRM_Cannot_Change_Owner
    Salesforce Object: WOD_2__Warranty_Code__c
    Primary Field: OwnerId
    
    
    Original Apex Formula:
    AND(
ISCHANGED(OwnerId),
$Profile.Name <> 'System Administrator'
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['OwnerId']
    if hasattr(row_data, 'keys'):
        _available = set(row_data.keys())
    elif hasattr(row_data, 'index'):
        _available = set(row_data.index)
    else:
        _available = set()
    if _required_fields and not _available.intersection(_required_fields):
        return True  # Skip: none of the rule fields are in the data
    
    # Helper to safely retrieve field values from row data
    def safe_get(field_name):
        try:
            if hasattr(row_data, 'get'):
                value = row_data.get(field_name, '')
            elif hasattr(row_data, '__getitem__'):
                try:
                    value = row_data[field_name]
                except (KeyError, IndexError):
                    value = ''
            else:
                value = ''
            if pd.isna(value):
                return ''
            return value
        except:
            return ''
    
    try:
        # Evaluate the error condition (converted from Salesforce formula)
        # Salesforce: formula True = Error condition = Record is INVALID
        # Salesforce: formula False = No error = Record is VALID
        error_condition = False  # Context-dependent rule — skipped in offline validation
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'VRM_Cannot_Change_Owner\': {e}")
        return False  # Mark as invalid on error

def validate_VRM_Resolution_Code_Mandatory_Job_Code(row_data):
    """
    Validation Rule: VRM_Resolution_Code_Mandatory_Job_Code
    Salesforce Object: WOD_2__Warranty_Code__c
    Primary Field: VRM_Resolution_Code__c
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),
$RecordType.DeveloperName = 'WOD_2__Job_Code',
ISBLANK(VRM_Resolution_Code__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['VRM_Resolution_Code__c']
    if hasattr(row_data, 'keys'):
        _available = set(row_data.keys())
    elif hasattr(row_data, 'index'):
        _available = set(row_data.index)
    else:
        _available = set()
    if _required_fields and not _available.intersection(_required_fields):
        return True  # Skip: none of the rule fields are in the data
    
    # Helper to safely retrieve field values from row data
    def safe_get(field_name):
        try:
            if hasattr(row_data, 'get'):
                value = row_data.get(field_name, '')
            elif hasattr(row_data, '__getitem__'):
                try:
                    value = row_data[field_name]
                except (KeyError, IndexError):
                    value = ''
            else:
                value = ''
            if pd.isna(value):
                return ''
            return value
        except:
            return ''
    
    try:
        # Evaluate the error condition (converted from Salesforce formula)
        # Salesforce: formula True = Error condition = Record is INVALID
        # Salesforce: formula False = No error = Record is VALID
        error_condition = False  # Context-dependent rule — skipped in offline validation
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'VRM_Resolution_Code_Mandatory_Job_Code\': {e}")
        return False  # Mark as invalid on error

def validate_VRM_Failure_Code_Mandatory_Job_Code(row_data):
    """
    Validation Rule: VRM_Failure_Code_Mandatory_Job_Code
    Salesforce Object: WOD_2__Warranty_Code__c
    Primary Field: VRM_Failure_Code__c
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),
$RecordType.DeveloperName = 'WOD_2__Job_Code',
ISBLANK(VRM_Failure_Code__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['VRM_Failure_Code__c']
    if hasattr(row_data, 'keys'):
        _available = set(row_data.keys())
    elif hasattr(row_data, 'index'):
        _available = set(row_data.index)
    else:
        _available = set()
    if _required_fields and not _available.intersection(_required_fields):
        return True  # Skip: none of the rule fields are in the data
    
    # Helper to safely retrieve field values from row data
    def safe_get(field_name):
        try:
            if hasattr(row_data, 'get'):
                value = row_data.get(field_name, '')
            elif hasattr(row_data, '__getitem__'):
                try:
                    value = row_data[field_name]
                except (KeyError, IndexError):
                    value = ''
            else:
                value = ''
            if pd.isna(value):
                return ''
            return value
        except:
            return ''
    
    try:
        # Evaluate the error condition (converted from Salesforce formula)
        # Salesforce: formula True = Error condition = Record is INVALID
        # Salesforce: formula False = No error = Record is VALID
        error_condition = False  # Context-dependent rule — skipped in offline validation
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'VRM_Failure_Code_Mandatory_Job_Code\': {e}")
        return False  # Mark as invalid on error

def validate_VRM_Standard_Labor_Hour_Required(row_data):
    """
    Validation Rule: VRM_Standard_Labor_Hour_Required
    Salesforce Object: WOD_2__Warranty_Code__c
    Primary Field: WOD_2__Standard_Labor_Hour__c
    
    
    Original Apex Formula:
    AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),
$RecordType.DeveloperName = 'WOD_2__Job_Code',
ISBLANK(WOD_2__Standard_Labor_Hour__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['WOD_2__Standard_Labor_Hour__c']
    if hasattr(row_data, 'keys'):
        _available = set(row_data.keys())
    elif hasattr(row_data, 'index'):
        _available = set(row_data.index)
    else:
        _available = set()
    if _required_fields and not _available.intersection(_required_fields):
        return True  # Skip: none of the rule fields are in the data
    
    # Helper to safely retrieve field values from row data
    def safe_get(field_name):
        try:
            if hasattr(row_data, 'get'):
                value = row_data.get(field_name, '')
            elif hasattr(row_data, '__getitem__'):
                try:
                    value = row_data[field_name]
                except (KeyError, IndexError):
                    value = ''
            else:
                value = ''
            if pd.isna(value):
                return ''
            return value
        except:
            return ''
    
    try:
        # Evaluate the error condition (converted from Salesforce formula)
        # Salesforce: formula True = Error condition = Record is INVALID
        # Salesforce: formula False = No error = Record is VALID
        error_condition = False  # Context-dependent rule — skipped in offline validation
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'VRM_Standard_Labor_Hour_Required\': {e}")
        return False  # Mark as invalid on error

def validate_record(row):
    '''Validate a single record (row) and return result dict.
    
    Each validation function receives a dict/Series and returns True (valid) or False (invalid).
    '''
    import pandas as pd
    # Convert to dict for consistent field access
    if hasattr(row, 'to_dict'):
        row_dict = row.to_dict()
    elif isinstance(row, dict):
        row_dict = row
    else:
        row_dict = dict(row)
    
    rule_results = {}
    errors = []
    is_valid = True
    try:
        rule_results['validate_Fault_Location_Level'] = bool(validate_Fault_Location_Level(row_dict))
        if not rule_results['validate_Fault_Location_Level']:
            errors.append('validate_Fault_Location_Level')
    except Exception as e:
        rule_results['validate_Fault_Location_Level'] = False
        errors.append(f'validate_Fault_Location_Level (error: {str(e)})')
    try:
        rule_results['validate_Standard_Labor_Time'] = bool(validate_Standard_Labor_Time(row_dict))
        if not rule_results['validate_Standard_Labor_Time']:
            errors.append('validate_Standard_Labor_Time')
    except Exception as e:
        rule_results['validate_Standard_Labor_Time'] = False
        errors.append(f'validate_Standard_Labor_Time (error: {str(e)})')
    try:
        rule_results['validate_VRM_Cannot_Change_Owner'] = bool(validate_VRM_Cannot_Change_Owner(row_dict))
        if not rule_results['validate_VRM_Cannot_Change_Owner']:
            errors.append('validate_VRM_Cannot_Change_Owner')
    except Exception as e:
        rule_results['validate_VRM_Cannot_Change_Owner'] = False
        errors.append(f'validate_VRM_Cannot_Change_Owner (error: {str(e)})')
    try:
        rule_results['validate_VRM_Resolution_Code_Mandatory_Job_Code'] = bool(validate_VRM_Resolution_Code_Mandatory_Job_Code(row_dict))
        if not rule_results['validate_VRM_Resolution_Code_Mandatory_Job_Code']:
            errors.append('validate_VRM_Resolution_Code_Mandatory_Job_Code')
    except Exception as e:
        rule_results['validate_VRM_Resolution_Code_Mandatory_Job_Code'] = False
        errors.append(f'validate_VRM_Resolution_Code_Mandatory_Job_Code (error: {str(e)})')
    try:
        rule_results['validate_VRM_Failure_Code_Mandatory_Job_Code'] = bool(validate_VRM_Failure_Code_Mandatory_Job_Code(row_dict))
        if not rule_results['validate_VRM_Failure_Code_Mandatory_Job_Code']:
            errors.append('validate_VRM_Failure_Code_Mandatory_Job_Code')
    except Exception as e:
        rule_results['validate_VRM_Failure_Code_Mandatory_Job_Code'] = False
        errors.append(f'validate_VRM_Failure_Code_Mandatory_Job_Code (error: {str(e)})')
    try:
        rule_results['validate_VRM_Standard_Labor_Hour_Required'] = bool(validate_VRM_Standard_Labor_Hour_Required(row_dict))
        if not rule_results['validate_VRM_Standard_Labor_Hour_Required']:
            errors.append('validate_VRM_Standard_Labor_Hour_Required')
    except Exception as e:
        rule_results['validate_VRM_Standard_Labor_Hour_Required'] = False
        errors.append(f'validate_VRM_Standard_Labor_Hour_Required (error: {str(e)})')
    if errors:
        is_valid = False
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
