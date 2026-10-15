"""
Org Migration - Related Objects Discovery & Extraction Module
Handles discovering, extracting, and managing child records for org migration

Key Concepts:
- Master-Detail: Parent-child relationship where child cannot exist without parent
- Lookup: Optional reference to another object
- Child objects: Objects that have a lookup/master-detail to the main object
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Tuple, Optional
from simple_salesforce import Salesforce
import json


# ---------------------------------------------------------------------------
# System / platform object detection
# ---------------------------------------------------------------------------
# API name suffixes that always mean system-generated objects
_SYSTEM_SUFFIXES = ('__Share', '__History', '__Feed', '__ChangeEvent', '__Event',
                    '__ViewStat', '__VoteStat')

# Exact API names (case-sensitive) for well-known system objects
_SYSTEM_EXACT = frozenset({
    'ActivityHistory', 'OpenActivity', 'AgentWork', 'AgentWorkItem',
    'EventRelation', 'TaskRelation', 'TaskWhoRelation', 'TaskWhatRelation',
    'Attachment', 'ContentDocumentLink', 'ContentDelivery', 'ContentVersion',
    'ContentDistribution',
    'FeedItem', 'FeedComment', 'FeedLike', 'FeedPollChoice', 'FeedPollVote',
    'FeedRevision', 'FeedSignal', 'FeedTrackedChange', 'EntitySubscription',
    'DuplicateRecordItem', 'DuplicateRecordSet',
    'TopicAssignment', 'LabelAssignment', 'TagDefinition',
    'Note',
    'ProcessInstance', 'ProcessInstanceWorkitem', 'ProcessInstanceHistory',
    'ProcessInstanceNode', 'ProcessException', 'RecordAction',
    'FlowRecordRelation',
    'PendingServiceRouting',
    'CollaborationGroupRecord', 'UserRecordAccess', 'GroupRecord', 'SiteDetail',
    'ObjectTag', 'AccountTag', 'ContactTag', 'LeadTag', 'OpportunityTag',
    'CaseTag', 'TaskTag', 'EventTag',
})

# Substrings (lowercase) whose presence in the API name indicates a system object.
# This catches objects whose exact API names vary by org/edition, e.g.:
#   ExperienceUserAccessHistoryRecent, ObjectRelatedUrl, LabelAssignment variants
_SYSTEM_SUBSTRINGS = (
    'accesshistory',        # ExperienceUserAccessHistoryRecent, etc.
    'accesshist',           # Truncated variants: AccessHistRecent, AccessHistoryRecent
    'historyrecent',        # Any *HistoryRecent system audit object
    'histrecent',           # Truncated: *HistRecent
    'usagehistory',
    'relatedurl',           # ObjectRelatedUrl / ObjectRelatedURL
    'labelassignment',      # LabelAssignment variants
    'topicassignment',
    'duplicaterecord',
    'entitysubscription',
    'experienceuser',       # Experience Cloud system objects
    'collaborationgroup',
    'useraccess',
    'flowrecord',
    'agentwork',
    'pendingservice',
    'processinstance',
    'recordaction',
    'contenttag',
    'contentdelivery',
    'contentdocument',
    'feeditem', 'feedcomment', 'feedlike', 'feedpoll', 'feedrevision',
    'feedsignal', 'feedtracked',
)


def _is_system_child(obj_name: str) -> bool:
    """Return True if the object is a Salesforce platform/system object to exclude."""
    # 1. Exact match
    if obj_name in _SYSTEM_EXACT:
        return True
    # 2. Suffix match (case-sensitive — Salesforce suffixes are always same case)
    if obj_name.endswith(_SYSTEM_SUFFIXES):
        return True
    # 3. Substring match (case-insensitive — catches API name variants across editions)
    obj_lower = obj_name.lower()
    if any(sub in obj_lower for sub in _SYSTEM_SUBSTRINGS):
        return True
    return False


def discover_child_objects(sf_conn: Salesforce, parent_object: str) -> Dict[str, Dict]:
    """
    Discover all child objects related to the parent object.

    ⚡ OPTIMIZED (2 API calls total instead of N+1):
      - Call 1: parent describe → childRelationships (has cascadeDelete for type detection)
      - Call 2: sf_conn.describe() → all object labels + createable flags (cached in session state)
      No individual child describe() calls are made.

    System/platform objects (Attachment, FeedItem, ContentDocumentLink, etc.) are
    automatically excluded — only actual business child objects are returned.

    Args:
        sf_conn: Salesforce connection
        parent_object: Parent object name (e.g., 'Account', 'Questionnaire')

    Returns:
        Dictionary with structure:
        {
            "child_object_name": {
                "relationship_name": "relationship_api_name",
                "relationship_type": "master_detail" or "lookup",
                "field_name": "field_api_name",
                "field_label": "Field Label",
                "is_required": True/False,
                "child_object_label": "Child Object Label",
                "is_cascading_delete": True/False,
                "creatable": True/False
            }
        }
    """
    try:
        child_objects = {}

        # CALL 1: Get parent metadata to access childRelationships
        parent_metadata = getattr(sf_conn, parent_object).describe()
        child_relationships = parent_metadata.get('childRelationships', [])

        if not child_relationships:
            st.info(f"ℹ️ No child objects found for {parent_object}")
            return {}

        # CALL 2: Global describe (cached) — gives label + createable for ALL objects at once
        # This replaces N sequential child describe() calls with one cached call
        cache_key = 'sf_global_object_info'
        if cache_key not in st.session_state:
            global_desc = sf_conn.describe()
            st.session_state[cache_key] = {
                obj['name']: {
                    'label': obj.get('label', obj['name']),
                    'createable': obj.get('createable', False)
                }
                for obj in global_desc.get('sobjects', [])
            }
        object_info = st.session_state[cache_key]

        # Process each child relationship using data already in memory (no more API calls)
        for relationship in child_relationships:
            child_object = relationship.get('childSObject')

            if not child_object:
                continue

            # Skip known Salesforce platform/system objects
            if _is_system_child(child_object):
                continue

            obj_info = object_info.get(child_object, {})

            # Skip objects that can't be created (audit/history objects)
            if not obj_info.get('createable', False):
                continue

            parent_field = relationship.get('field', '')
            if not parent_field:
                continue

            # cascadeDelete=True means master-detail relationship
            is_cascade = relationship.get('cascadeDelete', False)

            child_objects[child_object] = {
                "relationship_name": relationship.get('relationshipName', ''),
                "relationship_type": "master_detail" if is_cascade else "lookup",
                "field_name": parent_field,
                "field_label": parent_field,
                "is_required": is_cascade,
                "child_object_label": obj_info.get('label', child_object),
                "is_cascading_delete": is_cascade,
                "creatable": True
            }

        return child_objects

    except Exception as e:
        st.error(f"❌ Error discovering child objects: {str(e)}")
        return {}
    """
    Discover all child objects related to the parent object.

    ⚡ OPTIMIZED (2 API calls total instead of N+1):
      - Call 1: parent describe → childRelationships (has cascadeDelete for type detection)
      - Call 2: sf_conn.describe() → all object labels + createable flags (cached in session state)
      No individual child describe() calls are made.

    Args:
        sf_conn: Salesforce connection
        parent_object: Parent object name (e.g., 'Account', 'Questionnaire')

    Returns:
        Dictionary with structure:
        {
            "child_object_name": {
                "relationship_name": "relationship_api_name",
                "relationship_type": "master_detail" or "lookup",
                "field_name": "field_api_name",
                "field_label": "Field Label",
                "is_required": True/False,
                "child_object_label": "Child Object Label",
                "is_cascading_delete": True/False,
                "creatable": True/False
            }
        }
    """
    try:
        child_objects = {}

        # CALL 1: Get parent metadata to access childRelationships
        parent_metadata = getattr(sf_conn, parent_object).describe()
        child_relationships = parent_metadata.get('childRelationships', [])

        if not child_relationships:
            st.info(f"ℹ️ No child objects found for {parent_object}")
            return {}

        # CALL 2: Global describe (cached) — gives label + createable for ALL objects at once
        # This replaces N sequential child describe() calls with one cached call
        cache_key = 'sf_global_object_info'
        if cache_key not in st.session_state:
            global_desc = sf_conn.describe()
            st.session_state[cache_key] = {
                obj['name']: {
                    'label': obj.get('label', obj['name']),
                    'createable': obj.get('createable', False)
                }
                for obj in global_desc.get('sobjects', [])
            }
        object_info = st.session_state[cache_key]

        # Process each child relationship using data already in memory (no more API calls)
        for relationship in child_relationships:
            child_object = relationship.get('childSObject')

            if not child_object:
                continue

            obj_info = object_info.get(child_object, {})

            # Skip objects that can't be created (system/audit/history objects)
            if not obj_info.get('createable', False):
                continue

            parent_field = relationship.get('field', '')
            if not parent_field:
                continue

            # cascadeDelete=True means master-detail relationship
            # No child describe needed — cascadeDelete is already in parent's childRelationships
            is_cascade = relationship.get('cascadeDelete', False)

            child_objects[child_object] = {
                "relationship_name": relationship.get('relationshipName', ''),
                "relationship_type": "master_detail" if is_cascade else "lookup",
                "field_name": parent_field,
                "field_label": parent_field,        # API name; avoids needing child describe
                "is_required": is_cascade,           # master-detail fields are always required
                "child_object_label": obj_info.get('label', child_object),
                "is_cascading_delete": is_cascade,
                "creatable": True                    # already filtered above
            }

        return child_objects

    except Exception as e:
        st.error(f"❌ Error discovering child objects: {str(e)}")
        return {}


def get_child_object_fields(sf_conn: Salesforce, child_object: str) -> List[str]:
    """
    Get queryable fields for a child object
    
    Args:
        sf_conn: Salesforce connection
        child_object: Child object name
    
    Returns:
        List of queryable field names
    """
    try:
        obj_metadata = getattr(sf_conn, child_object).describe()
        fields = []
        
        for field in obj_metadata['fields']:
            if field.get('queryable', False):
                fields.append(field['name'])
        
        return sorted(fields)
    except Exception as e:
        st.error(f"Error getting fields for {child_object}: {str(e)}")
        return []


def extract_child_records(
    sf_conn: Salesforce,
    parent_object: str,
    parent_ids: List[str],
    child_object: str,
    child_config: Dict,
    limit: int = 50000
) -> Optional[pd.DataFrame]:
    """
    Extract child records for given parent IDs
    
    Args:
        sf_conn: Salesforce connection
        parent_object: Parent object name
        parent_ids: List of parent record IDs to get children for
        child_object: Child object name
        child_config: Configuration from discover_child_objects
        limit: Maximum records to extract
    
    Returns:
        DataFrame with child records or None if error
    """
    try:
        if not parent_ids:
            st.warning(f"⚠️ No parent IDs provided for {child_object}")
            return None
        
        # Build SOQL to get child records
        parent_id_list = "('{}')".format("','".join(parent_ids))
        
        parent_field = child_config['field_name']
        fields_to_select = get_child_object_fields(sf_conn, child_object)
        
        if not fields_to_select:
            st.error(f"❌ No queryable fields found for {child_object}")
            return None
        
        # Always include Id and parent reference field
        if 'Id' not in fields_to_select:
            fields_to_select.insert(0, 'Id')
        if parent_field not in fields_to_select:
            fields_to_select.append(parent_field)
        
        soql = f"SELECT {', '.join(fields_to_select)} FROM {child_object} WHERE {parent_field} IN {parent_id_list} LIMIT {limit}"
        
        result = sf_conn.query(soql)
        
        if result['totalSize'] == 0:
            return pd.DataFrame()
        
        # Convert to DataFrame
        records = result['records']
        df = pd.DataFrame(records)
        
        # Remove Salesforce metadata column
        if 'attributes' in df.columns:
            df = df.drop('attributes', axis=1)
        
        return df
        
    except Exception as e:
        st.error(f"❌ Error extracting {child_object} records: {str(e)}")
        return None


def build_parent_child_mapping(
    parent_df: pd.DataFrame,
    child_objects_config: Dict[str, Dict],
    sf_conn: Salesforce,
    parent_object: str
) -> Dict[str, Dict]:
    """
    Build complete parent-child data structure with all relationships
    
    Args:
        parent_df: DataFrame with parent records
        child_objects_config: Dictionary of selected child objects to extract
        sf_conn: Salesforce connection
        parent_object: Parent object name
    
    Returns:
        Dictionary with structure:
        {
            "parent": parent_df,
            "children": {
                "ChildObject1": {
                    "data": child_df,
                    "config": config_dict,
                    "parent_field": "field_name",
                    "record_count": N
                },
                "ChildObject2": {...}
            },
            "total_child_records": N
        }
    """
    result = {
        "parent": parent_df,
        "parent_object": parent_object,
        "children": {},
        "total_child_records": 0
    }
    
    try:
        # Get parent IDs for querying children
        parent_ids = parent_df['Id'].unique().tolist() if 'Id' in parent_df.columns else []
        
        if not parent_ids:
            st.warning("⚠️ No parent IDs found in data")
            return result
        
        st.info(f"📤 Extracting child records for {len(parent_ids)} parent records...")
        
        # For each selected child object, extract its data
        for child_obj in child_objects_config:
            if child_obj not in child_objects_config:
                continue
            
            config = child_objects_config[child_obj]
            
            # Skip if not creatable in target org
            if not config.get('creatable', True):
                st.warning(f"⚠️ Skipping {child_obj} - not creatable in target org")
                continue
            
            child_df = extract_child_records(
                sf_conn,
                parent_object,
                parent_ids,
                child_obj,
                config
            )
            
            if child_df is not None and not child_df.empty:
                result["children"][child_obj] = {
                    "data": child_df,
                    "config": config,
                    "parent_field": config['field_name'],
                    "record_count": len(child_df),
                    "relationship_type": config['relationship_type']
                }
                result["total_child_records"] += len(child_df)
                st.success(f"✅ Extracted {len(child_df)} {child_obj} records")
            else:
                st.info(f"ℹ️ No {child_obj} records found")
        
        return result
        
    except Exception as e:
        st.error(f"❌ Error building parent-child mapping: {str(e)}")
        return result


def display_child_objects_selection(child_objects: Dict[str, Dict]) -> List[str]:
    """
    Display UI for user to select which child objects to include in migration.

    Args:
        child_objects: Dictionary from discover_child_objects

    Returns:
        List of selected child object names
    """
    if not child_objects:
        st.info("ℹ️ No related objects found for this object")
        return []

    st.markdown("### 📋 Related Objects")
    st.markdown("Select the related objects you want to migrate along with the parent:")

    selected_children = []

    # Header row
    col1, col2, col3 = st.columns([0.5, 2.5, 2])
    with col2:
        st.caption("**Object**")
    with col3:
        st.caption("**Relationship Field**")
    st.markdown("---")

    for obj_name, config in child_objects.items():
        col1, col2, col3 = st.columns([0.5, 2.5, 2])

        with col1:
            include = st.checkbox(
                obj_name,
                value=False,
                key=f"include_{obj_name}",
                label_visibility="collapsed"
            )

        with col2:
            st.write(config['child_object_label'])

        with col3:
            st.caption(f"{config['field_name']}")

        if include:
            selected_children.append(obj_name)

    return selected_children


def display_migration_summary(migration_data: Dict) -> None:
    """
    Display summary of parent and child records to be migrated
    
    Args:
        migration_data: Dictionary from build_parent_child_mapping
    """
    st.markdown("### 📊 Migration Summary")
    
    col1, col2, col3 = st.columns(3)
    
    parent_df = migration_data.get('parent', pd.DataFrame())
    
    with col1:
        st.metric(
            "Parent Records",
            len(parent_df),
            help=f"Total {migration_data['parent_object']} records to migrate"
        )
    
    with col2:
        st.metric(
            "Related Objects",
            len(migration_data.get('children', {})),
            help="Number of child object types"
        )
    
    with col3:
        st.metric(
            "Child Records",
            migration_data.get('total_child_records', 0),
            help="Total child records across all types"
        )
    
    # Detailed breakdown
    if migration_data.get('children'):
        st.markdown("#### 📋 Child Records by Type")
        
        breakdown_data = []
        for child_obj, child_info in migration_data['children'].items():
            breakdown_data.append({
                "Child Object": child_obj,
                "Type": child_info['relationship_type'].upper(),
                "Records": child_info['record_count'],
                "Parent Field": child_info['parent_field']
            })
        
        breakdown_df = pd.DataFrame(breakdown_data)
        st.dataframe(breakdown_df, use_container_width=True, hide_index=True)


def validate_child_records(migration_data: Dict) -> List[str]:
    """
    Validate child records before migration
    
    Args:
        migration_data: Dictionary from build_parent_child_mapping
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    try:
        parent_df = migration_data.get('parent', pd.DataFrame())
        children = migration_data.get('children', {})
        
        if len(parent_df) == 0:
            errors.append("No parent records to migrate")
        
        # Validate each child object
        for child_obj, child_info in children.items():
            child_df = child_info.get('data', pd.DataFrame())
            parent_field = child_info.get('parent_field', '')
            
            if len(child_df) == 0:
                # This is okay - just no child records
                continue
            
            # Check if all child records have valid parent references
            if parent_field not in child_df.columns:
                errors.append(f"{child_obj}: Missing parent field '{parent_field}'")
            else:
                null_parents = child_df[parent_field].isna().sum()
                if null_parents > 0:
                    rel_type = child_info.get('relationship_type', 'lookup')
                    if rel_type == 'master_detail':
                        errors.append(f"{child_obj}: {null_parents} records have NULL parent (CRITICAL for Master-Detail)")
                    else:
                        # For lookups, this is okay
                        pass
        
        # Check for duplicate parent-child combinations
        for child_obj, child_info in children.items():
            child_df = child_info.get('data', pd.DataFrame())
            if len(child_df) > 0 and 'Id' in child_df.columns:
                duplicates = child_df.duplicated(subset=['Id']).sum()
                if duplicates > 0:
                    errors.append(f"{child_obj}: {duplicates} duplicate records found")
    
    except Exception as e:
        errors.append(f"Validation error: {str(e)}")
    
    return errors
