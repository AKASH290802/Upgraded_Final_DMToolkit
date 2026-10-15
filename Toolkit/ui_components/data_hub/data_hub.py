"""
Core Data Hub Class
===================
Manages data storage, retrieval, and caching
"""

import pandas as pd
from datetime import datetime
from typing import Dict, Optional, List, Any
import hashlib
import uuid


class DataHub:
    """Central data management system for the toolkit"""
    
    def __init__(self):
        """Initialize Data Hub"""
        self.cached_datasets: Dict[str, Dict[str, Any]] = {}
        self.active_dataset_id: Optional[str] = None
        self.creation_time = datetime.now()
    
    # ==================== DATA LOADING METHODS ====================
    
    def add_dataset(
        self,
        df: pd.DataFrame,
        dataset_name: str,
        source_type: str,  # 'file_upload', 'salesforce_soql', 'manual'
        source_details: Dict[str, str],
        set_active: bool = True
    ) -> str:
        """
        Add a new dataset to cache
        
        Args:
            df: DataFrame with data
            dataset_name: Human-readable name
            source_type: Type of source
            source_details: Dict with details (e.g., file_path, soql_query, org_name)
            set_active: Whether to set as active dataset
        
        Returns:
            dataset_id: Unique identifier for dataset
        """
        dataset_id = str(uuid.uuid4())
        
        self.cached_datasets[dataset_id] = {
            'id': dataset_id,
            'name': dataset_name,
            'df': df.copy(),
            'metadata': {
                'source_type': source_type,
                'source_details': source_details,
                'timestamp': datetime.now().isoformat(),
                'row_count': len(df),
                'column_count': len(df.columns),
                'columns': df.columns.tolist(),
                'memory_usage_kb': df.memory_usage(deep=True).sum() / 1024
            }
        }
        
        if set_active:
            self.active_dataset_id = dataset_id
        
        return dataset_id
    
    # ==================== DATASET ACCESS METHODS ====================
    
    def get_active_dataset(self) -> Optional[pd.DataFrame]:
        """Get active dataset DataFrame"""
        if self.active_dataset_id and self.active_dataset_id in self.cached_datasets:
            return self.cached_datasets[self.active_dataset_id]['df'].copy()
        return None
    
    def get_active_dataset_with_metadata(self) -> Optional[Dict[str, Any]]:
        """Get active dataset with full metadata"""
        if self.active_dataset_id and self.active_dataset_id in self.cached_datasets:
            return self.cached_datasets[self.active_dataset_id].copy()
        return None
    
    def get_dataset(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Get specific dataset by ID"""
        if dataset_id in self.cached_datasets:
            return self.cached_datasets[dataset_id]['df'].copy()
        return None
    
    def get_dataset_with_metadata(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get dataset with metadata"""
        if dataset_id in self.cached_datasets:
            return self.cached_datasets[dataset_id].copy()
        return None
    
    # ==================== DATASET MANAGEMENT METHODS ====================
    
    def set_active_dataset(self, dataset_id: str) -> bool:
        """Set active dataset"""
        if dataset_id in self.cached_datasets:
            self.active_dataset_id = dataset_id
            return True
        return False
    
    def list_datasets(self) -> List[Dict[str, Any]]:
        """List all cached datasets with metadata"""
        datasets = []
        for dataset_id, dataset in self.cached_datasets.items():
            datasets.append({
                'id': dataset_id,
                'name': dataset['name'],
                'is_active': dataset_id == self.active_dataset_id,
                'metadata': dataset['metadata']
            })
        return datasets
    
    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset"""
        if dataset_id in self.cached_datasets:
            if self.active_dataset_id == dataset_id:
                self.active_dataset_id = None
            del self.cached_datasets[dataset_id]
            return True
        return False
    
    def clear_all_datasets(self):
        """Clear all cached datasets"""
        self.cached_datasets.clear()
        self.active_dataset_id = None
    
    def rename_dataset(self, dataset_id: str, new_name: str) -> bool:
        """Rename a dataset"""
        if dataset_id in self.cached_datasets:
            self.cached_datasets[dataset_id]['name'] = new_name
            return True
        return False
    
    # ==================== UTILITY METHODS ====================
    
    def has_active_dataset(self) -> bool:
        """Check if there's an active dataset"""
        return self.active_dataset_id is not None and self.active_dataset_id in self.cached_datasets
    
    def get_dataset_count(self) -> int:
        """Get total number of cached datasets"""
        return len(self.cached_datasets)
    
    def get_active_dataset_info(self) -> Optional[Dict[str, Any]]:
        """Get info about active dataset"""
        if self.has_active_dataset():
            dataset = self.cached_datasets[self.active_dataset_id]
            return {
                'name': dataset['name'],
                'metadata': dataset['metadata']
            }
        return None
    
    def export_dataset(self, dataset_id: str, format: str = 'csv') -> Optional[bytes]:
        """
        Export dataset to bytes (CSV or Excel)
        
        Args:
            dataset_id: Dataset ID
            format: 'csv' or 'excel'
        
        Returns:
            Bytes for download
        """
        if dataset_id not in self.cached_datasets:
            return None
        
        df = self.cached_datasets[dataset_id]['df']
        
        if format == 'csv':
            return df.to_csv(index=False).encode()
        elif format == 'excel':
            import io
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            return buffer.getvalue()
        
        return None
