"""
Org Migration - Phase 2: Related Objects Loading Module
Handles ID mapping, sequential loading, and cascading operations for parent-child migration

Key Features:
- ID Mapping: Track source IDs → target IDs for parent records
- Sequential Loading: Load parents first, then children with mapped IDs
- Error Handling: Detailed error tracking and retry capability
- Cascading Operations: Handle parent deletion, sharing, record type inheritance
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from simple_salesforce import Salesforce
import json
from datetime import datetime


def build_id_mapping_from_results(
    source_parent_df: pd.DataFrame,
    insert_results: List[Dict]
) -> Dict[str, str]:
    """
    Build mapping of source Parent IDs to target Parent IDs after successful inserts
    
    Args:
        source_parent_df: DataFrame with source parent records (must have 'Id' column)
        insert_results: List of results from Salesforce insert operation
                       [{"id": "target_id", "success": True, "created": True}, ...]
    
    Returns:
        Dictionary mapping: {source_id: target_id}
    """
    try:
        id_mapping = {}
        
        if len(insert_results) != len(source_parent_df):
            st.error(f"❌ Result count mismatch: Expected {len(source_parent_df)}, got {len(insert_results)}")
            return id_mapping
        
        source_ids = source_parent_df['Id'].tolist() if 'Id' in source_parent_df.columns else []
        
        for idx, result in enumerate(insert_results):
            if result.get('success', False) and result.get('created', False):
                source_id = source_ids[idx] if idx < len(source_ids) else None
                target_id = result.get('id')
                
                if source_id and target_id:
                    id_mapping[source_id] = target_id
        
        return id_mapping
        
    except Exception as e:
        st.error(f"❌ Error building ID mapping: {str(e)}")
        return {}


def prepare_child_records_for_loading(
    child_df: pd.DataFrame,
    parent_field: str,
    id_mapping: Dict[str, str],
    exclude_fields: List[str] = None
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Prepare child records for loading by:
    1. Replacing old parent IDs with new parent IDs
    2. Removing Salesforce system fields
    3. Keeping only necessary columns
    
    Args:
        child_df: Child records DataFrame
        parent_field: Name of parent reference field (e.g., "Questionnaire__c")
        id_mapping: Mapping of source parent IDs to target parent IDs
        exclude_fields: Fields to exclude from loading
    
    Returns:
        Tuple of (prepared_df, unmapped_records)
        - prepared_df: Ready to load
        - unmapped_records: List of indices that couldn't be mapped
    """
    try:
        prepared_df = child_df.copy()
        unmapped_indices = []
        
        # Default exclude fields
        if exclude_fields is None:
            exclude_fields = ['Id', 'attributes', 'CreatedDate', 'LastModifiedDate', 
                            'SystemModstamp', 'CreatedById', 'LastModifiedById']
        
        # Replace old parent IDs with new ones
        if parent_field in prepared_df.columns:
            for idx, row in prepared_df.iterrows():
                old_parent_id = row[parent_field]
                
                if pd.isna(old_parent_id):
                    unmapped_indices.append(idx)
                    continue
                
                if str(old_parent_id) in id_mapping:
                    new_parent_id = id_mapping[str(old_parent_id)]
                    prepared_df.at[idx, parent_field] = new_parent_id
                else:
                    unmapped_indices.append(idx)
        else:
            st.error(f"❌ Parent field '{parent_field}' not found in child records")
            return None, list(range(len(prepared_df)))
        
        # Remove Salesforce system fields
        columns_to_drop = [col for col in exclude_fields if col in prepared_df.columns]
        if columns_to_drop:
            prepared_df = prepared_df.drop(columns=columns_to_drop, errors='ignore')
        
        # Remove rows with unmapped parents (for Master-Detail, these are critical)
        if unmapped_indices:
            st.warning(f"⚠️ {len(unmapped_indices)} child record(s) have unmapped parent references")
        
        return prepared_df, unmapped_indices
        
    except Exception as e:
        st.error(f"❌ Error preparing child records: {str(e)}")
        return None, []


