# Auto-generated validator by GenAI Validation System
import pandas as pd
from bundle import *
import os

def validate_data(csv_file):
    """Validate data using all validation rules"""
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} records")
    
    results = pd.DataFrame(index=df.index)
    
    # Apply all validation functions
    results['validate_Email_Required'] = validate_Email_Required(df)
    results['validate_Phone_Length_Check'] = validate_Phone_Length_Check(df)
    results['validate_Name_Not_Empty'] = validate_Name_Not_Empty(df)
    results['validate_Annual_Revenue_Positive'] = validate_Annual_Revenue_Positive(df)
    results['validate_Website_Format'] = validate_Website_Format(df)
    
    # Overall validity
    results['is_valid'] = results.all(axis=1)
    df['is_valid'] = results['is_valid']
    
    # Failed validations
    failed_cols = [col for col in results.columns if col != 'is_valid']
    df['failed_validations'] = results[failed_cols].apply(
        lambda row: ', '.join([col for col in failed_cols if not row[col]]), axis=1
    )
    
    # Save results
    df.to_csv('validated_data.csv', index=False)
    df[df['is_valid']].to_csv('valid_records.csv', index=False)
    df[~df['is_valid']].to_csv('invalid_records.csv', index=False)
    
    print(f"\nValidation Results:")
    print(f"Valid records: {df['is_valid'].sum()} / {len(df)} ({df['is_valid'].mean()*100:.1f}%)")
    print(f"Invalid records: {(~df['is_valid']).sum()} / {len(df)} ({(~df['is_valid']).mean()*100:.1f}%)")
    
    return df

if __name__ == "__main__":
    # Test with sample data
    sample_data = "../sample_data.csv"
    if os.path.exists(sample_data):
        validate_data(sample_data)
    else:
        print("Sample data file not found. Please provide a CSV file to validate.")
