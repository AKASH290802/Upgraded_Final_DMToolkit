#!/usr/bin/env python3
"""
Advanced ETL Engine for DM Toolkit
Integrates comprehensive data transformation logic from the provided script
"""

import pandas as pd
import numpy as np
import json
import glob
import time
import os
from collections import OrderedDict
from datetime import datetime
from dateutil import parser
import streamlit as st
from typing import Dict, List, Optional, Any
import csv

# Import existing utilities
import sys
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)

class ETLEngine:
    """
    Advanced ETL Engine that provides comprehensive data transformation capabilities
    mirroring the functionality from the provided script
    """
    
    def __init__(self, sf_conn=None):
        """Initialize ETL Engine with Salesforce connection"""
        self.sf_conn = sf_conn
        self.transformation_log = []
        self.error_summary = {}
        
    def get_data_from_folder(self, file_path: str, file_extension: str = 'csv', 
                           sheet_name: str = '', delimiter_value: str = ',', 
                           is_test: bool = False) -> pd.DataFrame:
        """
        Enhanced data reading with support for multiple file formats and error handling
        Mirrors get_data_from_folder() from the provided script
        """
        try:
            file_extension = 'csv' if file_extension == "" else file_extension
            delimiter_value = ',' if delimiter_value == "" else delimiter_value
            n_rows_value = 1000 if is_test else None
            
            output_df = pd.DataFrame()
            csv_files = glob.glob(os.path.join(file_path, f"*.{file_extension}"))
            
            if not csv_files:
                st.warning(f"No {file_extension} files found in {file_path}")
                return output_df
                
            st.info(f"Found {len(csv_files)} {file_extension} file(s) to process")
            
            if file_extension == "csv":
                # CSV processing with encoding fallback
                try:
                    dfs = []
                    for f in csv_files:
                        df = pd.read_csv(f, skipinitialspace=True, delimiter=delimiter_value, 
                                       nrows=n_rows_value, encoding='utf-8', dtype=str)
                        dfs.append(df)
                    return pd.concat(dfs, ignore_index=True)
                except Exception as e:
                    st.warning(f"UTF-8 encoding failed, trying unicode_escape: {str(e)}")
                    dfs = []
                    for f in csv_files:
                        df = pd.read_csv(f, skipinitialspace=True, delimiter=delimiter_value,
                                       nrows=n_rows_value, encoding='unicode_escape', dtype=str)
                        dfs.append(df)
                    return pd.concat(dfs, ignore_index=True)
                    
            else:
                # Excel processing
                for file in csv_files:
                    sheet = 0 if sheet_name == '' else sheet_name
                    df = pd.read_excel(file, sheet_name=sheet)
                    # Clean column names and data
                    df.columns = df.columns.str.strip()
                    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
                    output_df = pd.concat([output_df, df], ignore_index=True)
                return output_df
                
        except Exception as err:
            st.error(f"Error reading files: {str(err)}")
            return pd.DataFrame()
    
    def transform_columns_json(self, source_data: pd.DataFrame, json_mapping: Dict[str, str]) -> pd.DataFrame:
        """
        Transform column names using JSON mapping
        Mirrors transform_columns_json() from the provided script
        """
        try:
            transformed_data = source_data.rename(columns=json_mapping)
            self.transformation_log.append(f"Transformed {len(json_mapping)} columns using mapping")
            return transformed_data
        except Exception as e:
            st.error(f"Column transformation failed: {str(e)}")
            return source_data
    
    def isNotBlank(self, myString):
        """Check if string is not blank - from provided script"""
        return bool(myString and myString.strip())
    
    def query_bulk_data(self, object_name: str, query: str) -> pd.DataFrame:
        """
        Query Salesforce data in bulk
        Enhanced version of the original query_bulk_data function
        """
        try:
            if not self.sf_conn:
                st.error("No Salesforce connection available")
                return pd.DataFrame()
                
            result = self.sf_conn.query_all(query)
            records = result['records']
            
            if records:
                # Convert to DataFrame, excluding 'attributes' column
                df = pd.DataFrame(records)
                if 'attributes' in df.columns:
                    df = df.drop('attributes', axis=1)
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            st.error(f"Salesforce query failed: {str(e)}")
            return pd.DataFrame()
    
    def load_unique_df(self, transformed_data: pd.DataFrame, lookup_fields: Dict[str, Any], 
                      file_path: str = "") -> pd.DataFrame:
        """
        Advanced lookup field resolution with number handling
        Enhanced version of load_unique_DF() from the provided script
        """
        unique_records = pd.DataFrame()
        
        for field_name in lookup_fields:
            field_config = lookup_fields[field_name]
            
            if not self.is_not_blank(field_name):
                continue
                
            st.info(f"🔄 Processing lookup field: {field_name}")
            
            # Get unique values for lookup
            unique_records[field_name] = pd.Series(transformed_data[field_name].unique())
            
            # Build query
            fields = field_config['Fields']
            object_name = field_config['ObjectName']
            where_condition = field_config.get('WhereCondition', '')
            
            query = f"SELECT {fields} FROM {object_name} {where_condition}"
            
            # Execute query
            lookup_df = self.query_bulk_data(object_name, query)
            field_config['DataFrameName'] = lookup_df
            
            # Handle number formatting if specified
            handle_numbers = field_config.get('HandleNumbers', '')
            transformed_data[field_name] = transformed_data[field_name].astype(str)
            
            if handle_numbers == 'Y':
                # Remove decimals and handle leading zeros
                transformed_data[field_name] = transformed_data[field_name].str.split('.', n=1).str[0]
                transformed_data[field_name] = transformed_data[field_name].apply(
                    lambda x: x.lstrip('0') if len(x) > 7 else x
                )
            
            # Merge with lookup data
            join_field = field_config['JoinField']
            target_field = field_config['TargetField']
            
            transformed_data = pd.merge(
                transformed_data, 
                lookup_df, 
                how="left", 
                left_on=[field_name], 
                right_on=[join_field]
            )
            
            # Rename ID column to target field
            if 'Id' in transformed_data.columns:
                transformed_data.rename(columns={'Id': target_field}, inplace=True)
            
            # Generate summary table if file path provided
            if self.is_not_blank(file_path):
                table = transformed_data.groupby([field_name])[field_name].count().reset_index(name='count').sort_values('count', ascending=False)
                self.write_to_csv(table, file_path, f"{field_name}_lookup_summary")
        
        return transformed_data
    
    def prepare_date_fields(self, transformed_data: pd.DataFrame, fields: str, 
                          date_format: str = '%Y.%m.%d') -> pd.DataFrame:
        """
        Enhanced date field preparation with flexible format support
        Mirrors prepare_Date_fields() from the provided script
        """
        if not fields:
            return transformed_data
            
        date_fields = [f.strip() for f in fields.split(',') if f.strip()]
        
        for field in date_fields:
            if self.is_not_blank(field) and field in transformed_data.columns:
                try:
                    transformed_data[field] = transformed_data[field].astype(str)
                    transformed_data[field] = pd.to_datetime(
                        transformed_data[field], 
                        format=date_format, 
                        errors='coerce'
                    )
                    self.transformation_log.append(f"Processed date field: {field}")
                except Exception as e:
                    st.warning(f"Date processing failed for {field}: {str(e)}")
        
        # Replace NaN with None for Salesforce compatibility
        transformed_data = transformed_data.replace({np.nan: None})
        return transformed_data
    
    def prepare_mandatory_fields(self, transformed_data: pd.DataFrame, fields: str) -> pd.DataFrame:
        """Process mandatory fields exactly as in provided script"""
        field_list = fields.split(',')
        for field in field_list:
            if self.isNotBlank(field.strip()):
                field = field.strip()
                if field in transformed_data.columns:
                    transformed_data[field] = transformed_data[field].fillna(f'Missing {field}')
                    transformed_data.loc[transformed_data[field].astype(str).str.contains("Missing", na=False), f"Error{field}"] = f'Missing Mandatory Field {field}'
        return transformed_data
    
    def prepare_mandatory_fields(self, transformed_data: pd.DataFrame, fields: str) -> pd.DataFrame:
        """
        Validate mandatory fields and track missing values
        Mirrors prepare_Mandatory_fields() from the provided script
        """
        if not fields:
            return transformed_data
            
        mandatory_fields = [f.strip() for f in fields.split(',') if f.strip()]
        
        for field in mandatory_fields:
            if self.is_not_blank(field) and field in transformed_data.columns:
                # Fill missing values with error indicator
                transformed_data[field] = transformed_data[field].fillna(f'Missing {field}')
                
                # Create error column
                error_column = f"Error{field}"
                transformed_data.loc[
                    transformed_data[field].astype(str).str.contains("Missing", na=False), 
                    error_column
                ] = f'Missing Mandatory Field {field}'
                
                self.transformation_log.append(f"Validated mandatory field: {field}")
        
        return transformed_data
    
    def update_duplicates(self, transformed_data: pd.DataFrame, fields: str) -> pd.DataFrame:
        """
        Detect and flag duplicate records
        Mirrors update_duplicates() from the provided script
        """
        if not fields:
            return transformed_data
            
        key_fields = [f.strip() for f in fields.split(',') if f.strip()]
        boolean_dictionary = {True: 'Duplicate Record', False: ''}
        
        # Create composite key
        transformed_data["key"] = ''
        for field in key_fields:
            if self.is_not_blank(field) and field in transformed_data.columns:
                transformed_data["key"] += transformed_data[field].astype(str)
        
        # Mark duplicates
        transformed_data['Error Duplicate'] = transformed_data.duplicated(subset=['key'])
        transformed_data['Error Duplicate'] = transformed_data['Error Duplicate'].map(boolean_dictionary)
        
        self.transformation_log.append(f"Checked duplicates on fields: {', '.join(key_fields)}")
        return transformed_data
    
    def apply_conditions(self, transformed_data: pd.DataFrame, condition_fields: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply conditional business rules
        Mirrors apply_condition() from the provided script
        """
        for field_name in condition_fields:
            if not self.is_not_blank(field_name):
                continue
                
            config = condition_fields[field_name]
            condition_value = config['ConditionValue']
            condition_column = config['ConditionColumn']
            target_value_true = config['TargetValueTrue']
            target_value_false = config['TargetValueFalse']
            condition = config['Condition']
            
            if condition_column not in transformed_data.columns:
                continue
                
            transformed_data[condition_column] = transformed_data[condition_column].astype(str)
            
            if condition == 'isna':
                transformed_data[field_name] = np.where(
                    pd.isna(transformed_data[condition_column]), 
                    target_value_true, 
                    target_value_false
                )
            elif condition == 'neq':
                transformed_data[field_name] = np.where(
                    transformed_data[condition_column] != condition_value, 
                    target_value_true, 
                    target_value_false
                )
            else:  # equals condition
                transformed_data[field_name] = np.where(
                    transformed_data[condition_column] == condition_value, 
                    target_value_true, 
                    target_value_false
                )
            
            self.transformation_log.append(f"Applied condition on field: {field_name}")
        
        return transformed_data
    
    def replace_values(self, transformed_data: pd.DataFrame, replace_fields: Dict[str, Dict]) -> pd.DataFrame:
        """
        Replace values based on mapping configuration
        Mirrors replace_values() from the provided script
        """
        for field_name in replace_fields:
            if not self.is_not_blank(field_name) or field_name not in transformed_data.columns:
                continue
                
            try:
                replace_mapping = replace_fields[field_name]
                transformed_data[field_name] = transformed_data[field_name].replace(replace_mapping)
                self.transformation_log.append(f"Replaced values in field: {field_name}")
            except Exception as e:
                st.warning(f"Value replacement failed for {field_name}: {str(e)}")
        
        return transformed_data
    
    def populate_record_type_id(self, object_type: str, transformed_data: pd.DataFrame) -> pd.DataFrame:
        """
        Resolve record type names to IDs
        Mirrors populate_record_Type_id() from the provided script
        """
        if not object_type or not self.sf_conn:
            return transformed_data
            
        try:
            query = f"SELECT Id, Name FROM RecordType WHERE sObjectType='{object_type}'"
            record_types = self.query_bulk_data('RecordType', query)
            
            if not record_types.empty:
                record_types.rename(columns={'Id': 'RecordTypeId', 'Name': 'RecordTypeName'}, inplace=True)
                
                # Merge with data if RECORDTYPE column exists
                if 'RECORDTYPE' in transformed_data.columns:
                    transformed_data = pd.merge(
                        transformed_data, 
                        record_types, 
                        how="left", 
                        left_on='RECORDTYPE', 
                        right_on='RecordTypeName'
                    )
                    self.transformation_log.append(f"Resolved record types for: {object_type}")
        
        except Exception as e:
            st.warning(f"Record type resolution failed: {str(e)}")
        
        return transformed_data
    
    def populate_errors(self, transformed_data: pd.DataFrame) -> pd.DataFrame:
        """
        Consolidate all error columns into final error summary
        Mirrors populate_Errors() from the provided script
        """
        error_columns = [col for col in transformed_data.columns if col.startswith('Error')]
        
        if error_columns:
            transformed_data['FinalErrors'] = transformed_data[error_columns].apply(
                lambda x: ' '.join(i for i in x if pd.notna(i)), axis=1
            )
            self.transformation_log.append("Consolidated error information")
        
        return transformed_data
    
    def write_to_csv(self, data: pd.DataFrame, file_path: str, file_name: str) -> None:
        """
        Write DataFrame to CSV file
        Mirrors write_to_CSV() from the provided script
        """
        try:
            output_dir = os.path.join(file_path, "Output")
            os.makedirs(output_dir, exist_ok=True)
            
            full_path = os.path.join(output_dir, f"{file_name}.csv")
            data.to_csv(full_path, index=False, encoding='utf-8')
            
            st.success(f"✅ Saved: {file_name}.csv ({len(data)} records)")
        except Exception as e:
            st.error(f"Failed to save {file_name}.csv: {str(e)}")
    
    def is_not_blank(self, value: str) -> bool:
        """
        Check if string is not blank
        Mirrors isNotBlank() from the provided script
        """
        return bool(value and str(value).strip())
    
    def process_etl_pipeline(self, template_config: Dict[str, Any], is_test: bool = False) -> tuple:
        """
        Execute complete ETL pipeline based on configuration
        Main processing function that mirrors get_raw_data() logic
        """
        start_time = time.time()
        
        try:
            # Extract configuration
            field_rules = template_config.get('FieldRules', [{}])[0]
            file_path = field_rules.get('FolderURL', '')
            file_extension = field_rules.get('Extension', 'csv')
            delimiter = field_rules.get('Delimiter', ',')
            sheet_name = field_rules.get('SheetName', 'Sheet1')
            
            # Transformation rules
            column_mapping = template_config.get('FieldMapping', [{}])[0]
            lookup_fields = field_rules.get('LookUpFields', {})
            condition_fields = field_rules.get('ConditionFields', {})
            date_fields = field_rules.get('DateFields', '')
            mandatory_fields = field_rules.get('MandatoryFields', '')
            drop_fields = field_rules.get('DropFields', '')
            unique_fields = field_rules.get('UniqueFields', '')
            copy_fields = template_config.get('CopyFields', [{}])[0]
            replace_null_fields = field_rules.get('ReplaceValueIfNull', {})
            replace_value_fields = field_rules.get('ReplaceValues', {})
            record_type_object = field_rules.get('RecordTypeObject', '')
            error_columns = field_rules.get('ErrorColumns', 'FinalErrors')
            
            # Step 1: Read raw data
            st.info("📁 Reading source data...")
            raw_data = self.get_data_from_folder(file_path, file_extension, sheet_name, delimiter, is_test)
            
            if raw_data.empty:
                st.error("No data found to process")
                return None, None
            
            st.success(f"✅ Read {len(raw_data)} records from {len(raw_data.columns)} columns")
            
            # Step 2: Transform columns
            st.info("🔄 Transforming columns...")
            transformed_data = self.transform_columns_json(raw_data, column_mapping)
            
            # Step 3: Drop unwanted fields
            if drop_fields:
                drop_field_list = [f.strip() for f in drop_fields.split(',') if f.strip()]
                for field in drop_field_list:
                    if field in transformed_data.columns:
                        transformed_data.drop(field, axis=1, inplace=True)
            
            # Step 4: Process date fields
            st.info("📅 Processing date fields...")
            transformed_data = self.prepare_date_fields(transformed_data, date_fields)
            
            # Step 5: Handle null value replacements
            if replace_null_fields:
                for field_name, replacement_field in replace_null_fields.items():
                    if field_name in transformed_data.columns and replacement_field in transformed_data.columns:
                        transformed_data[field_name] = transformed_data[field_name].combine_first(transformed_data[replacement_field])
            
            # Step 6: Resolve lookup fields
            if lookup_fields:
                st.info("🔍 Resolving lookup relationships...")
                transformed_data = self.load_unique_df(transformed_data, lookup_fields, file_path)
            
            # Step 7: Validate mandatory fields
            st.info("✅ Validating mandatory fields...")
            transformed_data = self.prepare_mandatory_fields(transformed_data, mandatory_fields)
            
            # Step 8: Apply conditions
            if condition_fields:
                st.info("⚙️ Applying business rules...")
                transformed_data = self.apply_conditions(transformed_data, condition_fields)
            
            # Step 9: Copy fields
            if copy_fields:
                for source_field, target_field in copy_fields.items():
                    if source_field in transformed_data.columns:
                        transformed_data[target_field] = transformed_data[source_field]
            
            # Step 10: Replace values
            if replace_value_fields:
                transformed_data = self.replace_values(transformed_data, replace_value_fields)
            
            # Step 11: Check duplicates
            st.info("🔍 Checking for duplicates...")
            transformed_data = self.update_duplicates(transformed_data, unique_fields)
            
            # Step 12: Resolve record types
            if record_type_object:
                st.info("📋 Resolving record types...")
                transformed_data = self.populate_record_type_id(record_type_object, transformed_data)
            
            # Step 13: Consolidate errors
            transformed_data = self.populate_errors(transformed_data)
            
            # Step 14: Generate outputs
            st.info("📊 Generating output files...")
            
            # Error summary
            error_summary = transformed_data.groupby(['FinalErrors'])['FinalErrors'].count().reset_index(name='count').sort_values('count', ascending=False)
            
            # Separate good and bad records
            good_records = transformed_data[transformed_data['FinalErrors'].str.len() < 4]
            error_records = transformed_data[transformed_data['FinalErrors'].str.len() >= 4]
            
            # Save outputs if file path provided
            if file_path:
                self.write_to_csv(transformed_data, file_path, 'RawOutput')
                self.write_to_csv(good_records, file_path, 'GoodOutput')
                self.write_to_csv(error_records, file_path, 'ErrorFilesSummary')
                self.write_to_csv(error_summary, file_path, 'ErrorSummary')
            
            processing_time = time.time() - start_time
            st.success(f"🚀 ETL Pipeline completed in {processing_time:.2f} seconds")
            st.info(f"📈 Processed: {len(transformed_data)} total, {len(good_records)} clean, {len(error_records)} with errors")
            
            return good_records, error_records
            
        except Exception as e:
            st.error(f"ETL Pipeline failed: {str(e)}")
            return None, None