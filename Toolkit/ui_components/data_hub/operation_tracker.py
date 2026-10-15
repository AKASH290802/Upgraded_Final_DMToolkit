"""
Operation Tracker Integration
==============================
Enhances data loading with automatic operation tracking
"""

import pandas as pd
import streamlit as st
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


def track_file_upload(
    uploaded_file,
    source_org: Optional[str] = None,
    target_org: Optional[str] = None,
    object_name: Optional[str] = None,
    validation_status: Optional[str] = None,
    validation_passed: int = 0,
    validation_failed: int = 0
) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Load file and automatically track operation
    
    Args:
        uploaded_file: Streamlit UploadedFile
        source_org: Source org (if applicable)
        target_org: Target org
        object_name: Salesforce object name
        validation_status: "PASSED" / "FAILED" / "PARTIAL"
        validation_passed: Records that passed validation
        validation_failed: Records that failed validation
    
    Returns:
        Tuple of (DataFrame, operation_id) or (None, error_message)
    """
    try:
        from ui_components.data_hub.data_source_handler import load_from_file
        from ui_components.data_hub.operation_manager import get_operation_manager
        
        # Load the file
        df, error_msg = load_from_file(uploaded_file)
        
        if df is None:
            return None, error_msg
        
        # Track the operation
        op_manager = get_operation_manager()
        
        operation_id = op_manager.create_operation(
            operation_type="File_Upload",
            object_name=object_name or "Unknown",
            record_count=len(df),
            data=df,
            source_org=source_org,
            target_org=target_org,
            file_name=uploaded_file.name,
            validation_status=validation_status,
            validation_passed=validation_passed,
            validation_failed=validation_failed,
            created_by=st.session_state.get("current_user", "Unknown")
        )
        
        logger.info(f"Tracked file upload: {operation_id}")
        return df, operation_id
    
    except Exception as e:
        logger.error(f"Error tracking file upload: {str(e)}")
        return None, str(e)


def track_soql_query(
    sf_connection,
    query: str,
    source_org: str,
    object_name: str,
    validation_status: Optional[str] = None,
    validation_passed: int = 0,
    validation_failed: int = 0
) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Execute SOQL query and automatically track operation
    
    Args:
        sf_connection: Salesforce connection object
        query: SOQL query string
        source_org: Organization name
        object_name: Salesforce object name
        validation_status: Validation result
        validation_passed: Records that passed validation
        validation_failed: Records that failed validation
    
    Returns:
        Tuple of (DataFrame, operation_id) or (None, error_message)
    """
    try:
        from ui_components.data_hub.operation_manager import get_operation_manager
        
        # Execute query
        result = sf_connection.query(query)
        records = result.get('records', [])
        
        # Remove sObject metadata
        for record in records:
            record.pop('attributes', None)
        
        df = pd.DataFrame(records)
        
        # Track the operation
        op_manager = get_operation_manager()
        
        operation_id = op_manager.create_operation(
            operation_type="SOQL_Query",
            object_name=object_name,
            record_count=len(df),
            data=df,
            source_org=source_org,
            query=query,
            validation_status=validation_status,
            validation_passed=validation_passed,
            validation_failed=validation_failed,
            created_by=st.session_state.get("current_user", "Unknown")
        )
        
        logger.info(f"Tracked SOQL query: {operation_id}")
        return df, operation_id
    
    except Exception as e:
        logger.error(f"Error tracking SOQL query: {str(e)}")
        return None, str(e)


def track_data_load(
    data: pd.DataFrame,
    target_org: str,
    object_name: str,
    successful_records: int,
    failed_records: int,
    load_method: str = "API"
) -> str:
    """
    Track a data load operation to target org
    
    Args:
        data: DataFrame loaded
        target_org: Target organization name
        object_name: Object loaded to
        successful_records: Number successfully inserted
        failed_records: Number that failed
        load_method: "API" / "Bulk_API" / "Data_Loader"
    
    Returns:
        operation_id
    """
    try:
        from ui_components.data_hub.operation_manager import get_operation_manager
        
        op_manager = get_operation_manager()
        
        # Determine validation status
        if failed_records == 0:
            validation_status = "PASSED"
        elif successful_records == 0:
            validation_status = "FAILED"
        else:
            validation_status = "PARTIAL"
        
        operation_id = op_manager.create_operation(
            operation_type="Data_Load",
            object_name=object_name,
            record_count=len(data),
            data=data,
            target_org=target_org,
            validation_status=validation_status,
            validation_passed=successful_records,
            validation_failed=failed_records,
            notes=f"Load method: {load_method}",
            created_by=st.session_state.get("current_user", "Unknown")
        )
        
        logger.info(f"Tracked data load: {operation_id}")
        return operation_id
    
    except Exception as e:
        logger.error(f"Error tracking data load: {str(e)}")
        return None


def get_last_operation_data(object_name: str) -> Optional[pd.DataFrame]:
    """
    Get the last operation data for a specific object
    
    Useful for "Resume from last operation" functionality
    
    Args:
        object_name: Salesforce object name
    
    Returns:
        DataFrame or None if no operations found
    """
    try:
        from ui_components.data_hub.operation_manager import get_operation_manager
        
        op_manager = get_operation_manager()
        
        # Get history filtered by object
        history = op_manager.get_operation_history(object_filter=object_name)
        
        if not history:
            return None
        
        # Get the most recent operation
        latest_op = history[0]
        
        data, _ = op_manager.retrieve_operation_data(latest_op['operation_id'])
        return data
    
    except Exception as e:
        logger.error(f"Error getting last operation data: {str(e)}")
        return None