def load_parent_records(
    target_sf: Salesforce,
    parent_object: str,
    parent_df: pd.DataFrame,
    operation: str = "INSERT"
) -> Tuple[List[Dict], List[Dict], Optional[pd.DataFrame]]:
    """
    Load parent records to target org and track results
    
    Args:
        target_sf: Target Salesforce connection
        parent_object: Parent object name (e.g., "Questionnaire")
        parent_df: DataFrame with parent records to load
        operation: INSERT, UPDATE, or UPSERT
    
    Returns:
        Tuple of (successful_results, failed_results, failed_df)
        - successful_results: List of successful insert operations
        - failed_results: List of failed operations with error details
        - failed_df: DataFrame with failed records (None if all succeeded)
    """
    try:
        st.info(f"📤 Loading {len(parent_df)} {parent_object} records to target org...")
        
        successful_results = []
        failed_results = []
        failed_indices = []
        
        # Prepare data for insertion (remove Id for INSERT operation)
        parent_data = parent_df.copy()
        if operation == "INSERT":
            parent_data = parent_data.drop('Id', axis=1, errors='ignore')
        
        # Convert DataFrame to list of dicts for Salesforce API
        records_to_load = parent_data.to_dict('records')
        
        # Load using Salesforce bulk API
        progress_bar = st.progress(0)
        
        for idx, record in enumerate(records_to_load):
            try:
                # Get the Salesforce object
                sf_obj = getattr(target_sf, parent_object)
                
                if operation == "INSERT":
                    result = sf_obj.create(record)
                elif operation == "UPDATE":
                    record_id = parent_df.iloc[idx]['Id']
                    result = sf_obj.update(record_id, record)
                elif operation == "UPSERT":
                    # UPSERT requires external ID - using CREATE for now
                    result = sf_obj.create(record)
                else:
                    result = sf_obj.create(record)
                
                # Track success
                result_with_meta = {
                    "id": result if isinstance(result, str) else result.get('id', ''),
                    "success": True,
                    "created": True,
                    "record_index": idx,
                    "status_code": 201
                }
                successful_results.append(result_with_meta)
                
            except Exception as e:
                # Track failure
                failed_results.append({
                    "record_index": idx,
                    "success": False,
                    "error": str(e),
                    "status_code": 400
                })
                failed_indices.append(idx)
            
            # Update progress
            progress_bar.progress((idx + 1) / len(records_to_load))
        
        # Build failed records DataFrame
        failed_df = None
        if failed_indices:
            failed_df = parent_df.iloc[failed_indices].copy()
            failed_df['load_error'] = [
                failed_results[i]['error'] 
                for i in range(len(failed_results)) 
                if failed_results[i]['record_index'] in failed_indices
            ]
        
        # Display results
        st.success(f"✅ Loaded {len(successful_results)} {parent_object} records successfully")
        
        if failed_results:
            st.error(f"❌ {len(failed_results)} record(s) failed to load")
            
            # Show sample errors
            with st.expander(f"🔍 View {len(failed_results)} Failed Records"):
                for fail in failed_results[:10]:
                    st.error(f"Record index {fail['record_index']}: {fail['error']}")
                if len(failed_results) > 10:
                    st.info(f"... and {len(failed_results) - 10} more")
        
        return successful_results, failed_results, failed_df
        
    except Exception as e:
        st.error(f"❌ Error loading parent records: {str(e)}")
        return [], [], parent_df.copy()


def load_child_records(
    target_sf: Salesforce,
    child_object: str,
    child_df: pd.DataFrame,
    operation: str = "INSERT"
) -> Tuple[List[Dict], List[Dict], Optional[pd.DataFrame]]:
    """
    Load child records to target org
    
    Args:
        target_sf: Target Salesforce connection
        child_object: Child object name (e.g., "Section")
        child_df: DataFrame with child records (already mapped to target parent IDs)
        operation: INSERT, UPDATE, or UPSERT
    
    Returns:
        Tuple of (successful_results, failed_results, failed_df)
    """
    try:
        st.info(f"📤 Loading {len(child_df)} {child_object} records...")
        
        successful_results = []
        failed_results = []
        failed_indices = []
        
        # Prepare data
        child_data = child_df.copy()
        if operation == "INSERT":
            child_data = child_data.drop('Id', axis=1, errors='ignore')
        
        records_to_load = child_data.to_dict('records')
        
        progress_bar = st.progress(0)
        
        for idx, record in enumerate(records_to_load):
            try:
                sf_obj = getattr(target_sf, child_object)
                
                if operation == "INSERT":
                    result = sf_obj.create(record)
                else:
                    result = sf_obj.create(record)
                
                result_with_meta = {
                    "id": result if isinstance(result, str) else result.get('id', ''),
                    "success": True,
                    "created": True,
                    "record_index": idx
                }
                successful_results.append(result_with_meta)
                
            except Exception as e:
                failed_results.append({
                    "record_index": idx,
                    "success": False,
                    "error": str(e)
                })
                failed_indices.append(idx)
            
            progress_bar.progress((idx + 1) / len(records_to_load))
        
        failed_df = None
        if failed_indices:
            failed_df = child_df.iloc[failed_indices].copy()
            failed_df['load_error'] = [
                failed_results[i]['error']
                for i in range(len(failed_results))
                if failed_results[i]['record_index'] in failed_indices
            ]
        
        st.success(f"✅ Loaded {len(successful_results)} {child_object} records successfully")
        
        if failed_results:
            st.error(f"❌ {len(failed_results)} {child_object} record(s) failed")
        
        return successful_results, failed_results, failed_df
        
    except Exception as e:
        st.error(f"❌ Error loading {child_object} records: {str(e)}")
        return [], [], child_df.copy()


