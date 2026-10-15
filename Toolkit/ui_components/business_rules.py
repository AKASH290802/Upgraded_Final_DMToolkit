#!/usr/bin/env python3
"""
Business Rules Configuration Manager
Handles JSON-driven configuration for ETL processing
"""

import json
import os
import streamlit as st
from typing import Dict, List, Optional, Any

class BusinessRulesManager:
    """
    Manages JSON-driven business rules and ETL configurations
    """
    
    def __init__(self):
        self.config_templates = {}
        self.load_default_templates()
    
    def load_default_templates(self):
        """Load default configuration templates"""
        
        # Template for basic data transformation
        self.config_templates['basic_transform'] = {
            "Source": "basic_data_load",
            "FieldMapping": [{}],
            "CopyFields": [{}],
            "FieldRules": [{
                "FolderURL": "",
                "Extension": "csv",
                "Delimiter": ",",
                "SheetName": "Sheet1",
                "LookUpFields": {},
                "ConditionFields": {},
                "DateFields": "",
                "MandatoryFields": "",
                "DropFields": "",
                "UniqueFields": "",
                "RecordTypeObject": "",
                "ReplaceValueIfNull": {},
                "ReplaceValues": {},
                "ErrorColumns": "FinalErrors",
                "ErrorMessageReplace": {}
            }]
        }
        
        # Template for warranty claims processing
        self.config_templates['warranty_claims'] = {
            "Source": "warranty_claims_processing",
            "FieldMapping": [{
                "claim_number": "Name",
                "warranty_code": "WOD_2__Warranty_Code__c",
                "claim_date": "WOD_2__Claim_Date__c",
                "amount": "WOD_2__Amount__c",
                "status": "Status"
            }],
            "CopyFields": [{}],
            "FieldRules": [{
                "FolderURL": "",
                "Extension": "csv",
                "Delimiter": ",",
                "SheetName": "Sheet1",
                "LookUpFields": {
                    "WOD_2__Warranty_Code__c": {
                        "ObjectName": "WOD_2__Warranty_Code__c",
                        "Fields": "Id, Name",
                        "JoinField": "Name",
                        "TargetField": "WOD_2__Warranty_Code__c",
                        "WhereCondition": "",
                        "HandleNumbers": "N"
                    }
                },
                "ConditionFields": {
                    "AutoApproved": {
                        "ConditionColumn": "WOD_2__Amount__c",
                        "ConditionValue": "1000",
                        "Condition": "lt",
                        "TargetValueTrue": "Yes",
                        "TargetValueFalse": "No"
                    }
                },
                "DateFields": "WOD_2__Claim_Date__c",
                "MandatoryFields": "Name,WOD_2__Warranty_Code__c,WOD_2__Claim_Date__c",
                "DropFields": "internal_id,temp_field",
                "UniqueFields": "Name",
                "RecordTypeObject": "WOD_2__Claim__c",
                "ReplaceValueIfNull": {},
                "ReplaceValues": {
                    "Status": {
                        "New": "Open",
                        "Pending": "In Progress",
                        "Done": "Closed"
                    }
                },
                "ErrorColumns": "FinalErrors",
                "ErrorMessageReplace": {}
            }]
        }
        
        # Template for account processing
        self.config_templates['account_processing'] = {
            "Source": "account_data_load",
            "FieldMapping": [{
                "company_name": "Name",
                "account_type": "Type",
                "industry": "Industry",
                "phone": "Phone",
                "email": "Email__c",
                "billing_street": "BillingStreet",
                "billing_city": "BillingCity",
                "billing_state": "BillingState",
                "billing_country": "BillingCountry"
            }],
            "CopyFields": [{}],
            "FieldRules": [{
                "FolderURL": "",
                "Extension": "csv",
                "Delimiter": ",",
                "SheetName": "Sheet1",
                "LookUpFields": {},
                "ConditionFields": {
                    "Priority": {
                        "ConditionColumn": "Type",
                        "ConditionValue": "Customer",
                        "Condition": "eq",
                        "TargetValueTrue": "High",
                        "TargetValueFalse": "Medium"
                    }
                },
                "DateFields": "",
                "MandatoryFields": "Name,Type",
                "DropFields": "internal_notes,temp_id",
                "UniqueFields": "Name,Phone",
                "RecordTypeObject": "Account",
                "ReplaceValueIfNull": {
                    "Type": "Other"
                },
                "ReplaceValues": {
                    "Industry": {
                        "Tech": "Technology",
                        "Mfg": "Manufacturing",
                        "Fin": "Financial Services"
                    }
                },
                "ErrorColumns": "FinalErrors",
                "ErrorMessageReplace": {}
            }]
        }
    
    def get_template_names(self) -> List[str]:
        """Get list of available template names"""
        return list(self.config_templates.keys())
    
    def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get specific template by name"""
        return self.config_templates.get(template_name)
    
    def create_custom_template(self, template_name: str, config: Dict[str, Any]) -> bool:
        """Create or update a custom template"""
        try:
            self.config_templates[template_name] = config
            return True
        except Exception as e:
            st.error(f"Failed to create template: {str(e)}")
            return False
    
    def save_template_to_file(self, template_name: str, file_path: str) -> bool:
        """Save template to JSON file"""
        try:
            template = self.get_template(template_name)
            if template:
                with open(file_path, 'w') as f:
                    json.dump(template, f, indent=4)
                return True
            return False
        except Exception as e:
            st.error(f"Failed to save template: {str(e)}")
            return False
    
    def load_template_from_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load template from JSON file"""
        try:
            with open(file_path, 'r') as f:
                template = json.load(f)
            return template
        except Exception as e:
            st.error(f"Failed to load template: {str(e)}")
            return None
    
    def validate_template(self, template: Dict[str, Any]) -> tuple:
        """Validate template structure"""
        errors = []
        warnings = []
        
        # Check required top-level keys
        required_keys = ['Source', 'FieldMapping', 'FieldRules']
        for key in required_keys:
            if key not in template:
                errors.append(f"Missing required key: {key}")
        
        # Validate FieldRules structure
        if 'FieldRules' in template and template['FieldRules']:
            field_rules = template['FieldRules'][0]
            
            # Check for common misconfigurations
            if 'LookUpFields' in field_rules:
                for lookup_field, config in field_rules['LookUpFields'].items():
                    required_lookup_keys = ['ObjectName', 'Fields', 'JoinField', 'TargetField']
                    for req_key in required_lookup_keys:
                        if req_key not in config:
                            errors.append(f"Lookup field '{lookup_field}' missing required key: {req_key}")
            
            # Validate condition fields
            if 'ConditionFields' in field_rules:
                for condition_field, config in field_rules['ConditionFields'].items():
                    required_condition_keys = ['ConditionColumn', 'ConditionValue', 'Condition', 'TargetValueTrue', 'TargetValueFalse']
                    for req_key in required_condition_keys:
                        if req_key not in config:
                            errors.append(f"Condition field '{condition_field}' missing required key: {req_key}")
        
        return errors, warnings
    
    def create_field_mapping_ui(self, source_columns: List[str], target_object: str = None) -> Dict[str, str]:
        """Create interactive UI for field mapping"""
        st.subheader("🗺️ Field Mapping Configuration")
        
        field_mapping = {}
        
        # Get Salesforce fields if target object is specified
        sf_fields = []
        if target_object and hasattr(st.session_state, 'sf_conn') and st.session_state.sf_conn:
            try:
                obj_desc = getattr(st.session_state.sf_conn, target_object).describe()
                sf_fields = [field['name'] for field in obj_desc['fields'] if field['createable']]
            except:
                pass
        
        # Create mapping interface
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Source Columns**")
            for i, col in enumerate(source_columns):
                st.write(f"{i+1}. {col}")
        
        with col2:
            st.write("**Target Fields**")
            for i, col in enumerate(source_columns):
                if sf_fields:
                    # Dropdown with Salesforce fields
                    target_field = st.selectbox(
                        f"Map '{col}' to:",
                        options=["-- Skip --"] + sf_fields,
                        key=f"mapping_{i}_{col}",
                        help=f"Select Salesforce field for '{col}'"
                    )
                else:
                    # Text input for manual mapping
                    target_field = st.text_input(
                        f"Map '{col}' to:",
                        key=f"mapping_{i}_{col}",
                        help=f"Enter target field name for '{col}'"
                    )
                
                if target_field and target_field != "-- Skip --":
                    field_mapping[col] = target_field
        
        return field_mapping
    
    def create_lookup_fields_ui(self) -> Dict[str, Dict]:
        """Create UI for lookup field configuration"""
        st.subheader("🔍 Lookup Field Configuration")
        
        lookup_fields = {}
        
        # Number of lookup fields
        num_lookups = st.number_input("Number of lookup fields", min_value=0, max_value=10, value=0)
        
        for i in range(num_lookups):
            st.write(f"**Lookup Field {i+1}**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                field_name = st.text_input(f"Field Name", key=f"lookup_field_{i}")
                object_name = st.text_input(f"Lookup Object", key=f"lookup_object_{i}")
                fields = st.text_input(f"Fields to Query", key=f"lookup_fields_{i}", value="Id, Name")
            
            with col2:
                join_field = st.text_input(f"Join Field", key=f"lookup_join_{i}", value="Name")
                target_field = st.text_input(f"Target Field", key=f"lookup_target_{i}")
                handle_numbers = st.selectbox(f"Handle Numbers", ["N", "Y"], key=f"lookup_numbers_{i}")
            
            where_condition = st.text_input(f"Where Condition (optional)", key=f"lookup_where_{i}")
            
            if field_name and object_name and target_field:
                lookup_fields[field_name] = {
                    "ObjectName": object_name,
                    "Fields": fields,
                    "JoinField": join_field,
                    "TargetField": target_field,
                    "WhereCondition": where_condition,
                    "HandleNumbers": handle_numbers
                }
        
        return lookup_fields
    
    def create_business_rules_ui(self) -> Dict[str, Any]:
        """Create comprehensive UI for business rules configuration"""
        st.subheader("⚙️ Business Rules Configuration")
        
        # File processing settings
        with st.expander("📁 File Processing Settings", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                extension = st.selectbox("File Extension", ["csv", "xlsx", "xls"], key="br_extension")
                delimiter = st.text_input("CSV Delimiter", value=",", key="br_delimiter")
            
            with col2:
                sheet_name = st.text_input("Excel Sheet Name", value="Sheet1", key="br_sheet")
        
        # Data transformation rules
        with st.expander("🔄 Data Transformation Rules"):
            date_fields = st.text_input("Date Fields (comma-separated)", key="br_date_fields")
            mandatory_fields = st.text_input("Mandatory Fields (comma-separated)", key="br_mandatory")
            drop_fields = st.text_input("Fields to Drop (comma-separated)", key="br_drop_fields")
            unique_fields = st.text_input("Unique Key Fields (comma-separated)", key="br_unique")
        
        # Record type settings
        with st.expander("📋 Record Type Configuration"):
            record_type_object = st.text_input("Record Type Object", key="br_record_type")
        
        # Compile business rules
        business_rules = {
            "Extension": extension,
            "Delimiter": delimiter,
            "SheetName": sheet_name,
            "DateFields": date_fields,
            "MandatoryFields": mandatory_fields,
            "DropFields": drop_fields,
            "UniqueFields": unique_fields,
            "RecordTypeObject": record_type_object,
            "LookUpFields": {},
            "ConditionFields": {},
            "ReplaceValueIfNull": {},
            "ReplaceValues": {},
            "ErrorColumns": "FinalErrors",
            "ErrorMessageReplace": {}
        }
        
        return business_rules
    
    def export_configuration(self, template: Dict[str, Any]) -> str:
        """Export configuration as JSON string"""
        try:
            return json.dumps(template, indent=4)
        except Exception as e:
            st.error(f"Failed to export configuration: {str(e)}")
            return ""
    
    def import_configuration(self, json_string: str) -> Optional[Dict[str, Any]]:
        """Import configuration from JSON string"""
        try:
            template = json.loads(json_string)
            errors, warnings = self.validate_template(template)
            
            if errors:
                st.error("Configuration validation failed:")
                for error in errors:
                    st.error(f"• {error}")
                return None
            
            if warnings:
                st.warning("Configuration warnings:")
                for warning in warnings:
                    st.warning(f"• {warning}")
            
            return template
            
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON format: {str(e)}")
            return None
        except Exception as e:
            st.error(f"Failed to import configuration: {str(e)}")
            return None