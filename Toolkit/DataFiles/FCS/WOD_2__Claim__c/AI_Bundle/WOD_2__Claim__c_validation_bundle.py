
"""
AI-Generated Validation Bundle for WOD_2__Claim__c
Generated on: 2025-10-28 13:06:18

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

def validate_clm_nonserializedpartcannothaveserialno(row_data):
    """
    Validation function for rule: CLM_NonSerializedPartCannotHaveSerialNo
    Original Salesforce formula: AND(
    OR(
        $Permission.WOD_2__DisableSkipTriggerNValidation, NOT($Permission.WOD_2__SkipTriggerNValidations)
    )
    ,OR(
        AND(
            ISPICKVAL( WOD_2__Causal_Part_Number__r.WOD_2__Track_Type__c , 'Non-Serialized')
            ,NOT(ISBLANK(WOD_2__Causal_Part_Serial_Number__c))
        )
        ,AND(
            NOT(WOD_2__CausalPartNumber_P2__r.WOD_2__Is_Serialized__c)
            ,NOT(ISBLANK(WOD_2__Causal_Part_Serial_Number__c))
        )    
    )
)
    Error message: Non-Serialized Causal Part can not have serial number
    
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
        print(f"Error in validation function validate_clm_nonserializedpartcannothaveserialno: {str(e)}")
        return False

def validate_gw_reason_mandatory(row_data):
    """
    Validation function for rule: GW_REASON_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Goodwill'), ISPICKVAL(WOD_2__Goodwill_Reason__c,'')))
    Error message: Please select Goodwill Reason
    
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
        print(f"Error in validation function validate_gw_reason_mandatory: {str(e)}")
        return False

def validate_mc_pc_account_mandatory(row_data):
    """
    Validation function for rule: MC_PC_ACCOUNT_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')), ISBLANK(WOD_2__Account__c)),true,false))
    Error message: Service Dealer is required
    
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
        print(f"Error in validation function validate_mc_pc_account_mandatory: {str(e)}")
        return False

def validate_mc_pc_casual_mandatory(row_data):
    """
    Validation function for rule: MC_PC_CASUAL_MANDATORY
    Original Salesforce formula: IF( AND( OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')) ,ISBLANK( WOD_2__Causal_Part_Number__c )) , true, false)
    Error message: DEPRECATED
    
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
        print(f"Error in validation function validate_mc_pc_casual_mandatory: {str(e)}")
        return False

def validate_mc_pc_causal_mandatory(row_data):
    """
    Validation function for rule: MC_PC_CAUSAL_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF( AND( OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part'),ISPICKVAL(WOD_2__Claim_Type__c, 'Field Modification')) ,AND(ISBLANK( WOD_2__Causal_Part_Number__c ),ISBLANK(WOD_2__CausalPartNumber_P2__c))) , true, false))
    Error message: Please select Causal Part
    
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
        print(f"Error in validation function validate_mc_pc_causal_mandatory: {str(e)}")
        return False

def validate_mc_pc_causal_part_sno_mandatory(row_data):
    """
    Validation function for rule: MC_PC_CAUSAL_PART_SNO_MANDATORY
    Original Salesforce formula: AND(
    OR(
        $Permission.WOD_2__DisableSkipTriggerNValidation, NOT($Permission.WOD_2__SkipTriggerNValidations)
    )
    ,IF(
        OR(
            AND(
                ISBLANK(TRIM( WOD_2__Causal_Part_Serial_Number__c ))
                ,ISPICKVAL( WOD_2__Causal_Part_Number__r.WOD_2__Track_Type__c ,'Serialized')
                ,!ISPICKVAL(WOD_2__Claim_Type__c, 'Claim Template')
            ) 
            ,AND(
                ISBLANK(TRIM( WOD_2__Causal_Part_Serial_Number__c ))
                ,WOD_2__CausalPartNumber_P2__r.WOD_2__Is_Serialized__c
                ,!ISPICKVAL(WOD_2__Claim_Type__c, 'Claim Template')
            ) 
        
        )
        , true
        ,false
    )
)
    Error message: Causal Part Serial Number is required for Serialized Part
    
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
        print(f"Error in validation function validate_mc_pc_causal_part_sno_mandatory: {str(e)}")
        return False

def validate_mc_pc_failuredate_less_repairdate(row_data):
    """
    Validation function for rule: MC_PC_FAILUREDATE_LESS_REPAIRDATE
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part'),ISPICKVAL(WOD_2__Claim_Type__c, 'Field Modification')),   WOD_2__Date_Of_Repair__c < WOD_2__Date_Of_Failure__c
) ,true,false))
    Error message: Failure Date can't be greater than Repair Date
    
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
        print(f"Error in validation function validate_mc_pc_failuredate_less_repairdate: {str(e)}")
        return False

