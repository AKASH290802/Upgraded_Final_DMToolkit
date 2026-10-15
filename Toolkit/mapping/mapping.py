import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import json
import pandas as pd
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

# Function to get field API names for a Salesforce object
def get_salesforce_fields(object_name):
    try:
        # Retrieve object metadata
        schema = getattr(sf_conn, object_name).describe()
        fields = schema['fields']
        # Always include 'Id' as the first field
        field_names = ['Id']
        # Filter updateable fields, excluding 'isdeleted', 'sic', 'createdby'
        excluded_keywords = ['OwnerId','isdeleted', 'sic', 'createdby']
        for field in fields:
            if field['name'] == 'Id':
                continue  # Already added
            if field['updateable'] and not any(keyword.lower() in field['name'].lower() for keyword in excluded_keywords):
                field_names.append(field['name'])
        # Add external id fields if not already present
        external_id_fields = [field['name'] for field in fields if field.get('externalId', False)]
        for ext_id in external_id_fields:
            if ext_id not in field_names:
                field_names.append(ext_id)
        return field_names
    except Exception as e:
        print(f"Error retrieving fields for {object_name}: {e}")
        return []

# Function to generate DataFrame and JSON mapping
def generate_mapping(object_name):
    try:
        # Get Salesforce field API names
        fields = get_salesforce_fields(object_name)
        if not fields:
            print(f"No updateable fields found for {object_name} after filtering")
            return None, {}

        # Create DataFrame with field API names
        df = pd.DataFrame(fields, columns=['Field_API_Name'])
        print(f"DataFrame for {object_name}:\n{df}")

        # Create mapping where each field maps to itself
        mapping = {field: field for field in fields}

        # Save mapping to JSON file in the object folder
        root_folder = "C:\\DM_toolkit\\mapping_logs"
        if not os.path.exists(root_folder):
            os.makedirs(root_folder)
        object_folder = os.path.join(root_folder, selected_org, object_name)
        os.makedirs(object_folder, exist_ok=True)
        output_file = os.path.join(object_folder, "mapping.json")
        with open(output_file, 'w') as f:
            json.dump(mapping, f, indent=4)

        print(f"Mapping file created: {output_file}")
        return df, mapping
    except Exception as e:
        print(f"Error generating mapping for {object_name}: {e}")
        return None, {}

# Generate mapping for the selected object
df, mapping = generate_mapping(object_name)