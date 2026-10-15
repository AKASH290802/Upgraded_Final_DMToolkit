"""
Child Object Lookup Resolution Module
Handles auto-detection, configuration, and optimized resolution of child object lookups
with batch processing and parallel execution for performance
"""

import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# PHASE 1: AUTO-DETECTION OF CHILD OBJECT LOOKUP FIELDS
# ============================================================================

# System-managed lookup fields that users cannot/should not configure
_SYSTEM_LOOKUP_FIELDS = frozenset({
    'CreatedById', 'LastModifiedById', 'OwnerId', 'RecordTypeId',
    'MasterRecordId', 'LastActivityDate', 'LastViewedDate', 'LastReferencedDate',
    'SystemModstamp'
})


def detect_child_object_lookups(sf_conn, child_object_name: str) -> List[Dict[str, Any]]:
    """
    Auto-detect business lookup fields in a child object (system fields excluded).

    Args:
        sf_conn: Salesforce connection
        child_object_name: Name of child object (e.g., 'Contact', 'Opportunity')

    Returns:
        List of dicts: [{'field_name': str, 'reference_to': [str], 'type': str}, ...]
    """
    try:
        obj_desc = getattr(sf_conn, child_object_name).describe()

        lookup_fields = []
        for field in obj_desc['fields']:
            if field.get('type') not in ('reference', 'masterdetail'):
                continue
            name = field['name']
            if name in _SYSTEM_LOOKUP_FIELDS:
                continue
            ref_to = field.get('referenceTo', [])
            if not ref_to:
                continue
            lookup_fields.append({
                'field_name': name,
                'reference_to': list(ref_to),
                'type': field['type']
            })

        return lookup_fields
    except Exception as e:
        logger.error(f"Error detecting lookups in {child_object_name}: {str(e)}")
        return []


def build_child_lookup_metadata(sf_conn, selected_children: List[str]) -> Dict[str, List[Dict]]:
    """
    Build metadata for all selected child objects' lookup fields.
    Uses concurrent execution for speed.

    Args:
        sf_conn: Salesforce connection
        selected_children: List of selected child object names

    Returns:
        Dict: {child_object: [{field_name, reference_to, type}, ...]}
    """
    metadata = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_child = {
            executor.submit(detect_child_object_lookups, sf_conn, child): child
            for child in selected_children
        }

        for future in as_completed(future_to_child):
            child = future_to_child[future]
            try:
                lookups = future.result()
                if lookups:
                    metadata[child] = lookups
            except Exception as e:
                logger.error(f"Failed to get lookups for {child}: {str(e)}")

    return metadata


# ============================================================================
# PHASE 2: AUTO-CONFIGURATION OF CHILD LOOKUP STRATEGIES
# ============================================================================

def auto_configure_child_lookup_strategies(
    target_sf,
    child_object: str,
    lookup_fields: List[str]
) -> Dict[str, Dict]:
    """
    Auto-configure matching strategies for child object lookups
    Intelligently selects best strategy based on available fields
    
    Args:
        target_sf: Target Salesforce connection
        child_object: Child object name
        lookup_fields: List of lookup field names
    
    Returns:
        Dict: {
            'lookup_field': {
                'parent_object': 'Parent',
                'match_strategy': 'external_id|unique_field|field_combination',
                'match_fields': ['FieldName']
            }
        }
    """
    configs = {}
    
    try:
        obj_desc = getattr(target_sf, child_object).describe()
        field_map = {f['name']: f for f in obj_desc['fields']}
        
        for lookup_field in lookup_fields:
            if lookup_field not in field_map:
                continue
            
            field_info = field_map[lookup_field]
            parent_objects = field_info.get('referenceTo', [])
            
            if not parent_objects:
                continue
            
            parent_object = parent_objects[0]
            
            # Try to auto-detect best matching strategy
            strategy = _detect_best_matching_strategy(target_sf, parent_object, lookup_field)
            
            configs[lookup_field] = {
                'parent_object': parent_object,
                'match_strategy': strategy['strategy'],
                'match_fields': strategy['fields']
            }
    
    except Exception as e:
        logger.error(f"Error auto-configuring lookups for {child_object}: {str(e)}")
    
    return configs


def _detect_best_matching_strategy(target_sf, parent_object: str, lookup_field: str) -> Dict:
    """
    Detect the best matching strategy for a parent object
    Priority: external_id > unique_field > field_combination
    
    Returns:
        Dict: {'strategy': 'external_id|unique_field|...', 'fields': [field_names]}
    """
    try:
        parent_desc = getattr(target_sf, parent_object).describe()
        parent_fields = parent_desc['fields']
        
        # Check for external ID fields
        ext_id_fields = [f['name'] for f in parent_fields if f.get('externalIdTrackingEnabled')]
        if ext_id_fields:
            return {
                'strategy': 'external_id',
                'fields': [ext_id_fields[0]]
            }
        
        # Check for unique fields
        unique_fields = [f['name'] for f in parent_fields if f.get('unique') and not f.get('autoNumber')]
        if unique_fields:
            return {
                'strategy': 'unique_field',
                'fields': [unique_fields[0]]
            }
        
        # Fallback: use Name or any string field
        name_fields = [f['name'] for f in parent_fields if f['name'] in ['Name', 'DeveloperName']]
        if name_fields:
            return {
                'strategy': 'field_combination',
                'fields': [name_fields[0]]
            }
        
        # Last resort: use any string field
        string_fields = [f['name'] for f in parent_fields if f['type'] in ['string', 'email']]
        if string_fields:
            return {
                'strategy': 'field_combination',
                'fields': [string_fields[0]]
            }
    
    except Exception as e:
        logger.error(f"Error detecting strategy for {parent_object}: {str(e)}")
    
    return {'strategy': 'field_combination', 'fields': ['Name']}