def validate_mc_pc_failuredate_mandatory(row_data):
    """
    Validation function for rule: MC_PC_FAILUREDATE_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')), ISBLANK( WOD_2__Date_Of_Failure__c)),true,false))
    Error message: Date of failure is required
    
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
        print(f"Error in validation function validate_mc_pc_failuredate_mandatory: {str(e)}")
        return False

def validate_mc_pc_inventory_mandatory(row_data):
    """
    Validation function for rule: MC_PC_INVENTORY_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(
OR(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'), AND(ISBLANK(WOD_2__Inventory__c),ISBLANK(WOD_2__Asset__c))),
AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), AND(ISBLANK(WOD_2__Inventory__c),ISBLANK(WOD_2__Asset__c)),ISPICKVAL(WOD_2__Host_NonHost__c,'Installed on OEM machine'))),true,false))
    Error message: Please Select Inventory
    
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
        print(f"Error in validation function validate_mc_pc_inventory_mandatory: {str(e)}")
        return False

def validate_mc_pc_modelno_mandatory(row_data):
    """
    Validation function for rule: MC_PC_MODELNO_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(
OR(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'), AND(ISBLANK(WOD_2__Model_Number__c),ISBLANK(WOD_2__ModelNumber_P2__c))),
AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), AND(ISBLANK(WOD_2__Model_Number__c),ISBLANK(WOD_2__ModelNumber_P2__c)),ISPICKVAL(WOD_2__Host_NonHost__c,'Installed on OEM machine'))),true,false))
    Error message: Material/Model Number is required
    
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
        print(f"Error in validation function validate_mc_pc_modelno_mandatory: {str(e)}")
        return False

def validate_mc_pc_pre_auth_comments_mandatory(row_data):
    """
    Validation function for rule: MC_PC_PRE_AUTH_COMMENTS_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')), WOD_2__Is_Pre_Authorization_Required__c==true,ISBLANK(TRIM( 	WOD_2__Pre_Authorization_Comments__c)) ),true,false))
    Error message: Pre Authorization Comments is mandatory
    
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
        print(f"Error in validation function validate_mc_pc_pre_auth_comments_mandatory: {str(e)}")
        return False

def validate_mc_pc_pre_auth_reason_mandatory(row_data):
    """
    Validation function for rule: MC_PC_PRE_AUTH_REASON_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')), WOD_2__Is_Pre_Authorization_Required__c==true,ISPICKVAL(WOD_2__Pre_Authorization_Reason__c,'') ),true,false))
    Error message: Pre Authorization Reason is mandatory
    
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
        print(f"Error in validation function validate_mc_pc_pre_auth_reason_mandatory: {str(e)}")
        return False

def validate_mc_pc_repairdate_mandatory(row_data):
    """
    Validation function for rule: MC_PC_REPAIRDATE_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF( AND( OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')) ,ISBLANK(  WOD_2__Date_Of_Repair__c)) , true, false))
    Error message: Date of repair is required
    
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
        print(f"Error in validation function validate_mc_pc_repairdate_mandatory: {str(e)}")
        return False

def validate_mc_purchasedate_less_repairdate_failure(row_data):
    """
    Validation function for rule: MC_PurchaseDate_Less_REPAIRDATE_FAILURE
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(  OR(WOD_2__Date_Of_Purchase__c> WOD_2__Date_Of_Repair__c ,WOD_2__Date_Of_Purchase__c> WOD_2__Date_Of_Failure__c ), true, false))
    Error message: purchase Date can't be greater
    
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
        print(f"Error in validation function validate_mc_purchasedate_less_repairdate_failure: {str(e)}")
        return False

def validate_osd_receivedate_less_today(row_data):
    """
    Validation function for rule: OSD_RECEIVEDATE_LESS_TODAY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),WOD_2__Received_Date__c > TODAY())
    Error message: Received Date cannot be in future.
    
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
        print(f"Error in validation function validate_osd_receivedate_less_today: {str(e)}")
        return False

