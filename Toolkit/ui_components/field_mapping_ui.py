"""
UI Components for Field Mapping Management
Provides Streamlit UI components for saving/loading field mappings
"""

import streamlit as st
from typing import Dict, Optional, Tuple
from ui_components.field_mapping_manager import (
    save_field_mapping,
    load_field_mapping,
    list_saved_mappings,
    delete_field_mapping,
    check_mapping_exists,
    display_mapping_info
)


def show_mapping_save_options(org_name: str, object_name: str, field_mappings: Dict[str, str],
                              csv_columns: list, validation_type: str = "schema") -> bool:
    """
    Display save options for field mappings in the UI
    
    Args:
        org_name: Salesforce organization name
        object_name: Salesforce object name
        field_mappings: Dictionary of CSV column -> Salesforce field mappings
        csv_columns: List of CSV columns
        validation_type: Type of validation
    
    Returns:
        True if saved, False otherwise
    """
    st.markdown("---")
    st.markdown("### 💾 **Save Field Mappings**")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info("💡 Save these field mappings to reuse them in future validations for this object")
    
    with col2:
        if st.button("💾 Save Mappings", type="primary", help="Save these mappings for future use", 
                    key=f"save_mapping_{org_name}_{object_name}_{validation_type}"):
            success, message = save_field_mapping(
                org_name=org_name,
                object_name=object_name,
                field_mappings=field_mappings,
                csv_columns=csv_columns,
                validation_type=validation_type
            )
            
            if success:
                st.success(message)
                return True
            else:
                st.error(message)
                return False
    
    return False


def show_mapping_load_options(org_name: str, object_name: str, 
                              available_fields: list) -> Optional[Dict[str, str]]:
    """
    Display load options for previously saved field mappings
    
    Args:
        org_name: Salesforce organization name
        object_name: Salesforce object name
        available_fields: List of available Salesforce fields
    
    Returns:
        Dictionary of loaded mappings or None
    """
    st.markdown("---")
    st.markdown("### 📂 **Load Previous Mappings**")
    
    # Check if mappings exist for this object
    if check_mapping_exists(org_name, object_name):
        col1, col2 = st.columns(2)
        
        with col1:
            st.success(f"✅ Saved mappings found for {object_name}")
        
        with col2:
            if st.button("📥 Load Saved Mappings", help="Load previously saved field mappings",
                        key=f"load_mapping_{org_name}_{object_name}"):
                mapping_data, success, message = load_field_mapping(org_name, object_name)
                
                if success and mapping_data:
                    st.info(message)
                    
                    # Show mapping details
                    with st.expander("View Saved Mapping Details"):
                        st.markdown(display_mapping_info(mapping_data))
                    
                    return mapping_data.get('field_mappings', {})
                else:
                    st.error(message)
    
    return None


def show_managed_mappings(org_name: str):
    """
    Display interface to manage all saved mappings for an organization
    
    Args:
        org_name: Salesforce organization name
    """
    st.markdown("---")
    st.markdown("### 📋 **Manage Saved Field Mappings**")
    
    saved_mappings = list_saved_mappings(org_name)
    
    if not saved_mappings:
        st.info(f"No saved field mappings found for {org_name}")
        return
    
    # Create a summary table
    st.markdown(f"**Found {len(saved_mappings)} saved mapping(s):**")
    
    for idx, mapping in enumerate(saved_mappings):
        with st.expander(f"📌 {mapping['object_name']} ({mapping['mapping_count']} fields) - {mapping['validation_type']}", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**Object:** {mapping['object_name']}")
                st.write(f"**Fields:** {mapping['mapping_count']}")
            
            with col2:
                st.write(f"**Type:** {mapping['validation_type']}")
                st.write(f"**Saved:** {mapping['saved_at']}")
            
            with col3:
                # Load full mapping details
                mapping_data, _, _ = load_field_mapping(org_name, mapping['object_name'])
                
                if mapping_data:
                    st.markdown("**Field Mappings:**")
                    field_mappings = mapping_data.get('field_mappings', {})
                    
                    mapping_text = "\n".join([
                        f"• {csv_col} → {sf_field}"
                        for csv_col, sf_field in field_mappings.items()
                    ])
                    st.code(mapping_text)
            
            # Delete option
            if st.button(f"🗑️ Delete mapping for {mapping['object_name']}", key=f"delete_{idx}"):
                success, message = delete_field_mapping(org_name, mapping['object_name'])
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def auto_load_mapping(org_name: str, object_name: str, 
                      csv_columns: list, auto_apply: bool = False,
                      key_suffix: str = '') -> Optional[Dict[str, str]]:
    """
    Automatically check for and load saved mappings for an object
    Shows UI to apply saved mappings or create new ones
    
    Args:
        org_name: Salesforce organization name
        object_name: Salesforce object name
        csv_columns: List of CSV columns
        auto_apply: Whether to automatically apply saved mappings without asking
        key_suffix: Extra string appended to Streamlit widget keys to avoid
                    duplicate-key errors when this function is called from
                    multiple places in the same page render.
    
    Returns:
        Dictionary of field mappings or None
    """
    if not check_mapping_exists(org_name, object_name):
        return None
    
    mapping_data, success, _ = load_field_mapping(org_name, object_name)
    
    if not success or not mapping_data:
        return None
    
    field_mappings = mapping_data.get('field_mappings', {})
    
    # Check if saved mappings match current CSV columns
    saved_columns = set(field_mappings.keys())
    current_columns = set(csv_columns)
    
    if saved_columns == current_columns:
        # Perfect match - columns are identical
        if auto_apply:
            return field_mappings
        
        st.info("✅ Found matching saved field mappings for this object")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Use Saved Mappings", type="primary", 
                        key=f"use_saved_mappings_{org_name}_{object_name}{key_suffix}"):
                st.session_state.use_saved_mappings = True
                return field_mappings
        
        with col2:
            if st.button("🔄 Create New Mappings",
                        key=f"create_new_mappings_{org_name}_{object_name}{key_suffix}"):
                st.session_state.use_saved_mappings = False
                return None
    
    elif saved_columns < current_columns:
        # Saved mappings are a subset of current columns
        missing = current_columns - saved_columns
        st.warning(f"⚠️ Saved mappings found but missing columns: {missing}")
        st.info("These columns were not in the previous mapping. You can map them now or use partial saved mappings.")
        
        if st.button("📥 Partially Apply Saved Mappings",
                    key=f"partial_apply_mappings_{org_name}_{object_name}{key_suffix}"):
            return field_mappings
    
    else:
        # Saved mappings have extra columns that don't exist now
        extra = saved_columns - current_columns
        st.info(f"💡 Previous mapping had extra columns that no longer exist: {extra}")
    
    return None
