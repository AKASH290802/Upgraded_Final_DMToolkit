# Data Operations History - Quick Start Guide

## What's New?

✅ **All data is now saved permanently** - Never lose data when you close the app
✅ **New 📊 Data Operations tab** - View all historical operations with one click
✅ **Multi-org parallel processing** - Fetch from multiple Salesforce orgs simultaneously
✅ **Complete audit trail** - See what data was loaded, when, by whom, and validation status

## Getting Started in 2 Minutes

### 1. Run Your First Operation

Go to any tab and:
- Upload a CSV/Excel/PSV file, OR
- Run a SOQL query

That's it! Your operation is automatically tracked.

### 2. View Your Data Anytime

1. Open the app anytime (next day, next week, next month)
2. Go to **📊 Data Hub** → Click **📊 Data Operations** tab
3. Your data is still there! ✅

### 3. Explore Your History

In the **📊 Data Operations** tab (within Data Hub) you can:

- **📈 See statistics** - Total operations, records, validation results
- **🔍 Filter operations** - By org, object, type, status
- **📋 View any operation** - See all details and data
- **📥 Download data** - Export as CSV or Excel
- **📤 Export history** - Backup all your operations

## Key Features

### Feature 1: Persistent Storage

**Before (Lost data):**
```
Upload file → Close app → Data gone 😞
```

**After (Data saved):**
```
Upload file → Close app → Data still there! 😊
Operation: OP-20260109143522 (saved permanently)
```

### Feature 2: Complete Audit Trail

Every operation records:
- **When:** Exact timestamp
- **What:** File uploaded, SOQL query, or data load
- **Where:** Source org → Target org
- **Object:** Which Salesforce object (Account, Opportunity, etc.)
- **How many:** Total records, passed validation, failed validation
- **Who:** Which user performed operation

### Feature 3: Parallel Multi-Org Processing

**Old way (Slow - sequential):**
```
Fetch Account from Org1 → Wait ⏳
Fetch Account from Org2 → Wait ⏳
Fetch Opportunity from Org3 → Wait ⏳
Total time: 30 seconds
```

**New way (Fast - parallel):**
```
Fetch Account from Org1 ↓
Fetch Account from Org2 ↓ All run simultaneously!
Fetch Opportunity from Org3 ↓
Total time: 10 seconds (3x faster!)
```

## Example: Upload → Validate → Save

### Step 1: Upload Data
- Go to **4️⃣ Business Rules** tab
- Click "Upload data file for rules validation"
- Select your CSV/Excel/PSV file
- ✅ Automatically saved with operation ID

### Step 2: Run Validation
- Check validation rules
- See which records pass/fail
- ✅ Validation results saved to operation

### Step 3: View Anytime
- Go to **📊 Data Operations** tab
- Your operation appears in the history
- Click to see full data, validation details, download
- ✅ Same data available forever!

## Example: Fetch from Multiple Orgs

### What You Want:
Fetch Account from HeraQA, TestDev, and Navitas simultaneously

### How to Do It:
```python
# Code example (for advanced users)
from ui_components.async_processor import run_async_fetch

org_configs = [
    {"org_name": "HeraQA", "connection": sf_heraqa},
    {"org_name": "TestDev", "connection": sf_testdev},
    {"org_name": "Navitas", "connection": sf_navitas}
]

results = run_async_fetch(
    org_configs,
    ["Account"],  # Objects to fetch
    st.empty()    # Progress indicator
)
# All 3 fetches happen at the same time!
```

## Feature Walkthrough: 📊 Data Operations Tab

### 📈 Statistics Dashboard (Top Section)
Shows your operation metrics at a glance:
- Total operations performed
- Total records processed
- Records that passed validation
- Records that failed validation

### 🔍 Filters (Second Section)
Filter your operations:
- **Organization** - Select which org (HeraQA, TestDev, etc.)
- **Object** - Select which object (Account, Opportunity, etc.)
- **Operation Type** - SOQL_Query, File_Upload, Data_Load
- **Status** - COMPLETE or FAILED

### 📋 Operations Table (Third Section)
See all matching operations:
- Operation ID (unique identifier)
- Date/Time performed
- Source and target org
- Object name
- Number of records
- Validation status (✅ or ❌)

Click any row to see details

### 📂 View Details (Fourth Section)
Click an operation to see:
- **Metadata** - Who, when, what, status
- **SOQL Query** - The exact query used (if applicable)
- **File Info** - Which file was uploaded (if applicable)
- **Data Preview** - Sample of the data
- **Column Statistics** - Data quality metrics
- **Download Buttons** - Get data as CSV or Excel
- **Delete Button** - Remove operation if needed

### 📤 Export History (Bottom)
Export all operations to CSV file for:
- Backup
- Analysis in Excel
- Sharing with team
- Compliance/audit

