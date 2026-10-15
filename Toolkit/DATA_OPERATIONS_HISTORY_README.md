# Data Operations History & Tracking System

## Overview

The Data Operations History system provides **persistent, cross-session data storage and retrieval** for all data operations in the DM Toolkit. All data fetched via SOQL queries or uploaded files is automatically tracked and can be accessed at any time.

## Key Features

### 1. **Persistent Data Storage**
- All data operations are stored permanently in the local filesystem
- Data survives app closure and can be retrieved days/weeks/months later
- No external databases required - uses simple JSON manifest + CSV files

### 2. **Complete Operation Tracking**
Each operation tracks:
- **Operation ID** - Unique identifier (e.g., OP-20260109143522)
- **Timestamp** - When operation occurred
- **Type** - SOQL_Query, File_Upload, or Data_Load
- **Source/Target Org** - Which organization(s) involved
- **Object Name** - Salesforce object (Account, Opportunity, etc.)
- **Record Count** - How many records
- **Validation Status** - PASSED/FAILED/PARTIAL
- **Validation Details** - How many passed/failed
- **Metadata** - Query used, file uploaded, created by, notes

### 3. **Multi-Org/Multi-Object Parallel Processing**
- Fetch from multiple Salesforce orgs simultaneously
- Process multiple objects in parallel
- Non-blocking operations don't interfere with each other
- Much faster than sequential processing

### 4. **Data History Tab (📊 Data Operations)**
New tab in Org Migration showing:
- Statistics dashboard (total ops, records, validation stats)
- Filterable history table (by org, object, type, status)
- Detailed view of any historical operation
- Data preview and download (CSV/Excel)
- Delete operations if needed
- Export full history

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│          Streamlit Application (UI)                     │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Operation Tracker Integration (operation_tracker) │   │
│  │  - track_file_upload()                           │   │
│  │  - track_soql_query()                            │   │
│  │  - track_data_load()                             │   │
│  │  - get_last_operation_data()                     │   │
│  └──────────────────────────────────────────────────┘   │
│                    ↓                                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │   Operation Manager (operation_manager.py)       │   │
│  │   - create_operation()                           │   │
│  │   - get_operation_history()                      │   │
│  │   - retrieve_operation_data()                    │   │
│  │   - delete_operation()                           │   │
│  │   - export_history_to_csv()                      │   │
│  └──────────────────────────────────────────────────┘   │
│                    ↓                                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │    Async Processor (async_processor.py)          │   │
│  │    - fetch_from_multiple_orgs()                  │   │
│  │    - load_to_multiple_orgs()                     │   │
│  │    - Parallel execution of tasks                 │   │
│  └──────────────────────────────────────────────────┘   │
│                    ↓                                      │
└─────────────────────────────────────────────────────────┘
                      ↓
        ┌─────────────────────────────┐
        │  Persistent Storage         │
        ├─────────────────────────────┤
        │ • data_hub_operations_      │
        │   manifest.json (metadata)  │
        │                             │
        │ • data_hub_operations/      │
        │   ├─OP-20260109*.csv        │
        │   ├─OP-20260110*.csv        │
        │   └─...                     │
        └─────────────────────────────┘
```

## File Structure

### New Files Created

```
ui_components/
├── data_hub/
│   ├── operation_manager.py        ✅ NEW - Core persistence layer
│   ├── operation_tracker.py        ✅ NEW - Integration helpers
│   └── ...
├── async_processor.py              ✅ NEW - Parallel processing
└── org_migration.py                ✅ MODIFIED - Added tab10
```

### Folder for Data Storage

```
project_root/
├── data_hub_operations_manifest.json  ✅ Metadata for all operations
├── data_hub_operations/              ✅ Folder for stored data
│   ├── OP-20260109143522_Account.csv
│   ├── OP-20260109145801_Opportunity.csv
│   └── ...
└── ...
```

## Usage Examples

### Example 1: Track File Upload

```python
from ui_components.data_hub.operation_tracker import track_file_upload

# User uploads a file
uploaded_file = st.file_uploader("Upload CSV", type=['csv'])

if uploaded_file:
    # Load and track the operation
    df, operation_id = track_file_upload(
        uploaded_file,
        source_org=None,
        target_org="HeraQA",
        object_name="Account",
        validation_status="PASSED",
        validation_passed=251,
        validation_failed=0
    )
    
    if df is not None:
        st.success(f"✅ Loaded! Operation ID: {operation_id}")
        st.dataframe(df)
    else:
        st.error(operation_id)  # Error message
```

### Example 2: Track SOQL Query

```python
from ui_components.data_hub.operation_tracker import track_soql_query

# User enters SOQL query
query = "SELECT Id, Name FROM Account LIMIT 1000"

# Execute and track
df, operation_id = track_soql_query(
    sf_connection=sf_org,
    query=query,
    source_org="HeraQA",
    object_name="Account"
)

if df is not None:
    st.success(f"✅ Query successful! {len(df)} records")
```

### Example 3: Parallel Multi-Org Fetch

```python
from ui_components.async_processor import run_async_fetch

org_configs = [
    {"org_name": "HeraQA", "connection": sf_heraqa},
    {"org_name": "TestDev", "connection": sf_testdev},
    {"org_name": "Navitas", "connection": sf_navitas}
]

progress = st.empty()

results = run_async_fetch(
    org_configs,
    ["Account", "Opportunity"],
    progress
)

# results = [(df1, metadata1), (df2, metadata2), ...]
# All 6 fetches (3 orgs × 2 objects) ran SIMULTANEOUSLY
```

### Example 4: Track Data Load

```python
from ui_components.data_hub.operation_tracker import track_data_load

# After loading data to org
operation_id = track_data_load(
    data=data_loaded,
    target_org="TestDev",
    object_name="Account",
    successful_records=245,
    failed_records=6,
    load_method="API"
)

