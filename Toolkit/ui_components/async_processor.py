"""
Async Multi-Org/Multi-Object Processor
=======================================
Enables simultaneous data fetching/loading from multiple orgs and objects
"""

import asyncio
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any
import streamlit as st
import logging

logger = logging.getLogger(__name__)


class AsyncProcessor:
    """Handles asynchronous multi-org/multi-object operations"""
    
    def __init__(self):
        """Initialize async processor"""
        self.results = []
        self.errors = []
    
    async def fetch_from_org_async(
        self,
        sf_connection,
        object_name: str,
        org_name: str,
        query: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Asynchronously fetch data from a single org/object
        
        Args:
            sf_connection: Salesforce connection object
            object_name: Object to fetch from
            org_name: Name of the org (for tracking)
            query: Optional SOQL query (if None, fetch all)
        
        Returns:
            Tuple of (DataFrame, metadata dict)
        """
        try:
            loop = asyncio.get_event_loop()
            
            if query:
                # Execute specific query
                result = await loop.run_in_executor(
                    None,
                    lambda: sf_connection.query(query)
                )
            else:
                # Fetch all records for object
                result = await loop.run_in_executor(
                    None,
                    lambda: sf_connection.query(f"SELECT * FROM {object_name}")
                )
            
            # Convert to DataFrame
            records = result.get('records', [])
            # Remove sObject metadata
            for record in records:
                record.pop('attributes', None)
            
            df = pd.DataFrame(records)
            
            metadata = {
                "org_name": org_name,
                "object_name": object_name,
                "record_count": len(df),
                "query": query,
                "status": "SUCCESS"
            }
            
            logger.info(f"Fetched {len(df)} records from {org_name}.{object_name}")
            return df, metadata
        
        except Exception as e:
            logger.error(f"Error fetching from {org_name}.{object_name}: {str(e)}")
            error_info = {
                "org_name": org_name,
                "object_name": object_name,
                "error": str(e),
                "status": "FAILED"
            }
            self.errors.append(error_info)
            return pd.DataFrame(), error_info
    
    async def fetch_multiple_orgs(
        self,
        org_configs: List[Dict[str, Any]],
        object_names: Optional[List[str]] = None,
        queries: Optional[Dict[str, str]] = None
    ) -> List[Tuple[pd.DataFrame, Dict[str, Any]]]:
        """
        Fetch from multiple orgs and objects simultaneously
        
        Args:
            org_configs: List of org configs with 'connection' and 'org_name'
            object_names: List of object names to fetch (None = all in query)
            queries: Optional dict mapping 'org.object' to custom SOQL
        
        Returns:
            List of (DataFrame, metadata) tuples
        """
        self.results = []
        self.errors = []
        tasks = []
        
        # Build fetch tasks
        for org_config in org_configs:
            org_name = org_config.get("org_name")
            connection = org_config.get("connection")
            
            if not connection:
                logger.warning(f"No connection for org: {org_name}")
                continue
            
            if object_names:
                # Fetch specific objects
                for obj_name in object_names:
                    query_key = f"{org_name}.{obj_name}"
                    custom_query = queries.get(query_key) if queries else None
                    
                    task = self.fetch_from_org_async(
                        connection,
                        obj_name,
                        org_name,
                        custom_query
                    )
                    tasks.append(task)
            else:
                # Use provided queries
                if queries:
                    for query_key, query in queries.items():
                        if query_key.startswith(f"{org_name}."):
                            obj_name = query_key.split(".")[-1]
                            task = self.fetch_from_org_async(
                                connection,
                                obj_name,
                                org_name,
                                query
                            )
                            tasks.append(task)
        
        # Execute all tasks simultaneously
        if tasks:
            self.results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return self.results
    
    async def load_to_multiple_orgs(
        self,
        data: pd.DataFrame,
        target_orgs: List[Dict[str, Any]],
        object_name: str,
        operation_type: str = "Data_Load"
    ) -> List[Dict[str, Any]]:
        """
        Load same data to multiple target orgs simultaneously
        
        Args:
            data: DataFrame to load
            target_orgs: List of target org configs with 'connection' and 'org_name'
            object_name: Object to load to
            operation_type: Type of operation for tracking
        
        Returns:
            List of operation results
        """
        self.results = []
        self.errors = []
        tasks = []
        
        for org_config in target_orgs:
            org_name = org_config.get("org_name")
            connection = org_config.get("connection")
            
            if not connection:
                logger.warning(f"No connection for org: {org_name}")
                continue
            
            task = self._load_to_org_async(
                data,
                connection,
                object_name,
                org_name
            )
            tasks.append(task)
        
        # Execute all loads simultaneously
        if tasks:
            self.results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return self.results
    
    async def _load_to_org_async(
        self,
        data: pd.DataFrame,
        sf_connection,
        object_name: str,
        org_name: str
    ) -> Dict[str, Any]:
        """Asynchronously load data to a single org"""
        try:
            loop = asyncio.get_event_loop()
            
            # Validate data first
            obj_describe = await loop.run_in_executor(
                None,
                lambda: getattr(sf_connection, object_name).describe()
            )
            
            # Insert records
            records = data.to_dict('records')
            
            def bulk_insert():
                results = []
                for i, record in enumerate(records):
                    try:
                        result = getattr(sf_connection, object_name).create(record)
                        results.append({"index": i, "id": result, "status": "SUCCESS"})
                    except Exception as e:
                        results.append({"index": i, "error": str(e), "status": "FAILED"})
                return results
            
            insert_results = await loop.run_in_executor(None, bulk_insert)
            
            successful = sum(1 for r in insert_results if r["status"] == "SUCCESS")
            failed = sum(1 for r in insert_results if r["status"] == "FAILED")
            
            result = {
                "org_name": org_name,
                "object_name": object_name,
                "total_records": len(records),
                "successful_inserts": successful,
                "failed_inserts": failed,
                "status": "COMPLETE",
                "details": insert_results[:10]  # Keep first 10 for reference
            }
            
            logger.info(f"Loaded {successful}/{len(records)} records to {org_name}.{object_name}")
            return result
        
        except Exception as e:
            logger.error(f"Error loading to {org_name}.{object_name}: {str(e)}")
            error_result = {
                "org_name": org_name,
                "object_name": object_name,
                "error": str(e),
                "status": "FAILED"
            }
            self.errors.append(error_result)
            return error_result
    
    def get_results_summary(self) -> Dict[str, Any]:
        """Get summary of async operations"""
        successful = [r for r in self.results if isinstance(r, tuple) or r.get("status") == "SUCCESS"]
        failed = [r for r in self.results if isinstance(r, Exception) or 
                 (isinstance(r, dict) and r.get("status") == "FAILED")]
        
        return {
            "total_operations": len(self.results),
            "successful": len(successful),
            "failed": len(failed),
            "errors": self.errors
        }


# Streamlit helper to run async operations
def run_async_fetch(
    org_configs: List[Dict[str, Any]],
    object_names: List[str],
    progress_placeholder=None
) -> List[Tuple[pd.DataFrame, Dict[str, Any]]]:
    """
    Helper to run async fetch with Streamlit progress tracking
    
    Usage:
        org_configs = [
            {"org_name": "HeraQA", "connection": sf_conn1},
            {"org_name": "TestDev", "connection": sf_conn2}
        ]
        
        results = run_async_fetch(
            org_configs,
            ["Account", "Opportunity"],
            st.empty()
        )
    """
    processor = AsyncProcessor()
    
    # Show progress
    if progress_placeholder:
        progress_placeholder.info(
            f"🔄 Fetching from {len(org_configs)} org(s) × {len(object_names)} object(s) "
            f"= {len(org_configs) * len(object_names)} simultaneous tasks..."
        )
    
    try:
        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(
            processor.fetch_multiple_orgs(org_configs, object_names)
        )
        
        loop.close()
        
        if progress_placeholder:
            summary = processor.get_results_summary()
            progress_placeholder.success(
                f"✅ Completed: {summary['successful']} successful, {summary['failed']} failed"
            )
        
        return results
    
    except Exception as e:
        logger.error(f"Error in async fetch: {str(e)}")
        if progress_placeholder:
            progress_placeholder.error(f"❌ Error: {str(e)}")
        return []


def run_async_load(
    data: pd.DataFrame,
    target_orgs: List[Dict[str, Any]],
    object_name: str,
    progress_placeholder=None
) -> List[Dict[str, Any]]:
    """Helper to run async load with Streamlit progress tracking"""
    processor = AsyncProcessor()
    
    if progress_placeholder:
        progress_placeholder.info(
            f"🔄 Loading to {len(target_orgs)} org(s) simultaneously..."
        )
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(
            processor.load_to_multiple_orgs(data, target_orgs, object_name)
        )
        
        loop.close()
        
        if progress_placeholder:
            summary = processor.get_results_summary()
            progress_placeholder.success(
                f"✅ Load complete: {summary['successful']} successful, {summary['failed']} failed"
            )
        
        return results
    
    except Exception as e:
        logger.error(f"Error in async load: {str(e)}")
        if progress_placeholder:
            progress_placeholder.error(f"❌ Error: {str(e)}")
        return []