## Common Questions

### Q: How long are operations saved?
**A:** Forever! Until you manually delete them. They survive app restarts, computer restarts, everything.

### Q: Where is my data stored?
**A:** Locally in `data_hub_operations/` folder. Simple CSV files, very portable.

### Q: Can I share my operations history?
**A:** Yes! Go to **📊 Data Operations** tab → Click "📥 Export All Operations to CSV" → Share the CSV file.

### Q: What if I delete an operation?
**A:** It's removed from history and the data file is deleted. Can't be recovered.

### Q: How do I use data from a previous operation?
**A:** Go to **📊 Data Operations** tab → Find the operation → Click to view → Click "📥 Download as CSV" → Use that file.

### Q: Can I run operations on multiple orgs at the same time?
**A:** Yes! Use the async processor for parallel processing. Much faster than sequential!

### Q: What validation information is saved?
**A:** Number of records that passed/failed, validation status (PASSED/FAILED/PARTIAL), and validation errors if any.

## Workflow Examples

### Example 1: Monthly Data Validation

```
Day 1: Upload Account file → Auto-saved (OP-20260109*)
        Run validation → Status saved
        
Day 5: Need to re-check? Go to 📊 tab → Find OP-20260109* → View data
        Same file, no need to re-upload!
        
Day 15: Download data for analysis → Click download button → Get CSV
        
Day 30: Export all operations → Archive to team drive
```

### Example 2: Multi-Org Migration

```
Step 1: Fetch Account from 3 orgs (simultaneous)
        ✅ OP-20260109143522 (HeraQA - 251 records)
        ✅ OP-20260109143524 (TestDev - 1024 records)
        ✅ OP-20260109143526 (Navitas - 500 records)
        
Step 2: Validate all 3 datasets
        ✅ Results saved to each operation
        
Step 3: Compare validation results
        Go to 📊 tab → View each operation → Compare pass rates
        
Step 4: Merge and load
        Download 3 files → Merge locally → Upload merged file
        ✅ OP-20260109150000 (Merged Account - 1775 records)
```

### Example 3: Data Quality Monitoring

```
Every week:
1. Run Account query from source org
   ✅ OP-20260102* - 500 records
2. Run validation
   ✅ 480 passed, 20 failed
3. Next week:
   ✅ OP-20260109* - 512 records
   ✅ 505 passed, 7 failed
4. Trend: Quality improving! 📈
```

## Tips & Tricks

### Tip 1: Use Descriptive Names
When naming files for upload, use clear names:
- ✅ Good: `Account_2026_01_09.csv`
- ❌ Not good: `data.csv`

The filename is saved in the operation, so descriptive names help later!

### Tip 2: Add Notes
You can add notes to operations for context. (Advanced: Requires code modification)

### Tip 3: Filter Before Export
If exporting history:
1. Apply filters (e.g., only HeraQA operations)
2. Export CSV
3. You get only the filtered operations!

### Tip 4: Schedule Regular Backups
Export operation history weekly:
1. Go to **📊 Data Operations**
2. Click "📥 Export All Operations to CSV"
3. Save to Google Drive or team folder
4. You have backup of all operations!

### Tip 5: Delete Old Operations
To keep manifest lean, periodically delete very old operations:
1. Filter by date (oldest first)
2. Click operation to view
3. Click "🗑️ Delete Operation"
4. Frees up space!

## Troubleshooting

### Problem: Can't see my old operations
**Solution:** 
1. Refresh page (F5)
2. Check filters - they might be hiding operations
3. Check if app was run from same directory where you saved files

### Problem: "Data file not found" error
**Solution:**
1. The manifest exists but CSV was deleted
2. Go to 📊 Data Operations tab
3. Click the problematic operation
4. Click "🗑️ Delete Operation"
5. Re-create the operation by uploading the file again

### Problem: Can't download file
**Solution:**
1. Check browser download settings
2. Make sure browser allows downloads
3. Try different file format (CSV instead of Excel)

### Problem: Async fetch not working
**Solution:**
1. Make sure using correct function: `run_async_fetch()`
2. Check browser console for errors (F12 → Console)
3. Verify all org connections are valid

## Next Steps

### Ready to Use?
1. ✅ Open the app
2. ✅ Go to any data loading tab
3. ✅ Upload a file or run a query
4. ✅ Operations are auto-tracked!
5. ✅ Go to **📊 Data Operations** to see history

### Want Advanced Features?
- See `INTEGRATION_GUIDE.md` for code examples
- See `DATA_OPERATIONS_HISTORY_README.md` for complete documentation

### Have Questions?
- Check the FAQ above
- Read the documentation files
- Check application logs for error details

---

**Enjoy persistent data storage! Your operations are now forever.** 🎉
