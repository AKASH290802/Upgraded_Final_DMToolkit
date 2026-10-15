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


def validate_TCSNALA_Prevent_BlankSN(row_data):
    """
    Validation Rule: TCSNALA_Prevent_BlankSN
    Salesforce Object: Asset
    Primary Field: Quantity
    Additional Fields: TCSNALA_Serial_Number_Unknown__c, SerialNumber, RecordType, DeveloperName
    
    Original Apex Formula:
    AND(OR ( ISBLANK(Quantity) ,  Quantity < 2), 
$Permission.ETL_Validation_Rule_Bypass = FALSE,
TCSNALA_Serial_Number_Unknown__c = FALSE,
ISBLANK(SerialNumber),
OR(
RecordType.DeveloperName = "CHVAC_Americas",
RecordType.DeveloperName = "CHVAC_Latin_America"))
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['Quantity', 'TCSNALA_Serial_Number_Unknown__c', 'SerialNumber', 'RecordType', 'DeveloperName']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Prevent_BlankSN\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Prevent_Lg_Quantity(row_data):
    """
    Validation Rule: TCSNALA_Prevent_Lg_Quantity
    Salesforce Object: Asset
    Primary Field: Quantity
    Additional Fields: RecordType, DeveloperName
    
    Original Apex Formula:
    AND(
$Permission.ETL_Validation_Rule_Bypass = FALSE,
Quantity > 999,
OR(
RecordType.DeveloperName = "CHVAC_Americas",
RecordType.DeveloperName = "CHVAC_Latin_America"))
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['Quantity', 'RecordType', 'DeveloperName']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Prevent_Lg_Quantity\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Prevent_SN_And_Unknown(row_data):
    """
    Validation Rule: TCSNALA_Prevent_SN_And_Unknown
    Salesforce Object: Asset
    Primary Field: TCSNALA_Serial_Number_Unknown__c
    Additional Fields: SerialNumber, RecordType, DeveloperName
    
    Original Apex Formula:
    AND(
$Permission.ETL_Validation_Rule_Bypass = FALSE,
TCSNALA_Serial_Number_Unknown__c = TRUE,
NOT(ISBLANK(SerialNumber)),
NOT(LEFT(SerialNumber, 2) = "NS"),
OR(
RecordType.DeveloperName = "CHVAC_Americas",
RecordType.DeveloperName = "CHVAC_Latin_America"))
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['TCSNALA_Serial_Number_Unknown__c', 'SerialNumber', 'RecordType', 'DeveloperName']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Prevent_SN_And_Unknown\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Prevent_Strings_in_Serial_Num(row_data):
    """
    Validation Rule: TCSNALA_Prevent_Strings_in_Serial_Num
    Salesforce Object: Asset
    Primary Field: Quantity
    Additional Fields: TCSNALA_Serial_Number_Unknown__c, RecordType, DeveloperName, SerialNumber
    
    Original Apex Formula:
    AND(OR ( ISBLANK(Quantity) ,  Quantity < 2), 
$Permission.ETL_Validation_Rule_Bypass = FALSE,
TCSNALA_Serial_Number_Unknown__c = False,
OR(
   RecordType.DeveloperName = "CHVAC_Americas",
   RecordType.DeveloperName = "CHVAC_Latin_America"
),
OR(
ISBLANK(SerialNumber),
SerialNumber="UNKNOWN",
SerialNumber="PLEASE OBTAIN",
SerialNumber="NEED M/S #",
SerialNumber="NEED SERIAL #",
SerialNumber="NEED",
SerialNumber="NS-1",
SerialNumber="NS-2",
SerialNumber="No Tag",
SerialNumber="UNREADABLE",
SerialNumber="DUPLICATE",
SerialNumber="NONE",
SerialNumber="TBD1",
SerialNumber="Unknown",
SerialNumber="Please obtain",
SerialNumber="Need M/S #",
SerialNumber="Need Serial #",
SerialNumber="Need",
SerialNumber="NS-1",
SerialNumber="NS-2",
SerialNumber="No Tag",
SerialNumber="Unreadable",
SerialNumber="Duplicate",
SerialNumber="None",
SerialNumber="Tbd1",
SerialNumber="unknown",
SerialNumber="please obtain",
SerialNumber="need M/S #",
SerialNumber="need serial #",
SerialNumber="need",
SerialNumber="ns-1",
SerialNumber="ns-2",
SerialNumber="no tag",
SerialNumber="unreadable",
SerialNumber="duplicate",
SerialNumber="none",
SerialNumber="tbd1",
SerialNumber="1234",
SerialNumber="1111",
LEN(SerialNumber)<4))
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['Quantity', 'TCSNALA_Serial_Number_Unknown__c', 'RecordType', 'DeveloperName', 'SerialNumber']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Prevent_Strings_in_Serial_Num\': {e}")
        return False  # Mark as invalid on error

