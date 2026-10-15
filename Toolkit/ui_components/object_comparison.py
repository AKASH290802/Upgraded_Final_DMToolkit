import streamlit as st
import pandas as pd
import json
import os
from typing import Dict, Optional, List
from datetime import datetime
from io import BytesIO

def get_available_orgs():
    """Salesforce orgs configured in Configuration (same list as the sidebar)."""
    try:
        from ui_components.connection_manager import salesforce_orgs
        return list(salesforce_orgs().keys())
    except Exception as e:
        st.error(f"Error loading organizations: {str(e)}")
        return []

def get_salesforce_connection(org_name):
    """Shared, pooled Salesforce connection for org_name.

    Uses connection_manager, so the sidebar org reuses the sidebar connection,
    a second org gets its own cached connection, and nothing logs in again on
    reruns. The sidebar connection is never replaced.
    """
    try:
        from ui_components.connection_manager import get_sf_connection
        return get_sf_connection(org_name)
    except Exception as e:
        st.error(f"Error connecting to {org_name}: {str(e)}")
        return None

def get_salesforce_objects(sf_conn, filter_custom=False):
    """Get list of Salesforce objects"""
    try:
        from ui_components.utils import get_salesforce_objects as get_objects
        return get_objects(sf_conn, filter_custom=filter_custom)
    except Exception as e:
        st.error(f"Error retrieving objects: {str(e)}")
        return []

def get_object_description(sf_conn, object_name):
    """Get object field definitions"""
    try:
        from ui_components.utils import get_object_description as get_desc
        return get_desc(sf_conn, object_name)
    except Exception as e:
        st.error(f"Error retrieving object description: {str(e)}")
        return None

def compare_salesforce_objects(source_conn, target_conn, source_org, target_org, source_object, target_object, options):
    """
    Compare two Salesforce objects and generate a detailed comparison report
    """
    try:
        # Get object descriptions
        source_desc = get_object_description(source_conn, source_object)
        target_desc = get_object_description(target_conn, target_object)
        
        if not source_desc or not target_desc:
            return {'success': False, 'error': 'Failed to retrieve object descriptions'}
        
        comparison_result = {
            'success': True,
            'source_org': source_org,
            'target_org': target_org,
            'source_object': source_object,
            'target_object': target_object,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'comparisons': {}
        }
        
        # Compare Fields
        if options.get('compare_fields', True):
            field_comparison = compare_fields(source_desc, target_desc)
            comparison_result['comparisons']['fields'] = field_comparison
        
        # Compare Record Types
        if options.get('compare_record_types', True):
            recordtype_comparison = compare_record_types(source_conn, target_conn, source_object, target_object)
            comparison_result['comparisons']['record_types'] = recordtype_comparison
        
        # Compare Picklist Values
        if options.get('compare_picklists', True):
            picklist_comparison = compare_picklist_values(source_desc, target_desc)
            comparison_result['comparisons']['picklists'] = picklist_comparison
        
        # Compare Validation Rules
        if options.get('compare_validation_rules', True):
            validation_comparison = compare_validation_rules(source_conn, target_conn, source_object, target_object)
            comparison_result['comparisons']['validation_rules'] = validation_comparison
        
        # Compare Data Records
        if options.get('compare_data', False) and options.get('data_config'):
            data_config = options['data_config']
            
            # Fetch records from both orgs
            source_records_result = fetch_object_records(
                source_conn,
                source_object,
                fields=data_config.get('fields', ['Id', 'Name']),
                record_limit=data_config.get('record_limit', 100),
                where_clause=data_config.get('where_clause', '')
            )
            
            target_records_result = fetch_object_records(
                target_conn,
                target_object,
                fields=data_config.get('fields', ['Id', 'Name']),
                record_limit=data_config.get('record_limit', 100),
                where_clause=data_config.get('where_clause', '')
            )
            
            if source_records_result['success'] and target_records_result['success']:
                data_comparison = compare_data(
                    source_records_result['records'],
                    target_records_result['records'],
                    data_config.get('fields', ['Id', 'Name']),
                    matching_fields=data_config.get('matching_fields', ['Name'])
                )
                comparison_result['comparisons']['data'] = data_comparison
                comparison_result['data_config'] = {
                    'record_limit': data_config.get('record_limit', 100),
                    'where_clause': data_config.get('where_clause', ''),
                    'fields_compared': len(data_config.get('fields', [])),
                    'matching_fields': data_config.get('matching_fields', ['Name'])
                }
        
        # Generate summary statistics
        comparison_result['summary'] = generate_comparison_summary(comparison_result['comparisons'])
        
        return comparison_result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def compare_fields(source_desc, target_desc):
    """Compare field definitions between two objects"""
    source_fields = {f['name']: f for f in source_desc.get('fields', [])}
    target_fields = {f['name']: f for f in target_desc.get('fields', [])}
    
    only_in_source = []
    only_in_target = []
    common_fields = []
    differences = []
    
    # Fields only in source
    for field_name in source_fields:
        if field_name not in target_fields:
            only_in_source.append({
                'name': field_name,
                'type': source_fields[field_name].get('type'),
                'label': source_fields[field_name].get('label')
            })
    
    # Fields only in target
    for field_name in target_fields:
        if field_name not in source_fields:
            only_in_target.append({
                'name': field_name,
                'type': target_fields[field_name].get('type'),
                'label': target_fields[field_name].get('label')
            })
    
    # Common fields - check for differences
    for field_name in source_fields:
        if field_name in target_fields:
            source_field = source_fields[field_name]
            target_field = target_fields[field_name]
            
            field_diff = {
                'name': field_name,
                'label': source_field.get('label'),
                'differences': []
            }
            
            # Compare attributes
            if source_field.get('type') != target_field.get('type'):
                field_diff['differences'].append(f"Type: {source_field.get('type')} → {target_field.get('type')}")
            
            if source_field.get('length') != target_field.get('length'):
                field_diff['differences'].append(f"Length: {source_field.get('length')} → {target_field.get('length')}")
            
            if source_field.get('precision') != target_field.get('precision'):
                field_diff['differences'].append(f"Precision: {source_field.get('precision')} → {target_field.get('precision')}")
            
            if source_field.get('required', False) != target_field.get('required', False):
                field_diff['differences'].append(f"Required: {source_field.get('required')} → {target_field.get('required')}")
            
            if field_diff['differences']:
                differences.append(field_diff)
            else:
                common_fields.append(field_name)
    
    return {
        'only_in_source': only_in_source,
        'only_in_target': only_in_target,
        'common_fields': common_fields,
        'differences': differences,
        'total_source': len(source_fields),
        'total_target': len(target_fields),
        'total_common': len(common_fields),
        'total_differences': len(differences)
    }

