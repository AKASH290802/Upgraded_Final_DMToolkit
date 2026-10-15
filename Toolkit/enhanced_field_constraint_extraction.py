"""
Enhanced Field and Constraint Extraction Logic for Custom Validation
This module provides comprehensive extraction of fields and constraints from validation rule error messages
"""
import re
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional

def extract_field_names_from_message(error_message: str, rule_name: str = "") -> List[str]:
    """Enhanced field name extraction from error messages"""
    
    extracted_fields = []
    
    # Comprehensive field extraction patterns
    field_patterns = [
        # 1. Fields in single or double quotes
        r"'([^']+)'\s+(?:field|must|cannot|should|is|are)",
        r'"([^"]+)"\s+(?:field|must|cannot|should|is|are)',
        
        # 2. Field names at sentence beginning
        r"^([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:must|cannot|should|is required|is mandatory|field)",
        
        # 3. Field names with specific validation keywords
        r"([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:must be|cannot be|should be|is required|is mandatory)",
        
        # 4. Fields mentioned with actions
        r"(?:enter|provide|fill|specify|input|select)\s+(?:a\s+|an\s+|the\s+|valid\s+)?([A-Za-z][A-Za-z0-9_\s]*?)(?:\s|$|\.)",
        
        # 5. Fields with error context
        r"(?:invalid|missing|empty|blank|incorrect|wrong)\s+([A-Za-z][A-Za-z0-9_\s]*?)(?:\s|$|\.)",
        
        # 6. Fields in "for" context
        r"for\s+(?:the\s+)?([A-Za-z][A-Za-z0-9_\s]*?)(?:\s|$|\.)",
        
        # 7. Field names before "field" keyword
        r"([A-Za-z][A-Za-z0-9_\s]*?)\s+field",
        
        # 8. Possessive field references
        r"([A-Za-z][A-Za-z0-9_\s]*?)(?:'s|'s)\s+(?:value|format|length)",
        
        # 9. Fields in conditional statements
        r"when\s+([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:is|equals|contains)",
        
        # 10. Fields with type/format context
        r"([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:format|type|value|number|date|email|phone)",
    ]
    
    # Apply all patterns
    for pattern in field_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]  # Take first group if tuple
            
            # Clean and validate field name
            field_name = match.strip()
            
            # Skip if too short, too long, or contains only common words
            if (len(field_name) < 2 or len(field_name) > 50 or 
                field_name.lower() in ['a', 'an', 'the', 'is', 'are', 'be', 'and', 'or', 'not', 'for', 'to', 'in', 'on', 'at', 'by', 'with']):
                continue
            
            # Skip if it's a common validation word
            validation_words = ['required', 'mandatory', 'optional', 'valid', 'invalid', 'format', 'pattern', 'value', 'number', 'text']
            if field_name.lower() in validation_words:
                continue
            
            extracted_fields.append(field_name)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_fields = []
    for field in extracted_fields:
        field_lower = field.lower()
        if field_lower not in seen:
            seen.add(field_lower)
            unique_fields.append(field)
    
    return unique_fields

