import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import json
import dataset.Connections as Connections
import dataset.Org_selection as Org_selection
import pandas as pd
import requests
import os
import tkinter as tk
from tkinter import ttk
import simple_salesforce as sf

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

sf_conn = sf.Salesforce(
    username=creds[selected_org]['username'],
    password=creds[selected_org]['password'],
    security_token=creds[selected_org]['security_token'],
    domain=creds[selected_org]['domain']
)

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
if not object_name or object_name not in filtered_objects:
    raise ValueError("No valid Salesforce object selected.")
print(f"Selected Salesforce object: {object_name}")

SalesForce = sf_conn
session_id = SalesForce.session_id
instance_url = SalesForce.sf_instance

# === Describe Fields ===
fields_info = []
schema = getattr(SalesForce, object_name).describe()
for field in schema['fields']:
    picklist_values = [p['value'] for p in field.get('picklistValues', []) if not p.get('inactive', False)]
    fields_info.append({
        'Field Name': field['name'],
        'Label': field['label'],
        'Type': field['type'],
        'Required': not field['nillable'],
        'Unique': field.get('unique', False),
        'Picklist Values': ", ".join(picklist_values)
    })

fields_df = pd.DataFrame(fields_info)

# === Fetch Validation Rules using Tooling API ===
headers = {
    'Authorization': f'Bearer {session_id}',
    'Content-Type': 'application/json'
}

val_url = f"https://{instance_url}/services/data/v59.0/tooling/query"
val_query = f"SELECT Id, ValidationName, ErrorDisplayField, ErrorMessage, Active, Description, EntityDefinition.QualifiedApiName FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}'"
val_resp = requests.get(val_url, headers=headers, params={'q': val_query})
val_rules = val_resp.json().get('records', [])

validation_data = [{
    'Rule Name': v['ValidationName'],
    'Error Field': v['ErrorDisplayField'],
    'Error Message': v['ErrorMessage'],
    'Active': v['Active'],
    'Description': v.get('Description', '')
} for v in val_rules]

validation_df = pd.DataFrame(validation_data)

# === Fetch Triggers (names only) ===
trigger_query = f"SELECT Name, TableEnumOrId, Status FROM ApexTrigger WHERE TableEnumOrId = '{object_name}'"
trigger_resp = requests.get(val_url, headers=headers, params={'q': trigger_query})
triggers = trigger_resp.json().get('records', [])

trigger_data = [{
    'Trigger Name': t['Name'],
    'Status': t['Status']
} for t in triggers]

trigger_df = pd.DataFrame(trigger_data)

# === Write to Excel ===
root_folder = "DataFiles"
object_folder = os.path.join(root_folder,selected_org, object_name)

excel_file_name = selected_org+"_"+object_name+"_details.xlsx"
excel_file_path = os.path.join(object_folder, excel_file_name)

os.makedirs(object_folder, exist_ok=True)

with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
    fields_df.to_excel(writer, sheet_name=object_name, index=False)
    if not validation_df.empty:
        validation_df.to_excel(writer, sheet_name="Validation", index=False)
    if not trigger_df.empty:
        trigger_df.to_excel(writer, sheet_name="Triggers", index=False)
fields_df.to_csv(os.path.join(object_folder, "details.csv"), index=False)
validation_df.to_csv(os.path.join(object_folder, "validation.csv"), index=False)
print(f"\nExcel file created: {excel_file_path}")
