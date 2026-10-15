# Operation Tracking System - README

## Quick Start

The Operation Tracking System automatically records every operation performed in the DM Toolkit, providing a complete audit trail accessible from the Data Hub.

### View Operation History
1. Open the DM Toolkit
2. Navigate to **Data Hub** → **Tab 4: 📊 Operation History**
3. See all operations with details, filters, and export options

---

## What Gets Tracked?

### ✅ Currently Tracked
- **File Uploads** - When you upload data files
- **SOQL Queries** - When you query Salesforce orgs
- **Data Loads** - When you load data to Salesforce

### 🆕 Ready to Track (When Integrated)
- **Business Rules Validations** - When you validate business rules
- **Data Quality Checks** - When you run quality checks
- **Schema Validations** - When you validate data schema
- **Org-to-Org Migrations** - When you migrate data between orgs
- **Lookup Resolutions** - When you resolve lookup fields

---

## Operation History UI Features

### 📊 Statistics Dashboard
View at a glance:
- Total operations performed
- Success rate (%)
- Number of failed operations
- Date range statistics

### 🔍 Advanced Filtering
Filter operations by:
- **Organization** - Select which org(s) to see
- **Object** - Auto-filters based on selected org
- **Operation Type** - All 8 operation types
- **Status** - PASSED, FAILED, or PARTIAL
- **Date Range** - From/to dates

### 📋 Operations Table
See all operations with:
- Operation ID
- Type
- Organization(s)
- Object name
- Status
- Timestamp
- Created by (user)

### 📥 Download & Export
- Click any operation to view full details
- Download operation data as CSV
- Export entire history as CSV
- Delete individual or multiple operations

### ℹ️ Debug Info
View filter status:
- Current selections
- Total matching operations
- Operation count by type

---

## For Developers: Integration Guide

### Using track_file_upload()
```python
from ui_components.data_hub.operation_tracker import track_file_upload

# In your file upload code
df, operation_id = track_file_upload(
    uploaded_file=st.file_uploader("Upload"),
    source_org="HeraQA",
    target_org="TestDev",
    object_name="Account"
)

# Operation automatically recorded!
```

### Using track_soql_query()
```python
from ui_components.data_hub.operation_tracker import track_soql_query

# In your SOQL query code
df, operation_id = track_soql_query(
    sf_connection=connection,
    query="SELECT Id, Name FROM Account",
    source_org="HeraQA",
    object_name="Account"
)

# Operation automatically recorded!
```

### Using track_data_load()
```python
from ui_components.data_hub.operation_tracker import track_data_load

# In your data load code
operation_id = track_data_load(
    data=df,
    target_org="TestDev",
    object_name="Account",
    successful_records=95,
    failed_records=5,
    load_method="API"
)

# Operation automatically recorded!
```

### Using track_validation_check() [NEW]
```python
from ui_components.data_hub.operation_tracker import track_validation_check

# In Business Rules tab validation code
operation_id = track_validation_check(
    data=df,
    object_name="Account",
    source_org="HeraQA",
    validation_type="Business_Rules",  # or "Data_Quality", "Schema"
    total_records=100,
    passed_records=95,
    failed_records=5,
    validation_details={"rules": ["Required", "Format"]}
)

# Operation automatically recorded!
```

### Using track_migration_execution() [NEW]
```python
from ui_components.data_hub.operation_tracker import track_migration_execution

# In Org Migration Execute tab
operation_id = track_migration_execution(
    source_org="HeraQA",
    target_org="TestDev",
    object_name="Account",
    total_records=150,
    successful_records=148,
    failed_records=2,
    migration_details={"match_strategy": "External_Id"}
)

# Operation automatically recorded!
```

### Using track_lookup_resolution() [NEW]
```python
from ui_components.data_hub.operation_tracker import track_lookup_resolution

# In Lookup Resolution tab
operation_id = track_lookup_resolution(
    source_org="HeraQA",
    target_org="TestDev",
    object_name="Account",
    total_lookups=100,
    resolved_lookups=98,
    unresolved_lookups=2,
    lookup_details={"fields": ["ParentAccount"]}
)

# Operation automatically recorded!
```

---

## Data Storage

Operations are stored in:
```
DataFiles/
  operation_history/
    manifest.json              # All operation metadata
    data/
      op_001.csv              # Operation data
      op_002.csv
      ...
```

**Format:**
- `manifest.json`: Lightweight metadata (fast queries, small file)
- `*.csv`: Full operation data (for detailed analysis, downloadable)

