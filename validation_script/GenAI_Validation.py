import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import pandas as pd
import os
import dataset.Connections as Connections
import dataset.Org_selection as Org_selection
import tkinter as tk
from tkinter import filedialog
import json
import tkinter.ttk as ttk  # Add this import at the top


def select_file(selected_org=None, object_name=None):
    # Use filedialog with the VS Code file picker if available, else fallback to Tkinter
    print("Please select the validation formula CSV file:")
    
    # Set default location based on org and object
    default_dir = r"C:\DM_toolkit\DataFiles"
    if selected_org and object_name:
        specific_dir = os.path.join(r"C:\DM_toolkit\DataFiles", selected_org, object_name)
        if os.path.exists(specific_dir):
            default_dir = specific_dir
    
    try:
        # VS Code's file picker integration (works if running in VS Code with Python extension)
        import sys
        if "vscode" in sys.modules:
            import builtins
            if hasattr(builtins, "vscode"):
                # VS Code interactive window file picker
                from builtins import vscode
                file_path = vscode.open_file_dialog(title="Select Validation formula file", filters=[("CSV files", "*.csv"), ("All files", "*.*")])
                print("Selected file:", file_path)
                return file_path
    except Exception:
        pass

    # Fallback to Tkinter dialog (will open a native OS window)
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    file_path = filedialog.askopenfilename(
        title="Select Validation formula file",
        initialdir=default_dir,
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    print("Selected file:", file_path)
    return file_path

def select_org_dropdown(orgs):
    selected = {'value': None}
    def on_select():
        selected['value'] = var.get()
        win.destroy()
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Select Salesforce Org")
    win.geometry("600x250")
    win.grab_set()
    tk.Label(win, text="Select Salesforce Org:").pack(pady=20)
    var = tk.StringVar(win)
    var.set(orgs[0])
    dropdown = tk.OptionMenu(win, var, *orgs)
    dropdown.config(width=60)
    dropdown.pack(padx=20, pady=20)
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    return selected['value']

def select_object_dropdown(sf):
    # Get object names (custom + 'Account')
    objects = [
        obj['name'] for obj in sf.describe()['sobjects']
        if obj['name'].endswith('__c') or obj['name'].lower() == 'account'
    ]
    selected_object = {'value': None}
    def on_select(event=None):
        selected_object['value'] = combo.get()
        root.destroy()  # Fix: use root instead of win
    def on_type(event):
        typed = combo.get().strip().lower()
        if not typed:
            combo['values'] = objects
        else:
            filtered = [obj for obj in objects if typed in obj.lower()]
            combo['values'] = filtered
        if combo['values']:
            combo.event_generate('<Down>')
    root = tk.Tk()
    root.title("Select Salesforce Object")
    root.geometry("400x120")
    label = tk.Label(root, text="Choose a Salesforce object:")
    label.pack(pady=10)
    combo = ttk.Combobox(root, values=objects, width=50)
    combo.pack(pady=5)
    combo.bind("<<ComboboxSelected>>", on_select)
    combo.bind("<KeyRelease>", on_type)
    combo.focus_set()
    root.mainloop()
    return selected_object['value']

with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
    creds = json.load(f)
orgs = list(creds.keys())
selected_org = select_org_dropdown(orgs)
if not selected_org or selected_org not in creds:
    raise ValueError(f"Org '{selected_org}' not found in credentials file.")

# Connect to Salesforce for object dropdown
# Fix: Use correct argument name for org selection
sf_conn = Connections.get_salesforce_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json", org_name=selected_org)
object_name = select_object_dropdown(sf_conn)
if not object_name:
    raise ValueError("No Salesforce object selected.")
res = selected_org + "_" + object_name

def safe_func_name(name):
    return "".join(c if c.isalnum() or c == '_' else '_' for c in name.strip())

def build_function_code(name, formula, field, obj):
    func_name = f"validate_{safe_func_name(name)}"
    
    # Handle empty field names
    if not field or field.lower() == 'nan':
        field_logic = "pd.Series([True] * len(df))  # No field specified - always valid"
        field_comment = "# WARNING: No field name specified"
    else:
        field_logic = f"df['{field}'].notna()  # Placeholder logic - replace with actual validation"
        field_comment = f"# Field: {field}"
    
    return f'''
def {func_name}(df):
    """
    Validation Rule: {name}
    Salesforce Object: {obj if obj and obj.lower() != 'nan' else 'Not specified'}
    Field: {field if field and field.lower() != 'nan' else 'Not specified'}
    Apex Formula:
    {formula if formula and formula.lower() != 'nan' else 'Not specified'}
    
    Args:
        df (pandas.DataFrame): Input DataFrame to validate
    Returns:
        pandas.Series: Boolean mask indicating validation results
    """
    {field_comment}
    # TODO: Implement Python equivalent of Apex formula
    # Example placeholder - replace with actual formula logic
    try:
        return {field_logic}
    except KeyError as e:
        print(f"Warning: Column {{e}} not found in DataFrame for validation rule '{name}'")
        return pd.Series([False] * len(df))  # Mark all as invalid if column missing
'''

# Update folder structure to use Validation/[OrgName]/[ObjectName]/GenAIValidation
root_dir = os.path.join("Validation", selected_org, object_name, "GenAIValidation")
roots = root_dir  # Use the full path directly

def generate_validation_bundle(validation_csv, output_dir=None):
    # Place validation_bundle inside Validation/[OrgName]/[ObjectName]/GenAIValidation
    if output_dir is None:
        output_dir = os.path.join(roots, "validation_bundle")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(roots, "ValidatedData"), exist_ok=True)
    
    # Read and validate the CSV file
    try:
        df = pd.read_csv(validation_csv)
        print(f"Successfully loaded CSV with {len(df)} rows")
        print(f"CSV columns: {list(df.columns)}")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return
    
    # Check for required columns
    required_columns = ["ValidationName", "ErrorConditionFormula", "FieldName", "ObjectName", "Active"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"⚠️ Missing required columns in CSV: {missing_columns}")
        print(f"Available columns: {list(df.columns)}")
        print("Please ensure your CSV has the following columns:")
        for col in required_columns:
            print(f"  - {col}")
        return
    
    bundle_content = "# Auto-generated validation bundle\nimport pandas as pd\n\n"
    validation_functions = []
    skipped_rules = []

    for index, row in df.iterrows():
        # Check if the rule is active
        active_value = str(row.get("Active", "")).lower()
        if active_value not in ["true", "1", "yes"]:
            skipped_rules.append(f"Row {index + 1}: Not active (Active='{row.get('Active', '')}')")
            continue

        name = str(row.get("ValidationName", "")).strip()
        formula = str(row.get("ErrorConditionFormula", "")).strip()
        field = str(row.get("FieldName", "")).strip()
        obj = str(row.get("ObjectName", "")).strip()
        
        # Validate that we have the minimum required data
        if not name or name.lower() == 'nan':
            name = f"Rule_{index + 1}"
            print(f"⚠️ Row {index + 1}: Missing ValidationName, using '{name}'")
        
        if not field or field.lower() == 'nan':
            skipped_rules.append(f"Row {index + 1}: Missing FieldName for rule '{name}'")
            continue
            
        if not formula or formula.lower() == 'nan':
            skipped_rules.append(f"Row {index + 1}: Missing ErrorConditionFormula for rule '{name}'")
            continue
        
        # Generate unique function name
        safe_name = safe_func_name(name)
        func_name = f"validate_{safe_name}"
        
        # Ensure unique function names
        counter = 1
        original_func_name = func_name
        while func_name.replace("validate_", "") in validation_functions:
            func_name = f"{original_func_name}_{counter}"
            counter += 1
        
        func_code = build_function_code(name, formula, field, obj)
        bundle_content += func_code
        validation_functions.append(func_name.replace("validate_", ""))

    # Print summary
    print(f"\n📊 Validation Bundle Generation Summary:")
    print(f"✅ Successfully processed: {len(validation_functions)} validation rules")
    if skipped_rules:
        print(f"⚠️ Skipped: {len(skipped_rules)} rules")
        for skip_reason in skipped_rules[:5]:  # Show first 5 skipped rules
            print(f"   - {skip_reason}")
        if len(skipped_rules) > 5:
            print(f"   ... and {len(skipped_rules) - 5} more")
    
    if not validation_functions:
        print("❌ No valid validation rules found. Please check your CSV file.")
        return

    # Write bundle file
    bundle_path = os.path.join(output_dir, "bundle.py")
    with open(bundle_path, "w", encoding="utf-8") as f:
        f.write(bundle_content)

    # Create validator script
    validator_content = f'''import pandas as pd
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
        print(f"Loaded {{len(df)}} records from {{data_csv}}")
    except Exception as e:
        print(f"Error loading data file: {{e}}")
        return None
        
    df = df.fillna('')  # Fill NaN values with empty strings
    results = pd.DataFrame(index=df.index)
    
    # Apply each validation function
{chr(10).join(f"    try:" + chr(10) + f"        results['validate_{func}'] = validate_{func}(df)" + chr(10) + f"        print(f'✅ Applied validation: validate_{func}')" + chr(10) + f"    except Exception as e:" + chr(10) + f"        print(f'❌ Error in validate_{func}: {{e}}')" + chr(10) + f"        results['validate_{func}'] = pd.Series([False] * len(df))" for func in validation_functions)}
    
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
        
        print(f"\\n📊 Validation Results:")
        print(f"✅ Valid records: {{len(suc_df)}} ({{len(suc_df)/len(df)*100:.1f}}%)")
        print(f"❌ Invalid records: {{len(fail_df)}} ({{len(fail_df)/len(df)*100:.1f}}%)")
        print(f"📁 Results saved to: {{root_folder}}")
        
    except Exception as e:
        print(f"Error saving results: {{e}}")
    
    return results


if __name__ == "__main__":
    print("=== Validation Bundle Validator ===")
    print("This tool applies all validation rules to your data.")
    print()
    
    data_csv = select_file()
    if data_csv:
        results = validate_all(data_csv)
        if results is not None:
            print("\\n=== Summary ===")
            print(f"Total records processed: {{len(results)}}")
            if len(results) > 0:
                print(f"Valid records: {{results['is_valid'].sum()}}")
                print(f"Invalid records: {{len(results) - results['is_valid'].sum()}}")
        else:
            print("Validation failed. Please check your data file.")
    else:
        print("No file selected. Exiting.")
'''

    validator_path = os.path.join(output_dir, "validator.py")
    with open(validator_path, "w", encoding="utf-8") as f:
        f.write(validator_content)

    print(f"\n✅ Created validation bundle in Validation/{selected_org}/{object_name}/GenAIValidation/validation_bundle/")
    print(f"📄 bundle.py: Contains all validation functions")
    print(f"📄 validator.py: Applies all validations to data.csv")
    print(f"📊 {len(validation_functions)} validation functions generated")
    print(f"\nFolder structure:")
    print(f"C:\\DM_toolkit\\Validation\\{selected_org}\\{object_name}\\GenAIValidation\\validation_bundle\\")
    print(f"C:\\DM_toolkit\\Validation\\{selected_org}\\{object_name}\\GenAIValidation\\ValidatedData\\")
    print("\nTo use:")
    print(f"1. Implement actual validation logic in {bundle_path}")
    print(f"2. Run validator.py to validate data.csv")

if __name__ == "__main__":
    print("Welcome to the Validation Bundle Generator!\n please select the file from outside of VS Code")
    print(f"Selected Org: {selected_org}")
    validation_csv = select_file(selected_org, object_name)
    generate_validation_bundle(validation_csv)