def execute_parent_child_migration(
    target_sf: Salesforce,
    migration_data: Dict,
    operation: str = "INSERT"
) -> Dict:
    """
    Execute complete parent-child migration with proper sequencing
    
    Migration sequence:
    1. Load parent records
    2. Build ID mapping
    3. Prepare child records with mapped IDs
    4. Load child records
    5. Generate results summary
    
    Args:
        target_sf: Target Salesforce connection
        migration_data: Complete data structure from Phase 1:
                       {parent: df, children: {...}, parent_object: "..."}
        operation: INSERT, UPDATE, or UPSERT
    
    Returns:
        Complete results dictionary with all outcomes
    """
    try:
        results = {
            "status": "in_progress",
            "start_time": datetime.now().isoformat(),
            "parent_results": None,
            "child_results": {},
            "id_mapping": {},
            "errors": [],
            "summary": {}
        }
        
        parent_df = migration_data.get('parent', pd.DataFrame())
        parent_object = migration_data.get('parent_object', '')
        children = migration_data.get('children', {})
        
        if parent_df.empty:
            results['errors'].append("No parent records to migrate")
            results['status'] = "failed"
            return results
        
        # STEP 1: Load parent records
        st.markdown("## 📤 Phase 2: Parent-Child Migration")
        st.markdown("---")
        
        st.markdown("### Step 1: Loading Parent Records")
        parent_success, parent_failed, parent_failed_df = load_parent_records(
            target_sf, parent_object, parent_df, operation
        )
        
        results['parent_results'] = {
            "successful": len(parent_success),
            "failed": len(parent_failed),
            "object": parent_object,
            "failed_records": parent_failed_df
        }
        
        if not parent_success:
            results['errors'].append(f"Failed to load any {parent_object} records")
            results['status'] = "failed"
            return results
        
        # STEP 2: Build ID mapping
        st.markdown("### Step 2: Building ID Mapping")
        id_mapping = build_id_mapping_from_results(parent_df, parent_success)
        results['id_mapping'] = id_mapping
        st.success(f"✅ Created mapping for {len(id_mapping)} parent record(s)")
        
        if len(id_mapping) == 0:
            results['errors'].append("Could not build ID mapping")
            results['status'] = "failed"
            return results
        
        # STEP 3: Load child records
        st.markdown("### Step 3: Loading Child Records")
        st.markdown("---")
        
        total_children_loaded = 0
        total_children_failed = 0
        
        for child_object, child_info in children.items():
            child_df = child_info.get('data', pd.DataFrame())
            parent_field = child_info.get('parent_field', '')
            relationship_type = child_info.get('relationship_type', 'lookup')
            
            if child_df.empty:
                st.info(f"ℹ️ No {child_object} records to load")
                continue
            
            st.markdown(f"#### 📦 Loading {child_object}")
            
            # Prepare child records with mapped IDs
            prepared_df, unmapped = prepare_child_records_for_loading(
                child_df, parent_field, id_mapping
            )
            
            if prepared_df is None or prepared_df.empty:
                results['errors'].append(f"Failed to prepare {child_object} records")
                continue
            
            # Check for unmapped records in Master-Detail
            if unmapped and relationship_type == "master_detail":
                st.error(f"❌ {len(unmapped)} {child_object} record(s) have unmapped parents (CRITICAL for Master-Detail)")
                # Remove unmapped records for Master-Detail
                prepared_df = prepared_df.drop(prepared_df.index[unmapped])
            
            # Load child records
            child_success, child_failed, child_failed_df = load_child_records(
                target_sf, child_object, prepared_df, operation
            )
            
            results['child_results'][child_object] = {
                "successful": len(child_success),
                "failed": len(child_failed),
                "failed_records": child_failed_df,
                "relationship_type": relationship_type
            }
            
            total_children_loaded += len(child_success)
            total_children_failed += len(child_failed)
            
            st.markdown("---")
        
        # SUMMARY
        st.markdown("## 📊 Migration Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Parent Records",
                len(parent_success),
                f"-{len(parent_failed)} failed"
            )
        
        with col2:
            st.metric(
                "Child Objects",
                len(results['child_results'])
            )
        
        with col3:
            st.metric(
                "Child Records Loaded",
                total_children_loaded,
                f"-{total_children_failed} failed"
            )
        
        with col4:
            st.metric(
                "Total Records",
                len(parent_success) + total_children_loaded
            )
        
        # Summary breakdown
        st.markdown("### Results by Object")
        
        summary_data = []
        
        # Parent row
        summary_data.append({
            "Object": parent_object,
            "Type": "Parent",
            "Records": len(parent_success),
            "Failed": len(parent_failed),
            "Status": "✅" if len(parent_failed) == 0 else "⚠️"
        })
        
        # Child rows
        for child_obj, child_res in results['child_results'].items():
            summary_data.append({
                "Object": child_obj,
                "Type": child_res['relationship_type'].upper(),
                "Records": child_res['successful'],
                "Failed": child_res['failed'],
                "Status": "✅" if child_res['failed'] == 0 else "⚠️"
            })
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        
        results['summary'] = {
            "total_parent_records": len(parent_success),
            "parent_failed": len(parent_failed),
            "total_child_records": total_children_loaded,
            "child_failed": total_children_failed,
            "total_records": len(parent_success) + total_children_loaded
        }
        
        results['status'] = 'completed'
        results['end_time'] = datetime.now().isoformat()
        
        return results
        
    except Exception as e:
        st.error(f"❌ Migration failed: {str(e)}")
        results['status'] = 'failed'
        results['errors'].append(str(e))
        return results