**Each operation record contains:**
- operation_id: Unique identifier
- operation_type: File_Upload, SOQL_Query, Data_Load, etc.
- object_name: Salesforce object
- source_org: Source organization (if applicable)
- target_org: Target organization (if applicable)
- record_count: Total records in operation
- validation_status: PASSED, FAILED, PARTIAL
- validation_passed: Number that passed
- validation_failed: Number that failed
- timestamp: ISO 8601 format
- created_by: User who performed operation
- notes: Additional details
- file_name: Original filename (for uploads)
- query: SOQL query (for queries)
- ... and more

---

## Session State & Performance

### Session State (Streamlit)
The UI uses session state to:
- ✅ Persist filter selections across refreshes
- ✅ Auto-reset object filter when org changes
- ✅ Track last selected org
- ✅ Cache operation queries

### Performance
- Fast JSON queries for filtering
- CSV for large data exports
- Scalable to 10,000+ operations
- Future: Database backend for even larger scale

---

## Common Tasks

### Task: Find all Account validations
1. Open Operation History
2. Select Organization: "HeraQA"
3. Select Object: "Account"
4. Select Operation Type: "Validation_Check_Business_Rules"
5. See all Account validations with details

### Task: Check migration success rate
1. Open Operation History
2. Select Operation Type: "Migration_Execute"
3. See dashboard showing:
   - Total migrations
   - Success rate %
   - Failed count
4. Click any migration to see details

### Task: Export validation history
1. Open Operation History
2. Filter by Operation Type: "Validation_Check_Data_Quality"
3. Click "📄 Export History to CSV"
4. Opens CSV with all quality check results

### Task: Resume from previous operation
```python
from ui_components.data_hub.operation_tracker import get_last_operation_data

# Get the data from your last operation
df = get_last_operation_data(object_name="Account")

if df is not None:
    st.write(f"Resuming from previous operation with {len(df)} records")
else:
    st.write("No previous operations found")
```

---

## Troubleshooting

### Q: Where is my operation?
**A:** Check the filters in the Operation History tab. Make sure:
- Organization matches where operation occurred
- Date range includes operation date
- Operation Type is selected
- Status filter isn't excluding your operation

### Q: Why can't I see operations from a certain org?
**A:** Use the Organization dropdown to select it. The UI automatically filters:
1. First dropdown = Available orgs (those with operations)
2. Second dropdown = Objects in selected org

### Q: How do I delete an operation?
**A:** 
1. Find operation in table
2. Click the delete button (trash icon)
3. Confirm deletion
4. Or use "Delete Selected" for bulk delete

### Q: How large can the operation history get?
**A:** 
- Current: File-based, scalable to ~10,000 operations
- Future: Database backend for unlimited scale
- Estimate: Each operation ~10-100 KB depending on data size

### Q: Can I export the entire history?
**A:** Yes! Click "📄 Export History to CSV" to download all visible operations based on current filters.

---

## Best Practices

### When Tracking Operations

✅ **DO:**
- Always include object_name
- Always include source/target org
- Provide accurate pass/fail counts
- Use validation_details for context
- Include operation-specific metadata

❌ **DON'T:**
- Leave org as None (use "Unknown" if necessary)
- Forget to pass the DataFrame
- Set both passed and failed to 0
- Skip validation_details for complex operations

### For Integration

✅ **DO:**
- Call track_*() function right after operation completes
- Catch and log exceptions
- Verify operation_id returned
- Test with sample data first

❌ **DON'T:**
- Call multiple times for same operation
- Forget to pass all required parameters
- Ignore error messages
- Leave operations untracked

---

## Files Changed

### New Functions Added
- `track_validation_check()` - For validation operations
- `track_migration_execution()` - For migration operations
- `track_lookup_resolution()` - For lookup operations

### Files Modified
- `operation_tracker.py` - Added 3 new functions (~180 lines)
- `data_hub_ui.py` - Tab 4 displays all operations

### Documentation
- `OPERATION_TRACKING_GUIDE.md` - Complete API reference
- `OPERATION_TRACKER_EXPANSION.md` - Summary of new functions
- `IMPLEMENTATION_COMPLETE.md` - Full system overview
- This file - User-friendly README

---

## Support

For detailed information, see:
- **API Reference:** `OPERATION_TRACKING_GUIDE.md`
- **What's New:** `OPERATION_TRACKER_EXPANSION.md`
- **System Overview:** `IMPLEMENTATION_COMPLETE.md`

All files are in `ui_components/data_hub/`

---

## Version History

### v1.0 - Complete Implementation
- ✅ Core infrastructure (operation_manager, operation_tracker, async_processor)
- ✅ Operation History UI with cascading filters
- ✅ Support for 8 operation types
- ✅ Export/download capabilities
- ✅ Session state management
- ✅ Full documentation

**Status:** Production Ready

Next: Integrate into Business Rules, Data Quality, Org Migration, and Lookup Resolution tabs.