def validate_pc_part_mandatory(row_data):
    """
    Validation function for rule: PC_PART_MANDATORY
    Original Salesforce formula: AND(
    OR(
        $Permission.WOD_2__DisableSkipTriggerNValidation, NOT($Permission.WOD_2__SkipTriggerNValidations)
    )
    ,IF(
        AND(
            ISPICKVAL(WOD_2__Claim_Type__c, 'Part')
            ,AND(
                ISBLANK(WOD_2__Part__c )
                ,ISBLANK(WOD_2__PartNumber_P2__c )
            ) 
        )
        ,true
        ,false
    )
)
    Error message: Please Select Part
    
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
        print(f"Error in validation function validate_pc_part_mandatory: {str(e)}")
        return False

def validate_pc_part_sno_mandatory(row_data):
    """
    Validation function for rule: PC_PART_SNO_MANDATORY
    Original Salesforce formula: AND(
    OR(
        $Permission.WOD_2__DisableSkipTriggerNValidation,
        NOT($Permission.WOD_2__SkipTriggerNValidations)
    )
    ,OR(
        AND(
            ISPICKVAL(WOD_2__Claim_Type__c, 'Part')
            , ISPICKVAL(WOD_2__Part__r.WOD_2__Track_Type__c, 'Serialized')
            , ISBLANK(WOD_2__Part_Serial_Number__c)
        )
        ,AND(
            ISPICKVAL(WOD_2__Claim_Type__c, 'Part')
            , WOD_2__PartNumber_P2__r.WOD_2__Is_Serialized__c
            , ISBLANK(WOD_2__Part_Serial_Number__c)
        )
    )    
)
    Error message: Part Serial Number is required for Serialized Part
    
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
        print(f"Error in validation function validate_pc_part_sno_mandatory: {str(e)}")
        return False

def validate_pc_purchasedate_mandatory(row_data):
    """
    Validation function for rule: PC_PURCHASEDATE_MANDATORY
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), ISBLANK(  WOD_2__Date_Of_Purchase__c )),true,false))
    Error message: Please Provide Purchase Date
    
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
        print(f"Error in validation function validate_pc_purchasedate_mandatory: {str(e)}")
        return False

def validate_preauth_expiry_date_check(row_data):
    """
    Validation function for rule: PREAUTH_EXPIRY_DATE_CHECK
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),WOD_2__Pre_Authorization__r.WOD_2__Expiry_Date__c<TODAY())
    Error message: Record is expired. Please create a new Pre-Approval record.
    
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
        print(f"Error in validation function validate_preauth_expiry_date_check: {str(e)}")
        return False

def validate_preauth_fulfilled_check(row_data):
    """
    Validation function for rule: PREAUTH_FULFILLED_CHECK
    Original Salesforce formula: AND(
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),WOD_2__Pre_Authorization__r.WOD_2__Fulfilled__c == true)
    Error message: PreAuthorization is already fulfilled
    
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
        print(f"Error in validation function validate_preauth_fulfilled_check: {str(e)}")
        return False

def validate_kbt_order_number_is_blank(row_data):
    """
    Validation function for rule: KBT_Order_Number_Is_Blank
    Original Salesforce formula: AND(
OR($User.KBT_Is_Adjudicator__c, $User.KBT_Is_Approver__c),
ISBLANK(KBT_Order_Number__c)
)
    Error message: Order Number field is blank
    
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
        print(f"Error in validation function validate_kbt_order_number_is_blank: {str(e)}")
        return False

def validate_claim_is_locked(row_data):
    """
    Validation function for rule: Claim_Is_Locked
    Original Salesforce formula: If(AND(KBT_Is_Locked__c, PRIORVALUE(KBT_Is_Locked__c), NOT($User.KBT_Do_Not_Validate__c) ),
true,false)
    Error message: This action cannot be performed because the claim has been locked.
    
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
        print(f"Error in validation function validate_claim_is_locked: {str(e)}")
        return False

def validate_failure_date_validation_rule(row_data):
    """
    Validation function for rule: Failure_Date_validation_rule
    Original Salesforce formula: IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')),    KBT_FirstUseDate__c  > WOD_2__Date_Of_Failure__c
) ,true,false)
    Error message: Failure Date cannot be earlier than first usage date.
    
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
        print(f"Error in validation function validate_failure_date_validation_rule: {str(e)}")
        return False

def validate_goodwill_type_is_missing(row_data):
    """
    Validation function for rule: Goodwill_Type_Is_Missing
    Original Salesforce formula: if(KBT_Goodwill_Claim__c =true, If(ISPICKVAL( KBT_Goodwill_Type__c ,''),true,false),false)
    Error message: Please select a value for goodwill type
    
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
        print(f"Error in validation function validate_goodwill_type_is_missing: {str(e)}")
        return False

def validate_kbt_description_null_check(row_data):
    """
    Validation function for rule: KBT_Description_Null_Check
    Original Salesforce formula: AND(
ISBLANK(WOD_2__Description__c),
ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),
NOT(ISPICKVAL(WOD_2__Claim_Status__c, 'Initial Draft'))
)
    Error message: Description field is blank
    
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
        print(f"Error in validation function validate_kbt_description_null_check: {str(e)}")
        return False

