import pandas as pd
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, '.')

# Import the validation functions
from bundle import *

print("=== Testing GenAI Validation Functions ===\n")

# Load sample data
df = pd.read_csv("../sample_data.csv")
print(f"Loaded {len(df)} records:")
print(df)
print()

# Test individual validation functions
print("Testing validation functions:")

print("\n1. Email Required Validation:")
email_result = validate_Email_Required(df)
print(f"Results: {email_result.tolist()}")
print(f"Valid records: {email_result.sum()}/{len(df)}")

print("\n2. Phone Length Validation:")
phone_result = validate_Phone_Length_Check(df)
print(f"Results: {phone_result.tolist()}")
print(f"Valid records: {phone_result.sum()}/{len(df)}")

print("\n3. Name Not Empty Validation:")
name_result = validate_Name_Not_Empty(df)
print(f"Results: {name_result.tolist()}")
print(f"Valid records: {name_result.sum()}/{len(df)}")

print("\n4. Annual Revenue Positive Validation:")
revenue_result = validate_Annual_Revenue_Positive(df)
print(f"Results: {revenue_result.tolist()}")
print(f"Valid records: {revenue_result.sum()}/{len(df)}")

print("\n5. Website Format Validation:")
website_result = validate_Website_Format(df)
print(f"Results: {website_result.tolist()}")
print(f"Valid records: {website_result.sum()}/{len(df)}")

# Combine all results
print("\n=== Overall Validation Results ===")
results = pd.DataFrame({
    'Email_Required': email_result,
    'Phone_Length_Check': phone_result,
    'Name_Not_Empty': name_result,
    'Annual_Revenue_Positive': revenue_result,
    'Website_Format': website_result
})

results['is_valid'] = results.all(axis=1)
df['is_valid'] = results['is_valid']

# Add failed validation details
failed_cols = ['Email_Required', 'Phone_Length_Check', 'Name_Not_Empty', 'Annual_Revenue_Positive', 'Website_Format']
df['failed_validations'] = results[failed_cols].apply(
    lambda row: ', '.join([col for col in failed_cols if not row[col]]), axis=1
)

print(f"Overall Results:")
print(f"✅ Valid records: {results['is_valid'].sum()}/{len(df)} ({results['is_valid'].mean()*100:.1f}%)")
print(f"❌ Invalid records: {(~results['is_valid']).sum()}/{len(df)} ({(~results['is_valid']).mean()*100:.1f}%)")

print("\nDetailed Results:")
print(df[['Id', 'Name', 'Email', 'Phone', 'AnnualRevenue', 'is_valid', 'failed_validations']])

# Save results
df.to_csv('validation_results.csv', index=False)
print(f"\n📁 Results saved to 'validation_results.csv'")

print("\n🎉 GenAI Validation System Test Complete!")
print("✅ Successfully converted Salesforce validation rules to working Python functions!")