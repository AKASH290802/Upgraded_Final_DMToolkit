import pandas as pd
from bundle import *
import tkinter as tk
from tkinter import filedialog
import os

def select_file():
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    file_path = filedialog.askopenfilename(
        title="Select data file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    print("Selected file:", file_path)
    return file_path


def validate_all(data_csv):
    """
    Validates all records in data_csv using all validation functions
    Returns a DataFrame with validation results
    """
    if not data_csv:
        print("No file selected.")
        return None
        
    try:
        df = pd.read_csv(data_csv)
        gf = pd.read_csv(data_csv)
        print(f"Loaded {len(df)} records from {data_csv}")
    except Exception as e:
        print(f"Error loading data file: {e}")
        return None
        
    df = df.fillna('')  # Fill NaN values with empty strings
    results = pd.DataFrame(index=df.index)
    
    # Apply each validation function
    try:
        results['validate_DTAG_RestrictMultipleBUforWholeSale'] = validate_DTAG_RestrictMultipleBUforWholeSale(df)
        print(f'✅ Applied validation: validate_DTAG_RestrictMultipleBUforWholeSale')
    except Exception as e:
        print(f'❌ Error in validate_DTAG_RestrictMultipleBUforWholeSale: {e}')
        results['validate_DTAG_RestrictMultipleBUforWholeSale'] = pd.Series([False] * len(df))
    try:
        results['validate_DTAG_WACanCreateRWSOnly'] = validate_DTAG_WACanCreateRWSOnly(df)
        print(f'✅ Applied validation: validate_DTAG_WACanCreateRWSOnly')
    except Exception as e:
        print(f'❌ Error in validate_DTAG_WACanCreateRWSOnly: {e}')
        results['validate_DTAG_WACanCreateRWSOnly'] = pd.Series([False] * len(df))
    try:
        results['validate_Parent_cannot_be_Draft_for_Child_active'] = validate_Parent_cannot_be_Draft_for_Child_active(df)
        print(f'✅ Applied validation: validate_Parent_cannot_be_Draft_for_Child_active')
    except Exception as e:
        print(f'❌ Error in validate_Parent_cannot_be_Draft_for_Child_active: {e}')
        results['validate_Parent_cannot_be_Draft_for_Child_active'] = pd.Series([False] * len(df))
    try:
        results['validate_Restrict_For_ActiveOrReleased_Status'] = validate_Restrict_For_ActiveOrReleased_Status(df)
        print(f'✅ Applied validation: validate_Restrict_For_ActiveOrReleased_Status')
    except Exception as e:
        print(f'❌ Error in validate_Restrict_For_ActiveOrReleased_Status: {e}')
        results['validate_Restrict_For_ActiveOrReleased_Status'] = pd.Series([False] * len(df))
    try:
        results['validate_ValidFromIsRequiredForReleased'] = validate_ValidFromIsRequiredForReleased(df)
        print(f'✅ Applied validation: validate_ValidFromIsRequiredForReleased')
    except Exception as e:
        print(f'❌ Error in validate_ValidFromIsRequiredForReleased: {e}')
        results['validate_ValidFromIsRequiredForReleased'] = pd.Series([False] * len(df))
    try:
        results['validate_DT_Billing_country_should_be_AU_or_NZ'] = validate_DT_Billing_country_should_be_AU_or_NZ(df)
        print(f'✅ Applied validation: validate_DT_Billing_country_should_be_AU_or_NZ')
    except Exception as e:
        print(f'❌ Error in validate_DT_Billing_country_should_be_AU_or_NZ: {e}')
        results['validate_DT_Billing_country_should_be_AU_or_NZ'] = pd.Series([False] * len(df))
    try:
        results['validate_DTAG_Restrict_CurrencyforReleased'] = validate_DTAG_Restrict_CurrencyforReleased(df)
        print(f'✅ Applied validation: validate_DTAG_Restrict_CurrencyforReleased')
    except Exception as e:
        print(f'❌ Error in validate_DTAG_Restrict_CurrencyforReleased: {e}')
        results['validate_DTAG_Restrict_CurrencyforReleased'] = pd.Series([False] * len(df))
    try:
        results['validate_DTAG_Restrict_For_Released_Status_New'] = validate_DTAG_Restrict_For_Released_Status_New(df)
        print(f'✅ Applied validation: validate_DTAG_Restrict_For_Released_Status_New')
    except Exception as e:
        print(f'❌ Error in validate_DTAG_Restrict_For_Released_Status_New: {e}')
        results['validate_DTAG_Restrict_For_Released_Status_New'] = pd.Series([False] * len(df))
    try:
        results['validate_DTAG_Restrict_LandedCost_ReleasedStatus'] = validate_DTAG_Restrict_LandedCost_ReleasedStatus(df)
        print(f'✅ Applied validation: validate_DTAG_Restrict_LandedCost_ReleasedStatus')
    except Exception as e:
        print(f'❌ Error in validate_DTAG_Restrict_LandedCost_ReleasedStatus: {e}')
        results['validate_DTAG_Restrict_LandedCost_ReleasedStatus'] = pd.Series([False] * len(df))
    
    # Add summary column
    results['is_valid'] = results.all(axis=1)
    df['is_valid'] = results['is_valid']
    
    # Add 'issue' column: validation name if failed, else empty string
    failed_cols = [col for col in results.columns if col != 'is_valid']
    df['issue'] = results[failed_cols].apply(lambda row: ', '.join([col for col in failed_cols if not row[col]]), axis=1)

    # Save to ValidatedData folder one level above validation_bundle
    root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ValidatedData'))
    os.makedirs(root_folder, exist_ok=True)
    
    # Save results
    try:
        df.to_csv(os.path.join(root_folder, 'validatedData.csv'), index=False)
        suc_df = df[df['is_valid']]
        fail_df = df[~df['is_valid']]
        suc_df.to_csv(os.path.join(root_folder, 'success.csv'), index=False)
        fail_df.to_csv(os.path.join(root_folder, 'failure.csv'), index=False)
        
        print(f"\n📊 Validation Results:")
        print(f"✅ Valid records: {len(suc_df)} ({len(suc_df)/len(df)*100:.1f}%)")
        print(f"❌ Invalid records: {len(fail_df)} ({len(fail_df)/len(df)*100:.1f}%)")
        print(f"📁 Results saved to: {root_folder}")
        
    except Exception as e:
        print(f"Error saving results: {e}")
    
    return results


if __name__ == "__main__":
    print("=== Validation Bundle Validator ===")
    print("This tool applies all validation rules to your data.")
    print()
    
    data_csv = select_file()
    if data_csv:
        results = validate_all(data_csv)
        if results is not None:
            print("\n=== Summary ===")
            print(f"Total records processed: {len(results)}")
            if len(results) > 0:
                print(f"Valid records: {results['is_valid'].sum()}")
                print(f"Invalid records: {len(results) - results['is_valid'].sum()}")
        else:
            print("Validation failed. Please check your data file.")
    else:
        print("No file selected. Exiting.")
