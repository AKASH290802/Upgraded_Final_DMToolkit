import streamlit as st
import sys
import os
import json
import pandas as pd
from pathlib import Path
from PIL import Image

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Import UI modules
from ui_components import (
    data_operations, 
    mapping_operations, 
    validation_operations, 
    unit_testing_operations,
    config_management,
    dashboard_overview,
    logs_reports,
    org_migration,
    object_comparison
)
from ui_components import migration_readiness_ui
from ui_components import multi_data_file_ui
from ui_components import step1_data_loading
from ui_components import navigation
from ui_components import page_backgrounds
from ui_components import theme
from ui_components.navigation import STEP1_PAGE, STEP2_PAGE, STEP3_PAGE, STEP4_PAGE
from ui_components.connection_manager import (
    ORG_PLACEHOLDER, SOURCE_PLACEHOLDER,
    apply_pending_connection_changes, classify_credentials, clear_salesforce_metadata_cache,
    credentials_path, current_source_key, display_name, get_sf_connection, get_sf_connection_error,
    retry_sf_connection, set_current_org, set_current_source_connection, source_connections, source_label,
)
from ui_components.data_hub import show_data_hub_interface, initialize_data_hub
from ui_components.file_library_ui import show_file_library
from ui_components import large_data

# Big tables show at most large_data.DISPLAY_ROW_CAP rows (the browser message limit).
large_data.install_dataframe_cap()

# Page configuration
st.set_page_config(
    page_title="DM Toolkit - Data Migration & Validation",
    page_icon=theme.BRAND_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles are applied per run in main() (ui_components/theme.py).

def create_tavant_logo():
    """Create TAVANT logo if it doesn't exist"""
    logo_path = os.path.join(project_root, 'assets', 'tavant_logo.png')
    
    if not os.path.exists(logo_path):
        try:
            # Create logo image
            logo = Image.new('RGB', (160, 160), color='#17a697')
            
            # Add rounded corners
            from PIL import ImageDraw
            draw = ImageDraw.Draw(logo)
            
            # Create a rounded rectangle logo
            radius = 20
            draw.rounded_rectangle([(0, 0), (160, 160)], radius=radius, fill='#17a697')
            
            # Add white TAVANT text
            try:
                from PIL import ImageFont
                # Try to use a nice font
                font_size = 32
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                # Fallback to default
                font = ImageFont.load_default()
            
            # Calculate text position (center)
            text = "TAVANT"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (160 - text_width) // 2
            y = (160 - text_height) // 2
            
            draw.text((x, y), text, fill='white', font=font)
            
            # Save logo
            logo.save(logo_path)
            return logo_path
        except Exception as e:
            return None
    
    return logo_path

def initialize_session_state():
    """Initialize session state variables"""
    if 'current_org' not in st.session_state:
        st.session_state.current_org = None
    if 'current_sql_connection' not in st.session_state:
        st.session_state.current_sql_connection = None
    if 'current_object' not in st.session_state:
        st.session_state.current_object = None
    if 'sf_connection' not in st.session_state:
        st.session_state.sf_connection = None
    if 'sql_connection' not in st.session_state:
        st.session_state.sql_connection = None
    if 'connected_org' not in st.session_state:
        st.session_state.connected_org = None
    if 'connected_sql' not in st.session_state:
        st.session_state.connected_sql = None
    if 'available_orgs' not in st.session_state:
        st.session_state.available_orgs = []
    if 'available_sql_connections' not in st.session_state:
        st.session_state.available_sql_connections = []
    if 'current_oracle_connection' not in st.session_state:
        st.session_state.current_oracle_connection = None
    if 'current_source_connection' not in st.session_state:
        st.session_state.current_source_connection = None
    if 'available_oracle_connections' not in st.session_state:
        st.session_state.available_oracle_connections = []
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}
    if 'active_page' not in st.session_state:
        st.session_state.active_page = "🏠 Dashboard"

def load_credentials():
    """Load credentials from linkedservices.json"""
    try:
        creds_path = credentials_path()
        if os.path.exists(creds_path):
            with open(creds_path, 'r') as f:
                creds = json.load(f)

            # Split entries by type (Salesforce orgs, SQL Server, Oracle, ...)
            groups = classify_credentials(creds)

            # Update session state
            st.session_state.available_orgs = list(groups['salesforce'].keys())
            st.session_state.available_sql_connections = list(groups['sqlserver'].keys())
            st.session_state.available_oracle_connections = list(groups['oracle'].keys())

            return creds
        else:
            st.error("Credentials file not found. Please ensure linkedservices.json exists in the Services folder.")
            return {}
    except Exception as e:
        st.error(f"Error loading credentials: {str(e)}")
        return {}

