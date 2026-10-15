import sys
import pandas as pd
import os
# NOTE: this module is imported at app start (via validation_operations). It must not
# touch C:\DM_toolkit or import dataset.Connections / dataset.Org_selection (pyodbc,
# sqlalchemy, tkinter) - neither was used here.
import json
import re
import requests
from typing import Dict, List, Optional
import simple_salesforce as sf


def extract_fields_from_formula(formula):
    """Extract field names referenced in a Salesforce validation formula.
    
    Parses the Apex formula text to find field references, excluding
    known Salesforce functions, keywords, and string literals.
    
    Args:
        formula: The ErrorConditionFormula string from Salesforce
        
    Returns:
        str: Comma-separated list of field names found in the formula
    """
    if not formula or str(formula).lower() == 'nan':
        return ''
    
    formula_str = str(formula)
    
    # Remove quoted strings to avoid capturing string literal content
    cleaned = re.sub(r"'[^']*'|\"[^\"]*\"", '', formula_str)
    
    # Remove $-prefixed global merge field references ($Profile.Name, $User.Id, etc.)
    # These are runtime context fields, not data columns in the CSV/upload
    cleaned = re.sub(r'\$[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*', '', cleaned)
    
    # Known Salesforce functions to exclude
    sf_functions = {
        'ISBLANK', 'ISNULL', 'LEN', 'TEXT', 'VALUE', 'UPPER', 'LOWER', 'TRIM',
        'LEFT', 'RIGHT', 'MID', 'FIND', 'CONTAINS', 'TODAY', 'NOW', 'YEAR',
        'MONTH', 'DAY', 'AND', 'OR', 'NOT', 'IF', 'CASE', 'BEGINS', 'ENDS',
        'ABS', 'ROUND', 'CEILING', 'FLOOR', 'MAX', 'MIN', 'ISPICKVAL',
        'REGEX', 'MOD', 'SUBSTITUTE', 'CONCATENATE', 'DATEVALUE',
        'INCLUDES', 'EXCLUDES', 'PRIORVALUE', 'ISNEW', 'ISCHANGED',
        'NULLVALUE', 'BLANKVALUE', 'TRUE', 'FALSE', 'NULL', 'BR',
        'HYPERLINK', 'IMAGE',
    }
    
    # Find all word tokens
    tokens = re.findall(r'\b([A-Za-z][A-Za-z0-9_]*)\b', cleaned)
    
    fields = []
    for token in tokens:
        if token.upper() in sf_functions:
            continue
        if token.lower() in ['true', 'false', 'null']:
            continue
        # Skip $ references (already stripped of $ by this point but check anyway)
        if token.startswith('$'):
            continue
        if token not in fields:
            fields.append(token)
    
    return ','.join(fields)


def fetch_validation_rules_with_formula(sf_conn, object_name):
    """
    Fetch validation rules with formulas from Salesforce using Tooling API
    
    Args:
        sf_conn: Salesforce connection object
        object_name: Name of the Salesforce object
        
    Returns:
        List of validation rule dictionaries
    """
    try:
        # Validate sf_conn parameter
        if not sf_conn:
            raise ValueError("Salesforce connection object is None")
        
        if not hasattr(sf_conn, 'session_id'):
            raise ValueError(f"Invalid Salesforce connection object - missing session_id attribute. Got type: {type(sf_conn)}")
        
        if not hasattr(sf_conn, 'sf_instance'):
            raise ValueError(f"Invalid Salesforce connection object - missing sf_instance attribute. Got type: {type(sf_conn)}")
        
        session_id = sf_conn.session_id
        instance_url = sf_conn.sf_instance
        
        if not session_id:
            raise ValueError("Salesforce session_id is empty")
        
        print(f"Using session_id: {session_id[:10]}... for instance: {instance_url}")
        
        headers = {
            'Authorization': f'Bearer {session_id}',
            'Content-Type': 'application/json'
        }
        
        # Step 1: Get all validation rule Ids for the object
        val_url = f"https://{instance_url}/services/data/v59.0/tooling/query"
        id_query = (
            f"SELECT Id, ValidationName, ErrorMessage, Active, EntityDefinition.QualifiedApiName "
            f"FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object_name}'"
        )
        
        print(f"Executing query: {id_query}")
        id_resp = requests.get(val_url, headers=headers, params={'q': id_query})
        id_json = id_resp.json()
        
        if not isinstance(id_json, dict):
            print("Unexpected response from Salesforce Tooling API (Id query):")
            print(id_json)
            return []
            
        val_rules = id_json.get('records', [])
        print(f"Found {len(val_rules)} validation rules")
        validation_data = []
        
        # Step 2: For each Id, fetch Metadata (and formula)
        for i, v in enumerate(val_rules):
            print(f"Processing rule {i+1}/{len(val_rules)}: {v['ValidationName']}")
            rule_id = v['Id']
            meta_url = f"https://{instance_url}/services/data/v59.0/tooling/sobjects/ValidationRule/{rule_id}"
            meta_resp = requests.get(meta_url, headers=headers)
            meta_json = meta_resp.json()
            metadata = meta_json.get('Metadata', {})
            formula = metadata.get('errorConditionFormula', '') if isinstance(metadata, dict) else ''
            
            validation_data.append({
                'ValidationName': v['ValidationName'],
                'ErrorConditionFormula': formula,
                'FieldName': extract_fields_from_formula(formula),
                'ObjectName': object_name,
                'Active': v['Active'],
                'ErrorMessage': v['ErrorMessage'],
                'Description': ''
            })
            
        return validation_data
        
    except Exception as e:
        print(f"Error fetching validation rules: {e}")
        return []


def extract_validation_rules_to_csv(credentials, selected_org, object_name):
    """
    Extract validation rules from Salesforce and return CSV data
    
    Args:
        credentials: Dictionary of Salesforce credentials
        selected_org: Name of the selected organization
        object_name: Name of the Salesforce object
        
    Returns:
        pandas.DataFrame: DataFrame containing validation rules
    """
    try:
        # Validate inputs
        if not credentials or not isinstance(credentials, dict):
            raise ValueError("Invalid credentials provided")
        
        if selected_org not in credentials:
            raise ValueError(f"Organization '{selected_org}' not found in credentials")
        
        org_creds = credentials[selected_org]
        required_fields = ['username', 'password', 'security_token', 'domain']
        missing_fields = [field for field in required_fields if field not in org_creds]
        if missing_fields:
            raise ValueError(f"Missing required credential fields: {missing_fields}")
        
        # Connect to Salesforce
        print(f"Connecting to Salesforce org: {selected_org}")
        sf_conn = sf.Salesforce(
            username=org_creds['username'],
            password=org_creds['password'],
            security_token=org_creds['security_token'],
            domain=org_creds['domain']
        )
        
        print(f"Successfully connected to Salesforce. Session ID: {sf_conn.session_id[:10]}...")
        
        # Fetch validation rules
        print(f"Fetching validation rules for object: {object_name}")
        records = fetch_validation_rules_with_formula(sf_conn, object_name)
        df = pd.DataFrame(records)
        
        print(f"Found {len(df)} validation rules")
        
        # Save to DataFiles folder structure
        root_folder = "DataFiles"
        object_folder = os.path.join(root_folder, selected_org, object_name)
        os.makedirs(object_folder, exist_ok=True)
        csv_file_path = os.path.join(object_folder, "Formula_validation.csv")
        df.to_csv(csv_file_path, index=False)
        
        print(f"Saved validation rules to: {csv_file_path}")
        
        return df, csv_file_path
        
    except Exception as e:
        print(f"Error extracting validation rules: {e}")
        return None, None