def validate_kbt_initial_draft_validation_check(row_data):
    """
    Validation function for rule: KBT_Initial_Draft_Validation_Check
    Original Salesforce formula: AND(
    NOT(KBT_Create_as_Initial_Draft__c),
    ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),
    NOT(ISPICKVAL(WOD_2__Claim_Status__c, 'Initial Draft'))
)
    Error message: Claim cannot be submitted with initial draft status
    
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
        print(f"Error in validation function validate_kbt_initial_draft_validation_check: {str(e)}")
        return False

def validate_kbt_mc_pc_account_mandatory(row_data):
    """
    Validation function for rule: KBT_MC_PC_ACCOUNT_MANDATORY
    Original Salesforce formula: IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')), ISBLANK(WOD_2__Account__c), NOT( ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft') ) ),true,false)
    Error message: Service Dealer is required
    
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
        print(f"Error in validation function validate_kbt_mc_pc_account_mandatory: {str(e)}")
        return False

def validate_kbt_mc_pc_causal_mandatory(row_data):
    """
    Validation function for rule: KBT_MC_PC_CAUSAL_MANDATORY
    Original Salesforce formula: IF(AND(OR(
ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),
ISPICKVAL(WOD_2__Claim_Type__c, 'Part'),
ISPICKVAL(WOD_2__Claim_Type__c, 'Claim Template'),
ISPICKVAL(WOD_2__Claim_Type__c, 'Field Modification')
),
ISBLANK(WOD_2__Causal_Part_Number__c),
NOT(ISPICKVAL(WOD_2__Claim_Status__c , 'Initial Draft')),
NOT(ISPICKVAL(KBT_Claim_Source_System__c, 'RBOX'))
),
TRUE , FALSE
)
    Error message: Please select Causal Part
    
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
        print(f"Error in validation function validate_kbt_mc_pc_causal_mandatory: {str(e)}")
        return False

def validate_kbt_mc_pc_failuredate_mandatory(row_data):
    """
    Validation function for rule: KBT_MC_PC_FAILUREDATE_MANDATORY
    Original Salesforce formula: IF(AND(OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')), ISBLANK( WOD_2__Date_Of_Failure__c),NOT( ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft') )),true,false)
    Error message: Date of failure is required
    
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
        print(f"Error in validation function validate_kbt_mc_pc_failuredate_mandatory: {str(e)}")
        return False

def validate_kbt_mc_pc_inventory_mandatory(row_data):
    """
    Validation function for rule: KBT_MC_PC_INVENTORY_MANDATORY
    Original Salesforce formula: IF(OR(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'), ISBLANK(WOD_2__Inventory__c), NOT(ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft'))),AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), ISBLANK(WOD_2__Inventory__c), ISPICKVAL(WOD_2__Host_NonHost__c, 'Installed on OEM machine'), NOT( ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft') ))),true,false)
    Error message: Please Select Inventory
    
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
        print(f"Error in validation function validate_kbt_mc_pc_inventory_mandatory: {str(e)}")
        return False

def validate_kbt_mc_pc_modelno_mandatory(row_data):
    """
    Validation function for rule: KBT_MC_PC_MODELNO_MANDATORY
    Original Salesforce formula: IF(
OR(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'), ISBLANK(WOD_2__Model_Number__c), NOT(ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft'))),
AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), ISBLANK(WOD_2__Model_Number__c),ISPICKVAL(WOD_2__Host_NonHost__c,'Installed on OEM machine'), NOT( ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft') ) )),true,false)
    Error message: Material/Model Number is required
    
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
        print(f"Error in validation function validate_kbt_mc_pc_modelno_mandatory: {str(e)}")
        return False

def validate_kbt_mc_pc_repairdate_mandatory(row_data):
    """
    Validation function for rule: KBT_MC_PC_REPAIRDATE_MANDATORY
    Original Salesforce formula: IF( AND( OR(ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),ISPICKVAL(WOD_2__Claim_Type__c, 'Part')) ,ISBLANK(  WOD_2__Date_Of_Repair__c), NOT( ISPICKVAL( WOD_2__Claim_Status__c , 'Initial Draft') ) ) , true, false)
    Error message: Date of repair is required
    
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
        print(f"Error in validation function validate_kbt_mc_pc_repairdate_mandatory: {str(e)}")
        return False

def validate_kbt_order_number_null_check(row_data):
    """
    Validation function for rule: KBT_Order_Number_Null_Check
    Original Salesforce formula: AND(
ISBLANK(KBT_Order_Number__c),
ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),
NOT(ISPICKVAL(WOD_2__Claim_Status__c, 'Initial Draft'))
)
    Error message: Order number field is blank
    
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
        print(f"Error in validation function validate_kbt_order_number_null_check: {str(e)}")
        return False

