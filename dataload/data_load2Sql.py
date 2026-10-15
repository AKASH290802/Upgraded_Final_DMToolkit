import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path

import pandas as pd
import dataset.Connections as Connections
from sqlalchemy import text, inspect
import re
import logging
import tkinter as tk
from tkinter import simpledialog, filedialog

sql_avialale=input("Do you have SQL Server connection available? (yes/no): ").strip().lower()
if sql_avialale=="no":
    print("Please set up SQL Server connection in linkedservices.json file.")
    sys.exit(0)

# Configure logging (console only, no file)
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # Clean format, no timestamp
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Handle table operations function
def handle_table_operations(df, table_name, logger):
    """Handle table creation, truncation, deletion, and append operations"""
    try:
        sql_conn, sql_engine = Connections.get_sql_connection()
        logger.info("SQL Server connection established")
    except Exception as e:
        logger.error(f"Failed to connect to SQL Server: {e}")
        raise

    # Check if table exists
    inspector = inspect(sql_engine)
    
    if not inspector.has_table(table_name):
        # Table doesn't exist - create it
        print(f"\nTable '{table_name}' does not exist. Creating new table...")
        try:
            df.to_sql(table_name, con=sql_engine, if_exists='replace', index=False)
            logger.info(f"Table {table_name} created and {len(df)} records loaded successfully")
            print(f"✓ Table '{table_name}' created successfully with {len(df)} records")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            print(f"✗ Error creating table: {e}")
            raise
    else:
        # Table exists - ask user what to do
        print(f"\nTable '{table_name}' already exists. Choose your action:")
        print("1. Append - Add new data to existing table")
        print("2. Truncate & Insert - Clear table and insert new data (keeps table structure)")
        print("3. Drop & Create - Delete entire table and create new one with fresh data")
        print("4. Cancel - Exit without making changes")
        
        while True:
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                # Append data
                try:
                    df.to_sql(table_name, con=sql_engine, if_exists='append', index=False)
                    logger.info(f"{len(df)} records appended to table {table_name}")
                    print(f"✓ {len(df)} records appended to table '{table_name}'")
                    break
                except Exception as e:
                    logger.error(f"Error appending data to {table_name}: {e}")
                    print(f"✗ Error appending data: {e}")
                    raise
                    
            elif choice == "2":
                # Truncate and insert
                try:
                    safe_table_name = f"[{table_name}]" if " " in table_name or not table_name.isidentifier() else table_name
                    sql_conn.execute(text(f"TRUNCATE TABLE {safe_table_name}"))
                    sql_conn.commit()
                    logger.info(f"Table {table_name} truncated successfully")
                    
                    df.to_sql(table_name, con=sql_engine, if_exists='append', index=False)
                    logger.info(f"{len(df)} records loaded into table {table_name} (truncate & insert)")
                    print(f"✓ Table '{table_name}' truncated and {len(df)} new records inserted")
                    break
                except Exception as e:
                    logger.error(f"Error truncating/inserting table {table_name}: {e}")
                    print(f"✗ Error with truncate & insert: {e}")
                    raise
                    
            elif choice == "3":
                # Drop and create
                try:
                    df.to_sql(table_name, con=sql_engine, if_exists='replace', index=False)
                    logger.info(f"Table {table_name} dropped and recreated with {len(df)} records")
                    print(f"✓ Table '{table_name}' dropped and recreated with {len(df)} records")
                    break
                except Exception as e:
                    logger.error(f"Error dropping/creating table {table_name}: {e}")
                    print(f"✗ Error with drop & create: {e}")
                    raise
                    
            elif choice == "4":
                print("Operation cancelled by user.")
                logger.info("Table operation cancelled by user")
                sql_conn.close()
                sql_engine.dispose()
                sys.exit(0)
                
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
    
    # Close the connection
    try:
        sql_conn.close()
        sql_engine.dispose()
        logger.info("SQL connection closed")
    except Exception as e:
        logger.error(f"Error closing SQL connection: {e}")

# load data into sql using salesforce query or excel/csv file using dataframe

load_mechanism = input("Enter the load mechanism (salesforce/file): ").lower()
print("Please select the data source outside of VS Code, as it does not support GUI dialogs.")

if load_mechanism not in ['salesforce', 'file']:
    logger.error("Invalid load mechanism. Please enter 'salesforce' or 'file'.")
    raise ValueError("Invalid load mechanism")

