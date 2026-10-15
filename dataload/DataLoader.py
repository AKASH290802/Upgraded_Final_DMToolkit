import sys
import os
# Get the project root directory dynamically
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)  # Add project root to sys.path
import pandas as pd
import json
import simple_salesforce as sf
import tkinter
import tkinter.filedialog
import tkinter.messagebox
import os
import tkinter.simpledialog
import dataset.Connections as Connections
from dataload.batch_config import select_batch_and_parallel_settings, simple_batch_size_dialog
import concurrent.futures
import threading
import time
import datetime
import csv

# --- Step 1: Select Salesforce Org ---
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

with open(os.path.join(project_root, 'Services', 'linkedservices.json'), 'r') as f:
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

# --- Ask user for data source ---
def select_data_source():
    import tkinter as tk
    selected = {'value': None}
    def on_select():
        selected['value'] = var.get()
        win.destroy()
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Select Data Source")
    win.geometry("400x200")
    win.grab_set()
    tk.Label(win, text="Select data source:").pack(pady=20)
    var = tk.StringVar(win)
    var.set("file")
    dropdown = tk.OptionMenu(win, var, "file", "sql")
    dropdown.config(width=30)
    dropdown.pack(padx=20, pady=20)
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    return selected['value']

data_source = select_data_source()

if data_source == "sql":
    # Use Connections.get_sql_connection for SQL connection
    sql_conn, engine = Connections.get_sql_connection()
    query = tkinter.simpledialog.askstring("SQL Query", "Enter SQL query to fetch data:")
    if not query:
        raise ValueError("No SQL query provided.")
    df = pd.read_sql(query, engine)
elif data_source == "file":
    tkinter.Tk().withdraw()
    # Set default directory to DataLoader_Logs folder
    default_data_dir = os.path.join(project_root, 'DataLoader_Logs')
    file = tkinter.filedialog.askopenfilename(
        title="Select CSV or Excel File",
        initialdir=default_data_dir,
        filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
    )
    if not file:
        print("No file selected. Operation cancelled.")
        tkinter.messagebox.showinfo("No File Selected", "No data file was selected. Operation cancelled.")
        exit()
    
    # Check if file exists
    if not os.path.exists(file):
        print(f"Selected file does not exist: {file}")
        tkinter.messagebox.showerror(
            "File Not Found",
            f"The selected file could not be found:\n\n{file}\n\n"
            f"Please ensure the file exists and try again."
        )
        exit()
    
    # Check file size
    try:
        file_size = os.path.getsize(file)
        if file_size == 0:
            print(f"Selected file is empty (0 bytes): {file}")
            tkinter.messagebox.showerror(
                "Empty File Error",
                f"The selected file is empty (0 bytes):\n\n{file}\n\n"
                f"Please select a file that contains data."
            )
            exit()
        print(f"Reading file: {file} ({file_size:,} bytes)")
    except OSError as e:
        print(f"Cannot access file: {file} - {e}")
        tkinter.messagebox.showerror(
            "File Access Error",
            f"Cannot access the selected file:\n\n{file}\n\n"
            f"Error: {str(e)}\n\n"
            f"Please ensure the file is not locked by another application."
        )
        exit()
    try:
        if file.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        elif file.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            raise ValueError("Unsupported file format. Please select a CSV or Excel file.")
        
        # Validate that we have data
        if df.empty:
            print(f"Selected file: {file}")
            print("Error: The selected file appears to be empty (no data rows found).")
            print("Please check:")
            print("- The file contains data beyond just headers")
            print("- The file is not corrupted")
            print("- The file format is correct (CSV or Excel)")
            tkinter.messagebox.showerror(
                "Empty File Error",
                f"The selected file is empty or contains no data rows.\n\n"
                f"File: {file}\n\n"
                f"Please select a file that contains data."
            )
            exit()
        
        # Validate that we have columns
        if len(df.columns) == 0:
            print(f"Selected file: {file}")
            print("Error: The selected file has no columns.")
            tkinter.messagebox.showerror(
                "Invalid File Error",
                f"The selected file has no columns.\n\n"
                f"File: {file}\n\n"
                f"Please select a valid CSV or Excel file with column headers."
            )
            exit()
        
        print(f"Successfully loaded {len(df)} rows and {len(df.columns)} columns from: {file}")
        print(f"Columns found: {', '.join(df.columns[:10])}" + ("..." if len(df.columns) > 10 else ""))
        
    except pd.errors.EmptyDataError:
        print(f"Selected file: {file}")
        print("Error: The file is completely empty (no data or headers).")
        tkinter.messagebox.showerror(
            "Empty File Error",
            f"The selected file is completely empty.\n\n"
            f"File: {file}\n\n"
            f"Please select a file that contains data with headers."
        )
        exit()
    except Exception as e:
        print(f"Selected file: {file}")
        print(f"Error reading data file: {e}")
        tkinter.messagebox.showerror(
            "File Reading Error",
            f"Failed to read the selected file.\n\n"
            f"File: {file}\n"
            f"Error: {str(e)}\n\n"
            f"Please ensure the file is:\n"
            f"- Not open in another application\n"
            f"- A valid CSV or Excel file\n"
            f"- Not corrupted\n"
            f"- Contains data with proper formatting"
        )
        exit()
else:
    raise ValueError("Invalid data source selected.")

# Use data as-is (no mapping needed for pre-transformed data)
df_mapped = df.copy()

# --- Step 3: Select Operation (insert/upsert) ---
def select_operation():
    import tkinter as tk
    selected = {'value': None}
    def on_select():
        selected['value'] = var.get()
        win.destroy()
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Select Operation")
    win.geometry("400x200")
    win.grab_set()
    tk.Label(win, text="Select operation:").pack(pady=20)
    var = tk.StringVar(win)
    var.set("insert")
    dropdown = tk.OptionMenu(win, var, "insert", "upsert")
    dropdown.config(width=30)
    dropdown.pack(padx=20, pady=20)
    btn = tk.Button(win, text="Select", command=on_select)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    return selected['value']

operation = select_operation()
if operation not in ['insert', 'upsert']:
    raise ValueError("Operation must be 'insert' or 'upsert'.")

# --- Step 4: Select Salesforce Object ---
object_list = list(sf_conn.describe()['sobjects'])
object_names = [obj['name'] for obj in object_list]
filtered_objects = [name for name in object_names if name.lower() == 'account' or 'wod' in name.lower()]
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

selected_object = select_salesforce_object(filtered_objects)
if not selected_object or selected_object not in filtered_objects:
    raise ValueError("No valid Salesforce object selected.")
print(f"Selected Salesforce object: {selected_object}")

# --- Step 5: Prepare Data and Perform Load ---

df_mapped.columns = df_mapped.columns.str.strip()

import numpy as np

