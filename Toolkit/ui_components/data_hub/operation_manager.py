"""
Operation Manager
=================
Tracks all data operations (queries, uploads, loads) in persistent manifest
Enables data retrieval and history across sessions
"""

import json
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Any
import streamlit as st
import logging
import os

logger = logging.getLogger(__name__)

# Manifest file path - stored in Data Hub directory
MANIFEST_FILE = "data_hub_operations_manifest.json"


class OperationManager:
    """Manages operation tracking and data persistence"""
    
    def __init__(self):
        """Initialize operation manager"""
        self.manifest = self._load_manifest()
    
    def _load_manifest(self) -> Dict[str, Any]:
        """Load operations manifest from file"""
        try:
            if os.path.exists(MANIFEST_FILE):
                with open(MANIFEST_FILE, 'r') as f:
                    return json.load(f)
            else:
                return {
                    "version": "1.0",
                    "created": datetime.now().isoformat(),
                    "operations": []
                }
        except Exception as e:
            logger.warning(f"Could not load manifest: {str(e)}")
            return {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "operations": []
            }
    
    def _save_manifest(self):
        """Save operations manifest to file"""
        try:
            self.manifest["last_updated"] = datetime.now().isoformat()
            with open(MANIFEST_FILE, 'w') as f:
                json.dump(self.manifest, f, indent=2)
            logger.info("Manifest saved successfully")
        except Exception as e:
            logger.error(f"Could not save manifest: {str(e)}")
            raise
    
    def create_operation(
        self,
        operation_type: str,      # "SOQL_Query" / "File_Upload" / "Data_Load"
        object_name: str,          # "Account" / "Opportunity"
        record_count: int,
        data: pd.DataFrame,
        source_org: Optional[str] = None,
        target_org: Optional[str] = None,
        query: Optional[str] = None,
        file_name: Optional[str] = None,
        validation_status: Optional[str] = None,
        validation_passed: int = 0,
        validation_failed: int = 0,
        notes: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> str:
        """
        Create and track a new operation
        
        Args:
            operation_type: Type of operation
            object_name: Salesforce object name
            record_count: Number of records
            data: The actual data (DataFrame)
            source_org: Source organization
            target_org: Target organization
            query: SOQL query (if applicable)
            file_name: Uploaded file name (if applicable)
            validation_status: "PASSED" / "FAILED" / "PARTIAL"
            validation_passed: Number of records that passed validation
            validation_failed: Number of records that failed validation
            notes: Additional notes
            created_by: User who performed operation
        
        Returns:
            operation_id: Unique identifier for this operation
        """
        
        # Generate operation ID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        operation_id = f"OP-{timestamp}"
        
        # Store data to file
        data_file = f"data_hub_operations/{operation_id}_{object_name}.csv"
        os.makedirs("data_hub_operations", exist_ok=True)
        
        try:
            data.to_csv(data_file, index=False)
            logger.info(f"Stored operation data: {data_file}")
        except Exception as e:
            logger.error(f"Could not store operation data: {str(e)}")
            data_file = None
        
        # Create operation record
        operation = {
            "operation_id": operation_id,
            "timestamp": datetime.now().isoformat(),
            "operation_type": operation_type,
            "source_org": source_org,
            "target_org": target_org,
            "object_name": object_name,
            "record_count": record_count,
            "status": "COMPLETE",
            "data_location": data_file,
            "query": query,
            "file_uploaded": file_name,
            "validation_status": validation_status,
            "validation_passed": validation_passed,
            "validation_failed": validation_failed,
            "created_by": created_by or "Unknown",
            "notes": notes
        }
        
        # Add to manifest
        self.manifest["operations"].append(operation)
        
        # Save manifest
        self._save_manifest()
        
        logger.info(f"Created operation: {operation_id}")
        return operation_id
    
    def get_operation_history(
        self,
        org_filter: Optional[str] = None,
        object_filter: Optional[str] = None,
        operation_type_filter: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get operation history with optional filters
        
        Args:
            org_filter: Filter by org name (source or target)
            object_filter: Filter by object name
            operation_type_filter: Filter by operation type
            status_filter: Filter by status
        
        Returns:
            List of matching operations
        """
        filtered = self.manifest.get("operations", [])
        
        if org_filter:
            filtered = [op for op in filtered 
                       if org_filter in (op.get("source_org"), op.get("target_org"))]
        
        if object_filter:
            filtered = [op for op in filtered 
                       if op.get("object_name") == object_filter]
        
        if operation_type_filter:
            filtered = [op for op in filtered 
                       if op.get("operation_type") == operation_type_filter]
        
        if status_filter:
            filtered = [op for op in filtered 
                       if op.get("status") == status_filter]
        
        # Sort by timestamp descending (newest first)
        filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return filtered
    
    def retrieve_operation_data(self, operation_id: str) -> tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Retrieve stored data for a specific operation
        
        Args:
            operation_id: The operation ID to retrieve
        
        Returns:
            Tuple of (DataFrame, operation metadata)
        """
        # Find operation in manifest
        operation = next(
            (op for op in self.manifest.get("operations", []) 
             if op["operation_id"] == operation_id),
            None
        )
        
        if not operation:
            raise ValueError(f"Operation not found: {operation_id}")
        
        # Load data from file
        data_location = operation.get("data_location")
        if not data_location or not os.path.exists(data_location):
            raise FileNotFoundError(f"Data file not found: {data_location}")
        
        data = pd.read_csv(data_location)
        
        return data, operation
    
    def get_unique_orgs(self) -> List[str]:
        """Get list of unique organizations from operation history"""
        orgs = set()
        for op in self.manifest.get("operations", []):
            if op.get("source_org"):
                orgs.add(op.get("source_org"))
            if op.get("target_org"):
                orgs.add(op.get("target_org"))
        return sorted(list(orgs))
    
    def get_unique_objects(self) -> List[str]:
        """Get list of unique objects from operation history"""
        objects = set()
        for op in self.manifest.get("operations", []):
            if op.get("object_name"):
                objects.add(op.get("object_name"))
        return sorted(list(objects))
    
    def get_unique_objects_for_org(self, org_name: Optional[str] = None) -> List[str]:
        """
        Get list of unique objects for a specific organization
        
        Args:
            org_name: Organization name (source or target)
        
        Returns:
            Sorted list of object names in that org
        """
        if not org_name:
            return self.get_unique_objects()
        
        objects = set()
        for op in self.manifest.get("operations", []):
            # Check if this operation is from the selected org (source or target)
            if org_name in (op.get("source_org"), op.get("target_org")):
                if op.get("object_name"):
                    objects.add(op.get("object_name"))
        return sorted(list(objects))
    
    def get_operation_stats(self) -> Dict[str, Any]:
        """Get statistics about operations"""
        operations = self.manifest.get("operations", [])
        
        return {
            "total_operations": len(operations),
            "operations_by_type": self._count_by_field(operations, "operation_type"),
            "operations_by_status": self._count_by_field(operations, "status"),
            "total_records_processed": sum(op.get("record_count", 0) for op in operations),
            "total_validation_passed": sum(op.get("validation_passed", 0) for op in operations),
            "total_validation_failed": sum(op.get("validation_failed", 0) for op in operations),
        }
    
    @staticmethod
    def _count_by_field(operations: List[Dict], field: str) -> Dict[str, int]:
        """Count occurrences of field values"""
        counts = {}
        for op in operations:
            value = op.get(field, "Unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts
    
    def delete_operation(self, operation_id: str) -> bool:
        """Delete an operation from history"""
        try:
            # Find and remove operation from manifest
            self.manifest["operations"] = [
                op for op in self.manifest.get("operations", [])
                if op["operation_id"] != operation_id
            ]
            
            # Delete data file if exists
            operation = next(
                (op for op in self.manifest.get("operations", []) 
                 if op["operation_id"] == operation_id),
                None
            )
            
            if operation and operation.get("data_location"):
                try:
                    if os.path.exists(operation["data_location"]):
                        os.remove(operation["data_location"])
                except Exception as e:
                    logger.warning(f"Could not delete data file: {str(e)}")
            
            # Save updated manifest
            self._save_manifest()
            logger.info(f"Deleted operation: {operation_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting operation: {str(e)}")
            return False
    
    def export_history_to_csv(self, output_file: str = "operation_history.csv"):
        """Export operation history to CSV"""
        try:
            operations = self.manifest.get("operations", [])
            df = pd.DataFrame(operations)
            df.to_csv(output_file, index=False)
            logger.info(f"Exported history to {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Error exporting history: {str(e)}")
            raise


# Global instance for use across app
@st.cache_resource
def get_operation_manager() -> OperationManager:
    """Get singleton instance of OperationManager"""
    return OperationManager()
