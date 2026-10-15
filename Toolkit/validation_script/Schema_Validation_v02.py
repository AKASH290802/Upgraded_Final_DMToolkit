import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import pandas as pd
import re
import os
from uuid import uuid4
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import dataset.Org_selection as Org_selection
import tkinter as tk
from tkinter import filedialog
import simple_salesforce as sf
import json

# --- Org selection as picklist ---
def select_org(orgs):
    import tkinter as tk
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

import json
with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
    creds = json.load(f)
orgs = list(creds.keys())
selected_org = select_org(orgs)
if not selected_org or selected_org not in creds:
    raise ValueError(f"Org '{selected_org}' not found in credentials file.")

# --- Establish Salesforce connection ---
sf_conn = sf.Salesforce(
    username=creds[selected_org]['username'],
    password=creds[selected_org]['password'],
    security_token=creds[selected_org]['security_token'],
    domain=creds[selected_org]['domain']
)

# --- Select Salesforce Object from dropdown ---
def select_salesforce_object(sf_conn):
    """Display a dropdown to select a Salesforce object from the org."""
    import tkinter as tk
    
    # Get all Salesforce objects
    try:
        object_list = list(sf_conn.describe()['sobjects'])
        object_names = [obj['name'] for obj in object_list]
        object_names.sort()
        
        if not object_names:
            raise ValueError("No Salesforce objects found in the org.")
    except Exception as e:
        raise ValueError(f"Error fetching Salesforce objects: {e}")
    
    selected = {'value': None}
    def on_select(event=None):
        sel = listbox.curselection()
        if sel:
            selected['value'] = listbox.get(sel[0])
            win.destroy()
    
    def on_filter(*args):
        filter_text = filter_var.get().lower()
        listbox.delete(0, tk.END)
        for obj in object_names:
            if filter_text in obj.lower():
                listbox.insert(tk.END, obj)
    
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Salesforce Object Selection")
    win.geometry("800x600")
    win.grab_set()
    
    tk.Label(win, text="Type to filter, then select Salesforce object for validation:").pack(pady=10)
    
    # Filter entry
    filter_var = tk.StringVar()
    filter_var.trace_add('write', on_filter)
    filter_entry = tk.Entry(win, textvariable=filter_var, width=80)
    filter_entry.pack(padx=20, pady=10)
    filter_entry.focus_set()
    
    # Object listbox
    listbox = tk.Listbox(win, selectmode=tk.SINGLE, width=100, height=30)
    for obj in object_names:
        listbox.insert(tk.END, obj)
    listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
    
    # Bind events
    listbox.bind('<Double-1>', on_select)
    listbox.bind('<Return>', on_select)
    
    # Select button
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    
    win.wait_window()
    root.destroy()
    return selected['value']

object_name = select_salesforce_object(sf_conn)
if not object_name:
    raise ValueError("No Salesforce object selected.")

print(f"Selected Salesforce object: {object_name}")

# Create folder structure: C:\DM_toolkit\Validation\OrgName\ObjectName\SchemaValidation\
object_folder = os.path.join("Validation", selected_org, object_name)
schema_validation_folder = os.path.join(object_folder, "SchemaValidation")
# Ensure the schema validation folder exists
os.makedirs(schema_validation_folder, exist_ok=True)

# Set default location for details.csv file selection
default_details_folder = os.path.join(r"C:\DM_toolkit\DataFiles", selected_org, object_name)
details_path = tk.filedialog.askopenfilename(
    title="Select details file",
    initialdir=default_details_folder if os.path.exists(default_details_folder) else r"C:\DM_toolkit\DataFiles",
    filetypes=[("CSV files", "*.csv"), ("All files", "*")]
)
# details_path = os.path.join(object_folder, "details.csv")


# --- File open dialog for data file ---
tk.Tk().withdraw()
file_name = filedialog.askopenfilename(
    title="Select data file for validation",
    filetypes=[("CSV files", "*.csv"), ("All files", "*")]
)
if not file_name:
    raise ValueError("No data file selected.")
data_path = file_name

# Load the CSV files
mapping_df = pd.read_csv(details_path)
data_df = pd.read_csv(data_path, low_memory=False)

# Initialize the Issues column
data_df['Issues'] = ''

