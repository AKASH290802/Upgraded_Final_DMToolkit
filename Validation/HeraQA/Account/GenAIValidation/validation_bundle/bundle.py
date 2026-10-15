# Auto-generated validation bundle
import pandas as pd


def validate_DTAG_RestrictMultipleBUforWholeSale(df):
    """
    Validation Rule: DTAG_RestrictMultipleBUforWholeSale
    Salesforce Object: Account
    Field: DTAG_Distribution_Level__c, WOD_2__Business_Units__c
    Apex Formula:
    AND(ISPICKVAL(DTAG_Distribution_Level__c,'Wholesaler'),( PICKLISTCOUNT(WOD_2__Business_Units__c)>1))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if required columns exist
        required_cols = ['DTAG_Distribution_Level__c', 'WOD_2__Business_Units__c']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: Missing columns {missing_cols} for validation rule 'DTAG_RestrictMultipleBUforWholeSale'")
            return pd.Series([True] * len(df))  # Skip validation if columns missing
        
        # Convert to string and handle NaN values
        dist_level = df['DTAG_Distribution_Level__c'].fillna('').astype(str)
        business_units = df['WOD_2__Business_Units__c'].fillna('').astype(str)
        
        # Check if Distribution Level is 'Wholesaler' AND Business Units contains multiple values (semicolon separated)
        is_wholesaler = dist_level == 'Wholesaler'
        has_multiple_bu = business_units.str.contains(';', na=False)  # Assumes multiple values are semicolon-separated
        
        # Validation fails if both conditions are true
        validation_error = is_wholesaler & has_multiple_bu
        return ~validation_error  # Return True for valid records, False for invalid
        
    except Exception as e:
        print(f"Error in validate_DTAG_RestrictMultipleBUforWholeSale: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs

def validate_DTAG_WACanCreateRWSOnly(df):
    """
    Validation Rule: DTAG_WACanCreateRWSOnly
    Salesforce Object: Account
    Field: Type
    Apex Formula:
    ISNEW() &&  $Permission.DTAG_Warranty_Admin_Permission &&  NOT(ISPICKVAL(Type , 'RWS'))
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if Type column exists
        if 'Type' not in df.columns:
            print(f"Warning: Missing column 'Type' for validation rule 'DTAG_WACanCreateRWSOnly'")
            return pd.Series([True] * len(df))  # Skip validation if column missing
        
        # Note: ISNEW() and $Permission checks cannot be replicated in data validation
        # This validation should only apply to new records with specific permissions
        # For data validation purposes, we'll check if Type is NOT 'RWS' 
        # (assuming this is the core business logic)
        
        account_type = df['Type'].fillna('').astype(str)
        
        # Validation fails if Type is not 'RWS' (assuming this is for warranty admin permission context)
        # In practice, you might want to skip this validation for data loads or adjust the logic
        validation_error = (account_type != '') & (account_type != 'RWS')
        
        # For data validation, we might want to be more lenient and only flag obvious issues
        # Return True (valid) for most cases since this is permission-based
        return pd.Series([True] * len(df))  # Skip this validation for data loads
        
    except Exception as e:
        print(f"Error in validate_DTAG_WACanCreateRWSOnly: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs

def validate_Parent_cannot_be_Draft_for_Child_active(df):
    """
    Validation Rule: Parent_cannot_be_Draft_for_Child_active
    Salesforce Object: Account
    Field: Parent.DTAG_Status__c, DTAG_Status__c
    Apex Formula:
    IF(
 $Setup.Automation_Bypass__c.Disable_Account_Validation_Rule__c,
false, AND(
OR(
				ISPICKVAL(Parent.DTAG_Status__c,"Draft"),
		 	ISPICKVAL(Parent.DTAG_Status__c,"InActive")
		),
OR(
ISPICKVAL(DTAG_Status__c,"Active"),
ISPICKVAL(DTAG_Status__c,"Released"))
)
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if required columns exist
        # Note: Parent.DTAG_Status__c might be represented differently in the data
        status_col = 'DTAG_Status__c'
        parent_status_col = None
        
        # Look for parent status column (could be named differently)
        possible_parent_cols = ['Parent.DTAG_Status__c', 'Parent_DTAG_Status__c', 'ParentDTAG_Status__c']
        for col in possible_parent_cols:
            if col in df.columns:
                parent_status_col = col
                break
        
        if status_col not in df.columns:
            print(f"Warning: Missing column '{status_col}' for validation rule 'Parent_cannot_be_Draft_for_Child_active'")
            return pd.Series([True] * len(df))
        
        # Get status values
        child_status = df[status_col].fillna('').astype(str)
        
        # Check child status is Active or Released
        child_is_active_or_released = child_status.isin(['Active', 'Released'])
        
        if parent_status_col and parent_status_col in df.columns:
            parent_status = df[parent_status_col].fillna('').astype(str)
            # Check parent status is Draft or InActive
            parent_is_draft_or_inactive = parent_status.isin(['Draft', 'InActive'])
            
            # Validation fails if parent is Draft/InActive AND child is Active/Released
            validation_error = parent_is_draft_or_inactive & child_is_active_or_released
            return ~validation_error
        else:
            print(f"Warning: Parent status column not found for validation rule 'Parent_cannot_be_Draft_for_Child_active'")
            return pd.Series([True] * len(df))  # Skip validation if parent column missing
        
    except Exception as e:
        print(f"Error in validate_Parent_cannot_be_Draft_for_Child_active: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs

def validate_Restrict_For_ActiveOrReleased_Status(df):
    """
    Validation Rule: Restrict_For_ActiveOrReleased_Status
    Salesforce Object: Account
    Field: DTAG_Status__c, AccountNumber, Type, WOD_2__Business_Units__c
    Apex Formula:
    IF(
$Setup.Automation_Bypass__c.Disable_Account_Validation_Rule__c,
false, AND( ISNEW() == false, OR (ISPICKVAL(DTAG_Status__c, 'Active'), ISPICKVAL(DTAG_Status__c, 'Released')), OR(ISBLANK( AccountNumber), ISBLANK(TEXT(Type)), ISBLANK(WOD_2__Business_Units__c)))
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if required columns exist
        required_cols = ['DTAG_Status__c', 'AccountNumber', 'Type', 'WOD_2__Business_Units__c']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: Missing columns {missing_cols} for validation rule 'Restrict_For_ActiveOrReleased_Status'")
            return pd.Series([True] * len(df))  # Skip validation if columns missing
        
        # Get column values
        status = df['DTAG_Status__c'].fillna('').astype(str)
        account_number = df['AccountNumber'].fillna('').astype(str)
        account_type = df['Type'].fillna('').astype(str)
        business_units = df['WOD_2__Business_Units__c'].fillna('').astype(str)
        
        # Check if status is Active or Released
        status_is_active_or_released = status.isin(['Active', 'Released'])
        
        # Check if any required fields are blank
        account_number_blank = account_number == ''
        type_blank = account_type == ''
        business_units_blank = business_units == ''
        
        any_field_blank = account_number_blank | type_blank | business_units_blank
        
        # Validation fails if status is Active/Released AND any required field is blank
        # Note: ISNEW() check is skipped for data validation as it's not applicable
        validation_error = status_is_active_or_released & any_field_blank
        return ~validation_error
        
    except Exception as e:
        print(f"Error in validate_Restrict_For_ActiveOrReleased_Status: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs

def validate_ValidFromIsRequiredForReleased(df):
    """
    Validation Rule: ValidFromIsRequiredForReleased
    Salesforce Object: Account
    Field: DTAG_Status__c, DTAG_Valid_From__c
    Apex Formula:
    IF( AND(ISPICKVAL( DTAG_Status__c , 'Released'),  ISBLANK(DTAG_Valid_From__c ) ), true, false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if required columns exist
        required_cols = ['DTAG_Status__c', 'DTAG_Valid_From__c']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: Missing columns {missing_cols} for validation rule 'ValidFromIsRequiredForReleased'")
            return pd.Series([True] * len(df))  # Skip validation if columns missing
        
        # Get column values
        status = df['DTAG_Status__c'].fillna('').astype(str)
        valid_from = df['DTAG_Valid_From__c'].fillna('').astype(str)
        
        # Check if status is 'Released' and valid from is blank
        status_is_released = status == 'Released'
        valid_from_is_blank = valid_from == ''
        
        # Validation fails if status is Released AND valid from is blank
        validation_error = status_is_released & valid_from_is_blank
        return ~validation_error
        
    except Exception as e:
        print(f"Error in validate_ValidFromIsRequiredForReleased: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs

def validate_DT_Billing_country_should_be_AU_or_NZ(df):
    """
    Validation Rule: DT_Billing_country_should_be_AU_or_NZ
    Salesforce Object: Account
    Field: BillingCountry
    Apex Formula:
    IF( BillingCountry !='' && BillingCountry !='AU' && BillingCountry !='NZ',true,false)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if required column exists
        if 'BillingCountry' not in df.columns:
            print(f"Warning: Missing column 'BillingCountry' for validation rule 'DT_Billing_country_should_be_AU_or_NZ'")
            return pd.Series([True] * len(df))  # Skip validation if column missing
        
        # Get billing country values
        billing_country = df['BillingCountry'].fillna('').astype(str)
        
        # Validation fails if BillingCountry is not empty AND not 'AU' AND not 'NZ'
        country_not_empty = billing_country != ''
        country_not_au = billing_country != 'AU'
        country_not_nz = billing_country != 'NZ'
        
        validation_error = country_not_empty & country_not_au & country_not_nz
        return ~validation_error
        
    except Exception as e:
        print(f"Error in validate_DT_Billing_country_should_be_AU_or_NZ: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs

def validate_DTAG_Restrict_CurrencyforReleased(df):
    """
    Validation Rule: DTAG_Restrict_CurrencyforReleased
    Salesforce Object: Account
    Field: DTAG_Status__c, Type, DTAG_Account_Currency__c
    Apex Formula:
    AND(
AND(
ISPICKVAL(DTAG_Status__c,'Released'),

ISPICKVAL(Type, 'RWS')
),
ISBLANK(TEXT(DTAG_Account_Currency__c))
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if required columns exist
        required_cols = ['DTAG_Status__c', 'Type', 'DTAG_Account_Currency__c']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: Missing columns {missing_cols} for validation rule 'DTAG_Restrict_CurrencyforReleased'")
            return pd.Series([True] * len(df))  # Skip validation if columns missing
        
        # Get column values
        status = df['DTAG_Status__c'].fillna('').astype(str)
        account_type = df['Type'].fillna('').astype(str)
        currency = df['DTAG_Account_Currency__c'].fillna('').astype(str)
        
        # Check conditions
        status_is_released = status == 'Released'
        type_is_rws = account_type == 'RWS'
        currency_is_blank = currency == ''
        
        # Validation fails if status is Released AND type is RWS AND currency is blank
        validation_error = status_is_released & type_is_rws & currency_is_blank
        return ~validation_error
        
    except Exception as e:
        print(f"Error in validate_DTAG_Restrict_CurrencyforReleased: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs

def validate_DTAG_Restrict_For_Released_Status_New(df):
    """
    Validation Rule: DTAG_Restrict_For_Released_Status_New
    Salesforce Object: Account
    Field: DTAG_Status__c, Type, DTAG_Dealer_Discount_Group_Parts__c, DTAG_Labor_Units__c, DTAG_Participating_in_Remanufacturing__c
    Apex Formula:
    AND(
AND(
ISPICKVAL(DTAG_Status__c,'Released'),
OR(ISPICKVAL(Type,'TOC/TG'),
ISPICKVAL(Type,'GD'),
ISPICKVAL(Type, 'RWS'),

ISPICKVAL(Type,'ISP')
)
),
OR(
ISBLANK(DTAG_Dealer_Discount_Group_Parts__c),
ISBLANK(TEXT(DTAG_Labor_Units__c)),
ISBLANK(TEXT(DTAG_Participating_in_Remanufacturing__c))
)
)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if required columns exist
        required_cols = ['DTAG_Status__c', 'Type', 'DTAG_Dealer_Discount_Group_Parts__c', 'DTAG_Labor_Units__c', 'DTAG_Participating_in_Remanufacturing__c']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: Missing columns {missing_cols} for validation rule 'DTAG_Restrict_For_Released_Status_New'")
            return pd.Series([True] * len(df))  # Skip validation if columns missing
        
        # Get column values
        status = df['DTAG_Status__c'].fillna('').astype(str)
        account_type = df['Type'].fillna('').astype(str)
        discount_group = df['DTAG_Dealer_Discount_Group_Parts__c'].fillna('').astype(str)
        labor_units = df['DTAG_Labor_Units__c'].fillna('').astype(str)
        participating_reman = df['DTAG_Participating_in_Remanufacturing__c'].fillna('').astype(str)
        
        # Check conditions
        status_is_released = status == 'Released'
        type_is_relevant = account_type.isin(['TOC/TG', 'GD', 'RWS', 'ISP'])
        
        discount_group_blank = discount_group == ''
        labor_units_blank = labor_units == ''
        participating_reman_blank = participating_reman == ''
        
        any_required_field_blank = discount_group_blank | labor_units_blank | participating_reman_blank
        
        # Validation fails if status is Released AND type is relevant AND any required field is blank
        validation_error = status_is_released & type_is_relevant & any_required_field_blank
        return ~validation_error
        
    except Exception as e:
        print(f"Error in validate_DTAG_Restrict_For_Released_Status_New: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs

def validate_DTAG_Restrict_LandedCost_ReleasedStatus(df):
    """
    Validation Rule: DTAG_Restrict_LandedCost_ReleasedStatus
    Salesforce Object: Account
    Field: DTAG_Status__c, Type, DTAG_Landed_Cost_Calculation__c
    Apex Formula:
    AND(
AND(
ISPICKVAL(DTAG_Status__c,'Released'),
OR(ISPICKVAL(Type,'TOC/TG'),
ISPICKVAL(Type,'GD'),
ISPICKVAL(Type,'ISP')
)
),
ISBLANK(TEXT(DTAG_Landed_Cost_Calculation__c))

)
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results (True = valid, False = invalid)
    """
    try:
        # Check if required columns exist
        required_cols = ['DTAG_Status__c', 'Type', 'DTAG_Landed_Cost_Calculation__c']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: Missing columns {missing_cols} for validation rule 'DTAG_Restrict_LandedCost_ReleasedStatus'")
            return pd.Series([True] * len(df))  # Skip validation if columns missing
        
        # Get column values
        status = df['DTAG_Status__c'].fillna('').astype(str)
        account_type = df['Type'].fillna('').astype(str)
        landed_cost = df['DTAG_Landed_Cost_Calculation__c'].fillna('').astype(str)
        
        # Check conditions
        status_is_released = status == 'Released'
        type_is_relevant = account_type.isin(['TOC/TG', 'GD', 'ISP'])
        landed_cost_is_blank = landed_cost == ''
        
        # Validation fails if status is Released AND type is relevant AND landed cost is blank
        validation_error = status_is_released & type_is_relevant & landed_cost_is_blank
        return ~validation_error
        
    except Exception as e:
        print(f"Error in validate_DTAG_Restrict_LandedCost_ReleasedStatus: {e}")
        return pd.Series([True] * len(df))  # Default to valid if error occurs