if load_mechanism == 'file':
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    file_path = filedialog.askopenfilename(
        title="Select data file",
        filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("Excel files", "*.xls"), ("All files", "*.*")]
    )
    root.destroy()  # Clean up the root window
    
    if not file_path:
        logger.error("No file path provided.")
        raise ValueError("File path cannot be empty")
    
    # Load data from file
    if file_path.endswith('.xls'):
        df = pd.read_excel(file_path, engine='xlrd')  # Use xlrd for .xls files
    elif file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, engine='openpyxl')
    elif file_path.endswith('.csv'):
        try:
            df = pd.read_csv(file_path)
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='latin1')
    else:
        logger.error("Unsupported file format. Please select a CSV or Excel file.")
        raise ValueError("Unsupported file format")
    
    logger.info(f"Data loaded from {file_path} with {len(df)} records")
    
    # Always ask for table name when loading from file
    table_name = input("Enter table name to create/use in SQL Server: ").strip()
    if not table_name:
        logger.error("Table name cannot be empty.")
        raise ValueError("Table name cannot be empty")
    
    # Handle table operations
    handle_table_operations(df, table_name, logger)
elif load_mechanism == 'salesforce':

    # Get Salesforce connection
    try:
        salesforce = Connections.get_salesforce_connection()
        logger.info("Salesforce connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Salesforce: {e}")
        raise

    # Salesforce query
    query = input("Enter your Query: ")
    # logger.info(f"Executing query: {query}")

    def extract_table_name(query: str) -> str:
        match = re.search(r'FROM\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
        if match:
            tablename = match.group(1)
            if tablename.endswith('__c'):
                # Remove '__c', split by double underscore, take last part, replace _ with space, title case
                clean_name = tablename[:-3]
                # If there are double underscores, take everything after the last double underscore
                if '__' in clean_name:
                    label = clean_name.split('__')[-1].replace('_', ' ').title()
                else:
                    label = clean_name.replace('_', ' ').title()
                return label
            else:
                return tablename.title()
        return ''


    # Extract table name
    table_name = 'extracted ' + extract_table_name(query)

    # Fetch Salesforce data
    try:
        salesforce_data = salesforce.query_all(query)
        df = pd.DataFrame(salesforce_data['records']).drop(columns='attributes', errors='ignore')
        # Flatten nested dicts (e.g., CreatedBy) to just the 'Name' field if present
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, dict)).any():
                df[col] = df[col].apply(lambda x: x.get('Name') if isinstance(x, dict) and 'Name' in x else str(x) if isinstance(x, dict) else x)
        logger.info(f"Fetched {len(df)} records from Salesforce")
    except Exception as e:
        logger.error(f"Failed to fetch Salesforce data: {e}")
        raise
    
    # Handle table operations
    handle_table_operations(df, table_name, logger)