# Helper function to validate email format
def is_valid_email(email):
    # Handle non-string inputs (e.g., bool, float, etc.)
    if pd.isna(email) or email == '':
        return True  # Allow null/empty if not required
    # Convert to string to handle non-string types like bool
    email_str = str(email).strip()
    if email_str.lower() in ['true', 'false', '']:  # Skip boolean-like strings
        return True
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, email_str))

# Validation 1 & 3: Check for required fields (mapping.csv Required == True)
required_fields = mapping_df[mapping_df['Required'] == True]['Field Name'].tolist()

# --- NEW: Master-Detail Validation ---
print("\n" + "="*80)
print("MASTER-DETAIL RELATIONSHIP VALIDATION")
print("="*80)

try:
    from master_detail_validation_helper import (
        identify_master_detail_fields_for_validation,
        validate_master_detail_field_required
    )
    
    # Get object metadata
    object_metadata = getattr(sf_conn, object_name).describe()
    md_fields = identify_master_detail_fields_for_validation(object_metadata['fields'])
    
    if md_fields:
        print(f"\n🔗 Found {len(md_fields)} Master-Detail field(s)")
        
        md_issues = []
        for md_field_name, md_field_info in md_fields.items():
            if md_field_name in data_df.columns:
                # Validate that Master-Detail field has no NULL values
                md_validation = validate_master_detail_field_required(
                    md_field_name,
                    md_field_info,
                    data_df
                )
                
                print(f"\n{md_field_name} → {md_field_info['parent_object']}")
                print(f"  Status: {md_validation['message']}")
                
                # Add Master-Detail issues to data
                if md_validation['missing_count'] > 0:
                    for row_idx in md_validation['null_rows']:
                        data_df.loc[row_idx, 'Issues'] = (
                            data_df.loc[row_idx, 'Issues'] + 
                            f"🚫 CRITICAL: Master-Detail field '{md_field_name}' is NULL (Master-Detail relationships are MANDATORY); "
                        )
                    md_issues.append(f"{md_field_name}: {md_validation['missing_count']} missing values")
        
        # Summary
        if md_issues:
            print(f"\n❌ Master-Detail Issues Found:")
            for issue in md_issues:
                print(f"   - {issue}")
        else:
            print("\n✅ All Master-Detail fields are valid")
        
        # Add cascading delete warning
        print("\n⚠️  CASCADING DELETE WARNING:")
        for md_field_name, md_field_info in md_fields.items():
            print(f"   - If parent {md_field_info['parent_object']} is deleted, all child records will be deleted")
    else:
        print("✅ No Master-Detail relationships found for this object")

except ImportError:
    print("⚠️  Master-Detail validation module not available - skipping")
except Exception as e:
    print(f"⚠️  Error during Master-Detail validation: {str(e)}")

# --- End Master-Detail Validation ---

for field in required_fields:
    if field in data_df.columns:
        # Check for null values in required fields
        null_rows = data_df[field].isna() | (data_df[field] == '')
        if null_rows.any():
            data_df.loc[null_rows, 'Issues'] = data_df.loc[null_rows, 'Issues'] + f"Required field '{field}' data is missing; "

# Validation 2: Check if all fields in data.csv are present in mapping.csv
data_fields = data_df.columns.tolist()
missing_fields = [field for field in data_fields if field not in mapping_df['Field Name'].tolist() and field != 'Issues']
if missing_fields:
    print(f"Fields in sql_{selected_org}__{object_name}.csv not present in Mapping.csv: {missing_fields}")
else:
    print(f"All fields in sql_{selected_org}__{object_name}.csv are present in Mapping.csv")

# Validation 4: Email validation for columns containing 'email' in their name
email_columns = [col for col in data_df.columns if 'email' in col.lower()]
for email_col in email_columns:
    invalid_emails = data_df[email_col].apply(lambda x: not is_valid_email(x))
    if invalid_emails.any():
        data_df.loc[invalid_emails, 'Issues'] = data_df.loc[invalid_emails, 'Issues'] + f"Invalid email format in '{email_col}'; "

# Validation 5: Check for unique fields (mapping.csv Unique == True)
unique_fields = mapping_df[mapping_df['Unique'] == True]['Field Name'].tolist()
for field in unique_fields:
    if field in data_df.columns:
        # Check for duplicate values (ignoring NaN)
        duplicates = data_df[field].duplicated(keep=False) & data_df[field].notna()
        if duplicates.any():
            data_df.loc[duplicates, 'Issues'] = data_df.loc[duplicates, 'Issues'] + f"Duplicate value in unique field '{field}'; "

