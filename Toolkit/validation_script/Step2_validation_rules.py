import sys
import json
import pandas as pd
import os
import requests
import tkinter as tk
from tkinter import ttk, messagebox
import simple_salesforce as sf

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

def fetch_validation_rules_with_formula(sf_conn, object_name):
    session_id = sf_conn.session_id
    instance_url = sf_conn.sf_instance
    headers = {
        'Authorization': f'Bearer {session_id}',
        'Content-Type': 'application/json'
    }
    # Step 1: Get all validation rule Ids for the object
    val_url = f"https://{instance_url}/services/data/v59.0/tooling/query"
    id_query = (
        f"SELECT Id, ValidationName, ErrorMessage, Active, EntityDefinition.QualifiedApiName "
        f"FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}'"
    )
    id_resp = requests.get(val_url, headers=headers, params={'q': id_query})
    id_json = id_resp.json()
    if not isinstance(id_json, dict):
        print("Unexpected response from Salesforce Tooling API (Id query):")
        print(id_json)
        return []
    val_rules = id_json.get('records', [])
    validation_data = []
    # Step 2: For each Id, fetch Metadata (and formula)
    for v in val_rules:
        rule_id = v['Id']
        meta_url = f"https://{instance_url}/services/data/v59.0/tooling/sobjects/ValidationRule/{rule_id}"
        meta_resp = requests.get(meta_url, headers=headers)
        meta_json = meta_resp.json()
        metadata = meta_json.get('Metadata', {})
        formula = metadata.get('errorConditionFormula', '') if isinstance(metadata, dict) else ''
        validation_data.append({
            'ValidationName': v['ValidationName'],
            'ErrorConditionFormula': formula,
            'FieldName': '',  # You can add field parsing logic if needed
            'ObjectName': object_name,
            'Active': v['Active'],
            'ErrorMessage': v['ErrorMessage'],
            'Description': ''
        })
    return validation_data

def main():
    with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
        creds = json.load(f)
    orgs = list(creds.keys())
    selected_org = select_org(orgs)
    if not selected_org or selected_org not in creds:
        print(f"Org '{selected_org}' not found in credentials file.")
        return
    sf_conn = sf.Salesforce(
        username=creds[selected_org]['username'],
        password=creds[selected_org]['password'],
        security_token=creds[selected_org]['security_token'],
        domain=creds[selected_org]['domain']
    )
    # Get filtered Salesforce objects (Account, objects containing 'wod', and custom objects)
    object_list = [obj['name'] for obj in sf_conn.describe()['sobjects']
                   if (obj['name'].endswith('__c') or obj['name'].lower() == 'account' or 'wod' in obj['name'].lower())]
    object_list.sort()
    if not object_list:
        print("No eligible Salesforce objects found.")
        return
    object_name = select_salesforce_object(object_list)
    if not object_name or object_name not in object_list:
        print("No valid Salesforce object selected. Exiting.")
        return
    print(f"Selected Salesforce object: {object_name}")
    records = fetch_validation_rules_with_formula(sf_conn, object_name)
    df = pd.DataFrame(records)
    root_folder = "DataFiles"
    object_folder = os.path.join(root_folder, selected_org, object_name)
    os.makedirs(object_folder, exist_ok=True)
    csv_file_path = os.path.join(object_folder, "Formula_validation.csv")
    df.to_csv(csv_file_path, index=False)
    print(f"Formula_validation file saved at: {csv_file_path}")

if __name__ == "__main__":
    main()