import json
from sqlalchemy import create_engine
from simple_salesforce import Salesforce
import pandas as pd
from . import Org_selection
import logging
import pyodbc
import urllib.parse

# Configure logging (console only, no file)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Only console output
)
logger = logging.getLogger(__name__)

salesforce_org = ['fcs2', 'dinesh', 'deployement','TestQA','TestDev']
sql_org = ['sql', 'sql2']

def select_salesforce_org(org_name):
    if org_name not in salesforce_org:
        raise Exception(f"Invalid Salesforce organization: {org_name}")
    return org_name

def get_credentials(file_path):
    try:
        with open(file_path, 'r') as file:
            credentials = json.load(file)
        logger.info(f"Loaded credentials from {file_path}")
        return credentials
    except FileNotFoundError:
        logger.error(f"Credentials file {file_path} not found")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in {file_path}")
        raise
    except KeyError as e:
        logger.error(f"Missing required key in credentials: {e}")
        raise

def get_sql_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json"):
    logger.info(f"Available SQL organizations: {sql_org}")
    select_sql = input("Select SQL organization: ").lower()
    try:
        credentials = get_credentials(file_path)
        if select_sql not in credentials:
            raise Exception(f"Invalid SQL organization: {select_sql}")
        
        server = credentials[select_sql]['server']
        database = credentials[select_sql]['database']
        username = credentials[select_sql].get('username', '')
        password = credentials[select_sql].get('password', '')
        
        if select_sql == 'sql2':
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"Trusted_Connection=yes;"
            )
            try:
                pyodbc_conn = pyodbc.connect(conn_str)
                pyodbc_conn.close()
                logger.info("SQL connection test successful for sql2")
            except Exception as e:
                logger.error(f"SQL connection test failed for sql2: {e}")
                raise
            sqlalchemy_conn_str = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"
        else:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
            )
            try:
                pyodbc_conn = pyodbc.connect(conn_str)
                pyodbc_conn.close()
                logger.info("SQL connection test successful for sql")
            except Exception as e:
                logger.error(f"SQL connection test failed for sql: {e}")
                raise
            sqlalchemy_conn_str = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"
        
        logger.info(f"Connecting to {server}")
        engine = create_engine(sqlalchemy_conn_str, echo=False)  # Disable verbose output
        conn = engine.connect()
        logger.info(f"Connected to {server}")
        return conn, engine
    except Exception as e:
        logger.error(f"Failed to connect to SQL Server: {e}")
        raise Exception(f"Failed to connect to SQL Server: {e}")

def get_salesforce_connection(file_path=r"C:\DM_toolkit\Services\linkedservices.json", org_name=None):
    if org_name is None:
        org_name = Org_selection.org_select()
    
    credentials = get_credentials(file_path)
    try:
        sf = Salesforce(
            username=credentials[org_name]['username'],
            password=credentials[org_name].get('password', ''),
            security_token=credentials[org_name].get('security_token', ''),
            domain=credentials[org_name].get('domain', '')
        )
        logger.info(f"Connected to Salesforce org {org_name}")
        return sf
    except Exception as e:
        logger.error(f"Failed to connect to Salesforce: {e}")
        raise

def run_sql_query(engine, query):
    try:
        df = pd.read_sql(query, engine)
        if df.empty:
            logger.warning("Query returned no data")
        logger.info(f"SQL query executed successfully: {query}")
        return df
    except Exception as e:
        logger.error(f"SQL query failed: {e}")
        raise Exception(f"SQL query failed: {e}")

def run_salesforce_query(sf, query):
    try:
        result = sf.query_all(query)
        logger.info(f"Salesforce query executed successfully.")
        return result
    except Exception as e:
        logger.error(f"Salesforce query failed: {e}")
        raise Exception(f"Salesforce query failed: {e}")