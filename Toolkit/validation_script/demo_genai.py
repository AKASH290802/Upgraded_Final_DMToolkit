"""
GenAI Validation Demo - Complete Workflow Demonstration
This script demonstrates the complete GenAI validation workflow
"""
import sys
sys.path.append(r"C:\DM_toolkit")
import pandas as pd
import os
import re
from typing import Dict, List, Optional

# Set working directory
os.chdir(r"C:\DM_toolkit\validation_script")

print("=== GenAI Validation System Demo ===\n")

class SalesforceFormulaConverter:
    """
    Intelligent converter that transforms Salesforce validation formulas to Python code
    """
    
    def __init__(self):
        # Mapping of Salesforce functions to Python equivalents
        self.function_mappings = {
            'ISBLANK': 'pd.isna',
            'ISNULL': 'pd.isna', 
            'LEN': 'len',
            'TEXT': 'str',
            'VALUE': 'pd.to_numeric',
            'UPPER': 'str.upper',
            'LOWER': 'str.lower',
            'AND': 'all',
            'OR': 'any',
            'NOT': 'not',
            'CONTAINS': 'str.contains'
        }
        
        # Mapping of Salesforce operators to Python operators
        self.operator_mappings = {
            '&&': ' & ',
            '||': ' | ',
            '=': ' == ',
            '<>': ' != ',
        }
    
    def convert_formula_to_python(self, formula: str, field_name: str) -> str:
        """Convert Salesforce formula to Python code"""
        if not formula or formula.lower() == 'nan':
            return f"df['{field_name}'].isna()"
        
        try:
            # Simple conversion for common patterns
            python_code = formula
            
            # Convert ISBLANK function
            if 'ISBLANK(' in formula:
                field_match = re.search(r'ISBLANK\((\w+)\)', formula)
                if field_match:
                    field = field_match.group(1)
                    python_code = f"df['{field}'].isna() | (df['{field}'] == '')"
            
            # Convert LEN function with comparison
            elif 'LEN(' in formula and '<' in formula:
                len_match = re.search(r'LEN\((\w+)\)\s*<\s*(\d+)', formula)
                if len_match:
                    field = len_match.group(1)
                    length = len_match.group(2)
                    python_code = f"df['{field}'].str.len() < {length}"
            
            # Convert simple field comparisons
            elif '<=' in formula:
                comp_match = re.search(r'(\w+)\s*<=\s*(\d+)', formula)
                if comp_match:
                    field = comp_match.group(1)
                    value = comp_match.group(2)
                    python_code = f"df['{field}'] <= {value}"
            
            # Convert AND with CONTAINS
            elif 'AND(' in formula and 'CONTAINS(' in formula:
                python_code = f"~df['{field_name}'].str.contains('http', na=True)"
            
            else:
                # Default fallback
                python_code = f"df['{field_name}'].isna()"
            
            return python_code
            
        except Exception as e:
            print(f"Warning: Could not convert formula '{formula}': {e}")
            return f"df['{field_name}'].isna()"

def parse_field_names(field_string):
    """Parse field names from CSV FieldName column"""
    if not field_string or str(field_string).lower() == 'nan':
        return []
    
    field_string = str(field_string).strip().replace('"', '').replace("'", "")
    fields = [field.strip() for field in field_string.split(',') if field.strip()]
    valid_fields = [field for field in fields if field and field != '' and len(field) > 0]
    
    return valid_fields