# ============================================================================
# PHASE 3: OPTIMIZED CHILD LOOKUP RESOLUTION (BATCH + PARALLEL)
# ============================================================================

def resolve_child_object_lookups_optimized(
    child_df: pd.DataFrame,
    child_object: str,
    source_sf,
    target_sf,
    child_lookup_configs: Dict,
    parent_id_mapping: Dict[str, str],
    progress_callback=None
) -> Tuple[pd.DataFrame, Dict]:
    """
    Optimized resolution of child object lookups
    Uses batch queries and parallel processing for speed
    
    Args:
        child_df: Child object DataFrame with source IDs
        child_object: Child object name (e.g., 'Contact')
        source_sf: Source Salesforce connection
        target_sf: Target Salesforce connection
        child_lookup_configs: Lookup configurations for this child
        parent_id_mapping: Mapping of source parent IDs to target parent IDs
        progress_callback: Optional callback for progress updates
    
    Returns:
        Tuple: (resolved_df, resolution_stats)
    """
    resolved_df = child_df.copy()
    resolution_stats = {
        'resolved': {},
        'unresolved': {},
        'total_lookups': 0,
        'total_resolved': 0,
        'total_unresolved': 0
    }
    
    if not child_lookup_configs:
        return resolved_df, resolution_stats
    
    # First: Identify which column is the parent reference (usually ends with 'Id')
    parent_ref_field = _find_parent_reference_field(child_df.columns)
    
    # Execute lookups in parallel for speed
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        
        for lookup_field, config in child_lookup_configs.items():
            future = executor.submit(
                _resolve_single_lookup_batched,
                child_df=resolved_df,
                lookup_field=lookup_field,
                config=config,
                source_sf=source_sf,
                target_sf=target_sf,
                parent_id_mapping=parent_id_mapping,
                parent_ref_field=parent_ref_field
            )
            futures[future] = lookup_field
        
        # Collect results as they complete
        for future in as_completed(futures):
            lookup_field = futures[future]
            try:
                result_df, stats = future.result()
                resolved_df = result_df
                resolution_stats['resolved'][lookup_field] = stats['resolved']
                resolution_stats['unresolved'][lookup_field] = stats['unresolved']
                resolution_stats['total_lookups'] += stats['resolved'] + stats['unresolved']
                resolution_stats['total_resolved'] += stats['resolved']
                resolution_stats['total_unresolved'] += stats['unresolved']
                
                if progress_callback:
                    progress_callback(f"✅ Resolved {lookup_field}: {stats['resolved']} matched")
            
            except Exception as e:
                logger.error(f"Error resolving {lookup_field}: {str(e)}")
                if progress_callback:
                    progress_callback(f"❌ Failed to resolve {lookup_field}: {str(e)}")
    
    return resolved_df, resolution_stats


def _find_parent_reference_field(columns: List[str]) -> Optional[str]:
    """Find the parent reference field (usually AccountId, ParentId, etc.)"""
    common_parent_fields = [
        'AccountId', 'ParentId', 'OwnerId', 'ContactId',
        'LeadId', 'OpportunityId', 'CaseId', 'ContractId'
    ]
    
    for field in columns:
        if field in common_parent_fields:
            return field
    
    # Fallback: find any field ending with 'Id' that looks like a parent ref
    for field in columns:
        if field.endswith('Id') and field != 'Id':
            return field
    
    return None


