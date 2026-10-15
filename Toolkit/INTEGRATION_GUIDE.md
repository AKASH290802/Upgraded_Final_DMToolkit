# Integration Guide: Adding Operation Tracking to Existing Code

This guide shows how to add operation tracking to your existing data loading workflows.

## Quick Start

### Step 1: Import the Tracker

```python
from ui_components.data_hub.operation_tracker import (
    track_file_upload,
    track_soql_query,
    track_data_load,
    get_last_operation_data
)
```

### Step 2: Wrap Your File Upload

**BEFORE:**
```python
uploaded_file = st.file_uploader("Upload CSV")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.dataframe(df)
```

**AFTER:**
```python
uploaded_file = st.file_uploader("Upload CSV")
if uploaded_file:
    df, operation_id = track_file_upload(
        uploaded_file,
        target_org="HeraQA",
        object_name="Account"
    )
    
    if df is not None:
        st.success(f"✅ Loaded! Operation: {operation_id}")
        st.dataframe(df)
    else:
        st.error(f"❌ Error: {operation_id}")
```

### Step 3: Wrap Your SOQL Queries

**BEFORE:**
```python
query = "SELECT Id, Name FROM Account LIMIT 100"
result = sf_connection.query(query)
records = [r for r in result['records']]
df = pd.DataFrame(records)
```

**AFTER:**
```python
query = "SELECT Id, Name FROM Account LIMIT 100"
df, operation_id = track_soql_query(
    sf_connection,
    query,
    source_org="HeraQA",
    object_name="Account"
)

if df is not None:
    st.success(f"✅ Query successful! Operation: {operation_id}")
else:
    st.error(f"❌ Error: {operation_id}")
```

### Step 4: Wrap Your Data Loads

**BEFORE:**
```python
for record in data:
    sf_target.Account.create(record)
```

**AFTER:**
```python
successful = 0
failed = 0

for record in data:
    try:
        sf_target.Account.create(record)
        successful += 1
    except Exception as e:
        failed += 1

operation_id = track_data_load(
    data,
    target_org="TestDev",
    object_name="Account",
    successful_records=successful,
    failed_records=failed
)

st.info(f"✅ Load tracked: {operation_id}")
```

## Integration Examples by Tab

### Data Hub Tab

**Current Location:** Find data loading in `ui_components/data_hub/data_hub_ui.py`

**Add tracking after loading:**
```python
if uploaded_file:
    df, _ = load_from_file(uploaded_file)
    
    # Add operation tracking
    from ui_components.data_hub.operation_tracker import track_file_upload
    operation_id = track_file_upload(
        uploaded_file,
        object_name=selected_object
    )
```

### Business Rules Tab

**Location:** `org_migration.py` around line 2057 (file upload)

**Already has PSV support. Add tracking:**
```python
if uploaded_file:
    from ui_components.utils import load_data_file
    rules_data = load_data_file(uploaded_file)
    
    # Add operation tracking
    from ui_components.data_hub.operation_tracker import track_file_upload
    op_id = track_file_upload(
        uploaded_file,
        target_org=selected_org,
        object_name=selected_object,
        validation_status="PENDING"
    )
```

### Data Quality Tab

**Location:** `org_migration.py` around line 2280

**Add tracking:**
```python
if quality_file:
    df, _ = load_from_file(quality_file)
    
    # Add operation tracking
    from ui_components.data_hub.operation_tracker import track_file_upload
    op_id = track_file_upload(
        quality_file,
        target_org=selected_org,
        object_name=selected_object,
        validation_status="IN_PROGRESS"
    )
```

### Org Migration Execute Tab

**Location:** `org_migration.py` around line 3600 (actual migration execution)

**Add tracking after successful load:**
```python
# After executing migration...
if migration_successful:
    from ui_components.data_hub.operation_tracker import track_data_load
    
    operation_id = track_data_load(
        migrated_data,
        target_org=target_org_name,
        object_name=object_name,
        successful_records=success_count,
        failed_records=error_count,
        load_method="API"
    )
    
    st.success(f"Migration tracked: {operation_id}")
```

## Advanced Usage

### Resume from Last Operation

```python
from ui_components.data_hub.operation_tracker import get_last_operation_data

# Show button to load last operation's data
if st.button("📂 Use Last Loaded Data"):
    last_data = get_last_operation_data("Account")
    if last_data is not None:
        st.session_state.current_data = last_data
        st.success("✅ Loaded last operation data")
    else:
        st.info("No previous operations found")
```

### Add Validation Results to Tracking

```python
# After validation runs
validation_results = validate_data(data)

operation_id = track_file_upload(
    uploaded_file,
    target_org=selected_org,
    object_name=selected_object,
    validation_status="PASSED" if validation_results['all_passed'] else "FAILED",
    validation_passed=validation_results['passed_count'],
    validation_failed=validation_results['failed_count']
)
```