class SalesforceFormulaConverter:
    """
    Intelligent converter that transforms Salesforce validation formulas to Python code
    """
    
    def __init__(self):
        # Mapping of Salesforce functions to Python equivalents
        self.function_mappings = {
            'ISBLANK': '_is_blank',
            'ISNULL': '_is_null', 
            'LEN': 'len',
            'TEXT': 'str',
            'VALUE': '_to_number',
            'UPPER': 'str.upper',
            'LOWER': 'str.lower',
            'TRIM': '_trim',
            'LEFT': '_left',
            'RIGHT': '_right',
            'MID': '_mid',
            'FIND': '_find',
            'CONTAINS': '_contains',
            'TODAY': '_today',
            'NOW': '_now',
            'YEAR': '_year',
            'MONTH': '_month',
            'DAY': '_day',
            'AND': '_and',
            'OR': '_or',
            'NOT': '_not',
            'IF': '_if',
            'CASE': '_case',
            'BEGINS': '_begins_with',
            'ENDS': '_ends_with',
            'ABS': 'abs',
            'ROUND': 'round',
            'CEILING': '_ceiling',
            'FLOOR': '_floor',
            'MAX': 'max',
            'MIN': 'min',
            'ISPICKVAL': '_ispickval',
            'ISCHANGED': '_ischanged',
            'ISNEW': '_isnew',
            'PRIORVALUE': '_priorvalue'
        }
        
        # Mapping of Salesforce operators to Python operators
        self.operator_mappings = {
            '&&': ' and ',
            '||': ' or ',
            '=': ' == ',
            '<>': ' != ',
            '!': ' not ',
        }
    
    def convert_formula_to_python(self, formula: str, field_name: str) -> str:
        """
        Convert Salesforce formula to Python code for DataFrame operations
        """
        if not formula or formula.lower() == 'nan':
            return f"df['{field_name}'].isna() | (df['{field_name}'] == '')  # Default validation - field is empty"
        
        try:
            # Clean and prepare the formula
            python_code = self._preprocess_formula(formula)
            
            # Convert field references
            python_code = self._convert_field_references(python_code, field_name)
            
            # Convert functions
            python_code = self._convert_functions(python_code)
            
            # Convert operators
            python_code = self._convert_operators(python_code)
            
            # Post-process and wrap in proper structure
            python_code = self._postprocess_formula(python_code)
            
            return python_code
            
        except Exception as e:
            print(f"Warning: Could not convert formula '{formula}'. Using default validation. Error: {e}")
            return f"df['{field_name}'].isna() | (df['{field_name}'] == '')  # Fallback validation - could not parse formula"

    def convert_formula_to_python_for_validation(self, formula: str) -> str:
        """
        Convert Salesforce formula to Python code for row-based validation
        """
        if not formula or formula.lower() == 'nan':
            return "False  # Default - invalid when formula is empty"
        
        try:
            print(f"Starting conversion for formula: {formula[:50]}...")
            
            # Clean and prepare the formula
            python_code = self._preprocess_formula(formula)
            print(f"After preprocessing: {python_code[:50]}...")
            
            # Convert operators FIRST (before functions) - important for AND/OR/NOT keywords
            python_code = self._convert_operators(python_code)
            print(f"After operator conversion: {python_code[:50]}...")
            
            # Convert functions (AFTER operators to avoid keyword conversion to function names)
            python_code = self._convert_functions(python_code)
            print(f"After function conversion: {python_code[:50]}...")
            
            # Convert field references for validation context
            python_code = self._convert_field_references_for_validation(python_code)
            print(f"After field conversion: {python_code[:50]}...")
            
            # Post-process for validation context (no DataFrame wrapping)
            python_code = self._postprocess_formula_for_validation(python_code)
            print(f"Final converted code: {python_code[:50]}...")
            
            return python_code
            
        except Exception as e:
            print(f"Error converting formula: {e}")
            return "False  # Fallback - invalid due to conversion error"
    
    def _preprocess_formula(self, formula: str) -> str:
        """Clean and prepare formula for conversion"""
        # Remove line breaks and normalize whitespace
        formula = re.sub(r'\n|\r', ' ', formula)
        formula = re.sub(r'\s+', ' ', formula.strip())
        
        # Handle common Salesforce syntax patterns
        formula = formula.replace('$ObjectType', 'ObjectType')
        formula = formula.replace('$User', 'User')
        
        # Handle ALL $-prefixed global merge fields (e.g. $Profile.Name, $UserRole.Name,
        # $Organization.Name, $Setup.X, $Label.X, $CustomMetadata.X, $Api.X, $System.X,
        # $RecordType.X).  Replace with the part after the "$" so the dot-flattening
        # stage can turn e.g. Profile.Name into Profile_Name and treat it as a field.
        formula = re.sub(r'\$(Profile|UserRole|Organization|Setup|Label|CustomMetadata|Api|System|RecordType)',
                         r'\1', formula, flags=re.IGNORECASE)
        
        # Handle picklist value comparisons - protect string literals
        # This is a basic approach - in a real implementation you'd need more sophisticated parsing
        
        return formula
    
    def _convert_field_references(self, formula: str, primary_field: str) -> str:
        """Convert field references to DataFrame column access"""
        # FIRST: Protect quoted strings so their content isn't treated as field names
        quoted_strings = {}
        quote_idx = 0
        
        def protect_quote(match):
            nonlocal quote_idx
            placeholder = f"__DFQUOTED_{quote_idx}__"
            quoted_strings[placeholder] = match.group(0)
            quote_idx += 1
            return placeholder
        
        formula = re.sub(r"'[^']*'|\"[^\"]*\"", protect_quote, formula)
        
        # Handle relationship field dot notation (e.g., Account__r.Name -> Account__r_Name)
        while re.search(r'([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)', formula):
            formula = re.sub(r'([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)', r'\1_\2', formula)
        
        # Pattern to match field references
        field_pattern = r'\b([A-Za-z][A-Za-z0-9_]*)\b'
        
        # Names to skip (not field references)
        skip_names = {
            'AND', 'OR', 'NOT', 'IF', 'TRUE', 'FALSE', 'NULL',
            'CASE', 'THEN', 'ELSE', 'END',
            'pd', 'df', 'np', 'len', 'str', 'int', 'float', 'bool',
            'True', 'False', 'None', 'null',
            'math', 'import', 'from', 'return', 'def', 'class',
        }
        
        def replace_field(match):
            field = match.group(1)
            # Skip function names
            if field.upper() in self.function_mappings:
                return field
            # Skip keywords and built-ins
            if field in skip_names or field.upper() in skip_names:
                return field
            # Skip placeholder names
            if '__DFQUOTED_' in field:
                return field
            # Convert field reference to DataFrame access
            return f"df['{field}']"
        
        result = re.sub(field_pattern, replace_field, formula)
        
        # Restore quoted strings
        for placeholder, original in quoted_strings.items():
            result = result.replace(placeholder, original)
        
        return result

    def _convert_field_references_for_validation(self, formula: str) -> str:
        """Convert field references for row-based validation functions"""
        print(f"DEBUG: Starting field reference conversion for: {formula}")
        
        # PRIORITY 1: Extract and protect quoted strings to preserve string literals
        quoted_strings = {}
        quote_placeholder_count = 0
        
        def protect_quoted_string(match):
            nonlocal quote_placeholder_count
            quoted_val = match.group(0)
            placeholder = f"__QUOTED_STRING_{quote_placeholder_count}__"
            quoted_strings[placeholder] = quoted_val
            quote_placeholder_count += 1
            return placeholder
        
        # Protect quoted strings FIRST
        formula = re.sub(r"'[^']*'|\"[^\"]*\"", protect_quoted_string, formula)
        print(f"DEBUG: Protected quoted strings: {quoted_strings}")
        print(f"DEBUG: After protecting quotes: {formula}")
        
        # PRIORITY 2: Extract and protect special Salesforce functions that take arguments
        # These functions must not have their arguments wrapped with safe_get()
        special_functions = {}
        special_func_count = 0
        
        # Protect ISCHANGED, ISNEW, PRIORVALUE functions with their complete arguments
        def protect_special_function(match):
            nonlocal special_func_count
            full_match = match.group(0)  # e.g., "ISCHANGED(OwnerId)"
            func_name = match.group(1).upper()  # e.g., "ISCHANGED"
            func_arg = match.group(2)  # e.g., "OwnerId"
            
            placeholder = f"__SPECIAL_FUNC_{special_func_count}__"
            
            # Store the function with its argument for later conversion
            special_functions[placeholder] = {
                'name': func_name,
                'arg': func_arg,
                'original': full_match
            }
            special_func_count += 1
            print(f"DEBUG: Protected {func_name}({func_arg}) -> {placeholder}")
            return placeholder
        
        # Extract special functions BEFORE field conversion
        # Pattern matches: ISCHANGED(FieldName), ISNEW(), PRIORVALUE(FieldName)
        formula = re.sub(r'\b(ISCHANGED|ISNEW|PRIORVALUE)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)', 
                         protect_special_function, formula, flags=re.IGNORECASE)
        print(f"DEBUG: After protecting special functions: {formula}")
        
        # PRIORITY 3: Handle Salesforce-specific references
        # Handle $Permission and $User references (replace with True/dummy values)
        original_formula = formula
        formula = re.sub(r'\$Permission\.[A-Za-z0-9_]+', 'True', formula, flags=re.IGNORECASE)
        formula = re.sub(r'\$User\.[A-Za-z0-9_]+', "'Unknown'", formula, flags=re.IGNORECASE)
        formula = formula.replace('$User', "'Unknown'")
        # Catch-all: strip any remaining $ prefix from global merge fields that
        # were not handled by _preprocess_formula (e.g. $Profile, $UserRole, etc.)
        formula = re.sub(r'\$([A-Za-z])', r'\1', formula)
        if formula != original_formula:
            print(f"DEBUG: After permission/user replacement: {formula}")
        
        # PRIORITY 4: Handle ALL dot-notation field references (both custom __r and standard like RecordType.Name)
        # Flatten recursively: Account__r.Owner.Name -> Account__r_Owner_Name
        # BUT DON'T touch placeholders
        original_formula = formula
        while re.search(r'(?<!__)([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)(?!__)', formula):
            # Make sure we're not converting inside placeholders
            formula = re.sub(r'(?<!_)(?<!__)([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)(?!_)(?!__)', r'\1_\2', formula)
            # If no change, break to avoid infinite loop
            if formula == original_formula:
                break
            original_formula = formula
        
        print(f"DEBUG: After relationship field conversion: {formula}")
        
        # PRIORITY 5: Now find and replace regular field references
        # Extract tokens but skip placeholder tokens
        tokens = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', formula)
        
        result_formula = formula
        
        for token in set(tokens):  # Use set to avoid duplicate replacements
            # Skip special placeholders
            if 'SPECIAL_FUNC_' in token or 'QUOTED_STRING_' in token:
                continue
            
            # Skip function names and keywords
            if token.upper() in self.function_mappings or token.upper() in ['AND', 'OR', 'NOT', 'IF', 'TRUE', 'FALSE', 'ISCHANGED', 'ISNEW', 'PRIORVALUE']:
                continue
                
            # Skip common keywords
            if token.lower() in ['true', 'false', 'null']:
                continue
            
            # Skip helper function names (Python equivalents that start with _)
            if token.startswith('_') and token in ['_ispickval', '_is_blank', '_is_null', '_to_number', 
                                                     '_trim', '_left', '_right', '_mid', '_find', '_contains',
                                                     '_today', '_now', '_year', '_month', '_day', '_and', '_or',
                                                     '_not', '_if', '_case', '_begins_with', '_ends_with',
                                                     '_ceiling', '_floor', '_regex', '_mod', '_substitute',
                                                     '_concatenate', '_datevalue', '_includes', '_excludes', '_ischanged', '_isnew', '_priorvalue']:
                continue
            
            # Check if this looks like a Salesforce field
            is_field = False
            
            # Salesforce custom fields end with __c
            if token.endswith('__c'):
                is_field = True
            # Relationship fields end with __r
            elif token.endswith('__r'):
                is_field = True
            # Field names with underscores (likely custom or flattened relationship)
            elif '_' in token and len(token) > 2:
                is_field = True
            # Any capitalized identifier (standard SF fields like Email, Phone, Name, Status, etc.)
            elif token[0].isupper() and len(token) > 1:
                is_field = True
            
            if is_field:
                # Replace whole word only
                safe_get_replacement = f"safe_get('{token}')"
                # Use word boundary regex to replace only whole words
                pattern = r'\b' + re.escape(token) + r'\b'
                old_formula = result_formula
                result_formula = re.sub(pattern, safe_get_replacement, result_formula)
                if old_formula != result_formula:
                    print(f"DEBUG: Converted field '{token}' -> 'safe_get('{token}')'")
        
        # PRIORITY 6: Convert the protected special functions to their Python equivalents
        # Now that field references are converted, convert ISCHANGED, ISNEW, PRIORVALUE
        for placeholder, func_info in special_functions.items():
            func_name = func_info['name'].upper()
            func_arg = func_info['arg']
            
            # The argument has already been wrapped with safe_get() if it's a field
            arg_converted = f"safe_get('{func_arg}')"
            
            # Convert to Python equivalent
            if func_name == 'ISCHANGED':
                python_equivalent = f"_ischanged({arg_converted})"
            elif func_name == 'ISNEW':
                python_equivalent = "_isnew()"
            elif func_name == 'PRIORVALUE':
                python_equivalent = f"_priorvalue({arg_converted})"
            else:
                python_equivalent = f"_is_blank({arg_converted})"  # Fallback
            
            result_formula = result_formula.replace(placeholder, python_equivalent)
            print(f"DEBUG: Converted {placeholder} -> {python_equivalent}")
        
        # PRIORITY 7: Restore the protected quoted strings
        for placeholder, original_value in quoted_strings.items():
            result_formula = result_formula.replace(placeholder, original_value)
            print(f"DEBUG: Restored {placeholder} -> {original_value}")
        
        print(f"DEBUG: Final field conversion result: {result_formula}")
        return result_formula
    
    def _convert_functions(self, formula: str) -> str:
        """Convert Salesforce functions to Python equivalents"""
        # Add additional function mappings for missing Salesforce functions
        extended_mappings = self.function_mappings.copy()
        extended_mappings.update({
            'REGEX': '_regex',
            'MOD': '_mod',
            'SUBSTITUTE': '_substitute',
            'CONCATENATE': '_concatenate',
            'DATEVALUE': '_datevalue',
            'INCLUDES': '_includes',
            'EXCLUDES': '_excludes',
        })
        
        for sf_func, py_func in extended_mappings.items():
            # Replace function calls (case insensitive)
            pattern = rf'\b{sf_func}\s*\('
            replacement = f'{py_func}('
            formula = re.sub(pattern, replacement, formula, flags=re.IGNORECASE)
        
        return formula
    
    def _convert_operators(self, formula: str) -> str:
        """Convert Salesforce operators to Python operators"""
        # Process operators in order: compound first, then single
        
        # FIRST: Handle Salesforce keyword operators (AND, OR, NOT) - case insensitive, as word boundaries
        # These must be done BEFORE other conversions
        formula = re.sub(r'\bAND\b', ' and ', formula, flags=re.IGNORECASE)
        formula = re.sub(r'\bOR\b', ' or ', formula, flags=re.IGNORECASE)
        formula = re.sub(r'\bNOT\b', ' not ', formula, flags=re.IGNORECASE)
        
        # Compound operators (must be done next to avoid partial replacements)
        formula = re.sub(r'<>', ' != ', formula)
        formula = re.sub(r'&&', ' and ', formula)
        formula = re.sub(r'\|\|', ' or ', formula)
        
        # Less/Greater than or equal
        formula = re.sub(r'<=', ' <= ', formula)
        formula = re.sub(r'>=', ' >= ', formula)
        
        # Less/Greater than (single)
        formula = re.sub(r'(?<![<>!])\s*<\s*(?!=)', ' < ', formula)
        formula = re.sub(r'(?<![<>!])\s*>\s*(?!=)', ' > ', formula)
        
        # Single equals (not already ==)
        formula = re.sub(r'(?<![=!<>])\s*=\s*(?!=)', ' == ', formula)
        
        # NOT operator (! but not !=)
        formula = re.sub(r'!(?!=)', ' not ', formula)
        
        return formula
    
    def _postprocess_formula(self, formula: str) -> str:
        """Final processing and wrapping"""
        # Ensure the formula returns a boolean series
        # Only wrap if formula doesn't start with 'df' and doesn't call a function that returns a Series
        if not formula.strip().startswith('df') and not any(func in formula for func in ['_is_blank', '_is_null', 'isna()', 'isnull()']):
            formula = f"pd.Series([{formula}] * len(df))"
        
        return formula
    
    def _postprocess_formula_for_validation(self, formula: str) -> str:
        """Final processing for validation context - no DataFrame wrapping needed"""
        # Convert boolean literals to proper Python case
        # BUT: Be careful not to replace inside string literals
        
        # Protect quoted strings first
        quoted_strings = {}
        quote_placeholder_count = 0
        
        def protect_quoted_string(match):
            nonlocal quote_placeholder_count
            quoted_val = match.group(0)
            placeholder = f"__QUOTED_STRING_{quote_placeholder_count}__"
            quoted_strings[placeholder] = quoted_val
            quote_placeholder_count += 1
            return placeholder
        
        formula_protected = re.sub(r"'[^']*'|\"[^\"]*\"", protect_quoted_string, formula)
        
        # Now convert boolean values
        formula_protected = re.sub(r'\btrue\b', 'True', formula_protected, flags=re.IGNORECASE)
        formula_protected = re.sub(r'\bfalse\b', 'False', formula_protected, flags=re.IGNORECASE)
        
        # Restore quoted strings
        for placeholder, original_value in quoted_strings.items():
            formula_protected = formula_protected.replace(placeholder, original_value)
        
        return formula_protected.strip()
    
    def generate_helper_functions(self) -> str:
        """Generate Python helper functions for Salesforce functions"""
        return '''
def _is_blank(value):
    """Salesforce ISBLANK function"""
    if hasattr(value, 'isna'):
        return value.isna() | (value == '')
    return pd.isna(value) or value == ''

def _is_null(value):
    """Salesforce ISNULL function"""
    if hasattr(value, 'isna'):
        return value.isna()
    return pd.isna(value)

def _to_number(value):
    """Salesforce VALUE function"""
    if hasattr(value, 'astype'):
        return pd.to_numeric(value, errors='coerce')
    try:
        return float(value)
    except:
        return 0

def _trim(text):
    """Salesforce TRIM function"""
    if hasattr(text, 'str'):
        return text.str.strip()
    return str(text).strip() if text else ''

def _left(text, num_chars):
    """Salesforce LEFT function"""
    if hasattr(text, 'str'):
        return text.str[:num_chars]
    return str(text)[:num_chars] if text else ''

def _right(text, num_chars):
    """Salesforce RIGHT function"""
    if hasattr(text, 'str'):
        return text.str[-num_chars:]
    return str(text)[-num_chars:] if text else ''

def _mid(text, start_pos, num_chars):
    """Salesforce MID function"""
    if hasattr(text, 'str'):
        return text.str[start_pos-1:start_pos-1+num_chars]
    return str(text)[start_pos-1:start_pos-1+num_chars] if text else ''

def _find(search_text, text):
    """Salesforce FIND function"""
    if hasattr(text, 'str'):
        return text.str.find(search_text) + 1  # Salesforce is 1-indexed
    return str(text).find(str(search_text)) + 1 if text else 0

def _contains(text, search_text):
    """Salesforce CONTAINS function"""
    if hasattr(text, 'str'):
        return text.str.contains(search_text, na=False)
    return str(search_text) in str(text) if text else False

def _today():
    """Salesforce TODAY function"""
    from datetime import date
    return date.today()

def _now():
    """Salesforce NOW function"""
    from datetime import datetime
    return datetime.now()

def _year(date_value):
    """Salesforce YEAR function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.year
    return pd.to_datetime(date_value).year if date_value else None

def _month(date_value):
    """Salesforce MONTH function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.month
    return pd.to_datetime(date_value).month if date_value else None

def _day(date_value):
    """Salesforce DAY function"""
    if hasattr(date_value, 'dt'):
        return date_value.dt.day
    return pd.to_datetime(date_value).day if date_value else None

def _and(*conditions):
    """Salesforce AND function"""
    result = conditions[0]
    for condition in conditions[1:]:
        result = result & condition
    return result

def _or(*conditions):
    """Salesforce OR function"""
    result = conditions[0]
    for condition in conditions[1:]:
        result = result | condition
    return result

def _not(condition):
    """Salesforce NOT function"""
    return ~condition

def _if(condition, true_value, false_value):
    """Salesforce IF function"""
    if hasattr(condition, '__len__') and len(condition) > 1:
        return pd.where(condition, true_value, false_value)
    return true_value if condition else false_value

def _begins_with(text, prefix):
    """Salesforce BEGINS function"""
    if hasattr(text, 'str'):
        return text.str.startswith(prefix)
    return str(text).startswith(str(prefix)) if text else False

def _ends_with(text, suffix):
    """Salesforce ENDS function"""
    if hasattr(text, 'str'):
        return text.str.endswith(suffix)
    return str(text).endswith(str(suffix)) if text else False

def _ceiling(number):
    """Salesforce CEILING function"""
    import math
    if hasattr(number, 'apply'):
        return number.apply(math.ceil)
    return math.ceil(number) if number else 0

def _floor(number):
    """Salesforce FLOOR function"""
    import math
    if hasattr(number, 'apply'):
        return number.apply(math.floor)
    return math.floor(number) if number else 0

def _mod(dividend, divisor):
    """Salesforce MOD function"""
    if hasattr(dividend, 'apply'):
        return dividend.apply(lambda x: x % divisor if divisor else 0)
    return int(dividend) % int(divisor) if dividend and divisor else 0

def _regex(text, pattern):
    """Salesforce REGEX function - checks if text matches pattern"""
    import re as regex_module
    if hasattr(text, 'str'):
        return text.str.contains(pattern, regex=True, na=False)
    return bool(regex_module.search(pattern, str(text))) if text else False

def _substitute(text, search_text, replace_text):
    """Salesforce SUBSTITUTE function - replaces text"""
    if hasattr(text, 'str'):
        return text.str.replace(search_text, replace_text)
    return str(text).replace(search_text, replace_text) if text else ''

def _concatenate(*args):
    """Salesforce CONCATENATE function - joins strings"""
    return ''.join(str(arg) for arg in args if arg is not None)

def _datevalue(date_string):
    """Salesforce DATEVALUE function - converts string to date"""
    try:
        return pd.to_datetime(date_string)
    except:
        return None

def _includes(field_value, search_value):
    """Salesforce INCLUDES function for multi-select picklists"""
    if hasattr(field_value, 'str'):
        return field_value.str.contains(search_value, na=False)
    return search_value in str(field_value) if field_value else False

def _excludes(field_value, search_value):
    """Salesforce EXCLUDES function for multi-select picklists"""
    if hasattr(field_value, 'str'):
        return ~field_value.str.contains(search_value, na=True)
    return search_value not in str(field_value) if field_value else True

def _ispickval(field_value, compare_value):
    """Salesforce ISPICKVAL function - check if field equals specific picklist value"""
    if hasattr(field_value, 'str'):
        # DataFrame Series - element-wise comparison
        return field_value.astype(str).str.strip() == str(compare_value).strip()
    # Scalar comparison
    field_str = str(field_value).strip() if field_value is not None and not pd.isna(field_value) else ''
    compare_str = str(compare_value).strip() if compare_value is not None else ''
    return field_str == compare_str

def _case(expression, *args):
    """Salesforce CASE function - CASE(expr, val1, result1, val2, result2, ..., else_result)"""
    if hasattr(expression, 'map'):
        # DataFrame Series - build mapping
        mapping = {}
        i = 0
        while i < len(args) - 1:
            mapping[args[i]] = args[i + 1]
            i += 2
        default = args[-1] if len(args) % 2 == 1 else None
        return expression.map(mapping).fillna(default)
    # Scalar
    i = 0
    while i < len(args) - 1:
        if expression == args[i]:
            return args[i + 1]
        i += 2
    return args[-1] if len(args) % 2 == 1 else None

def _trim(text):
    """Salesforce TRIM function"""
    if hasattr(text, 'str'):
        return text.str.strip()
    return str(text).strip() if text is not None and not pd.isna(text) else ''
'''

    def convert_formula_to_python_function(self, formula: str, function_name: str, rule_name: str, error_message: str) -> str:
        """
        Convert a single Salesforce formula to a Python validation function
        """
        try:
            # Convert the formula to Python logic
            python_logic = self.convert_formula_to_python_for_validation(formula)
            
            if not python_logic or python_logic.strip() == "":
                print(f"Warning: Empty python_logic for rule {rule_name}")
                return None
            
            # Escape any problematic characters in the logic for safe string formatting
            python_logic_safe = python_logic.replace('{', '{{').replace('}', '}}')
            
            # Create individual validation function template first
            function_template = '''
def {function_name}(row_data):
    """
    Validation function for rule: {rule_name}
    Original Salesforce formula: {formula}
    Error message: {error_message}
    
    Args:
        row_data: Dictionary containing the row data to validate
        
    Returns:
        bool: True if valid, False if invalid
    """
    try:
        # Convert to pandas-like object for compatibility
        if hasattr(row_data, 'get'):
            # Dictionary-like access
            get_field = lambda field: row_data.get(field, '')
        else:
            # Assume it's a pandas Series
            get_field = lambda field: getattr(row_data, field, '') if hasattr(row_data, field) else row_data.get(field, '') if hasattr(row_data, 'get') else ''
        
        # Helper function to safely get field values
        def safe_get(field_name):
            try:
                value = get_field(field_name)
                if pd.isna(value):
                    return ''
                return str(value).strip()
            except:
                return ''
        
        # Validation logic (converted from Salesforce formula)
        validation_result = {python_logic_placeholder}
        
        # Salesforce validation rules define ERROR conditions
        # If formula evaluates to True = Error condition = Record is INVALID
        # If formula evaluates to False = No error = Record is VALID
        # So we invert: True becomes False (invalid), False becomes True (valid)
        return not bool(validation_result)
        
    except Exception as e:
        # On error, assume invalid for safety
        print(f"Error in validation function {function_name}: {{str(e)}}")
        return False
'''
            
            # Now safely substitute the values
            function_code = function_template.format(
                function_name=function_name,
                rule_name=rule_name,
                formula=formula.replace('{', '{{').replace('}', '}}'),
                error_message=error_message.replace('{', '{{').replace('}', '}}'),
                python_logic_placeholder=python_logic
            )
            
            return function_code
            
        except Exception as e:
            print(f"Error converting formula '{formula}': {str(e)}")
            return None

    def test_basic_conversion(self, formula: str) -> str:
        """
        Test basic formula conversion without full function wrapping
        Used for debugging conversion issues
        """
        try:
            print(f"=== TESTING CONVERSION FOR: {formula} ===")
            
            # Step by step conversion with detailed output
            print(f"1. Original formula: {formula}")
            
            step1 = self._preprocess_formula(formula)
            print(f"2. After preprocessing: {step1}")
            
            step2 = self._convert_functions(step1)
            print(f"3. After function conversion: {step2}")
            
            step3 = self._convert_field_references_for_validation(step2)
            print(f"4. After field conversion: {step3}")
            
            step4 = self._convert_operators(step3)
            print(f"5. After operator conversion: {step4}")
            
            step5 = self._postprocess_formula_for_validation(step4)
            print(f"6. Final result: {step5}")
            
            print("=== CONVERSION TEST COMPLETE ===")
            return step5
        except Exception as e:
            print(f"Test conversion failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def validate_python_syntax(self, code: str) -> tuple:
        """
        Validate Python code syntax
        Returns: (is_valid: bool, error_message: str)
        """
        try:
            import ast
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def generate_complete_validation_bundle(self, python_functions: list, function_mappings: list, object_name: str) -> str:
        """
        Generate a complete validation bundle with all functions and helper utilities
        """
        import datetime
        helper_functions = self._generate_helper_functions()
        
        # Combine all functions
        all_functions = [helper_functions] + python_functions
        
        # Create function registry
        function_registry = {}
        for mapping in function_mappings:
            function_registry[mapping['rule_name']] = {
                'function_name': mapping['function_name'],
                'error_message': mapping['error_message'],
                'active': mapping.get('active', True)
            }
        
        bundle_content = f'''
"""
AI-Generated Validation Bundle for {object_name}
Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This file contains Python validation functions converted from Salesforce validation rules.
Each function validates a specific business rule extracted from Salesforce.
"""

import pandas as pd
import re
from datetime import datetime, date
from typing import Dict, List, Any, Union

# ================================
# HELPER FUNCTIONS
# ================================

{"".join(all_functions)}

# ================================
# FUNCTION REGISTRY
# ================================

VALIDATION_FUNCTIONS = {repr(function_registry)}

def get_all_validation_functions():
    """Get all available validation functions"""
    return VALIDATION_FUNCTIONS

def validate_record(row_data: Dict, active_only: bool = True) -> Dict:
    """
    Validate a single record against all validation rules
    
    Args:
        row_data: Dictionary containing the record data
        active_only: Only run active validation rules
        
    Returns:
        Dict with validation results
    """
    results = {{
        'is_valid': True,
        'errors': [],
        'rule_results': {{}}
    }}
    
    for rule_name, rule_info in VALIDATION_FUNCTIONS.items():
        if active_only and not rule_info.get('active', True):
            continue
            
        function_name = rule_info['function_name']
        error_message = rule_info['error_message']
        
        try:
            # Get the validation function
            validation_func = globals().get(function_name)
            if validation_func:
                is_valid = validation_func(row_data)
                results['rule_results'][rule_name] = is_valid
                
                if not is_valid:
                    results['is_valid'] = False
                    results['errors'].append({{
                        'rule': rule_name,
                        'message': error_message
                    }})
            else:
                print(f"Warning: Function {{function_name}} not found")
                
        except Exception as e:
            print(f"Error validating rule {{rule_name}}: {{str(e)}}")
            results['is_valid'] = False
            results['errors'].append({{
                'rule': rule_name,
                'message': f"Validation error: {{str(e)}}"
            }})
    
    return results

def validate_dataframe(df: pd.DataFrame, active_only: bool = True) -> pd.DataFrame:
    """
    Validate an entire DataFrame
    
    Args:
        df: DataFrame to validate
        active_only: Only run active validation rules
        
    Returns:
        DataFrame with validation results added
    """
    validation_results = []
    
    for index, row in df.iterrows():
        row_dict = row.to_dict()
        result = validate_record(row_dict, active_only)
        validation_results.append(result)
    
    # Add validation columns
    df_result = df.copy()
    df_result['is_valid'] = [r['is_valid'] for r in validation_results]
    df_result['validation_errors'] = [r['errors'] for r in validation_results]
    df_result['error_count'] = [len(r['errors']) for r in validation_results]
    
    return df_result
'''
        
        return bundle_content

    def generate_standalone_validator(self, bundle_file_path: str, object_name: str, function_mappings: list) -> str:
        """
        Generate a standalone validator script that can be run independently
        """
        import datetime
        return f'''
"""
Standalone Validator for {object_name}
Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This script can be used to validate CSV/Excel files using the generated validation bundle.
"""

import pandas as pd
import os
import sys
from typing import Dict, List

# Import the validation bundle
try:
    from {os.path.basename(bundle_file_path).replace('.py', '')} import validate_dataframe, get_all_validation_functions
except ImportError:
    print("Error: Could not import validation bundle. Make sure the bundle file is in the same directory.")
    sys.exit(1)

def validate_file(file_path: str, output_path: str = None) -> Dict:
    """
    Validate a CSV or Excel file
    
    Args:
        file_path: Path to the file to validate
        output_path: Optional path to save results
        
    Returns:
        Dict with validation summary
    """
    try:
        # Read the file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format. Please use CSV or Excel files.")
        
        print(f"Loaded {{len(df)}} records from {{file_path}}")
        
        # Run validation
        print("Running validation...")
        validated_df = validate_dataframe(df)
        
        # Calculate summary
        total_records = len(validated_df)
        valid_records = validated_df['is_valid'].sum()
        invalid_records = total_records - valid_records
        
        summary = {{
            'total_records': total_records,
            'valid_records': valid_records,
            'invalid_records': invalid_records,
            'success_rate': (valid_records / total_records * 100) if total_records > 0 else 0
        }}
        
        print(f"Validation complete:")
        print(f"  Total records: {{total_records}}")
        print(f"  Valid records: {{valid_records}}")
        print(f"  Invalid records: {{invalid_records}}")
        print(f"  Success rate: {{summary['success_rate']:.1f}}%")
        
        # Save results if output path provided
        if output_path:
            validated_df.to_csv(output_path, index=False)
            print(f"Results saved to: {{output_path}}")
        
        return {{
            'summary': summary,
            'validated_data': validated_df
        }}
        
    except Exception as e:
        print(f"Error validating file: {{str(e)}}")
        return {{'error': str(e)}}

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate CSV/Excel files using Salesforce validation rules')
    parser.add_argument('input_file', help='Path to the CSV or Excel file to validate')
    parser.add_argument('-o', '--output', help='Path to save validation results')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: File {{args.input_file}} not found")
        return
    
    # Run validation
    result = validate_file(args.input_file, args.output)
    
    if 'error' in result:
        print(f"Validation failed: {{result['error']}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''

    def _generate_helper_functions(self) -> str:
        """Generate helper functions needed for validation"""
        return '''
# Helper functions for Salesforce formula conversion

def _is_blank(value):
    """Check if value is blank (empty, null, or whitespace)"""
    if pd.isna(value):
        return True
    if value is None:
        return True
    if str(value).strip() == '':
        return True
    return False

def _is_null(value):
    """Check if value is null"""
    return pd.isna(value) or value is None

def _to_number(value):
    """Convert value to number"""
    try:
        return float(value)
    except:
        return 0

def _left(text, num_chars):
    """Get leftmost characters"""
    return str(text)[:int(num_chars)]

def _right(text, num_chars):
    """Get rightmost characters"""
    return str(text)[-int(num_chars):]

def _mid(text, start, length):
    """Get middle characters"""
    start_idx = int(start) - 1  # Salesforce is 1-indexed
    return str(text)[start_idx:start_idx + int(length)]

def _find(search_text, within_text):
    """Find position of text"""
    pos = str(within_text).find(str(search_text))
    return pos + 1 if pos >= 0 else 0  # Salesforce is 1-indexed

def _contains(text, search_text):
    """Check if text contains search text"""
    return str(search_text) in str(text)

def _begins_with(text, prefix):
    """Check if text begins with prefix"""
    return str(text).startswith(str(prefix))

def _ends_with(text, suffix):
    """Check if text ends with suffix"""
    return str(text).endswith(str(suffix))

def _today():
    """Get today's date"""
    return date.today()

def _now():
    """Get current datetime"""
    return datetime.now()

def _year(date_value):
    """Get year from date"""
    try:
        if isinstance(date_value, (date, datetime)):
            return date_value.year
        return int(str(date_value)[:4])
    except:
        return 0

def _month(date_value):
    """Get month from date"""
    try:
        if isinstance(date_value, (date, datetime)):
            return date_value.month
        return int(str(date_value)[5:7])
    except:
        return 0

def _day(date_value):
    """Get day from date"""
    try:
        if isinstance(date_value, (date, datetime)):
            return date_value.day
        return int(str(date_value)[8:10])
    except:
        return 0

def _and(*args):
    """Logical AND"""
    return all(args)

def _or(*args):
    """Logical OR"""
    return any(args)

def _not(value):
    """Logical NOT"""
    return not value

def _if(condition, true_value, false_value):
    """IF function"""
    return true_value if condition else false_value

def _ceiling(value):
    """Ceiling function"""
    import math
    return math.ceil(float(value))

def _floor(value):
    """Floor function"""
    import math
    return math.floor(float(value))

def _ispickval(field_value, compare_value):
    """Salesforce ISPICKVAL function - check if field equals specific picklist value"""
    field_str = str(field_value).strip() if field_value is not None else ''
    compare_str = str(compare_value).strip() if compare_value is not None else ''
    return field_str == compare_str

def _ischanged(field_value):
    """
    Salesforce ISCHANGED function - check if field changed
    NOTE: In offline/external validation we cannot detect field changes.
    Returning False so that rules guarded by ISCHANGED are skipped (safe default).
    """
    return False

def _isnew():
    """
    Salesforce ISNEW function - check if record is new
    NOTE: In offline/external validation we cannot detect record creation context.
    Returning False so that rules guarded by ISNEW are skipped (safe default).
    """
    return False

def _priorvalue(field_value):
    """
    Salesforce PRIORVALUE function - get prior value of field
    NOTE: In external validation context, we can't access the prior value, so return None/blank
    """
    return None
'''


def generate_validation_bundle_from_dataframe(validation_df, selected_org, object_name, output_dir=None):
    """
    Generate validation bundle from DataFrame containing validation rules
    
    Args:
        validation_df: DataFrame containing validation rules
        selected_org: Name of the selected organization
        object_name: Name of the Salesforce object
        output_dir: Optional output directory path
        
    Returns:
        tuple: (bundle_path, validator_path, num_functions)
    """
    # Create output directory structure
    root_dir = os.path.join("Validation", selected_org, object_name, "GenAIValidation")
    if output_dir is None:
        output_dir = os.path.join(root_dir, "validation_bundle")
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(root_dir, "ValidatedData"), exist_ok=True)
    
    # Generate validation functions for each rule
    bundle_content = "# Auto-generated validation bundle\nimport pandas as pd\nimport numpy as np\nfrom typing import List, Dict\n\n"
    validation_functions = []
    rule_names = []
    skipped_rules = []
    function_mappings = []  # Store function details for UI preview

    # Add global helper functions once at the top
    converter = SalesforceFormulaConverter()
    bundle_content += converter.generate_helper_functions()
    bundle_content += "\n"

    for index, row in validation_df.iterrows():
        active_value = str(row.get("Active", "")).lower()
        if active_value not in ["true", "1", "yes"]:
            skipped_rules.append(f"Row {index + 1}: Not active (Active='{row.get('Active', '')}')")
            continue

        name = str(row.get("ValidationName", "")).strip()
        formula = str(row.get("ErrorConditionFormula", "")).strip()
        field = str(row.get("FieldName", "")).strip()
        obj = str(row.get("ObjectName", "")).strip()

        if not name or name.lower() == 'nan':
            name = f"Rule_{index + 1}"

        field_names = parse_field_names(field)
        if not field_names:
            field_names = ['Id']

        if not formula or formula.lower() == 'nan':
            formula = f"ISBLANK({field_names[0]})"

        # Detect context-dependent formulas that cannot be validated offline
        _ctx_keywords = re.findall(
            r'\b(ISCHANGED|ISNEW|PRIORVALUE)\b|\$(Profile|UserRole|Permission|User|Organization|Setup|Label|CustomMetadata|Api|System|RecordType)\b',
            formula, flags=re.IGNORECASE
        )
        is_context_dependent = len(_ctx_keywords) > 0

        safe_name = safe_func_name(name)
        func_name = f"validate_{safe_name}"
        counter = 1
        original_func_name = func_name
        while func_name in validation_functions:
            func_name = f"{original_func_name}_{counter}"
            counter += 1

        func_code = build_function_code(name, formula, field, obj, is_context_dependent=is_context_dependent)
        bundle_content += func_code
        validation_functions.append(func_name)
        rule_names.append(name)
        
        # Store function mapping for UI preview
        function_mappings.append({
            'rule_name': name,
            'function_name': func_name,
            'formula': formula,
            'field': field,
            'object': obj,
            'active': True,
            'context_dependent': is_context_dependent
        })
        if is_context_dependent:
            matched_kw = [m[0] or f'${m[1]}' for m in _ctx_keywords]
            skipped_rules.append(
                f"Row {index + 1} ('{name}'): Uses context-dependent references "
                f"({', '.join(matched_kw)}) — will always pass in offline validation"
            )

    # Add validate_record and validate_dataframe functions
    print(f"DEBUG: Adding coordination functions with {len(validation_functions)} validation functions")
    print(f"DEBUG: Validation functions: {validation_functions}")
    
    bundle_content += """
def validate_record(row):
    '''Validate a single record (row) and return result dict.
    
    Each validation function receives a dict/Series and returns True (valid) or False (invalid).
    '''
    import pandas as pd
    # Convert to dict for consistent field access
    if hasattr(row, 'to_dict'):
        row_dict = row.to_dict()
    elif isinstance(row, dict):
        row_dict = row
    else:
        row_dict = dict(row)
    
    rule_results = {}
    errors = []
    is_valid = True
"""
    for func in validation_functions:
        bundle_content += f"""    try:
        rule_results['{func}'] = bool({func}(row_dict))
        if not rule_results['{func}']:
            errors.append('{func}')
    except Exception as e:
        rule_results['{func}'] = False
        errors.append(f'{func} (error: {{str(e)}})')
"""

    bundle_content += """    if errors:
        is_valid = False
    return {'is_valid': is_valid, 'errors': errors, 'rule_results': rule_results}
"""

    bundle_content += """
def validate_dataframe(df):
    '''Validate all records in a DataFrame'''
    valid_idx = []
    invalid_idx = []
    validation_results = []
    for idx, row in df.iterrows():
        result = validate_record(row)
        result['index'] = idx
        validation_results.append(result)
        if result['is_valid']:
            valid_idx.append(idx)
        else:
            invalid_idx.append(idx)
    valid_df = df.loc[valid_idx].copy()
    invalid_df = df.loc[invalid_idx].copy()
    return valid_df, invalid_df, validation_results
"""
    print(f"DEBUG: validate_dataframe function added")

    # Write bundle file with enhanced error handling
    bundle_path = os.path.join(output_dir, "bundle.py")
    
    # Debug: Check bundle content before writing
    print(f"DEBUG: Bundle content length: {len(bundle_content)} characters")
    print(f"DEBUG: Number of validation functions: {len(validation_functions)}")
    print(f"DEBUG: Bundle content ends with: ...{bundle_content[-200:]}")
    
    # Ensure the bundle content has the essential functions
    if "def validate_record" not in bundle_content:
        print("ERROR: validate_record function missing from bundle content!")
        return None, None, 0
        
    if "def validate_dataframe" not in bundle_content:
        print("ERROR: validate_dataframe function missing from bundle content!")
        return None, None, 0
    
    try:
        with open(bundle_path, "w", encoding="utf-8") as f:
            f.write(bundle_content)
        print(f"DEBUG: Bundle file written to: {bundle_path}")
    except Exception as e:
        print(f"ERROR: Failed to write bundle file: {e}")
        return None, None, 0
    
    # Verify file was written correctly
    try:
        with open(bundle_path, "r", encoding="utf-8") as f:
            written_content = f.read()
        print(f"DEBUG: Written file length: {len(written_content)} characters")
        print(f"DEBUG: File ends with: ...{written_content[-200:]}")
        
        # Check if critical functions are present
        has_validate_record = "def validate_record" in written_content
        has_validate_dataframe = "def validate_dataframe" in written_content
        print(f"DEBUG: validate_record present: {has_validate_record}")
        print(f"DEBUG: validate_dataframe present: {has_validate_dataframe}")
        
        # If functions are missing from the written file, something is wrong
        if not has_validate_record or not has_validate_dataframe:
            print("ERROR: Critical functions missing from written bundle file!")
            
            # Try to append the missing functions manually
            missing_functions = ""
            if not has_validate_record:
                missing_functions += f"""
def validate_record(row):
    '''Validate a single record (row) and return result dict'''
    import pandas as pd
    df = pd.DataFrame([row])
    rule_results = {{}}
    errors = []
    is_valid = True
"""
                for func in validation_functions:
                    missing_functions += f"    try:\n        rule_results['{func}'] = bool({func}(df).iloc[0])\n        if not rule_results['{func}']:\n            errors.append('{func}')\n    except Exception as e:\n        rule_results['{func}'] = False\n        errors.append(f'{func} (error: {{str(e)}})')\n"
                missing_functions += "    if errors:\n        is_valid = False\n    return {'is_valid': is_valid, 'errors': errors, 'rule_results': rule_results}\n"
            
            if not has_validate_dataframe:
                missing_functions += """
def validate_dataframe(df):
    '''Validate all records in a DataFrame'''
    valid_idx = []
    invalid_idx = []
    validation_results = []
    for idx, row in df.iterrows():
        result = validate_record(row)
        result['index'] = idx
        validation_results.append(result)
        if result['is_valid']:
            valid_idx.append(idx)
        else:
            invalid_idx.append(idx)
    valid_df = df.loc[valid_idx].copy()
    invalid_df = df.loc[invalid_idx].copy()
    return valid_df, invalid_df, validation_results
"""
            
            # Append missing functions
            with open(bundle_path, "a", encoding="utf-8") as f:
                f.write(missing_functions)
            print("DEBUG: Missing functions appended to bundle file")
        
    except Exception as e:
        print(f"DEBUG: Error verifying bundle file: {e}")
        return None, None, 0

    # Create validator script
    validator_content = f'''import pandas as pd
from bundle import validate_dataframe
import os

def validate_csv_data(csv_file_path, output_folder=None):
    """
    Validate CSV data using generated validation bundle
    
    Args:
        csv_file_path: Path to CSV file to validate
        output_folder: Optional output folder for results
    
    Returns:
        dict: Validation results summary
    """
    if output_folder is None:
        output_folder = os.path.join(os.path.dirname(__file__), '..', 'ValidatedData')
    
    os.makedirs(output_folder, exist_ok=True)
    
    try:
        # Load data
        df = pd.read_csv(csv_file_path)
        print(f"Loaded {{len(df)}} records from {{csv_file_path}}")
        
        # Validate data
        valid_df, invalid_df, validation_results = validate_dataframe(df)
        
        # Save results
        valid_df.to_csv(os.path.join(output_folder, 'success.csv'), index=False)
        invalid_df.to_csv(os.path.join(output_folder, 'failure.csv'), index=False)
        
        # Create summary
        summary = {{
            'total_records': len(df),
            'valid_records': len(valid_df),
            'invalid_records': len(invalid_df),
            'validation_rate': len(valid_df) / len(df) * 100 if len(df) > 0 else 0,
            'results_folder': output_folder
        }}
        
        print(f"\\n📊 Validation Results:")
        print(f"✅ Valid records: {{len(valid_df)}} ({{summary['validation_rate']:.1f}}%)")
        print(f"❌ Invalid records: {{len(invalid_df)}} ({{100-summary['validation_rate']:.1f}}%)")
        print(f"📁 Results saved to: {{output_folder}}")
        
        return summary
        
    except Exception as e:
        print(f"Error during validation: {{e}}")
        return None

if __name__ == "__main__":
    print("Validation Bundle - CSV Validator")
    # This can be called programmatically from the UI
'''

    validator_path = os.path.join(output_dir, "validator.py")
    with open(validator_path, "w", encoding="utf-8") as f:
        f.write(validator_content)

    return bundle_path, validator_path, len(validation_functions), function_mappings


def safe_func_name(name):
    """Convert name to safe Python function name"""
    return "".join(c if c.isalnum() or c == '_' else '_' for c in name.strip())


def parse_field_names(field_string):
    """
    Parse field names from CSV FieldName column that may contain comma-separated values
    """
    if not field_string or str(field_string).lower() == 'nan':
        return []
    
    # Clean up the field string
    field_string = str(field_string).strip()
    
    # Remove quotes and extra spaces
    field_string = field_string.replace('"', '').replace("'", "")
    
    # Split by comma and clean each field
    fields = [field.strip() for field in field_string.split(',') if field.strip()]
    
    # Filter out empty or invalid fields
    valid_fields = [field for field in fields if field and field != '' and len(field) > 0]
    
    return valid_fields


def build_function_code(name, formula, field, obj, is_context_dependent=False):
    """Build validation function code using row-based validation.
    
    Converts Salesforce Apex formula to a Python function that validates
    a single record (dict/Series) and returns True (valid) or False (invalid).
    Uses convert_formula_to_python_for_validation() which handles:
    - Quoted string protection
    - Relationship field flattening
    - $Permission/$User references
    - All SF functions (ISPICKVAL, REGEX, CONTAINS, etc.)
    
    If is_context_dependent is True, the generated function always returns True
    (valid) because runtime-only references like $Permission, $User, $Profile,
    ISCHANGED, ISNEW, PRIORVALUE cannot be evaluated in offline validation.
    """
    func_name = f"validate_{safe_func_name(name)}"
    
    # Initialize the formula converter
    converter = SalesforceFormulaConverter()
    
    # Parse field names (handle comma-separated values)
    field_names = parse_field_names(field)
    primary_field = field_names[0] if field_names else 'Id'
    
    # Convert Salesforce formula to Python code for row-based validation
    if is_context_dependent:
        # Rule uses runtime-only references ($Permission, $User, ISCHANGED, etc.)
        # Cannot evaluate offline — always treat as valid (error condition = False)
        python_logic = "False  # Context-dependent rule — skipped in offline validation"
        field_comment = f"# SKIPPED: This rule uses runtime context ($Permission/$User/ISCHANGED/etc.) that cannot be evaluated offline"
    elif formula and formula.lower() != 'nan' and formula.strip():
        try:
            python_logic = converter.convert_formula_to_python_for_validation(formula)
            # Only fall back if conversion produced a fallback marker or empty result
            if not python_logic or python_logic.strip() == '' or python_logic.strip().startswith('False  # Fallback') or python_logic.strip().startswith('False  # Default'):
                python_logic = f"_is_blank(safe_get('{primary_field}'))"
            field_comment = f"# Primary Field: {primary_field}"
            if len(field_names) > 1:
                field_comment += f"\n    # Additional Fields: {', '.join(field_names[1:])}"
        except Exception as e:
            print(f"Warning: Error converting formula for '{name}': {e}")
            python_logic = f"_is_blank(safe_get('{primary_field}'))"
            field_comment = f"# Field: {primary_field} (Formula conversion failed - using default ISBLANK check)"
    else:
        python_logic = f"_is_blank(safe_get('{primary_field}'))"
        field_comment = f"# Field: {primary_field} (No formula provided - using default ISBLANK check)"
    
    obj_str = obj if obj and obj.lower() != 'nan' else 'Not specified'
    formula_str = formula if formula and formula.lower() != 'nan' else 'Not specified'
    additional_fields_str = ", ".join(field_names[1:]) if len(field_names) > 1 else ""
    docstring_additional = f"Additional Fields: {additional_fields_str}" if additional_fields_str else ""
    
    # Build the required_fields list for the presence check
    fields_list_str = repr(field_names)
    
    return f'''
def {func_name}(row_data):
    """
    Validation Rule: {name}
    Salesforce Object: {obj_str}
    Primary Field: {primary_field}
    {docstring_additional}
    
    Original Apex Formula:
    {formula_str}
    
    Args:
        row_data: Dictionary or pandas Series containing the row data to validate
    Returns:
        bool: True if record is valid, False if invalid
    """
    {field_comment}
    
    import pandas as pd
    
    # Skip this rule if none of its required fields are present in the data
    _required_fields = {fields_list_str}
    if hasattr(row_data, 'keys'):
        _available = set(row_data.keys())
    elif hasattr(row_data, 'index'):
        _available = set(row_data.index)
    else:
        _available = set()
    if _required_fields and not _available.intersection(_required_fields):
        return True  # Skip: none of the rule fields are in the data
    
    # Helper to safely retrieve field values from row data
    def safe_get(field_name):
        try:
            if hasattr(row_data, 'get'):
                value = row_data.get(field_name, '')
            elif hasattr(row_data, '__getitem__'):
                try:
                    value = row_data[field_name]
                except (KeyError, IndexError):
                    value = ''
            else:
                value = ''
            if pd.isna(value):
                return ''
            return value
        except:
            return ''
    
    try:
        # Evaluate the error condition (converted from Salesforce formula)
        # Salesforce: formula True = Error condition = Record is INVALID
        # Salesforce: formula False = No error = Record is VALID
        error_condition = {python_logic}
        
        # Invert: return True when valid (no error), False when invalid (error)
        return not bool(error_condition)
        
    except Exception as e:
        print(f"Warning: Error in validation rule \\'{name}\\': {{e}}")
        return False  # Mark as invalid on error
'''


def add_master_detail_awareness_to_validation_rules(
    validation_rules_df: pd.DataFrame,
    sf_conn,
    object_name: str
) -> pd.DataFrame:
    """
    Add Master-Detail awareness to validation rules
    Flags validation rules that involve Master-Detail fields
    
    Args:
        validation_rules_df: DataFrame of validation rules
        sf_conn: Salesforce connection
        object_name: Object name
    
    Returns:
        Updated DataFrame with Master-Detail metadata
    """
    try:
        # Get Master-Detail fields
        object_metadata = getattr(sf_conn, object_name).describe()
        md_field_names = [
            field['name'] for field in object_metadata['fields']
            if field.get('type') == 'masterdetail'
        ]
        
        if not md_field_names:
            return validation_rules_df
        
        # Add Master-Detail flag column
        validation_rules_df['involves_master_detail'] = False
        validation_rules_df['master_detail_fields_involved'] = ''
        
        # Check each rule for Master-Detail field references
        for idx, rule in validation_rules_df.iterrows():
            formula = str(rule.get('ErrorConditionFormula', ''))
            
            involved_md_fields = []
            for md_field in md_field_names:
                if md_field in formula:
                    involved_md_fields.append(md_field)
            
            if involved_md_fields:
                validation_rules_df.at[idx, 'involves_master_detail'] = True
                validation_rules_df.at[idx, 'master_detail_fields_involved'] = ','.join(involved_md_fields)
        
        return validation_rules_df
    
    except Exception as e:
        print(f"Warning: Could not add Master-Detail awareness: {str(e)}")
        return validation_rules_df