def track_validation_check(
    data: pd.DataFrame,
    object_name: str,
    source_org: str,
    validation_type: str,
    total_records: int,
    passed_records: int,
    failed_records: int,
    validation_details: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Track a validation check operation (Business Rules or Data Quality)
    
    Args:
        data: DataFrame being validated
        object_name: Salesforce object name
        source_org: Organization where data resides
        validation_type: "Business_Rules" / "Data_Quality" / "Schema"
        total_records: Total records checked
        passed_records: Records that passed validation
        failed_records: Records that failed validation
        validation_details: Dict with additional validation info
    
    Returns:
        operation_id
    """
    try:
        from ui_components.data_hub.operation_manager import get_operation_manager
        
        op_manager = get_operation_manager()
        
        # Determine validation status
        if failed_records == 0:
            validation_status = "PASSED"
        elif passed_records == 0:
            validation_status = "FAILED"
        else:
            validation_status = "PARTIAL"
        
        operation_id = op_manager.create_operation(
            operation_type=f"Validation_Check_{validation_type}",
            object_name=object_name,
            record_count=total_records,
            data=data,
            source_org=source_org,
            validation_status=validation_status,
            validation_passed=passed_records,
            validation_failed=failed_records,
            notes=f"Validation Type: {validation_type}. Details: {validation_details or {}}",
            created_by=st.session_state.get("current_user", "Unknown")
        )
        
        logger.info(f"Tracked {validation_type} validation: {operation_id}")
        return operation_id
    
    except Exception as e:
        logger.error(f"Error tracking validation check: {str(e)}")
        return None


def track_migration_execution(
    source_org: str,
    target_org: str,
    object_name: str,
    total_records: int,
    successful_records: int,
    failed_records: int,
    migration_details: Optional[Dict[str, Any]] = None,
    data: Optional[pd.DataFrame] = None
) -> Optional[str]:
    """
    Track a migration execution from source to target org
    
    Args:
        source_org: Source organization
        target_org: Target organization
        object_name: Salesforce object being migrated
        total_records: Total records migrated
        successful_records: Records successfully migrated
        failed_records: Records that failed migration
        migration_details: Dict with mapping strategy, field mappings, etc.
        data: DataFrame of migrated data
    
    Returns:
        operation_id
    """
    try:
        from ui_components.data_hub.operation_manager import get_operation_manager
        
        op_manager = get_operation_manager()
        
        # Determine validation status
        if failed_records == 0:
            validation_status = "PASSED"
        elif successful_records == 0:
            validation_status = "FAILED"
        else:
            validation_status = "PARTIAL"
        
        operation_id = op_manager.create_operation(
            operation_type="Migration_Execute",
            object_name=object_name,
            record_count=total_records,
            data=data,
            source_org=source_org,
            target_org=target_org,
            validation_status=validation_status,
            validation_passed=successful_records,
            validation_failed=failed_records,
            notes=f"Migration from {source_org} to {target_org}. Details: {migration_details or {}}",
            created_by=st.session_state.get("current_user", "Unknown")
        )
        
        logger.info(f"Tracked migration execution: {operation_id}")
        return operation_id
    
    except Exception as e:
        logger.error(f"Error tracking migration execution: {str(e)}")
        return None


def track_lookup_resolution(
    source_org: str,
    target_org: str,
    object_name: str,
    total_lookups: int,
    resolved_lookups: int,
    unresolved_lookups: int,
    lookup_details: Optional[Dict[str, Any]] = None,
    data: Optional[pd.DataFrame] = None
) -> Optional[str]:
    """
    Track lookup resolution operation during data integration
    
    Args:
        source_org: Source organization
        target_org: Target organization
        object_name: Object with lookups being resolved
        total_lookups: Total lookup references
        resolved_lookups: Successfully resolved
        unresolved_lookups: Could not be resolved
        lookup_details: Fields resolved, resolution strategy, etc.
        data: DataFrame with lookup data
    
    Returns:
        operation_id
    """
    try:
        from ui_components.data_hub.operation_manager import get_operation_manager
        
        op_manager = get_operation_manager()
        
        # Determine validation status
        if unresolved_lookups == 0:
            validation_status = "PASSED"
        elif resolved_lookups == 0:
            validation_status = "FAILED"
        else:
            validation_status = "PARTIAL"
        
        operation_id = op_manager.create_operation(
            operation_type="Lookup_Resolution",
            object_name=object_name,
            record_count=total_lookups,
            data=data,
            source_org=source_org,
            target_org=target_org,
            validation_status=validation_status,
            validation_passed=resolved_lookups,
            validation_failed=unresolved_lookups,
            notes=f"Lookup Resolution Details: {lookup_details or {}}",
            created_by=st.session_state.get("current_user", "Unknown")
        )
        
        logger.info(f"Tracked lookup resolution: {operation_id}")
        return operation_id
    
    except Exception as e:
        logger.error(f"Error tracking lookup resolution: {str(e)}")
        return None


def display_operation_summary(operation_id: str):
    """Display a summary of an operation in Streamlit"""
    try:
        from ui_components.data_hub.operation_manager import get_operation_manager
        
        op_manager = get_operation_manager()
        data, operation = op_manager.retrieve_operation_data(operation_id)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Records", operation['record_count'])
        with col2:
            st.metric("Validation", operation.get('validation_status', '-'))
        with col3:
            st.metric("Passed", operation.get('validation_passed', 0))
        with col4:
            st.metric("Failed", operation.get('validation_failed', 0))
        
        st.caption(f"Operation: {operation_id}")
        st.caption(f"Timestamp: {operation['timestamp']}")
    
    except Exception as e:
        st.error(f"Could not display operation summary: {str(e)}")
