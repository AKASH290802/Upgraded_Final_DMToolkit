"""
Organization Migration - Data Preview & Review Module
Provides interactive data preview, sampling, and pre-flight validation checks.
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Any, Tuple
from datetime import datetime
import json


def generate_data_summary(data: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate comprehensive data summary statistics.
    
    Args:
        data: DataFrame to summarize
    
    Returns:
        Dict with summary statistics
    """
    summary = {
        'total_records': len(data),
        'total_fields': len(data.columns),
        'column_names': list(data.columns),
        'data_types': data.dtypes.to_dict(),
        'memory_usage': f"{data.memory_usage(deep=True).sum() / 1024**2:.2f} MB",
        'null_summary': {},
        'sample_values': {}
    }
    
    # Null value summary
    for col in data.columns:
        null_count = data[col].isna().sum()
        summary['null_summary'][col] = {
            'null_count': int(null_count),
            'non_null': int(len(data) - null_count),
            'null_percent': f"{(null_count / len(data) * 100):.1f}%"
        }
    
    # Sample values per column
    for col in data.columns:
        try:
            non_null_values = data[data[col].notna()][col].unique()
            sample_size = min(3, len(non_null_values))
            summary['sample_values'][col] = [str(v) for v in non_null_values[:sample_size]]
        except:
            summary['sample_values'][col] = []
    
    return summary


def display_data_overview(data: pd.DataFrame):
    """
    Display data overview with summary statistics.
    
    Args:
        data: DataFrame to display
    """
    summary = generate_data_summary(data)
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", summary['total_records'])
    
    with col2:
        st.metric("Total Fields", summary['total_fields'])
    
    with col3:
        st.metric("Memory Size", summary['memory_usage'])
    
    with col4:
        null_cols = sum(1 for v in summary['null_summary'].values() if v['null_count'] > 0)
        st.metric("Fields with Nulls", null_cols)
    
    st.divider()
    
    # Column details
    st.subheader("📋 Column Details")
    
    col_info = []
    for col in summary['column_names']:
        null_info = summary['null_summary'][col]
        col_info.append({
            'Field': col,
            'Type': str(summary['data_types'][col]),
            'Non-Null': null_info['non_null'],
            'Null %': null_info['null_percent'],
            'Sample Values': ', '.join(summary['sample_values'][col])
        })
    
    col_df = pd.DataFrame(col_info)
    st.dataframe(col_df, use_container_width=True, hide_index=True)


def display_data_samples(data: pd.DataFrame, num_samples: int = 5):
    """
    Display random sample records from data.
    
    Args:
        data: DataFrame to sample from
        num_samples: Number of random samples to show
    """
    if len(data) == 0:
        st.info("No data to preview")
        return
    
    st.subheader("🎯 Random Sample Records")
    
    sample_size = min(num_samples, len(data))
    sample_data = data.sample(n=sample_size, random_state=42).reset_index(drop=True)
    
    st.dataframe(sample_data, use_container_width=True, height=min(400, sample_size * 50 + 100))
    
    st.caption(f"Showing {sample_size} random records out of {len(data)} total")