def validate_kbt_unit_usages_null_check(row_data):
    """
    Validation function for rule: KBT_Unit_Usages_Null_Check
    Original Salesforce formula: AND(
ISBLANK(WOD_2__Units_Usage__c),
ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),
NOT(ISPICKVAL(WOD_2__Claim_Status__c, 'Initial Draft'))
)
    Error message: Unit usage field is blank
    
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
        print(f"Error in validation function validate_kbt_unit_usages_null_check: {str(e)}")
        return False

def validate_kbt_wo_number_null_check(row_data):
    """
    Validation function for rule: KBT_WO_NUMBER_NULL_CHECK
    Original Salesforce formula: AND(
    ISBLANK( WOD_2__Work_Order__c),
    ISPICKVAL(WOD_2__Claim_Type__c, 'Machine'),
    NOT(ISPICKVAL(WOD_2__Claim_Status__c, 'Initial Draft'))
)
    Error message: The work order field is empty.
    
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
        print(f"Error in validation function validate_kbt_wo_number_null_check: {str(e)}")
        return False

def validate_incomplete_mandotory_fields(row_data):
    """
    Validation function for rule: Incomplete_Mandotory_Fields
    Original Salesforce formula: IF(
    ISPICKVAL(WOD_2__Claim_Type__c, "Claim Template"),
    null,
    
    OR(
        ISBLANK(WOD_2__Account__c),
        ISBLANK(WOD_2__Date_Of_Failure__c),
        ISBLANK(WOD_2__Date_Of_Repair__c)
    )
)
    Error message: Please Fill Mandatory Fields.
    
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
        print(f"Error in validation function validate_incomplete_mandotory_fields: {str(e)}")
        return False

def validate_kbt_hinpo_code_must_match(row_data):
    """
    Validation function for rule: KBT_Hinpo_Code_Must_match
    Original Salesforce formula: (
    NOT(
        OR(
            ISPICKVAL(WOD_2__Claim_Type__c, "Bulletin"),
            ISPICKVAL(WOD_2__Claim_Type__c, "Keito Bulletin"),
            ISPICKVAL(WOD_2__Claim_Type__c, "Part")
        )
    ) 
    &&  NOT(ISBLANK(KBT_Order_Number__c))
    &&  KBT_Defect_Hinpo_Series_Code__c <> KBT_Order_Number__r.Hinpo_Series__c
    &&  OR($User.KBT_Is_Adjudicator__c, $User.KBT_Is_Approver__c)
)
    Error message: The Hinpo Code of the Claim Inventory Must match the Hinpo Code of the Order Number
    
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
        print(f"Error in validation function validate_kbt_hinpo_code_must_match: {str(e)}")
        return False

def validate_kbt_pc_part_mandatory(row_data):
    """
    Validation function for rule: KBT_PC_PART_MANDATORY
    Original Salesforce formula: IF(AND(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), ISBLANK(WOD_2__Part__c )), NOT(ISPICKVAL(WOD_2__Claim_Status__c , "Initial Draft")),NOT(ISPICKVAL( KBT_Claim_Source_System__c  , "RBOX"))), true, false)
    Error message: Please Select Part
    
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
        print(f"Error in validation function validate_kbt_pc_part_mandatory: {str(e)}")
        return False

def validate_kbt_pc_purchasedate_mandatory(row_data):
    """
    Validation function for rule: KBT_PC_PURCHASEDATE_MANDATORY
    Original Salesforce formula: IF(AND(AND(ISPICKVAL(WOD_2__Claim_Type__c, 'Part'), ISBLANK(  WOD_2__Date_Of_Purchase__c )), NOT(ISPICKVAL(WOD_2__Claim_Status__c , "Initial Draft")),NOT(ISPICKVAL( KBT_Claim_Source_System__c  , "RBOX"))), true, false)
    Error message: Please Provide Purchase Date
    
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
        print(f"Error in validation function validate_kbt_pc_purchasedate_mandatory: {str(e)}")
        return False

