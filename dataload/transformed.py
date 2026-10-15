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
import tkinter.simpledialog
import dataset.Connections as Connections

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
    file = tkinter.filedialog.askopenfilename(
        title="Select CSV or Excel File",
        filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
    )
    if not file:
        raise ValueError("No data file selected.")
    try:
        if file.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        elif file.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            raise ValueError("Unsupported file format. Please select a CSV or Excel file.")
        
        # Validate that we have data
        if df.empty:
            raise ValueError("The selected file is empty.")
        
        print(f"Loaded {len(df)} rows and {len(df.columns)} columns from data file.")
    except Exception as e:
        raise ValueError(f"Error reading data file: {e}")
else:
    raise ValueError("Invalid data source selected.")

# --- Ask for mapping file ---
def ask_for_mapping():
    import tkinter as tk
    selected = {'value': None}
    def on_yes():
        selected['value'] = 'yes'
        win.destroy()
    def on_no():
        selected['value'] = 'no'
        win.destroy()
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel()
    win.title("Mapping File")
    win.geometry("400x150")
    win.grab_set()
    tk.Label(win, text="Do you have a mapping file?").pack(pady=20)
    button_frame = tk.Frame(win)
    button_frame.pack(pady=20)
    tk.Button(button_frame, text="Yes", command=on_yes, width=10).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="No", command=on_no, width=10).pack(side=tk.LEFT, padx=10)
    win.wait_window()
    root.destroy()
    return selected['value']

