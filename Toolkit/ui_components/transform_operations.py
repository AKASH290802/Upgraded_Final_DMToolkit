"""
Transform Operations - Advanced Data Transformation and Validation
Integrates the valuable logic from transformed.py into the DM Toolkit
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import simple_salesforce as sf


def _required_on_create(field: Dict) -> bool:
    """A field Salesforce requires on insert: createable, not nillable, no default, not boolean."""
    return (field.get('createable', False) and not field.get('nillable', True)
            and not field.get('defaultedOnCreate', False) and field.get('type') != 'boolean'
            and field.get('name') != 'Id')


SKIP_MAPPING_VALUES = ('', '-- Skip Field --', '⚠️ No mapping', None)


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    if not pd.api.types.is_scalar(value):
        return False
    return bool(pd.isna(value)) or str(value).strip() == ''


def _unique_key(value, case_sensitive: bool) -> str:
    key = str(value).strip()
    return key if case_sensitive else key.lower()


def categorize_transform_results(df_original: pd.DataFrame, df_transformed: pd.DataFrame,
                                lookup_fields: Dict, selected_object: str, sf_conn,
                                field_mappings: Optional[Dict] = None) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Categorize records into transform success and failure based on:
    1. Lookup field changes
    2. Salesforce picklist value validation
    3. Salesforce unique field validation
    4. Required fields (mapped fields Salesforce requires on insert must not be empty)

    Rules:
    - Transform Failure: If any lookup field data remains the same as original raw data
                        OR picklist values don't match Salesforce picklist options
                        OR unique field values are duplicated
                        OR a mapped required field is empty
    - Transform Success: If all validations pass

    field_mappings ({source column: Salesforce field}) lets checks 2-4 find the
    Salesforce field behind each source column; columns already named like a
    Salesforce field are checked as that field.
    """
    st.info("🔍 **Analyzing Transform Results with Advanced Validation**")
    
    # Get Salesforce object metadata for validation
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text(f"Fetching Salesforce metadata for {selected_object}...")
    try:
        from ui_components.utils import get_object_description
        object_metadata = get_object_description(sf_conn, selected_object)
        sf_fields = {field['name']: field for field in object_metadata['fields']}
        st.success(f"✅ Retrieved metadata for {len(sf_fields)} fields in {selected_object}")
    except Exception as e:
        st.warning(f"⚠️ Could not fetch Salesforce metadata: {e}")
        sf_fields = {}

    progress_bar.progress(25)

    # Lookup resolution drops unresolved rows but keeps the row labels, so line the
    # original rows up with the transformed rows by label, not by position.
    if (not df_transformed.index.equals(df_original.index) and df_original.index.is_unique
            and df_transformed.index.isin(df_original.index).all()):
        df_original = df_original.loc[df_transformed.index]
    df_original_indexed = df_original.reset_index(drop=True)
    df_transformed_indexed = df_transformed.reset_index(drop=True)

    # Salesforce field behind each column: explicit mapping first, then same-name columns.
    # A column explicitly set to "skip" in the mapping is not loaded, so it is not checked.
    column_fields = {}
    for column in df_transformed_indexed.columns:
        if field_mappings and column in field_mappings:
            mapped = field_mappings[column]
            if mapped not in SKIP_MAPPING_VALUES and mapped in sf_fields:
                column_fields[column] = mapped
        elif column in sf_fields:
            column_fields[column] = column
    # Unrestricted picklists accept any value in Salesforce, so only restricted ones are checked.
    picklist_columns = {c: f for c, f in column_fields.items()
                        if sf_fields[f].get('type') in ('picklist', 'multipicklist')
                        and sf_fields[f].get('restrictedPicklist', True)}
    unique_columns = {c: f for c, f in column_fields.items() if sf_fields[f].get('unique', False)}
    required_columns = {c: f for c, f in column_fields.items() if _required_on_create(sf_fields[f])}
    unmapped_required = sorted(f for f, meta in sf_fields.items()
                               if _required_on_create(meta) and f not in column_fields.values())
    # Rows sharing a value, per unique column (computed once, not per row). Salesforce
    # compares unique text case-insensitively unless the field is case sensitive.
    duplicate_groups = {}
    for column, field_name in unique_columns.items():
        case_sensitive = sf_fields[field_name].get('caseSensitive', False)
        values = df_transformed_indexed[column]
        keys = values.map(lambda v: None if _is_blank(v) else _unique_key(v, case_sensitive))
        groups = {}
        for position, key in zip(df_transformed_indexed.index, keys):
            if key is not None:
                groups.setdefault(key, []).append(position)
        duplicate_groups[column] = ({k: v for k, v in groups.items() if len(v) > 1}, keys)

    # Initialize lists to track success and failure records
    success_indices = []
    failure_indices = []
    transform_details = []

    status_text.text(f"Analyzing transform results for {len(df_transformed_indexed)} records...")
    st.info(f"📊 **Validation Scope:**")
    st.write(f"- **Records to analyze:** {len(df_transformed_indexed)}")
    st.write(f"- **Lookup fields:** {len(lookup_fields)} ({list(lookup_fields.keys()) if lookup_fields else 'None'})")
    st.write(f"- **Validation checks:** Lookup transformation, Picklist values, Unique constraints, Required fields")
    if unmapped_required:
        st.warning(f"⚠️ Required fields not mapped to any column: {', '.join(unmapped_required)}. "
                   "Inserts will fail unless they are set in Step 3 (e.g. as Additional Columns); "
                   "updates are not affected.")
    
    # Early exit if no records to analyze
    if len(df_transformed_indexed) == 0:
        st.warning("⚠️ No records to analyze. Skipping transform validation.")
        empty_df = pd.DataFrame()
        return empty_df, empty_df, {
            'success_count': 0,
            'failure_count': 0,
            'total_count': 0,
            'success_percentage': 0,
            'failure_percentage': 0,
            'lookup_failures': 0,
            'picklist_failures': 0,
            'unique_failures': 0,
            'details': []
        }
    
    progress_bar.progress(50)
    
    # Process each record
    for idx in range(len(df_transformed_indexed)):
        record_failed = False
        record_details = {
            'row_index': idx,
            'lookup_fields_checked': [],
            'unchanged_fields': [],
            'changed_fields': [],
            'picklist_failures': [],
            'unique_field_failures': [],
            'required_field_failures': [],
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
        
        row = df_transformed_indexed.iloc[idx]

        # Check 2: Picklist value validation
        for column, field_name in picklist_columns.items():
            field_value = row[column]
            if _is_blank(field_value):
                continue
            # Get valid picklist values (API names)
            valid_values = [pv.get('valueName', pv.get('value', '')) for pv in sf_fields[field_name].get('picklistValues', [])
                            if pv.get('active', True)]
            current_value = str(field_value).strip()
            if sf_fields[field_name].get('type') == 'multipicklist':
                invalid = [v.strip() for v in current_value.split(';') if v.strip() and v.strip() not in valid_values]
            else:
                invalid = [current_value] if current_value not in valid_values else []
            if valid_values and invalid:
                record_failed = True
                record_details['picklist_failures'].append({
                    'field': field_name,
                    'column': column,
                    'invalid_value': '; '.join(invalid),
                    'valid_values': valid_values[:10]  # Show first 10 valid values
                })

        # Check 3: Unique field validation (check for duplicates within the dataset)
        for column, field_name in unique_columns.items():
            groups, keys = duplicate_groups[column]
            key = keys.iloc[idx]
            if key is None or key not in groups:
                continue
            record_failed = True
            duplicate_indices = [i for i in groups[key] if i != idx]
            record_details['unique_field_failures'].append({
                'field': field_name,
                'column': column,
                'duplicate_value': str(row[column]).strip(),
                'duplicate_row_indices': duplicate_indices[:5]  # Show first 5 duplicate rows
            })

        # Check 4: Required fields must have a value
        for column, field_name in required_columns.items():
            if _is_blank(row[column]):
                record_failed = True
                record_details['required_field_failures'].append({'field': field_name, 'column': column})

        # Determine final status and reason
        checked_anything = bool(record_details['lookup_fields_checked'] or picklist_columns
                                or unique_columns or required_columns)
        if record_failed:
            failure_indices.append(idx)
            failure_reasons = []
            if record_details['unchanged_fields']:
                failure_reasons.append(f"Unchanged lookup fields: {[f['field'] for f in record_details['unchanged_fields']]}")
            if record_details['picklist_failures']:
                failure_reasons.append(f"Invalid picklist values: {[f['field'] for f in record_details['picklist_failures']]}")
            if record_details['unique_field_failures']:
                failure_reasons.append(f"Duplicate unique field values: {[f['field'] for f in record_details['unique_field_failures']]}")
            if record_details['required_field_failures']:
                failure_reasons.append(f"Missing required fields: {[f['field'] for f in record_details['required_field_failures']]}")
            record_details['reason'] = "; ".join(failure_reasons)
        elif not checked_anything:
            success_indices.append(idx)
            record_details['reason'] = 'No validations required (no lookup/picklist/unique/required fields)'
        else:
            success_indices.append(idx)
            record_details['reason'] = 'All validations passed (lookups transformed, picklist values valid, unique fields unique, required fields present)'
        
        transform_details.append(record_details)
    
    progress_bar.progress(75)
    
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
        
        # Add detailed validation failure information with specific data issues
        validation_details = []
        data_issues = []
        for i in failure_indices:
            details = transform_details[i]
            detail_parts = []
            issue_parts = []
            
            if details['unchanged_fields']:
                detail_parts.append(f"Unchanged: {', '.join([f['field'] for f in details['unchanged_fields']])}")
                for uf in details['unchanged_fields']:
                    issue_parts.append(f"Lookup not found for {uf['field']}='{uf['value']}'")
            
            if details['picklist_failures']:
                for pf in details['picklist_failures']:
                    detail_parts.append(f"Invalid picklist {pf['field']}: '{pf['invalid_value']}'")
                    valid_options = pf['valid_values'][:5]  # Show first 5 valid options
                    issue_parts.append(f"Wrong picklist value '{pf['invalid_value']}' for {pf['field']} (valid: {', '.join(valid_options)}{'...' if len(pf['valid_values']) > 5 else ''})")
            
            if details['unique_field_failures']:
                for uf in details['unique_field_failures']:
                    detail_parts.append(f"Duplicate unique {uf['field']}: '{uf['duplicate_value']}'")
                    issue_parts.append(f"Duplicate value '{uf['duplicate_value']}' in unique field {uf['field']} (found in rows: {', '.join(map(str, uf['duplicate_row_indices']))})")

            if details.get('required_field_failures'):
                for rf in details['required_field_failures']:
                    detail_parts.append(f"Missing required {rf['field']}")
                    issue_parts.append(f"Required field {rf['field']} is empty (column '{rf['column']}')")
            
            validation_details.append("; ".join(detail_parts))
            data_issues.append("; ".join(issue_parts) if issue_parts else "Unknown validation failure")
        
        df_failure['Validation_Details'] = validation_details
        df_failure['Data_Issue_Details'] = data_issues
    
    progress_bar.progress(100)
    
    # Summary with detailed breakdown
    success_count = len(success_indices)
    failure_count = len(failure_indices)
    total_count = len(df_transformed_indexed)
    
    # Count different types of failures
    lookup_failures = sum(1 for i in failure_indices if transform_details[i]['unchanged_fields'])
    picklist_failures = sum(1 for i in failure_indices if transform_details[i]['picklist_failures']) 
    unique_failures = sum(1 for i in failure_indices if transform_details[i]['unique_field_failures'])
    required_failures = sum(1 for i in failure_indices if transform_details[i]['required_field_failures'])

    status_text.text("✅ Transform analysis completed!")
    
    return df_success, df_failure, {
        'success_count': success_count,
        'failure_count': failure_count,
        'total_count': total_count,
        'success_percentage': success_count/total_count*100 if total_count > 0 else 0,
        'failure_percentage': failure_count/total_count*100 if total_count > 0 else 0,
        'lookup_failures': lookup_failures,
        'picklist_failures': picklist_failures,
        'unique_failures': unique_failures,
        'required_failures': required_failures,
        'unmapped_required_fields': unmapped_required,
        'details': transform_details
    }


def save_transform_results(df_success: pd.DataFrame, df_failure: pd.DataFrame, df_all_transformed: pd.DataFrame,
                          selected_org: str, selected_object: str, transform_summary: Dict,
                          lookup_fields: Dict = None, lookup_count_summary: Dict = None) -> Dict[str, str]:
    """
    Save transform results in organized folder structure with comprehensive reporting
    """
    # Create folder structure: DataLoader_Logs/dataload/Dataload_{org}/{object}/TransformedData/
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_folder = os.path.join(project_root, 'DataLoader_Logs')
    dataload_folder = os.path.join(root_folder, 'dataload')
    org_folder = os.path.join(dataload_folder, f'Dataload_{selected_org}')
    object_folder = os.path.join(org_folder, selected_object)
    transformed_data_folder = os.path.join(object_folder, 'TransformedData')
    
    # Ensure directory exists
    os.makedirs(transformed_data_folder, exist_ok=True)
    
    # Generate timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # File paths
    success_file_path = os.path.join(transformed_data_folder, f'transform_success_{timestamp}.csv')
    failure_file_path = os.path.join(transformed_data_folder, f'transform_failure_{timestamp}.csv')
    all_data_file_path = os.path.join(transformed_data_folder, f'Transformed_Data_{timestamp}.csv')
    summary_file_path = os.path.join(transformed_data_folder, f'transform_summary_{timestamp}.txt')
    
    file_paths = {}
    
    try:
        # Save transform success data (exclude validation columns)
        if not df_success.empty:
            df_success_clean = df_success.drop(columns=['Transform_Status', 'Transform_Reason', 'Validation_Details'], errors='ignore')
            df_success_clean.to_csv(success_file_path, index=False)
            file_paths['success'] = success_file_path
            st.success(f"✅ **Transform success data saved:** `{os.path.basename(success_file_path)}`")
        else:
            st.info("ℹ️ No transform success records to save")
        
        # Save transform failure data (keep Data_Issue_Details column but exclude other validation columns)
        if not df_failure.empty:
            df_failure_clean = df_failure.drop(columns=['Transform_Status', 'Transform_Reason', 'Validation_Details'], errors='ignore')
            df_failure_clean.to_csv(failure_file_path, index=False)
            file_paths['failure'] = failure_file_path
            st.warning(f"❌ **Transform failure data saved:** `{os.path.basename(failure_file_path)}`")
        else:
            st.info("ℹ️ No transform failure records to save")
        
        # Save all transformed data
        df_all_transformed.to_csv(all_data_file_path, index=False)
        file_paths['all_data'] = all_data_file_path
        st.info(f"📄 **All transformed data saved:** `{os.path.basename(all_data_file_path)}`")
        
        # Save comprehensive summary report
        with open(summary_file_path, 'w', encoding='utf-8') as summary_file:
            summary_file.write("TRANSFORM RESULTS SUMMARY REPORT\n")
            summary_file.write("=" * 50 + "\n\n")
            summary_file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            summary_file.write(f"Salesforce Org: {selected_org}\n")
            summary_file.write(f"Target Object: {selected_object}\n\n")
            
            summary_file.write("OVERALL STATISTICS:\n")
            summary_file.write(f"Total Records Processed: {transform_summary['total_count']}\n")
            summary_file.write(f"Transform Success: {transform_summary['success_count']} ({transform_summary['success_percentage']:.1f}%)\n")
            summary_file.write(f"Transform Failure: {transform_summary['failure_count']} ({transform_summary['failure_percentage']:.1f}%)\n\n")
            
            if transform_summary['failure_count'] > 0:
                summary_file.write("FAILURE BREAKDOWN:\n")
                summary_file.write(f"- Lookup transformation failures: {transform_summary.get('lookup_failures', 0)}\n")
                summary_file.write(f"- Picklist validation failures: {transform_summary.get('picklist_failures', 0)}\n")
                summary_file.write(f"- Unique field constraint failures: {transform_summary.get('unique_failures', 0)}\n\n")
            
            if lookup_fields:
                summary_file.write("LOOKUP FIELDS PROCESSED:\n")
                for lookup_field, related_object in lookup_fields.items():
                    lookup_count = lookup_count_summary.get(lookup_field, 0) if lookup_count_summary else 0
                    summary_file.write(f"- {lookup_field} -> {related_object} ({lookup_count} values resolved)\n")
                if lookup_count_summary:
                    summary_file.write(f"\nTotal Lookup Values Resolved: {sum(lookup_count_summary.values())}\n\n")
            
            summary_file.write("VALIDATION LOGIC:\n")
            summary_file.write("- SUCCESS: All validations passed (lookup fields transformed, picklist values valid, unique fields unique)\n")
            summary_file.write("- FAILURE: One or more validations failed:\n")
            summary_file.write("  * Lookup fields remain unchanged from original raw data\n")
            summary_file.write("  * Picklist values don't match Salesforce picklist API names\n")
            summary_file.write("  * Unique field values are duplicated within the dataset\n\n")
            
            summary_file.write("FILES GENERATED:\n")
            if 'success' in file_paths:
                summary_file.write(f"- Success Data: {os.path.basename(file_paths['success'])}\n")
            if 'failure' in file_paths:
                summary_file.write(f"- Failure Data: {os.path.basename(file_paths['failure'])}\n")
            summary_file.write(f"- All Transformed Data: {os.path.basename(file_paths['all_data'])}\n")
            summary_file.write(f"- Summary Report: {os.path.basename(summary_file_path)}\n\n")
            
            summary_file.write(f"FOLDER LOCATION:\n{transformed_data_folder}\n")
        
        file_paths['summary'] = summary_file_path
        st.success(f"📊 **Transform summary report saved:** `{os.path.basename(summary_file_path)}`")
        
        # Show final summary
        st.success(f"🎉 **All files saved successfully to:**")
        st.code(transformed_data_folder)
        
        return file_paths
        
    except Exception as e:
        st.error(f"❌ **Error saving transform results:** {str(e)}")
        return {}


def display_transform_results_preview(df_success: pd.DataFrame, df_failure: pd.DataFrame, 
                                     selected_object: str, transform_summary: Dict):
    """
    Display comprehensive transform results preview with success/failure breakdown
    """
    st.subheader("🔍 Transform Results Preview")
    
    # Summary stats in columns
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎯 Target Object", selected_object)
    with col2:
        st.metric("✅ Success", f"{transform_summary['success_count']}", f"{transform_summary['success_percentage']:.1f}%")
    with col3:
        st.metric("❌ Failure", f"{transform_summary['failure_count']}", f"{transform_summary['failure_percentage']:.1f}%")
    with col4:
        st.metric("📊 Total", transform_summary['total_count'])
    
    if transform_summary['failure_count'] > 0:
        st.warning("🔍 **Detailed Failure Analysis:**")
        failure_col1, failure_col2, failure_col3 = st.columns(3)
        with failure_col1:
            st.metric("🔗 Lookup Failures", transform_summary.get('lookup_failures', 0))
        with failure_col2:
            st.metric("📋 Picklist Failures", transform_summary.get('picklist_failures', 0))
        with failure_col3:
            st.metric("🔑 Unique Field Failures", transform_summary.get('unique_failures', 0))
    
    # Tabbed data preview
    tab1, tab2 = st.tabs([f"✅ Success Data ({transform_summary['success_count']})", 
                          f"❌ Failure Data ({transform_summary['failure_count']})"])
    
    with tab1:
        if not df_success.empty:
            st.success(f"📋 **Success Records Preview** (showing first 100)")
            
            # Show columns of interest
            display_columns = [col for col in df_success.columns if not col.startswith('Transform_') and not col.startswith('Validation_')]
            if len(display_columns) > 10:
                display_columns = display_columns[:10]
            
            st.dataframe(df_success[display_columns].head(100), use_container_width=True)
            
            if len(df_success) > 100:
                st.info(f"📈 Showing first 100 rows of {len(df_success)} success records")
        else:
            st.info("No successful transform records")
    
    with tab2:
        if not df_failure.empty:
            st.error(f"📋 **Failure Records Preview** (showing first 100)")
            
            # Show detailed failure information
            if 'Data_Issue_Details' in df_failure.columns:
                st.warning("🔍 **Issue Details:**")
                for idx, row in df_failure.head(10).iterrows():
                    with st.expander(f"Record {idx + 1}: {row.get('Data_Issue_Details', 'Unknown issue')[:100]}..."):
                        issue_details = row.get('Data_Issue_Details', 'No details available')
                        st.error(f"**Issues:** {issue_details}")
                        
                        # Show the actual data
                        data_cols = [col for col in df_failure.columns if not col.startswith('Transform_') 
                                   and not col.startswith('Validation_') and col != 'Data_Issue_Details']
                        if data_cols:
                            st.write("**Record Data:**")
                            for col in data_cols[:5]:  # Show first 5 columns
                                st.write(f"- **{col}:** `{row.get(col, 'N/A')}`")
                
                if len(df_failure) > 10:
                    st.info(f"📈 Showing details for first 10 rows of {len(df_failure)} failure records")
            
            # Show raw failure data
            st.write("**Raw Failure Data:**")
            display_columns = [col for col in df_failure.columns if not col.startswith('Transform_') and not col.startswith('Validation_')]
            if len(display_columns) > 8:
                display_columns = display_columns[:8]
            
            st.dataframe(df_failure[display_columns].head(100), use_container_width=True)
            
            if len(df_failure) > 100:
                st.info(f"📈 Showing first 100 rows of {len(df_failure)} failure records")
        else:
            st.success("🎉 No failure records - all transforms were successful!")


def clean_dataframe_for_salesforce(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean DataFrame to make it JSON compliant and Salesforce-ready
    Enhanced version from transformed.py
    """
    df_clean = df.copy()
    
    # Replace NaN, inf, -inf with empty strings for better Salesforce compatibility
    df_clean = df_clean.replace([float('inf'), float('-inf')], '')
    df_clean = df_clean.where(pd.notnull(df_clean), '')
    
    # Convert numpy data types to Python native types
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            # Handle string columns - convert NaN/None to empty string and strip whitespace
            df_clean[col] = df_clean[col].apply(
                lambda x: str(x).strip() if pd.notnull(x) and str(x).strip() not in ['nan', 'None', 'null'] else ''
            )
        elif pd.api.types.is_numeric_dtype(df_clean[col]):
            # Handle numeric columns - ensure they're JSON compliant, replace NaN with empty string
            if pd.api.types.is_integer_dtype(df_clean[col]):
                # Convert to nullable integer, then to regular int where possible, empty string for NaN
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                df_clean[col] = df_clean[col].apply(lambda x: int(x) if pd.notnull(x) and x == x else '')
            else:
                # Convert to float, handling NaN with empty string
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                df_clean[col] = df_clean[col].apply(lambda x: float(x) if pd.notnull(x) and x == x and abs(x) != float('inf') else '')
        elif pd.api.types.is_datetime64_any_dtype(df_clean[col]):
            # Handle datetime columns - empty string for null dates
            df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ').where(pd.notnull(df_clean[col]), '')
        elif pd.api.types.is_bool_dtype(df_clean[col]):
            # Handle boolean columns - convert NaN to empty string
            df_clean[col] = df_clean[col].apply(lambda x: bool(x) if pd.notnull(x) else '')
    
    return df_clean


def validate_json_compliance(df: pd.DataFrame) -> bool:
    """
    Validate that DataFrame can be converted to JSON for Salesforce operations
    """
    try:
        test_records = df.head(1).to_dict('records')
        json.dumps(test_records, allow_nan=False)
        return True
    except (ValueError, TypeError) as e:
        st.warning(f"⚠️ **Data validation warning:** {e}")
        return False


def enhanced_transform_workflow(df_original: pd.DataFrame, df_transformed: pd.DataFrame,
                               lookup_fields: Dict, selected_object: str, selected_org: str,
                               sf_conn, lookup_count_summary: Dict = None) -> bool:
    """
    Complete enhanced transform workflow with validation, preview, and saving
    Returns True if user confirms saving, False if cancelled
    """
    st.info("🚀 **Starting Enhanced Transform Validation Workflow**")
    
    # Step 1: Categorize transform results
    with st.spinner("Analyzing transform results..."):
        df_success, df_failure, transform_summary = categorize_transform_results(
            df_original, df_transformed, lookup_fields, selected_object, sf_conn
        )
    
    # Step 2: Clean data for Salesforce compatibility  
    st.info("🧹 **Cleaning data for Salesforce compatibility...**")
    df_transformed_clean = clean_dataframe_for_salesforce(df_transformed)
    
    # Step 3: Validate JSON compliance
    if not validate_json_compliance(df_transformed_clean):
        st.warning("⚠️ **Warning:** Data contains values that may not be JSON compliant.")
    else:
        st.success("✅ **Data is JSON compliant and ready for Salesforce**")
    
    # Step 4: Display comprehensive preview
    display_transform_results_preview(df_success, df_failure, selected_object, transform_summary)
    
    # Step 5: User decision
    st.subheader("💾 Save Transform Results")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("**Review the transform results above. Click 'Save Transform Results' to proceed or 'Cancel' to abort.**")
    
    with col2:
        save_button = st.button("💾 **Save Transform Results**", type="primary", use_container_width=True)
        cancel_button = st.button("❌ **Cancel**", use_container_width=True)
    
    if cancel_button:
        st.error("❌ **Transform workflow cancelled by user**")
        st.stop()
        return False
    
    if save_button:
        # Step 6: Save all results
        with st.spinner("Saving transform results..."):
            file_paths = save_transform_results(
                df_success, df_failure, df_transformed_clean,
                selected_org, selected_object, transform_summary,
                lookup_fields, lookup_count_summary
            )
        
        if file_paths:
            # Step 7: Show final success message
            st.balloons()
            st.success("🎉 **Transform workflow completed successfully!**")
            
            # Create summary for user
            lookup_summary = ""
            if lookup_fields and lookup_count_summary:
                total_resolved = sum(lookup_count_summary.values())
                lookup_summary = f"🔗 **Lookup Processing:** {len(lookup_fields)} field(s), {total_resolved} values resolved\n\n"
            
            with st.expander("📋 **Complete Transform Summary**", expanded=True):
                st.markdown(f"""
**📊 TRANSFORM RESULTS:**
- ✅ **Success:** {transform_summary['success_count']} records ({transform_summary['success_percentage']:.1f}%)
- ❌ **Failure:** {transform_summary['failure_count']} records ({transform_summary['failure_percentage']:.1f}%)
- 📋 **Total:** {transform_summary['total_count']} records

**🔍 FAILURE BREAKDOWN:**
- 🔗 Lookup failures: {transform_summary.get('lookup_failures', 0)}
- 📋 Picklist failures: {transform_summary.get('picklist_failures', 0)}
- 🔑 Unique field failures: {transform_summary.get('unique_failures', 0)}

{lookup_summary}**📁 FILES SAVED:**
{chr(10).join([f'- {os.path.basename(path)}' for path in file_paths.values()])}

**📂 Location:** `{os.path.dirname(list(file_paths.values())[0])}`
""")
            
            return True
    
    return False