def main():
    """Main application function"""
    
    # Initialize session state
    initialize_session_state()
    
    # Load credentials and store in session state for dynamic updates
    credentials = load_credentials()
    st.session_state.credentials = credentials  # Store for config management updates
    
    # Create or get TAVANT logo
    logo_path = create_tavant_logo()
    
    # Tavant styles + hero header
    theme.apply_theme()
    theme.render_header()

    
    # Sidebar navigation
    with st.sidebar:
        # Connection changes requested by a screen are applied before any
        # sidebar widget is drawn, so the sidebar always shows what is in use.
        apply_pending_connection_changes()

        theme.render_sidebar_brand()
        _render_connection_settings()
        current_page = navigation.render_navigation_radio()

        # Background art for this screen (toggle at the bottom of the sidebar).
        st.divider()
        page_backgrounds.render_page_background(current_page)
        theme.mount_theme_watcher()

    # Use session state credentials (may be updated by config management)
    current_credentials = st.session_state.get('credentials', credentials)
    
    # Initialize Data Hub
    data_hub = initialize_data_hub()
    
    if current_page == "🏠 Dashboard":
        dashboard_overview.show_dashboard(current_credentials)
    elif current_page == "⚙️ Configuration":
        config_management.show_configuration(current_credentials)
    elif current_page == STEP1_PAGE:
        step1_data_loading.show_data_loading_step(current_credentials)
    elif current_page == STEP2_PAGE:
        validation_operations.show_validation_operations(current_credentials)
    elif current_page == STEP3_PAGE:
        data_operations.show_data_operations(current_credentials)
    elif current_page == STEP4_PAGE:
        unit_testing_operations.show_unit_testing(current_credentials)
    elif current_page == "📊 Data Hub":
        sf_conn = get_sf_connection(credentials=current_credentials) if st.session_state.current_org else None
        show_data_hub_interface(sf_conn)
    elif current_page == "📁 File Library":
        show_file_library()
    elif current_page == "🎯 Migration Readiness":
        migration_readiness_ui.show_migration_readiness(current_credentials)
    elif current_page == "🧩 Multi Data File":
        multi_data_file_ui.show_multi_data_file(current_credentials)
    elif current_page == "🗺️ Mapping":
        mapping_operations.show_mapping_operations(current_credentials)
    elif current_page == "🔄 Org Migration":
        org_migration.show_org_migration(current_credentials)
    elif current_page == "🔍 Object Comparison":
        object_comparison.show_object_comparison()
    elif current_page == "📋 Logs & Reports":
        logs_reports.show_logs_reports()


def _on_org_selected():
    value = st.session_state.global_org_selector
    set_current_org(None if value == ORG_PLACEHOLDER else value)


def _on_source_selected():
    value = st.session_state.global_source_selector
    set_current_source_connection(None if value == SOURCE_PLACEHOLDER else value)


def _sync_selector(widget_key: str, current_key: str, options: list, placeholder: str, setter) -> None:
    """Keep a sidebar selectbox showing the connection that is actually in use."""
    current = st.session_state.get(current_key)
    if current and current not in options:
        setter(None)  # removed from Configuration
        current = None
    wanted = current or placeholder
    if st.session_state.get(widget_key) != wanted:
        st.session_state[widget_key] = wanted


def _render_connection_settings():
    """Sidebar status + the ONE place where the org and the source connection are chosen."""
    ss = st.session_state
    orgs = ss.available_orgs or []
    sources = list(source_connections())

    _sync_selector('global_org_selector', 'current_org', orgs, ORG_PLACEHOLDER, set_current_org)
    # One source picker (SQL Server, Oracle, Snowflake, PostgreSQL); a deleted source is dropped.
    current_source = current_source_key()
    if current_source and current_source not in sources:
        set_current_source_connection(None)
        current_source = None
    if ss.get('global_source_selector') != (current_source or SOURCE_PLACEHOLDER):
        ss['global_source_selector'] = current_source or SOURCE_PLACEHOLDER

    # Connect the sidebar org once here; every screen then reuses this connection.
    sf_conn = get_sf_connection(quiet=True) if ss.current_org else None
    login_error = get_sf_connection_error() if ss.current_org and sf_conn is None else None

    if sf_conn is not None:
        state, status = 'ok', "Connected"
    elif ss.current_org:
        state, status = 'bad', "Not connected"
    else:
        state, status = 'none', "No org selected"

    # One card at the top of the sidebar: status, the pickers every screen uses, the current object.
    with st.container(key="dm_connection_card"):
        st.markdown(theme.connection_status_html(state, status), unsafe_allow_html=True)
        if orgs:
            st.selectbox("🏢 Salesforce org", [ORG_PLACEHOLDER] + orgs, key="global_org_selector",
                         on_change=_on_org_selected,
                         help="The Salesforce organization every screen works with")
        else:
            st.error("❌ No organizations found in credentials")

        if sources:
            st.selectbox("🔌 Source connection", [SOURCE_PLACEHOLDER] + sources, key="global_source_selector",
                         on_change=_on_source_selected, format_func=source_label,
                         help="Where source data is read from (and SQL loads are written to) on every screen: "
                              "any saved SQL Server, Oracle, Snowflake or PostgreSQL connection")
        else:
            st.caption("🔌 No source connection saved — add one in ⚙️ Configuration → Source Connections.")

        st.markdown(theme.connection_object_html(ss.current_object), unsafe_allow_html=True)
        if ss.current_org:
            from ui_components.projects import project_for_org
            project = project_for_org(ss.current_org)
            st.markdown(theme.connection_project_html(project['name'] if project else None),
                        unsafe_allow_html=True)

        if state == 'bad':
            st.error(f"❌ {login_error}" if login_error else "🔌 Not connected")
            if st.button("🔁 Retry connection", key="retry_sf_connection_status", use_container_width=True,
                         help="Log in to the selected org again"):
                retry_sf_connection()
                st.rerun()

        if st.button("🔄 Refresh", help="Reload the connection list and Salesforce object metadata",
                     key="refresh_connections", use_container_width=True):
            clear_salesforce_metadata_cache()
            st.rerun()

if __name__ == "__main__":
    main()