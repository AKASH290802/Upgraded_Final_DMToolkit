# Data Operations History - Reference Card

## Quick Reference

### 📊 Data Operations Tab Features

| Feature | Location | What It Does |
|---------|----------|--------------|
| **Statistics** | Data Hub → Operations Tab | Shows total ops, records, validation stats |
| **Filters** | Data Hub → Operations Tab | Filter by org, object, type, status |
| **Operations Table** | Data Hub → Operations Tab | List all matching operations |
| **View Details** | Data Hub → Operations Tab | Click to see full data and metadata |
| **Download** | Data Hub → Operations Tab | Get data as CSV or Excel |
| **Delete** | Data Hub → Operations Tab | Remove operation from history |
| **Export** | Data Hub → Operations Tab | Export all ops to CSV file |

### 🔧 Core APIs

```python
# Import the manager
from ui_components.data_hub.operation_manager import get_operation_manager
om = get_operation_manager()

# Create operation
operation_id = om.create_operation(
    operation_type="SOQL_Query",        # or "File_Upload" or "Data_Load"
    object_name="Account",
    record_count=500,
    data=df,
    source_org="HeraQA",
    query="SELECT * FROM Account"
)

# Get history (with filters)
history = om.get_operation_history(
    org_filter="HeraQA",               # Optional
    object_filter="Account",            # Optional
    operation_type_filter="SOQL_Query", # Optional
    status_filter="COMPLETE"            # Optional
)

# Retrieve data
data, metadata = om.retrieve_operation_data(operation_id)

# Get stats
stats = om.get_operation_stats()
# Returns: {total_operations, operations_by_type, total_records, passed, failed}

# Get unique values (for UI)
orgs = om.get_unique_orgs()           # ["HeraQA", "TestDev", "Navitas"]
objects = om.get_unique_objects()     # ["Account", "Opportunity", "Claim__c"]

# Delete operation
om.delete_operation(operation_id)

# Export to CSV
om.export_history_to_csv("history.csv")
```

### 🚀 Tracker Integration APIs

```python
from ui_components.data_hub.operation_tracker import (
    track_file_upload,
    track_soql_query,
    track_data_load,
    get_last_operation_data,
    display_operation_summary
)

# Track file upload
df, operation_id = track_file_upload(
    uploaded_file,
    source_org=None,
    target_org="HeraQA",
    object_name="Account",
    validation_status="PASSED",
    validation_passed=251,
    validation_failed=0
)

# Track SOQL query
df, operation_id = track_soql_query(
    sf_connection,
    "SELECT Id, Name FROM Account",
    source_org="HeraQA",
    object_name="Account"
)

# Track data load
operation_id = track_data_load(
    data=df,
    target_org="TestDev",
    object_name="Account",
    successful_records=245,
    failed_records=6,
    load_method="API"
)

# Resume from last operation
last_data = get_last_operation_data("Account")  # Gets last Account operation

# Display in UI
display_operation_summary(operation_id)
```

### ⚡ Async Processing APIs

```python
from ui_components.async_processor import run_async_fetch, run_async_load

# Parallel fetch from multiple orgs
org_configs = [
    {"org_name": "HeraQA", "connection": sf1},
    {"org_name": "TestDev", "connection": sf2},
    {"org_name": "Navitas", "connection": sf3}
]

progress = st.empty()  # For progress display

results = run_async_fetch(
    org_configs,
    ["Account", "Opportunity"],  # Objects to fetch
    progress
)

# Results: [(df1, metadata1), (df2, metadata2), ...]
# All 6 fetches (3 orgs × 2 objects) happen SIMULTANEOUSLY!

# Parallel load to multiple orgs
results = run_async_load(
    data=df,
    target_orgs=org_configs,
    object_name="Account",
    progress_placeholder=st.empty()
)
```

## Data Flow Diagrams

### Flow 1: File Upload → Track → Use Later

```
User uploads CSV
       ↓
track_file_upload()
       ↓
Stored in: data_hub_operations_manifest.json
           + data_hub_operations/OP-*.csv
       ↓
Next day: User opens app
       ↓
Go to 📊 Data Operations tab
       ↓
Click operation
       ↓
Download CSV (same file)
```

### Flow 2: Multi-Org Parallel Fetch

```
Org 1 (HeraQA)   ─┐
Org 2 (TestDev)  ─┼─ run_async_fetch() ─┬─ All 6 happen
Org 3 (Navitas)  ─┤                     │  SIMULTANEOUSLY!
Object: Account  ─┤                     │  (3x faster)
Object: Opp      ─┘                     │
                                        ↓
                            Results: [(df1, meta1),
                                     (df2, meta2),
                                     (df3, meta3),
                                     (df4, meta4),
                                     (df5, meta5),
                                     (df6, meta6)]
```

### Flow 3: Load → Track → View

```
Prepare data (df)
       ↓
track_data_load(df, "TestDev", "Account", success=245, failed=6)
       ↓
Stored in manifest with metadata:
  - How many succeeded
  - How many failed
  - When loaded
  - To which org
       ↓
Later: View in 📊 Data Operations
       ↓
See validation stats immediately
```