### Multi-Org Async Loading

```python
from ui_components.async_processor import run_async_load

target_orgs = [
    {"org_name": "HeraQA", "connection": sf_heraqa},
    {"org_name": "TestDev", "connection": sf_testdev},
    {"org_name": "Navitas", "connection": sf_navitas}
]

progress = st.empty()

results = run_async_load(
    data,
    target_orgs,
    "Account",
    progress
)

# Track each load separately
for result in results:
    if result['status'] == 'COMPLETE':
        track_data_load(
            data,
            target_org=result['org_name'],
            object_name=result['object_name'],
            successful_records=result['successful_inserts'],
            failed_records=result['failed_inserts']
        )
```

## Common Patterns

### Pattern 1: Load → Validate → Track

```python
# 1. Load data
df, load_op_id = track_file_upload(uploaded_file, ...)

# 2. Run validation
validation_result = run_validation(df)

# 3. Update operation with validation status
# (Note: To update, use get_operation_manager() and modify manifest)
from ui_components.data_hub.operation_manager import get_operation_manager

op_manager = get_operation_manager()
operations = op_manager.get_operation_history()

# Find and update the operation
for op in operations:
    if op['operation_id'] == load_op_id:
        op['validation_status'] = 'PASSED' if validation_result else 'FAILED'
        break
```

### Pattern 2: Query → Filter → Load

```python
# 1. Query from source
df1, _ = track_soql_query(sf_source, query, "SourceOrg", "Account")

# 2. Filter/transform
df_filtered = df1[df1['Status'] == 'Active']

# 3. Load to target
operation_id = track_data_load(
    df_filtered,
    target_org="TargetOrg",
    object_name="Account",
    successful_records=len(df_filtered),
    failed_records=0
)
```

### Pattern 3: Multi-Source Merge

```python
from ui_components.async_processor import run_async_fetch

# 1. Fetch from multiple orgs in parallel
org_configs = [...]
results = run_async_fetch(org_configs, ["Account"])

# 2. Merge all DataFrames
all_data = []
for df, metadata in results:
    df['source_org'] = metadata['org_name']
    all_data.append(df)

merged_df = pd.concat(all_data, ignore_index=True)

# 3. Track the merged dataset
operation_id = track_data_load(
    merged_df,
    source_org="Multi-Org",
    object_name="Account",
    successful_records=len(merged_df),
    failed_records=0
)
```

## Testing Your Integration

### Test 1: Upload File

1. Go to any tab with file upload
2. Upload a CSV file
3. Go to **📊 Data Operations** tab
4. Should see your operation in the list

### Test 2: View Historical Data

1. Upload a file (or run a query)
2. Close the browser
3. Open the app again
4. Go to **📊 Data Operations** tab
5. Your previous operation should still be there!

### Test 3: Parallel Operations

```python
# Run this code somewhere
from ui_components.async_processor import run_async_fetch

result = run_async_fetch(org_configs, ["Account", "Opportunity"])
# Should complete much faster than sequential
```

### Test 4: Export History

1. Go to **📊 Data Operations** tab
2. Click "📥 Export All Operations to CSV"
3. Download and open in Excel
4. Should show all your historical operations

## Performance Tips

1. **Large DataFrames:** For >100k records, consider batching operations
2. **Manifest Size:** Periodically delete old operations to keep manifest small
3. **File Storage:** Monitor `data_hub_operations/` folder size
4. **Async Limits:** Don't fetch >10 objects simultaneously to avoid rate limits

## Troubleshooting Integration

### Issue: "Operation tracking not working"

**Check:**
1. `data_hub_operations/` folder exists and is writable
2. Import statements are correct
3. No import errors in console

**Solution:**
```python
# Test the import
try:
    from ui_components.data_hub.operation_manager import get_operation_manager
    om = get_operation_manager()
    print("✅ Operation Manager loaded")
except Exception as e:
    print(f"❌ Error: {e}")
```

### Issue: "Async operations not running in parallel"

**Check:**
1. Using `run_async_fetch()` helper function
2. Not running inside a Streamlit callback (uses different thread)
3. Event loop not already active

**Solution:**
```python
# Use the helper instead of direct asyncio
from ui_components.async_processor import run_async_fetch
results = run_async_fetch(org_configs, objects, st.empty())
```

### Issue: "Old operations not loading"

**Check:**
1. `data_hub_operations_manifest.json` exists
2. CSV files referenced in manifest still exist
3. File permissions are correct

**Solution:**
```python
# Verify manifest
import json
with open('data_hub_operations_manifest.json', 'r') as f:
    manifest = json.load(f)
    print(f"Operations in manifest: {len(manifest['operations'])}")
```

---

**Need more help?** Check `DATA_OPERATIONS_HISTORY_README.md` for complete documentation.
