"""
Field Mapping Manager Module
Handles saving, loading, and managing field mappings for Salesforce objects
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

# Define mappings storage directory
MAPPINGS_DIR = os.path.join(os.path.dirname(__file__), '..', 'field_mappings')


def ensure_mappings_directory():
    """Create the field mappings directory if it doesn't exist"""
    os.makedirs(MAPPINGS_DIR, exist_ok=True)


def get_mapping_file_path(org_name: str, object_name: str) -> str:
    """
    Get the file path for storing field mappings for a specific org and object
    
    Args:
        org_name: Salesforce organization name
        object_name: Salesforce object name
    
    Returns:
        File path for the mapping
    """
    ensure_mappings_directory()
    # Create a safe filename from org and object names
    safe_filename = f"{org_name}_{object_name}_mappings.json"
    return os.path.join(MAPPINGS_DIR, safe_filename)


def save_field_mapping(org_name: str, object_name: str, field_mappings: Dict[str, str],
                       csv_columns: List[str] = None, validation_type: str = "schema") -> Tuple[bool, str]:
    """
    Save field mappings for a specific organization and object
    
    Args:
        org_name: Salesforce organization name
        object_name: Salesforce object name
        field_mappings: Dictionary of CSV column -> Salesforce field mappings
        csv_columns: List of CSV columns (for reference)
        validation_type: Type of validation (schema, genai, enhanced)
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        ensure_mappings_directory()
        file_path = get_mapping_file_path(org_name, object_name)
        
        # Create mapping data structure
        mapping_data = {
            'org_name': org_name,
            'object_name': object_name,
            'field_mappings': field_mappings,
            'csv_columns': csv_columns or list(field_mappings.keys()),
            'validation_type': validation_type,
            'saved_at': datetime.now().isoformat(),
            'mapping_count': len(field_mappings)
        }
        
        # Save to JSON file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2, ensure_ascii=False)
        
        return True, f"✅ Field mappings saved successfully for {object_name} in {org_name}"
    
    except Exception as e:
        return False, f"❌ Error saving field mappings: {str(e)}"


def load_field_mapping(org_name: str, object_name: str) -> Tuple[Optional[Dict], bool, str]:
    """
    Load saved field mappings for a specific organization and object
    
    Args:
        org_name: Salesforce organization name
        object_name: Salesforce object name
    
    Returns:
        Tuple of (mapping_data: dict or None, success: bool, message: str)
    """
    try:
        file_path = get_mapping_file_path(org_name, object_name)
        
        if not os.path.exists(file_path):
            return None, False, f"No saved mappings found for {object_name}"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        return mapping_data, True, "✅ Field mappings loaded successfully"
    
    except Exception as e:
        return None, False, f"Error loading field mappings: {str(e)}"


def list_saved_mappings(org_name: str = None) -> List[Dict]:
    """
    List all saved field mappings for an organization or globally
    
    Args:
        org_name: Salesforce organization name (optional, for filtering)
    
    Returns:
        List of mapping metadata
    """
    try:
        ensure_mappings_directory()
        saved_mappings = []
        
        if not os.path.exists(MAPPINGS_DIR):
            return saved_mappings
        
        for filename in os.listdir(MAPPINGS_DIR):
            if filename.endswith('_mappings.json'):
                file_path = os.path.join(MAPPINGS_DIR, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        mapping_data = json.load(f)
                    
                    # Filter by org if specified
                    if org_name is None or mapping_data.get('org_name') == org_name:
                        saved_mappings.append({
                            'org_name': mapping_data.get('org_name'),
                            'object_name': mapping_data.get('object_name'),
                            'mapping_count': mapping_data.get('mapping_count', 0),
                            'validation_type': mapping_data.get('validation_type', 'unknown'),
                            'saved_at': mapping_data.get('saved_at'),
                            'file_path': file_path
                        })
                except Exception as e:
                    print(f"Error reading mapping file {filename}: {str(e)}")
                    continue
        
        # Sort by saved_at in descending order (newest first)
        saved_mappings.sort(key=lambda x: x.get('saved_at', ''), reverse=True)
        
        return saved_mappings
    
    except Exception as e:
        print(f"Error listing saved mappings: {str(e)}")
        return []


def delete_field_mapping(org_name: str, object_name: str) -> Tuple[bool, str]:
    """
    Delete saved field mappings for a specific organization and object
    
    Args:
        org_name: Salesforce organization name
        object_name: Salesforce object name
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        file_path = get_mapping_file_path(org_name, object_name)
        
        if not os.path.exists(file_path):
            return False, f"No saved mappings found for {object_name}"
        
        os.remove(file_path)
        return True, f"✅ Field mappings deleted for {object_name}"
    
    except Exception as e:
        return False, f"❌ Error deleting field mappings: {str(e)}"


def check_mapping_exists(org_name: str, object_name: str) -> bool:
    """
    Check if field mappings exist for an organization and object
    
    Args:
        org_name: Salesforce organization name
        object_name: Salesforce object name
    
    Returns:
        True if mappings exist, False otherwise
    """
    file_path = get_mapping_file_path(org_name, object_name)
    return os.path.exists(file_path)


def export_mappings_to_csv(org_name: str) -> Tuple[Optional[str], bool, str]:
    """
    Export all field mappings for an organization to CSV
    
    Args:
        org_name: Salesforce organization name
    
    Returns:
        Tuple of (file_path: str or None, success: bool, message: str)
    """
    try:
        mappings = list_saved_mappings(org_name)
        
        if not mappings:
            return None, False, f"No saved mappings found for {org_name}"
        
        # Create DataFrame from mappings
        df_data = []
        for mapping in mappings:
            df_data.append({
                'Organization': mapping['org_name'],
                'Object': mapping['object_name'],
                'Fields Mapped': mapping['mapping_count'],
                'Validation Type': mapping['validation_type'],
                'Saved At': mapping['saved_at']
            })
        
        df = pd.DataFrame(df_data)
        
        # Save to CSV
        export_dir = os.path.join(MAPPINGS_DIR, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_file = os.path.join(export_dir, f"{org_name}_mappings_{timestamp}.csv")
        
        df.to_csv(export_file, index=False)
        
        return export_file, True, f"✅ Mappings exported to CSV"
    
    except Exception as e:
        return None, False, f"Error exporting mappings: {str(e)}"


def display_mapping_info(mapping_data: Dict) -> str:
    """
    Create a formatted string displaying mapping information
    
    Args:
        mapping_data: Mapping data dictionary
    
    Returns:
        Formatted string for display
    """
    info = f"""
**Organization:** {mapping_data.get('org_name')}
**Object:** {mapping_data.get('object_name')}
**Fields Mapped:** {mapping_data.get('mapping_count', 0)}
**Validation Type:** {mapping_data.get('validation_type', 'Unknown')}
**Saved At:** {mapping_data.get('saved_at', 'Unknown')}

**Field Mappings:**
"""
    field_mappings = mapping_data.get('field_mappings', {})
    for csv_col, sf_field in field_mappings.items():
        info += f"\n• {csv_col} → {sf_field}"
    
    return info
