# Operation Tracking System - Complete Guide

## Overview
The Operation Tracking System provides comprehensive audit trail capabilities across all DM Toolkit operations. Every action is automatically recorded with timestamps, success/failure status, and detailed metadata.

## Supported Operation Types

### 1. **SOQL_Query** ✅
Tracks SOQL queries executed from Salesforce orgs.

```python
from ui_components.data_hub.operation_tracker import track_soql_query

df, operation_id = track_soql_query(
    sf_connection=conn,
    query="SELECT Id, Name FROM Account",
    source_org="HeraQA",
    object_name="Account",
    validation_status="PASSED",
    validation_passed=100,
    validation_failed=0
)
```

**Operation Record Contains:**
- Organization (source_org)
- SOQL query executed
- Record count
- Timestamp
- User who executed

---

### 2. **File_Upload** ✅
Tracks file uploads to the Data Hub.

```python
from ui_components.data_hub.operation_tracker import track_file_upload

df, operation_id = track_file_upload(
    uploaded_file=uploaded_file,
    source_org="HeraQA",
    target_org="TestDev",
    object_name="Account",
    validation_status="PARTIAL",
    validation_passed=95,
    validation_failed=5
)
```

**Operation Record Contains:**
- File name and size
- Source/Target org
- Object name
- Validation result
- Record count

---

### 3. **Data_Load** ✅
Tracks data load operations to target Salesforce orgs.

```python
from ui_components.data_hub.operation_tracker import track_data_load

operation_id = track_data_load(
    data=df,
    target_org="TestDev",
    object_name="Account",
    successful_records=95,
    failed_records=5,
    load_method="API"
)
```

**Operation Record Contains:**
- Target org
- Object loaded to
- Success/failure counts
- Load method (API, Bulk API, Data Loader)
- Batch information

---

### 4. **Validation_Check_Business_Rules** 🆕
Tracks Business Rules validation operations.

```python
from ui_components.data_hub.operation_tracker import track_validation_check

operation_id = track_validation_check(
    data=df,
    object_name="Account",
    source_org="HeraQA",
    validation_type="Business_Rules",
    total_records=100,
    passed_records=95,
    failed_records=5,
    validation_details={
        "rules_checked": ["Required fields", "Format validation"],
        "rule_version": "v1.2"
    }
)
```

**Operation Record Contains:**
- Business rules applied
- Pass/fail breakdown
- Validation errors (if any)
- Rule version

---

### 5. **Validation_Check_Data_Quality** 🆕
Tracks Data Quality check operations.

```python
from ui_components.data_hub.operation_tracker import track_validation_check

operation_id = track_validation_check(
    data=df,
    object_name="Account",
    source_org="HeraQA",
    validation_type="Data_Quality",
    total_records=100,
    passed_records=92,
    failed_records=8,
    validation_details={
        "duplicates_found": 3,
        "null_values": 5,
        "format_issues": 0
    }
)
```

**Operation Record Contains:**
- Data quality metrics
- Duplicate count
- Null/empty field count
- Format validation result

---

### 6. **Validation_Check_Schema** 🆕
Tracks Schema validation operations.

```python
from ui_components.data_hub.operation_tracker import track_validation_check(
    data=df,
    object_name="Account",
    source_org="HeraQA",
    validation_type="Schema",
    total_records=100,
    passed_records=100,
    failed_records=0,
    validation_details={
        "fields_validated": ["Id", "Name", "Industry"],
        "schema_version": "Salesforce_Schema_v10"
    }
)
```

**Operation Record Contains:**
- Schema version validated against
- Fields checked
- Schema mismatches
- Type conversion issues

---

### 7. **Migration_Execute** 🆕
Tracks data migration operations between orgs.

```python
from ui_components.data_hub.operation_tracker import track_migration_execution(
    source_org="HeraQA",
    target_org="TestDev",
    object_name="Account",
    total_records=150,
    successful_records=148,
    failed_records=2,
    migration_details={
        "match_strategy": "External_Id",
        "field_mappings": {"SourceField": "TargetField"},
        "transformation_rules_applied": ["Lookup_Resolution", "Format_Conversion"]
    },
    data=df
)
```

**Operation Record Contains:**
- Source and Target orgs
- Migration success rate
- Match strategy used
- Field mappings
- Transformation rules applied

---

### 8. **Lookup_Resolution** 🆕
Tracks lookup resolution during data integration.

```python
from ui_components.data_hub.operation_tracker import track_lookup_resolution(
    source_org="HeraQA",
    target_org="TestDev",
    object_name="Account",
    total_lookups=100,
    resolved_lookups=98,
    unresolved_lookups=2,
    lookup_details={
        "lookup_fields": ["ParentAccount", "Owner"],
        "resolution_strategy": "ExternalId_Matching",
        "fallback_strategy": "Null_If_Not_Found"
    },
    data=df
)
```