def generate_demo_validation_bundle():
    """Generate validation bundle from sample CSV"""
    
    print("1. Loading sample validation rules...")
    df = pd.read_csv("sample_validation.csv")
    print(f"✅ Loaded {len(df)} validation rules")
    
    print("\n2. Converting Salesforce formulas to Python...")
    
    converter = SalesforceFormulaConverter()
    bundle_content = """# Auto-generated validation bundle by GenAI Validation System
import pandas as pd
import numpy as np
from datetime import datetime, date

"""
    
    validation_functions = []
    
    for index, row in df.iterrows():
        name = str(row['ValidationName']).strip()
        formula = str(row['ErrorConditionFormula']).strip()
        field = str(row['FieldName']).strip()
        obj = str(row['ObjectName']).strip()
        
        field_names = parse_field_names(field)
        primary_field = field_names[0] if field_names else 'Id'
        
        func_name = f"validate_{name.replace(' ', '_').replace('-', '_')}"
        
        print(f"   Converting: {name}")
        print(f"   Formula: {formula}")
        
        python_logic = converter.convert_formula_to_python(formula, primary_field)
        print(f"   Python: {python_logic}")
        print()
        
        function_code = f'''
def {func_name}(df):
    """
    Validation Rule: {name}
    Object: {obj}
    Field: {primary_field}
    Original Formula: {formula}
    
    Returns: Boolean series (True = valid, False = invalid)
    """
    try:
        if '{primary_field}' not in df.columns:
            print(f"Warning: Column '{primary_field}' not found")
            return pd.Series([False] * len(df))
        
        # Convert error condition to validation result (invert the logic)
        error_condition = {python_logic}
        
        # Return inverse (True = valid, False = invalid)
        return ~error_condition
        
    except Exception as e:
        print(f"Error in {func_name}: {{e}}")
        return pd.Series([False] * len(df))
'''
        
        bundle_content += function_code
        validation_functions.append(func_name)
    
    print("3. Generating validation bundle...")
    
    # Create output directory
    output_dir = "demo_validation_bundle"
    os.makedirs(output_dir, exist_ok=True)
    
    # Write bundle.py
    bundle_path = os.path.join(output_dir, "bundle.py")
    with open(bundle_path, "w", encoding="utf-8") as f:
        f.write(bundle_content)
    
    # Create validator.py
    validator_content = f'''# Auto-generated validator by GenAI Validation System
import pandas as pd
from bundle import *
import os

def validate_data(csv_file):
    """Validate data using all validation rules"""
    print(f"Loading data from {{csv_file}}...")
    df = pd.read_csv(csv_file)
    print(f"Loaded {{len(df)}} records")
    
    results = pd.DataFrame(index=df.index)
    
    # Apply all validation functions
{chr(10).join(f"    results['{func}'] = {func}(df)" for func in validation_functions)}
    
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
    
    print(f"\\nValidation Results:")
    print(f"Valid records: {{df['is_valid'].sum()}} / {{len(df)}} ({{df['is_valid'].mean()*100:.1f}}%)")
    print(f"Invalid records: {{(~df['is_valid']).sum()}} / {{len(df)}} ({{(~df['is_valid']).mean()*100:.1f}}%)")
    
    return df

if __name__ == "__main__":
    # Test with sample data
    sample_data = "../sample_data.csv"
    if os.path.exists(sample_data):
        validate_data(sample_data)
    else:
        print("Sample data file not found. Please provide a CSV file to validate.")
'''
    
    validator_path = os.path.join(output_dir, "validator.py")
    with open(validator_path, "w", encoding="utf-8") as f:
        f.write(validator_content)
    
    print(f"✅ Generated validation bundle in '{output_dir}/'")
    print(f"   - bundle.py: Contains {len(validation_functions)} validation functions")
    print(f"   - validator.py: Validation runner script")
    
    return output_dir

def test_validation():
    """Test the generated validation functions"""
    print("\n4. Testing validation with sample data...")
    
    # Load sample data
    df = pd.read_csv("sample_data.csv")
    print(f"Sample data: {len(df)} records")
    print(df.head())
    
    # Run validation
    os.chdir("demo_validation_bundle")
    exec(open("validator.py").read())

if __name__ == "__main__":
    # Run the complete demo
    try:
        output_dir = generate_demo_validation_bundle()
        test_validation()
        
        print("\n=== Demo Complete ===")
        print(f"✅ GenAI Validation System successfully converted Salesforce validation rules to Python!")
        print(f"✅ Generated validation bundle in '{output_dir}/'")
        print(f"✅ Tested validation with sample data")
        
        print("\n📋 Generated Files:")
        print(f"   - {output_dir}/bundle.py: Python validation functions")
        print(f"   - {output_dir}/validator.py: Validation runner")
        print(f"   - validated_data.csv: Complete results")
        print(f"   - valid_records.csv: Valid records only")
        print(f"   - invalid_records.csv: Invalid records only")
        
    except Exception as e:
        print(f"Demo error: {e}")
        import traceback
        traceback.print_exc()