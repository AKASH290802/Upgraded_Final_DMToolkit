# Auto-generated validation bundle by GenAI Validation System
import pandas as pd
import numpy as np
from datetime import datetime, date


def validate_Email_Required(df):
    """
    Validation Rule: Email_Required
    Object: Account
    Field: Email
    Original Formula: ISBLANK(Email)
    
    Returns: Boolean series (True = valid, False = invalid)
    """
    try:
        if 'Email' not in df.columns:
            print(f"Warning: Column 'Email' not found")
            return pd.Series([False] * len(df))
        
        # Convert error condition to validation result (invert the logic)
        error_condition = df['Email'].isna() | (df['Email'] == '')
        
        # Return inverse (True = valid, False = invalid)
        return ~error_condition
        
    except Exception as e:
        print(f"Error in validate_Email_Required: {e}")
        return pd.Series([False] * len(df))

def validate_Phone_Length_Check(df):
    """
    Validation Rule: Phone_Length_Check
    Object: Account
    Field: Phone
    Original Formula: LEN(Phone) < 10
    
    Returns: Boolean series (True = valid, False = invalid)
    """
    try:
        if 'Phone' not in df.columns:
            print(f"Warning: Column 'Phone' not found")
            return pd.Series([False] * len(df))
        
        # Convert error condition to validation result (invert the logic)
        error_condition = df['Phone'].str.len() < 10
        
        # Return inverse (True = valid, False = invalid)
        return ~error_condition
        
    except Exception as e:
        print(f"Error in validate_Phone_Length_Check: {e}")
        return pd.Series([False] * len(df))

def validate_Name_Not_Empty(df):
    """
    Validation Rule: Name_Not_Empty
    Object: Account
    Field: Name
    Original Formula: ISBLANK(Name)
    
    Returns: Boolean series (True = valid, False = invalid)
    """
    try:
        if 'Name' not in df.columns:
            print(f"Warning: Column 'Name' not found")
            return pd.Series([False] * len(df))
        
        # Convert error condition to validation result (invert the logic)
        error_condition = df['Name'].isna() | (df['Name'] == '')
        
        # Return inverse (True = valid, False = invalid)
        return ~error_condition
        
    except Exception as e:
        print(f"Error in validate_Name_Not_Empty: {e}")
        return pd.Series([False] * len(df))

def validate_Annual_Revenue_Positive(df):
    """
    Validation Rule: Annual_Revenue_Positive
    Object: Account
    Field: AnnualRevenue
    Original Formula: AnnualRevenue <= 0
    
    Returns: Boolean series (True = valid, False = invalid)
    """
    try:
        if 'AnnualRevenue' not in df.columns:
            print(f"Warning: Column 'AnnualRevenue' not found")
            return pd.Series([False] * len(df))
        
        # Convert error condition to validation result (invert the logic)
        error_condition = df['AnnualRevenue'] <= 0
        
        # Return inverse (True = valid, False = invalid)
        return ~error_condition
        
    except Exception as e:
        print(f"Error in validate_Annual_Revenue_Positive: {e}")
        return pd.Series([False] * len(df))

def validate_Website_Format(df):
    """
    Validation Rule: Website_Format
    Object: Account
    Field: Website
    Original Formula: AND(NOT(ISBLANK(Website)), NOT(CONTAINS(Website, "http")))
    
    Returns: Boolean series (True = valid, False = invalid)
    """
    try:
        if 'Website' not in df.columns:
            print(f"Warning: Column 'Website' not found")
            return pd.Series([False] * len(df))
        
        # Convert error condition to validation result (invert the logic)
        error_condition = df['Website'].isna() | (df['Website'] == '')
        
        # Return inverse (True = valid, False = invalid)
        return ~error_condition
        
    except Exception as e:
        print(f"Error in validate_Website_Format: {e}")
        return pd.Series([False] * len(df))