def extract_constraints_from_message(error_message: str, rule_name: str = "") -> Dict[str, Any]:
    """Enhanced constraint extraction from error messages"""
    
    constraints = {}
    constraint_types = []
    
    message_lower = error_message.lower()
    
    # 1. REQUIRED/MANDATORY CONSTRAINTS
    required_patterns = [
        r'(?:is\s+)?required',
        r'(?:is\s+)?mandatory', 
        r'cannot\s+be\s+(?:blank|empty|null)',
        r'must\s+not\s+be\s+(?:blank|empty|null)',
        r'(?:must|should)\s+be\s+(?:provided|filled|specified)',
        r'please\s+(?:enter|provide|fill|specify)'
    ]
    
    for pattern in required_patterns:
        if re.search(pattern, message_lower):
            constraints['required'] = True
            constraint_types.append('required')
            break
    
    # 2. RANGE CONSTRAINTS
    range_patterns = [
        # "between X and Y"
        r'between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)',
        # "from X to Y"  
        r'from\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)',
        # "X to Y" or "X-Y"
        r'(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)',
        # "in the range X-Y"
        r'(?:in\s+the\s+)?range\s+(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)',
    ]
    
    for pattern in range_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            min_val, max_val = float(matches[0][0]), float(matches[0][1])
            constraints['min_value'] = min_val
            constraints['max_value'] = max_val
            constraint_types.append('range')
            break
    
    # 3. MINIMUM CONSTRAINTS
    min_patterns = [
        r'(?:minimum|min|at\s+least|greater\s+than\s+or\s+equal\s+to|>=)\s+(\d+(?:\.\d+)?)',
        r'must\s+be\s+(\d+(?:\.\d+)?)\s+or\s+(?:more|greater|higher)',
        r'(?:no\s+less\s+than|not\s+less\s+than)\s+(\d+(?:\.\d+)?)',
    ]
    
    for pattern in min_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches and 'min_value' not in constraints:
            constraints['min_value'] = float(matches[0])
            constraint_types.append('minimum')
            break
    
    # 4. MAXIMUM CONSTRAINTS  
    max_patterns = [
        r'(?:maximum|max|at\s+most|no\s+more\s+than|less\s+than\s+or\s+equal\s+to|<=)\s+(\d+(?:\.\d+)?)',
        r'must\s+be\s+(\d+(?:\.\d+)?)\s+or\s+(?:less|fewer|lower)',
        r'(?:cannot\s+exceed|should\s+not\s+exceed|must\s+not\s+exceed)\s+(\d+(?:\.\d+)?)',
    ]
    
    for pattern in max_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches and 'max_value' not in constraints:
            constraints['max_value'] = float(matches[0])
            constraint_types.append('maximum')
            break
    
    # 5. LENGTH CONSTRAINTS
    length_patterns = [
        # Exact length
        r'(?:must\s+be\s+|exactly\s+|should\s+be\s+)?(\d+)\s+characters?\s+(?:long|in\s+length)',
        r'length\s+(?:of\s+|must\s+be\s+|should\s+be\s+)?(\d+)',
        
        # Minimum length
        r'(?:minimum|min|at\s+least)\s+(\d+)\s+characters?',
        r'(?:must\s+be\s+at\s+least|should\s+be\s+at\s+least)\s+(\d+)\s+characters?',
        
        # Maximum length
        r'(?:maximum|max|at\s+most|no\s+more\s+than)\s+(\d+)\s+characters?',
        r'(?:must\s+not\s+exceed|cannot\s+exceed)\s+(\d+)\s+characters?',
        
        # Range length
        r'between\s+(\d+)\s+and\s+(\d+)\s+characters?',
        r'(\d+)\s*(?:to|-)\s*(\d+)\s+characters?',
    ]
    
    for pattern in length_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            if 'minimum' in pattern or 'at least' in pattern:
                constraints['min_length'] = int(matches[0])
                constraint_types.append('min_length')
            elif 'maximum' in pattern or 'at most' in pattern or 'exceed' in pattern:
                constraints['max_length'] = int(matches[0])
                constraint_types.append('max_length')
            elif 'between' in pattern or 'to' in pattern or '-' in pattern:
                if isinstance(matches[0], tuple) and len(matches[0]) == 2:
                    constraints['min_length'] = int(matches[0][0])
                    constraints['max_length'] = int(matches[0][1])
                    constraint_types.append('length_range')
            else:
                constraints['exact_length'] = int(matches[0])
                constraint_types.append('exact_length')
            break
    
    # 6. FORMAT CONSTRAINTS
    format_patterns = {
        'email': [r'(?:valid\s+)?email(?:\s+address)?(?:\s+format)?', r'@.*\..*format', r'electronic\s+mail'],
        'phone': [r'(?:valid\s+)?phone(?:\s+number)?(?:\s+format)?', r'telephone(?:\s+number)?', r'\d{3}[-.]?\d{3}[-.]?\d{4}'],
        'date': [r'(?:valid\s+)?date(?:\s+format)?', r'mm/dd/yyyy|dd/mm/yyyy|yyyy-mm-dd', r'date\s+format'],
        'url': [r'(?:valid\s+)?url(?:\s+format)?', r'web(?:site)?\s+address', r'http[s]?://'],
        'zip': [r'(?:zip|postal)\s+code', r'\d{5}(?:-\d{4})?'],
        'ssn': [r'social\s+security\s+number', r'ssn', r'\d{3}-\d{2}-\d{4}'],
    }
    
    for format_type, patterns in format_patterns.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                constraints['format_type'] = format_type
                constraint_types.append('format')
                break
        if 'format_type' in constraints:
            break
    
    # Custom format patterns
    custom_format_patterns = [
        r'format\s+(?:must\s+be|should\s+be)\s+"([^"]+)"',
        r'pattern\s+"([^"]+)"',
        r'must\s+match\s+(?:the\s+)?pattern\s+"([^"]+)"',
    ]
    
    for pattern in custom_format_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            constraints['format_pattern'] = matches[0]
            constraint_types.append('custom_format')
            break
    
    # 7. VALUE CONSTRAINTS
    # Allowed values
    allowed_value_patterns = [
        r'must\s+be\s+(?:one\s+of\s+)?(?:the\s+following:?\s*)?["\']([^"\']+)["\']',
        r'(?:only\s+|should\s+be\s+)?(?:one\s+of\s+)?["\']([^"\']+)["\'](?:\s+(?:or|,)\s+["\']([^"\']+)["\'])*',
        r'valid\s+values?\s+(?:are|include)?\s*:?\s*["\']([^"\']+)["\']',
    ]
    
    for pattern in allowed_value_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            allowed_values = []
            for match in matches:
                if isinstance(match, tuple):
                    allowed_values.extend([v for v in match if v])
                else:
                    allowed_values.append(match)
            if allowed_values:
                constraints['allowed_values'] = allowed_values
                constraint_types.append('allowed_values')
            break
    
    # Prohibited values
    prohibited_value_patterns = [
        r'cannot\s+be\s+["\']([^"\']+)["\']',
        r'(?:not\s+allowed\s+to\s+be|should\s+not\s+be)\s+["\']([^"\']+)["\']',
        r'prohibited\s+values?\s*:?\s*["\']([^"\']+)["\']',
    ]
    
    for pattern in prohibited_value_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            prohibited_values = []
            for match in matches:
                if isinstance(match, tuple):
                    prohibited_values.extend([v for v in match if v])
                else:
                    prohibited_values.append(match)
            if prohibited_values:
                constraints['prohibited_values'] = prohibited_values
                constraint_types.append('prohibited_values')
            break
    
    # 8. CONDITIONAL CONSTRAINTS
    conditional_patterns = [
        r'when\s+([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:is|equals?|contains?)\s+["\']([^"\']+)["\']',
        r'if\s+([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:is|equals?|contains?)\s+["\']([^"\']+)["\']',
        r'only\s+when\s+([A-Za-z][A-Za-z0-9_\s]*?)\s+(?:is|equals?)\s+["\']([^"\']+)["\']',
    ]
    
    for pattern in conditional_patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        if matches:
            condition_field, condition_value = matches[0]
            constraints['condition'] = {
                'field': condition_field.strip(),
                'value': condition_value.strip()
            }
            constraint_types.append('conditional')
            break
    
    # 9. UNIQUENESS CONSTRAINTS
    uniqueness_patterns = [
        r'must\s+be\s+unique',
        r'(?:already\s+exists|duplicate\s+(?:value|entry))',
        r'uniqueness\s+(?:constraint|violation)',
        r'cannot\s+be\s+(?:duplicated|the\s+same)',
    ]
    
    for pattern in uniqueness_patterns:
        if re.search(pattern, message_lower):
            constraints['unique'] = True
            constraint_types.append('unique')
            break
    
    constraints['constraint_types'] = constraint_types
    return constraints