**Operation Record Contains:**
- Lookup fields resolved
- Resolution success rate
- Resolution strategy
- Unresolved references
- Fallback action taken

---

## Integration Points

### Business Rules Tab
When users run business rule validations, automatically call:
```python
track_validation_check(..., validation_type="Business_Rules")
```

### Data Quality Tab
When users run data quality checks, automatically call:
```python
track_validation_check(..., validation_type="Data_Quality")
```

### Data Migration / Org Migration Tab
When users execute migrations, automatically call:
```python
track_migration_execution(...)
```

### Lookup Resolution Tab
When users resolve lookups, automatically call:
```python
track_lookup_resolution(...)
```

---

## Operation History UI

Access all tracked operations in **Data Hub → Tab 4: Operation History**

### Features
- **Statistics Dashboard**: Total operations, success rate, failed operations
- **Cascading Filters**: Filter by Organization → Object → Operation Type → Status
- **Operation Table**: View all operation metadata
- **Details View**: Expand any operation to see full data and validation details
- **Export**: Download operation history as CSV
- **Delete**: Remove individual operations or bulk delete

### View Details
Click any operation in the table to:
- View operation metadata (timestamp, user, org, object)
- See operation data (the DataFrame)
- Review validation results
- Check source/target information

---

## Session State Management

The Operation History tab uses Streamlit session state to:
- **Persist filter selections** across page refreshes
- **Auto-reset object filter** when organization changes
- **Track last selected values** for context preservation
- **Cache operation queries** for performance

### Debug Mode
An "ℹ️ Debug Info" expander shows:
- Currently selected filters
- Total matching operations
- Operation count by type

---

## Data Persistence

All operations are stored in:
```
DataFiles/
  operation_history/
    manifest.json        # Operation metadata
    data/
      {operation_id}.csv # Operation data
      {operation_id}_details.json # Additional details
```

**Key Properties in Manifest:**
```json
{
  "operation_id": "op_123456",
  "operation_type": "Validation_Check_Business_Rules",
  "object_name": "Account",
  "source_org": "HeraQA",
  "target_org": "TestDev",
  "record_count": 100,
  "validation_status": "PASSED",
  "validation_passed": 95,
  "validation_failed": 5,
  "timestamp": "2025-01-15T10:30:00Z",
  "created_by": "john.doe@example.com",
  "notes": "Additional details..."
}
```

---

## Best Practices

### 1. Always Provide Context
```python
# ✅ GOOD - Clear context
track_validation_check(
    data=df,
    object_name="Account",
    source_org="HeraQA",
    validation_type="Data_Quality",
    total_records=100,
    passed_records=98,
    failed_records=2,
    validation_details={"duplicates": 2}
)

# ❌ BAD - Missing context
track_validation_check(
    data=df,
    object_name="Unknown",
    source_org=None,
    validation_type="Data_Quality",
    total_records=100,
    passed_records=98,
    failed_records=2
)
```

### 2. Use Validation Details for Additional Context
```python
# Include any custom validation info
validation_details = {
    "rule_version": "1.2",
    "rules_applied": ["Required_Fields", "Format_Validation"],
    "warnings": ["5 records had partial matches"]
}
```

### 3. Track Both Success and Failure
Even failed operations should be tracked:
```python
track_validation_check(
    data=df,
    object_name="Account",
    source_org="HeraQA",
    validation_type="Business_Rules",
    total_records=100,
    passed_records=0,      # None passed
    failed_records=100,    # All failed
    validation_details={"error": "Database connection failed"}
)
```

### 4. Include Complete Metadata
For migrations, include mapping details:
```python
track_migration_execution(
    source_org="HeraQA",
    target_org="TestDev",
    object_name="Account",
    total_records=150,
    successful_records=148,
    failed_records=2,
    migration_details={
        "match_strategy": "External_Id",
        "field_mappings": {
            "SourceField1": "TargetField1",
            "SourceField2": "TargetField2"
        },
        "transformation_rules": ["Lookup_Resolution"]
    }
)
```

---

## Future Enhancements

- [ ] Database backend for scalability (> 10,000 operations)
- [ ] Analytics dashboard (operation trends, performance metrics)
- [ ] Audit reports with compliance certification
- [ ] Real-time operation monitoring
- [ ] Automated alerts for failures
- [ ] Integration with external logging (CloudWatch, Datadog)

---

## Support

For issues or questions about operation tracking:
1. Check the Operation History UI for operation details
2. Review the manifest.json file in `DataFiles/operation_history/`
3. Check application logs in `DataLoader_Logs/`

