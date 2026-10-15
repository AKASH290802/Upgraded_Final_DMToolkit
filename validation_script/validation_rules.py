import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import pandas as pd
import json
import re
import dataset.Connections as Connections
import dataset.Org_selection as Org_selection
import tkinter as tk
from tkinter import ttk, messagebox
import os
import simple_salesforce as sf

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

def parse_field_names(formula):
    """Parse field names from the error condition formula."""
    if not formula or formula == 'N/A':
        return 'N/A'
    field_pattern = r'\b[A-Za-z0-9_]+(__c)?\b'
    fields = re.findall(field_pattern, formula)
    salesforce_keywords = {'AND', 'OR', 'NOT', 'IF', 'ISBLANK', 'LEN', 'ISPICKVAL', 'TRUE', 'FALSE', 'NULL'}
    fields = [f for f in fields if f not in salesforce_keywords and not f.isdigit()]
    return ', '.join(fields) if fields else 'N/A'

def get_validation_rules(sf, object_name):
    """Query Salesforce validation rules for a specific object using the Tooling API."""
    try:
        query = f"""
            SELECT Id, ValidationName, EntityDefinition.DeveloperName, Active
            FROM ValidationRule
            WHERE EntityDefinition.DeveloperName = '{object_name}'
        """
        result = sf.toolingexecute('query?q=' + query.replace('\n', ' ').replace('  ', ' '))
        records = result['records']
        if not records:
            print(f"No validation rules found for object {object_name}.")
            return []

        validation_rules = []
        for record in records:
            try:
                metadata_query = f"SELECT Metadata FROM ValidationRule WHERE Id = '{record['Id']}'"
                metadata_result = sf.toolingexecute('query?q=' + metadata_query.replace('\n', ' ').replace('  ', ' '))
                if not metadata_result or 'records' not in metadata_result or not metadata_result['records']:
                    print(f"No metadata returned for Validation Rule {record['ValidationName']} (Id: {record['Id']})")
                    continue
                metadata = metadata_result['records'][0].get('Metadata', {})
                formula = metadata.get('errorConditionFormula', 'N/A')
                rule_info = {
                    'ValidationName': record['ValidationName'],
                    'ObjectName': record['EntityDefinition']['DeveloperName'],
                    'ErrorConditionFormula': formula,
                    'FieldName': parse_field_names(formula),
                    'Active': record['Active'],
                    'ErrorMessage': metadata.get('errorMessage', 'N/A')
                }
                validation_rules.append(rule_info)
            except Exception as e:
                print(f"Error fetching metadata for Validation Rule {record['ValidationName']} (Id: {record['Id']}): {str(e)}")
                continue
        return validation_rules
    except Exception as e:
        print(f"Failed to query validation rules for object {object_name}: {e}")
        return []

def main():
    """Main function to extract and save validation rules for a selected object."""
    try:
        # Print selected org
        print(f"Selected Salesforce org: {selected_org}")

        # Prompt for object name via Tkinter popup (filterable list)
        object_name = select_salesforce_object(filtered_objects)
        if not object_name or object_name not in filtered_objects:
            print("No valid Salesforce object selected. Exiting.")
            return

        print(f"Selected Salesforce object: {object_name}")

        # Get validation rules for the specified object
        records = get_validation_rules(sf_conn, object_name)
        
        # Create DataFrame
        if not records:
            print(f"No validation rules found for object {object_name} or an error occurred.")
            df = pd.DataFrame(columns=['ValidationName', 'ErrorConditionFormula', 'FieldName', 'ObjectName', 'Active'])
        else:
            df = pd.DataFrame(records)

        # Save to CSV
        root_folder = "DataFiles"
        object_folder = os.path.join(root_folder, selected_org, object_name)
        os.makedirs(object_folder, exist_ok=True)
        csv_df = df[['ValidationName', 'ErrorConditionFormula', 'FieldName', 'ObjectName', 'Active']]
        csv_file_path = os.path.join(object_folder, "Formula_validation.csv")
        csv_df.to_csv(csv_file_path, index=False)
        active_count = df['Active'].sum() if not df.empty else 0
        print(f"no of custom validation == {active_count}")
        print(f"Formula_validation file saved at: {csv_file_path}")

    except Exception as e:
        print(f"Error in main execution: {e}")

if __name__ == "__main__":
    main()