# Get SQL connection and engine
def handle_table_operations(df, table_name, logger):
    """Handle table creation, truncation, deletion, and append operations"""
    try:
        sql_conn, sql_engine = Connections.get_sql_connection()
        logger.info("SQL Server connection established")
    except Exception as e:
        logger.error(f"Failed to connect to SQL Server: {e}")
        raise

    # Check if table exists
    inspector = inspect(sql_engine)
    
    if not inspector.has_table(table_name):
        # Table doesn't exist - create it
        print(f"\nTable '{table_name}' does not exist. Creating new table...")
        try:
            df.to_sql(table_name, con=sql_engine, if_exists='replace', index=False)
            logger.info(f"Table {table_name} created and {len(df)} records loaded successfully")
            print(f"✓ Table '{table_name}' created successfully with {len(df)} records")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            print(f"✗ Error creating table: {e}")
            raise
    else:
        # Table exists - ask user what to do
        print(f"\nTable '{table_name}' already exists. Choose your action:")
        print("1. Append - Add new data to existing table")
        print("2. Truncate & Insert - Clear table and insert new data (keeps table structure)")
        print("3. Drop & Create - Delete entire table and create new one with fresh data")
        print("4. Cancel - Exit without making changes")
        
        while True:
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                # Append data
                try:
                    df.to_sql(table_name, con=sql_engine, if_exists='append', index=False)
                    logger.info(f"{len(df)} records appended to table {table_name}")
                    print(f"✓ {len(df)} records appended to table '{table_name}'")
                    break
                except Exception as e:
                    logger.error(f"Error appending data to {table_name}: {e}")
                    print(f"✗ Error appending data: {e}")
                    raise
                    
            elif choice == "2":
                # Truncate and insert
                try:
                    safe_table_name = f"[{table_name}]" if " " in table_name or not table_name.isidentifier() else table_name
                    sql_conn.execute(text(f"TRUNCATE TABLE {safe_table_name}"))
                    sql_conn.commit()
                    logger.info(f"Table {table_name} truncated successfully")
                    
                    df.to_sql(table_name, con=sql_engine, if_exists='append', index=False)
                    logger.info(f"{len(df)} records loaded into table {table_name} (truncate & insert)")
                    print(f"✓ Table '{table_name}' truncated and {len(df)} new records inserted")
                    break
                except Exception as e:
                    logger.error(f"Error truncating/inserting table {table_name}: {e}")
                    print(f"✗ Error with truncate & insert: {e}")
                    raise
                    
            elif choice == "3":
                # Drop and create
                try:
                    df.to_sql(table_name, con=sql_engine, if_exists='replace', index=False)
                    logger.info(f"Table {table_name} dropped and recreated with {len(df)} records")
                    print(f"✓ Table '{table_name}' dropped and recreated with {len(df)} records")
                    break
                except Exception as e:
                    logger.error(f"Error dropping/creating table {table_name}: {e}")
                    print(f"✗ Error with drop & create: {e}")
                    raise
                    
            elif choice == "4":
                print("Operation cancelled by user.")
                logger.info("Table operation cancelled by user")
                sql_conn.close()
                sql_engine.dispose()
                sys.exit(0)
                
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
    
    # Close the connection
    try:
        sql_conn.close()
        sql_engine.dispose()
        logger.info("SQL connection closed")
    except Exception as e:
        logger.error(f"Error closing SQL connection: {e}")

# Get SQL connection and engine
try:
    sql_conn, sql_engine = Connections.get_sql_connection()
    logger.info("SQL Server connection established")
except Exception as e:
    logger.error(f"Failed to connect to SQL Server: {e}")
    raise

# Check if table exists, create if it doesn't
inspector = inspect(sql_engine)
if not inspector.has_table(table_name):
    logger.info(f"Table {table_name} does not exist.")
    create_table = input(f"Table '{table_name}' does not exist. Do you want to create it? (yes/no): ").strip().lower()
    if create_table == "yes":
        try:
            df.to_sql(table_name, con=sql_engine, if_exists='replace', index=False)
            logger.info(f"Table {table_name} created and {len(df)} records loaded successfully")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise
    else:
        logger.info("Table creation cancelled by user.")
        sys.exit(0)
else:
    # Ask user for load mode
    print("Table already exists. Choose load mode:")
    print("1. Truncate and Insert (replace all data)")
    print("2. Delete and Insert (delete all rows, keep structure)")
    print("3. Append (add new data)")
    mode = input("Enter 1, 2, or 3: ").strip()
    safe_table_name = f"[{table_name}]" if " " in table_name or not table_name.isidentifier() else table_name

    if mode == "1":
        try:
            sql_conn.execute(text(f"TRUNCATE TABLE {safe_table_name}"))
            sql_conn.commit()
            logger.info(f"Table {table_name} truncated successfully")
            df.to_sql(table_name, con=sql_engine, if_exists='append', index=False)
            logger.info(f"{len(df)} records loaded into table {table_name} (truncate & insert)")
        except Exception as e:
            logger.error(f"Error truncating/inserting table {table_name}: {e}")
            raise
    elif mode == "2":
        try:
            sql_conn.execute(text(f"DELETE FROM {safe_table_name}"))
            sql_conn.commit()
            logger.info(f"All rows deleted from {table_name}")
            df.to_sql(table_name, con=sql_engine, if_exists='append', index=False)
            logger.info(f"{len(df)} records loaded into table {table_name} (delete & insert)")
        except Exception as e:
            logger.error(f"Error deleting/inserting table {table_name}: {e}")
            raise
    elif mode == "3":
        try:
            df.to_sql(table_name, con=sql_engine, if_exists='append', index=False)
            logger.info(f"{len(df)} records appended to table {table_name}")
        except Exception as e:
            logger.error(f"Error appending data to {table_name}: {e}")
            raise
    else:
        logger.error("Invalid mode selected. Exiting.")
        sys.exit(1)

# Close the connection
try:
    sql_conn.close()
    sql_engine.dispose()
    logger.info("SQL connection closed")
except Exception as e:
    logger.error(f"Error closing SQL connection failed: {e}")


