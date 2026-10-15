import sys
sys.path.append(r"C:\DM_toolkit")
import pandas as pd
import json
import tkinter as tk
from tkinter import filedialog, simpledialog
import simple_salesforce as sf
import os

# --- Salesforce Org Selection ---
def select_org(orgs):
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

with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
    creds = json.load(f)
orgs = list(creds.keys())
selected_org = select_org(orgs)
if not selected_org or selected_org not in creds:
    raise ValueError(f"Org '{selected_org}' not found in credentials file.")

sf_conn = sf.Salesforce(
    username=creds[selected_org]['username'],
    password=creds[selected_org]['password'],
    security_token=creds[selected_org]['security_token'],
    domain=creds[selected_org]['domain']
)
print('Salesforce connected successfully')

# --- Select Data File ---
tk.Tk().withdraw()
file_path = filedialog.askopenfilename(
    title="Select source data CSV file",
    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
)
if not file_path:
    raise ValueError("No CSV file selected.")

if file_path.endswith('.xls'):
    source_df = pd.read_excel(file_path)
elif file_path.endswith('.xlsx'):
    source_df = pd.read_excel(file_path)
elif file_path.endswith('.csv'):
    try:
        source_df = pd.read_csv(file_path)
    except UnicodeDecodeError:
        source_df = pd.read_csv(file_path, encoding='latin1')
print("Source data\n", source_df.head(5))

# --- Select Salesforce Object ---
object_list = list(sf_conn.describe()['sobjects'])
object_names = [obj['name'] for obj in object_list]
filtered_objects = []
for name in object_names:
    if name.lower() == 'account' or 'wod' in name.lower():
        filtered_objects.append(name)
filtered_objects.sort()
if not filtered_objects:
    raise ValueError("No eligible Salesforce objects found (Account or objects containing 'wod').")

def select_salesforce_object(object_list):
    selected = {'value': None}
    def on_select(event=None):
        sel = listbox.curselection()
        if sel:
            selected['value'] = listbox.get(sel[0])
            win.destroy()
    def on_filter(*args):
        filter_text = filter_var.get().lower()
        listbox.delete(0, tk.END)
        for obj in object_list:
            if filter_text in obj.lower():
                listbox.insert(tk.END, obj)
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Salesforce Object Selection")
    win.geometry("800x600")
    win.grab_set()
    tk.Label(win, text="Type to filter, then select Salesforce object to load to:").pack(pady=10)
    filter_var = tk.StringVar()
    filter_var.trace_add('write', on_filter)
    filter_entry = tk.Entry(win, textvariable=filter_var, width=80)
    filter_entry.pack(padx=20, pady=10)
    filter_entry.focus_set()
    listbox = tk.Listbox(win, selectmode=tk.SINGLE, width=100, height=30)
    for obj in object_list:
        listbox.insert(tk.END, obj)
    listbox.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
    listbox.bind('<Double-1>', on_select)
    listbox.bind('<Return>', on_select)
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    return selected['value']

object_name = select_salesforce_object(filtered_objects)
print(f"Selected Salesforce object: {object_name}")

# --- Fetch Salesforce Object Metadata ---
sf_obj_desc = getattr(sf_conn, object_name).describe()
sf_fields = {f['name']: f for f in sf_obj_desc['fields']}

# --- Fetch Salesforce Data ---
# Salesforce does not support SELECT *; must specify fields explicitly
sf_field_names = [f['name'] for f in sf_obj_desc['fields']]
query = f"SELECT {', '.join(sf_field_names)} FROM {object_name}"
sf_data = sf_conn.query_all(query)
sf_df = pd.DataFrame(sf_data['records']).drop(columns='attributes', errors='ignore')

# --- Unit Test Results List ---
unit_tests = []

# 1. Record count matching
if len(source_df) == len(sf_df):
    unit_tests.append(("unittest001", "Record count match", "PASS", "Record count matches"))