# Validation 6: Check picklist values (API names)
picklist_fields = mapping_df[mapping_df['Type'] == 'picklist'][['Field Name', 'Picklist Values']].dropna()
for _, row in picklist_fields.iterrows():
    field = row['Field Name']
    # Valid API names that should be present in uploaded files
    valid_api_names = [val.strip() for val in row['Picklist Values'].split(',') if val.strip()]
    
    if field in data_df.columns:
        # Check if values in data file match valid picklist API names (ignoring NaN)
        invalid_values = data_df[field].apply(
            lambda x: str(x).strip() not in valid_api_names 
            if pd.notna(x) and str(x).strip() != '' 
            else False
        )
        
        if invalid_values.any():
            # Get the invalid values for better error reporting
            invalid_vals = data_df.loc[invalid_values, field].unique()
            invalid_vals_str = ", ".join([str(v) for v in invalid_vals if pd.notna(v)])
            
            data_df.loc[invalid_values, 'Issues'] = (
                data_df.loc[invalid_values, 'Issues'] + 
                f"Invalid picklist API name in '{field}' (found: {invalid_vals_str}, valid: {', '.join(valid_api_names)}); "
            )

# Clean up Issues column (remove trailing semicolons and spaces)
data_df['Issues'] = data_df['Issues'].str.rstrip('; ')

# Check number of rows with issues
issues_count = len(data_df[data_df['Issues'] != ''])
print(f"Number of rows with issues: {issues_count}")

# Save the validated data
if issues_count <= 900000:
    # Save to single SchemaValidation_SelectedObject.csv in SchemaValidation folder
    validated_path = os.path.join(schema_validation_folder, f'SchemaValidation_{object_name}.csv')
    data_df.to_csv(validated_path, index=False)
    print(f"Validation complete. Output saved to '{validated_path}'")
else:
    # Create new folder for split files within SchemaValidation
    split_folder = os.path.join(schema_validation_folder, 'SplitFiles')
    os.makedirs(split_folder, exist_ok=True)
    
    # Save main file (complete dataset) as SchemaValidation_SelectedObject.csv
    main_file_path = os.path.join(schema_validation_folder, f'SchemaValidation_{object_name}.csv')
    data_df.to_csv(main_file_path, index=False)
    print(f"Main file saved to '{main_file_path}'")
    
    # Calculate number of files (500,000 records per file)
    records = len(data_df)
    file_count = records // 500000 + (1 if records % 500000 else 0)
    print(f"Splitting {records} records into {file_count} files")
    
    # Split and save files in SplitFiles subfolder
    for i in range(file_count):
        start_idx = i * 500000
        end_idx = min((i + 1) * 500000, records)
        split_df = data_df.iloc[start_idx:end_idx]
        split_file_path = os.path.join(split_folder, f'validated_part_{i + 1}.csv')
        split_df.to_csv(split_file_path, index=False)
        print(f"Saved file {i + 1} with {len(split_df)} records to '{split_file_path}'")

# Return the required columns from data_df
required_cols = mapping_df[mapping_df['Required'] == True]['Field Name'].tolist()
if all(col in data_df.columns for col in required_cols):
    print("All required fields are present")
    output_df = data_df[required_cols + ['Issues']]
else:
    missing_required = [col for col in required_cols if col not in data_df.columns]
    print(f"Missing required fields: {missing_required}")
    output_df = None

# Display the first few rows of the output (for verification)
if output_df is not None:
    print(output_df.head())

# --- Cleanup and completion ---
import atexit
def cleanup_tkinter():
    try:
        for widget in tk._default_root.winfo_children():
            widget.destroy()
        tk._default_root.quit()
        tk._default_root.destroy()
    except:
        pass

atexit.register(cleanup_tkinter)

print("Validation completed successfully!")
print(f"Object: {object_name}")
print(f"Org: {selected_org}")
print(f"Output folder: {schema_validation_folder}")

# Show completion message
try:
    import tkinter.messagebox
    root = tk.Tk()
    root.withdraw()
    tkinter.messagebox.showinfo("Validation Complete", 
                               f"Validation completed successfully!\n\n"
                               f"Object: {object_name}\n"
                               f"Org: {selected_org}\n"
                               f"Rows with issues: {issues_count}\n"
                               f"Output saved to: {schema_validation_folder}")
    root.destroy()
except:
    pass