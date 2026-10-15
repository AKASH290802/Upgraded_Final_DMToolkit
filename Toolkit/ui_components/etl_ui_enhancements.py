#!/usr/bin/env python3
"""
Enhanced UI Components for Advanced ETL Processing
Provides visual enhancements and interactive components
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Optional, Any
import time

class ETLUIEnhancements:
    """
    Enhanced UI components for the ETL processing system
    """
    
    def __init__(self):
        self.setup_custom_css()
    
    def setup_custom_css(self):
        """Add custom CSS for better ETL UI appearance"""
        st.markdown("""
        <style>
        /* ETL Processing Cards */
        .etl-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1rem;
            border-radius: 10px;
            color: white;
            margin: 0.5rem 0;
        }
        
        .etl-success-card {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            padding: 1rem;
            border-radius: 10px;
            color: white;
            margin: 0.5rem 0;
        }
        
        .etl-error-card {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
            padding: 1rem;
            border-radius: 10px;
            color: white;
            margin: 0.5rem 0;
        }
        
        /* Progress indicators (translucent: readable on the light and the dark theme) */
        .etl-progress {
            background: rgba(127, 127, 140, 0.18);
            border-radius: 20px;
            padding: 0.2rem;
            margin: 0.5rem 0;
        }
        
        .etl-progress-bar {
            background: linear-gradient(45deg, #667eea, #764ba2);
            height: 20px;
            border-radius: 15px;
            transition: width 0.3s ease;
        }
        
        /* Configuration panels */
        .config-panel {
            border: 2px solid var(--dm-card-border, #e1e5e9);
            border-radius: 10px;
            padding: 1rem;
            margin: 0.5rem 0;
            background: var(--dm-card-bg, transparent);
        }

        .config-panel-active {
            border-color: #667eea;
            background: rgba(102, 126, 234, 0.12);
        }
        
        /* Data quality indicators */
        .quality-good {
            color: #28a745;
            font-weight: bold;
        }
        
        .quality-warning {
            color: #ffc107;
            font-weight: bold;
        }
        
        .quality-error {
            color: #dc3545;
            font-weight: bold;
        }
        
        /* ETL Pipeline Steps */
        .pipeline-step {
            display: flex;
            align-items: center;
            padding: 0.5rem;
            margin: 0.25rem 0;
            border-radius: 5px;
        }
        
        .step-pending { background-color: rgba(127, 127, 140, 0.14); }
        .step-running { background-color: rgba(255, 181, 71, 0.24); }
        .step-complete { background-color: rgba(18, 128, 92, 0.22); }
        .step-error { background-color: rgba(220, 53, 69, 0.22); }
        </style>
        """, unsafe_allow_html=True)
    
    def render_etl_dashboard_header(self):
        """Enhanced header for ETL dashboard"""
        st.markdown("""
        <div class="etl-card">
            <h2>⚙️ Advanced ETL Processing Dashboard</h2>
            <p>Transform, validate, and load your data with comprehensive business rules</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_pipeline_progress(self, steps: List[Dict[str, Any]], current_step: int = 0):
        """Visual pipeline progress indicator"""
        st.markdown("### 🔄 ETL Pipeline Progress")
        
        for i, step in enumerate(steps):
            status = "pending"
            if i < current_step:
                status = "complete"
            elif i == current_step:
                status = "running"
            elif step.get('error'):
                status = "error"
            
            # Status icon
            icons = {
                "pending": "⭕",
                "running": "🔄", 
                "complete": "✅",
                "error": "❌"
            }
            
            # Progress bar for current step
            progress_html = ""
            if status == "running" and step.get('progress'):
                progress_html = f"""
                <div class="etl-progress">
                    <div class="etl-progress-bar" style="width: {step['progress']}%"></div>
                </div>
                """
            
            st.markdown(f"""
            <div class="pipeline-step step-{status}">
                {icons[status]} <strong>Step {i+1}:</strong> {step['name']}
                {f"<br><small>{step.get('description', '')}</small>" if step.get('description') else ""}
                {progress_html}
            </div>
            """, unsafe_allow_html=True)
    
    def render_data_quality_dashboard(self, df: pd.DataFrame, title: str = "Data Quality Analysis"):
        """Comprehensive data quality visualization dashboard"""
        st.markdown(f"### 📊 {title}")
        
        if df.empty:
            st.warning("No data available for quality analysis")
            return
        
        # Quality metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_records = len(df)
            st.metric("Total Records", f"{total_records:,}")
        
        with col2:
            total_fields = len(df.columns)
            st.metric("Total Fields", total_fields)
        
        with col3:
            null_percentage = (df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100)
            st.metric("Null Values %", f"{null_percentage:.1f}%")
        
        with col4:
            duplicate_percentage = ((len(df) - len(df.drop_duplicates())) / len(df) * 100)
            st.metric("Duplicates %", f"{duplicate_percentage:.1f}%")
        
        # Interactive visualizations
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Data Overview", "🔍 Missing Data", "📊 Data Types", "⚠️ Quality Issues"])
        
        with tab1:
            self.render_data_overview_charts(df)
        
        with tab2:
            self.render_missing_data_analysis(df)
        
        with tab3:
            self.render_data_types_analysis(df)
        
        with tab4:
            self.render_quality_issues_analysis(df)
    
    def render_data_overview_charts(self, df: pd.DataFrame):
        """Data overview visualizations"""
        col1, col2 = st.columns(2)
        
        with col1:
            # Records per column chart
            non_null_counts = df.count()
            fig = px.bar(
                x=non_null_counts.index,
                y=non_null_counts.values,
                title="Non-Null Records per Field",
                labels={'x': 'Fields', 'y': 'Count'}
            )
            fig.update_layout(xaxis_tickangle=-45, height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Data completeness heatmap
            if len(df.columns) <= 20:  # Only for manageable number of columns
                missing_data = df.isnull().head(100)  # First 100 rows
                fig = px.imshow(
                    missing_data.values,
                    labels=dict(x="Fields", y="Records", color="Missing"),
                    x=missing_data.columns,
                    title="Missing Data Pattern (First 100 records)",
                    color_continuous_scale="Reds"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
    
    def render_missing_data_analysis(self, df: pd.DataFrame):
        """Missing data analysis"""
        missing_stats = df.isnull().sum().sort_values(ascending=False)
        missing_pct = (missing_stats / len(df) * 100).round(2)
        
        if missing_stats.sum() == 0:
            st.success("🎉 No missing data found!")
            return
        
        # Missing data summary
        missing_df = pd.DataFrame({
            'Field': missing_stats.index,
            'Missing Count': missing_stats.values,
            'Missing %': missing_pct.values
        })
        missing_df = missing_df[missing_df['Missing Count'] > 0]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Missing Data Summary:**")
            st.dataframe(missing_df, use_container_width=True)
        
        with col2:
            # Missing data visualization
            if not missing_df.empty:
                fig = px.bar(
                    missing_df.head(10),
                    x='Missing %',
                    y='Field',
                    orientation='h',
                    title="Top 10 Fields with Missing Data",
                    color='Missing %',
                    color_continuous_scale="Reds"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
    
    def render_data_types_analysis(self, df: pd.DataFrame):
        """Data types analysis"""
        type_counts = df.dtypes.value_counts()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Data type distribution
            fig = px.pie(
                values=type_counts.values,
                names=[str(dtype) for dtype in type_counts.index],
                title="Data Type Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Data type details
            type_info = []
            for col in df.columns:
                dtype = str(df[col].dtype)
                unique_count = df[col].nunique()
                sample_val = str(df[col].dropna().iloc[0]) if not df[col].dropna().empty else "N/A"
                
                type_info.append({
                    'Field': col,
                    'Type': dtype,
                    'Unique Values': unique_count,
                    'Sample Value': sample_val
                })
            
            st.write("**Field Type Details:**")
            st.dataframe(pd.DataFrame(type_info), use_container_width=True)
    
    def render_quality_issues_analysis(self, df: pd.DataFrame):
        """Quality issues analysis"""
        issues = []
        
        for col in df.columns:
            col_data = df[col]
            
            # Check for potential issues
            if col_data.dtype == 'object':
                # String length variations
                if not col_data.dropna().empty:
                    lengths = col_data.dropna().astype(str).str.len()
                    if lengths.std() > lengths.mean() * 0.5:  # High variation
                        issues.append({
                            'Field': col,
                            'Issue': 'High string length variation',
                            'Severity': 'Warning',
                            'Details': f"Length varies from {lengths.min()} to {lengths.max()}"
                        })
                
                # Special characters
                special_chars = col_data.dropna().astype(str).str.contains(r'[^\w\s]', na=False).sum()
                if special_chars > 0:
                    issues.append({
                        'Field': col,
                        'Issue': 'Contains special characters',
                        'Severity': 'Info',
                        'Details': f"{special_chars} records with special characters"
                    })
            
            # Duplicate values in what should be unique fields
            if 'id' in col.lower() or 'key' in col.lower():
                duplicates = col_data.duplicated().sum()
                if duplicates > 0:
                    issues.append({
                        'Field': col,
                        'Issue': 'Duplicate values in ID/Key field',
                        'Severity': 'Error',
                        'Details': f"{duplicates} duplicate values found"
                    })
        
        if not issues:
            st.success("🎉 No obvious quality issues detected!")
            return
        
        # Display issues
        issues_df = pd.DataFrame(issues)
        
        # Color code by severity
        from ui_components.theme import STATUS_CELL

        def highlight_severity(row):
            # Tints readable in light and dark mode
            colors = {'Error': STATUS_CELL['fail'], 'Warning': STATUS_CELL['warn'], 'Info': STATUS_CELL['info']}
            return [colors.get(row['Severity'], '')] * len(row)
        
        st.write("**Potential Quality Issues:**")
        styled_df = issues_df.style.apply(highlight_severity, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # Issue summary
        severity_counts = issues_df['Severity'].value_counts()
        col1, col2, col3 = st.columns(3)
        
        if 'Error' in severity_counts:
            with col1:
                st.markdown(f'<div class="quality-error">❌ {severity_counts["Error"]} Errors</div>', unsafe_allow_html=True)
        
        if 'Warning' in severity_counts:
            with col2:
                st.markdown(f'<div class="quality-warning">⚠️ {severity_counts["Warning"]} Warnings</div>', unsafe_allow_html=True)
        
        if 'Info' in severity_counts:
            with col3:
                st.markdown(f'<div class="quality-good">ℹ️ {severity_counts["Info"]} Info</div>', unsafe_allow_html=True)
    
    def render_transformation_log_viewer(self, log_entries: List[str], title: str = "Transformation Log"):
        """Enhanced transformation log viewer"""
        st.markdown(f"### 📋 {title}")
        
        if not log_entries:
            st.info("No transformation logs available")
            return
        
        # Create expandable log sections
        for i, entry in enumerate(log_entries):
            timestamp = time.strftime("%H:%M:%S")
            
            # Determine log level
            if "error" in entry.lower() or "failed" in entry.lower():
                icon = "❌"
                style_class = "etl-error-card"
            elif "warning" in entry.lower():
                icon = "⚠️"
                style_class = "etl-card"
            else:
                icon = "✅"
                style_class = "etl-success-card"
            
            st.markdown(f"""
            <div class="{style_class}">
                {icon} <strong>[{timestamp}]</strong> {entry}
            </div>
            """, unsafe_allow_html=True)
    
    def render_configuration_builder_wizard(self, step: int = 1, total_steps: int = 6):
        """Interactive configuration builder wizard"""
        st.markdown("### 🧙‍♂️ Configuration Wizard")
        
        # Progress indicator
        progress = step / total_steps
        st.progress(progress)
        st.write(f"Step {step} of {total_steps}")
        
        # Step indicators
        steps = [
            "📁 File Settings",
            "🗺️ Field Mapping", 
            "🔍 Lookup Fields",
            "⚙️ Business Rules",
            "✅ Validation",
            "💾 Save Config"
        ]
        
        cols = st.columns(total_steps)
        for i, (col, step_name) in enumerate(zip(cols, steps)):
            with col:
                if i + 1 < step:
                    st.markdown(f"✅ {step_name}")
                elif i + 1 == step:
                    st.markdown(f"🔄 **{step_name}**")
                else:
                    st.markdown(f"⭕ {step_name}")
    
    def render_error_analysis_dashboard(self, error_df: pd.DataFrame):
        """Comprehensive error analysis dashboard"""
        if error_df.empty:
            st.success("🎉 No errors found in the data!")
            return
        
        st.markdown("### ❌ Error Analysis Dashboard")
        
        # Error summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Errors", len(error_df))
        
        with col2:
            if 'FinalErrors' in error_df.columns:
                unique_error_types = error_df['FinalErrors'].nunique()
                st.metric("Error Types", unique_error_types)
        
        with col3:
            error_rate = (len(error_df) / (len(error_df) + 1000)) * 100  # Assuming total processed
            st.metric("Error Rate %", f"{error_rate:.2f}")
        
        with col4:
            if 'FinalErrors' in error_df.columns:
                avg_errors_per_record = error_df['FinalErrors'].str.split(';').str.len().mean()
                st.metric("Avg Errors/Record", f"{avg_errors_per_record:.1f}")
        
        # Error type analysis
        if 'FinalErrors' in error_df.columns:
            col1, col2 = st.columns(2)
            
            with col1:
                # Error type distribution
                error_summary = error_df['FinalErrors'].value_counts().head(10)
                fig = px.bar(
                    x=error_summary.values,
                    y=error_summary.index,
                    orientation='h',
                    title="Top 10 Error Types",
                    labels={'x': 'Count', 'y': 'Error Type'}
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Error severity distribution
                error_severities = []
                for error_text in error_df['FinalErrors'].dropna():
                    if 'missing mandatory' in error_text.lower():
                        error_severities.append('Critical')
                    elif 'invalid' in error_text.lower():
                        error_severities.append('Error')
                    elif 'duplicate' in error_text.lower():
                        error_severities.append('Warning')
                    else:
                        error_severities.append('Info')
                
                severity_counts = pd.Series(error_severities).value_counts()
                fig = px.pie(
                    values=severity_counts.values,
                    names=severity_counts.index,
                    title="Error Severity Distribution"
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Detailed error table
        with st.expander("📋 Detailed Error Records"):
            st.dataframe(error_df, use_container_width=True)
    
    def render_lookup_resolution_status(self, lookup_results: Dict[str, Any]):
        """Visual status for lookup field resolution"""
        st.markdown("### 🔍 Lookup Resolution Status")
        
        for field_name, result in lookup_results.items():
            status = result.get('status', 'unknown')
            resolved_count = result.get('resolved', 0)
            total_count = result.get('total', 0)
            
            # Status indicators
            if status == 'success':
                icon = "✅"
                color = "success"
            elif status == 'partial':
                icon = "⚠️"
                color = "warning"
            else:
                icon = "❌"
                color = "error"
            
            resolution_rate = (resolved_count / total_count * 100) if total_count > 0 else 0
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"{icon} **{field_name}**")
                st.progress(resolution_rate / 100)
            
            with col2:
                st.metric("Resolved", f"{resolved_count}/{total_count}")
            
            with col3:
                st.metric("Success Rate", f"{resolution_rate:.1f}%")

# Usage example function
def enhance_etl_ui():
    """
    Example usage of ETL UI enhancements
    This should be integrated into the main ETL interface
    """
    ui = ETLUIEnhancements()
    
    # Example usage in ETL interface
    ui.render_etl_dashboard_header()
    
    # Example pipeline steps
    pipeline_steps = [
        {"name": "Data Loading", "description": "Reading source files", "progress": 100},
        {"name": "Column Mapping", "description": "Transforming field names", "progress": 80},
        {"name": "Lookup Resolution", "description": "Resolving parent relationships", "progress": 40},
        {"name": "Data Validation", "description": "Checking business rules"},
        {"name": "Error Analysis", "description": "Generating quality reports"},
        {"name": "Output Generation", "description": "Creating final outputs"}
    ]
    
    ui.render_pipeline_progress(pipeline_steps, current_step=2)
    
    # Example with sample data
    if st.button("Show Data Quality Demo"):
        # Create sample data for demo
        sample_data = pd.DataFrame({
            'Name': ['John Doe', 'Jane Smith', None, 'Bob Johnson'],
            'Email': ['john@email.com', None, 'invalid-email', 'bob@company.com'],
            'Amount': [100.50, 250.75, None, -50.25],
            'Date': ['2023-01-01', '2023-02-15', 'invalid-date', '2023-03-30']
        })
        
        ui.render_data_quality_dashboard(sample_data, "Sample Data Quality Analysis")