else:
    unit_tests.append(("unittest001", "Record count match", "FAIL", f"Source: {len(source_df)}, Salesforce: {len(sf_df)}"))

# 2. Picklist value check
picklist_failures = []
for col in source_df.columns:
    if col in sf_fields and sf_fields[col]['type'] == 'picklist':
        valid_values = [v['value'] for v in sf_fields[col]['picklistValues'] if not v.get('inactive', False)]
        invalid = source_df[~source_df[col].isin(valid_values) & source_df[col].notna()]
        if not invalid.empty:
            picklist_failures.append(col)
if not picklist_failures:
    unit_tests.append(("unittest002", "Picklist value check", "PASS", "All picklist values valid"))
else:
    unit_tests.append(("unittest002", "Picklist value check", "FAIL", f"Invalid picklist values in: {', '.join(picklist_failures)}"))

# 3. Email unit testing
import re
email_cols = [col for col in source_df.columns if 'email' in col.lower()]
email_failures = []
email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
for col in email_cols:
    invalid = source_df[col].dropna().apply(lambda x: not re.match(email_regex, str(x)))
    if invalid.any():
        email_failures.append(col)
if not email_failures:
    unit_tests.append(("unittest003", "Email format check", "PASS", "All emails valid"))
else:
    unit_tests.append(("unittest003", "Email format check", "FAIL", f"Invalid emails in: {', '.join(email_failures)}"))

# 4. Duplicate unit testing
duplicate_failures = []
for col in source_df.columns:
    if col in sf_fields and sf_fields[col].get('unique', False):
        if source_df[col].duplicated(keep=False).any():
            duplicate_failures.append(col)
if not duplicate_failures:
    unit_tests.append(("unittest004", "Duplicate check", "PASS", "No duplicates in unique fields"))
else:
    unit_tests.append(("unittest004", "Duplicate check", "FAIL", f"Duplicates found in: {', '.join(duplicate_failures)}"))

# 5. Correct data loaded (example: name == 'dummy')
if 'Name' in source_df.columns and 'Name' in sf_df.columns:
    dummy_in_source = source_df['Name'].str.lower() == 'dummy'
    dummy_in_sf = sf_df['Name'].str.lower() == 'dummy'
    if dummy_in_source.any() and dummy_in_sf.any():
        unit_tests.append(("unittest005", "Correct data loaded (dummy name)", "PASS", "Dummy name found in both source and Salesforce"))
    else:
        unit_tests.append(("unittest005", "Correct data loaded (dummy name)", "FAIL", "Dummy name not found in both source and Salesforce"))
else:
    unit_tests.append(("unittest005", "Correct data loaded (dummy name)", "SKIP", "Name field not present in both source and Salesforce"))

# 6. Lookup unit testing
lookup_failures = []
for col in source_df.columns:
    if col in sf_fields and sf_fields[col]['type'] == 'reference':
        required = not sf_fields[col]['nillable']
        if required and source_df[col].isnull().any():
            lookup_failures.append(f"{col} (required)")
        # Optionally, check if lookup values exist in Salesforce (not implemented here for performance)
if not lookup_failures:
    unit_tests.append(("unittest006", "Lookup field check", "PASS", "All required lookup fields populated"))
else:
    unit_tests.append(("unittest006", "Lookup field check", "FAIL", f"Missing required lookup values in: {', '.join(lookup_failures)}"))

# --- Save Results ---
save_root = r"C:\DM_toolkit"
unit_folder = os.path.join(save_root, "Unit Testing Generates", selected_org, object_name)
os.makedirs(unit_folder, exist_ok=True)
excel_path = os.path.join(unit_folder, f"unitTest_{object_name}.xlsx")

df_result = pd.DataFrame(unit_tests, columns=["unit tests", "unit test describe", "status", "status explain"])
df_result.to_excel(excel_path, index=False)
print(f"Unit test results saved to: {excel_path}")
