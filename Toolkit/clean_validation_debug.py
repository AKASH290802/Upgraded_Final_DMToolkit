"""
Script to remove all debug st.write statements from validation_operations.py
"""
import re

def clean_validation_debug():
    """Remove all validation debug st.write statements"""
    
    file_path = r"C:\DM_toolkit\ui_components\validation_operations.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match validation debug st.write statements
    patterns_to_remove = [
        r'^\s*st\.write\(f"[^"]*\*\*[^"]*Validation[^"]*"\)\s*\n',
        r'^\s*st\.write\(f"[^"]*Range Validation[^"]*"\)\s*\n',
        r'^\s*st\.write\(f"[^"]*Length[^"]*Validation[^"]*"\)\s*\n',
        r'^\s*st\.write\(f"[^"]*Minimum Validation[^"]*"\)\s*\n',
        r'^\s*st\.write\(f"[^"]*Maximum Validation[^"]*"\)\s*\n',
        r'^\s*st\.write\(f"[^"]*Email Format Validation[^"]*"\)\s*\n',
        r'^\s*st\.write\(f"[^"]*Phone Format Validation[^"]*"\)\s*\n',
        r'^\s*st\.write\(f"[^"]*Required Field Validation[^"]*"\)\s*\n',
        r'^\s*st\.write\(f"[^"]*Allowed Values Validation[^"]*"\)\s*\n',
    ]
    
    original_lines = len(content.split('\n'))
    
    # Remove debug statements
    for pattern in patterns_to_remove:
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    # Also remove any remaining validation debug statements with a more general pattern
    general_pattern = r'^\s*st\.write\(f"[^"]*\*\*[^"]*Validation[^"]*PASS.*FAIL[^"]*"\)\s*\n'
    content = re.sub(general_pattern, '', content, flags=re.MULTILINE)
    
    # Clean up any double newlines that might have been created
    content = re.sub(r'\n\n\n+', '\n\n', content)
    
    # Write the cleaned content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    final_lines = len(content.split('\n'))
    lines_removed = original_lines - final_lines
    
    print(f"✅ Cleaned validation debug statements")
    print(f"   Original lines: {original_lines}")
    print(f"   Final lines: {final_lines}")  
    print(f"   Lines removed: {lines_removed}")

if __name__ == "__main__":
    clean_validation_debug()