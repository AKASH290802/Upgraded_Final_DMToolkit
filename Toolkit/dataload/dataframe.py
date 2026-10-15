import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import dataset.Connections as Connections
import pandas as pd
import dataset.Org_selection as Org_selection
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Valid data sources
SOURCES = ['excel/csv', 'sql', 'salesforce']

class DataExtractionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Data Extraction Tool")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # Initialize variables
        self.selected_org = None
        self.salesforce_conn = None
        self.sql_engine = None
        self.object_name = None
        self.data_source = None
        self.df = None
        
        # Setup GUI
        self.setup_gui()
        
    def setup_gui(self):
        # Main container with scrollbar
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_frame, text="Data Extraction Tool", 
                              font=("Arial", 16, "bold"), fg="#2E86AB")
        title_label.pack(pady=(0, 20))
        
        # Step 1: Organization Selection
        step1_frame = tk.LabelFrame(main_frame, text="Step 1: Select Organization", 
                                   font=("Arial", 12, "bold"), padx=10, pady=10)
        step1_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.org_var = tk.StringVar()
        self.org_dropdown = ttk.Combobox(step1_frame, textvariable=self.org_var, 
                                        width=40, state="readonly")
        self.org_dropdown.pack(side=tk.LEFT, padx=(0, 10))
        
        org_btn = tk.Button(step1_frame, text="Load Organizations", 
                           command=self.load_organizations, bg="#4CAF50", fg="white")
        org_btn.pack(side=tk.LEFT)
        
        # Step 2: Data Source Selection
        step2_frame = tk.LabelFrame(main_frame, text="Step 2: Select Data Source", 
                                   font=("Arial", 12, "bold"), padx=10, pady=10)
        step2_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.source_var = tk.StringVar(value=SOURCES[0])
        for i, source in enumerate(SOURCES):
            rb = tk.Radiobutton(step2_frame, text=source.upper(), variable=self.source_var, 
                               value=source, font=("Arial", 10))
            rb.pack(side=tk.LEFT, padx=20)
        
        # Step 3: Object Selection
        step3_frame = tk.LabelFrame(main_frame, text="Step 3: Select Salesforce Object", 
                                   font=("Arial", 12, "bold"), padx=10, pady=10)
        step3_frame.pack(fill=tk.X, pady=(0, 10))
        
        object_search_frame = tk.Frame(step3_frame)
        object_search_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(object_search_frame, text="Filter:").pack(side=tk.LEFT)
        self.object_filter_var = tk.StringVar()
        self.object_filter_var.trace_add('write', self.filter_objects)
        filter_entry = tk.Entry(object_search_frame, textvariable=self.object_filter_var, width=30)
        filter_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        load_objects_btn = tk.Button(object_search_frame, text="Load Objects", 
                                    command=self.load_objects, bg="#2196F3", fg="white")
        load_objects_btn.pack(side=tk.LEFT)
        
        self.object_listbox = tk.Listbox(step3_frame, height=8, width=60)
        self.object_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        object_scroll = tk.Scrollbar(step3_frame, orient=tk.VERTICAL)
        object_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.object_listbox.config(yscrollcommand=object_scroll.set)
        object_scroll.config(command=self.object_listbox.yview)
        
        # Step 4: Data Source Specific Options
        step4_frame = tk.LabelFrame(main_frame, text="Step 4: Source Options", 
                                   font=("Arial", 12, "bold"), padx=10, pady=10)
        step4_frame.pack(fill=tk.X, pady=(0, 10))
        
        # File selection for Excel/CSV
        self.file_frame = tk.Frame(step4_frame)
        tk.Label(self.file_frame, text="Selected File:").pack(side=tk.LEFT)
        self.file_label = tk.Label(self.file_frame, text="No file selected", 
                                  fg="gray", width=40, anchor="w")
        self.file_label.pack(side=tk.LEFT, padx=(5, 10))
        file_btn = tk.Button(self.file_frame, text="Browse", command=self.select_file)
        file_btn.pack(side=tk.LEFT)
        
        # SQL options
        self.sql_frame = tk.Frame(step4_frame)
        self.sql_access_var = tk.BooleanVar()
        sql_check = tk.Checkbutton(self.sql_frame, text="I have SQL access", 
                                  variable=self.sql_access_var)
        sql_check.pack(side=tk.LEFT, padx=(0, 20))
        
        self.sql_query_var = tk.BooleanVar()
        sql_query_check = tk.Checkbutton(self.sql_frame, text="I have a custom query", 
                                        variable=self.sql_query_var, 
                                        command=self.toggle_sql_query)
        sql_query_check.pack(side=tk.LEFT)
        
        self.sql_query_text = tk.Text(step4_frame, height=3, width=60)
        
        # Salesforce options
        self.sf_frame = tk.Frame(step4_frame)
        
        sf_query_frame = tk.Frame(self.sf_frame)
        sf_query_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.sf_query_var = tk.BooleanVar()
        sf_query_check = tk.Checkbutton(sf_query_frame, text="I have a custom SOQL query", 
                                       variable=self.sf_query_var, 
                                       command=self.toggle_sf_query)
        sf_query_check.pack(side=tk.LEFT)
        
        sf_limit_frame = tk.Frame(self.sf_frame)
        sf_limit_frame.pack(fill=tk.X)
        
        tk.Label(sf_limit_frame, text="Record Limit:").pack(side=tk.LEFT)
        self.sf_limit_var = tk.StringVar(value="100")
        limit_entry = tk.Entry(sf_limit_frame, textvariable=self.sf_limit_var, width=20)
        limit_entry.pack(side=tk.LEFT, padx=(5, 10))
        tk.Label(sf_limit_frame, text="(Enter number or 'all')").pack(side=tk.LEFT)
        
        self.sf_query_text = tk.Text(step4_frame, height=3, width=60)
        
        # Initially show file frame
        self.file_frame.pack(fill=tk.X)
        
        # Step 5: Execute
        step5_frame = tk.LabelFrame(main_frame, text="Step 5: Execute Extraction", 
                                   font=("Arial", 12, "bold"), padx=10, pady=10)
        step5_frame.pack(fill=tk.X, pady=(0, 10))
        
        execute_btn = tk.Button(step5_frame, text="Extract Data", command=self.extract_data,
                               bg="#FF9800", fg="white", font=("Arial", 12, "bold"),
                               height=2, width=20)
        execute_btn.pack(pady=10)
        
        # Data Preview
        preview_frame = tk.LabelFrame(main_frame, text="Data Preview", 
                                     font=("Arial", 12, "bold"), padx=10, pady=10)
        preview_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Preview controls
        preview_controls = tk.Frame(preview_frame)
        preview_controls.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(preview_controls, text="Rows to preview:").pack(side=tk.LEFT)
        self.preview_rows_var = tk.StringVar(value="10")
        preview_entry = tk.Entry(preview_controls, textvariable=self.preview_rows_var, width=10)
        preview_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        preview_btn = tk.Button(preview_controls, text="Refresh Preview", 
                           command=self.refresh_preview, bg="#9C27B0", fg="white")
        preview_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        clear_preview_btn = tk.Button(preview_controls, text="Clear Preview", 
                                 command=self.clear_preview, bg="#757575", fg="white")
        clear_preview_btn.pack(side=tk.LEFT)
        
        # Data info label
        self.data_info_label = tk.Label(preview_controls, text="No data loaded", fg="gray")
        self.data_info_label.pack(side=tk.RIGHT)
        
        # Preview display with scrollbars
        preview_display_frame = tk.Frame(preview_frame)
        preview_display_frame.pack(fill=tk.X)
        
        # Create Treeview for tabular data display
        self.preview_tree = ttk.Treeview(preview_display_frame, height=8)
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbars for preview
        preview_v_scroll = ttk.Scrollbar(preview_display_frame, orient=tk.VERTICAL, 
                                    command=self.preview_tree.yview)
        preview_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_tree.configure(yscrollcommand=preview_v_scroll.set)
        
        preview_h_scroll = ttk.Scrollbar(preview_frame, orient=tk.HORIZONTAL, 
                                    command=self.preview_tree.xview)
        preview_h_scroll.pack(fill=tk.X, pady=(5, 0))
        self.preview_tree.configure(xscrollcommand=preview_h_scroll.set)
        
        # Initialize field selection variables
        self.field_vars = {}
        self.available_fields = []
        
        # Status and Progress
        status_frame = tk.LabelFrame(main_frame, text="Status", 
                                    font=("Arial", 12, "bold"), padx=10, pady=10)
        status_frame.pack(fill=tk.BOTH, expand=True)
        
        self.status_text = tk.Text(status_frame, height=6, width=60, state=tk.DISABLED)
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        status_scroll = tk.Scrollbar(status_frame, orient=tk.VERTICAL)
        status_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.config(yscrollcommand=status_scroll.set)
        status_scroll.config(command=self.status_text.yview)
        
        # Bind source selection to show/hide options
        self.source_var.trace_add('write', self.on_source_change)
        
    def log_status(self, message):
        """Add message to status text widget"""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update()
        
    def load_organizations(self):
        try:
            self.log_status("Loading organizations...")
            credentials_path = r"C:\DM_toolkit\Services\linkedservices.json"
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
            
            import json
            with open(credentials_path, 'r') as f:
                creds = json.load(f)
            
            orgs = list(creds.keys())
            self.org_dropdown['values'] = orgs
            if orgs:
                self.org_dropdown.current(0)
            self.log_status(f"Loaded {len(orgs)} organizations")
        except Exception as e:
            self.log_status(f"Error loading organizations: {e}")
            messagebox.showerror("Error", f"Failed to load organizations: {e}")
    
    def load_objects(self):
        try:
            if not self.org_var.get():
                messagebox.showwarning("Warning", "Please select an organization first")
                return
                
            self.log_status("Connecting to Salesforce...")
            self.selected_org = self.org_var.get()
            credentials_path = r"C:\DM_toolkit\Services\linkedservices.json"
            
            self.salesforce_conn = Connections.get_salesforce_connection(
                file_path=credentials_path, org_name=self.selected_org)
            
            self.log_status("Loading Salesforce objects...")
            object_list = list(self.salesforce_conn.describe()['sobjects'])
            object_names = [obj['name'] for obj in object_list]
            
            # Filter for Account and WOD objects
            filtered_objects = [name for name in object_names 
                              if name.lower() == 'account' or 'wod' in name.lower()]
            filtered_objects.sort()
            
            self.all_objects = filtered_objects
            self.update_object_list(filtered_objects)
            
            self.log_status(f"Loaded {len(filtered_objects)} objects")
            
        except Exception as e:
            self.log_status(f"Error loading objects: {e}")
            messagebox.showerror("Error", f"Failed to load objects: {e}")
    
    def filter_objects(self, *args):
        if hasattr(self, 'all_objects'):
            filter_text = self.object_filter_var.get().lower()
            filtered = [obj for obj in self.all_objects if filter_text in obj.lower()]
            self.update_object_list(filtered)
    
    def update_object_list(self, objects):
        self.object_listbox.delete(0, tk.END)
        for obj in objects:
            self.object_listbox.insert(tk.END, obj)
    
    def on_source_change(self, *args):
        # Hide all frames first
        self.file_frame.pack_forget()
        self.sql_frame.pack_forget()
        self.sf_frame.pack_forget()
        self.sql_query_text.pack_forget()
        self.sf_query_text.pack_forget()
        
        source = self.source_var.get()
        if source == 'excel/csv':
            self.file_frame.pack(fill=tk.X)
        elif source == 'sql':
            self.sql_frame.pack(fill=tk.X)
        elif source == 'salesforce':
            self.sf_frame.pack(fill=tk.X)
    
    def toggle_sql_query(self):
        if self.sql_query_var.get():
            self.sql_query_text.pack(fill=tk.X, pady=(5, 0))
        else:
            self.sql_query_text.pack_forget()
    
    def toggle_sf_query(self):
        if self.sf_query_var.get():
            self.sf_query_text.pack(fill=tk.X, pady=(5, 0))
        else:
            self.sf_query_text.pack_forget()
    
    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="Select a CSV or Excel file",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx;*.xls"), ("All files", "*.*")])
        if file_path:
            self.selected_file = file_path
            self.file_label.config(text=os.path.basename(file_path), fg="black")
            self.log_status(f"Selected file: {os.path.basename(file_path)}")
    
    def extract_data(self):
        try:
            # Validation
            if not self.selected_org:
                messagebox.showwarning("Warning", "Please select an organization")
                return
            
            if not self.object_listbox.curselection():
                messagebox.showwarning("Warning", "Please select a Salesforce object")
                return
            
            self.object_name = self.object_listbox.get(self.object_listbox.curselection()[0])
            self.data_source = self.source_var.get()
            
            self.log_status(f"Starting data extraction...")
            self.log_status(f"Organization: {self.selected_org}")
            self.log_status(f"Object: {self.object_name}")
            self.log_status(f"Source: {self.data_source}")
            
            # Extract data based on source
            if self.data_source == 'excel/csv':
                self.extract_from_file()
            elif self.data_source == 'sql':
                self.extract_from_sql()
            elif self.data_source == 'salesforce':
                self.extract_from_salesforce()
            
            # Save data
            self.save_data()
            
        except Exception as e:
            self.log_status(f"Error during extraction: {e}")
            messagebox.showerror("Error", f"Extraction failed: {e}")
    
    def extract_from_file(self):
        if not hasattr(self, 'selected_file'):
            raise ValueError("Please select a file first")
        
        self.log_status("Reading file...")
        file_path = self.selected_file
        
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            self.df = pd.read_excel(file_path)
        elif file_path.endswith('.csv'):
            try:
                self.df = pd.read_csv(file_path)
            except UnicodeDecodeError:
                self.df = pd.read_csv(file_path, encoding='latin1')
        else:
            raise ValueError("Unsupported file format")
        
        self.log_status(f"Loaded {len(self.df)} rows from file")
    
    def extract_from_sql(self):
        if not self.sql_access_var.get():
            raise ValueError("SQL access is required for this option")
        
        self.log_status("Establishing SQL connection...")
        credentials_path = r"C:\DM_toolkit\Services\linkedservices.json"
        sql_conn, self.sql_engine = Connections.get_sql_connection(file_path=credentials_path)
        
        if self.sql_query_var.get():
            sql_query = self.sql_query_text.get("1.0", tk.END).strip()
        else:
            sql_query = f"SELECT * FROM stg.[{self.object_name}]"
        
        self.log_status(f"Executing SQL query: {sql_query}")
        self.df = Connections.run_sql_query(self.sql_engine, sql_query)
        self.log_status(f"Retrieved {len(self.df)} rows from SQL")
    
    def extract_from_salesforce(self):
        if self.sf_query_var.get():
            sf_query = self.sf_query_text.get("1.0", tk.END).strip()
        else:
            self.log_status("Building comprehensive SOQL query...")
            sf_query = self.build_comprehensive_soql()
        
        self.log_status(f"Executing SOQL query...")
        sf_result = Connections.run_salesforce_query(self.salesforce_conn, sf_query)
        self.df = pd.DataFrame(sf_result['records']).drop(columns='attributes', errors='ignore')
        
        # After self.df = pd.DataFrame(sf_result['records']).drop(columns='attributes', errors='ignore')
        if 'RecordType.Name' in self.df.columns:
            self.df.rename(columns={'RecordType.Name': 'RecordTypeid'}, inplace=True)
        
        self.log_status(f"Retrieved {len(self.df)} rows from Salesforce")
        
        # Flatten all relationship fields (columns with dict values)
        for col in self.df.columns:
            if self.df[col].apply(lambda x: isinstance(x, dict)).any():
                # Try to extract 'Name' or 'ExternalId' or fallback to string
                def extract_value(val):
                    if isinstance(val, dict):
                        for key in ['Name', 'ExternalId', 'Id']:
                            if key in val:
                                return val[key]
                        return str(val)
                    return val
                self.df[col] = self.df[col].apply(extract_value)
    
    def build_comprehensive_soql(self):
        try:
            obj_metadata = getattr(self.salesforce_conn, self.object_name).describe()
            fields = []
            
            for field in obj_metadata['fields']:
                field_name = field['name']
                field_type = field['type']

                fields.append(field_name)

                # Add this block to handle RecordType.Name
                if field_name == "RecordTypeId":
                    fields.append("RecordType.Name")
                
                if field_type == 'reference' and field['referenceTo']:
                    reference_obj = field['referenceTo'][0]
                    relationship_name = field['relationshipName']
                    
                    if relationship_name:
                        try:
                            ref_obj_desc = getattr(self.salesforce_conn, reference_obj).describe()
                            external_id_field = None
                            unique_field = None
                            
                            for ref_field in ref_obj_desc['fields']:
                                if ref_field.get('externalId', False):
                                    external_id_field = ref_field['name']
                                    break
                                elif ref_field.get('unique', False) and ref_field['name'] != 'Id':
                                    unique_field = ref_field['name']
                            
                            if external_id_field:
                                lookup_field = f"{relationship_name}.{external_id_field}"
                            elif unique_field:
                                lookup_field = f"{relationship_name}.{unique_field}"
                            else:
                                lookup_field = f"{relationship_name}.Name"
                            
                            fields.append(lookup_field)
                        except:
                            fields.append(f"{relationship_name}.Name")
            
            fields = list(set([f for f in fields if f]))
            
            limit_value = self.sf_limit_var.get().strip()
            if limit_value.lower() == 'all':
                limit_clause = ""
            else:
                try:
                    limit_num = int(limit_value)
                    limit_clause = f" LIMIT {limit_num}"
                except ValueError:
                    limit_clause = " LIMIT 100"
            
            fields_str = ", ".join(fields)
            return f"SELECT {fields_str} FROM {self.object_name}{limit_clause}"
            
        except Exception as e:
            self.log_status(f"Error building SOQL: {e}, using fallback")
            return f"SELECT Id, Name FROM {self.object_name} LIMIT 100"
    
    def save_data(self):
        root_folder = "DataFiles"
        extract_folder = os.path.join(root_folder, self.selected_org, self.object_name, 
                                     "extract", self.data_source)
        csv_file_name = f"{self.object_name}.csv"
        csv_file_path = os.path.join(extract_folder, csv_file_name)
        
        os.makedirs(extract_folder, exist_ok=True)
        self.df.to_csv(csv_file_path, index=False)
        
        self.log_status(f"Data saved to: {csv_file_path}")
        self.log_status("Extraction completed successfully!")
        messagebox.showinfo("Success", f"Data extracted successfully!\nSaved to: {csv_file_path}")
    
    def refresh_preview(self):
        """Refresh the data preview with current data"""
        if self.df is not None and not self.df.empty:
            self.update_preview()
        else:
            messagebox.showwarning("Warning", "No data to preview. Please extract data first.")

    def clear_preview(self):
        """Clear the data preview"""
        # Clear treeview
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        
        # Clear columns
        self.preview_tree['columns'] = ()
        
        self.log_status("Data preview cleared")

    def update_preview(self):
        """Update the data preview with current dataframe"""
        if self.df is None or self.df.empty:
            self.clear_preview()
            return
        
        try:
            # Get number of rows to display
            try:
                max_rows = int(self.preview_rows_var.get())
            except ValueError:
                max_rows = 10
                self.preview_rows_var.set("10")
        
            # Clear existing treeview
            for item in self.preview_tree.get_children():
                self.preview_tree.delete(item)
        
            # Get data subset
            preview_df = self.df.head(max_rows)
        
            # Configure columns
            columns = list(preview_df.columns)
            self.preview_tree['columns'] = columns
            self.preview_tree['show'] = 'headings'
        
            # Configure column headings and widths
            for col in columns:
                self.preview_tree.heading(col, text=col)
                # Set column width based on content
                max_width = max(len(str(col)), 
                               max(len(str(val)) for val in preview_df[col].head(10) if val is not None))
                self.preview_tree.column(col, width=min(max_width * 8, 200), minwidth=50)
        
            # Insert data rows
            for index, row in preview_df.iterrows():
                values = [str(val) if val is not None else "" for val in row]
                self.preview_tree.insert("", "end", values=values)
        
            # Log preview info
            total_rows = len(self.df)
            shown_rows = min(max_rows, total_rows)
            total_cols = len(self.df.columns)
        
            self.log_status(f"Preview updated: Showing {shown_rows} of {total_rows} rows, {total_cols} columns")
        
        except Exception as e:
            self.log_status(f"Error updating preview: {e}")
            messagebox.showerror("Error", f"Failed to update preview: {e}")
    
    def preview_before_extraction(self):
        """Preview data before extraction, allowing field selection and record limit adjustment"""
        try:
            if not self.selected_org:
                messagebox.showwarning("Warning", "Please select an organization")
                return
            
            if not self.object_listbox.curselection():
                messagebox.showwarning("Warning", "Please select a Salesforce object")
                return
            
            self.object_name = self.object_listbox.get(self.object_listbox.curselection()[0])
            self.data_source = self.source_var.get()
            
            self.log_status(f"Preparing preview for extraction...")
            self.log_status(f"Organization: {self.selected_org}")
            self.log_status(f"Object: {self.object_name}")
            self.log_status(f"Source: {self.data_source}")
            
            # Clear previous field selections
            self.field_vars.clear()
            
            # Show field selection frame
            self.field_selection_frame.pack(fill=tk.X)
            
            # Get available fields for the selected object
            self.log_status("Loading available fields...")
            obj_metadata = getattr(self.salesforce_conn, self.object_name).describe()
            all_fields = [field['name'] for field in obj_metadata['fields']]
            
            # Filter fields based on selection
            selected_fields = [field for field in all_fields if field in self.df.columns]
            
            # Add checkboxes for each field
            self.add_field_checkboxes(selected_fields)
            
            # Set default extraction limit
            self.extraction_limit_var.set("100")
            
            self.log_status(f"Loaded {len(selected_fields)} fields")
            
        except Exception as e:
            self.log_status(f"Error preparing preview: {e}")
            messagebox.showerror("Error", f"Failed to prepare preview: {e}")
    
    def add_field_checkboxes(self, fields):
        """Add checkboxes for field selection"""
        for widget in self.field_checkboxes_frame.winfo_children():
            widget.destroy()
        
        self.field_vars = {field: tk.BooleanVar(value=True) for field in fields}
        
        for field, var in self.field_vars.items():
            cb = tk.Checkbutton(self.field_checkboxes_frame, text=field, variable=var)
            cb.pack(anchor=tk.W)
        
        # Update scroll region to encompass all checkboxes
        self.field_checkboxes_frame.update_idletasks()
        self.field_canvas.config(scrollregion=self.field_canvas.bbox("all"))
    
    def select_all_fields(self):
        """Select all fields for extraction"""
        for var in self.field_vars.values():
            var.set(True)
    
    def deselect_all_fields(self):
        """Deselect all fields"""
        for var in self.field_vars.values():
            var.set(False)
    
    def refresh_preview_with_selected_fields(self):
        """Refresh preview with currently selected fields and record limit"""
        if not self.df.empty and self.field_vars:
            try:
                # Get selected fields
                selected_fields = [field for field, var in self.field_vars.items() if var.get()]
                
                if not selected_fields:
                    messagebox.showwarning("Warning", "No fields selected for extraction")
                    return
                
                # Get record limit
                try:
                    record_limit = int(self.extraction_limit_var.get())
                except ValueError:
                    record_limit = 100
                    self.extraction_limit_var.set("100")
                
                # Limit the number of rows for preview
                preview_df = self.df.head(record_limit)
                
                # Create a subset of the dataframe with selected fields
                self.df_preview = preview_df[selected_fields]
                
                # Update the preview display
                self.update_preview()
                
                self.log_status(f"Preview updated: Showing {len(self.df_preview)} rows, {len(selected_fields)} fields")
            
            except Exception as e:
                self.log_status(f"Error refreshing preview: {e}")
                messagebox.showerror("Error", f"Failed to refresh preview: {e}")
        else:
            messagebox.showwarning("Warning", "No data available for preview")
    
def main():
    root = tk.Tk()
    app = DataExtractionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()