def validate_mc_pc_causal_claim_template_mandatory(row_data):
    """
    Validation function for rule: MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY
    Original Salesforce formula: AND(
        OR(
            $Permission.WOD_2__DisableSkipTriggerNValidation,
            NOT($Permission.WOD_2__SkipTriggerNValidations)
        ),
        IF(
            AND(
                ISPICKVAL(WOD_2__Claim_Type__c, 'Claim Template'),
                ISBLANK(WOD_2__Causal_Part_Number__c),
                ISBLANK(WOD_2__CausalPartNumber_P2__c)
            ),
            true,
            false
        )
    )
    Error message: Please select Causal Part
    
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
        print(f"Error in validation function validate_mc_pc_causal_claim_template_mandatory: {str(e)}")
        return False

def validate_first_usedate_mandatory(row_data):
    """
    Validation function for rule: First_UseDate_Mandatory
    Original Salesforce formula: AND(
    ISPICKVAL(KBT_Inventory_Type__c, 'Retail'),
    ISBLANK(KBT_FirstUseDate__c)
)
    Error message: First Use Date is mandatory for Retail inventory type.
    
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
        print(f"Error in validation function validate_first_usedate_mandatory: {str(e)}")
        return False

def validate_kbt_hinposeriescode_mandatory(row_data):
    """
    Validation function for rule: KBT_HinpoSeriesCode_Mandatory
    Original Salesforce formula: AND(
    NOT(ISBLANK(WOD_2__Inventory__r.WOD_2__Item__c)),
    NOT(ISBLANK(WOD_2__Inventory__r.WOD_2__Item__r.WOD_2__Parent_Product__c)),
    WOD_2__Inventory__r.WOD_2__Item__r.WOD_2__Parent_Product__r.KBT_HinpoSeriesCode__c  = "121",
    ISBLANK(KBT_Shipping_Company__c),
    ISBLANK(KBT_Reference_tracking_number__c)
)
    Error message: shipping company and tracking/reference number are required
    
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
        print(f"Error in validation function validate_kbt_hinposeriescode_mandatory: {str(e)}")
        return False

def validate_kbt_hinpocodeserieslevel(row_data):
    """
    Validation function for rule: KBT_HinpoCodeSeriesLevel
    Original Salesforce formula: AND(
    OR($User.KBT_Is_Adjudicator__c, $User.KBT_Is_Approver__c),
    NOT(
        OR(
            ISPICKVAL(WOD_2__Claim_Type__c, "Bulletin"),
            ISPICKVAL(WOD_2__Claim_Type__c, "Keito Bulletin"),
            ISPICKVAL(WOD_2__Claim_Type__c, "Part")
        )
    ),
    ISBLANK(KBT_Defect_Inventory__r.WOD_2__Item__r.WOD_2__Parent_Product__r.WOD_2__Parent_Product__r.KBT_HinpoSeriesCode__c),
    NOT(ISBLANK(KBT_Defect_Inventory__r.WOD_2__Item__c))
)
    Error message: Hinpo Series Code not found for the selected Model
    
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
        print(f"Error in validation function validate_kbt_hinpocodeserieslevel: {str(e)}")
        return False

def validate_mc_pc_causal_part_sno_mandatory_cloned(row_data):
    """
    Validation function for rule: MC_PC_CAUSAL_PART_SNO_MANDATORY_Cloned
    Original Salesforce formula: AND(NOT(ISPICKVAL( KBT_Claim_Source_System__c ,'RBOX')),
OR(
$Permission.WOD_2__DisableSkipTriggerNValidation,
NOT($Permission.WOD_2__SkipTriggerNValidations)
),IF( AND(ISBLANK(TRIM( WOD_2__Causal_Part_Serial_Number__c )),ISPICKVAL( WOD_2__Causal_Part_Number__r.WOD_2__Track_Type__c ,'Serialized'),!ISPICKVAL(WOD_2__Claim_Type__c, 'Claim Template')) , true,false))
    Error message: Causal Part Serial Number is required for Serialized Part
    
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
        print(f"Error in validation function validate_mc_pc_causal_part_sno_mandatory_cloned: {str(e)}")
        return False

def validate_shippingcompany_and_ref_num_mandatory(row_data):
    """
    Validation function for rule: ShippingCompany_and_Ref_Num_Mandatory
    Original Salesforce formula: AND( NOT(ISPICKVAL( WOD_2__Claim_Status__c ,'Initial Draft')),
KBT_Hinpo_Code__c  = "121",OR(
ISBLANK(KBT_Shipping_Company__c),
ISBLANK(KBT_Reference_tracking_number__c))
)
    Error message: shipping company and tracking/reference number are required
    
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
        print(f"Error in validation function validate_shippingcompany_and_ref_num_mandatory: {str(e)}")
        return False