mapping_files = ask_for_mapping()
if mapping_files=='yes':
    # --- Step 3: Select Mapping File ---
    # Set default directory to mapping_logs folder
    default_mapping_dir = os.path.join(project_root, 'mapping_logs')
    
    mapping_file = tkinter.filedialog.askopenfilename(
        title="Select Mapping JSON File",
        initialdir=default_mapping_dir,
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    if not mapping_file:
        raise ValueError("No mapping file selected.")

    try:
        with open(mapping_file, 'r') as f:
            mapping = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise ValueError(f"Error reading mapping file: {e}")
    
    # --- Step 4: Apply Mapping ---
    # Filter mapping to only include columns that exist in the input DataFrame
    filtered_mapping = {k: v for k, v in mapping.items() if k in df.columns}
else:
    print('Using all columns as-is (no mapping file provided)')
    # If no mapping file, use all columns as-is
    mapping = {}
    filtered_mapping = {col: col for col in df.columns}

if not filtered_mapping:
    raise ValueError("None of the columns in the mapping file match the columns in the data file.")

# Rename DataFrame columns based on the filtered mapping
try:
    df_mapped = df.rename(columns=filtered_mapping)
    # Keep only the columns that were mapped
    df_mapped = df_mapped[list(filtered_mapping.values())]
except Exception as e:
    raise ValueError(f"Error applying mapping: {e}")

# Log ignored mappings
ignored_mappings = [k for k in mapping.keys() if k not in df.columns]
if ignored_mappings:
    tkinter.messagebox.showwarning(
        "Ignored Mappings",
        f"The following columns in the mapping file were ignored as they are not in the data file: {', '.join(ignored_mappings)}"
    )

# --- Step 5: Select Salesforce Object ---
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
    tk.Label(win, text="Type to filter, then select Salesforce object for transformation:").pack(pady=10)
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

# --- Step 6: Validate Lookup Fields ---
# Get the object's field metadata
object_metadata = getattr(sf_conn, selected_object).describe()
lookup_fields = {}
for field in object_metadata['fields']:
    if field['type'] in ['reference'] and field['name'] in df_mapped.columns:
        lookup_fields[field['name']] = field['referenceTo'][0] if field['referenceTo'] else None

# --- Step 7: Prompt for Lookup Field Matching ---
lookup_match_fields = {}
for lookup_field, related_object in lookup_fields.items():
    if related_object:
        # Get the related object's metadata to list available fields
        try:
            related_metadata = getattr(sf_conn, related_object).describe()
            field_names = [f['name'] for f in related_metadata['fields']]
        except Exception as e:
            tkinter.messagebox.showerror(
                "Metadata Error",
                f"Failed to retrieve metadata for {related_object}: {e}"
            )
            raise
        root = tkinter.Tk()
        root.withdraw()
        # Use a dropdown for match_field selection for each lookup field
        match_field = {'value': None}
        def on_select_dropdown():
            match_field['value'] = combo.get()
            win.destroy()
        win = tkinter.Toplevel()
        win.title(f"Select Match Field for {lookup_field}")
        win.geometry("600x200")
        win.grab_set()
        label = tkinter.Label(win, text=f"Select the field on {related_object} to match values for {lookup_field}:")
        label.pack(pady=10)
        from tkinter import ttk
        combo = ttk.Combobox(win, values=field_names, width=60)
        combo.set('Name' if 'Name' in field_names else field_names[0])
        combo.pack(pady=10)
        btn = tkinter.Button(win, text="Select", command=on_select_dropdown)
        btn.pack(pady=20)
        win.wait_window()
        root.destroy()
        selected_match_field = match_field['value']
        if not selected_match_field:
            raise ValueError(f"No matching field provided for {lookup_field}")
        if selected_match_field not in field_names:
            raise ValueError(f"Invalid field '{selected_match_field}' for {related_object}. Choose from: {', '.join(field_names)}")
        lookup_match_fields[lookup_field] = selected_match_field

# --- Step 8: Store Original Data for Transform Comparison ---
# Keep a copy of the original data before any transformations
df_original_raw = df_mapped.copy()
print(f"Stored original raw data for transform comparison: {len(df_original_raw)} records")

# --- Step 8: Automatically Resolve Lookup Values ---
def show_lookup_preview(df, lookup_field, resolved_count, total_lookups, current_lookup_num, related_object, field_names):
    """Show data preview after each lookup resolution with option to reselect lookup field"""
    import tkinter as tk
    from tkinter import ttk
    
    user_choice = {'value': None}
    
    def on_next():
        user_choice['value'] = 'next'
        preview_win.destroy()
    
    def on_cancel():
        user_choice['value'] = 'cancel'
        preview_win.destroy()
    
    def on_select_lookup_field():
        user_choice['value'] = 'reselect'
        preview_win.destroy()
    
    root = tk.Tk()
    root.withdraw()
    
    preview_win = tk.Toplevel()
    preview_win.title(f"Lookup Resolution Preview - {lookup_field}")
    preview_win.geometry("1200x800")
    preview_win.grab_set()
    
    # Header info
    header_frame = tk.Frame(preview_win)
    header_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text=f"Lookup Resolution Progress: {current_lookup_num}/{total_lookups}", 
             font=("Arial", 14, "bold")).pack()
    tk.Label(header_frame, text=f"Field: {lookup_field} | Related Object: {related_object}", 
             font=("Arial", 12)).pack()
    tk.Label(header_frame, text=f"Resolved: {resolved_count} values", 
             font=("Arial", 12), fg="green").pack()
    tk.Label(header_frame, text="Preview of data after lookup resolution:", 
             font=("Arial", 10)).pack(pady=(5,0))
    
    # Data preview frame
    data_frame = tk.Frame(preview_win)
    data_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    # Create Treeview for data display
    columns = list(df.columns)
    tree = ttk.Treeview(data_frame, columns=columns, show='headings', height=20)
    
    # Configure column headings and widths
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, minwidth=80)
        # Highlight the lookup field
        if col == lookup_field:
            tree.heading(col, text=f"🔍 {col}")
    
    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Pack scrollbars and treeview
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Add data to treeview (first 100 rows)
    preview_df = df.head(100)
    for idx, row in preview_df.iterrows():
        values = [str(val) if val is not None else '' for val in row.values]
        tree.insert('', tk.END, values=values)
    
    # Button frame
    button_frame = tk.Frame(preview_win)
    button_frame.pack(pady=20)
    
    # Next button (green) - Changes to "Save Transformed Data" for last lookup
    button_text = "Save Transformed Data" if current_lookup_num == total_lookups else "Next Lookup"
    next_btn = tk.Button(button_frame, text=button_text, 
                        command=on_next, bg="#4CAF50", fg="white", 
                        font=("Arial", 11, "bold"), width=20, height=2)
    next_btn.pack(side=tk.LEFT, padx=10)
    
    # Reselect Lookup Field button (orange)
    select_field_btn = tk.Button(button_frame, text="Reselect Lookup Field", 
                                command=on_select_lookup_field, bg="#FF9800", fg="white", 
                                font=("Arial", 11, "bold"), width=20, height=2)
    select_field_btn.pack(side=tk.LEFT, padx=10)
    
    # Cancel button (red)
    cancel_btn = tk.Button(button_frame, text="Cancel", 
                          command=on_cancel, bg="#f44336", fg="white", 
                          font=("Arial", 11, "bold"), width=20, height=2)
    cancel_btn.pack(side=tk.LEFT, padx=10)
    
    # Additional info
    info_frame = tk.Frame(preview_win)
    info_frame.pack(pady=(0,10))
    tk.Label(info_frame, text=f"Showing first 100 rows | Lookup field '{lookup_field}' is highlighted", 
             font=("Arial", 9), fg="gray").pack()
    if current_lookup_num == total_lookups:
        tk.Label(info_frame, text="Click 'Save Transformed Data' when satisfied, or 'Reselect Lookup Field' to change match field", 
                 font=("Arial", 9), fg="blue").pack()
    else:
        tk.Label(info_frame, text="Click 'Next Lookup' when satisfied, or 'Reselect Lookup Field' to change match field", 
                 font=("Arial", 9), fg="blue").pack()
    
    preview_win.wait_window()
    root.destroy()
    
    return user_choice['value']