def display_migration_results(results: Dict) -> None:
    """
    Display detailed migration results and options for retry/rollback
    
    Args:
        results: Results dictionary from execute_parent_child_migration
    """
    st.markdown("## 📋 Detailed Migration Results")
    
    # Show any errors
    if results.get('errors'):
        st.markdown("### ⚠️ Errors Encountered")
        for error in results['errors']:
            st.error(f"• {error}")
    
    # Show parent results
    if results.get('parent_results'):
        parent_res = results['parent_results']
        
        st.markdown(f"### Parent Records ({parent_res['object']})")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Successfully Loaded", parent_res['successful'])
        
        with col2:
            if parent_res['failed'] > 0:
                st.metric("Failed", parent_res['failed'], delta=f"-{parent_res['failed']}", delta_color="inverse")
            else:
                st.metric("Failed", 0)
        
        # Show failed parent records
        if parent_res.get('failed_records') is not None and not parent_res['failed_records'].empty:
            with st.expander(f"❌ Failed Parent Records ({len(parent_res['failed_records'])})"):
                st.dataframe(parent_res['failed_records'], use_container_width=True)
                
                # Download failed records
                csv = parent_res['failed_records'].to_csv(index=False)
                st.download_button(
                    label="⬇️ Download Failed Records",
                    data=csv,
                    file_name=f"failed_{parent_res['object']}_records.csv",
                    mime="text/csv"
                )
    
    # Show child results
    if results.get('child_results'):
        st.markdown("### Child Records Details")
        
        for child_obj, child_res in results['child_results'].items():
            with st.expander(f"📦 {child_obj} ({child_res['relationship_type'].upper()})", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Successfully Loaded", child_res['successful'])
                
                with col2:
                    if child_res['failed'] > 0:
                        st.metric("Failed", child_res['failed'], delta=f"-{child_res['failed']}", delta_color="inverse")
                    else:
                        st.metric("Failed", 0)
                
                # Show failed records
                if child_res.get('failed_records') is not None and not child_res['failed_records'].empty:
                    st.markdown("#### Failed Records")
                    st.dataframe(child_res['failed_records'], use_container_width=True)
                    
                    csv = child_res['failed_records'].to_csv(index=False)
                    st.download_button(
                        label=f"⬇️ Download Failed {child_obj} Records",
                        data=csv,
                        file_name=f"failed_{child_obj}_records.csv",
                        mime="text/csv"
                    )
