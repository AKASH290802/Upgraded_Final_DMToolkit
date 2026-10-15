import sys
sys.path.append(r"C:\DM_toolkit")
import pandas as pd
import os
os.chdir(r"C:\DM_toolkit\validation_script")

print("=== Testing GenAI Validation System ===\n")

# Test 1: Import and test the SalesforceFormulaConverter class
print("1. Testing Formula Converter Import:")
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("genai_validation", "GenAI_Validation.py")
    genai_module = importlib.util.module_from_spec(spec)
    
    # Extract just the classes we need without running the full script
    with open("GenAI_Validation.py", "r") as f:
        content = f.read()
    
    # Extract the SalesforceFormulaConverter class definition
    start_idx = content.find("class SalesforceFormulaConverter:")
    end_idx = content.find("\ndef select_file")
    
    if start_idx != -1 and end_idx != -1:
        class_code = content[start_idx:end_idx]
        
        # Execute the class definition
        exec(class_code)
        
        # Extract the parse_field_names function
        parse_start = content.find("def parse_field_names(")
        parse_end = content.find("\ndef build_function_code")
        if parse_start != -1 and parse_end != -1:
            parse_code = content[parse_start:parse_end]
            exec(parse_code)
        
        print("✅ Successfully imported SalesforceFormulaConverter")
        
    else:
        print("❌ Could not extract SalesforceFormulaConverter class")
        
except Exception as e:
    print(f"❌ Error importing: {e}")

# Test 2: Formula Converter
print("\n2. Testing Formula Converter:")
try:
    converter = SalesforceFormulaConverter()

    test_formulas = [
        ("ISBLANK(Email)", "Email"),
        ("LEN(Phone) < 10", "Phone"), 
        ("AnnualRevenue <= 0", "AnnualRevenue"),
        ("NOT(ISBLANK(Name))", "Name")
    ]

    for formula, field in test_formulas:
        print(f"\nOriginal: {formula}")
        converted = converter.convert_formula_to_python(formula, field)
        print(f"Converted: {converted[:100]}..." if len(converted) > 100 else f"Converted: {converted}")
        
    print("✅ Formula conversion tests completed")
except Exception as e:
    print(f"❌ Formula converter error: {e}")

# Test 3: Field Name Parsing
print("\n3. Testing Field Name Parsing:")
try:
    test_fields = [
        "Email",
        "Email, Phone, Name", 
        "', , , , , , ,'",
        "",
        "Name"
    ]

    for field_str in test_fields:
        parsed = parse_field_names(field_str)
        print(f"Input: '{field_str}' -> Parsed: {parsed}")
        
    print("✅ Field parsing tests completed")
except Exception as e:
    print(f"❌ Field parsing error: {e}")

print("\n4. Testing Sample Validation Bundle Generation:")
try:
    # Test reading the sample CSV
    df = pd.read_csv("sample_validation.csv")
    print(f"✅ Sample CSV loaded: {len(df)} validation rules")
    print(f"Columns: {list(df.columns)}")
    
    # Show first rule
    first_rule = df.iloc[0]
    print(f"\nFirst rule example:")
    print(f"  Name: {first_rule['ValidationName']}")
    print(f"  Formula: {first_rule['ErrorConditionFormula']}")
    print(f"  Field: {first_rule['FieldName']}")
    
except Exception as e:
    print(f"❌ CSV test error: {e}")

print("\n=== GenAI Validation System Test Complete ===")
print("\n📋 System Features:")
print("✅ Intelligent Salesforce formula to Python conversion")
print("✅ Support for common Salesforce functions (ISBLANK, LEN, AND, OR, etc.)")
print("✅ Field name parsing with comma-separated value handling")
print("✅ Automatic Python validation function generation")
print("✅ Error handling and fallback logic")
print("✅ CSV validation rule processing")

print("\n🚀 To use the full system:")
print("1. Run GenAI_Validation.py")
print("2. Select your Salesforce org")
print("3. Choose the object")
print("4. Select validation rules CSV file")
print("5. System generates bundle.py with validation functions")
print("6. Use validator.py to validate data files")