"""
Data Hub Integration Helpers
=============================
Utility functions for other modules to use Data Hub
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any


def get_all_datasets() -> list:
    """
    Get list of all datasets in Data Hub.
    
    Returns:
        List of dicts with 'id', 'name', 'is_active', 'metadata' keys.
        Empty list if no datasets.
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.list_datasets()
    return []


def get_dataset_by_id(dataset_id: str) -> Optional[pd.DataFrame]:
    """
    Get a specific dataset DataFrame by its ID.
    
    Args:
        dataset_id: UUID of the dataset
    
    Returns:
        DataFrame or None
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_dataset(dataset_id)
    return None


def select_dataset_from_hub(key: str) -> Optional[pd.DataFrame]:
    """
    Show a dropdown of all Data Hub datasets and return the selected DataFrame.
    
    If only one dataset exists, it is auto-selected (no dropdown shown).
    
    Args:
        key: Unique Streamlit widget key prefix for this selector
    
    Returns:
        DataFrame of the selected dataset, or None if nothing selected/available
    """
    datasets = get_all_datasets()
    if not datasets:
        st.info("💡 No datasets in Data Hub yet. Load your data in **1️⃣ Source/Target Information** "
                "(or the 📊 Data Hub page → Load Data) first.")
        return None

    if len(datasets) == 1:
        ds = datasets[0]
        meta = ds['metadata']
        st.success(f"📊 Data Hub dataset: **{ds['name']}** ({meta['row_count']} rows, {meta['column_count']} columns)")
        return get_dataset_by_id(ds['id'])

    # Multiple datasets — show a selectbox
    display_names = []
    id_map = {}
    for ds in datasets:
        meta = ds['metadata']
        label = f"{ds['name']}  ({meta['row_count']} rows, {meta['column_count']} cols)"
        if ds['is_active']:
            label += "  ★ active"
        display_names.append(label)
        id_map[label] = ds['id']

    # Default to the active dataset
    default_idx = 0
    for i, ds in enumerate(datasets):
        if ds['is_active']:
            default_idx = i
            break

    selected_label = st.selectbox(
        "📊 Select dataset from Data Hub:",
        options=display_names,
        index=default_idx,
        key=f"hub_dataset_select_{key}"
    )

    if selected_label:
        selected_id = id_map[selected_label]
        return get_dataset_by_id(selected_id)

    return None


def get_data_from_hub() -> Optional[pd.DataFrame]:
    """
    Get active dataset from Data Hub
    
    Use in any module that needs data:
    
    Usage:
        from ui_components.data_hub.integration import get_data_from_hub
        
        df = get_data_from_hub()
        if df is not None:
            # Use data
            st.dataframe(df)
        else:
            st.warning("Please load data in 1️⃣ Source/Target Information first")
    
    Returns:
        DataFrame or None if no active dataset
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_active_dataset()
    return None


def get_data_info() -> Optional[Dict[str, Any]]:
    """
    Get info about active dataset
    
    Returns:
        Dict with 'name' and 'metadata' keys, or None
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.get_active_dataset_info()
    return None


def has_data() -> bool:
    """
    Check if active dataset exists
    
    Usage:
        from ui_components.data_hub.integration import has_data
        
        if has_data():
            # User has loaded data
            df = get_data_from_hub()
        else:
            st.info("Please load data in 1️⃣ Source/Target Information first")
    
    Returns:
        True if active dataset exists, False otherwise
    """
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.has_active_dataset()
    return False


def show_data_source_info():
    """
    Display active dataset source information
    
    Call this in your module's UI to show user what data they're working with
    
    Usage:
        from ui_components.data_hub.integration import show_data_source_info
        
        st.subheader("Data Configuration")
        show_data_source_info()
    """
    data_info = get_data_info()
    
    if data_info is None:
        st.warning("⚠️ No active dataset selected. Please load data in 1️⃣ Source/Target Information first.")
        st.info("💡 Go to **1️⃣ Source/Target Information** to upload a file or query Salesforce, SQL Server or Oracle.")
        return False
    
    # Display data source info
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 Dataset", data_info['name'])
    with col2:
        st.metric("📦 Rows", data_info['metadata']['row_count'])
    with col3:
        st.metric("📋 Columns", data_info['metadata']['column_count'])
    
    # Show source details
    st.caption(f"Source: {data_info['metadata']['source_type'].replace('_', ' ').title()}")
    
    return True


def validate_data_available(module_name: str) -> bool:
    """
    Validate that data is available and show helpful message if not
    
    Usage:
        from ui_components.data_hub.integration import validate_data_available
        
        if not validate_data_available("Enhanced Validation"):
            st.stop()
        
        # Now proceed with processing
        df = get_data_from_hub()
    
    Args:
        module_name: Name of the module using this check (e.g., "Enhanced Validation")
    
    Returns:
        True if data is available, False otherwise
    """
    if not has_data():
        st.error(f"❌ {module_name} requires data to be loaded")
        st.info("""
        **Steps to use this module:**
        1. Go to **1️⃣ Source/Target Information** (sidebar)
        2. Load data from any source:
           - **Upload File** (CSV, PSV or Excel) or the **File Library**
           - **Salesforce** (SOQL), **SQL Server** or **Oracle** — using the sidebar connections
        3. Confirm the dataset, then return to this module
        """)
        return False
    
    return True


def get_data_summary() -> str:
    """
    Get a summary string of the active dataset
    
    Usage:
        summary = get_data_summary()
        st.write(f"Working with: {summary}")
    
    Returns:
        Summary string like "Dataset_Name (251 rows, 36 columns, loaded at 10:30)"
    """
    data_info = get_data_info()
    
    if data_info is None:
        return "No active dataset"
    
    from datetime import datetime
    name = data_info['name']
    rows = data_info['metadata']['row_count']
    cols = data_info['metadata']['column_count']
    timestamp = datetime.fromisoformat(data_info['metadata']['timestamp'])
    time_str = timestamp.strftime("%H:%M:%S")
    
    return f"{name} ({rows} rows, {cols} columns, loaded at {time_str})"