def select_lookup_match_field(lookup_field, related_object, field_names, current_selection):
    """Allow user to select/change the lookup match field"""
    import tkinter as tk
    from tkinter import ttk
    
    selected_field = {'value': None, 'action': 'cancel'}
    
    def on_select():
        selected_field['value'] = combo.get()
        selected_field['action'] = 'select'
        field_win.destroy()
    
    def on_cancel():
        selected_field['value'] = current_selection
        selected_field['action'] = 'cancel'
        field_win.destroy()
    
    root = tk.Tk()
    root.withdraw()
    
    field_win = tk.Toplevel()
    field_win.title(f"Select Match Field for {lookup_field}")
    field_win.geometry("700x300")
    field_win.grab_set()
    
    # Header
    header_frame = tk.Frame(field_win)
    header_frame.pack(pady=20, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text=f"Select Match Field for Lookup: {lookup_field}", 
             font=("Arial", 14, "bold")).pack()
    tk.Label(header_frame, text=f"Related Object: {related_object}", 
             font=("Arial", 12)).pack(pady=5)
    tk.Label(header_frame, text="Choose which field in the related object to match against:", 
             font=("Arial", 10)).pack()
    
    # Field selection
    selection_frame = tk.Frame(field_win)
    selection_frame.pack(pady=20, padx=20, fill=tk.X)
    
    tk.Label(selection_frame, text="Available fields:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
    
    combo = ttk.Combobox(selection_frame, values=field_names, width=60, font=("Arial", 11))
    combo.set(current_selection)
    combo.pack(pady=10, anchor=tk.W)
    
    # Current selection info
    info_frame = tk.Frame(field_win)
    info_frame.pack(pady=10, padx=20, fill=tk.X)
    tk.Label(info_frame, text=f"Current selection: {current_selection}", 
             font=("Arial", 10), fg="blue").pack(anchor=tk.W)
    
    # Instructions
    instruction_frame = tk.Frame(field_win)
    instruction_frame.pack(pady=5, padx=20, fill=tk.X)
    tk.Label(instruction_frame, text="Select a field from the dropdown and click 'Select' to use it for matching", 
             font=("Arial", 9), fg="gray").pack(anchor=tk.W)
    tk.Label(instruction_frame, text="Click 'Cancel' to keep the current field unchanged", 
             font=("Arial", 9), fg="gray").pack(anchor=tk.W)
    
    # Buttons
    button_frame = tk.Frame(field_win)
    button_frame.pack(pady=20)
    
    tk.Button(button_frame, text="Select", command=on_select, 
             bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=15).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="Cancel", command=on_cancel, 
             bg="#f44336", fg="white", font=("Arial", 11, "bold"), width=15).pack(side=tk.LEFT, padx=10)
    
    field_win.wait_window()
    root.destroy()
    
    return selected_field['value'], selected_field['action']

print("Processing lookup fields...")
lookup_count_summary = {}
current_lookup_num = 0
total_lookups = len(lookup_fields)

for lookup_field, related_object in lookup_fields.items():
    if lookup_field in df_mapped.columns and related_object:
        current_lookup_num += 1
        print(f"Resolving lookup field {current_lookup_num}/{total_lookups}: {lookup_field} -> {related_object}")
        
        # Get field metadata for reselection option
        try:
            related_metadata = getattr(sf_conn, related_object).describe()
            field_names = [f['name'] for f in related_metadata['fields']]
        except Exception as e:
            print(f"Error getting metadata for {related_object}: {e}")
            field_names = ['Name']  # Fallback
        
        # Initial match field selection
        match_field = lookup_match_fields.get(lookup_field, 'Name')
        
        # Store original values for reprocessing
        original_values = df_mapped[lookup_field].copy()
        
        # Process lookup resolution in a continuous loop
        while True:
            # Reset to original values before each processing attempt
            df_mapped[lookup_field] = original_values.copy()
            
            unique_values = df_mapped[lookup_field].dropna().unique()
            lookup_count = 0
            
            for value in unique_values:
                # Check if the value is already a valid Salesforce ID (15 or 18 characters)
                if isinstance(value, str) and len(value) in [15, 18] and value.isalnum():
                    continue
                # Query Salesforce for the ID using the specified field
                try:
                    # Escape single quotes in the value to prevent SOQL injection
                    escaped_value = str(value).replace("'", "\\'")
                    result = sf_conn.query(f"SELECT Id FROM {related_object} WHERE {match_field} = '{escaped_value}'")
                    if result['records']:
                        salesforce_id = result['records'][0]['Id']
                        df_mapped.loc[df_mapped[lookup_field] == value, lookup_field] = salesforce_id
                        lookup_count += 1
                    else:
                        print(f"Warning: No record found in {related_object} with {match_field} = '{value}'")
                        # Continue processing instead of raising error
                except Exception as e:
                    print(f"Error processing lookup value '{value}': {e}")
                    # Continue processing instead of raising error
            
            print(f"Resolved {lookup_count} lookup values for {lookup_field} using {match_field}")
            lookup_count_summary[lookup_field] = lookup_count
            
            # Show preview with options
            if total_lookups > 0:
                user_decision = show_lookup_preview(df_mapped, lookup_field, lookup_count, total_lookups, 
                                                  current_lookup_num, related_object, field_names)
                
                if user_decision == 'cancel':
                    print("=" * 60)
                    print("✗ LOOKUP PROCESSING CANCELLED BY USER")
                    print("✗ User cancelled the lookup resolution process.")
                    print("✗ Operation aborted.")
                    print("=" * 60)
                    exit()
                elif user_decision == 'reselect':
                    # Allow user to reselect the lookup field
                    new_match_field, action = select_lookup_match_field(lookup_field, related_object, field_names, match_field)
                    if action == 'select' and new_match_field and new_match_field != match_field:
                        print(f"User changed match field from '{match_field}' to '{new_match_field}' for {lookup_field}")
                        match_field = new_match_field
                        lookup_match_fields[lookup_field] = match_field
                        # Continue loop to reprocess with new match field
                        continue
                    elif action == 'select' and new_match_field == match_field:
                        print(f"User confirmed current match field '{match_field}' for {lookup_field}")
                        # Continue loop to show preview again
                        continue
                    else:
                        print(f"User cancelled field selection, keeping match field '{match_field}' for {lookup_field}")
                        # Continue loop to show preview again
                        continue
                elif user_decision == 'next':
                    # If this is the last lookup and user clicked "Save Transformed Data", proceed to save
                    if current_lookup_num == total_lookups:
                        print(f"✓ User confirmed final lookup resolution. Proceeding to save transformed data...")
                        break  # Exit the reselection loop and proceed to save
                    else:
                        print(f"✓ User confirmed lookup resolution for {lookup_field}. Continuing to next lookup...")
                        break  # Continue to next lookup field
            else:
                break  # No preview needed if no lookups

