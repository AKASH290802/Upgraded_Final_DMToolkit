"""
Master-Detail Validation Helper for Validation Operations
Adds Master-Detail awareness to Schema, Enhanced, and GenAI validation
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional
import streamlit as st


def identify_master_detail_fields_for_validation(sf_fields_metadata: List[Dict]) -> Dict[str, Dict]:
    """
    Identify Master-Detail fields from Salesforce field metadata
    Used in Schema Validation, Enhanced Validation, and GenAI Validation
    
    Args:
        sf_fields_metadata: List of field metadata dictionaries from Salesforce describe()
    
    Returns:
        Dictionary mapping field_name -> field_info with Master-Detail properties
    """
    master_detail_fields = {}
    
    for field in sf_fields_metadata:
        if field.get('type') == 'masterdetail' and field.get('referenceTo'):
            master_detail_fields[field['name']] = {
                'name': field['name'],
                'label': field.get('label', field['name']),
                'type': 'masterdetail',
                'parent_object': field['referenceTo'][0],
                'is_required': True,
                'is_nillable': False,
                'cascading_delete': True,
                'inherits_record_type': True,
                'updateable': field.get('updateable', False),
                'createable': field.get('createable', False),
                'length': field.get('length', 0)
            }
    
    return master_detail_fields


def separate_lookup_from_master_detail(sf_fields_metadata: List[Dict]) -> Tuple[Dict, Dict]:
    """
    Separate Master-Detail relationships from generic Lookup relationships
    
    Args:
        sf_fields_metadata: List of field metadata from Salesforce describe()
    
    Returns:
        Tuple of (master_detail_fields, lookup_fields)
    """
    master_detail_fields = {}
    lookup_fields = {}
    
    for field in sf_fields_metadata:
        if field.get('type') == 'masterdetail' and field.get('referenceTo'):
            master_detail_fields[field['name']] = field
        elif field.get('type') in ['reference', 'lookup'] and field.get('referenceTo'):
            lookup_fields[field['name']] = field
    
    return master_detail_fields, lookup_fields


def validate_master_detail_field_required(field_name: str, field_info: Dict, data_df: pd.DataFrame) -> Dict:
    """
    Validate that Master-Detail field has no NULL/missing values
    Master-Detail fields are ALWAYS required
    
    Args:
        field_name: Name of Master-Detail field
        field_info: Field metadata
        data_df: DataFrame containing the data
    
    Returns:
        Validation report with missing count and status
    """
    report = {
        'field_name': field_name,
        'field_type': 'masterdetail',
        'validation': 'Required (Master-Detail)',
        'status': 'PASS',
        'missing_count': 0,
        'null_rows': [],
        'message': ''
    }
    
    if field_name not in data_df.columns:
        report['status'] = 'WARN'
        report['message'] = f"Master-Detail field '{field_name}' not found in data"
        return report
    
    # Check for NULL/missing values
    null_mask = data_df[field_name].isna() | (data_df[field_name] == '')
    missing_count = null_mask.sum()
    
    report['missing_count'] = missing_count
    report['null_rows'] = data_df[null_mask].index.tolist()[:10]  # First 10 for display
    
    if missing_count > 0:
        report['status'] = 'FAIL'
        report['message'] = (
            f"🚫 CRITICAL: Master-Detail field '{field_name}' has {missing_count} missing values. "
            f"Master-Detail relationships are MANDATORY and cannot be NULL."
        )
    else:
        report['status'] = 'PASS'
        report['message'] = f"✅ Master-Detail field '{field_name}' has no missing values"
    
    return report


def validate_master_detail_relationships_in_data(
    sf_fields_metadata: List[Dict],
    data_df: pd.DataFrame
) -> Dict:
    """
    Comprehensive Master-Detail validation for Enhanced Validation
    
    Args:
        sf_fields_metadata: Field metadata from Salesforce
        data_df: Data to validate
    
    Returns:
        Comprehensive validation report
    """
    report = {
        'overall_status': 'PASS',
        'total_md_fields': 0,
        'valid_md_fields': 0,
        'invalid_md_fields': 0,
        'critical_issues': 0,
        'field_validations': {},
        'warnings': [],
        'errors': []
    }
    
    # Identify Master-Detail fields
    md_fields = identify_master_detail_fields_for_validation(sf_fields_metadata)
    report['total_md_fields'] = len(md_fields)
    
    if len(md_fields) == 0:
        report['warnings'].append("No Master-Detail fields found in this object")
        return report
    
    # Validate each Master-Detail field
    for md_field_name, md_field_info in md_fields.items():
        # Check if field is required
        field_validation = validate_master_detail_field_required(
            md_field_name,
            md_field_info,
            data_df
        )
        
        report['field_validations'][md_field_name] = field_validation
        
        if field_validation['status'] == 'PASS':
            report['valid_md_fields'] += 1
        else:
            report['invalid_md_fields'] += 1
            if field_validation['status'] == 'FAIL':
                report['critical_issues'] += field_validation['missing_count']
                report['overall_status'] = 'FAIL'
    
    return report


def generate_master_detail_validation_report_for_ui(validation_report: Dict) -> str:
    """
    Generate report string for displaying in Streamlit UI
    
    Args:
        validation_report: Report from validate_master_detail_relationships_in_data()
    
    Returns:
        Formatted markdown string
    """
    lines = [
        "## 🔗 Master-Detail Relationship Validation\n",
        f"**Overall Status**: {'✅ PASS' if validation_report['overall_status'] == 'PASS' else '❌ FAIL'}\n",
        f"**Total Master-Detail Fields**: {validation_report['total_md_fields']}\n",
        f"**Valid Fields**: {validation_report['valid_md_fields']}\n",
        f"**Invalid Fields**: {validation_report['invalid_md_fields']}\n",
        f"**Critical Issues**: {validation_report['critical_issues']}\n"
    ]
    
    if validation_report['field_validations']:
        lines.append("\n### Field-by-Field Validation:\n")
        for field_name, field_report in validation_report['field_validations'].items():
            status_icon = "✅" if field_report['status'] == 'PASS' else "❌"
            parent_obj = field_report.get('field_info', {}).get('parent_object', 'Unknown')
            lines.append(f"{status_icon} **{field_name}** → {parent_obj}")
            lines.append(f"  - Status: {field_report['message']}")
            if field_report['missing_count'] > 0:
                lines.append(f"  - Missing Rows: {field_report['missing_count']}")
            lines.append("")
    
    if validation_report['warnings']:
        lines.append("\n### ⚠️ Warnings:\n")
        for warning in validation_report['warnings']:
            lines.append(f"- {warning}")
    
    if validation_report['errors']:
        lines.append("\n### ❌ Errors:\n")
        for error in validation_report['errors']:
            lines.append(f"- {error}")
    
    return "\n".join(lines)


def display_master_detail_validation_ui(sf_fields_metadata: List[Dict], data_df: pd.DataFrame):
    """
    Display Master-Detail validation in Streamlit UI
    Call this in the validation section to add Master-Detail awareness
    
    Args:
        sf_fields_metadata: Field metadata from Salesforce
        data_df: Data to validate
    """
    # Identify Master-Detail fields
    md_fields = identify_master_detail_fields_for_validation(sf_fields_metadata)
    
    if len(md_fields) == 0:
        st.info("ℹ️ No Master-Detail relationships found in this object")
        return
    
    st.subheader("🔗 Master-Detail Relationship Validation")
    
    # Show warning about Master-Details
    with st.expander("⚠️ What are Master-Detail Relationships?", expanded=False):
        st.markdown("""
        **Master-Detail Relationships are CRITICAL:**
        - **Always Required**: Cannot be NULL
        - **Cascading Delete**: Deleting parent deletes ALL children
        - **Record Type Inheritance**: Child inherits parent's Record Type
        - **Data Integrity**: Missing parent records will cause upload failures
        
        **Examples:**
        - Order → OrderItem (Items are children of Order)
        - Account → Opportunity (Opportunities are children of Account)
        - Warranty → Claim (Claims are children of Warranty)
        """)
    
    # Run validation
    validation_report = validate_master_detail_relationships_in_data(sf_fields_metadata, data_df)
    
    # Display results
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Master-Detail Fields", validation_report['total_md_fields'])
    with col2:
        st.metric("Valid ✅", validation_report['valid_md_fields'])
    with col3:
        st.metric("Invalid ❌", validation_report['invalid_md_fields'])
    
    # Show details
    if validation_report['invalid_md_fields'] > 0:
        st.error(f"🚫 **CRITICAL**: {validation_report['critical_issues']} records have missing Master-Detail values")
        
        with st.expander("📋 Details", expanded=True):
            for field_name, field_report in validation_report['field_validations'].items():
                if field_report['status'] != 'PASS':
                    st.write(f"**{field_name}**")
                    st.write(f"- Missing Count: {field_report['missing_count']}")
                    if field_report['null_rows']:
                        st.write(f"- Sample Row Indices: {field_report['null_rows'][:5]}")
    else:
        st.success("✅ All Master-Detail fields are valid")
    
    # Show cascading delete warnings
    st.warning(
        f"⚠️ **Cascading Delete Implications:**\n\n"
        f"This object has {len(md_fields)} Master-Detail relationship(s):\n" +
        "\n".join([f"• {name} → {info['parent_object']}" for name, info in md_fields.items()]) +
        f"\n\nIf parent records are deleted, ALL child records will be deleted automatically."
    )


def add_master_detail_to_schema_validation(sf_conn, object_name: str) -> Dict:
    """
    Helper function for Schema Validation to include Master-Detail checks
    
    Args:
        sf_conn: Salesforce connection
        object_name: Object to validate
    
    Returns:
        Master-Detail validation results
    """
    try:
        object_metadata = getattr(sf_conn, object_name).describe()
        fields = object_metadata['fields']
        
        md_fields = identify_master_detail_fields_for_validation(fields)
        
        results = {
            'total': len(md_fields),
            'fields': md_fields,
            'status': 'OK' if len(md_fields) > 0 else 'NO_MD_FIELDS'
        }
        
        return results
    except Exception as e:
        return {
            'total': 0,
            'fields': {},
            'status': 'ERROR',
            'error': str(e)
        }


def get_master_detail_validation_checklist() -> Dict:
    """
    Return a checklist of Master-Detail validation points
    Use this for pre-migration planning
    """
    return {
        'required_fields': {
            'description': 'All Master-Detail fields must have values (no NULLs)',
            'impact': 'CRITICAL - Upload will fail if NULL'
        },
        'parent_existence': {
            'description': 'All parent records must exist in target system',
            'impact': 'CRITICAL - Child records cannot be created without parent'
        },
        'cascading_delete': {
            'description': 'Deleting parent automatically deletes all children',
            'impact': 'HIGH - Data loss risk'
        },
        'record_type_inheritance': {
            'description': 'Child records inherit parent Record Type',
            'impact': 'MEDIUM - May affect Record Type validation rules'
        },
        'sharing_inheritance': {
            'description': 'Child records inherit parent sharing settings',
            'impact': 'MEDIUM - May affect access levels'
        },
        'field_updatability': {
            'description': 'Master-Detail field cannot be updated after creation',
            'impact': 'HIGH - Cannot change parent after record created'
        }
    }
