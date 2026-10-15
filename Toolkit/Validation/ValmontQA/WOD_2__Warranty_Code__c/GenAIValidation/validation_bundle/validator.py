import pandas as pd
from bundle import validate_dataframe
import os

def validate_csv_data(csv_file_path, output_folder=None):
    """
    Validate CSV data using generated validation bundle
    
    Args:
        csv_file_path: Path to CSV file to validate
        output_folder: Optional output folder for results
    
    Returns:
        dict: Validation results summary
    """
    if output_folder is None:
        output_folder = os.path.join(os.path.dirname(__file__), '..', 'ValidatedData')
    
    os.makedirs(output_folder, exist_ok=True)
    
    try:
        # Load data
        df = pd.read_csv(csv_file_path)
        print(f"Loaded {len(df)} records from {csv_file_path}")
        
        # Validate data
        valid_df, invalid_df, validation_results = validate_dataframe(df)
        
        # Save results
        valid_df.to_csv(os.path.join(output_folder, 'success.csv'), index=False)
        invalid_df.to_csv(os.path.join(output_folder, 'failure.csv'), index=False)
        
        # Create summary
        summary = {
            'total_records': len(df),
            'valid_records': len(valid_df),
            'invalid_records': len(invalid_df),
            'validation_rate': len(valid_df) / len(df) * 100 if len(df) > 0 else 0,
            'results_folder': output_folder
        }
        
        print(f"\n📊 Validation Results:")
        print(f"✅ Valid records: {len(valid_df)} ({summary['validation_rate']:.1f}%)")
        print(f"❌ Invalid records: {len(invalid_df)} ({100-summary['validation_rate']:.1f}%)")
        print(f"📁 Results saved to: {output_folder}")
        
        return summary
        
    except Exception as e:
        print(f"Error during validation: {e}")
        return None

if __name__ == "__main__":
    print("Validation Bundle - CSV Validator")
    # This can be called programmatically from the UI