def determine_validation_logic(constraints: Dict[str, Any]) -> str:
    """Determine the appropriate validation logic based on extracted constraints"""
    
    constraint_types = constraints.get('constraint_types', [])
    
    if 'range' in constraint_types:
        return 'range_validation'
    elif 'minimum' in constraint_types and 'maximum' in constraint_types:
        return 'min_max_validation'
    elif 'minimum' in constraint_types:
        return 'minimum_validation'
    elif 'maximum' in constraint_types:
        return 'maximum_validation'
    elif 'length_range' in constraint_types:
        return 'length_range_validation'
    elif 'min_length' in constraint_types or 'max_length' in constraint_types:
        return 'length_validation'
    elif 'exact_length' in constraint_types:
        return 'exact_length_validation'
    elif 'format' in constraint_types or 'custom_format' in constraint_types:
        return 'format_validation'
    elif 'allowed_values' in constraint_types:
        return 'allowed_values_validation'
    elif 'prohibited_values' in constraint_types:
        return 'prohibited_values_validation'
    elif 'conditional' in constraint_types:
        return 'conditional_validation'
    elif 'unique' in constraint_types:
        return 'uniqueness_validation'
    elif 'required' in constraint_types:
        return 'required_validation'
    else:
        return 'default_validation'

def apply_enhanced_validation(row: pd.Series, field_name: str, constraints: Dict[str, Any]) -> Tuple[bool, str]:
    """Apply validation based on enhanced constraint extraction"""
    
    if not field_name or field_name not in row.index:
        return True, "Field not found in data"
    
    field_value = row[field_name]
    validation_logic = determine_validation_logic(constraints)
    
    # Handle empty values
    if pd.isna(field_value) or str(field_value).strip() == '':
        if constraints.get('required', False):
            return False, f"Required field '{field_name}' is empty"
        else:
            return True, f"Empty field '{field_name}' is acceptable"
    
    value_str = str(field_value).strip()
    
    # Apply specific validation logic
    try:
        if validation_logic == 'range_validation':
            num_value = float(value_str)
            min_val = constraints['min_value']
            max_val = constraints['max_value']
            if min_val <= num_value <= max_val:
                return True, f"Value {num_value} is within range [{min_val}, {max_val}]"
            else:
                return False, f"Value {num_value} is outside range [{min_val}, {max_val}]"
        
        elif validation_logic == 'minimum_validation':
            num_value = float(value_str)
            min_val = constraints['min_value']
            if num_value >= min_val:
                return True, f"Value {num_value} meets minimum requirement of {min_val}"
            else:
                return False, f"Value {num_value} is below minimum requirement of {min_val}"
        
        elif validation_logic == 'maximum_validation':
            num_value = float(value_str)
            max_val = constraints['max_value']
            if num_value <= max_val:
                return True, f"Value {num_value} meets maximum requirement of {max_val}"
            else:
                return False, f"Value {num_value} exceeds maximum requirement of {max_val}"
        
        elif validation_logic == 'length_range_validation':
            length = len(value_str)
            min_len = constraints['min_length']
            max_len = constraints['max_length']
            if min_len <= length <= max_len:
                return True, f"Length {length} is within range [{min_len}, {max_len}]"
            else:
                return False, f"Length {length} is outside range [{min_len}, {max_len}]"
        
        elif validation_logic == 'exact_length_validation':
            length = len(value_str)
            exact_len = constraints['exact_length']
            if length == exact_len:
                return True, f"Length {length} matches required length {exact_len}"
            else:
                return False, f"Length {length} does not match required length {exact_len}"
        
        elif validation_logic == 'format_validation':
            format_type = constraints.get('format_type')
            if format_type == 'email':
                if '@' in value_str and '.' in value_str.split('@')[-1]:
                    return True, f"Email format is valid"
                else:
                    return False, f"Email format is invalid"
            elif format_type == 'phone':
                digits = re.sub(r'[^\\d]', '', value_str)
                if len(digits) >= 10:
                    return True, f"Phone format is valid"
                else:
                    return False, f"Phone format is invalid"
            # Add more format validations as needed
        
        elif validation_logic == 'allowed_values_validation':
            allowed_values = constraints['allowed_values']
            if value_str in allowed_values:
                return True, f"Value '{value_str}' is in allowed list"
            else:
                return False, f"Value '{value_str}' is not in allowed list: {allowed_values}"
        
        elif validation_logic == 'prohibited_values_validation':
            prohibited_values = constraints['prohibited_values']
            if value_str not in prohibited_values:
                return True, f"Value '{value_str}' is not in prohibited list"
            else:
                return False, f"Value '{value_str}' is in prohibited list: {prohibited_values}"
        
        elif validation_logic == 'required_validation':
            return True, f"Required field '{field_name}' has value"
        
        else:  # default_validation
            return True, f"Default validation passed for field '{field_name}'"
    
    except Exception as e:
        return False, f"Validation error: {str(e)}"

# Test the enhanced extraction
if __name__ == "__main__":
    # Test message
    test_message = "Account Name is required and cannot be blank"
    
    fields = extract_field_names_from_message(test_message)
    constraints = extract_constraints_from_message(test_message)
    logic = determine_validation_logic(constraints)
    
    print(f"Message: {test_message}")
    print(f"Extracted fields: {fields}")
    print(f"Extracted constraints: {constraints}")
    print(f"Validation logic: {logic}")