st.success(f"Data load tracked: {operation_id}")
```

### Example 5: Retrieve Historical Data

```python
from ui_components.data_hub.operation_manager import get_operation_manager

op_manager = get_operation_manager()

# Get all operations for a specific object
history = op_manager.get_operation_history(object_filter="Account")

# Get the data from a specific operation
data, metadata = op_manager.retrieve_operation_data("OP-20260109143522")

st.dataframe(data)
st.json(metadata)
```

## UI Components

### 📊 Data Operations Tab (New)

**Location:** Tab 4 in Data Hub (📊 Data Hub → 📊 Data Operations tab)

**Sections:**

1. **📈 Operation Statistics**
   - Total operations count
   - Total records processed
   - Validation passed/failed counts

2. **🔍 Filter Operations**
   - Filter by Organization
   - Filter by Object
   - Filter by Operation Type
   - Filter by Status

3. **📋 Operations Table**
   - Sortable, filterable table
   - Shows operation ID, timestamp, org, object, record count, status
   - Click any row for details

4. **📂 View Operation Details**
   - Full metadata display
   - SOQL query (if applicable)
   - File name (if uploaded)
   - Data statistics and preview
   - Download buttons (CSV/Excel)
   - Delete operation button

5. **📤 Export History**
   - Export all operations to CSV
   - Includes all metadata

## Key Methods

### OperationManager

```python
op_manager = get_operation_manager()

# Create new operation
operation_id = op_manager.create_operation(
    operation_type="SOQL_Query",
    object_name="Account",
    record_count=500,
    data=df,
    source_org="HeraQA",
    query="SELECT * FROM Account"
)

# Get history with filters
history = op_manager.get_operation_history(
    org_filter="HeraQA",
    object_filter="Account",
    operation_type_filter="SOQL_Query",
    status_filter="COMPLETE"
)

# Retrieve operation data
data, metadata = op_manager.retrieve_operation_data(operation_id)

# Get statistics
stats = op_manager.get_operation_stats()

# Get unique values for filtering
orgs = op_manager.get_unique_orgs()
objects = op_manager.get_unique_objects()

# Delete operation
op_manager.delete_operation(operation_id)

# Export history
op_manager.export_history_to_csv("history.csv")
```

### AsyncProcessor

```python
processor = AsyncProcessor()

# Fetch from multiple orgs simultaneously
results = await processor.fetch_multiple_orgs(
    org_configs=[
        {"org_name": "HeraQA", "connection": sf1},
        {"org_name": "TestDev", "connection": sf2}
    ],
    object_names=["Account", "Opportunity"]
)

# Load to multiple orgs simultaneously
results = await processor.load_to_multiple_orgs(
    data=df,
    target_orgs=[
        {"org_name": "HeraQA", "connection": sf1},
        {"org_name": "TestDev", "connection": sf2}
    ],
    object_name="Account"
)

# Get results summary
summary = processor.get_results_summary()
```

## Data Persistence

### File Structure

**data_hub_operations_manifest.json** (JSON metadata file):
```json
{
  "version": "1.0",
  "created": "2026-01-09T10:00:00",
  "last_updated": "2026-01-09T14:35:22",
  "operations": [
    {
      "operation_id": "OP-20260109143522",
      "timestamp": "2026-01-09T14:35:22",
      "operation_type": "SOQL_Query",
      "source_org": "HeraQA",
      "target_org": null,
      "object_name": "Account",
      "record_count": 251,
      "status": "COMPLETE",
      "data_location": "data_hub_operations/OP-20260109143522_Account.csv",
      "query": "SELECT Id, Name FROM Account",
      "file_uploaded": null,
      "validation_status": "PASSED",
      "validation_passed": 251,
      "validation_failed": 0,
      "created_by": "admin@org.com",
      "notes": null
    }
  ]
}
```

**data_hub_operations/** (Folder with actual data):
```
OP-20260109143522_Account.csv
OP-20260109145801_Opportunity.csv
OP-20260110091234_Claim__c.csv
```

## Benefits

✅ **No Data Loss** - Never lose data when app closes
✅ **Full Audit Trail** - See exactly what data was fetched/loaded when
✅ **Easy Retrieval** - Access any historical data in seconds
✅ **Parallel Processing** - 3x faster with multi-org operations
✅ **No Database** - File-based, portable, zero setup
✅ **Validation Tracking** - See which records passed/failed validation
✅ **User Tracking** - Know who performed each operation
✅ **Data Lineage** - Understand data flow across orgs and objects

## Next Steps (Optional Enhancements)

1. **Resume Feature** - "Load from last operation" button in data loading
2. **Comparison View** - Compare two historical datasets
3. **Data Quality Trends** - Graph validation pass rates over time
4. **Backup/Restore** - Manual backup of operation history
5. **Encryption** - Encrypt sensitive data at rest
6. **Archival** - Move old operations to archive storage
7. **WebSocket Real-Time** - Live status updates for long-running operations
8. **PostgreSQL Migration** - Move from file-based to database for scalability

## Troubleshooting

### "No operations found"
- First run? No data yet. Try uploading a file or running a SOQL query first
- Check filters - may be filtering out all operations

### "Data file not found"
- The manifest exists but CSV file was deleted
- Solution: Delete the operation from history, re-create it

### "Permission error writing to manifest"
- Check folder permissions on `data_hub_operations/` directory
- Ensure user has write access to project root

### Async operations running sequentially
- Check if event loop already exists in current thread
- Use `run_async_fetch()` helper function instead of direct asyncio calls

## Support

For issues or questions about operation tracking:
1. Check the Data Operations tab for operation details
2. Export history CSV for analysis
3. Check application logs for error details