def validate_Serial_Number_Means_Qty_1(row_data):
    """
    Validation Rule: Serial_Number_Means_Qty_1
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, SerialNumber, Quantity
    
    Original Apex Formula:
    AND(
OR(
   RecordType.DeveloperName = "CHVAC_Americas",
   RecordType.DeveloperName = "CHVAC_Latin_America"
),
SerialNumber != NULL,
Quantity > 1
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # Primary Field: RecordType
    # Additional Fields: DeveloperName, SerialNumber, Quantity
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'SerialNumber', 'Quantity']
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
        error_condition = _and(  _or( safe_get('RecordType_DeveloperName') == "CHVAC_Americas", safe_get('RecordType_DeveloperName') == "CHVAC_Latin_America" ), safe_get('SerialNumber') != NULL, safe_get('Quantity') > 1 )
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'Serial_Number_Means_Qty_1\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Asset_Quantity_Greater_Equal_One(row_data):
    """
    Validation Rule: TCSNALA_Asset_Quantity_Greater_Equal_One
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, Quantity
    
    Original Apex Formula:
    AND(
    OR(
        RecordType.DeveloperName = "CHVAC_Americas",
        RecordType.DeveloperName = "CHVAC_Latin_America"
    ),
    Quantity < 1
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # Primary Field: RecordType
    # Additional Fields: DeveloperName, Quantity
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'Quantity']
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
        error_condition = _and(  _or( safe_get('RecordType_DeveloperName') == "CHVAC_Americas", safe_get('RecordType_DeveloperName') == "CHVAC_Latin_America" ), safe_get('Quantity') < 1 )
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'TCSNALA_Asset_Quantity_Greater_Equal_One\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Credit_Job_Name_Not_Editable(row_data):
    """
    Validation Rule: TCSNALA_Credit_Job_Name_Not_Editable
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, TCSNALA_SIL__c, TCSNALA_Credit_Job_Name__c
    
    Original Apex Formula:
    AND(
    RecordType.DeveloperName = "CHVAC_Americas",
    TCSNALA_SIL__c,
    ISCHANGED(TCSNALA_Credit_Job_Name__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'TCSNALA_SIL__c', 'TCSNALA_Credit_Job_Name__c']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Credit_Job_Name_Not_Editable\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Credit_Job_Number_Not_Editable(row_data):
    """
    Validation Rule: TCSNALA_Credit_Job_Number_Not_Editable
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, TCSNALA_SIL__c, TCSNALA_Legacy_Job_Number__c
    
    Original Apex Formula:
    AND(
    RecordType.DeveloperName = "CHVAC_Americas",
    TCSNALA_SIL__c,
    ISCHANGED(TCSNALA_Legacy_Job_Number__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'TCSNALA_SIL__c', 'TCSNALA_Legacy_Job_Number__c']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Credit_Job_Number_Not_Editable\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Known_Serial_Number(row_data):
    """
    Validation Rule: TCSNALA_Known_Serial_Number
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, Quantity, TCSNALA_Serial_Number_Unknown__c, SerialNumber
    
    Original Apex Formula:
    AND(
   (RecordType.DeveloperName = "CHVAC_Americas" || RecordType.DeveloperName = "CHVAC_Latin_America"),
   Quantity = 1, 
   NOT (TCSNALA_Serial_Number_Unknown__c), 
   ISBLANK (SerialNumber)


)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # Primary Field: RecordType
    # Additional Fields: DeveloperName, Quantity, TCSNALA_Serial_Number_Unknown__c, SerialNumber
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'Quantity', 'TCSNALA_Serial_Number_Unknown__c', 'SerialNumber']
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
        error_condition = _and( (safe_get('RecordType_DeveloperName') == "CHVAC_Americas"  or  safe_get('RecordType_DeveloperName') == "CHVAC_Latin_America"), safe_get('Quantity') == 1,  _not(safe_get('TCSNALA_Serial_Number_Unknown__c')), _is_blank(safe_get('SerialNumber')) )
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'TCSNALA_Known_Serial_Number\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Other_Asset_Manufacturer_Require(row_data):
    """
    Validation Rule: TCSNALA_Other_Asset_Manufacturer_Require
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, TCSNALA_Asset_Manufacturer__c, TCSNALA_Other_Manufacturer__c
    
    Original Apex Formula:
    AND(
    (RecordType.DeveloperName = "CHVAC_Americas" || RecordType.DeveloperName = "CHVAC_Latin_America"),
    ISPICKVAL(TCSNALA_Asset_Manufacturer__c, "Other"),
    ISBLANK(TCSNALA_Other_Manufacturer__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # Primary Field: RecordType
    # Additional Fields: DeveloperName, TCSNALA_Asset_Manufacturer__c, TCSNALA_Other_Manufacturer__c
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'TCSNALA_Asset_Manufacturer__c', 'TCSNALA_Other_Manufacturer__c']
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
        error_condition = _and( (safe_get('RecordType_DeveloperName') == "CHVAC_Americas"  or  safe_get('RecordType_DeveloperName') == "CHVAC_Latin_America"), _ispickval(safe_get('TCSNALA_Asset_Manufacturer__c'), "Other"), _is_blank(safe_get('TCSNALA_Other_Manufacturer__c')) )
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'TCSNALA_Other_Asset_Manufacturer_Require\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Quantity_Not_Editable(row_data):
    """
    Validation Rule: TCSNALA_Quantity_Not_Editable
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, TCSNALA_SIL__c, Quantity
    
    Original Apex Formula:
    AND(
    RecordType.DeveloperName = "CHVAC_Americas",
    TCSNALA_SIL__c,
    ISCHANGED(Quantity)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'TCSNALA_SIL__c', 'Quantity']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Quantity_Not_Editable\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Sales_Order_Number_Not_Editable(row_data):
    """
    Validation Rule: TCSNALA_Sales_Order_Number_Not_Editable
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, TCSNALA_SIL__c, TCSNALA_Legacy_Order_Number__c
    
    Original Apex Formula:
    AND(
    RecordType.DeveloperName = "CHVAC_Americas",
    TCSNALA_SIL__c,
    ISCHANGED(TCSNALA_Legacy_Order_Number__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'TCSNALA_SIL__c', 'TCSNALA_Legacy_Order_Number__c']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Sales_Order_Number_Not_Editable\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Serial_Number_Not_Editable(row_data):
    """
    Validation Rule: TCSNALA_Serial_Number_Not_Editable
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, TCSNALA_SIL__c, SerialNumber
    
    Original Apex Formula:
    AND(
    RecordType.DeveloperName = "CHVAC_Americas",
    TCSNALA_SIL__c,
    ISCHANGED(SerialNumber)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'TCSNALA_SIL__c', 'SerialNumber']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Serial_Number_Not_Editable\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Serial_Number_Unkn_Not_Editable(row_data):
    """
    Validation Rule: TCSNALA_Serial_Number_Unkn_Not_Editable
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, TCSNALA_SIL__c, TCSNALA_Serial_Number_Unknown__c
    
    Original Apex Formula:
    AND(
    RecordType.DeveloperName = "CHVAC_Americas",
    TCSNALA_SIL__c,
    ISCHANGED(TCSNALA_Serial_Number_Unknown__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'TCSNALA_SIL__c', 'TCSNALA_Serial_Number_Unknown__c']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Serial_Number_Unkn_Not_Editable\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Ship_Date_Not_Editable(row_data):
    """
    Validation Rule: TCSNALA_Ship_Date_Not_Editable
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, TCSNALA_SIL__c, TCSNALA_Ship_Date__c
    
    Original Apex Formula:
    AND(
    RecordType.DeveloperName = "CHVAC_Americas",
    TCSNALA_SIL__c,
    ISCHANGED(TCSNALA_Ship_Date__c)
)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'TCSNALA_SIL__c', 'TCSNALA_Ship_Date__c']
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
        print(f"Warning: Error in validation rule \'TCSNALA_Ship_Date_Not_Editable\': {e}")
        return False  # Mark as invalid on error

def validate_TCSNALA_Unknown_Serial_Number(row_data):
    """
    Validation Rule: TCSNALA_Unknown_Serial_Number
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, Quantity, TCSNALA_Serial_Number_Unknown__c, SerialNumber
    
    Original Apex Formula:
    AND(
   RecordType.DeveloperName = "CHVAC_Americas",
   Quantity = 1, 
   TCSNALA_Serial_Number_Unknown__c, 
   NOT(LEFT(SerialNumber, 3) = "NS-"), 
   NOT(ISBLANK(SerialNumber))
   )
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # Primary Field: RecordType
    # Additional Fields: DeveloperName, Quantity, TCSNALA_Serial_Number_Unknown__c, SerialNumber
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'Quantity', 'TCSNALA_Serial_Number_Unknown__c', 'SerialNumber']
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
        error_condition = _and( safe_get('RecordType_DeveloperName') == "CHVAC_Americas", safe_get('Quantity') == 1, safe_get('TCSNALA_Serial_Number_Unknown__c'),  _not(_left(safe_get('SerialNumber'), 3) == "NS-"),  _not(_is_blank(safe_get('SerialNumber'))) )
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'TCSNALA_Unknown_Serial_Number\': {e}")
        return False  # Mark as invalid on error

def validate_TK_Model_Year_Number(row_data):
    """
    Validation Rule: TK_Model_Year_Number
    Salesforce Object: Asset
    Primary Field: ISNUMBER
    Additional Fields: TK_ModelYear__c, RecordType, DeveloperName
    
    Original Apex Formula:
    AND(
					OR(
				    NOT(ISNUMBER(TK_ModelYear__c)),
        LEN(TK_ModelYear__c) < 4
				    ),
					 RecordType.DeveloperName == 'TK_Transport'
					)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # Primary Field: ISNUMBER
    # Additional Fields: TK_ModelYear__c, RecordType, DeveloperName
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['ISNUMBER', 'TK_ModelYear__c', 'RecordType', 'DeveloperName']
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
        error_condition = _and(  _or(  _not(safe_get('ISNUMBER')(safe_get('TK_ModelYear__c'))), len(safe_get('TK_ModelYear__c')) < 4 ), safe_get('RecordType_DeveloperName') == 'TK_Transport' )
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'TK_Model_Year_Number\': {e}")
        return False  # Mark as invalid on error

def validate_Asset_Required_Fields(row_data):
    """
    Validation Rule: Asset_Required_Fields
    Salesforce Object: Asset
    Primary Field: RecordTypeName__c
    Additional Fields: Product2, RecordType, DeveloperName, Type__c, AccountId, Product2Id, SerialNumber
    
    Original Apex Formula:
    IF(RecordTypeName__c = 'TK_EMEA_Fleet_Monitoring', 
		AND(
		   	AND(
        Product2.RecordType.DeveloperName = 'TK_Transport_EMEA',
	    	  ISPICKVAL(Product2.Type__c, 'Base Product')
						  ),
  				OR(
								 ISBLANK( AccountId ) ,
									ISBLANK( Product2Id ) ,
									ISBLANK( SerialNumber ) 
		  				  )
			   ),
		FALSE
		)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # Primary Field: RecordTypeName__c
    # Additional Fields: Product2, RecordType, DeveloperName, Type__c, AccountId, Product2Id, SerialNumber
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordTypeName__c', 'Product2', 'RecordType', 'DeveloperName', 'Type__c', 'AccountId', 'Product2Id', 'SerialNumber']
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
        error_condition = _if(safe_get('RecordTypeName__c') == 'TK_EMEA_Fleet_Monitoring',  _and(  _and( safe_get('Product2_RecordType_DeveloperName') == 'TK_Transport_EMEA', _ispickval(safe_get('Product2_Type__c'), 'Base Product') ),  _or( _is_blank( safe_get('AccountId') ) , _is_blank( safe_get('Product2Id') ) , _is_blank( safe_get('SerialNumber') ) ) ), False )
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \'Asset_Required_Fields\': {e}")
        return False  # Mark as invalid on error

def validate_CHVAC_APAC_Asset_Required_Fields(row_data):
    """
    Validation Rule: CHVAC_APAC_Asset_Required_Fields
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, Model_Name__c, SerialNumber
    
    Original Apex Formula:
    AND(
$Permission.ETL_Validation_Rule_Bypass = FALSE,
OR(
RecordType.DeveloperName == "CHVAC_China",
RecordType.DeveloperName == "CHVAC_Thailand",
RecordType.DeveloperName == "CHVAC_Singapore"
),
OR(
ISBLANK( Model_Name__c ) ,
ISBLANK(SerialNumber )
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
    _required_fields = ['RecordType', 'DeveloperName', 'Model_Name__c', 'SerialNumber']
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
        print(f"Warning: Error in validation rule \'CHVAC_APAC_Asset_Required_Fields\': {e}")
        return False  # Mark as invalid on error

def validate_CTS_Dryer_Make_Other_Require_Other_Value(row_data):
    """
    Validation Rule: CTS_Dryer_Make_Other_Require_Other_Value
    Salesforce Object: Asset
    Primary Field: Dryer_Make__c
    Additional Fields: Dryer_Make_Other__c
    
    Original Apex Formula:
    ISPICKVAL( Dryer_Make__c ,"Other") && ISBLANK( Dryer_Make_Other__c )&& $Permission.ETL_Validation_Rule_Bypass = FALSE
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['Dryer_Make__c', 'Dryer_Make_Other__c']
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
        print(f"Warning: Error in validation rule \'CTS_Dryer_Make_Other_Require_Other_Value\': {e}")
        return False  # Mark as invalid on error

def validate_CTS_Dryer_Type_Other_Require_Other_Value(row_data):
    """
    Validation Rule: CTS_Dryer_Type_Other_Require_Other_Value
    Salesforce Object: Asset
    Primary Field: Dryer_Type__c
    Additional Fields: Dryer_Type_Other__c
    
    Original Apex Formula:
    ISPICKVAL(Dryer_Type__c, "Other") && ISBLANK(Dryer_Type_Other__c) && $Permission.ETL_Validation_Rule_Bypass = FALSE
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['Dryer_Type__c', 'Dryer_Type_Other__c']
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
        print(f"Warning: Error in validation rule \'CTS_Dryer_Type_Other_Require_Other_Value\': {e}")
        return False  # Mark as invalid on error

def validate_CTS_VFD_Used_Require_Make_KW(row_data):
    """
    Validation Rule: CTS_VFD_Used_Require_Make_KW
    Salesforce Object: Asset
    Primary Field: Is_VFD_Used__c
    Additional Fields: VFD_Make__c, VFD_KW__c
    
    Original Apex Formula:
    AND (
$Permission.ETL_Validation_Rule_Bypass = FALSE,
ISPICKVAL(Is_VFD_Used__c , "Yes"),
 OR((ISPICKVAL( VFD_Make__c ,"")),
    (ISBLANK(  VFD_KW__c  ))))
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['Is_VFD_Used__c', 'VFD_Make__c', 'VFD_KW__c']
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
        print(f"Warning: Error in validation rule \'CTS_VFD_Used_Require_Make_KW\': {e}")
        return False  # Mark as invalid on error

def validate_Name_Product_Contact_Disabled_from_edit(row_data):
    """
    Validation Rule: Name_Product_Contact_Disabled_from_edit
    Salesforce Object: Asset
    Primary Field: Name
    Additional Fields: ContactId, Product2Id
    
    Original Apex Formula:
    AND(
$Permission.ETL_Validation_Rule_Bypass = FALSE,
OR(ISCHANGED(Name),
    ISCHANGED(ContactId ),
    ISCHANGED(Product2Id )
    ),
NOT( $Setup.IR_API_Bypass__c.IR_Validation_Bypass__c ),
$RecordType.DeveloperName = "NA_Air_Edit"

)
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['Name', 'ContactId', 'Product2Id']
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
        print(f"Warning: Error in validation rule \'Name_Product_Contact_Disabled_from_edit\': {e}")
        return False  # Mark as invalid on error

def validate_Ship_Date_less_or_equal_to_Install_Date(row_data):
    """
    Validation Rule: Ship_Date_less_or_equal_to_Install_Date
    Salesforce Object: Asset
    Primary Field: InstallDate
    Additional Fields: Ship_Date__c
    
    Original Apex Formula:
    AND(
$Permission.ETL_Validation_Rule_Bypass = FALSE,
NOT(ISNULL(InstallDate)),
    NOT(ISNULL(Ship_Date__c)),
    NOT((Ship_Date__c <=  InstallDate))
   )
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['InstallDate', 'Ship_Date__c']
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
        print(f"Warning: Error in validation rule \'Ship_Date_less_or_equal_to_Install_Date\': {e}")
        return False  # Mark as invalid on error

def validate_TCLA_Sales_Office_Required(row_data):
    """
    Validation Rule: TCLA_Sales_Office_Required
    Salesforce Object: Asset
    Primary Field: TCLA_Sales_Office__c
    
    
    Original Apex Formula:
    AND(
  ISPICKVAL(TCLA_Sales_Office__c, ""),
 OR(
 $Profile.Name = "CHVAC LAR Service Technician",
 $Profile.Name = "CHVAC LAR Services",
 $Profile.Name = "CHVAC LAR ASM",
 $Profile.Name = "Commercial Leadership - LAM",
 $Profile.Name = "Commercial Sales - LAM"
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
    _required_fields = ['TCLA_Sales_Office__c']
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
        print(f"Warning: Error in validation rule \'TCLA_Sales_Office_Required\': {e}")
        return False  # Mark as invalid on error

def validate_TKM_Validation(row_data):
    """
    Validation Rule: TKM_Validation
    Salesforce Object: Asset
    Primary Field: RecordType
    Additional Fields: DeveloperName, Name
    
    Original Apex Formula:
    RecordType.DeveloperName == 'Thermo_King_Marine'  &&  ISCHANGED( Name )
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    # SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = ['RecordType', 'DeveloperName', 'Name']
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
        print(f"Warning: Error in validation rule \'TKM_Validation\': {e}")
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
        rule_results['validate_TCSNALA_Prevent_BlankSN'] = bool(validate_TCSNALA_Prevent_BlankSN(row_dict))
        if not rule_results['validate_TCSNALA_Prevent_BlankSN']:
            errors.append('validate_TCSNALA_Prevent_BlankSN')
    except Exception as e:
        rule_results['validate_TCSNALA_Prevent_BlankSN'] = False
        errors.append(f'validate_TCSNALA_Prevent_BlankSN (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Prevent_Lg_Quantity'] = bool(validate_TCSNALA_Prevent_Lg_Quantity(row_dict))
        if not rule_results['validate_TCSNALA_Prevent_Lg_Quantity']:
            errors.append('validate_TCSNALA_Prevent_Lg_Quantity')
    except Exception as e:
        rule_results['validate_TCSNALA_Prevent_Lg_Quantity'] = False
        errors.append(f'validate_TCSNALA_Prevent_Lg_Quantity (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Prevent_SN_And_Unknown'] = bool(validate_TCSNALA_Prevent_SN_And_Unknown(row_dict))
        if not rule_results['validate_TCSNALA_Prevent_SN_And_Unknown']:
            errors.append('validate_TCSNALA_Prevent_SN_And_Unknown')
    except Exception as e:
        rule_results['validate_TCSNALA_Prevent_SN_And_Unknown'] = False
        errors.append(f'validate_TCSNALA_Prevent_SN_And_Unknown (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Prevent_Strings_in_Serial_Num'] = bool(validate_TCSNALA_Prevent_Strings_in_Serial_Num(row_dict))
        if not rule_results['validate_TCSNALA_Prevent_Strings_in_Serial_Num']:
            errors.append('validate_TCSNALA_Prevent_Strings_in_Serial_Num')
    except Exception as e:
        rule_results['validate_TCSNALA_Prevent_Strings_in_Serial_Num'] = False
        errors.append(f'validate_TCSNALA_Prevent_Strings_in_Serial_Num (error: {str(e)})')
    try:
        rule_results['validate_Serial_Number_Means_Qty_1'] = bool(validate_Serial_Number_Means_Qty_1(row_dict))
        if not rule_results['validate_Serial_Number_Means_Qty_1']:
            errors.append('validate_Serial_Number_Means_Qty_1')
    except Exception as e:
        rule_results['validate_Serial_Number_Means_Qty_1'] = False
        errors.append(f'validate_Serial_Number_Means_Qty_1 (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Asset_Quantity_Greater_Equal_One'] = bool(validate_TCSNALA_Asset_Quantity_Greater_Equal_One(row_dict))
        if not rule_results['validate_TCSNALA_Asset_Quantity_Greater_Equal_One']:
            errors.append('validate_TCSNALA_Asset_Quantity_Greater_Equal_One')
    except Exception as e:
        rule_results['validate_TCSNALA_Asset_Quantity_Greater_Equal_One'] = False
        errors.append(f'validate_TCSNALA_Asset_Quantity_Greater_Equal_One (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Credit_Job_Name_Not_Editable'] = bool(validate_TCSNALA_Credit_Job_Name_Not_Editable(row_dict))
        if not rule_results['validate_TCSNALA_Credit_Job_Name_Not_Editable']:
            errors.append('validate_TCSNALA_Credit_Job_Name_Not_Editable')
    except Exception as e:
        rule_results['validate_TCSNALA_Credit_Job_Name_Not_Editable'] = False
        errors.append(f'validate_TCSNALA_Credit_Job_Name_Not_Editable (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Credit_Job_Number_Not_Editable'] = bool(validate_TCSNALA_Credit_Job_Number_Not_Editable(row_dict))
        if not rule_results['validate_TCSNALA_Credit_Job_Number_Not_Editable']:
            errors.append('validate_TCSNALA_Credit_Job_Number_Not_Editable')
    except Exception as e:
        rule_results['validate_TCSNALA_Credit_Job_Number_Not_Editable'] = False
        errors.append(f'validate_TCSNALA_Credit_Job_Number_Not_Editable (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Known_Serial_Number'] = bool(validate_TCSNALA_Known_Serial_Number(row_dict))
        if not rule_results['validate_TCSNALA_Known_Serial_Number']:
            errors.append('validate_TCSNALA_Known_Serial_Number')
    except Exception as e:
        rule_results['validate_TCSNALA_Known_Serial_Number'] = False
        errors.append(f'validate_TCSNALA_Known_Serial_Number (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Other_Asset_Manufacturer_Require'] = bool(validate_TCSNALA_Other_Asset_Manufacturer_Require(row_dict))
        if not rule_results['validate_TCSNALA_Other_Asset_Manufacturer_Require']:
            errors.append('validate_TCSNALA_Other_Asset_Manufacturer_Require')
    except Exception as e:
        rule_results['validate_TCSNALA_Other_Asset_Manufacturer_Require'] = False
        errors.append(f'validate_TCSNALA_Other_Asset_Manufacturer_Require (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Quantity_Not_Editable'] = bool(validate_TCSNALA_Quantity_Not_Editable(row_dict))
        if not rule_results['validate_TCSNALA_Quantity_Not_Editable']:
            errors.append('validate_TCSNALA_Quantity_Not_Editable')
    except Exception as e:
        rule_results['validate_TCSNALA_Quantity_Not_Editable'] = False
        errors.append(f'validate_TCSNALA_Quantity_Not_Editable (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Sales_Order_Number_Not_Editable'] = bool(validate_TCSNALA_Sales_Order_Number_Not_Editable(row_dict))
        if not rule_results['validate_TCSNALA_Sales_Order_Number_Not_Editable']:
            errors.append('validate_TCSNALA_Sales_Order_Number_Not_Editable')
    except Exception as e:
        rule_results['validate_TCSNALA_Sales_Order_Number_Not_Editable'] = False
        errors.append(f'validate_TCSNALA_Sales_Order_Number_Not_Editable (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Serial_Number_Not_Editable'] = bool(validate_TCSNALA_Serial_Number_Not_Editable(row_dict))
        if not rule_results['validate_TCSNALA_Serial_Number_Not_Editable']:
            errors.append('validate_TCSNALA_Serial_Number_Not_Editable')
    except Exception as e:
        rule_results['validate_TCSNALA_Serial_Number_Not_Editable'] = False
        errors.append(f'validate_TCSNALA_Serial_Number_Not_Editable (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Serial_Number_Unkn_Not_Editable'] = bool(validate_TCSNALA_Serial_Number_Unkn_Not_Editable(row_dict))
        if not rule_results['validate_TCSNALA_Serial_Number_Unkn_Not_Editable']:
            errors.append('validate_TCSNALA_Serial_Number_Unkn_Not_Editable')
    except Exception as e:
        rule_results['validate_TCSNALA_Serial_Number_Unkn_Not_Editable'] = False
        errors.append(f'validate_TCSNALA_Serial_Number_Unkn_Not_Editable (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Ship_Date_Not_Editable'] = bool(validate_TCSNALA_Ship_Date_Not_Editable(row_dict))
        if not rule_results['validate_TCSNALA_Ship_Date_Not_Editable']:
            errors.append('validate_TCSNALA_Ship_Date_Not_Editable')
    except Exception as e:
        rule_results['validate_TCSNALA_Ship_Date_Not_Editable'] = False
        errors.append(f'validate_TCSNALA_Ship_Date_Not_Editable (error: {str(e)})')
    try:
        rule_results['validate_TCSNALA_Unknown_Serial_Number'] = bool(validate_TCSNALA_Unknown_Serial_Number(row_dict))
        if not rule_results['validate_TCSNALA_Unknown_Serial_Number']:
            errors.append('validate_TCSNALA_Unknown_Serial_Number')
    except Exception as e:
        rule_results['validate_TCSNALA_Unknown_Serial_Number'] = False
        errors.append(f'validate_TCSNALA_Unknown_Serial_Number (error: {str(e)})')
    try:
        rule_results['validate_TK_Model_Year_Number'] = bool(validate_TK_Model_Year_Number(row_dict))
        if not rule_results['validate_TK_Model_Year_Number']:
            errors.append('validate_TK_Model_Year_Number')
    except Exception as e:
        rule_results['validate_TK_Model_Year_Number'] = False
        errors.append(f'validate_TK_Model_Year_Number (error: {str(e)})')
    try:
        rule_results['validate_Asset_Required_Fields'] = bool(validate_Asset_Required_Fields(row_dict))
        if not rule_results['validate_Asset_Required_Fields']:
            errors.append('validate_Asset_Required_Fields')
    except Exception as e:
        rule_results['validate_Asset_Required_Fields'] = False
        errors.append(f'validate_Asset_Required_Fields (error: {str(e)})')
    try:
        rule_results['validate_CHVAC_APAC_Asset_Required_Fields'] = bool(validate_CHVAC_APAC_Asset_Required_Fields(row_dict))
        if not rule_results['validate_CHVAC_APAC_Asset_Required_Fields']:
            errors.append('validate_CHVAC_APAC_Asset_Required_Fields')
    except Exception as e:
        rule_results['validate_CHVAC_APAC_Asset_Required_Fields'] = False
        errors.append(f'validate_CHVAC_APAC_Asset_Required_Fields (error: {str(e)})')
    try:
        rule_results['validate_CTS_Dryer_Make_Other_Require_Other_Value'] = bool(validate_CTS_Dryer_Make_Other_Require_Other_Value(row_dict))
        if not rule_results['validate_CTS_Dryer_Make_Other_Require_Other_Value']:
            errors.append('validate_CTS_Dryer_Make_Other_Require_Other_Value')
    except Exception as e:
        rule_results['validate_CTS_Dryer_Make_Other_Require_Other_Value'] = False
        errors.append(f'validate_CTS_Dryer_Make_Other_Require_Other_Value (error: {str(e)})')
    try:
        rule_results['validate_CTS_Dryer_Type_Other_Require_Other_Value'] = bool(validate_CTS_Dryer_Type_Other_Require_Other_Value(row_dict))
        if not rule_results['validate_CTS_Dryer_Type_Other_Require_Other_Value']:
            errors.append('validate_CTS_Dryer_Type_Other_Require_Other_Value')
    except Exception as e:
        rule_results['validate_CTS_Dryer_Type_Other_Require_Other_Value'] = False
        errors.append(f'validate_CTS_Dryer_Type_Other_Require_Other_Value (error: {str(e)})')
    try:
        rule_results['validate_CTS_VFD_Used_Require_Make_KW'] = bool(validate_CTS_VFD_Used_Require_Make_KW(row_dict))
        if not rule_results['validate_CTS_VFD_Used_Require_Make_KW']:
            errors.append('validate_CTS_VFD_Used_Require_Make_KW')
    except Exception as e:
        rule_results['validate_CTS_VFD_Used_Require_Make_KW'] = False
        errors.append(f'validate_CTS_VFD_Used_Require_Make_KW (error: {str(e)})')
    try:
        rule_results['validate_Name_Product_Contact_Disabled_from_edit'] = bool(validate_Name_Product_Contact_Disabled_from_edit(row_dict))
        if not rule_results['validate_Name_Product_Contact_Disabled_from_edit']:
            errors.append('validate_Name_Product_Contact_Disabled_from_edit')
    except Exception as e:
        rule_results['validate_Name_Product_Contact_Disabled_from_edit'] = False
        errors.append(f'validate_Name_Product_Contact_Disabled_from_edit (error: {str(e)})')
    try:
        rule_results['validate_Ship_Date_less_or_equal_to_Install_Date'] = bool(validate_Ship_Date_less_or_equal_to_Install_Date(row_dict))
        if not rule_results['validate_Ship_Date_less_or_equal_to_Install_Date']:
            errors.append('validate_Ship_Date_less_or_equal_to_Install_Date')
    except Exception as e:
        rule_results['validate_Ship_Date_less_or_equal_to_Install_Date'] = False
        errors.append(f'validate_Ship_Date_less_or_equal_to_Install_Date (error: {str(e)})')
    try:
        rule_results['validate_TCLA_Sales_Office_Required'] = bool(validate_TCLA_Sales_Office_Required(row_dict))
        if not rule_results['validate_TCLA_Sales_Office_Required']:
            errors.append('validate_TCLA_Sales_Office_Required')
    except Exception as e:
        rule_results['validate_TCLA_Sales_Office_Required'] = False
        errors.append(f'validate_TCLA_Sales_Office_Required (error: {str(e)})')
    try:
        rule_results['validate_TKM_Validation'] = bool(validate_TKM_Validation(row_dict))
        if not rule_results['validate_TKM_Validation']:
            errors.append('validate_TKM_Validation')
    except Exception as e:
        rule_results['validate_TKM_Validation'] = False
        errors.append(f'validate_TKM_Validation (error: {str(e)})')
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
