"""
Data Source Handler
===================
Handles retrieval from files and Salesforce SOQL queries
"""

import pandas as pd
import streamlit as st
from typing import Tuple, Optional
import io


class DataSourceHandler:
    """Handles different data sources"""
    
    @staticmethod
    def load_from_file(uploaded_file) -> Tuple[Optional[pd.DataFrame], str]:
        """
        Load data from uploaded file (CSV, PSV, or Excel)
        
        Args:
            uploaded_file: Streamlit UploadedFile object
        
        Returns:
            Tuple of (DataFrame, message)
        
        Supported Formats:
            - CSV (.csv)
            - PSV (.psv) - Pipe-separated values
            - Excel (.xlsx, .xls)
        """
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, dtype=str)
                message = f"✅ Loaded CSV: {len(df)} rows, {len(df.columns)} columns"
                return df, message
            
            elif uploaded_file.name.endswith('.psv'):
                df = pd.read_csv(uploaded_file, sep='|', dtype=str)
                message = f"✅ Loaded PSV: {len(df)} rows, {len(df.columns)} columns"
                return df, message
            
            elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                sheet_name = st.selectbox(
                    "Select Sheet (if Excel file):",
                    pd.ExcelFile(uploaded_file).sheet_names,
                    key=f"sheet_select_{uploaded_file.name}"
                )
                df = pd.read_excel(uploaded_file, sheet_name=sheet_name, dtype=str)
                message = f"✅ Loaded Excel Sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns"
                return df, message
            
            else:
                message = "❌ Unsupported file format. Please use CSV, PSV, or Excel (.csv, .psv, .xlsx, .xls)."
                return None, message
        
        except Exception as e:
            message = f"❌ Error loading file: {str(e)}"
            return None, message
    
    @staticmethod
    def load_from_soql(
        sf_conn,
        soql_query: str,
        object_name: str
    ) -> Tuple[Optional[pd.DataFrame], str]:
        """
        Execute SOQL query and return results as DataFrame
        
        Args:
            sf_conn: Salesforce connection object
            soql_query: SOQL query string
            object_name: Name of object being queried
        
        Returns:
            Tuple of (DataFrame, message)
        """
        try:
            if not soql_query or not soql_query.strip():
                return None, "❌ Please enter a SOQL query"
            
            # Show spinner while executing
            with st.spinner(f"🔄 Executing SOQL query on {object_name}..."):
                # Execute the query
                results = sf_conn.query_all(soql_query)
                
                if not results or 'records' not in results:
                    return None, "❌ Query returned no results"
                
                records = results['records']
                
                # Remove Salesforce metadata field
                cleaned_records = []
                for record in records:
                    cleaned_record = {k: v for k, v in record.items() if k != 'attributes'}
                    cleaned_records.append(cleaned_record)
                
                df = pd.DataFrame(cleaned_records)
                
                message = f"✅ Query executed successfully: {len(df)} rows, {len(df.columns)} columns"
                return df, message
        
        except Exception as e:
            message = f"❌ SOQL Query Error: {str(e)}"
            return None, message
    
    @staticmethod
    def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate DataFrame before adding to hub
        
        Args:
            df: DataFrame to validate
        
        Returns:
            Tuple of (is_valid, message)
        """
        if df is None:
            return False, "DataFrame is None"
        
        if df.empty:
            return False, "DataFrame is empty"
        
        if len(df.columns) == 0:
            return False, "DataFrame has no columns"
        
        return True, "✅ DataFrame is valid"