def compare_picklist_values(source_desc, target_desc):
    """Compare picklist values between two objects"""
    source_fields = {f['name']: f for f in source_desc.get('fields', []) if f.get('type') in ['picklist', 'multipicklist']}
    target_fields = {f['name']: f for f in target_desc.get('fields', []) if f.get('type') in ['picklist', 'multipicklist']}
    
    picklist_differences = []
    
    for field_name in source_fields:
        if field_name in target_fields:
            source_values = set([v['value'] for v in source_fields[field_name].get('picklistValues', [])])
            target_values = set([v['value'] for v in target_fields[field_name].get('picklistValues', [])])
            
            only_in_source = list(source_values - target_values)
            only_in_target = list(target_values - source_values)
            
            if only_in_source or only_in_target:
                picklist_differences.append({
                    'field': field_name,
                    'label': source_fields[field_name].get('label'),
                    'only_in_source': only_in_source,
                    'only_in_target': only_in_target,
                    'total_source': len(source_values),
                    'total_target': len(target_values)
                })
    
    return {
        'differences': picklist_differences,
        'total_compared': len([f for f in source_fields if f in target_fields])
    }

def compare_record_types(source_conn, target_conn, source_object, target_object):
    """Compare record types between two objects"""
    try:
        source_rt_query = f"SELECT Id, Name, DeveloperName, IsActive FROM RecordType WHERE SObjectType = '{source_object}'"
        source_rts = source_conn.query(source_rt_query).get('records', [])
        
        target_rt_query = f"SELECT Id, Name, DeveloperName, IsActive FROM RecordType WHERE SObjectType = '{target_object}'"
        target_rts = target_conn.query(target_rt_query).get('records', [])
        
        source_rt_names = {rt['DeveloperName']: rt for rt in source_rts}
        target_rt_names = {rt['DeveloperName']: rt for rt in target_rts}
        
        only_in_source = [name for name in source_rt_names if name not in target_rt_names]
        only_in_target = [name for name in target_rt_names if name not in source_rt_names]
        common = [name for name in source_rt_names if name in target_rt_names]
        
        return {
            'only_in_source': only_in_source,
            'only_in_target': only_in_target,
            'common': common,
            'total_source': len(source_rts),
            'total_target': len(target_rts)
        }
    except Exception as e:
        return {'error': str(e)}

def compare_validation_rules(source_conn, target_conn, source_object, target_object):
    """Compare validation rules between two objects"""
    try:
        source_vr_query = f"SELECT ValidationName, Active, ErrorDisplayField, ErrorMessage FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{source_object}'"
        try:
            source_vrs = source_conn.toolingapi.query(source_vr_query).get('records', [])
        except:
            source_vrs = []
        
        target_vr_query = f"SELECT ValidationName, Active, ErrorDisplayField, ErrorMessage FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{target_object}'"
        try:
            target_vrs = target_conn.toolingapi.query(target_vr_query).get('records', [])
        except:
            target_vrs = []
        
        source_vr_names = {vr.get('ValidationName', ''): vr for vr in source_vrs if vr.get('ValidationName')}
        target_vr_names = {vr.get('ValidationName', ''): vr for vr in target_vrs if vr.get('ValidationName')}
        
        only_in_source = [name for name in source_vr_names if name not in target_vr_names]
        only_in_target = [name for name in target_vr_names if name not in source_vr_names]
        common = [name for name in source_vr_names if name in target_vr_names]
        
        return {
            'only_in_source': only_in_source,
            'only_in_target': only_in_target,
            'common': common,
            'total_source': len(source_vrs),
            'total_target': len(target_vrs)
        }
    except Exception as e:
        return {'error': str(e)}

def fetch_object_records(sf_conn, object_name, fields=None, record_limit=1000, where_clause=""):
    """Fetch records from a Salesforce object"""
    try:
        if fields is None or len(fields) == 0:
            # Default to Id and Name if no fields specified
            fields = ['Id', 'Name']
        
        # Build SOQL query
        select_clause = ', '.join(fields)
        query = f"SELECT {select_clause} FROM {object_name}"
        
        if where_clause.strip():
            query += f" {where_clause}"
        
        query += f" LIMIT {record_limit}"
        
        result = sf_conn.query(query)
        records = result.get('records', [])
        
        return {
            'success': True,
            'records': records,
            'total': len(records),
            'query': query
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'records': [],
            'total': 0
        }

