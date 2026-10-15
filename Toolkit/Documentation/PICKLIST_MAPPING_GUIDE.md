# Picklist Mapping Feature Documentation

## Overview
The Picklist Mapping feature allows users to create and manage value transformations between source data and Salesforce picklist fields. This ensures that validation and data loading operations can automatically transform source values to match Salesforce picklist options.

## Feature Location
**Configuration → Picklist Mappings**

## How It Works

### 1. Create New Mappings
**Step 1: Upload Sample File**
- Upload a CSV or Excel file containing data with picklist values
- System displays file preview and summary

**Step 2: Select Salesforce Configuration**
- Choose Salesforce Organization
- Choose Salesforce Object
- Optionally load existing field mappings

**Step 3: Analyze Picklist Fields**
- Click "Detect Picklist Fields" button
- System automatically:
  - Identifies picklist fields in your data
  - Extracts unique values from each field
  - Compares with Salesforce valid values
  - Shows which values need mapping

**Step 4: Map Values**
- For each picklist field, system shows:
  - Values that already match Salesforce (no mapping needed)
  - Values that need mapping
  - Record count for each value
- User selects target Salesforce value for each source value using dropdowns
- Only active Salesforce picklist values are shown

**Step 5: Save Mappings**
- Click "Save All Mappings"
- Mappings are stored in: `picklist_mappings/{org_name}/{object_name}/picklist_mappings.json`

### 2. View/Edit Mappings
- Select Organization and Object
- View all existing mappings
- Download mappings as CSV
- See last updated timestamp

### 3. Delete Mappings
- Delete specific field mappings
- Delete all mappings for an object
- Confirmation required for deletion

## File Structure

```
c:\DM_toolkit\picklist_mappings\
├── HeraQA\
│   ├── Account\
│   │   └── picklist_mappings.json
│   └── WOD_2__Claim__c\
│       └── picklist_mappings.json
└── TestQA\
    └── Account\
        └── picklist_mappings.json
```

### Mapping File Format
```json
{
    "org_name": "HeraQA",
    "object_name": "Account",
    "last_updated": "2025-11-26 10:30:00",
    "fields": {
        "Status__c": {
            "csv_column": "Status_CSV",
            "mappings": {
                "Act": "Active",
                "Inact": "Inactive",
                "Pend": "Pending",
                "Active": "Active"
            }
        },
        "Industry": {
            "csv_column": "Industry_Code",
            "mappings": {
                "Mfg": "Manufacturing",
                "Tech": "Technology",
                "Fin": "Finance"
            }
        }
    }
}
```

## Integration with Validation

### Automatic Transformation
When Schema Validation runs with "Validate Picklist Values" enabled:

1. **Load Mappings**: System loads saved mappings for the org/object
2. **Transform Values**: For each picklist field value:
   - Check if mapping exists
   - Transform source → target value
   - Validate transformed value against Salesforce
3. **Enhanced Error Messages**:
   - If valid after transformation: Pass
   - If invalid after transformation: Show "Invalid value 'X' (transformed from 'Y')"
   - If no mapping exists: Show "Invalid value 'X'. No mapping defined. Expected: ..."

### Example
**Original Data:**
```
Row 5: Status_CSV = "Act"
```

**With Mapping:**
```
"Act" → "Active" ✅ VALID
```

**Error Messages:**
- Before mapping: `Invalid picklist value 'Act'. Expected: Active, Inactive, Pending`
- After mapping: Value passes validation
- Bad mapping: `Invalid picklist value 'Act' (transformed from 'Wrong'). Expected: Active, Inactive, Pending`

## Best Practices

### 1. Create Mappings Before Validation
- Set up picklist mappings for your data sources first
- This ensures validation uses correct transformations

### 2. Use Sample Files
- Upload representative sample files with all possible values
- Ensures all variations are mapped

### 3. Regular Updates
- Review mappings when Salesforce picklist values change
- Update mappings when new source values appear

### 4. Documentation
- Download mappings as CSV for documentation
- Share with team members
- Keep backup copies

### 5. Testing
- Test validation with sample data after creating mappings
- Verify transformations work correctly

## Functions Reference

### Utility Functions (utils.py)

**Storage Functions:**
- `save_picklist_mappings(org_name, object_name, mappings)` - Save mappings to file
- `load_picklist_mappings(org_name, object_name, field_name)` - Load mappings for specific field
- `get_all_picklist_mappings(org_name, object_name)` - Load all mappings for object
- `update_picklist_mapping(org_name, object_name, field_name, csv_column, field_mappings)` - Update specific field
- `delete_picklist_mappings(org_name, object_name, field_name)` - Delete mappings

**Transformation Functions:**
- `transform_picklist_value(org_name, object_name, field_name, source_value)` - Transform single value
- `extract_picklist_values_from_file(df, org_name, object_name, sf_conn, field_mappings)` - Analyze file

### Validation Functions (validation_operations.py)

**Enhanced Validation:**
- `validate_picklist_value(field_name, value, field_info, org_name, object_name)` - Validate with transformation
- `validate_comprehensive_row(..., org_name, object_name)` - Row validation with mappings
- `run_schema_validation(..., org_name)` - Main validation with mapping support

## Troubleshooting

### Issue: Mappings Not Found
**Cause:** Mappings not created for org/object
**Solution:** Go to Configuration → Picklist Mappings → Create New Mappings

### Issue: Values Still Show as Invalid
**Cause 1:** Mapping not saved properly
**Solution:** Re-create and save mappings

**Cause 2:** Target value not in active Salesforce values
**Solution:** Check Salesforce picklist values, map to active values only

**Cause 3:** Case sensitivity
**Solution:** Ensure exact match (mappings are case-sensitive)

### Issue: Cannot See Picklist Fields
**Cause:** No picklist fields in selected object or data columns don't match
**Solution:** 
- Verify object has picklist fields
- Use field mappings to map CSV columns to Salesforce fields
- Check that CSV columns exist in uploaded file

## Future Enhancements (Potential)

1. **Auto-suggestion**: AI-based mapping suggestions based on similarity
2. **Bulk Import**: Import mappings from CSV/Excel
3. **Validation Rules**: Add custom transformation rules
4. **History Tracking**: Track changes to mappings over time
5. **Global Mappings**: Share mappings across objects
6. **Multi-select Support**: Better handling of multi-select picklist fields
7. **Record Type Support**: Different mappings for different record types

## Questions & Support

For questions about the picklist mapping feature:
1. Check this documentation
2. Review sample mapping files in `picklist_mappings/` directory
3. Test with sample data in Configuration → Picklist Mappings
4. Contact development team

## Version History

- **v1.0** (2025-11-26): Initial implementation
  - Create, view, edit, delete mappings
  - Integration with schema validation
  - Automatic value transformation
  - Enhanced error messages
