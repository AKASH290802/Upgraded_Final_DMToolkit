# 📊 Data Hub Integration Guide

## Overview

The **Data Hub** is a centralized data management system that allows users to:
- Upload files (CSV, Excel) once
- Query Salesforce via SOQL directly
- Reuse data across all toolkit modules without re-uploading
- Track data source and freshness

## Key Features

✅ **Unified Data Source** - Single point of data entry
✅ **Multiple Input Methods** - File upload OR SOQL query
✅ **Caching System** - Data stored in session state for instant access
✅ **Metadata Tracking** - Know where data came from and when
✅ **Easy Integration** - Simple helper functions for other modules

---

## How It Works for End Users

### Step 1: Load Data
User goes to **📊 Data Hub** tab and either:
- Uploads a CSV/Excel file
- Executes a SOQL query
- Loads a previously cached dataset

### Step 2: Data is Stored
- Data cached in Streamlit session state
- Metadata tracked (source, timestamp, row count, etc.)
- Dataset marked as "active"

### Step 3: Use Anywhere
- User goes to any other module (Validation, Data Operations, etc.)
- Module automatically detects and uses the active dataset
- No need to upload data again!

### Step 4: Switch Datasets
- User can switch between cached datasets anytime
- All modules automatically use the newly active dataset

---

## Integration for Developers

### Option 1: Basic Data Check (Recommended for simple modules)

```python
from ui_components.data_hub.integration import has_data, get_data_from_hub, show_data_source_info

def my_module_function():
    st.header("My Module")
    
    # Check if data is loaded
    if not has_data():
        st.warning("Please load data from Data Hub first")
        st.stop()
    
    # Get the data
    df = get_data_from_hub()
    
    # Show user what data they're working with
    show_data_source_info()
    
    # Process data
    st.write("Data shape:", df.shape)
    st.dataframe(df.head())
```

### Option 2: Full Validation (Recommended for complex operations)

```python
from ui_components.data_hub.integration import validate_data_available, get_data_from_hub

def enhanced_validation():
    st.header("Enhanced Validation")
    
    # Validate data is available (shows helpful message if not)
    if not validate_data_available("Enhanced Validation"):
        st.stop()
    
    # Get data
    df = get_data_from_hub()
    
    # Proceed with processing
    # ... validation logic ...
```

### Option 3: Detailed Data Info

```python
from ui_components.data_hub.integration import get_data_info, get_data_summary

def my_module():
    # Get detailed information
    data_info = get_data_info()
    
    if data_info:
        st.metric("Dataset", data_info['name'])
        st.metric("Rows", data_info['metadata']['row_count'])
        st.metric("Columns", data_info['metadata']['column_count'])
        
        # Show summary
        summary = get_data_summary()
        st.caption(f"Working with: {summary}")
```

---

## Integration Examples for Each Module

### 1. Enhanced Validation Module

**Current Flow:**
```
User uploads file → Validation processes → Shows results
```

**With Data Hub:**
```
User loads data from Hub → Validation uses cached data → Shows results
```

**Implementation:**
```python
# In validation_operations.py - Add at the beginning of show_validation_operations()

from ui_components.data_hub.integration import validate_data_available, get_data_from_hub

def show_validation_operations(credentials):
    st.header("✅ Enhanced Validation")
    
    # Check if data is available from Data Hub
    if validate_data_available("Enhanced Validation"):
        df_original = get_data_from_hub()
        
        st.info("✅ Using data from Data Hub")
        show_data_source_info()
        
        # Continue with existing validation logic
        # (All your existing code here - NO CHANGES NEEDED)
        # ...
    
    # If validation_data_available returns False, st.stop() is called
    # and user sees helpful message
```

### 2. Data Operations Module

**Implementation:**
```python
# In data_operations.py

from ui_components.data_hub.integration import has_data, get_data_from_hub

def show_data_operations(credentials):
    st.header("📥 Data Operations")
    
    # Optional: Add tab for manual upload OR use Hub data
    use_hub_data = st.radio(
        "Data Source:",
        ["Use Hub Data", "Upload New File"]
    )
    
    if use_hub_data:
        if not has_data():
            st.warning("No data in Data Hub. Please load data first.")
            st.stop()
        
        df = get_data_from_hub()
        st.success("✅ Using Hub data")
        
    else:
        # Original file upload logic
        uploaded_file = st.file_uploader("Upload CSV")
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
    
    # Process df (rest of logic unchanged)
    # ...
```

### 3. Unit Testing Module

**Implementation:**
```python
# In unit_testing_operations.py

from ui_components.data_hub.integration import has_data, get_data_from_hub, get_data_summary

def show_unit_testing(credentials):
    st.header("🧪 Unit Testing")
    
    # Show what data will be tested
    if has_data():
        st.info(f"Test Data: {get_data_summary()}")
        df_test = get_data_from_hub()
    else:
        st.info("Using sample data")
        # Load sample data or ask for upload
    
    # Rest of unit testing logic
    # ...
```

### 4. Mapping Operations Module