if lookup_fields:
    print(f"\nLookup Resolution Summary:")
    for field, count in lookup_count_summary.items():
        print(f"- {field}: {count} values resolved")

# --- Step 9: Clean Data for Salesforce ---
def clean_dataframe_for_salesforce(df):
    """Clean DataFrame to make it JSON compliant for Salesforce"""
    df_clean = df.copy()
    
    # Replace NaN, inf, -inf with None
    df_clean = df_clean.replace([float('inf'), float('-inf')], None)
    df_clean = df_clean.where(pd.notnull(df_clean), None)
    
    # Convert numpy data types to Python native types
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            # Handle string columns - convert NaN to None and strip whitespace
            df_clean[col] = df_clean[col].apply(
                lambda x: str(x).strip() if pd.notnull(x) and str(x).strip() != 'nan' and str(x).strip() != '' else None
            )
        elif pd.api.types.is_numeric_dtype(df_clean[col]):
            # Handle numeric columns - ensure they're JSON compliant
            if pd.api.types.is_integer_dtype(df_clean[col]):
                # Convert to nullable integer, then to regular int where possible
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                df_clean[col] = df_clean[col].apply(lambda x: int(x) if pd.notnull(x) and x == x else None)
            else:
                # Convert to float, handling NaN
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                df_clean[col] = df_clean[col].apply(lambda x: float(x) if pd.notnull(x) and x == x and abs(x) != float('inf') else None)
        elif pd.api.types.is_datetime64_any_dtype(df_clean[col]):
            # Handle datetime columns
            df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ').where(pd.notnull(df_clean[col]), None)
        elif pd.api.types.is_bool_dtype(df_clean[col]):
            # Handle boolean columns
            df_clean[col] = df_clean[col].apply(lambda x: bool(x) if pd.notnull(x) else None)
    
    return df_clean

print("Cleaning data for Salesforce compatibility...")
df_mapped.columns = df_mapped.columns.str.strip()
df_transformed = clean_dataframe_for_salesforce(df_mapped)

