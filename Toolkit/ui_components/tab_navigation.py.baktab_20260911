"""
Tab Navigation Helper - Provides Next button functionality for tab navigation.
Uses JS injection via streamlit.components.v1.html to click native Streamlit tabs.
"""

import streamlit as st
import streamlit.components.v1 as components


def add_next_tab_button(next_tab_label, key_suffix=""):
    """
    Add a styled Next button at bottom-right that navigates to the next Streamlit tab
    by programmatically clicking the native tab header via JavaScript.
    
    Args:
        next_tab_label (str): The label text of the next tab to navigate to (partial match ok).
        key_suffix (str): Optional suffix for uniqueness.
    """
    escaped = next_tab_label.replace("'", "\\'").replace('"', '\\"')
    
    components.html(f"""
    <div style="display: flex; justify-content: flex-end; padding: 10px 0;">
        <button onclick="
            var tabs = window.parent.document.querySelectorAll('button[data-baseweb=\\'tab\\']');
            for (var i = 0; i < tabs.length; i++) {{
                if (tabs[i].innerText.includes('{escaped}')) {{
                    tabs[i].click();
                    break;
                }}
            }}
        " style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.55rem 1.4rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.88rem;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
            transition: all 0.3s ease;
        "
        onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(102,126,234,0.5)'"
        onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(102,126,234,0.3)'"
        >
            Next &#10145;&#65039;
        </button>
    </div>
    """, height=60)


def add_next_session_button(next_tab_index, session_key, next_tab_label=""):
    """
    Add a Next button for custom-button-based tabs (like data_operations).
    Uses st.button + session state to switch tab.
    """
    col1, col2 = st.columns([0.85, 0.15])
    with col2:
        if st.button("Next ➡️", key=f"next_session_{session_key}_{next_tab_index}", use_container_width=True):
            st.session_state[session_key] = next_tab_index
            st.rerun()