**Implementation:**
```python
# In mapping_operations.py

from ui_components.data_hub.integration import validate_data_available, get_data_from_hub

def show_mapping_operations(credentials):
    st.header("🗺️ Field Mapping")
    
    if not validate_data_available("Field Mapping"):
        st.stop()
    
    df = get_data_from_hub()
    
    # Get columns for mapping configuration
    csv_columns = list(df.columns)
    st.write(f"CSV Columns: {csv_columns}")
    
    # Rest of mapping logic
    # ...
```

---

## Helper Functions Reference

### `has_data()` → bool
Check if active dataset exists.

```python
from ui_components.data_hub.integration import has_data

if has_data():
    # User has loaded data
    pass
else:
    # No data loaded
    st.warning("Please load data first")
```

### `get_data_from_hub()` → DataFrame or None
Get the active dataset.

```python
from ui_components.data_hub.integration import get_data_from_hub

df = get_data_from_hub()
if df is not None:
    st.write(f"Processing {len(df)} records")
```

### `get_data_info()` → Dict or None
Get metadata about active dataset.

```python
from ui_components.data_hub.integration import get_data_info

info = get_data_info()
if info:
    st.write(f"Dataset: {info['name']}")
    st.write(f"Rows: {info['metadata']['row_count']}")
    st.write(f"Source: {info['metadata']['source_type']}")
```

### `show_data_source_info()`
Display a formatted info box about active dataset.

```python
from ui_components.data_hub.integration import show_data_source_info

st.subheader("Current Data")
show_data_source_info()  # Shows metrics and source info
```

### `validate_data_available(module_name)` → bool
Validate data exists and show helpful error if not.

```python
from ui_components.data_hub.integration import validate_data_available

if not validate_data_available("My Module"):
    st.stop()  # User sees helpful message

# If we reach here, data is guaranteed to exist
df = get_data_from_hub()
```

### `get_data_summary()` → str
Get a one-line summary of the dataset.

```python
from ui_components.data_hub.integration import get_data_summary

summary = get_data_summary()
# Returns: "MyDataset (251 rows, 36 columns, loaded at 10:30)"
st.write(f"Working with: {summary}")
```

---

## Migration Guide: Existing Modules

### Before (File Upload in Each Module)

```python
# Each module had its own file upload
uploaded_file = st.file_uploader("Upload CSV")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
```

### After (Using Data Hub)

```python
from ui_components.data_hub.integration import validate_data_available, get_data_from_hub

# One-liner to get data
if validate_data_available("Module Name"):
    df = get_data_from_hub()
```

### Key Benefits

✅ No code duplication
✅ Single upload for all modules
✅ Better user experience
✅ Data consistency across operations
✅ Backward compatible (existing logic works unchanged)

---

## Implementation Checklist

- [ ] Review the Data Hub tab in the application
- [ ] Understand how to load data (file or SOQL)
- [ ] Test loading different file types
- [ ] Test SOQL query execution
- [ ] Test switching between cached datasets
- [ ] Integrate with Validation module
- [ ] Integrate with Data Operations module
- [ ] Integrate with Unit Testing module
- [ ] Integrate with Mapping module
- [ ] Test complete workflow (Load → Validate → Export)

---

## FAQ

**Q: What happens to cached data when I close the browser?**
A: Data is cleared. Streamlit session state is temporary. This is intentional for data privacy.

**Q: Can I save datasets permanently?**
A: Currently, data is session-only. Future enhancement could add persistent storage.

**Q: Can multiple users share a dataset?**
A: No, each user has their own session. Each user must load their own data.

**Q: What's the maximum dataset size?**
A: Depends on available memory. Typically 100K+ rows per dataset.

**Q: Can I use Data Hub with SQL Server data?**
A: Currently only CSV, Excel, and Salesforce SOQL. SQL Server integration could be added.

---

## Troubleshooting

### Module Says "No Data Available"
1. Go to **📊 Data Hub** tab
2. Load data using "Upload File" or "Query Salesforce"
3. Return to your module
4. Refresh the page (F5)

### Data Not Appearing in Module
1. Check **Data Hub** → **Active Dataset** tab
2. Confirm dataset is marked as active (🎯 symbol)
3. Try switching to another dataset and back

### SOQL Query Fails
1. Check query syntax
2. Verify you're connected to the right Salesforce org
3. Try adding LIMIT clause if missing
4. Check that object and field names are correct

---

## Advanced: Custom Integration

For custom modules that need more control:

```python
from ui_components.data_hub import DataHub

def my_custom_function():
    # Direct access to Data Hub
    data_hub = st.session_state.data_hub
    
    # List all datasets
    datasets = data_hub.list_datasets()
    
    # Work with specific dataset
    for dataset in datasets:
        df = data_hub.get_dataset(dataset['id'])
        # Process each dataset
```

---

## Support & Documentation

- **Data Hub Module:** `ui_components/data_hub/`
- **Integration Helpers:** `ui_components/data_hub/integration.py`
- **Main App:** `streamlit_app.py`

For questions or issues, refer to the implementation comments in the code.