def compare_data(source_records, target_records, fields_to_compare, matching_fields=['Name']):
    """Compare actual data records between source and target by matching on specified fields
    
    Args:
        source_records: Records from source org
        target_records: Records from target org
        fields_to_compare: Fields to compare in matched records
        matching_fields: Fields to use for matching records (e.g., ['Name'], ['Name', 'Email'], etc.)
    """
    try:
        def create_matching_key(record, key_fields):
            """Create a matching key from specified fields"""
            values = []
            for field in key_fields:
                val = record.get(field, '')
                values.append(str(val).strip().lower() if val is not None else '')
            return '|'.join(values)
        
        # Create maps using matching key instead of ID
        source_map = {}
        for record in source_records:
            key = create_matching_key(record, matching_fields)
            if key:  # Only add if we have at least one non-empty matching field
                source_map[key] = record
        
        target_map = {}
        for record in target_records:
            key = create_matching_key(record, matching_fields)
            if key:  # Only add if we have at least one non-empty matching field
                target_map[key] = record
        
        source_keys = set(source_map.keys())
        target_keys = set(target_map.keys())
        
        only_in_source_keys = source_keys - target_keys
        only_in_target_keys = target_keys - source_keys
        common_keys = source_keys & target_keys
        
        # Compare common records for field differences
        data_differences = []
        for match_key in common_keys:
            source_record = source_map[match_key]
            target_record = target_map[match_key]
            
            # Create a display name from matching fields
            display_name = ' | '.join([str(source_record.get(f, '')) for f in matching_fields if source_record.get(f)])
            
            record_diff = {
                'matching_key': display_name,
                'source_id': source_record.get('Id', 'N/A'),
                'target_id': target_record.get('Id', 'N/A'),
                'field_differences': []
            }
            
            for field in fields_to_compare:
                if field != 'Id':  # Don't compare IDs since they're org-specific
                    source_value = source_record.get(field)
                    target_value = target_record.get(field)
                    
                    if source_value != target_value:
                        record_diff['field_differences'].append({
                            'field': field,
                            'source_value': str(source_value) if source_value is not None else 'NULL',
                            'target_value': str(target_value) if target_value is not None else 'NULL'
                        })
            
            if record_diff['field_differences']:
                data_differences.append(record_diff)
        
        # Prepare records only in source
        only_in_source_list = []
        for key in only_in_source_keys:
            record = source_map[key]
            display_name = ' | '.join([str(record.get(f, '')) for f in matching_fields if record.get(f)])
            only_in_source_list.append({
                'matching_key': display_name,
                'record_id': record.get('Id', 'N/A')
            })
        
        # Prepare records only in target
        only_in_target_list = []
        for key in only_in_target_keys:
            record = target_map[key]
            display_name = ' | '.join([str(record.get(f, '')) for f in matching_fields if record.get(f)])
            only_in_target_list.append({
                'matching_key': display_name,
                'record_id': record.get('Id', 'N/A')
            })
        
        return {
            'success': True,
            'matching_fields': matching_fields,
            'only_in_source': only_in_source_list,
            'only_in_target': only_in_target_list,
            'data_differences': data_differences,
            'common_records': len(common_keys),
            'total_differences': len(data_differences),
            'unmatched_source': len(only_in_source_keys),
            'unmatched_target': len(only_in_target_keys)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def generate_comparison_summary(comparisons):
    """Generate summary statistics for the comparison"""
    summary = {
        'total_differences': 0,
        'categories_compared': len(comparisons)
    }
    
    for category, data in comparisons.items():
        if 'differences' in data:
            if isinstance(data['differences'], list):
                summary['total_differences'] += len(data['differences'])
        if 'only_in_source' in data:
            summary['total_differences'] += len(data.get('only_in_source', []))
        if 'only_in_target' in data:
            summary['total_differences'] += len(data.get('only_in_target', []))
    
    return summary

def display_comparison_results(comparison_result):
    """Display object comparison results"""
    st.markdown("## 📊 Comparison Report")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**🔵 Source:** {comparison_result['source_org']} / {comparison_result['source_object']}")
    with col2:
        st.info(f"**🟢 Target:** {comparison_result['target_org']} / {comparison_result['target_object']}")
    
    st.caption(f"Generated: {comparison_result['timestamp']}")
    
    st.markdown("### 📈 Summary")
    summary = comparison_result.get('summary', {})
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Categories Compared", summary.get('categories_compared', 0))
    with col2:
        st.metric("Total Differences", summary.get('total_differences', 0))
    with col3:
        match_percentage = max(0, 100 - (summary.get('total_differences', 0) * 10))
        st.metric("Match Score", f"{match_percentage:.1f}%")
    
    st.markdown("---")
    
    # Field Comparison
    if 'fields' in comparison_result['comparisons']:
        display_field_comparison(comparison_result['comparisons']['fields'])
    
    # Picklist Comparison
    if 'picklists' in comparison_result['comparisons']:
        display_picklist_comparison(comparison_result['comparisons']['picklists'])
    
    # Record Type Comparison
    if 'record_types' in comparison_result['comparisons']:
        display_recordtype_comparison(comparison_result['comparisons']['record_types'])
    
    # Validation Rules Comparison
    if 'validation_rules' in comparison_result['comparisons']:
        display_validation_comparison(comparison_result['comparisons']['validation_rules'])
    
    # Data Comparison
    if 'data' in comparison_result['comparisons']:
        st.markdown("---")
        display_data_comparison(comparison_result['comparisons']['data'])
        
        if 'data_config' in comparison_result:
            st.markdown("---")
            st.markdown("#### 📋 Data Comparison Configuration")
            config = comparison_result['data_config']
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Record Limit", config.get('record_limit', 'N/A'))
            with col2:
                st.metric("Matching Fields", ', '.join(config.get('matching_fields', ['Name'])))
            with col3:
                st.metric("Fields Compared", config.get('fields_compared', 0))
            with col4:
                where_clause = config.get('where_clause', 'None')
                st.metric("Filter Applied", "Yes" if where_clause and where_clause.strip() else "No")
    
    st.markdown("---")
    st.markdown("### 📥 Generate & Export Detailed Report")
    
    col1, col2, col3 = st.columns(3)
    
    # Excel Report
    with col1:
        excel_data = generate_detailed_excel_report(comparison_result)
        if excel_data:
            st.download_button(
                "📊 Download Excel Report",
                excel_data,
                f"comparison_report_{comparison_result['source_object']}_{comparison_result['target_object']}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    # JSON Report
    with col2:
        report_json = json.dumps(comparison_result, indent=2, default=str)
        st.download_button(
            "📄 Download JSON Report",
            report_json,
            f"comparison_report_{comparison_result['source_object']}_{comparison_result['target_object']}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json"
        )
    
    # CSV Summary Report
    with col3:
        # Create detailed CSV with summary
        csv_lines = [
            "COMPARISON REPORT - DETAILED SUMMARY",
            "",
            "REPORT INFORMATION",
            f"Report Generated,{comparison_result['timestamp']}",
            "",
            "ORGANIZATIONS & OBJECTS",
            f"Source Organization,{comparison_result['source_org']}",
            f"Source Object,{comparison_result['source_object']}",
            f"Target Organization,{comparison_result['target_org']}",
            f"Target Object,{comparison_result['target_object']}",
            "",
            "COMPARISON SUMMARY",
            f"Categories Compared,{comparison_result.get('summary', {}).get('categories_compared', 0)}",
            f"Total Differences Found,{comparison_result.get('summary', {}).get('total_differences', 0)}",
            ""
        ]
        
        # Add field comparison details
        if 'fields' in comparison_result['comparisons']:
            fields_data = comparison_result['comparisons']['fields']
            csv_lines.extend([
                "FIELD COMPARISON",
                f"Source Fields,{fields_data.get('total_source', 0)}",
                f"Target Fields,{fields_data.get('total_target', 0)}",
                f"Common Fields,{fields_data.get('total_common', 0)}",
                f"Field Differences,{fields_data.get('total_differences', 0)}",
                ""
            ])
        
        # Add picklist details
        if 'picklists' in comparison_result['comparisons']:
            picklist_data = comparison_result['comparisons']['picklists']
            csv_lines.extend([
                "PICKLIST COMPARISON",
                f"Picklists Compared,{picklist_data.get('total_compared', 0)}",
                f"Picklist Value Differences,{len(picklist_data.get('differences', []))}",
                ""
            ])
        
        # Add record type details
        if 'record_types' in comparison_result['comparisons']:
            rt_data = comparison_result['comparisons']['record_types']
            if 'error' not in rt_data:
                csv_lines.extend([
                    "RECORD TYPE COMPARISON",
                    f"Source Record Types,{rt_data.get('total_source', 0)}",
                    f"Target Record Types,{rt_data.get('total_target', 0)}",
                    f"Common Record Types,{len(rt_data.get('common', []))}",
                    ""
                ])
        
        # Add validation rule details
        if 'validation_rules' in comparison_result['comparisons']:
            vr_data = comparison_result['comparisons']['validation_rules']
            if 'error' not in vr_data:
                csv_lines.extend([
                    "VALIDATION RULE COMPARISON",
                    f"Source Validation Rules,{vr_data.get('total_source', 0)}",
                    f"Target Validation Rules,{vr_data.get('total_target', 0)}",
                    f"Common Validation Rules,{len(vr_data.get('common', []))}",
                    ""
                ])
        
        # Add data comparison details
        if 'data' in comparison_result['comparisons']:
            data_comp = comparison_result['comparisons']['data']
            if data_comp.get('success'):
                csv_lines.extend([
                    "DATA RECORD COMPARISON",
                    f"Common Records,{data_comp.get('common_records', 0)}",
                    f"Records Only in Source,{len(data_comp.get('only_in_source', []))}",
                    f"Records Only in Target,{len(data_comp.get('only_in_target', []))}",
                    f"Records with Field Differences,{data_comp.get('total_differences', 0)}",
                    ""
                ])
                
                if 'data_config' in comparison_result:
                    config = comparison_result['data_config']
                    csv_lines.extend([
                        "DATA COMPARISON CONFIGURATION",
                        f"Record Limit,{config.get('record_limit', 'N/A')}",
                        f"Matching Fields,{', '.join(config.get('matching_fields', ['Name']))}",
                        f"WHERE Clause,{config.get('where_clause', 'None')}",
                        f"Fields Compared,{config.get('fields_compared', 0)}",
                        ""
                    ])
        
        csv_data = "\n".join(csv_lines)
        
        st.download_button(
            "📋 Download Summary Report",
            csv_data,
            f"comparison_summary_{comparison_result['source_object']}_{comparison_result['target_object']}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv"
        )
    
    # Detailed text report preview
    st.markdown("---")
    st.markdown("### 📝 Detailed Report Preview")
    
    with st.expander("📊 View Full Report Summary", expanded=False):
        st.markdown(f"""
        **Report Generated:** {comparison_result['timestamp']}
        
        **Source Organization:** {comparison_result['source_org']} / {comparison_result['source_object']}
        **Target Organization:** {comparison_result['target_org']} / {comparison_result['target_object']}
        
        **Categories Compared:** {comparison_result.get('summary', {}).get('categories_compared', 0)}
        **Total Differences Found:** {comparison_result.get('summary', {}).get('total_differences', 0)}
        """)
        
        # Field Summary
        if 'fields' in comparison_result['comparisons']:
            fields_data = comparison_result['comparisons']['fields']
            st.markdown(f"""
            #### Field Comparison
            - Source Fields: {fields_data.get('total_source', 0)}
            - Target Fields: {fields_data.get('total_target', 0)}
            - Common Fields: {fields_data.get('total_common', 0)}
            - Fields with Differences: {fields_data.get('total_differences', 0)}
            """)
        
        # Data Comparison Summary
        if 'data' in comparison_result['comparisons']:
            data_comp = comparison_result['comparisons']['data']
            if data_comp.get('success'):
                st.markdown(f"""
                #### Data Record Comparison
                - Common Records: {data_comp.get('common_records', 0)}
                - Records Only in Source: {len(data_comp.get('only_in_source', []))}
                - Records Only in Target: {len(data_comp.get('only_in_target', []))}
                - Records with Field Value Differences: {data_comp.get('total_differences', 0)}
                """)

def display_field_comparison(field_data):
    """Display field comparison results"""
    st.markdown("### 📋 Field Comparison")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Source Fields", field_data.get('total_source', 0))
    with col2:
        st.metric("Target Fields", field_data.get('total_target', 0))
    with col3:
        st.metric("Common Fields", field_data.get('total_common', 0))
    with col4:
        st.metric("Differences", field_data.get('total_differences', 0))
    
    if field_data.get('only_in_source'):
        with st.expander(f"🔵 Fields Only in Source ({len(field_data['only_in_source'])})", expanded=False):
            df_source = pd.DataFrame(field_data['only_in_source'])
            st.dataframe(df_source, use_container_width=True)
    
    if field_data.get('only_in_target'):
        with st.expander(f"🟢 Fields Only in Target ({len(field_data['only_in_target'])})", expanded=False):
            df_target = pd.DataFrame(field_data['only_in_target'])
            st.dataframe(df_target, use_container_width=True)
    
    if field_data.get('differences'):
        with st.expander(f"⚠️ Field Attribute Differences ({len(field_data['differences'])})", expanded=True):
            for diff in field_data['differences']:
                st.write(f"**{diff['name']}** ({diff['label']})")
                for change in diff['differences']:
                    st.write(f"  • {change}")
                st.write("")

def display_picklist_comparison(picklist_data):
    """Display picklist comparison results"""
    st.markdown("### 🎨 Picklist Value Comparison")
    
    if picklist_data.get('differences'):
        for diff in picklist_data['differences']:
            with st.expander(f"📋 {diff['field']} ({diff['label']})", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    if diff['only_in_source']:
                        st.warning(f"**Only in Source ({len(diff['only_in_source'])}):**")
                        for val in diff['only_in_source']:
                            st.write(f"• {val}")
                
                with col2:
                    if diff['only_in_target']:
                        st.info(f"**Only in Target ({len(diff['only_in_target'])}):**")
                        for val in diff['only_in_target']:
                            st.write(f"• {val}")
    else:
        st.success("✅ All picklist values match!")

def display_recordtype_comparison(rt_data):
    """Display record type comparison results"""
    st.markdown("### 📑 Record Type Comparison")
    
    if 'error' in rt_data:
        st.warning(f"⚠️ Could not compare record types: {rt_data['error']}")
        return
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Source Record Types", rt_data.get('total_source', 0))
    with col2:
        st.metric("Target Record Types", rt_data.get('total_target', 0))
    with col3:
        st.metric("Common", len(rt_data.get('common', [])))
    
    if rt_data.get('only_in_source'):
        st.warning(f"**Only in Source:** {', '.join(rt_data['only_in_source'])}")
    
    if rt_data.get('only_in_target'):
        st.info(f"**Only in Target:** {', '.join(rt_data['only_in_target'])}")
    
    if not rt_data.get('only_in_source') and not rt_data.get('only_in_target'):
        st.success("✅ All record types match!")

def display_validation_comparison(vr_data):
    """Display validation rule comparison results"""
    st.markdown("### ✅ Validation Rule Comparison")
    
    if 'error' in vr_data:
        st.warning(f"⚠️ Could not compare validation rules: {vr_data['error']}")
        return
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Source Rules", vr_data.get('total_source', 0))
    with col2:
        st.metric("Target Rules", vr_data.get('total_target', 0))
    with col3:
        st.metric("Common", len(vr_data.get('common', [])))
    
    if vr_data.get('only_in_source'):
        st.warning(f"**Only in Source:** {', '.join(vr_data['only_in_source'])}")
    
    if vr_data.get('only_in_target'):
        st.info(f"**Only in Target:** {', '.join(vr_data['only_in_target'])}")
    
    if not vr_data.get('only_in_source') and not vr_data.get('only_in_target'):
        st.success("✅ All validation rules match!")

def generate_detailed_excel_report(comparison_result):
    """Generate a detailed Excel report with all comparison information"""
    try:
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Summary Sheet
            summary_data = {
                'Metric': [
                    'Source Organization',
                    'Source Object',
                    'Target Organization',
                    'Target Object',
                    'Report Generated',
                    'Total Differences Found',
                    'Categories Compared'
                ],
                'Value': [
                    comparison_result.get('source_org', ''),
                    comparison_result.get('source_object', ''),
                    comparison_result.get('target_org', ''),
                    comparison_result.get('target_object', ''),
                    comparison_result.get('timestamp', ''),
                    comparison_result.get('summary', {}).get('total_differences', 0),
                    comparison_result.get('summary', {}).get('categories_compared', 0)
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Field Comparison Sheet
            if 'fields' in comparison_result['comparisons']:
                fields_data = comparison_result['comparisons']['fields']
                
                # Create combined field sheet
                field_details = []
                
                # Only in source
                for field in fields_data.get('only_in_source', []):
                    field_details.append({
                        'Status': 'Only in Source',
                        'Field Name': field.get('name'),
                        'Type': field.get('type'),
                        'Label': field.get('label'),
                        'Details': ''
                    })
                
                # Only in target
                for field in fields_data.get('only_in_target', []):
                    field_details.append({
                        'Status': 'Only in Target',
                        'Field Name': field.get('name'),
                        'Type': field.get('type'),
                        'Label': field.get('label'),
                        'Details': ''
                    })
                
                # Differences
                for diff in fields_data.get('differences', []):
                    for change in diff.get('differences', []):
                        field_details.append({
                            'Status': 'Attribute Difference',
                            'Field Name': diff['name'],
                            'Type': '',
                            'Label': diff['label'],
                            'Details': change
                        })
                
                if field_details:
                    df = pd.DataFrame(field_details)
                    df.to_excel(writer, sheet_name='Fields', index=False)
            
            # Picklist Values Sheet
            if 'picklists' in comparison_result['comparisons']:
                picklist_data = comparison_result['comparisons']['picklists']
                picklist_list = []
                
                for diff in picklist_data.get('differences', []):
                    for source_val in diff.get('only_in_source', []):
                        picklist_list.append({
                            'Field': diff['field'],
                            'Label': diff['label'],
                            'Value': source_val,
                            'Status': 'Only in Source'
                        })
                    for target_val in diff.get('only_in_target', []):
                        picklist_list.append({
                            'Field': diff['field'],
                            'Label': diff['label'],
                            'Value': target_val,
                            'Status': 'Only in Target'
                        })
                
                if picklist_list:
                    df = pd.DataFrame(picklist_list)
                    df.to_excel(writer, sheet_name='Picklists', index=False)
            
            # Record Types Sheet
            if 'record_types' in comparison_result['comparisons']:
                rt_data = comparison_result['comparisons']['record_types']
                if 'error' not in rt_data:
                    rt_list = []
                    for rt in rt_data.get('only_in_source', []):
                        rt_list.append({'Record Type': rt, 'Status': 'Only in Source'})
                    for rt in rt_data.get('only_in_target', []):
                        rt_list.append({'Record Type': rt, 'Status': 'Only in Target'})
                    
                    if rt_list:
                        df = pd.DataFrame(rt_list)
                        df.to_excel(writer, sheet_name='Record Types', index=False)
            
            # Validation Rules Sheet
            if 'validation_rules' in comparison_result['comparisons']:
                vr_data = comparison_result['comparisons']['validation_rules']
                if 'error' not in vr_data:
                    vr_list = []
                    for vr in vr_data.get('only_in_source', []):
                        vr_list.append({'Validation Rule': vr, 'Status': 'Only in Source'})
                    for vr in vr_data.get('only_in_target', []):
                        vr_list.append({'Validation Rule': vr, 'Status': 'Only in Target'})
                    
                    if vr_list:
                        df = pd.DataFrame(vr_list)
                        df.to_excel(writer, sheet_name='Validation Rules', index=False)
            
            # Data Comparison Sheet
            if 'data' in comparison_result['comparisons']:
                data_comp = comparison_result['comparisons']['data']
                if data_comp.get('success'):
                    data_details = []
                    
                    # Records only in source
                    for record in data_comp.get('only_in_source', []):
                        data_details.append({
                            'Status': 'Only in Source',
                            'Record ID': record.get('Id'),
                            'Record Name': record.get('Name'),
                            'Field': '',
                            'Source Value': '',
                            'Target Value': ''
                        })
                    
                    # Records only in target
                    for record in data_comp.get('only_in_target', []):
                        data_details.append({
                            'Status': 'Only in Target',
                            'Record ID': record.get('Id'),
                            'Record Name': record.get('Name'),
                            'Field': '',
                            'Source Value': '',
                            'Target Value': ''
                        })
                    
                    # Field value differences
                    for record_diff in data_comp.get('data_differences', []):
                        for field_diff in record_diff.get('field_differences', []):
                            data_details.append({
                                'Status': 'Field Value Difference',
                                'Record ID': record_diff['Id'],
                                'Record Name': record_diff['Name'],
                                'Field': field_diff['field'],
                                'Source Value': field_diff['source_value'],
                                'Target Value': field_diff['target_value']
                            })
                    
                    if data_details:
                        df = pd.DataFrame(data_details)
                        df.to_excel(writer, sheet_name='Data Differences', index=False)
        
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        st.error(f"Error generating Excel report: {str(e)}")
        return None

def display_data_comparison(data_comparison_result):
    """Display data comparison results"""
    st.markdown("### 📊 Data Comparison")
    
    if not data_comparison_result.get('success'):
        st.error(f"❌ Data comparison failed: {data_comparison_result.get('error', 'Unknown error')}")
        return
    
    st.info(f"**Matching Fields Used:** {', '.join(data_comparison_result.get('matching_fields', ['Name']))}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Matched Records", data_comparison_result.get('common_records', 0))
    with col2:
        st.metric("Only in Source", data_comparison_result.get('unmatched_source', 0))
    with col3:
        st.metric("Only in Target", data_comparison_result.get('unmatched_target', 0))
    with col4:
        st.metric("Data Differences", data_comparison_result.get('total_differences', 0))
    
    # Records only in source
    if data_comparison_result.get('only_in_source'):
        with st.expander(f"🔵 Records Only in Source ({len(data_comparison_result['only_in_source'])})", expanded=False):
            st.write("_These records exist in source org but no matching record found in target org_")
            df_source = pd.DataFrame(data_comparison_result['only_in_source'])
            st.dataframe(df_source, use_container_width=True)
    
    # Records only in target
    if data_comparison_result.get('only_in_target'):
        with st.expander(f"🟢 Records Only in Target ({len(data_comparison_result['only_in_target'])})", expanded=False):
            st.write("_These records exist in target org but no matching record found in source org_")
            df_target = pd.DataFrame(data_comparison_result['only_in_target'])
            st.dataframe(df_target, use_container_width=True)
    
    # Data value differences
    if data_comparison_result.get('data_differences'):
        with st.expander(f"⚠️ Matched Records with Field Value Differences ({len(data_comparison_result['data_differences'])})", expanded=True):
            st.write("_These records were matched by the selected fields but have different values in other fields_")
            
            for diff in data_comparison_result['data_differences']:
                st.write(f"**Record:** {diff['matching_key']}")
                st.caption(f"Source ID: {diff['source_id']} | Target ID: {diff['target_id']}")
                
                # Create a comparison table for this record
                diff_data = []
                for field_diff in diff['field_differences']:
                    diff_data.append({
                        'Field': field_diff['field'],
                        'Source Value': field_diff['source_value'],
                        'Target Value': field_diff['target_value']
                    })
                
                df_diff = pd.DataFrame(diff_data)
                st.dataframe(df_diff, use_container_width=True, hide_index=True)
                st.write("")
    else:
        if data_comparison_result.get('common_records', 0) > 0:
            st.success("✅ All matched records have identical field values!")

def show_object_comparison():
    """Main Object Comparison interface"""
    st.title("🔍 Object Comparison")
    st.markdown("Compare Salesforce objects between two organizations to identify schema differences and data discrepancies")
    
    # Initialize session state
    if 'comparison_source_org' not in st.session_state:
        st.session_state.comparison_source_org = None
    if 'comparison_target_org' not in st.session_state:
        st.session_state.comparison_target_org = None
    if 'comparison_source_conn' not in st.session_state:
        st.session_state.comparison_source_conn = None
    if 'comparison_target_conn' not in st.session_state:
        st.session_state.comparison_target_conn = None
    if 'comparison_source_desc' not in st.session_state:
        st.session_state.comparison_source_desc = None
    if 'comparison_target_desc' not in st.session_state:
        st.session_state.comparison_target_desc = None
    
    st.markdown("### 📍 Step 1: Select Organizations")
    
    col1, col2 = st.columns(2)
    
    available_orgs = get_available_orgs()
    # Seed the pickers before they are drawn: keep the last choice (widget state is
    # dropped while the page is not shown); the source defaults to the sidebar org
    # and follows it when the sidebar org changes (the remembered choice only
    # lasts while the sidebar org stays the same).
    sidebar_org = st.session_state.get('current_org')
    if st.session_state.get("comparison_source_seeded_for") != sidebar_org:
        st.session_state["comparison_source_seeded_for"] = sidebar_org
        if sidebar_org in available_orgs:
            st.session_state["comparison_source_org_select"] = sidebar_org
    if st.session_state.get("comparison_source_org_select") not in [""] + available_orgs:
        remembered = st.session_state.comparison_source_org or sidebar_org
        st.session_state["comparison_source_org_select"] = remembered if remembered in available_orgs else ""
    if st.session_state.get("comparison_target_org_select") not in [""] + available_orgs:
        remembered = st.session_state.comparison_target_org
        st.session_state["comparison_target_org_select"] = remembered if remembered in available_orgs else ""

    with col1:
        st.markdown("#### 🔵 Source Organization")
        source_orgs = available_orgs
        
        if source_orgs:
            source_org = st.selectbox(
                "Select Source Org",
                options=[""] + source_orgs,
                key="comparison_source_org_select",
                help="Select the source organization (defaults to the sidebar org)"
            )
            
            st.session_state.comparison_source_org = source_org or None
            st.session_state.comparison_source_conn = None
            if source_org:
                # Pooled: logs in once per org, later reruns reuse the connection.
                source_conn = get_salesforce_connection(source_org)
                if source_conn:
                    st.session_state.comparison_source_conn = source_conn
                    st.success(f"✅ Connected to {source_org}")
                else:
                    st.error(f"❌ Failed to connect to {source_org}")
        else:
            st.warning("⚠️ No organizations configured")
    
    with col2:
        st.markdown("#### 🟢 Target Organization")
        target_orgs = available_orgs
        
        if target_orgs:
            target_org = st.selectbox(
                "Select Target Org",
                options=[""] + target_orgs,
                key="comparison_target_org_select",
                help="Select the target organization"
            )
            
            st.session_state.comparison_target_org = target_org or None
            st.session_state.comparison_target_conn = None
            if target_org:
                target_conn = get_salesforce_connection(target_org)
                if target_conn:
                    st.session_state.comparison_target_conn = target_conn
                    st.success(f"✅ Connected to {target_org}")
                else:
                    st.error(f"❌ Failed to connect to {target_org}")
        else:
            st.warning("⚠️ No organizations configured")
    
    if not (st.session_state.comparison_source_conn and st.session_state.comparison_target_conn):
        st.info("👆 Please select and connect to both organizations")
        return
    
    if st.session_state.comparison_source_org == st.session_state.comparison_target_org:
        st.warning("⚠️ Source and target must be different organizations")
        return
    
    st.markdown("---")
    st.markdown("### 📦 Step 2: Select Objects")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔵 Source Object")
        source_objects = get_salesforce_objects(st.session_state.comparison_source_conn, filter_custom=False)
        try:
            from ui_components import step_flow as _flow
            _flow.default_to_flow_object("comp_source_obj", source_objects)
        except ImportError:
            pass
        source_object = st.selectbox("Select Source Object", options=[""] + source_objects, key="comp_source_obj")
        
        if source_object:
            st.session_state.comparison_source_desc = get_object_description(st.session_state.comparison_source_conn, source_object)
    
    with col2:
        st.markdown("#### 🟢 Target Object")
        target_objects = get_salesforce_objects(st.session_state.comparison_target_conn, filter_custom=False)
        try:
            from ui_components import step_flow as _flow
            _flow.default_to_flow_object("comp_target_obj", target_objects)
        except ImportError:
            pass
        target_object = st.selectbox("Select Target Object", options=[""] + target_objects, key="comp_target_obj")
        
        if target_object:
            st.session_state.comparison_target_desc = get_object_description(st.session_state.comparison_target_conn, target_object)
    
    if not (source_object and target_object):
        st.info("👆 Select objects from both organizations")
        return
    
    st.markdown("---")
    st.markdown("### ⚙️ Step 3: Comparison Options")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        compare_fields = st.checkbox("Compare Fields", value=True)
        compare_record_types = st.checkbox("Compare Record Types", value=True)
    
    with col2:
        compare_picklists = st.checkbox("Compare Picklist Values", value=True)
        compare_layouts = st.checkbox("Compare Page Layouts", value=False)
    
    with col3:
        compare_validation_rules = st.checkbox("Compare Validation Rules", value=True)
        compare_data = st.checkbox("Compare Data Records", value=True)
    
    # Data comparison options
    data_comparison_config = None
    if compare_data:
        st.markdown("---")
        st.markdown("### 📊 Step 3a: Data Comparison Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            record_limit = st.slider(
                "Number of Records to Compare",
                min_value=1,
                max_value=10000,
                value=100,
                step=10,
                help="Maximum number of records to fetch from each object"
            )
        
        with col2:
            where_clause = st.text_input(
                "Optional WHERE Clause",
                value="",
                placeholder="e.g., WHERE Status = 'Active'",
                help="Optional WHERE clause to filter records (leave empty to get all records)"
            )
        
        # Field selection for comparison
        if st.session_state.comparison_source_desc:
            available_fields = [f['name'] for f in st.session_state.comparison_source_desc.get('fields', [])]
            
            # Get common fields between both objects
            if st.session_state.comparison_target_desc:
                target_fields = {f['name'] for f in st.session_state.comparison_target_desc.get('fields', [])}
                common_fields = [f for f in available_fields if f in target_fields]
            else:
                common_fields = available_fields
            
            st.markdown("**Select Fields to Use for Matching Records:**")
            st.caption("_Records in different orgs have different IDs. Choose which field(s) to use to identify the same record across orgs (e.g., Name, Email, Account Number)_")
            
            # Matching field selection with "Select All" option
            # Exclude ID field from matching
            matchable_fields = [f for f in common_fields if f.lower() != 'id']
            default_matching_fields = ['Name'] if 'Name' in matchable_fields else matchable_fields[:1] if matchable_fields else []
            
            # Add Select All checkbox
            col1, col2 = st.columns([1, 4])
            with col1:
                select_all_matching = st.checkbox("✓ All Fields", value=False, key="select_all_matching_fields",
                                                   help="Select all available fields (excluding ID) for record matching")
            
            if select_all_matching:
                # If Select All is checked, use all fields except ID
                matching_fields = matchable_fields
                st.info(f"📌 Matching with all fields: {', '.join(matching_fields)}")
            else:
                # Otherwise, let user select specific fields
                matching_fields = st.multiselect(
                    "Matching Fields (records with same values in these fields are considered matching)",
                    options=matchable_fields,
                    default=default_matching_fields,
                    key="data_matching_fields",
                    help="Use fields that uniquely identify records (e.g., Name, Email, Account Number)"
                )
            
            if not matching_fields:
                st.warning("⚠️ Please select at least one field for matching records")
                return
            
            # Use all common fields except matching fields for comparison
            fields_to_compare = [f for f in common_fields if f not in matching_fields]
            
            data_comparison_config = {
                'record_limit': record_limit,
                'where_clause': where_clause,
                'fields': fields_to_compare if fields_to_compare else common_fields,
                'matching_fields': matching_fields
            }
    
    st.markdown("---")
    st.markdown("### 🚀 Step 4: Run Comparison")
    
    if st.button("🔍 Compare Objects", type="primary", use_container_width=True):
        with st.spinner("🔄 Comparing objects..."):
            result = compare_salesforce_objects(
                source_conn=st.session_state.comparison_source_conn,
                target_conn=st.session_state.comparison_target_conn,
                source_org=st.session_state.comparison_source_org,
                target_org=st.session_state.comparison_target_org,
                source_object=source_object,
                target_object=target_object,
                options={
                    'compare_fields': compare_fields,
                    'compare_record_types': compare_record_types,
                    'compare_picklists': compare_picklists,
                    'compare_layouts': compare_layouts,
                    'compare_validation_rules': compare_validation_rules,
                    'compare_data': compare_data,
                    'data_config': data_comparison_config
                }
            )
            
            if result and result.get('success'):
                st.session_state.comparison_result = result
                st.success("✅ Comparison completed!")
                st.rerun()
            else:
                st.error(f"❌ Comparison failed: {result.get('error', 'Unknown error')}")
    
    if hasattr(st.session_state, 'comparison_result') and st.session_state.comparison_result:
        st.markdown("---")
        display_comparison_results(st.session_state.comparison_result)