## File Structure

```
project_root/
│
├── data_hub_operations_manifest.json    ← JSON metadata
│   {
│     "version": "1.0",
│     "operations": [
│       {
│         "operation_id": "OP-20260109143522",
│         "timestamp": "2026-01-09T14:35:22",
│         "operation_type": "SOQL_Query",
│         "source_org": "HeraQA",
│         "object_name": "Account",
│         "record_count": 251,
│         "data_location": "data_hub_operations/OP-*.csv",
│         "validation_status": "PASSED",
│         "created_by": "admin@org.com"
│       },
│       ...
│     ]
│   }
│
├── data_hub_operations/                 ← Actual data folder
│   ├── OP-20260109143522_Account.csv     (251 records)
│   ├── OP-20260109145801_Opportunity.csv (1024 records)
│   ├── OP-20260110091234_Claim__c.csv    (500 records)
│   └── ...
│
└── ui_components/
    ├── data_hub/
    │   ├── operation_manager.py         ✅ Core persistence
    │   ├── operation_tracker.py         ✅ Integration helpers
    │   └── ...
    ├── async_processor.py               ✅ Parallel processing
    ├── org_migration.py                 ✅ + Tab 10 UI
    └── ...
```

## Common Tasks

### Task 1: Upload File and See History

```
1. Go to any data tab
2. Upload CSV/Excel/PSV file
3. Operation auto-saved ✅
4. Go to 📊 Data Operations tab
5. Find your operation in list
6. Click to view details
```

### Task 2: Fetch from Multiple Orgs (Fast)

```python
# Use async function for 3x speed boost
org_configs = [
    {"org_name": "HeraQA", "connection": sf_heraqa},
    {"org_name": "TestDev", "connection": sf_testdev},
    {"org_name": "Navitas", "connection": sf_navitas}
]

results = run_async_fetch(org_configs, ["Account"])
# Fetches from all 3 orgs simultaneously!
```

### Task 3: Download Yesterday's Data

```
1. Go to 📊 Data Operations tab
2. Filter by Date (if you remember it)
3. Find your operation
4. Click operation name
5. Click "📥 Download as CSV"
6. Open CSV in Excel
```

### Task 4: Export History for Backup

```
1. Go to 📊 Data Operations tab
2. (Optional) Apply filters for specific subset
3. Click "📥 Export All Operations to CSV"
4. Opens file with all operations
5. Can save to Google Drive or email
```

### Task 5: Add Tracking to Your Code

```python
# Before (no tracking):
df = pd.read_csv(uploaded_file)

# After (with tracking - 1 line):
from ui_components.data_hub.operation_tracker import track_file_upload
df, op_id = track_file_upload(uploaded_file, target_org="HeraQA", object_name="Account")

# That's it! Data is now permanently saved
```

## Performance Reference

### Fetch Speed

| Scenario | Time | Benefit |
|----------|------|---------|
| 1 org, 1 object (sequential) | 10s | Baseline |
| 3 orgs, 1 object (sequential) | 30s | 3x slower |
| 3 orgs, 1 object (parallel) | 10s | **3x faster!** ⚡ |
| 3 orgs, 3 objects (parallel) | 10s | **9x faster!** ⚡⚡ |

### Storage Size

| Item | Size |
|------|------|
| Manifest (100 operations) | ~50 KB |
| 1000 Account records | ~100 KB |
| 10,000 Account records | ~1 MB |
| 100,000 Account records | ~10 MB |

## Troubleshooting Checklist

- [ ] Check if `data_hub_operations_manifest.json` exists
- [ ] Check if `data_hub_operations/` folder exists and is writable
- [ ] Verify file permissions are correct
- [ ] Refresh browser (F5) to reload manifest
- [ ] Check if filters are hiding your operation
- [ ] Look for error messages in browser console (F12)
- [ ] Try downloading the operation (tests if file exists)
- [ ] Try exporting all operations (tests manifest)

## Key Differences: Before vs After

### Data Storage
- **Before:** Lost when app closes
- **After:** Saved forever in JSON + CSV

### Audit Trail
- **Before:** No history at all
- **After:** Complete tracking (when, what, where, who, status)

### Multi-Org
- **Before:** One org at a time (slow)
- **After:** Multiple orgs simultaneously (3x faster)

### Data Retrieval
- **Before:** Must re-upload to use again
- **After:** Download from history anytime

### Validation
- **Before:** Not recorded
- **After:** Pass/fail counts saved automatically

## Reference: Operation Types

```
Operation Type     | How to Create | Example
─────────────────┼──────────────┼──────────────────────
SOQL_Query       | Query SF     | Fetch Account from HeraQA
File_Upload      | Upload file  | Upload Rates_Details.csv
Data_Load        | Load to SF   | Insert 245 records to TestDev
```

## Reference: Validation Status

```
Status   | Meaning | Example
─────────┼─────────┼──────────────────────
PASSED   | 100%ok  | All 500 records valid
FAILED   | 0% ok   | 0 records valid
PARTIAL  | ~50% ok | 245 pass, 6 fail
```

---

**Print this card and keep it nearby!** 📋