def _resolve_single_lookup_batched(
    child_df: pd.DataFrame,
    lookup_field: str,
    config: Dict,
    source_sf,
    target_sf,
    parent_id_mapping: Dict[str, str],
    parent_ref_field: Optional[str]
) -> Tuple[pd.DataFrame, Dict]:
    """
    Resolve a single lookup field using batch processing
    Optimized to minimize API calls
    """
    result_df = child_df.copy()
    stats = {'resolved': 0, 'unresolved': 0}
    
    if lookup_field not in result_df.columns:
        return result_df, stats
    
    parent_object = config.get('parent_object')
    match_strategy = config.get('match_strategy', 'external_id')
    match_fields = config.get('match_fields', [])
    
    try:
        # Get unique source parent IDs from lookup column (batch operation)
        unique_source_ids = result_df[lookup_field].dropna().unique()
        
        if len(unique_source_ids) == 0:
            return result_df, stats
        
        # BATCH 1: Query source org for match field values
        # Use IN clause for bulk querying
        source_match_values = _batch_query_source(
            source_sf, parent_object, unique_source_ids, match_fields
        )
        
        # BATCH 2: Query target org for matching records
        # All at once using IN clause
        target_id_map = _batch_query_target(
            target_sf, parent_object, list(source_match_values.values()), match_fields
        )
        
        # BATCH 3: Map source IDs to target IDs
        source_to_target = {}
        for source_id, match_value in source_match_values.items():
            if match_value in target_id_map:
                source_to_target[source_id] = target_id_map[match_value]
        
        # Update DataFrame with resolved lookups
        for idx, source_id in enumerate(result_df[lookup_field]):
            if pd.isna(source_id):
                continue
            
            source_id_str = str(source_id)
            if source_id_str in source_to_target:
                result_df.at[idx, lookup_field] = source_to_target[source_id_str]
                stats['resolved'] += 1
            else:
                result_df.at[idx, lookup_field] = None
                stats['unresolved'] += 1
    
    except Exception as e:
        logger.error(f"Error in batch lookup resolution for {lookup_field}: {str(e)}")
    
    return result_df, stats


def _batch_query_source(source_sf, object_name: str, source_ids: List[str], match_fields: List[str]) -> Dict:
    """
    Batch query source org to get match field values
    Uses single SOQL query with IN clause instead of per-ID queries
    """
    results = {}
    
    try:
        if not source_ids or not match_fields:
            return results
        
        # Convert IDs to proper format for SOQL
        id_list = "','".join([str(id).replace("'", "") for id in source_ids[:200]])  # SOQL limit
        match_field_str = ', '.join(match_fields)
        
        # Single batch query
        soql = f"SELECT Id, {match_field_str} FROM {object_name} WHERE Id IN ('{id_list}')"
        
        response = source_sf.query(soql)
        
        for record in response.get('records', []):
            record_id = record.get('Id')
            # Get first match field value
            match_value = record.get(match_fields[0]) if match_fields else None
            if record_id and match_value:
                results[str(record_id)] = str(match_value)
    
    except Exception as e:
        logger.error(f"Batch query error for {object_name}: {str(e)}")
    
    return results


def _batch_query_target(target_sf, object_name: str, match_values: List[str], match_fields: List[str]) -> Dict:
    """
    Batch query target org to find IDs matching the values
    Returns: {match_value: target_id}
    """
    results = {}
    
    try:
        if not match_values or not match_fields:
            return results
        
        # Process in chunks (SOQL IN clause has limits)
        chunk_size = 200
        match_field = match_fields[0] if match_fields else 'Name'
        
        for i in range(0, len(match_values), chunk_size):
            chunk = match_values[i:i + chunk_size]
            value_list = "','".join([str(v).replace("'", "") for v in chunk])
            
            soql = f"SELECT Id, {match_field} FROM {object_name} WHERE {match_field} IN ('{value_list}')"
            
            response = target_sf.query(soql)
            
            for record in response.get('records', []):
                match_value = record.get(match_field)
                target_id = record.get('Id')
                if match_value and target_id:
                    results[str(match_value)] = target_id
    
    except Exception as e:
        logger.error(f"Batch target query error for {object_name}: {str(e)}")
    
    return results


# ============================================================================
# PHASE 3B: PARENT ID REMAPPING FOR CHILD RECORDS
# ============================================================================

def remap_child_parent_ids(
    child_df: pd.DataFrame,
    parent_id_mapping: Dict[str, str],
    parent_ref_field: str = 'AccountId'
) -> pd.DataFrame:
    """
    Remap child records' parent ID references to target org IDs
    Fast operation - just dict lookups
    
    Args:
        child_df: Child DataFrame with source parent IDs
        parent_id_mapping: Dict of source_parent_id -> target_parent_id
        parent_ref_field: Name of the parent reference column (e.g., 'AccountId')
    
    Returns:
        DataFrame with remapped parent IDs
    """
    remapped_df = child_df.copy()
    
    if parent_ref_field not in remapped_df.columns:
        logger.warning(f"Parent reference field '{parent_ref_field}' not found in child DataFrame")
        return remapped_df
    
    # Vectorized mapping using pandas map (faster than iterrows)
    remapped_df[parent_ref_field] = remapped_df[parent_ref_field].astype(str).map(
        lambda x: parent_id_mapping.get(x, x) if pd.notna(x) else None
    )
    
    return remapped_df


def get_parent_id_mapping_from_results(load_results: List[Dict]) -> Dict[str, str]:
    """
    Extract source → target ID mapping from Salesforce load results
    
    Args:
        load_results: List of Salesforce bulk API results
    
    Returns:
        Dict: {source_id: target_id, ...}
    """
    mapping = {}
    
    try:
        for result in load_results:
            source_id = result.get('external_id')  # From input
            target_id = result.get('id') or result.get('Id')  # From response
            
            if source_id and target_id:
                mapping[str(source_id)] = str(target_id)
    
    except Exception as e:
        logger.error(f"Error extracting ID mapping: {str(e)}")
    
    return mapping
