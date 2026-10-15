import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import pandas as pd
import json
import tkinter as tk
from tkinter import filedialog
import simple_salesforce as sf
import os  # Added import for os
import logging

# Salesforce org selection
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

with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
    creds = json.load(f)
orgs = list(creds.keys())
selected_org = select_org(orgs)
if not selected_org or selected_org not in creds:
    raise ValueError(f"Org '{selected_org}' not found in credentials file.")

# Connect to Salesforce
sf_conn = sf.Salesforce(
    username=creds[selected_org]['username'],
    password=creds[selected_org]['password'],
    security_token=creds[selected_org]['security_token'],
    domain=creds[selected_org]['domain']
)
print('Salesforce connected successfully')

# File dialog to select CSV
tk.Tk().withdraw()
cdf_path = filedialog.askopenfilename(
    title="Select customer data CSV file",
    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
)
if not cdf_path:
    raise ValueError("No CSV file selected.")
cdf = pd.read_csv(cdf_path)

print("Customer data\n", cdf.head(5))

# Get filtered Salesforce objects (Account and objects containing 'wod')
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
    import tkinter as tk
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

# Use the filterable selection dialog (Tkinter-based)
object_name = select_salesforce_object(filtered_objects)
print(f"Selected Salesforce object: {object_name}")

# --- UNIT TESTING 01 ---
def get_sf_query(default_query):
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    query = simpledialog.askstring("Salesforce Query", "Enter Salesforce query:", initialvalue=default_query)
    root.destroy()
    if not query:
        raise ValueError("No Salesforce query provided.")
    return query

default_query = f"SELECT Id FROM {object_name}"
query = get_sf_query(default_query)

# Extract all data from Salesforce for the selected object/query
s_data = sf_conn.query_all(query)
s_df = pd.DataFrame(s_data['records']).drop(columns='attributes', errors='ignore')

def run_tests(raw_data, sf_data):
    results = []
    # Test 1: Record count match
    try:
        raw_count = len(raw_data)
        sf_count = len(sf_data)
        logging.info(f"Record count - Raw data: {raw_count}, Salesforce data: {sf_count}")
        assert raw_count == sf_count, "Record count mismatch"
        results.append(("unittest001", "Record count match", "PASS", "Record count matches"))
    except AssertionError as e:
        results.append(("unittest001", "Record count match", "FAIL", str(e)))

    # Test 2: Picklist value consistency
    try:
        raw_picklist_values = set(raw_data['PicklistField'].unique())
        sf_picklist_values = set(sf_data['PicklistField'].unique())
        logging.info(f"Picklist values - Raw data: {raw_picklist_values}, Salesforce data: {sf_picklist_values}")
        assert raw_picklist_values == sf_picklist_values, "Picklist value mismatch"
        results.append(("unittest002", "Picklist value consistency", "PASS", "Picklist values match"))
    except Exception as e:
        results.append(("unittest002", "Picklist value consistency", "FAIL", str(e)))

    # Test 3: Successful data load verification
    try:
        raw_ids = set(raw_data['Id'])
        sf_ids = set(sf_data['Id'])
        logging.info(f"IDs - Raw data: {len(raw_ids)}, Salesforce data: {len(sf_ids)}")
        assert raw_ids == sf_ids, "Data load verification failed"
        results.append(("unittest003", "Successful data load verification", "PASS", "All IDs match"))
    except Exception as e:
        results.append(("unittest003", "Successful data load verification", "FAIL", str(e)))

    # Test 4: Record presence in both datasets
    try:
        raw_ids = set(raw_data['Id'])
        sf_ids = set(sf_data['Id'])
        missing_in_sf = raw_ids - sf_ids
        missing_in_raw = sf_ids - raw_ids
        logging.info(f"Missing in Salesforce: {missing_in_sf}, Missing in raw data: {missing_in_raw}")
        assert not missing_in_sf and not missing_in_raw, "Record presence mismatch"
        results.append(("unittest004", "Record presence in both datasets", "PASS", "All records present in both datasets"))
    except Exception as e:
        results.append(("unittest004", "Record presence in both datasets", "FAIL", str(e)))

    # Test 5: Lookup field validation
    try:
        raw_lookup_values = set(raw_data['LookupField'].unique())
        sf_lookup_values = set(sf_data['LookupField'].unique())
        logging.info(f"Lookup values - Raw data: {raw_lookup_values}, Salesforce data: {sf_lookup_values}")
        assert raw_lookup_values == sf_lookup_values, "Lookup field validation failed"
        results.append(("unittest005", "Lookup field validation", "PASS", "Lookup values match"))
    except Exception as e:
        results.append(("unittest005", "Lookup field validation", "FAIL", str(e)))

    # Test 6: Data format consistency
    try:
        raw_dtypes = raw_data.dtypes
        sf_dtypes = sf_data.dtypes
        logging.info(f"Data types - Raw data: {raw_dtypes}, Salesforce data: {sf_dtypes}")
        assert raw_dtypes.equals(sf_dtypes), "Data format consistency failed"
        results.append(("unittest006", "Data format consistency", "PASS", "Data types match"))
    except Exception as e:
        results.append(("unittest006", "Data format consistency", "FAIL", str(e)))

    return results


# Prepare unit test results
unit_tests = []
if len(cdf) <= len(s_df):
    status = "PASS"
    status_explain = "Input file row count is less than or equal to Salesforce data row count."
else:
    status = "FAIL"
    status_explain = f"cdf count = {len(cdf)}, Salesforce count = {len(s_df)}"

unit_tests.append({
    "unit tests": "unittest001",
    "unit test describe": "Check all data from input file is available in Salesforce (row count match or less)",
    "status": status,
    "status explain": status_explain
})

# Save results to Excel
save_root = r"C:\DM_toolkit"
unit_folder = os.path.join(save_root, "Unit Testing Generates", selected_org, object_name)
os.makedirs(unit_folder, exist_ok=True)
excel_path = os.path.join(unit_folder, f"unitTest_{object_name}.xlsx")
excel_path2 = os.path.join(unit_folder, f"unittest_{object_name}.xlsx")

df_result = pd.DataFrame(unit_tests)
df_result.to_excel(excel_path, index=False)

# Run additional unit tests and save results to unittest_{object_name}.xlsx
results = run_tests(cdf, s_df)
df_result2 = pd.DataFrame(results, columns=["unit tests", "unit test describe", "status", "status explain"])
df_result2.to_excel(excel_path2, index=False)

print(f"Unit test results saved to: {excel_path}")
print(f"run_tests results saved to: {excel_path2}")


# Example usage after loading cdf and s_df:
# results = run_tests(cdf, s_df)
# df_result = pd.DataFrame(results, columns=["unit tests", "unit test describe", "status", "status explain"])
# df_result.to_excel(excel_path, index=False)
# print(f"Unit test results saved to: {excel_path}")
