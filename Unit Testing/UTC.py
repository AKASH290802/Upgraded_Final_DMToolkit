import pandas as pd
import os
import logging
from simple_salesforce import Salesforce
import json
import sys

# Fix import for Connections and Org_selection
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path

import dataset.Connections as Connections
import dataset.Org_selection as Org_selection


# Basic logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('validation.log'),
        logging.StreamHandler()
    ]
)

# Function to load data from Excel file
def load_excel_data(file_path):
    try:
        excel_data = pd.ExcelFile(file_path)
        sheets = excel_data.sheet_names
        data_frames = {sheet: excel_data.parse(sheet) for sheet in sheets}
        return data_frames
    except Exception as e:
        logging.error(f"Error loading Excel file: {e}")
        return None

# Function to connect to Salesforce (use a Tkinter dropdown for org selection)
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

with open(r"C:\DM_toolkit\Services\linkedservices.json", "r") as login_file:
    creds = json.load(login_file)
orgs = list(creds.keys())
selected_org = select_org(orgs)
if not selected_org or selected_org not in creds:
    raise ValueError(f"Org '{selected_org}' not found in credentials file.")

sf = Salesforce(
    username=creds[selected_org]['username'],
    password=creds[selected_org]['password'],
    security_token=creds[selected_org]['security_token'],
    domain=creds[selected_org]['domain']
)

# Function to retrieve Salesforce data for a specified object
def get_salesforce_data(sf, object_name):
    try:
        query = f"SELECT * FROM {object_name}"
        data = sf.query_all(query)
        records = data['records']
        df = pd.DataFrame(records)
        return df
    except Exception as e:
        logging.error(f"Error retrieving Salesforce data: {e}")
        return None

# Function to run unit tests
def run_tests(raw_data, sf_data):
    try:
        # Test 1: Record count match
        raw_count = len(raw_data)
        sf_count = len(sf_data)
        logging.info(f"Record count - Raw data: {raw_count}, Salesforce data: {sf_count}")
        assert raw_count == sf_count, "Record count mismatch"

        # Test 2: Picklist value consistency
        # Assuming 'PicklistField' is a picklist field in Salesforce
        raw_picklist_values = raw_data['PicklistField'].unique()
        sf_picklist_values = sf_data['PicklistField'].unique()
        logging.info(f"Picklist values - Raw data: {raw_picklist_values}, Salesforce data: {sf_picklist_values}")
        assert set(raw_picklist_values) == set(sf_picklist_values), "Picklist value mismatch"

        # Test 3: Successful data load verification
        # Assuming 'Id' is a unique identifier in Salesforce
        raw_ids = set(raw_data['Id'])
        sf_ids = set(sf_data['Id'])
        logging.info(f"IDs - Raw data: {len(raw_ids)}, Salesforce data: {len(sf_ids)}")
        assert raw_ids == sf_ids, "Data load verification failed"

        # Test 4: Record presence in both datasets
        missing_in_sf = raw_ids - sf_ids
        missing_in_raw = sf_ids - raw_ids
        logging.info(f"Missing in Salesforce: {missing_in_sf}, Missing in raw data: {missing_in_raw}")
        assert not missing_in_sf and not missing_in_raw, "Record presence mismatch"

        # Test 5: Lookup field validation
        # Assuming 'LookupField' is a lookup field in Salesforce
        raw_lookup_values = raw_data['LookupField'].unique()
        sf_lookup_values = sf_data['LookupField'].unique()
        logging.info(f"Lookup values - Raw data: {raw_lookup_values}, Salesforce data: {sf_lookup_values}")
        assert set(raw_lookup_values) == set(sf_lookup_values), "Lookup field validation failed"

        # Test 6: Data format consistency
        raw_dtypes = raw_data.dtypes
        sf_dtypes = sf_data.dtypes
        logging.info(f"Data types - Raw data: {raw_dtypes}, Salesforce data: {sf_dtypes}")
        assert raw_dtypes.equals(sf_dtypes), "Data format consistency failed"

        logging.info("All tests passed successfully")
    except AssertionError as e:
        logging.error(f"Test failed: {e}")

# Main function
def main():
    try:
        # Load raw data from a user-selected Excel or CSV file
        import tkinter as tk
        import tkinter.filedialog

        tk.Tk().withdraw()
        raw_data_file = tkinter.filedialog.askopenfilename(
            title="Select Raw Data File (Excel or CSV)",
            filetypes=[("Excel files", "*.xlsx;*.xls"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not raw_data_file:
            logging.error("No raw data file selected.")
            return

        # Load raw data based on file extension
        if raw_data_file.lower().endswith(('.xlsx', '.xls')):
            raw_data_frames = pd.read_excel(raw_data_file, sheet_name=None, engine='openpyxl')
        elif raw_data_file.lower().endswith('.csv'):
            # For CSV, load as a single sheet dict
            raw_data_frames = {'Sheet1': pd.read_csv(raw_data_file)}
        else:
            logging.error("Unsupported file type selected.")
            return

        # Locate the generated Salesforce Excel file
        # PATCH: Prompt user for Salesforce object name instead of using sf.object_name (which is not set)
        import tkinter.simpledialog
        object_name = tkinter.simpledialog.askstring(
            "Salesforce Object Name",
            "Enter the Salesforce object name (folder name) to validate:"
        )
        if not object_name:
            logging.error("No Salesforce object name provided.")
            return

        sf_excel_file = os.path.join("DataFiles", selected_org, object_name, f"{selected_org}_{object_name}_details.xlsx")

        if not os.path.exists(sf_excel_file):
            logging.error(f"Salesforce data file not found: {sf_excel_file}")
            return

        # Load Salesforce data from the generated Excel file
        sf_data_frames = pd.read_excel(sf_excel_file, sheet_name=None, engine='openpyxl')

        # Run tests for each sheet in the raw data
        for sheet_name, raw_data in raw_data_frames.items():
            logging.info(f"Running tests for sheet: {sheet_name}")
            if sheet_name in sf_data_frames:
                sf_data = sf_data_frames[sheet_name]
                run_tests(raw_data, sf_data)
            else:
                logging.warning(f"Sheet {sheet_name} not found in Salesforce data")

    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    main()
