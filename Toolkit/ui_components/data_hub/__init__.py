"""
Data Hub Module
===============
Centralized data management for DM Toolkit

Provides unified data retrieval and caching from:
- File uploads (CSV, Excel)
- Salesforce SOQL queries
- Cached datasets

Usage:
    from ui_components.data_hub import DataHub, initialize_data_hub
    
    # Initialize in main app
    data_hub = initialize_data_hub()
    
    # Use in modules
    if 'active_dataset' in st.session_state:
        df = st.session_state['active_dataset']['df']
"""

from .data_hub import DataHub
from .data_hub_ui import show_data_hub_interface, get_active_dataset, get_active_dataset_info, has_active_dataset
from .integration import get_data_from_hub, get_data_info, has_data, show_data_source_info, validate_data_available, get_data_summary, get_all_datasets, get_dataset_by_id, select_dataset_from_hub

__all__ = [
    'DataHub',
    'show_data_hub_interface',
    'get_active_dataset',
    'get_active_dataset_info',
    'has_active_dataset',
    'get_data_from_hub',
    'get_data_info',
    'has_data',
    'show_data_source_info',
    'validate_data_available',
    'get_data_summary',
    'get_all_datasets',
    'get_dataset_by_id',
    'select_dataset_from_hub',
    'initialize_data_hub'
]


def initialize_data_hub():
    """Initialize Data Hub in session state"""
    import streamlit as st
    
    if 'data_hub' not in st.session_state:
        st.session_state.data_hub = DataHub()
    
    return st.session_state.data_hub