def clean_value_for_json(val):
    """Recursively clean a value for JSON compliance (no NaN, inf, -inf, or non-serializable types)"""
    import math
    import numpy as np
    import pandas as pd
    import math
    # Aggressively treat anything that is None, NaN, pd.NA, or string 'nan' as None
    import pandas as pd
    import numpy as np
    import math
    if val is None:
        return None
    # Catch pandas NA, numpy nan, math nan, string 'nan'
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    elif isinstance(val, (np.floating, np.integer)):
        if np.isnan(val) or np.isinf(val):
            return None
        return val.item() if hasattr(val, 'item') else float(val)
    elif isinstance(val, str):
        if val.strip().lower() == 'nan':
            return None
        return val
    elif isinstance(val, (int, bool)):
        return val
    elif isinstance(val, dict):
        return {k: clean_value_for_json(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [clean_value_for_json(v) for v in val]
    else:
        # Try to convert to string, else None
        try:
            sval = str(val)
            if sval.strip().lower() == 'nan':
                return None
            return sval
        except Exception:
            return None

def clean_dataframe_for_salesforce(df):
    """Clean DataFrame to make it JSON compliant for Salesforce"""
    df_clean = df.copy()
    # Replace all np.nan, inf, -inf with None at the DataFrame level first
    df_clean.replace({np.nan: None, np.inf: None, -np.inf: None}, inplace=True)
    for col in df_clean.columns:
        df_clean[col] = df_clean[col].apply(clean_value_for_json)
    # Final pass: applymap to catch any remaining NaN/NA or string 'nan' in the DataFrame
    import pandas as pd
    def final_clean(x):
        try:
            if pd.isna(x):
                return None
            if isinstance(x, str) and x.strip().lower() == 'nan':
                return None
        except Exception:
            pass
        return x
    df_clean = df_clean.applymap(final_clean)
    # Debug: print any columns/rows that still have NaN
    if df_clean.isnull().values.any():
        print("[DEBUG] DataFrame still contains nulls after cleaning. Null counts per column:")
        print(df_clean.isnull().sum())
        print(df_clean[df_clean.isnull().any(axis=1)])
    return df_clean

# --- Salesforce Boolean Field Coercion ---
def get_salesforce_boolean_fields(sf_conn, selected_object):
    """Return a set of field names that are boolean type for the given Salesforce object."""
    try:
        obj_describe = getattr(sf_conn, selected_object).describe()
        return set(f['name'] for f in obj_describe['fields'] if f['type'] == 'boolean')
    except Exception as e:
        print(f"[WARN] Could not fetch boolean fields for {selected_object}: {e}")
        return set()

def coerce_to_bool(val):
    """Convert various representations to True/False/None for Salesforce boolean fields."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        if val == 1 or val == 1.0:
            return True
        if val == 0 or val == 0.0:
            return False
        return None
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("1", "true", "yes", "y", "t"): return True
        if v in ("0", "false", "no", "n", "f"): return False
        if v == "": return None
        return None
    return None

    df_mapped = clean_dataframe_for_salesforce(df_mapped)

# --- Coerce boolean fields to True/False/None ---
    boolean_fields = get_salesforce_boolean_fields(sf_conn, selected_object)
    for col in df_mapped.columns:
        if col in boolean_fields:
            print(f"[INFO] Coercing column '{col}' to boolean for Salesforce upload.")
            df_mapped[col] = df_mapped[col].apply(coerce_to_bool)

# Check for any remaining NaN after cleaning
if df_mapped.isnull().values.any():
    print("Warning: DataFrame still contains NaN/null values after cleaning. These will be converted to None for JSON.")
    # Optionally, force replace again
    df_mapped = df_mapped.where(pd.notnull(df_mapped), None)

# Additional validation - check for any remaining problematic values
def validate_json_compliance(df):
    """Validate that DataFrame can be converted to JSON"""
    try:
        test_records = df.head(1).to_dict('records')
        json.dumps(test_records, allow_nan=False)
        return True
    except (ValueError, TypeError) as e:
        print(f"Data validation failed: {e}")
        
        # Try to identify problematic columns
        for col in df.columns:
            try:
                test_data = df[col].head(5).to_list()
                json.dumps(test_data, allow_nan=False)
            except (ValueError, TypeError) as col_error:
                print(f"  - Column '{col}' contains problematic values: {col_error}")
                print(f"    Sample values: {df[col].head(5).to_list()}")
                print(f"    Data type: {df[col].dtype}")
                print(f"    Unique values (first 10): {df[col].unique()[:10]}")
        
        return False

if not validate_json_compliance(df_mapped):
    raise ValueError("Data contains values that are not JSON compliant. Please check your data for NaN, infinity, or other problematic values.")

# --- Salesforce Field Validation ---
def validate_salesforce_fields(sf_conn, selected_object, df_columns):
    """Validate Salesforce fields for permissions and compatibility"""
    print("Validating Salesforce field permissions...")
    
    field_validation = {
        'valid_fields': [],
        'permission_issues': [],
        'not_found': [],
        'read_only': [],
        'validation_errors': []
    }
    
    try:
        # Get object description
        obj_describe = getattr(sf_conn, selected_object).describe()
        sf_fields = {field['name'].lower(): field for field in obj_describe['fields']}
        
        for col in df_columns:
            col_lower = col.lower()
            
            # Check if field exists in Salesforce
            if col_lower not in sf_fields:
                field_validation['not_found'].append(col)
                continue
            
            field_info = sf_fields[col_lower]
            
            # Check field permissions and properties
            if not field_info.get('createable', False) and not field_info.get('updateable', False):
                if field_info.get('calculated', False) or field_info.get('autoNumber', False):
                    field_validation['read_only'].append(col)
                else:
                    field_validation['permission_issues'].append(col)
            elif field_info.get('calculated', False):
                field_validation['read_only'].append(col)
            elif field_info.get('autoNumber', False):
                field_validation['read_only'].append(col)
            else:
                # Additional validation checks
                field_type = field_info.get('type', '')
                
                # Check for restricted field types
                if field_type in ['address', 'location']:
                    field_validation['validation_errors'].append(f"{col} (Complex field type: {field_type})")
                else:
                    field_validation['valid_fields'].append(col)
        
        return field_validation
        
    except Exception as e:
        print(f"Warning: Could not validate Salesforce fields: {e}")
        # If validation fails, assume all fields are valid
        field_validation['valid_fields'] = list(df_columns)
        field_validation['validation_errors'].append(f"Field validation failed: {e}")
        return field_validation

# --- Column Skip Selection ---
def show_column_skip_selection(df, sf_conn, selected_object):
    """Allow user to select which columns to skip before loading using dual-list interface with Salesforce validation"""
    import tkinter as tk
    from tkinter import ttk
    
    user_choice = {'value': None, 'skip_columns': set()}
    
    # Validate Salesforce fields first
    field_validation = validate_salesforce_fields(sf_conn, selected_object, df.columns)
    
    # Initialize column lists
    all_columns = list(df.columns)
    skip_columns = []
    
    # Auto-add problematic fields to skip list
    problematic_fields = (field_validation['permission_issues'] + 
                         field_validation['not_found'] + 
                         field_validation['read_only'] + 
                         [field.split(' (')[0] for field in field_validation['validation_errors']])
    
    for field in problematic_fields:
        if field in all_columns:
            all_columns.remove(field)
            skip_columns.append(field)
    
    def get_field_display_text(field_name, location='skip'):
        """Get display text for a field with validation indicators"""
        if location == 'skip':
            if field_name in field_validation['permission_issues']:
                return f"🔒 {field_name} (Permission Issue)"
            elif field_name in field_validation['not_found']:
                return f"❌ {field_name} (Not Found in SF)"
            elif field_name in field_validation['read_only']:
                return f"📖 {field_name} (Read-Only)"
            elif any(field_name in error for error in field_validation['validation_errors']):
                error_detail = next((error.split(' (')[1].rstrip(')') for error in field_validation['validation_errors'] if field_name in error), "Validation Error")
                return f"⚠️ {field_name} ({error_detail})"
        return field_name
    
    def extract_field_name(display_text):
        """Extract actual field name from display text with indicators"""
        # Remove emoji and description
        if any(emoji in display_text for emoji in ['🔒', '❌', '📖', '⚠️']):
            # Extract field name between emoji and parentheses
            parts = display_text.split(' ')
            if len(parts) >= 2:
                return parts[1].split(' (')[0]
        return display_text
    
    def move_to_skip():
        """Move selected columns from all_columns to skip_columns"""
        selected_indices = list(all_columns_listbox.curselection())
        selected_indices.reverse()  # Reverse to maintain indices while removing
        
        for index in selected_indices:
            column = all_columns_listbox.get(index)
            skip_columns.append(column)
            all_columns.remove(column)
            all_columns_listbox.delete(index)
            display_text = get_field_display_text(column, 'skip')
            skip_columns_listbox.insert(tk.END, display_text)
        
        update_counts()
    
    def move_to_all():
        """Move selected columns from skip_columns to all_columns"""
        selected_indices = list(skip_columns_listbox.curselection())
        selected_indices.reverse()  # Reverse to maintain indices while removing
        
        for index in selected_indices:
            display_text = skip_columns_listbox.get(index)
            column = extract_field_name(display_text)
            all_columns.append(column)
            skip_columns.remove(column)
            skip_columns_listbox.delete(index)
            all_columns_listbox.insert(tk.END, column)
        
        update_counts()
    
    def move_all_to_skip():
        """Move all columns to skip list"""
        while all_columns_listbox.size() > 0:
            column = all_columns_listbox.get(0)
            skip_columns.append(column)
            all_columns.remove(column)
            all_columns_listbox.delete(0)
            display_text = get_field_display_text(column, 'skip')
            skip_columns_listbox.insert(tk.END, display_text)
        
        update_counts()
    
    def move_all_to_all():
        """Move all columns back to all list"""
        while skip_columns_listbox.size() > 0:
            display_text = skip_columns_listbox.get(0)
            column = extract_field_name(display_text)
            all_columns.append(column)
            skip_columns.remove(column)
            skip_columns_listbox.delete(0)
            all_columns_listbox.insert(tk.END, column)
        
        update_counts()
    
    def update_counts():
        """Update the count labels"""
        all_count_label.config(text=f"Available Columns ({len(all_columns)})")
        skip_count_label.config(text=f"Skip Columns ({len(skip_columns)})")
        
        # Update status
        if len(all_columns) == 0:
            status_label.config(text="⚠️ All columns will be skipped - No data will be loaded!", fg="red")
        elif len(skip_columns) == 0:
            status_label.config(text="ℹ️ No columns will be skipped - All data will be loaded", fg="blue")
        else:
            status_label.config(text=f"✓ {len(skip_columns)} column(s) will be skipped, {len(all_columns)} will be loaded", fg="green")
    
    def search_all_columns():
        """Filter all columns list based on search"""
        search_term = search_all_entry.get().lower()
        all_columns_listbox.delete(0, tk.END)
        
        for col in all_columns:
            if search_term == "" or search_term in col.lower():
                all_columns_listbox.insert(tk.END, col)
    
    def search_skip_columns():
        """Filter skip columns list based on search"""
        search_term = search_skip_entry.get().lower()
        skip_columns_listbox.delete(0, tk.END)
        
        for col in skip_columns:
            if search_term == "" or search_term in col.lower():
                display_text = get_field_display_text(col, 'skip')
                skip_columns_listbox.insert(tk.END, display_text)
    
    def clear_search_all():
        """Clear search for all columns"""
        search_all_entry.delete(0, tk.END)
        search_all_columns()
    
    def clear_search_skip():
        """Clear search for skip columns"""
        search_skip_entry.delete(0, tk.END)
        search_skip_columns()
    
    def preview_data():
        """Preview data with current skip column selection"""
        if len(all_columns) == 0:
            tkinter.messagebox.showwarning("No Data", "All columns would be skipped. No data would remain for loading.")
            return
        
        # Show preview of remaining data
        preview_df = df[all_columns].head(10)
        
        preview_text = f"Preview of data after skipping {len(skip_columns)} column(s):\n"
        preview_text += f"Remaining columns ({len(all_columns)}): {', '.join(all_columns)}\n\n"
        if skip_columns:
            preview_text += f"Skipped columns ({len(skip_columns)}): {', '.join(skip_columns)}\n\n"
        preview_text += f"Sample data (first 10 rows):\n{preview_df.to_string()}"
        
        # Create preview window
        preview_win = tk.Toplevel()
        preview_win.title("Data Preview After Column Skip")
        preview_win.geometry("1000x700")
        preview_win.grab_set()
        
        # Header
        tk.Label(preview_win, text="Data Preview After Column Skip", 
                font=("Arial", 14, "bold")).pack(pady=10)
        tk.Label(preview_win, text=f"Keeping {len(all_columns)} columns, skipping {len(skip_columns)} columns", 
                font=("Arial", 12)).pack()
        
        # Text area with scrollbar
        text_frame = tk.Frame(preview_win)
        text_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        text_area = tk.Text(text_frame, wrap=tk.NONE, font=("Courier", 9))
        v_scroll = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_area.yview)
        h_scroll = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=text_area.xview)
        text_area.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        text_area.insert(tk.END, preview_text)
        text_area.config(state=tk.DISABLED)
        
        # Close button
        tk.Button(preview_win, text="Close", command=preview_win.destroy, 
                 bg="#2196F3", fg="white", font=("Arial", 10, "bold")).pack(pady=10)
    
    def on_save():
        """Save the current column selection"""
        if len(all_columns) == 0:
            result = tkinter.messagebox.askyesno(
                "No Columns Remaining", 
                "All columns will be skipped. This means no data will be loaded to Salesforce.\n\nDo you want to continue anyway?"
            )
            if not result:
                return
            user_choice['value'] = 'skip_all'
        else:
            user_choice['value'] = 'proceed'
        
        user_choice['skip_columns'] = set(skip_columns)
        skip_win.destroy()
    
    def on_cancel():
        user_choice['value'] = 'cancel'
        skip_win.destroy()
    
    def on_window_close():
        """Handle window close event (X button) - cancel the entire operation"""
        user_choice['value'] = 'cancel'
        skip_win.destroy()
    
    # Create main window
    root = tk.Tk()
    root.withdraw()
    
    skip_win = tk.Toplevel()
    
    # Detect DPI scaling to adjust layout (moved before window title)
    try:
        # Get DPI scaling factor
        dpi = skip_win.winfo_fpixels('1i')
        scaling_factor = dpi / 96.0  # 96 DPI is 100% scaling
        is_high_dpi = scaling_factor > 1.2  # 120% or higher scaling
        print(f"Detected screen DPI: {dpi:.1f}, scaling factor: {scaling_factor:.2f}")
    except Exception as e:
        print(f"Could not detect DPI: {e}")
        is_high_dpi = False
        scaling_factor = 1.0
    
    # Add DPI mode indicator to window title
    title_suffix = " (Scrollable Mode)" if scaling_factor > 1.2 else " (Standard Mode)"
    skip_win.title(f"Column Selection - Move Columns to Skip{title_suffix}")
    
    print(f"DPI Mode: {'High DPI (150%+)' if is_high_dpi else 'Normal DPI (100-120%)'} - Scaling: {scaling_factor:.2f}x")
    
    # Adjust window size based on DPI scaling
    screen_width = skip_win.winfo_screenwidth()
    screen_height = skip_win.winfo_screenheight()
    
    if is_high_dpi:
        # For high DPI, use larger window and enable scrolling
        window_width = min(1400, int(screen_width * 0.9))
        window_height = min(900, int(screen_height * 0.9))
    else:
        # For normal DPI, use standard sizing
        window_width = min(1200, int(screen_width * 0.8))
        window_height = min(800, int(screen_height * 0.8))
    
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    skip_win.geometry(f"{window_width}x{window_height}+{x}+{y}")
    skip_win.grab_set()
    
    # Handle window close event (X button)
    skip_win.protocol("WM_DELETE_WINDOW", on_window_close)
    
    # Use skip_win as the parent for all content (simplified - no scrolling needed with buttons at top)
    content_parent = skip_win
    
    # Header
    header_frame = tk.Frame(content_parent)
    header_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text="Column Selection Wizard", 
             font=("Arial", 18, "bold"), fg="darkblue").pack()
    
    # Add DPI-specific instructions
    if is_high_dpi:
        tk.Label(header_frame, text="Move columns between lists to choose which columns to skip", 
                 font=("Arial", 12), fg="blue").pack()
    else:
        tk.Label(header_frame, text="Move columns between lists to choose which columns to skip", 
                 font=("Arial", 12)).pack()
    
    # Action buttons frame - MOVED TO TOP for universal visibility
    button_frame = tk.Frame(content_parent, bg="#f0f0f0", relief="solid", bd=2)
    button_frame.pack(pady=15, padx=20, fill=tk.X)
    
    # Inner frame for better padding control
    button_inner_frame = tk.Frame(button_frame, bg="#f0f0f0")
    button_inner_frame.pack(pady=15, padx=20)
    
    # Center the buttons
    button_center_frame = tk.Frame(button_inner_frame, bg="#f0f0f0")
    button_center_frame.pack()
    
    # Adjust button sizing based on DPI
    if is_high_dpi:
        btn_font_size = 14
        btn_padx = 30
        btn_pady = 15
    else:
        btn_font_size = 12
        btn_padx = 25
        btn_pady = 12
    
    # Save button (green) - Always visible at top
    save_btn = tk.Button(button_center_frame, text="[Save] Save and Continue", 
                        command=on_save, bg="#4CAF50", fg="white", 
                        font=("Arial", btn_font_size, "bold"), 
                        relief="raised", bd=3, cursor="hand2",
                        padx=btn_padx, pady=btn_pady)
    save_btn.pack(side=tk.LEFT, padx=15)
    
    # Cancel button (red) - Always visible at top
    cancel_btn = tk.Button(button_center_frame, text="[X] Cancel", 
                          command=on_cancel, bg="#f44336", fg="white", 
                          font=("Arial", btn_font_size, "bold"), 
                          relief="raised", bd=3, cursor="hand2",
                          padx=btn_padx, pady=btn_pady)
    cancel_btn.pack(side=tk.LEFT, padx=15)
    
    # Status frame
    status_frame = tk.Frame(content_parent)
    status_frame.pack(pady=5, padx=20, fill=tk.X)
    
    status_label = tk.Label(status_frame, text="", font=("Arial", 11, "bold"))
    status_label.pack()
    
    # Main content frame with dual lists
    main_frame = tk.Frame(content_parent)
    main_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    # Left side - Available columns
    left_frame = tk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
    
    # Available columns header and search
    all_count_label = tk.Label(left_frame, text=f"Available Columns ({len(df.columns)})", 
                              font=("Arial", 12, "bold"), fg="green")
    all_count_label.pack(anchor=tk.W)
    
    # Search for available columns
    search_all_frame = tk.Frame(left_frame)
    search_all_frame.pack(fill=tk.X, pady=5)
    tk.Label(search_all_frame, text="Search:", font=("Arial", 9)).pack(side=tk.LEFT)
    search_all_entry = tk.Entry(search_all_frame, width=20)
    search_all_entry.pack(side=tk.LEFT, padx=5)
    search_all_entry.bind('<KeyRelease>', lambda e: search_all_columns())
    tk.Button(search_all_frame, text="Clear", command=clear_search_all, 
             padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=5)
    
    # Available columns listbox
    all_listbox_frame = tk.Frame(left_frame)
    all_listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    
    all_columns_listbox = tk.Listbox(all_listbox_frame, selectmode=tk.EXTENDED, font=("Arial", 10))
    all_v_scroll = tk.Scrollbar(all_listbox_frame, orient=tk.VERTICAL, command=all_columns_listbox.yview)
    all_columns_listbox.configure(yscrollcommand=all_v_scroll.set)
    
    # Load available columns (excluding problematic ones)
    for col in all_columns:
        all_columns_listbox.insert(tk.END, col)
    
    all_columns_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    all_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Middle - Control buttons
    middle_frame = tk.Frame(main_frame)
    middle_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)
    
    # Add some space at the top
    tk.Label(middle_frame, text="").pack(pady=30)
    
    # Move buttons - DPI-aware sizing
    tk.Button(middle_frame, text="Move →", command=move_to_skip, 
             bg="#FF9800", fg="white", font=("Arial", 10, "bold"), 
             padx=15, pady=8, cursor="hand2").pack(pady=5)
    tk.Button(middle_frame, text="← Move Back", command=move_to_all, 
             bg="#2196F3", fg="white", font=("Arial", 10, "bold"), 
             padx=15, pady=8, cursor="hand2").pack(pady=5)
    
    tk.Label(middle_frame, text="", height=2).pack()  # Spacer
    
    tk.Button(middle_frame, text="Move All →", command=move_all_to_skip, 
             bg="#f44336", fg="white", font=("Arial", 9, "bold"), 
             padx=15, pady=8, cursor="hand2").pack(pady=5)
    tk.Button(middle_frame, text="← Move All Back", command=move_all_to_all, 
             bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), 
             padx=15, pady=8, cursor="hand2").pack(pady=5)
    
    tk.Label(middle_frame, text="", height=2).pack()  # Spacer
    
    # Preview button - DPI-aware sizing
    tk.Button(middle_frame, text="Preview Data", command=preview_data, 
             bg="#9C27B0", fg="white", font=("Arial", 10, "bold"), 
             padx=15, pady=8, cursor="hand2").pack(pady=5)
    
    # Right side - Skip columns
    right_frame = tk.Frame(main_frame)
    right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
    
    # Skip columns header and search
    skip_count_label = tk.Label(right_frame, text="Skip Columns (0)", 
                               font=("Arial", 12, "bold"), fg="red")
    skip_count_label.pack(anchor=tk.W)
    
    # Search for skip columns
    search_skip_frame = tk.Frame(right_frame)
    search_skip_frame.pack(fill=tk.X, pady=5)
    tk.Label(search_skip_frame, text="Search:", font=("Arial", 9)).pack(side=tk.LEFT)
    search_skip_entry = tk.Entry(search_skip_frame, width=20)
    search_skip_entry.pack(side=tk.LEFT, padx=5)
    search_skip_entry.bind('<KeyRelease>', lambda e: search_skip_columns())
    tk.Button(search_skip_frame, text="Clear", command=clear_search_skip, 
             padx=10, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=5)
    
    # Skip columns listbox
    skip_listbox_frame = tk.Frame(right_frame)
    skip_listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    
    skip_columns_listbox = tk.Listbox(skip_listbox_frame, selectmode=tk.EXTENDED, font=("Arial", 10))
    skip_v_scroll = tk.Scrollbar(skip_listbox_frame, orient=tk.VERTICAL, command=skip_columns_listbox.yview)
    skip_columns_listbox.configure(yscrollcommand=skip_v_scroll.set)
    
    # Load problematic fields to skip list with indicators
    for col in skip_columns:
        display_text = get_field_display_text(col, 'skip')
        skip_columns_listbox.insert(tk.END, display_text)
    
    skip_columns_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    skip_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Field Validation Summary
    validation_frame = tk.Frame(content_parent)
    validation_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(validation_frame, text="Salesforce Field Validation Summary:", font=("Arial", 11, "bold"), fg="darkblue").pack(anchor=tk.W)
    
    # Create summary text
    summary_text = []
    if field_validation['permission_issues']:
        summary_text.append(f"🔒 {len(field_validation['permission_issues'])} field(s) with permission issues")
    if field_validation['not_found']:
        summary_text.append(f"❌ {len(field_validation['not_found'])} field(s) not found in Salesforce")
    if field_validation['read_only']:
        summary_text.append(f"📖 {len(field_validation['read_only'])} read-only field(s)")
    if field_validation['validation_errors']:
        summary_text.append(f"⚠️ {len(field_validation['validation_errors'])} field(s) with validation errors")
    
    if summary_text:
        for text in summary_text:
            tk.Label(validation_frame, text=f"• {text}", font=("Arial", 9), fg="red").pack(anchor=tk.W, padx=20)
        tk.Label(validation_frame, text="These fields have been automatically moved to the Skip list.", 
                font=("Arial", 9), fg="orange").pack(anchor=tk.W, padx=20)
    else:
        tk.Label(validation_frame, text="• ✅ All fields are compatible with Salesforce", 
                font=("Arial", 9), fg="green").pack(anchor=tk.W, padx=20)
    
    # Instructions frame
    instructions_frame = tk.Frame(content_parent)
    instructions_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(instructions_frame, text="Instructions:", font=("Arial", 11, "bold")).pack(anchor=tk.W)
    tk.Label(instructions_frame, text="• Select columns from left list and use 'Move →' to add them to skip list", 
             font=("Arial", 9)).pack(anchor=tk.W)
    tk.Label(instructions_frame, text="• Select columns from right list and use '← Move Back' to remove them from skip list", 
             font=("Arial", 9)).pack(anchor=tk.W)
    tk.Label(instructions_frame, text="• Use Ctrl+Click for multiple selection, Shift+Click for range selection", 
             font=("Arial", 9)).pack(anchor=tk.W)
    tk.Label(instructions_frame, text="• Fields with icons indicate Salesforce compatibility issues:", 
             font=("Arial", 9), fg="darkblue").pack(anchor=tk.W)
    tk.Label(instructions_frame, text="  🔒 Permission issues | ❌ Not found | 📖 Read-only | ⚠️ Validation errors", 
             font=("Arial", 8), fg="gray").pack(anchor=tk.W, padx=10)
    tk.Label(instructions_frame, text="• Columns in the 'Skip Columns' list will be EXCLUDED from the Salesforce load", 
             font=("Arial", 9), fg="red").pack(anchor=tk.W)
    
    # Initialize counts
    update_counts()
    
    skip_win.wait_window()
    root.destroy()
    
    return user_choice

# Show column skip selection
print("Showing column skip selection...")
skip_decision = show_column_skip_selection(df_mapped, sf_conn, selected_object)

if skip_decision['value'] == 'cancel':
    print("=" * 60)
    print("✗ OPERATION CANCELLED BY USER - HARD CLOSED")
    print("✗ User cancelled the column skip selection by closing the window.")
    print("✗ No data was loaded to Salesforce.")
    print("=" * 60)
    exit()
elif skip_decision['value'] == 'skip_all':
    print("=" * 60)
    print("✗ ALL COLUMNS SKIPPED BY USER")
    print("✗ User chose to skip all columns.")
    print("✗ No data was loaded to Salesforce.")
    print("=" * 60)
    exit()

# Remove skipped columns from the dataframe
skip_columns = skip_decision['skip_columns']
if skip_columns:
    print(f"User selected to skip {len(skip_columns)} columns: {sorted(list(skip_columns))}")
    remaining_columns = [col for col in df_mapped.columns if col not in skip_columns]
    if not remaining_columns:
        print("=" * 60)
        print("✗ NO COLUMNS REMAINING")
        print("✗ All columns were skipped. No data to load.")
        print("✗ Operation aborted.")
        print("=" * 60)
        exit()
    df_mapped = df_mapped[remaining_columns]
    print(f"Remaining columns for loading: {len(remaining_columns)} ({', '.join(remaining_columns)})")
else:
    print("User chose to load all columns (no columns skipped)")

# --- Batch Size and Parallel Processing Selection ---
batch_size = 10000  # Default batch size
parallel_batches = 1  # Default sequential processing

if len(df_mapped) > 5000:  # Show advanced settings for larger datasets
    batch_settings = select_batch_and_parallel_settings(len(df_mapped))
    
    # Check if user cancelled
    if batch_settings.get('cancelled', True):
        print("=" * 60)
        print("✗ BATCH PROCESSING CANCELLED BY USER")
        print("✗ User cancelled the batch processing configuration.")
        print("✗ Operation aborted.")
        print("=" * 60)
        exit()
    
    batch_size = batch_settings['batch_size']
    parallel_batches = batch_settings['parallel_batches']
    
    total_batches = (len(df_mapped) + batch_size - 1) // batch_size
    print(f"Processing {len(df_mapped):,} records in {total_batches} batches of {batch_size:,} records each")
    if parallel_batches > 1:
        print(f"Using parallel processing: {parallel_batches} batches simultaneously")
    else:
        print("Using sequential processing")
        
elif len(df_mapped) > 10000:  # Simple batch size dialog for medium datasets
    user_batch_size = simple_batch_size_dialog(len(df_mapped))
    if user_batch_size:
        batch_size = user_batch_size
        print(f"Processing {len(df_mapped):,} records in batches of {batch_size:,}")
    else:
        print("=" * 60)
        print("✗ BATCH SIZE SELECTION CANCELLED")
        print("✗ No batch size selected.")
        print("✗ Operation aborted.")
        print("=" * 60)
        exit()
else:
    print(f"Processing {len(df_mapped):,} records (single batch)")
    parallel_batches = 1

external_id_name = None
if operation == 'upsert':
    root = tkinter.Tk()
    root.withdraw()
    from tkinter import ttk
    selectable_columns = [col for col in df_mapped.columns if col.lower() != 'id']
    selected = {'value': None}
    def on_select_dropdown():
        selected['value'] = combo.get()
        win.destroy()
    win = tkinter.Toplevel()
    win.title("Select External ID Field")
    win.geometry("600x200")
    win.grab_set()
    label = tkinter.Label(win, text="Select the Salesforce External ID field for upsert (Id cannot be used):")
    label.pack(pady=10)
    combo = ttk.Combobox(win, values=selectable_columns, width=60)
    if selectable_columns:
        combo.set(selectable_columns[0])
    combo.pack(pady=10)
    btn = tkinter.Button(win, text="Select", command=on_select_dropdown)
    btn.pack(pady=20)
    win.wait_window()
    root.destroy()
    external_id_name = selected['value']
    if not external_id_name:
        raise ValueError("No External ID field name provided.")
    if external_id_name not in df_mapped.columns:
        raise ValueError(f"{external_id_name} column is missing in the mapped data.")

root_folder = r'DataLoader_Logs'
data_load_folder = os.path.join(root_folder, 'DataLoad')
org_folder = os.path.join(data_load_folder, f'DataLoad_{selected_org}')
object_folder = os.path.join(org_folder, selected_object)
batches_folder = os.path.join(object_folder, 'Batches')
logs_folder = os.path.join(object_folder, 'Logs')
summary_folder = os.path.join(object_folder, 'Summary')

# Create all necessary folders
os.makedirs(object_folder, exist_ok=True)
os.makedirs(batches_folder, exist_ok=True)
os.makedirs(logs_folder, exist_ok=True)
os.makedirs(summary_folder, exist_ok=True)

# Function to create detailed log file
def create_processing_log(start_time, end_time, total_records, success_count, error_count, 
                         batch_results, operation, selected_object, selected_org, logs_folder):
    """Create a comprehensive CSV log file with processing details"""
    
    # Calculate processing metrics
    processing_duration = end_time - start_time
    unprocessed_count = total_records - success_count - error_count
    success_rate = (success_count / total_records * 100) if total_records > 0 else 0
    error_rate = (error_count / total_records * 100) if total_records > 0 else 0
    
    # Create summary log file in Logs folder
    summary_log_file = os.path.join(logs_folder, "processing_summary.csv")
    
    with open(summary_log_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow([
            'Start_Time', 'End_Time', 'Processing_Duration_Seconds', 'Processing_Duration_Formatted',
            'Total_Records', 'Total_Success', 'Total_Errors', 'Total_Unprocessed',
            'Success_Rate_Percent', 'Error_Rate_Percent', 'Operation', 'Salesforce_Object', 
            'Salesforce_Org', 'Total_Batches', 'Parallel_Processing', 'Log_Generated_At'
        ])
        
        # Format times for readability
        start_time_str = datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
        end_time_str = datetime.datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
        duration_formatted = str(datetime.timedelta(seconds=int(processing_duration)))
        log_generated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Determine if parallel processing was used
        parallel_used = any(batch.get('processing_time', 0) > 0 for batch in batch_results) and len(batch_results) > 1
        
        # Write summary data
        writer.writerow([
            start_time_str, end_time_str, f"{processing_duration:.2f}", duration_formatted,
            total_records, success_count, error_count, unprocessed_count,
            f"{success_rate:.2f}", f"{error_rate:.2f}", operation, selected_object,
            selected_org, len(batch_results), parallel_used, log_generated_at
        ])
    
    # Create detailed batch log file in Logs folder
    batch_log_file = os.path.join(logs_folder, "batch_processing_details.csv")
    
    with open(batch_log_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow([
            'Batch_Number', 'Batch_Records', 'Batch_Success', 'Batch_Errors', 
            'Batch_Processing_Time_Seconds', 'Batch_Success_Rate_Percent', 
            'Batch_Error_Rate_Percent', 'Batch_Status', 'Error_Details'
        ])
        
        # Write batch details
        for batch in batch_results:
            batch_success_rate = (batch['success_count'] / batch['total_records'] * 100) if batch['total_records'] > 0 else 0
            batch_error_rate = (batch['error_count'] / batch['total_records'] * 100) if batch['total_records'] > 0 else 0
            batch_status = "SUCCESS" if batch['error_count'] == 0 else "PARTIAL" if batch['success_count'] > 0 else "FAILED"
            error_details = batch.get('error', '') if 'error' in batch else ''
            
            writer.writerow([
                batch['batch_num'], batch['total_records'], batch['success_count'], 
                batch['error_count'], f"{batch.get('processing_time', 0):.2f}",
                f"{batch_success_rate:.2f}", f"{batch_error_rate:.2f}", 
                batch_status, error_details
            ])
    
    return summary_log_file, batch_log_file

# Function to process data in batches with parallel processing support
def create_sf_connection(org_creds):
    """Create a new Salesforce connection for thread safety"""
    return sf.Salesforce(
        username=org_creds['username'],
        password=org_creds['password'],
        security_token=org_creds['security_token'],
        domain=org_creds['domain']
    )

def clean_record_for_json(record):
    # Recursively replace all float('nan')/np.nan with None in a dict/list
    import math
    import numpy as np
    if isinstance(record, dict):
        return {k: clean_record_for_json(v) for k, v in record.items()}
    elif isinstance(record, list):
        return [clean_record_for_json(v) for v in record]
    elif isinstance(record, float):
        if math.isnan(record) or math.isinf(record):
            return None
        return record
    elif isinstance(record, (np.floating, np.integer)):
        if np.isnan(record) or np.isinf(record):
            return None
        return record.item() if hasattr(record, 'item') else float(record)
    else:
        return record

def process_single_batch(batch_data, batch_num, operation, external_id_name, selected_object, org_creds, batches_folder):
    """Process a single batch - designed to be thread-safe"""
    try:
        # Create new SF connection for this thread
        thread_sf_conn = create_sf_connection(org_creds)
        batch_df, start_time = batch_data
        print(f"[Batch {batch_num}] Starting processing of {len(batch_df)} records...")

        # --- Boolean field coercion logic ---
        def get_salesforce_boolean_fields(sf_conn, object_name):
            """Return a set of field names that are booleans for the given Salesforce object."""
            try:
                obj_desc = getattr(sf_conn, object_name).describe()
                return set(f['name'] for f in obj_desc['fields'] if f['type'] == 'boolean')
            except Exception as e:
                print(f"[Batch {batch_num}] Warning: Could not fetch boolean fields: {e}")
                return set()

        def coerce_to_bool(val):
            if val is None:
                return None
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                if val == 1 or val == 1.0:
                    return True
                if val == 0 or val == 0.0:
                    return False
            if isinstance(val, str):
                if val.strip().lower() in ['true', '1', 'yes', 'y']:
                    return True
                if val.strip().lower() in ['false', '0', 'no', 'n']:
                    return False
            return None

        # Get boolean fields for this object
        boolean_fields = get_salesforce_boolean_fields(thread_sf_conn, selected_object)
        if boolean_fields:
            print(f"[Batch {batch_num}] Coercing boolean fields: {sorted(boolean_fields)}")
        else:
            print(f"[Batch {batch_num}] No boolean fields detected for coercion.")

        # Convert batch to records, clean for JSON, and coerce booleans
        batch_records = []
        for rec in batch_df.to_dict('records'):
            rec_clean = clean_record_for_json(rec)
            for field in boolean_fields:
                if field in rec_clean:
                    rec_clean[field] = coerce_to_bool(rec_clean[field])
            batch_records.append(rec_clean)

        # Perform bulk operation for this batch
        if operation == 'upsert':
            results = getattr(thread_sf_conn.bulk, selected_object).upsert(batch_records, external_id_field=external_id_name)
        else:
            results = getattr(thread_sf_conn.bulk, selected_object).insert(batch_records)

        # Process results for this batch
        batch_success_rows = []
        batch_error_rows = []

        for i, res in enumerate(results):
            row = batch_df.iloc[i].copy()
            if res.get('success'):
                batch_success_rows.append(row)
            else:
                row['errors'] = str(res.get('errors'))
                batch_error_rows.append(row)

        # Save batch-specific files
        batch_file_prefix = f"{selected_object}_Batch{batch_num}"

        # Save batch source data
        batch_df.to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_source.csv"), index=False)

        # Save batch results
        if batch_success_rows:
            pd.DataFrame(batch_success_rows).to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_success.csv"), index=False)

        if batch_error_rows:
            pd.DataFrame(batch_error_rows).to_csv(os.path.join(batches_folder, f"{batch_file_prefix}_error.csv"), index=False)

        processing_time = time.time() - start_time
        print(f"[Batch {batch_num}] Completed in {processing_time:.2f}s: {len(batch_success_rows)} success, {len(batch_error_rows)} errors")

        return {
            'batch_num': batch_num,
            'total_records': len(batch_df),
            'success_count': len(batch_success_rows),
            'error_count': len(batch_error_rows),
            'success_rows': batch_success_rows,
            'error_rows': batch_error_rows,
            'processing_time': processing_time
        }

    except Exception as e:
        processing_time = time.time() - start_time if 'start_time' in locals() else 0
        print(f"[Batch {batch_num}] Failed in {processing_time:.2f}s: {e}")

        # Mark all records in this batch as errors
        error_rows = []
        for i in range(len(batch_df)):
            row = batch_df.iloc[i].copy()
            row['errors'] = f"Batch processing failed: {str(e)}"
            error_rows.append(row)

        return {
            'batch_num': batch_num,
            'total_records': len(batch_df),
            'success_count': 0,
            'error_count': len(batch_df),
            'success_rows': [],
            'error_rows': error_rows,
            'processing_time': processing_time,
            'error': str(e)
        }

def process_in_batches(df_data, batch_size, operation, parallel_batches=1, external_id_name=None):
    """Process DataFrame in batches with optional parallel processing support"""
    total_records = len(df_data)
    num_batches = (total_records + batch_size - 1) // batch_size  # Ceiling division
    
    all_success_rows = []
    all_error_rows = []
    batch_results = []
    
    print(f"Processing {total_records:,} records in {num_batches} batches...")
    if parallel_batches > 1:
        print(f"Using parallel processing with {parallel_batches} simultaneous batches")
    else:
        print("Using sequential processing")
    
    # Get org credentials for thread-safe connections
    org_creds = creds[selected_org]
    
    if parallel_batches == 1:
        # Sequential processing (traditional method)
        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_records)
            batch_df = df_data.iloc[start_idx:end_idx].copy()
            
            print(f"Processing Batch {batch_num + 1}/{num_batches} ({len(batch_df)} records)...")
            
            batch_data = (batch_df, time.time())
            result = process_single_batch(batch_data, batch_num + 1, operation, external_id_name, 
                                        selected_object, org_creds, batches_folder)
            
            # Collect results
            all_success_rows.extend(result['success_rows'])
            all_error_rows.extend(result['error_rows'])
            batch_results.append(result)
    else:
        # Parallel processing
        print(f"Preparing {num_batches} batches for parallel processing...")
        
        # Prepare batch data
        batch_data_list = []
        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_records)
            batch_df = df_data.iloc[start_idx:end_idx].copy()
            batch_data_list.append((batch_df, time.time()))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_batches) as executor:
            # Submit all batches
            future_to_batch = {}
            for i, batch_data in enumerate(batch_data_list):
                batch_num = i + 1
                future = executor.submit(process_single_batch, batch_data, batch_num, operation, 
                                       external_id_name, selected_object, org_creds, batches_folder)
                future_to_batch[future] = batch_num
            
            # Collect results as they complete
            completed_batches = 0
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_num = future_to_batch[future]
                completed_batches += 1
                
                try:
                    result = future.result()
                    
                    # Collect results
                    all_success_rows.extend(result['success_rows'])
                    all_error_rows.extend(result['error_rows'])
                    batch_results.append(result)
                    
                    print(f"Completed {completed_batches}/{num_batches} batches - Batch {batch_num}: {result['success_count']} success, {result['error_count']} errors")
                    
                except Exception as e:
                    print(f"Batch {batch_num} execution failed: {str(e)}")
                    # Create error result for failed batch
                    batch_df = batch_data_list[batch_num - 1][0]
                    error_rows = []
                    for i in range(len(batch_df)):
                        row = batch_df.iloc[i].copy()
                        row['errors'] = f"Thread execution failed: {str(e)}"
                        error_rows.append(row)
                    
                    error_result = {
                        'batch_num': batch_num,
                        'total_records': len(batch_df),
                        'success_count': 0,
                        'error_count': len(batch_df),
                        'success_rows': [],
                        'error_rows': error_rows,
                        'processing_time': 0,
                        'error': str(e)
                    }
                    
                    all_error_rows.extend(error_result['error_rows'])
                    batch_results.append(error_result)
    
    # Sort batch results by batch number for consistent reporting
    batch_results.sort(key=lambda x: x['batch_num'])
    
    return all_success_rows, all_error_rows, batch_results

try:
    print(f"Starting {operation} operation for {len(df_mapped)} records...")
    
    # Record start time for logging
    operation_start_time = time.time()
    operation_start_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Operation started at: {operation_start_timestamp}")
    
    # Validate Salesforce fields before processing
    field_validation = validate_salesforce_fields(sf_conn, selected_object, df_mapped.columns)
    
    # Check for any validation errors
    if field_validation['validation_errors']:
        error_message = "Field validation errors:\n- " + "\n- ".join(field_validation['validation_errors'])
        print(f"Validation failed: {error_message}")
        tkinter.messagebox.showerror("Field Validation Error", error_message)
        exit()
    
    # Process data in batches with optional parallel processing
    success_rows, error_rows, batch_results = process_in_batches(
        df_mapped, batch_size, operation, parallel_batches, external_id_name
    )
    
    # Record end time for logging
    operation_end_time = time.time()
    operation_end_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"Operation completed at: {operation_end_timestamp}")
    
    # Print batch summary
    print("\nBatch Processing Summary:")
    total_processing_time = sum(batch_info.get('processing_time', 0) for batch_info in batch_results)
    for batch_info in batch_results:
        processing_time = batch_info.get('processing_time', 0)
        print(f"Batch {batch_info['batch_num']}: {batch_info['success_count']} success, {batch_info['error_count']} errors "
              f"out of {batch_info['total_records']} records ({processing_time:.2f}s)")
    
    total_success = len(success_rows)
    total_errors = len(error_rows)
    total_unprocessed = len(df_mapped) - total_success - total_errors
    avg_batch_time = total_processing_time / len(batch_results) if batch_results else 0
    
    print(f"\nOverall Results: {total_success:,} success, {total_errors:,} errors, {total_unprocessed:,} unprocessed out of {len(df_mapped):,} total records")
    print(f"Average batch processing time: {avg_batch_time:.2f} seconds")
    print(f"Total operation time: {operation_end_time - operation_start_time:.2f} seconds")
    if parallel_batches > 1:
        print(f"Parallel processing used: {parallel_batches} simultaneous batches")
    
    # Save consolidated files in Summary folder
    df.to_csv(os.path.join(summary_folder, "raw.csv"), index=False)
    df_mapped.to_csv(os.path.join(summary_folder, "transformed_file.csv"), index=False)
    df_mapped.to_csv(os.path.join(summary_folder, "source.csv"), index=False)
    
    if success_rows:
        pd.DataFrame(success_rows).to_csv(os.path.join(summary_folder, "success.csv"), index=False)
    else:
        # Create empty success file
        pd.DataFrame(columns=df_mapped.columns).to_csv(os.path.join(summary_folder, "success.csv"), index=False)
    
    if error_rows:
        pd.DataFrame(error_rows).to_csv(os.path.join(summary_folder, "error.csv"), index=False)
    else:
        # Create empty error file
        error_columns = list(df_mapped.columns) + ['errors']
        pd.DataFrame(columns=error_columns).to_csv(os.path.join(summary_folder, "error.csv"), index=False)
    
    print(f"Summary files saved to {summary_folder}/")
    print(f"Batch details saved to {batches_folder}/")
    
    # Generate comprehensive log files
    print("Generating processing log files...")
    try:
        summary_log_file, batch_log_file = create_processing_log(
            operation_start_time, operation_end_time, len(df_mapped), 
            total_success, total_errors, batch_results, operation, 
            selected_object, selected_org, logs_folder
        )
        print(f"Processing summary log saved to: {summary_log_file}")
        print(f"Batch details log saved to: {batch_log_file}")
    except Exception as log_error:
        print(f"Warning: Failed to generate log files: {log_error}")
    
    # Calculate final processing metrics for display
    processing_duration = operation_end_time - operation_start_time
    success_rate = (total_success / len(df_mapped) * 100) if len(df_mapped) > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"PROCESSING COMPLETED SUCCESSFULLY")
    print(f"{'='*60}")
    print(f"Start Time: {operation_start_timestamp}")
    print(f"End Time: {operation_end_timestamp}")
    print(f"Duration: {processing_duration:.2f} seconds ({datetime.timedelta(seconds=int(processing_duration))})")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Records Processed: {total_success + total_errors:,} / {len(df_mapped):,}")
    print(f"{'='*60}")
    
    if error_rows:
        tkinter.messagebox.showwarning(
            "Load Completed with Errors",
            f"{len(error_rows):,} out of {len(df_mapped):,} records failed to load.\n\n"
            f"Check {summary_folder}/error.csv for details.\n"
            f"Batch details available in {batches_folder}/\n"
            f"Processing logs saved to {logs_folder}/\n"
            f"Processing method: {'Parallel' if parallel_batches > 1 else 'Sequential'}"
        )
    else:
        parallel_info = f"({parallel_batches} parallel batches)" if parallel_batches > 1 else "(sequential)"
        tkinter.messagebox.showinfo(
            "Load Completed Successfully",
            f"All {len(df_mapped):,} records {operation}ed successfully into Salesforce {selected_object} object.\n\n"
            f"Processed in {len(batch_results)} batch(es) {parallel_info}.\n"
            f"Summary files saved to {summary_folder}/\n"
            f"Processing logs saved to {logs_folder}/"
        )
except Exception as e:
    tkinter.messagebox.showerror(
        "Bulk Load Failed",
        f"Bulk {operation} failed: {e}"
    )
    raise