# --- Step 11: Categorize Transform Success and Failure ---
def categorize_transform_results(df_original, df_transformed, lookup_fields, selected_object, sf_conn):
    """
    Categorize records into transform success and failure based on:
    1. Lookup field changes
    2. Salesforce picklist value validation  
    3. Salesforce unique field validation
    
    Rules:
    - Transform Failure: If any lookup field data remains the same as original raw data
                        OR picklist values don't match Salesforce picklist options
                        OR unique field values are duplicated
    - Transform Success: If all validations pass
    """
    # Get Salesforce object metadata for validation
    print(f"Fetching Salesforce metadata for {selected_object}...")
    try:
        object_metadata = getattr(sf_conn, selected_object).describe()
        sf_fields = {field['name']: field for field in object_metadata['fields']}
        print(f"Retrieved metadata for {len(sf_fields)} fields in {selected_object}")
    except Exception as e:
        print(f"Warning: Could not fetch Salesforce metadata: {e}")
        sf_fields = {}
    
    # Add row index for tracking
    df_original_indexed = df_original.reset_index(drop=True)
    df_transformed_indexed = df_transformed.reset_index(drop=True)
    
    # Initialize lists to track success and failure records
    success_indices = []
    failure_indices = []
    transform_details = []
    
    print(f"Analyzing transform results for {len(df_transformed_indexed)} records...")
    print(f"Checking {len(lookup_fields)} lookup field(s): {list(lookup_fields.keys())}")
    print(f"Validating picklist and unique field constraints...")
    
    for idx in range(len(df_transformed_indexed)):
        record_failed = False
        record_details = {
            'row_index': idx,
            'lookup_fields_checked': [],
            'unchanged_fields': [],
            'changed_fields': [],
            'picklist_failures': [],
            'unique_field_failures': [],
            'validation_errors': []
        }
        
        # Check 1: Lookup field transformations
        for lookup_field in lookup_fields.keys():
            if lookup_field in df_original_indexed.columns and lookup_field in df_transformed_indexed.columns:
                original_value = df_original_indexed.iloc[idx][lookup_field]
                transformed_value = df_transformed_indexed.iloc[idx][lookup_field]
                
                record_details['lookup_fields_checked'].append(lookup_field)
                
                # Convert values to string for comparison (handle NaN, None, etc.)
                orig_str = str(original_value).strip() if pd.notnull(original_value) else ''
                trans_str = str(transformed_value).strip() if pd.notnull(transformed_value) else ''
                
                # If the value is exactly the same (not transformed), mark as failure
                if orig_str == trans_str and orig_str != '':
                    record_failed = True
                    record_details['unchanged_fields'].append({
                        'field': lookup_field,
                        'value': orig_str
                    })
                elif orig_str != trans_str:
                    record_details['changed_fields'].append({
                        'field': lookup_field,
                        'original': orig_str,
                        'transformed': trans_str
                    })
        
        # Check 2: Picklist value validation
        for field_name, field_value in df_transformed_indexed.iloc[idx].items():
            if field_name in sf_fields and sf_fields[field_name]['type'] == 'picklist':
                if pd.notnull(field_value) and str(field_value).strip() != '':
                    # Get valid picklist values
                    valid_values = []
                    if 'picklistValues' in sf_fields[field_name]:
                        valid_values = [pv['value'] for pv in sf_fields[field_name]['picklistValues'] if pv['active']]
                    
                    # Check if current value is in valid picklist values
                    current_value = str(field_value).strip()
                    if valid_values and current_value not in valid_values:
                        record_failed = True
                        record_details['picklist_failures'].append({
                            'field': field_name,
                            'invalid_value': current_value,
                            'valid_values': valid_values[:10]  # Show first 10 valid values
                        })
        
        # Check 3: Unique field validation (check for duplicates within the dataset)
        for field_name, field_meta in sf_fields.items():
            if (field_name in df_transformed_indexed.columns and 
                field_meta.get('unique', False) and 
                pd.notnull(df_transformed_indexed.iloc[idx][field_name]) and
                str(df_transformed_indexed.iloc[idx][field_name]).strip() != ''):
                
                current_value = df_transformed_indexed.iloc[idx][field_name]
                
                # Check for duplicates in the dataset (excluding current row)
                duplicate_mask = (df_transformed_indexed[field_name] == current_value) & (df_transformed_indexed.index != idx)
                duplicate_count = duplicate_mask.sum()
                
                if duplicate_count > 0:
                    record_failed = True
                    duplicate_indices = df_transformed_indexed.index[duplicate_mask].tolist()
                    record_details['unique_field_failures'].append({
                        'field': field_name,
                        'duplicate_value': str(current_value),
                        'duplicate_row_indices': duplicate_indices[:5]  # Show first 5 duplicate rows
                    })
        
        # Determine final status and reason
        if not record_details['lookup_fields_checked'] and not record_details['picklist_failures'] and not record_details['unique_field_failures']:
            success_indices.append(idx)
            record_details['reason'] = 'No validations required (no lookup/picklist/unique fields)'
        elif record_failed:
            failure_indices.append(idx)
            failure_reasons = []
            if record_details['unchanged_fields']:
                failure_reasons.append(f"Unchanged lookup fields: {[f['field'] for f in record_details['unchanged_fields']]}")
            if record_details['picklist_failures']:
                failure_reasons.append(f"Invalid picklist values: {[f['field'] for f in record_details['picklist_failures']]}")
            if record_details['unique_field_failures']:
                failure_reasons.append(f"Duplicate unique field values: {[f['field'] for f in record_details['unique_field_failures']]}")
            record_details['reason'] = "; ".join(failure_reasons)
        else:
            success_indices.append(idx)
            record_details['reason'] = 'All validations passed (lookup fields transformed, picklist values valid, unique fields unique)'
        
        transform_details.append(record_details)
    
    # Create success and failure DataFrames
    df_success = df_transformed_indexed.iloc[success_indices].copy() if success_indices else pd.DataFrame()
    df_failure = df_transformed_indexed.iloc[failure_indices].copy() if failure_indices else pd.DataFrame()
    
    # Add transform status column with detailed validation info
    if not df_success.empty:
        df_success['Transform_Status'] = 'SUCCESS'
        df_success['Transform_Reason'] = [transform_details[i]['reason'] for i in success_indices]
        df_success['Validation_Details'] = ['All validations passed' for _ in success_indices]
    
    if not df_failure.empty:
        df_failure['Transform_Status'] = 'FAILURE' 
        df_failure['Transform_Reason'] = [transform_details[i]['reason'] for i in failure_indices]
        
        # Add detailed validation failure information
        validation_details = []
        for i in failure_indices:
            details = transform_details[i]
            detail_parts = []
            if details['unchanged_fields']:
                detail_parts.append(f"Unchanged: {', '.join([f['field'] for f in details['unchanged_fields']])}")
            if details['picklist_failures']:
                for pf in details['picklist_failures']:
                    detail_parts.append(f"Invalid picklist {pf['field']}: '{pf['invalid_value']}'")
            if details['unique_field_failures']:
                for uf in details['unique_field_failures']:
                    detail_parts.append(f"Duplicate unique {uf['field']}: '{uf['duplicate_value']}'")
            validation_details.append("; ".join(detail_parts))
        
        df_failure['Validation_Details'] = validation_details
    
    # Summary with detailed breakdown
    success_count = len(success_indices)
    failure_count = len(failure_indices)
    total_count = len(df_transformed_indexed)
    
    # Count different types of failures
    lookup_failures = sum(1 for i in failure_indices if transform_details[i]['unchanged_fields'])
    picklist_failures = sum(1 for i in failure_indices if transform_details[i]['picklist_failures']) 
    unique_failures = sum(1 for i in failure_indices if transform_details[i]['unique_field_failures'])
    
    print(f"\nTransform Results Summary:")
    print(f"✓ Transform Success: {success_count} records ({success_count/total_count*100:.1f}%)")
    print(f"✗ Transform Failure: {failure_count} records ({failure_count/total_count*100:.1f}%)")
    if failure_count > 0:
        print(f"  - Lookup transformation failures: {lookup_failures}")
        print(f"  - Picklist validation failures: {picklist_failures}")
        print(f"  - Unique field constraint failures: {unique_failures}")
    print(f"📊 Total Records: {total_count}")
    
    return df_success, df_failure, {
        'success_count': success_count,
        'failure_count': failure_count,
        'total_count': total_count,
        'success_percentage': success_count/total_count*100 if total_count > 0 else 0,
        'failure_percentage': failure_count/total_count*100 if total_count > 0 else 0,
        'lookup_failures': lookup_failures,
        'picklist_failures': picklist_failures,
        'unique_failures': unique_failures,
        'details': transform_details
    }