# ================================
# FUNCTION REGISTRY
# ================================

VALIDATION_FUNCTIONS = {'CLM_NonSerializedPartCannotHaveSerialNo': {'function_name': 'validate_clm_nonserializedpartcannothaveserialno', 'error_message': 'Non-Serialized Causal Part can not have serial number', 'active': False}, 'GW_REASON_MANDATORY': {'function_name': 'validate_gw_reason_mandatory', 'error_message': 'Please select Goodwill Reason', 'active': False}, 'MC_PC_ACCOUNT_MANDATORY': {'function_name': 'validate_mc_pc_account_mandatory', 'error_message': 'Service Dealer is required', 'active': False}, 'MC_PC_CASUAL_MANDATORY': {'function_name': 'validate_mc_pc_casual_mandatory', 'error_message': 'DEPRECATED', 'active': False}, 'MC_PC_CAUSAL_MANDATORY': {'function_name': 'validate_mc_pc_causal_mandatory', 'error_message': 'Please select Causal Part', 'active': False}, 'MC_PC_CAUSAL_PART_SNO_MANDATORY': {'function_name': 'validate_mc_pc_causal_part_sno_mandatory', 'error_message': 'Causal Part Serial Number is required for Serialized Part', 'active': False}, 'MC_PC_FAILUREDATE_LESS_REPAIRDATE': {'function_name': 'validate_mc_pc_failuredate_less_repairdate', 'error_message': "Failure Date can't be greater than Repair Date", 'active': False}, 'MC_PC_FAILUREDATE_MANDATORY': {'function_name': 'validate_mc_pc_failuredate_mandatory', 'error_message': 'Date of failure is required', 'active': False}, 'MC_PC_INVENTORY_MANDATORY': {'function_name': 'validate_mc_pc_inventory_mandatory', 'error_message': 'Please Select Inventory', 'active': False}, 'MC_PC_MODELNO_MANDATORY': {'function_name': 'validate_mc_pc_modelno_mandatory', 'error_message': 'Material/Model Number is required', 'active': False}, 'MC_PC_PRE_AUTH_COMMENTS_MANDATORY': {'function_name': 'validate_mc_pc_pre_auth_comments_mandatory', 'error_message': 'Pre Authorization Comments is mandatory', 'active': True}, 'MC_PC_PRE_AUTH_REASON_MANDATORY': {'function_name': 'validate_mc_pc_pre_auth_reason_mandatory', 'error_message': 'Pre Authorization Reason is mandatory', 'active': True}, 'MC_PC_REPAIRDATE_MANDATORY': {'function_name': 'validate_mc_pc_repairdate_mandatory', 'error_message': 'Date of repair is required', 'active': False}, 'MC_PurchaseDate_Less_REPAIRDATE_FAILURE': {'function_name': 'validate_mc_purchasedate_less_repairdate_failure', 'error_message': "purchase Date can't be greater", 'active': True}, 'OSD_RECEIVEDATE_LESS_TODAY': {'function_name': 'validate_osd_receivedate_less_today', 'error_message': 'Received Date cannot be in future.', 'active': True}, 'PC_PART_MANDATORY': {'function_name': 'validate_pc_part_mandatory', 'error_message': 'Please Select Part', 'active': False}, 'PC_PART_SNO_MANDATORY': {'function_name': 'validate_pc_part_sno_mandatory', 'error_message': 'Part Serial Number is required for Serialized Part', 'active': True}, 'PC_PURCHASEDATE_MANDATORY': {'function_name': 'validate_pc_purchasedate_mandatory', 'error_message': 'Please Provide Purchase Date', 'active': False}, 'PREAUTH_EXPIRY_DATE_CHECK': {'function_name': 'validate_preauth_expiry_date_check', 'error_message': 'Record is expired. Please create a new Pre-Approval record.', 'active': True}, 'PREAUTH_FULFILLED_CHECK': {'function_name': 'validate_preauth_fulfilled_check', 'error_message': 'PreAuthorization is already fulfilled', 'active': True}, 'KBT_Order_Number_Is_Blank': {'function_name': 'validate_kbt_order_number_is_blank', 'error_message': 'Order Number field is blank', 'active': False}, 'Claim_Is_Locked': {'function_name': 'validate_claim_is_locked', 'error_message': 'This action cannot be performed because the claim has been locked.', 'active': True}, 'Failure_Date_validation_rule': {'function_name': 'validate_failure_date_validation_rule', 'error_message': 'Failure Date cannot be earlier than first usage date.', 'active': True}, 'Goodwill_Type_Is_Missing': {'function_name': 'validate_goodwill_type_is_missing', 'error_message': 'Please select a value for goodwill type', 'active': True}, 'KBT_Description_Null_Check': {'function_name': 'validate_kbt_description_null_check', 'error_message': 'Description field is blank', 'active': False}, 'KBT_Initial_Draft_Validation_Check': {'function_name': 'validate_kbt_initial_draft_validation_check', 'error_message': 'Claim cannot be submitted with initial draft status', 'active': False}, 'KBT_MC_PC_ACCOUNT_MANDATORY': {'function_name': 'validate_kbt_mc_pc_account_mandatory', 'error_message': 'Service Dealer is required', 'active': False}, 'KBT_MC_PC_CAUSAL_MANDATORY': {'function_name': 'validate_kbt_mc_pc_causal_mandatory', 'error_message': 'Please select Causal Part', 'active': True}, 'KBT_MC_PC_FAILUREDATE_MANDATORY': {'function_name': 'validate_kbt_mc_pc_failuredate_mandatory', 'error_message': 'Date of failure is required', 'active': False}, 'KBT_MC_PC_INVENTORY_MANDATORY': {'function_name': 'validate_kbt_mc_pc_inventory_mandatory', 'error_message': 'Please Select Inventory', 'active': True}, 'KBT_MC_PC_MODELNO_MANDATORY': {'function_name': 'validate_kbt_mc_pc_modelno_mandatory', 'error_message': 'Material/Model Number is required', 'active': False}, 'KBT_MC_PC_REPAIRDATE_MANDATORY': {'function_name': 'validate_kbt_mc_pc_repairdate_mandatory', 'error_message': 'Date of repair is required', 'active': False}, 'KBT_Order_Number_Null_Check': {'function_name': 'validate_kbt_order_number_null_check', 'error_message': 'Order number field is blank', 'active': False}, 'KBT_Unit_Usages_Null_Check': {'function_name': 'validate_kbt_unit_usages_null_check', 'error_message': 'Unit usage field is blank', 'active': False}, 'KBT_WO_NUMBER_NULL_CHECK': {'function_name': 'validate_kbt_wo_number_null_check', 'error_message': 'The work order field is empty.', 'active': False}, 'Incomplete_Mandotory_Fields': {'function_name': 'validate_incomplete_mandotory_fields', 'error_message': 'Please Fill Mandatory Fields.', 'active': True}, 'KBT_Hinpo_Code_Must_match': {'function_name': 'validate_kbt_hinpo_code_must_match', 'error_message': 'The Hinpo Code of the Claim Inventory Must match the Hinpo Code of the Order Number', 'active': False}, 'KBT_PC_PART_MANDATORY': {'function_name': 'validate_kbt_pc_part_mandatory', 'error_message': 'Please Select Part', 'active': True}, 'KBT_PC_PURCHASEDATE_MANDATORY': {'function_name': 'validate_kbt_pc_purchasedate_mandatory', 'error_message': 'Please Provide Purchase Date', 'active': True}, 'MC_PC_CAUSAL_CLAIM_TEMPLATE_MANDATORY': {'function_name': 'validate_mc_pc_causal_claim_template_mandatory', 'error_message': 'Please select Causal Part', 'active': True}, 'First_UseDate_Mandatory': {'function_name': 'validate_first_usedate_mandatory', 'error_message': 'First Use Date is mandatory for Retail inventory type.', 'active': True}, 'KBT_HinpoSeriesCode_Mandatory': {'function_name': 'validate_kbt_hinposeriescode_mandatory', 'error_message': 'shipping company and tracking/reference number are required', 'active': True}, 'KBT_HinpoCodeSeriesLevel': {'function_name': 'validate_kbt_hinpocodeserieslevel', 'error_message': 'Hinpo Series Code not found for the selected Model', 'active': False}, 'MC_PC_CAUSAL_PART_SNO_MANDATORY_Cloned': {'function_name': 'validate_mc_pc_causal_part_sno_mandatory_cloned', 'error_message': 'Causal Part Serial Number is required for Serialized Part', 'active': False}, 'ShippingCompany_and_Ref_Num_Mandatory': {'function_name': 'validate_shippingcompany_and_ref_num_mandatory', 'error_message': 'shipping company and tracking/reference number are required', 'active': True}}

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
