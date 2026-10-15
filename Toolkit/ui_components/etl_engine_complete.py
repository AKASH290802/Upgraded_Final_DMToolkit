#!/usr/bin/env python3
"""
Complete ETL Engine for DM Toolkit
Implements all functionality from the provided ETL script
"""

import pandas as pd
import numpy as np
import json
import glob
import time
import os
import csv
from collections import OrderedDict
from datetime import datetime
from dateutil import parser
import streamlit as st
from typing import Dict, List, Optional, Any

# Import existing utilities
import sys
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)

# Import query_bulk_data function to match provided script
try:
    from .utils import query_bulk_data
except ImportError:
    from utils import query_bulk_data

class ETLEngine:
    """
    Complete ETL Engine implementing all functionality from the provided script
    """
    
    def __init__(self, sf_conn=None):
        """Initialize ETL Engine with Salesforce connection"""
        self.sf_conn = sf_conn
        self.transformation_log = []
        self.error_summary = {}
    
    def isNotBlank(self, myString):
        """Check if string is not blank - from provided script"""
        return bool(myString and myString.strip())
    
    def safe_str_column(self, df: pd.DataFrame, column_name: str) -> pd.DataFrame:
        """Safely convert a column to string type and handle all edge cases"""
        if column_name in df.columns:
            # Convert to string, handle NaN, None, and other edge cases
            df[column_name] = df[column_name].astype(str).fillna('').replace(['nan', 'None', 'NaT'], '')
        else:
            # Create the column if it doesn't exist
            df[column_name] = ''
        return df
    
    def get_data_from_folder(self, file_path: str, file_extension: str = 'csv', 
                           sheet_name: str = '', delimiter_value: str = ',', 
                           is_test: bool = False) -> pd.DataFrame:
        """
        Get data from folder - exact implementation from provided script
        """
        try:
            file_extension = 'csv' if file_extension == "" else file_extension
            delimiter_value = ',' if delimiter_value == "" else delimiter_value
            n_rows_value = 1000 if is_test else None
            
            print(f"Processing: {file_extension}, {file_path}")
            output_xlsx = pd.DataFrame()
            csv_files = glob.glob(os.path.join(file_path, f"*.{file_extension}"))
            print(f"Files found: {csv_files}")
            
            if file_extension == "csv":
                try:
                    return pd.concat([
                        pd.read_csv(f, skipinitialspace=True, delimiter=delimiter_value, 
                                   nrows=n_rows_value, encoding='utf-8', dtype=str) 
                        for f in csv_files
                    ], ignore_index=True)
                except Exception as err:
                    print('Error reading CSV with UTF-8, trying unicode_escape:', repr(err))
                    return pd.concat([
                        pd.read_csv(f, skipinitialspace=True, delimiter=delimiter_value,
                                   nrows=n_rows_value, encoding='unicode_escape', dtype=str)
                        for f in csv_files
                    ], ignore_index=True)
            else:
                # Excel processing
                for file in csv_files:
                    all_dfs = pd.read_excel(file, sheet_name=0)
                    all_dfs.columns = all_dfs.columns.str.strip()
                    all_dfs = all_dfs.applymap(lambda x: x.strip() if isinstance(x, str) else x)
                    print(f"Shape: {all_dfs.shape[0]}, Columns: {all_dfs.columns}")
                    output_xlsx = pd.concat([output_xlsx, all_dfs], ignore_index=True)
                return output_xlsx
                
        except Exception as err:
            print('Error reading files:', repr(err))
            st.error(f"Error reading files: {str(err)}")
            return pd.DataFrame()
    
    def transform_columns_json(self, source_data: pd.DataFrame, json_mapping: Dict[str, str]) -> pd.DataFrame:
        """Transform column names using JSON mapping - from provided script"""
        try:
            transformed_data = source_data.rename(columns=json_mapping)
            return transformed_data
        except Exception as e:
            print(f'Error in transform_columns_json: {repr(e)}')
            st.error(f"Column transformation failed: {str(e)}")
            return source_data
    
    def prepare_date_fields(self, transformed_data: pd.DataFrame, fields: str) -> pd.DataFrame:
        """Process date fields - exact implementation from provided script"""
        date_fields = fields.split(',')
        for field in date_fields:
            field = field.strip()
            if self.isNotBlank(field) and field in transformed_data.columns:
                transformed_data[field] = transformed_data[field].astype(str)
                transformed_data[field] = pd.to_datetime(
                    transformed_data[field], format='%Y.%m.%d', errors='coerce'
                )
        transformed_data = transformed_data.replace({np.nan: None})
        return transformed_data
    
    def prepare_mandatory_fields(self, transformed_data: pd.DataFrame, fields: str) -> pd.DataFrame:
        """Process mandatory fields - exact implementation from provided script"""
        field_list = fields.split(',')
        for field in field_list:
            field = field.strip()
            if self.isNotBlank(field) and field in transformed_data.columns:
                transformed_data[field] = transformed_data[field].fillna(f'Missing {field}')
                transformed_data.loc[
                    transformed_data[field].astype(str).str.contains("Missing", na=False), 
                    f"Error{field}"
                ] = f'Missing Mandatory Field {field}'
        return transformed_data
    
    def drop_fields(self, transformed_data: pd.DataFrame, fields: str) -> pd.DataFrame:
        """Drop fields - exact implementation from provided script"""
        field_list = fields.split(',')
        for field in field_list:
            field = field.strip()
            if field != '' and field in transformed_data.columns:
                del transformed_data[field]
        return transformed_data
    
    def using_np_where(self, transformed_data: pd.DataFrame, from_field: str, to_field: str):
        """Helper function for replace_value_if_null - from provided script"""
        transformed_data[from_field] = transformed_data[from_field].combine_first(transformed_data[to_field])
    
    def replace_value_if_null(self, transformed_data: pd.DataFrame, replace_value_if_null: Dict) -> pd.DataFrame:
        """Replace null values - exact implementation from provided script"""
        for each_field in replace_value_if_null:
            if each_field in transformed_data.columns and replace_value_if_null[each_field] in transformed_data.columns:
                self.using_np_where(transformed_data, each_field, replace_value_if_null[each_field])
        return transformed_data
    
    def replace_values(self, transformed_data: pd.DataFrame, fields: Dict) -> pd.DataFrame:
        """Replace values - exact implementation from provided script"""
        for each_field in fields:
            if each_field != '' and each_field in transformed_data.columns:
                try:
                    replace_fields = fields[each_field]
                    transformed_data[each_field] = transformed_data[each_field].replace(replace_fields)
                except Exception as err:
                    print('Error Replace Values:', repr(err), transformed_data.columns, each_field)
                    st.warning(f'Error Replace Values: {str(err)} - Field: {each_field}')
        return transformed_data
    
    def apply_condition(self, transformed_data: pd.DataFrame, condition_fields: Dict) -> pd.DataFrame:
        """Apply conditions - exact implementation from provided script"""
        for each_field in condition_fields:
            if each_field != '':
                condition_config = condition_fields[each_field]
                condition_value = condition_config['ConditionValue']
                condition_column = condition_config['ConditionColumn']
                target_value_true = condition_config['TargetValueTrue']
                target_value_false = condition_config['TargetValueFalse']
                condition = condition_config['Condition']
                
                if condition_column in transformed_data.columns:
                    transformed_data[condition_column] = transformed_data[condition_column].astype(str)
                    print(f"Condition: {condition_value}, {condition_column}, {target_value_true}, {target_value_false}, {condition}, {each_field}")
                    
                    if condition == 'isna':
                        transformed_data[each_field] = np.where(
                            pd.isna(transformed_data[condition_column]), 
                            target_value_true, target_value_false
                        )
                    elif condition == 'neq':
                        transformed_data[each_field] = np.where(
                            transformed_data[condition_column] != condition_value, 
                            target_value_true, target_value_false
                        )
                    else:
                        transformed_data[each_field] = np.where(
                            transformed_data[condition_column] == condition_value, 
                            target_value_true, target_value_false
                        )
        return transformed_data
    
    def update_duplicates(self, transformed_data: pd.DataFrame, fields: str) -> pd.DataFrame:
        """Update duplicates - exact implementation from provided script"""
        key_fields = fields.split(',')
        boolean_dictionary = {True: 'Duplicate Record', False: ''}
        transformed_data["key"] = ''
        
        for field in key_fields:
            field = field.strip()
            if self.isNotBlank(field) and field in transformed_data.columns:
                transformed_data["key"] = transformed_data[field].astype(str) + transformed_data["key"]
        
        transformed_data['Error Duplicate'] = transformed_data.duplicated(subset=['key'])
        transformed_data['Error Duplicate'] = transformed_data['Error Duplicate'].map(boolean_dictionary)
        return transformed_data
    
    def populate_errors(self, transformed_data: pd.DataFrame, error_column: str = 'FinalErrors') -> pd.DataFrame:
        """Populate errors - exact implementation from provided script"""
        error_columns = [col for col in transformed_data if col.startswith('Error')]
        
        # If no error columns exist, create an empty error column
        if not error_columns:
            transformed_data[error_column] = ''
        else:
            transformed_data[error_column] = transformed_data[error_columns].apply(
                lambda x: ' '.join(str(i) for i in x if pd.notna(i) and str(i).strip() != '' and str(i) != 'nan'), axis=1
            )
        
        # Use safe string conversion
        transformed_data = self.safe_str_column(transformed_data, error_column)
        return transformed_data
    
    def prepare_copy_fields(self, transformed_data: pd.DataFrame, fields: Dict) -> pd.DataFrame:
        """Prepare copy fields - exact implementation from provided script"""
        for field in fields:
            if field in transformed_data.columns and fields[field]:
                print(f"Copying: {fields[field]} -> {field}")
                transformed_data[fields[field]] = transformed_data[field]
        return transformed_data
    
    def query_bulk_data_method(self, object_name: str, query: str) -> pd.DataFrame:
        """Query Salesforce data - wrapper for utils.query_bulk_data to match provided script"""
        return query_bulk_data(object_name, query, self.sf_conn)
    
    def perform_salesforce_lookups(self, transformed_data: pd.DataFrame, lookup_fields: Dict, file_path_file: str = "") -> pd.DataFrame:
        """
        Perform Salesforce lookups - exact implementation from provided script
        This is the load_unique_DF function from the original script
        """
        if not self.sf_conn:
            st.warning("No Salesforce connection - skipping lookups")
            return transformed_data
        
        unique_records = pd.DataFrame()
        print("Transformed data:", transformed_data)
        
        for each_field in lookup_fields:
            print(f"Processing lookup field: {each_field}, Config: {lookup_fields[each_field]['Fields']}")
            if self.isNotBlank(each_field) and each_field in transformed_data.columns:
                try:
                    unique_records[each_field] = pd.Series(transformed_data[each_field].unique())
                    
                    lookup_config = lookup_fields[each_field]
                    query = f"SELECT {lookup_config['Fields']} FROM {lookup_config['ObjectName']} {lookup_config['WhereCondition']}"
                    
                    lookup_config['DataFrameName'] = self.query_bulk_data_method(lookup_config['ObjectName'], query)
                    print(f"Lookup DataFrame columns: {lookup_config['DataFrameName'].columns}")
                    print(f"Transformed data columns: {transformed_data.columns}")
                    
                    # Handle numbers if specified
                    handle_numbers = lookup_config.get('HandleNumbers', '')
                    print(f"HandleNumbers: {handle_numbers}")
                    
                    transformed_data[each_field] = transformed_data[each_field].astype(str)
                    print(f"Field values: {transformed_data[each_field]}")
                    
                    if handle_numbers == 'Y':
                        transformed_data[each_field] = transformed_data[each_field].str.split('.', n=1).str[0]
                        transformed_data[each_field] = transformed_data[each_field].apply(
                            lambda x: x.lstrip('0') if len(x) > 7 else x
                        )
                        print(f"After number handling: {transformed_data[each_field]}")
                    
                    # Perform merge
                    if not lookup_config['DataFrameName'].empty:
                        transformed_data = pd.merge(
                            transformed_data, 
                            lookup_config['DataFrameName'], 
                            how="left", 
                            left_on=[each_field], 
                            right_on=[lookup_config['JoinField']]
                        )
                        
                        # Rename Id column to target field
                        if 'Id' in transformed_data.columns:
                            transformed_data.rename(
                                columns={'Id': lookup_config['TargetField']}, 
                                inplace=True
                            )
                        
                        # Generate summary table
                        table = transformed_data.groupby([each_field])[each_field].count().reset_index(name='count').sort_values('count', ascending=False)
                        if self.isNotBlank(file_path_file):
                            self.write_to_csv(table, file_path_file, each_field)
                    
                except Exception as e:
                    st.warning(f"Lookup failed for field {each_field}: {str(e)}")
                    print(f"Lookup error for {each_field}: {repr(e)}")
        
        return transformed_data
    
    def populate_record_type_id(self, object_type: str, merged_data: pd.DataFrame) -> pd.DataFrame:
        """Populate record type ID - exact implementation from provided script"""
        if object_type != '' and self.sf_conn:
            try:
                query = f"SELECT Id,Name FROM RecordType WHERE sObjectType='{object_type}'"
                record_types = self.query_bulk_data_method('RecordType', query)
                
                if not record_types.empty:
                    record_types.rename(columns={'Id': 'RecordTypeId', 'Name': 'RecordTypeName'}, inplace=True)
                    merged_data = pd.merge(
                        merged_data, record_types, 
                        how="left", 
                        left_on='RECORDTYPE', 
                        right_on='RecordTypeName'
                    )
                    
            except Exception as e:
                st.warning(f"Record type lookup failed: {str(e)}")
                print(f"Record type error: {repr(e)}")
                
        return merged_data
    
    def write_to_csv(self, source_data: pd.DataFrame, file_path: str, file_name: str):
        """Write data to CSV - exact implementation from provided script"""
        try:
            output_dir = os.path.join(file_path, "Output")
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{file_name}.csv")
            source_data.to_csv(output_file, index=False, encoding='utf-8')
            print(f"Written file: {output_file}")
        except Exception as e:
            st.error(f"Failed to write CSV: {str(e)}")
            print(f"Write error: {repr(e)}")
    
    def execute_complete_pipeline(self, json_settings: Dict, is_test: bool = False) -> pd.DataFrame:
        """
        Execute the complete ETL pipeline exactly as in the provided get_raw_data function
        """
        try:
            start_time = time.time()
            
            # Extract configuration
            field_rules = json_settings['FieldRules'][0]
            file_path_file = field_rules['FolderURL']
            file_extension = field_rules.get('Extension', 'csv')
            delimiter_value = field_rules.get('Delimiter', ',')
            sheet_name_file = field_rules.get('SheetName', 'Sheet1')
            column_mapping = json_settings['FieldMapping'][0]
            lookup_fields = field_rules.get('LookUpFields', {})
            condition_fields = field_rules.get('ConditionFields', {})
            date_fields = field_rules.get('DateFields', '')
            mandatory_fields = field_rules.get('MandatoryFields', '')
            drop_fields_config = field_rules.get('DropFields', '')
            unique_fields = field_rules.get('UniqueFields', '')
            copy_fields = json_settings.get('CopyFields', [{}])[0]
            replace_null_value_fields = field_rules.get('ReplaceValueIfNull', {})
            replace_value_fields = field_rules.get('ReplaceValues', {})
            record_type_object = field_rules.get('RecordTypeObject', '')
            final_error_columns = field_rules.get('ErrorColumns', 'FinalErrors')
            error_message_replace = field_rules.get('ErrorMessageReplace', {})
            
            st.info("🚀 Starting complete ETL pipeline execution...")
            
            # Step 1: Load raw data
            st.text("📁 Loading raw data from files...")
            raw_excel_data = self.get_data_from_folder(file_path_file, file_extension, sheet_name_file, delimiter_value, is_test)
            print(f"Raw data columns: {raw_excel_data.columns}")
            print(f"Time after load: {time.time() - start_time}")
            st.success(f"✅ Loaded {len(raw_excel_data)} records")
            
            # Step 2: Transform columns
            st.text("🔄 Transforming column names...")
            transformed_data = self.transform_columns_json(raw_excel_data, column_mapping)
            print(f"Time after transform: {time.time() - start_time}")
            
            # Step 3: Drop fields
            st.text("🗑️ Dropping unnecessary fields...")
            self.drop_fields(transformed_data, drop_fields_config)
            
            # Step 4: Prepare date fields
            st.text("📅 Processing date fields...")
            self.prepare_date_fields(transformed_data, date_fields)
            
            # Step 5: Replace null values
            st.text("🔄 Replacing null values...")
            self.replace_value_if_null(transformed_data, replace_null_value_fields)
            
            # Step 6: Perform lookups
            st.text("🔍 Performing Salesforce lookups...")
            merged_data = self.perform_salesforce_lookups(transformed_data, lookup_fields, file_path_file)
            
            # Step 7: Prepare mandatory fields
            st.text("✅ Validating mandatory fields...")
            self.prepare_mandatory_fields(merged_data, mandatory_fields)
            print(f"Time after mandatory fields: {time.time() - start_time}")
            
            # Step 8: Apply conditions
            st.text("🎯 Applying business rules...")
            self.apply_condition(merged_data, condition_fields)
            
            # Step 9: Copy fields
            st.text("📋 Copying fields...")
            self.prepare_copy_fields(merged_data, copy_fields)
            
            # Step 10: Replace values
            st.text("🔄 Replacing values...")
            self.replace_values(merged_data, replace_value_fields)
            
            # Step 11: Update duplicates
            st.text("🔍 Checking for duplicates...")
            self.update_duplicates(merged_data, unique_fields)
            
            # Step 12: Populate record type
            st.text("📝 Populating record types...")
            merged_data = self.populate_record_type_id(record_type_object, merged_data)
            
            # Step 13: Populate errors
            st.text("⚠️ Consolidating errors...")
            self.populate_errors(merged_data, final_error_columns)
            
            # Safely ensure error column is properly formatted for string operations
            merged_data = self.safe_str_column(merged_data, final_error_columns)
            
            # Step 14: Generate summary
            table = merged_data.groupby([final_error_columns])[final_error_columns].count().reset_index(name='count').sort_values('count', ascending=False)
            print("Error summary:")
            print(table)
            
            # Step 15: Write outputs exactly as in provided script
            st.text("📤 Generating output files...")
            self.write_to_csv(merged_data, file_path_file, 'RawOutput')
            self.write_to_csv(table, file_path_file, 'ErrorOutput')
            
            # Error file summary - ensure error column is string before using .str methods
            only_error_file = merged_data[merged_data[final_error_columns].str.len() > 3]
            self.write_to_csv(only_error_file, file_path_file, 'ErrorFileSumary')
            
            # Business error file
            only_error_file_bu = pd.DataFrame()
            error_columns_list = final_error_columns.split(',')
            if len(only_error_file) > 0:
                only_error_file_bu = only_error_file[error_columns_list].copy()
            self.write_to_csv(only_error_file_bu, file_path_file, 'ErrorFileSummaryBusiness')
            
            # Good output
            good_output = merged_data[merged_data[final_error_columns].str.len() < 4]
            self.write_to_csv(good_output, file_path_file, 'GoodOutput')
            
            print(f"Total processing time: {time.time() - start_time}")
            st.success(f"🎉 ETL pipeline completed in {time.time() - start_time:.2f} seconds")
            
            return good_output
            
        except Exception as e:
            st.error(f"❌ ETL pipeline failed: {str(e)}")
            print(f"Pipeline error: {repr(e)}")
            raise e