# Categorize the transform results
if lookup_fields:
    print("Categorizing transform results based on lookup field changes and Salesforce validations...")
    df_transform_success, df_transform_failure, transform_summary = categorize_transform_results(
        df_original_raw, df_transformed, lookup_fields, selected_object, sf_conn
    )
else:
    print("No lookup fields found - validating against Salesforce picklist and unique field constraints...")
    df_transform_success, df_transform_failure, transform_summary = categorize_transform_results(
        df_original_raw, df_transformed, {}, selected_object, sf_conn
    )

# --- Step 10: Validate JSON Compliance ---
def validate_json_compliance(df):
    """Validate that DataFrame can be converted to JSON"""
    try:
        test_records = df.head(1).to_dict('records')
        json.dumps(test_records, allow_nan=False)
        return True
    except (ValueError, TypeError) as e:
        print(f"Data validation failed: {e}")
        return False

if not validate_json_compliance(df_transformed):
    print("Warning: Data contains values that may not be JSON compliant.")

# --- Final Data Preview Before Saving ---
def show_final_preview(df_success, df_failure, selected_object, transform_summary):
    """Show final data preview with transform success/failure summary before saving"""
    import tkinter as tk
    from tkinter import ttk
    
    user_choice = {'value': None}
    
    def on_save():
        user_choice['value'] = 'save'
        preview_win.destroy()
    
    def on_cancel():
        user_choice['value'] = 'cancel'
        preview_win.destroy()
    
    def show_success_data():
        current_tab['value'] = 'success'
        populate_treeview(tree, df_success, 'success')
    
    def show_failure_data():
        current_tab['value'] = 'failure'
        populate_treeview(tree, df_failure, 'failure')
    
    def populate_treeview(tree_widget, dataframe, tab_type):
        # Clear existing data
        for item in tree_widget.get_children():
            tree_widget.delete(item)
        
        if dataframe.empty:
            tree_widget.insert('', tk.END, values=['No data to display'])
            return
        
        # Update columns
        columns = list(dataframe.columns)
        tree_widget['columns'] = columns
        tree_widget['show'] = 'headings'
        
        # Configure column headings and widths
        for col in columns:
            tree_widget.heading(col, text=col)
            tree_widget.column(col, width=120, minwidth=80)
            # Highlight transform status columns
            if col in ['Transform_Status', 'Transform_Reason', 'Validation_Details']:
                color = 'green' if tab_type == 'success' else 'red'
                tree_widget.heading(col, text=f"📊 {col}")
        
        # Add data to treeview (first 100 rows)
        preview_df = dataframe.head(100)
        for idx, row in preview_df.iterrows():
            values = [str(val) if val is not None else '' for val in row.values]
            tree_widget.insert('', tk.END, values=values)
    
    current_tab = {'value': 'success'}
    
    root = tk.Tk()
    root.withdraw()
    
    preview_win = tk.Toplevel()
    preview_win.title("Final Transform Results Preview")
    preview_win.geometry("1400x900")
    preview_win.grab_set()
    
    # Header info
    header_frame = tk.Frame(preview_win)
    header_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(header_frame, text=f"Transform Results Preview", 
             font=("Arial", 16, "bold")).pack()
    tk.Label(header_frame, text=f"Target Object: {selected_object} | Total Records: {transform_summary['total_count']}", 
             font=("Arial", 12)).pack()
    
    # Summary frame with color-coded stats
    summary_frame = tk.Frame(preview_win)
    summary_frame.pack(pady=5, padx=20, fill=tk.X)
    
    # Success stats (green)
    success_frame = tk.Frame(summary_frame)
    success_frame.pack(side=tk.LEFT, padx=20)
    tk.Label(success_frame, text="✓ TRANSFORM SUCCESS", 
             font=("Arial", 11, "bold"), fg="green").pack()
    tk.Label(success_frame, text=f"{transform_summary['success_count']} records ({transform_summary['success_percentage']:.1f}%)", 
             font=("Arial", 10), fg="green").pack()
    
    # Failure stats (red)
    failure_frame = tk.Frame(summary_frame)
    failure_frame.pack(side=tk.LEFT, padx=20)
    tk.Label(failure_frame, text="✗ TRANSFORM FAILURE", 
             font=("Arial", 11, "bold"), fg="red").pack()
    tk.Label(failure_frame, text=f"{transform_summary['failure_count']} records ({transform_summary['failure_percentage']:.1f}%)", 
             font=("Arial", 10), fg="red").pack()
    
    # Tab selection frame
    tab_frame = tk.Frame(preview_win)
    tab_frame.pack(pady=10, padx=20, fill=tk.X)
    
    tk.Label(tab_frame, text="View Data:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    
    success_btn = tk.Button(tab_frame, text=f"Success Data ({transform_summary['success_count']})", 
                           command=show_success_data, bg="#E8F5E8", 
                           font=("Arial", 10), width=20)
    success_btn.pack(side=tk.LEFT, padx=10)
    
    failure_btn = tk.Button(tab_frame, text=f"Failure Data ({transform_summary['failure_count']})", 
                           command=show_failure_data, bg="#FFE8E8", 
                           font=("Arial", 10), width=20)
    failure_btn.pack(side=tk.LEFT, padx=10)
    
    # Data preview frame
    data_frame = tk.Frame(preview_win)
    data_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
    
    # Create Treeview for data display
    tree = ttk.Treeview(data_frame)
    
    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Pack scrollbars and treeview
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Show success data by default
    show_success_data()
    
    # Button frame
    button_frame = tk.Frame(preview_win)
    button_frame.pack(pady=20)
    
    # Save button (green)
    save_btn = tk.Button(button_frame, text="Save All Transform Data", 
                        command=on_save, bg="#4CAF50", fg="white", 
                        font=("Arial", 12, "bold"), width=25, height=2)
    save_btn.pack(side=tk.LEFT, padx=20)
    
    # Cancel button (red)
    cancel_btn = tk.Button(button_frame, text="Cancel", 
                          command=on_cancel, bg="#f44336", fg="white", 
                          font=("Arial", 12, "bold"), width=20, height=2)
    cancel_btn.pack(side=tk.LEFT, padx=20)
    
    # Additional info
    info_frame = tk.Frame(preview_win)
    info_frame.pack(pady=(0,10))
    tk.Label(info_frame, text="Switch between Success/Failure tabs | Showing first 100 rows per category", 
             font=("Arial", 9), fg="gray").pack()
    tk.Label(info_frame, text="Success: All validations passed | Failure: Lookup/Picklist/Unique field validation failed", 
             font=("Arial", 9), fg="blue").pack()
    
    preview_win.wait_window()
    root.destroy()
    
    return user_choice['value']

print("Preparing final transform results preview...")
user_decision = show_final_preview(df_transform_success, df_transform_failure, selected_object, transform_summary)

if user_decision != 'save':
    print("=" * 60)
    print("✗ OPERATION ABORTED BY USER")
    print("✗ User denied saving the transformed data.")
    print("✗ No files were saved. Operation cancelled.")
    print("=" * 60)
    exit()

print("✓ User confirmed saving transformed data. Proceeding...")

# --- Step 12: Save Transform Success and Failure Data ---
# Create folder structure: C:\DM_toolkit\DataLoader_Logs\dataload\Dataload_{selectedorg}\{objectname}\TransformedData\
root_folder = 'DataLoader_Logs'
dataload_folder = os.path.join(root_folder, 'dataload')
org_folder = os.path.join(dataload_folder, f'Dataload_{selected_org}')
object_folder = os.path.join(org_folder, selected_object)
transformed_data_folder = os.path.join(object_folder, 'TransformedData')
os.makedirs(transformed_data_folder, exist_ok=True)

# Save files with timestamp for uniqueness
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# File paths
success_file_path = os.path.join(transformed_data_folder, 'transform_success.csv')
failure_file_path = os.path.join(transformed_data_folder, 'transform_failure.csv')
transformed_data_file_path = os.path.join(transformed_data_folder, 'Transformed_Data.csv')
# summary_file_path = os.path.join(transformed_data_folder, f'transform_summary_{timestamp}.txt')

# Save transform success data (exclude validation columns)
if not df_transform_success.empty:
    # Remove the last 3 columns (Transform_Status, Transform_Reason, Validation_Details) for CSV export
    df_success_clean = df_transform_success.drop(columns=['Transform_Status', 'Transform_Reason', 'Validation_Details'], errors='ignore')
    df_success_clean.to_csv(success_file_path, index=False)
    print(f"✓ Transform success data saved: {success_file_path}")
else:
    print("ℹ No transform success records to save")

# Save transform failure data (exclude validation columns)
if not df_transform_failure.empty:
    # Remove the last 3 columns (Transform_Status, Transform_Reason, Validation_Details) for CSV export
    df_failure_clean = df_transform_failure.drop(columns=['Transform_Status', 'Transform_Reason', 'Validation_Details'], errors='ignore')
    df_failure_clean.to_csv(failure_file_path, index=False)
    print(f"✗ Transform failure data saved: {failure_file_path}")
else:
    print("ℹ No transform failure records to save")

# Save combined transformed data (all records without validation columns)
df_transformed_clean = df_transformed.copy()
df_transformed_clean.to_csv(transformed_data_file_path, index=False)
print(f"📄 All transformed data saved: {transformed_data_file_path}")

# Save detailed summary report (commented out - uncomment to enable)
# with open(summary_file_path, 'w') as summary_file:
#     summary_file.write("TRANSFORM RESULTS SUMMARY REPORT\n")
#     summary_file.write("=" * 50 + "\n\n")
#     summary_file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
#     summary_file.write(f"Salesforce Org: {selected_org}\n")
#     summary_file.write(f"Target Object: {selected_object}\n\n")
#     
#     summary_file.write("OVERALL STATISTICS:\n")
#     summary_file.write(f"Total Records Processed: {transform_summary['total_count']}\n")
#     summary_file.write(f"Transform Success: {transform_summary['success_count']} ({transform_summary['success_percentage']:.1f}%)\n")
#     summary_file.write(f"Transform Failure: {transform_summary['failure_count']} ({transform_summary['failure_percentage']:.1f}%)\n\n")
#     
#     if transform_summary['failure_count'] > 0:
#         summary_file.write("FAILURE BREAKDOWN:\n")
#         summary_file.write(f"- Lookup transformation failures: {transform_summary.get('lookup_failures', 0)}\n")
#         summary_file.write(f"- Picklist validation failures: {transform_summary.get('picklist_failures', 0)}\n")
#         summary_file.write(f"- Unique field constraint failures: {transform_summary.get('unique_failures', 0)}\n\n")
#     
#     if lookup_fields:
#         summary_file.write("LOOKUP FIELDS PROCESSED:\n")
#         for lookup_field, related_object in lookup_fields.items():
#             lookup_count = lookup_count_summary.get(lookup_field, 0)
#             summary_file.write(f"- {lookup_field} -> {related_object} ({lookup_count} values resolved)\n")
#         summary_file.write(f"\nTotal Lookup Values Resolved: {sum(lookup_count_summary.values())}\n\n")
#     
#     summary_file.write("VALIDATION LOGIC:\n")
#     summary_file.write("- SUCCESS: All validations passed (lookup fields transformed, picklist values valid, unique fields unique)\n")
#     summary_file.write("- FAILURE: One or more validations failed:\n")
#     summary_file.write("  * Lookup fields remain unchanged from original raw data\n")
#     summary_file.write("  * Picklist values don't match Salesforce picklist options\n")
#     summary_file.write("  * Unique field values are duplicated within the dataset\n\n")
#     
#     summary_file.write("FILES GENERATED:\n")
#     if not df_transform_success.empty:
#         summary_file.write(f"- Success Data: {success_file_path}\n")
#     if not df_transform_failure.empty:
#         summary_file.write(f"- Failure Data: {failure_file_path}\n")
#     summary_file.write(f"- Summary Report: {summary_file_path}\n")

# print(f"📊 Transform summary report saved: {summary_file_path}")

print(f"\nTransformation completed successfully!")
print(f"Transform Data saved to folder: {transformed_data_folder}")
print(f"✓ Success records: {transform_summary['success_count']}")
print(f"✗ Failure records: {transform_summary['failure_count']}")
print(f"📊 Total records: {transform_summary['total_count']}")

if lookup_fields:
    print(f"🔍 Processed {len(lookup_fields)} lookup field(s): {list(lookup_fields.keys())}")
    total_resolved = sum(lookup_count_summary.values()) if 'lookup_count_summary' in locals() else 0
    print(f"🔗 Total lookup values resolved: {total_resolved}")

# Show completion dialog with detailed summary
lookup_summary = ""
if lookup_fields:
    total_resolved = sum(lookup_count_summary.values()) if 'lookup_count_summary' in locals() else 0
    lookup_summary = f"Lookup fields processed: {len(lookup_fields)}\nTotal values resolved: {total_resolved}\n\n"

success_files_text = ""
if not df_transform_success.empty:
    success_files_text += f"Success data: {os.path.basename(success_file_path)}\n"
if not df_transform_failure.empty:
    success_files_text += f"Failure data: {os.path.basename(failure_file_path)}\n"
success_files_text += f"All transformed data: {os.path.basename(transformed_data_file_path)}\n"
# success_files_text += f"Summary report: {os.path.basename(summary_file_path)}"

tkinter.messagebox.showinfo(
    "Transform Results - Enhanced Validation Analysis",
    f"Data transformation completed with comprehensive validation!\n\n"
    f"📊 TRANSFORM RESULTS:\n"
    f"✓ Success: {transform_summary['success_count']} records ({transform_summary['success_percentage']:.1f}%)\n"
    f"✗ Failure: {transform_summary['failure_count']} records ({transform_summary['failure_percentage']:.1f}%)\n"
    f"📋 Total: {transform_summary['total_count']} records\n\n"
    f"🔍 FAILURE BREAKDOWN:\n"
    f"• Lookup failures: {transform_summary.get('lookup_failures', 0)}\n"
    f"• Picklist failures: {transform_summary.get('picklist_failures', 0)}\n"
    f"• Unique field failures: {transform_summary.get('unique_failures', 0)}\n\n"
    f"{lookup_summary}"
    f"📁 FILES SAVED:\n{success_files_text}\n\n"
    f"📂 Location: {transformed_data_folder}"
)

print(f"\n📁 File locations:")
if not df_transform_success.empty:
    print(f"✓ Transform success data: {success_file_path}")
if not df_transform_failure.empty:
    print(f"✗ Transform failure data: {failure_file_path}")
print(f"📄 All transformed data: {transformed_data_file_path}")
# print(f"📊 Summary report: {summary_file_path}")
print(f"📂 TransformedData folder: {transformed_data_folder}")
