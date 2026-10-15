"""
Style utilities for consistent UI appearance across DM Toolkit
"""
import streamlit as st

def apply_custom_css():
    """Apply custom CSS for consistent styling"""
    st.markdown("""
    <style>
    /* Clean section headers */
    .section-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .status-success {
        background-color: #d4edda;
        color: #155724;
    }
    
    .status-warning {
        background-color: #fff3cd;
        color: #856404;
    }
    
    .status-error {
        background-color: #f8d7da;
        color: #721c24;
    }
    
    /* Clean info boxes */
    .info-box {
        background-color: #f8f9fa;
        border-left: 4px solid #667eea;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
    }
    
    /* Button improvements */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: #f8f9fa;
        border-radius: 6px;
        color: #495057;
        font-weight: 500;
        border: 1px solid #e9ecef;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: 1px solid #667eea !important;
    }
    
    /* Sidebar improvements */
    .css-1d391kg {
        background-color: #f8f9fa;
    }
    
    /* Remove excessive padding */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 1200px;
    }
    
    /* Compact metrics */
    [data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

def create_section_header(title: str, icon: str = ""):
    """Create a consistent section header"""
    return f'<div class="section-header">{icon} {title}</div>'

def create_status_badge(text: str, status: str = "success"):
    """Create a status badge"""
    return f'<span class="status-badge status-{status}">{text}</span>'

def create_info_box(content: str):
    """Create an info box"""
    return f'<div class="info-box">{content}</div>'

def show_loading_spinner(text: str = "Loading..."):
    """Show a loading spinner with text"""
    return st.spinner(text)

def success_message(message: str):
    """Show a success message with consistent styling"""
    st.success(f"✅ {message}")

def error_message(message: str):
    """Show an error message with consistent styling"""
    st.error(f"❌ {message}")

def warning_message(message: str):
    """Show a warning message with consistent styling"""
    st.warning(f"⚠️ {message}")

def info_message(message: str):
    """Show an info message with consistent styling"""
    st.info(f"ℹ️ {message}")