def check_pre_flight_validations(data: pd.DataFrame, validations_config: Dict = None) -> Dict[str, Any]:
    """
    Run pre-flight validation checks before migration.
    Checks that all previous validation steps passed.
    
    Args:
        data: DataFrame to validate
        validations_config: Configuration for pre-flight checks
    
    Returns:
        Pre-flight validation results
    """
    results = {
        'total_checks': 0,
        'passed_checks': 0,
        'checks': {},
        'ready_for_migration': True,
        'blocking_issues': [],
        'warnings': []
    }
    
    if len(data) == 0:
        results['ready_for_migration'] = False
        results['blocking_issues'].append("No data loaded")
        return results
    
    validations_config = validations_config or {}
    
    # Check 1: Data is not empty
    results['total_checks'] += 1
    if len(data) > 0:
        results['passed_checks'] += 1
        results['checks']['data_exists'] = {'passed': True, 'message': f'{len(data)} records loaded'}
    else:
        results['ready_for_migration'] = False
        results['blocking_issues'].append("Dataset is empty")
        results['checks']['data_exists'] = {'passed': False, 'message': 'No data loaded'}
    
    # Check 2: Required columns exist
    results['total_checks'] += 1
    required_cols = validations_config.get('required_columns', [])
    missing_cols = [col for col in required_cols if col not in data.columns]
    
    if not missing_cols:
        results['passed_checks'] += 1
        results['checks']['required_columns'] = {'passed': True, 'message': f'All {len(required_cols)} required columns present'}
    else:
        results['ready_for_migration'] = False
        results['blocking_issues'].append(f"Missing required columns: {', '.join(missing_cols)}")
        results['checks']['required_columns'] = {'passed': False, 'message': f'Missing columns: {missing_cols}'}
    
    # Check 3: No critical nulls in required fields
    results['total_checks'] += 1
    critical_fields = validations_config.get('critical_fields', [])
    critical_nulls = {}
    
    for field in critical_fields:
        if field in data.columns:
            null_count = data[field].isna().sum()
            if null_count > 0:
                critical_nulls[field] = null_count
    
    if not critical_nulls:
        results['passed_checks'] += 1
        results['checks']['no_critical_nulls'] = {'passed': True, 'message': 'No nulls in critical fields'}
    else:
        results['ready_for_migration'] = False
        null_msg = '; '.join([f'{k}: {v} records' for k, v in critical_nulls.items()])
        results['blocking_issues'].append(f"Critical field nulls detected: {null_msg}")
        results['checks']['no_critical_nulls'] = {'passed': False, 'message': f'Nulls in: {list(critical_nulls.keys())}'}
    
    # Check 4: Field count matches expected
    results['total_checks'] += 1
    expected_field_count = validations_config.get('expected_field_count')
    
    if expected_field_count is None or len(data.columns) == expected_field_count:
        results['passed_checks'] += 1
        results['checks']['field_count'] = {'passed': True, 'message': f'{len(data.columns)} fields'}
    else:
        results['warnings'].append(f"Expected {expected_field_count} fields but found {len(data.columns)}")
        results['checks']['field_count'] = {'passed': False, 'message': f'Expected {expected_field_count}, got {len(data.columns)}'}
    
    # Check 5: File size is reasonable
    results['total_checks'] += 1
    max_size_mb = validations_config.get('max_size_mb', 500)
    data_size_mb = data.memory_usage(deep=True).sum() / 1024**2
    
    if data_size_mb <= max_size_mb:
        results['passed_checks'] += 1
        results['checks']['file_size'] = {'passed': True, 'message': f'{data_size_mb:.2f} MB'}
    else:
        results['warnings'].append(f"Large file size: {data_size_mb:.2f} MB (max: {max_size_mb} MB)")
        results['checks']['file_size'] = {'passed': False, 'message': f'{data_size_mb:.2f} MB (max: {max_size_mb})'}
    
    return results


def generate_pre_flight_report(data: pd.DataFrame, validation_history: Dict = None) -> str:
    """
    Generate comprehensive pre-flight validation report.
    
    Args:
        data: DataFrame being validated
        validation_history: Previous validation results
    
    Returns:
        HTML/Markdown formatted report
    """
    summary = generate_data_summary(data)
    
    report = f"""
# Pre-Flight Validation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Dataset Overview
- **Total Records:** {summary['total_records']:,}
- **Total Fields:** {summary['total_fields']}
- **Memory Size:** {summary['memory_usage']}

## Field Summary
| Field | Type | Non-Null | Null % |
|-------|------|----------|--------|
"""
    
    for col in summary['column_names']:
        null_info = summary['null_summary'][col]
        report += f"| {col} | {summary['data_types'][col]} | {null_info['non_null']} | {null_info['null_percent']} |\n"
    
    report += """

## Validation Checklist
- ☐ Schema Validation Passed
- ☐ Business Rules Passed
- ☐ Data Quality Checks Passed
- ☐ Duplicate Detection Passed
- ☐ Referential Integrity Passed
- ☐ Data Completeness Passed

## Next Steps
1. Review any flagged issues above
2. Make necessary corrections to source data
3. Re-upload and re-validate if changes made
4. Proceed to Execute Migration tab when all checks pass
5. Monitor migration execution in real-time

## Migration Readiness
✅ Ready for migration (all checks passed)

---
*Report generated by DM Toolkit Org Migration Pre-Flight Check*
"""
    
    return report


