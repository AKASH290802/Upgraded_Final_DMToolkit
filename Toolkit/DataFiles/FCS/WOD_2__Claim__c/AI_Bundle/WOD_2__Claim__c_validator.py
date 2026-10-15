
"""
Standalone Validator for WOD_2__Claim__c
Generated on: 2025-10-28 13:06:18

This script can be used to validate CSV/Excel files using the generated validation bundle.
"""

import pandas as pd
import os
import sys
from typing import Dict, List

# Import the validation bundle
try:
    from WOD_2__Claim__c_validation_bundle import validate_dataframe, get_all_validation_functions
except ImportError:
    print("Error: Could not import validation bundle. Make sure the bundle file is in the same directory.")
    sys.exit(1)

def validate_file(file_path: str, output_path: str = None) -> Dict:
    """
    Validate a CSV or Excel file
    
    Args:
        file_path: Path to the file to validate
        output_path: Optional path to save results
        
    Returns:
        Dict with validation summary
    """
    try:
        # Read the file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format. Please use CSV or Excel files.")
        
        print(f"Loaded {len(df)} records from {file_path}")
        
        # Run validation
        print("Running validation...")
        validated_df = validate_dataframe(df)
        
        # Calculate summary
        total_records = len(validated_df)
        valid_records = validated_df['is_valid'].sum()
        invalid_records = total_records - valid_records
        
        summary = {
            'total_records': total_records,
            'valid_records': valid_records,
            'invalid_records': invalid_records,
            'success_rate': (valid_records / total_records * 100) if total_records > 0 else 0
        }
        
        print(f"Validation complete:")
        print(f"  Total records: {total_records}")
        print(f"  Valid records: {valid_records}")
        print(f"  Invalid records: {invalid_records}")
        print(f"  Success rate: {summary['success_rate']:.1f}%")
        
        # Save results if output path provided
        if output_path:
            validated_df.to_csv(output_path, index=False)
            print(f"Results saved to: {output_path}")
        
        return {
            'summary': summary,
            'validated_data': validated_df
        }
        
    except Exception as e:
        print(f"Error validating file: {str(e)}")
        return {'error': str(e)}

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate CSV/Excel files using Salesforce validation rules')
    parser.add_argument('input_file', help='Path to the CSV or Excel file to validate')
    parser.add_argument('-o', '--output', help='Path to save validation results')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: File {args.input_file} not found")
        return
    
    # Run validation
    result = validate_file(args.input_file, args.output)
    
    if 'error' in result:
        print(f"Validation failed: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
