"""
Salesforce Client for Validation Rules Extraction
Provides methods to fetch actual validation rules from Salesforce
"""

import streamlit as st
import simple_salesforce as sf
import requests
import json
from typing import Dict, List, Optional

class SalesforceValidationClient:
    """Client for fetching Salesforce validation rules"""
    
    def __init__(self, sf_connection):
        """Initialize with a Salesforce connection"""
        self.sf_conn = sf_connection
        self.session_id = sf_connection.session_id
        self.base_url = sf_connection.base_url
    
    def fetch_validation_rules(self, object_name: str) -> Dict:
        """
        Fetch validation rules for a specific Salesforce object
        Returns a dictionary with 'records' containing the validation rules
        """
        try:
            # Method 1: Try Tooling API (most comprehensive)
            result = self._fetch_via_tooling_api(object_name)
            if result and not result.get("error"):
                return result
            
            # Method 2: Try Metadata API approach
            result = self._fetch_via_metadata_api(object_name)
            if result and not result.get("error"):
                return result
            
            # Method 3: Try SOQL query (limited info)
            result = self._fetch_via_soql(object_name)
            if result and not result.get("error"):
                return result
            
            # If all methods fail, return empty result
            return {
                "records": [],
                "error": False,
                "message": f"No validation rules found for {object_name}"
            }
            
        except Exception as e:
            return {
                "records": [],
                "error": True,
                "message": f"Error fetching validation rules: {str(e)}"
            }
    
    def _fetch_via_tooling_api(self, object_name: str) -> Optional[Dict]:
        """Fetch validation rules using Tooling API - basic info only"""
        try:
            # Get the instance URL from the SF connection
            if hasattr(self.sf_conn, 'sf_instance'):
                instance_url = self.sf_conn.sf_instance
            else:
                # Extract instance URL from base URL
                instance_url = self.base_url.replace('https://', '').split('/')[0]
            
            # Construct proper Tooling API URL
            query_url = f"https://{instance_url}/services/data/v59.0/tooling/query/"
            
            # Use only fields that definitely exist in ValidationRule
            soql = (
                "SELECT Id, ValidationName, Active, ErrorMessage, ErrorDisplayField, Description "
                f"FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}'"
            )
            
            headers = {
                "Authorization": f"Bearer {self.session_id}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(query_url, headers=headers, params={"q": soql})
            
            if response.status_code != 200:
                st.warning(f"⚠️ Tooling API returned status {response.status_code}: {response.text}")
                return {"error": True, "message": f"Tooling API failed: {response.text}"}

            response_data = response.json()
            if not isinstance(response_data, dict) or "records" not in response_data:
                return {"error": True, "message": "Unexpected response format from Tooling API"}

            records = response_data.get("records", [])
            
            if records:
                st.success(f"✅ Tooling API: Found {len(records)} validation rules for {object_name}")
                
                # Format records to match expected structure
                formatted_records = []
                for record in records:
                    formatted_record = {
                        "Id": record.get("Id"),
                        "FullName": record.get("ValidationName"),  # Map ValidationName to FullName
                        "ValidationName": record.get("ValidationName"),
                        "ValidationFormula": "FORMULA_NOT_ACCESSIBLE_VIA_API",  # Salesforce limitation
                        "Active": record.get("Active"),
                        "ErrorMessage": record.get("ErrorMessage"),
                        "ErrorDisplayField": record.get("ErrorDisplayField"),
                        "Description": record.get("Description")
                    }
                    formatted_records.append(formatted_record)
                
                return {"success": True, "records": formatted_records, "error": False}
            else:
                st.info(f"ℹ️ No validation rules found for {object_name} via Tooling API")
                return {"error": False, "records": [], "message": f"No validation rules found for {object_name}"}
                
        except Exception as e:
            st.error(f"❌ Tooling API error: {str(e)}")
            return {"error": True, "message": f"Tooling API error: {str(e)}"}
    
    def get_validation_rule_details(self, object_name: str, rule_name: str) -> Optional[Dict]:
        """Get detailed information for a specific validation rule"""
        try:
            # Get the instance URL
            if hasattr(self.sf_conn, 'sf_instance'):
                instance_url = self.sf_conn.sf_instance
            else:
                instance_url = self.base_url.replace('https://', '').split('/')[0]
            
            query_url = f"https://{instance_url}/services/data/v59.0/tooling/query/"
            
            query = {
                "q": f"SELECT Id, ValidationName, ErrorMessage, Active FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}' AND ValidationName = '{rule_name}'"
            }
            
            headers = {
                "Authorization": f"Bearer {self.session_id}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(query_url, headers=headers, params=query)

            if response.status_code != 200:
                raise Exception(f"Failed to fetch validation rule: {response.text}")

            records = response.json().get("records", [])
            if not records:
                raise Exception(f"Validation rule '{rule_name}' not found for object '{object_name}'.")

            return records[0]
            
        except Exception as e:
            st.error(f"❌ Error getting validation rule details: {str(e)}")
            return None
    
    def _fetch_via_metadata_api(self, object_name: str) -> Optional[Dict]:
        """Fetch validation rules using Metadata API approach"""
        try:
            # This is a simplified approach - full Metadata API requires more setup
            # Try to get object metadata
            describe_url = f"{self.base_url}sobjects/{object_name}/describe/"
            headers = {'Authorization': f'Bearer {self.session_id}'}
            
            response = requests.get(describe_url, headers=headers)
            
            if response.status_code == 200:
                obj_data = response.json()
                
                # Check if validation rules are included (rare in standard describe)
                validation_rules = obj_data.get('validationRules', [])
                
                if validation_rules:
                    return {
                        "records": validation_rules,
                        "error": False,
                        "message": f"Found {len(validation_rules)} validation rules via Metadata API"
                    }
                else:
                    return {
                        "records": [],
                        "error": True,
                        "message": "Metadata API: No validation rules in object description"
                    }
            else:
                return {
                    "records": [],
                    "error": True,
                    "message": f"Metadata API failed with status {response.status_code}"
                }
                
        except Exception as e:
            return {
                "records": [],
                "error": True,
                "message": f"Metadata API error: {str(e)}"
            }
    
    def _fetch_via_soql(self, object_name: str) -> Optional[Dict]:
        """Fetch validation rules using SOQL (limited information)"""
        try:
            # Try to query ValidationRule object directly (may not work in all orgs)
            query = f"SELECT Id, DeveloperName FROM ValidationRule WHERE SobjectType = '{object_name}'"
            
            result = self.sf_conn.query(query)
            
            if result.get('records'):
                # Convert SOQL results to validation rule format
                validation_rules = []
                for record in result['records']:
                    validation_rules.append({
                        'Id': record.get('Id'),
                        'FullName': record.get('DeveloperName'),
                        'Active': True,  # Default assumption
                        'ErrorDisplayField': 'Unknown',
                        'ErrorMessage': 'Details available only via Tooling API',
                        'Description': f'Validation rule for {object_name}',
                        'CreatedDate': None,
                        'LastModifiedDate': None
                    })
                
                return {
                    "records": validation_rules,
                    "error": False,
                    "message": f"Found {len(validation_rules)} validation rules via SOQL (limited details)"
                }
            else:
                return {
                    "records": [],
                    "error": True,
                    "message": "SOQL: No validation rules found or access restricted"
                }
                
        except Exception as e:
            return {
                "records": [],
                "error": True,
                "message": f"SOQL error: {str(e)}"
            }
    
    def _get_tooling_url(self) -> str:
        """Construct the correct Tooling API URL"""
        base_url = self.base_url.rstrip('/')
        
        # Extract version from base URL or use default
        if '/v' in base_url:
            # URL already contains version
            tooling_url = base_url.replace('/services/data/', '/services/data/') + '/tooling/query/'
        else:
            # Add default version
            tooling_url = base_url + '/services/data/v58.0/tooling/query/'
        
        return tooling_url
    
    def get_object_info(self, object_name: str) -> Dict:
        """Get basic object information"""
        try:
            describe_url = f"{self.base_url}sobjects/{object_name}/describe/"
            headers = {'Authorization': f'Bearer {self.session_id}'}
            
            response = requests.get(describe_url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to get object info: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Error getting object info: {str(e)}"}

def create_sf_validation_client(sf_connection):
    """Create a Salesforce validation client"""
    return SalesforceValidationClient(sf_connection)