def display_validation_summary(session_state) -> Dict[str, bool]:
    """
    Display summary of all validation steps completed.
    
    Args:
        session_state: Streamlit session state
    
    Returns:
        Dict indicating which validations passed
    """
    validation_status = {
        'pre_migration': False,
        'business_rules': False,
        'data_quality': False,
        'lookup_ready': False
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pre-Migration Validation status
        if 'migration_validation_results' in session_state:
            all_passed = all(
                r.get('passed', False) 
                for r in session_state.migration_validation_results.get('validation_details', {}).values()
            )
            status_icon = "✅" if all_passed else "❌"
            st.write(f"{status_icon} **Pre-Migration Validation:** {'Passed' if all_passed else 'Has Issues'}")
            validation_status['pre_migration'] = all_passed
        else:
            st.write("⏳ **Pre-Migration Validation:** Not Run")
        
        # Business Rules status
        if 'business_rules_validation' in session_state:
            rules_passed = session_state.business_rules_validation.get('passed', False)
            status_icon = "✅" if rules_passed else "❌"
            failed_count = session_state.business_rules_validation.get('failed', 0)
            rules_text = 'Passed' if rules_passed else f'Failed ({failed_count} records)'
            st.write(f"{status_icon} **Business Rules:** {rules_text}")
            validation_status['business_rules'] = rules_passed
        else:
            st.write("⏳ **Business Rules:** Not Run")
    
    with col2:
        # Data Quality status
        if 'quality_check_results' in session_state:
            quality_passed = session_state.quality_check_results.get('pass', False)
            score = 0
            total_checks = len(session_state.quality_check_results.get('checks', {}))
            passed_checks = sum(1 for check in session_state.quality_check_results.get('checks', {}).values() 
                              if check.get('pass', False))
            if total_checks > 0:
                score = (passed_checks / total_checks * 100)
            status_icon = "✅" if quality_passed else "❌"
            st.write(f"{status_icon} **Data Quality:** {score:.0f}% ({'Passed' if quality_passed else 'Has Issues'})")
            validation_status['data_quality'] = quality_passed
        else:
            st.write("⏳ **Data Quality:** Not Run")
        
        # Lookup configuration status
        if 'migration_lookup_configs' in session_state and session_state.migration_lookup_configs:
            st.write(f"✅ **Lookup Resolution:** Configured ({len(session_state.migration_lookup_configs)} configs)")
            validation_status['lookup_ready'] = True
        else:
            st.write("⏳ **Lookup Resolution:** Not Configured")
    
    return validation_status


def create_migration_checklist(session_state) -> List[Tuple[str, bool]]:
    """
    Create migration readiness checklist.
    
    Args:
        session_state: Streamlit session state
    
    Returns:
        List of (item, is_complete) tuples
    """
    checklist = []
    
    # Configuration complete
    config_complete = (
        'migration_org_pair' in session_state and 
        'migration_object' in session_state
    )
    checklist.append(("✓ Configuration Complete", config_complete))
    
    # Field mapping complete
    mapping_complete = (
        'migration_field_mappings' in session_state and 
        len(session_state.migration_field_mappings) > 0
    )
    checklist.append(("✓ Field Mapping Complete", mapping_complete))
    
    # Pre-migration validation done
    pre_mig_done = 'migration_validation_results' in session_state
    checklist.append(("✓ Pre-Migration Validation Complete", pre_mig_done))
    
    # Business rules validation done
    business_rules_done = 'business_rules_validation' in session_state
    checklist.append(("✓ Business Rules Validation Complete", business_rules_done))
    
    # Data quality checks done
    quality_done = 'quality_check_results' in session_state
    checklist.append(("✓ Data Quality Checks Complete", quality_done))
    
    # Lookup resolution configured
    lookup_config = (
        'migration_lookup_configs' in session_state and 
        len(session_state.migration_lookup_configs) > 0
    )
    checklist.append(("✓ Lookup Resolution Configured", lookup_config))
    
    # Data loaded and ready
    data_ready = 'migration_data' in session_state
    checklist.append(("✓ Migration Data Ready", data_ready))
    
    return checklist


def display_migration_readiness(session_state) -> bool:
    """
    Display migration readiness status and checklist.
    
    Args:
        session_state: Streamlit session state
    
    Returns:
        True if ready for migration, False otherwise
    """
    checklist = create_migration_checklist(session_state)
    
    st.subheader("📋 Migration Readiness Checklist")
    
    all_complete = True
    for item, is_complete in checklist:
        icon = "✅" if is_complete else "⏳"
        st.write(f"{icon} {item}")
        if not is_complete:
            all_complete = False
    
    st.divider()
    
    if all_complete:
        st.success("🎉 **All pre-flight checks complete! Ready for migration.**")
        return True
    else:
        incomplete_items = [item for item, is_complete in checklist if not is_complete]
        st.warning(f"⚠️ **{len(incomplete_items)} items still need to be completed:**")
        for item in incomplete_items:
            st.write(f"  • {item.replace('✓ ', '').replace(' Complete', '')}")
        return False


def summarize_validation_findings(session_state) -> Dict[str, Any]:
    """
    Summarize all validation findings from previous steps.
    
    Args:
        session_state: Streamlit session state
    
    Returns:
        Summary of all issues and recommendations
    """
    summary = {
        'total_issues': 0,
        'blocking_issues': [],
        'warnings': [],
        'info_items': [],
        'overall_risk': 'LOW'
    }
    
    # Schema validation issues
    if 'migration_validation_results' in session_state:
        results = session_state.migration_validation_results
        for check_name, check_result in results.get('validation_details', {}).items():
            if not check_result.get('passed', False):
                summary['total_issues'] += 1
                summary['blocking_issues'].append(f"Schema: {check_result.get('message', check_name)}")
    
    # Business rules violations
    if 'business_rules_validation' in session_state:
        results = session_state.business_rules_validation
        if not results.get('pass', False):
            failed = results.get('failed', 0)
            summary['total_issues'] += len(results.get('validation_details', []))
            summary['warnings'].append(f"Business Rules: {failed} records violate rules")
    
    # Data quality issues
    if 'quality_check_results' in session_state:
        results = session_state.quality_check_results
        if not results.get('pass', False):
            for check_name, check_result in results.get('checks', {}).items():
                if not check_result.get('pass', True):
                    if check_name == 'duplicates':
                        dup_count = check_result.get('duplicate_count', 0)
                        summary['total_issues'] += 1
                        summary['warnings'].append(f"Quality: {dup_count} duplicate records found")
                    elif check_name == 'completeness':
                        issues = len(check_result.get('issues', []))
                        summary['total_issues'] += issues
                        summary['warnings'].append(f"Quality: {issues} completeness issues")
    
    # Determine risk level
    if summary['blocking_issues']:
        summary['overall_risk'] = 'HIGH'
    elif len(summary['warnings']) >= 3:
        summary['overall_risk'] = 'MEDIUM'
    else:
        summary['overall_risk'] = 'LOW'
    
    return summary
