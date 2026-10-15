# Data Hub Integration Example: Validation Operations

This document shows exactly how to integrate the Data Hub with the existing **Validation Operations** module without breaking existing functionality.

---

## Option 1: MINIMAL Integration (Recommended First Step)

### What to Do

Add just 5 lines of code to check for Data Hub data, but keep all existing code:

**File:** `ui_components/validation_operations.py`

**Location:** At the beginning of `show_validation_operations()` function

**Code to Add:**
```python
def show_validation_operations(credentials):
    """Show validation operations interface"""
    
    # ===== NEW: ADD THESE LINES =====
    from ui_components.data_hub.integration import has_data, get_data_from_hub
    
    # Try to get data from Data Hub first
    df_from_hub = None
    if has_data():
        df_from_hub = get_data_from_hub()
        st.info("✅ Using data from Data Hub")
    
    # ===== END NEW CODE =====
    
    # Existing validation code continues here
    # ... (no changes to existing code)
```

### Then Later in the Function

Where file upload currently happens, add a check:

```python
# Original file upload section
if df_from_hub is not None:
    # Use data from hub
    df_original = df_from_hub
else:
    # Original file upload code (unchanged)
    uploaded_file = st.file_uploader("Choose a file", type=['csv', 'xlsx', 'xls'])
    
    if uploaded_file is not None:
        # ... existing file processing code ...
```

---

## Option 2: ENHANCED Integration (Recommended)

### What to Do

Provide user choice between Hub data and file upload:

**Code:**
```python
def show_validation_operations(credentials):
    """Show validation operations interface"""
    
    from ui_components.data_hub.integration import (
        has_data,
        get_data_from_hub,
        show_data_source_info
    )
    
    st.header("✅ Enhanced Validation")
    
    # Data source selection
    if has_data():
        data_source = st.radio(
            "Data Source:",
            ["Use Data from Hub", "Upload New File"],
            help="Choose where to get data from"
        )
    else:
        data_source = "Upload New File"
        st.info("💡 Load data from **Data Hub** for faster workflow")
    
    # Get data based on selection
    df_original = None
    
    if data_source == "Use Data from Hub":
        df_original = get_data_from_hub()
        st.success("✅ Using Hub data")
        show_data_source_info()  # Shows metrics
        
    else:  # Upload New File
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['csv', 'xlsx', 'xls']
        )
        
        if uploaded_file is not None:
            # ... existing file processing code ...
            df_original = processed_df  # Your existing code
    
    # Continue with validation (all existing code unchanged)
    if df_original is not None:
        st.divider()
        # ... ALL YOUR EXISTING VALIDATION CODE HERE ...
        # No changes needed below this point!
```

---

## Option 3: CLEAN Integration (Best Practice)

### What to Do

Refactor to use a shared data loading function:

**In validation_operations.py, add helper function:**
```python
def _load_validation_data():
    """Load data from Hub or file upload"""
    from ui_components.data_hub.integration import (
        has_data,
        get_data_from_hub,
        show_data_source_info
    )
    
    st.subheader("📊 Data Configuration")
    
    # Option 1: Data Hub
    if has_data():
        use_hub = st.checkbox(
            "Use data from Data Hub",
            value=True,
            help="Reuse previously loaded data"
        )
        
        if use_hub:
            df = get_data_from_hub()
            st.success("✅ Using Data Hub")
            show_data_source_info()
            return df
    
    # Option 2: File upload
    uploaded_file = st.file_uploader(
        "Or upload a new file:",
        type=['csv', 'xlsx', 'xls'],
        help="CSV or Excel file"
    )
    
    if uploaded_file is not None:
        # ... existing file processing ...
        return processed_df  # Your existing code
    
    return None


def show_validation_operations(credentials):
    """Show validation operations interface"""
    
    st.header("✅ Enhanced Validation")
    
    # Load data using the helper
    df_original = _load_validation_data()
    
    if df_original is None:
        st.warning("Please load data from Data Hub or upload a file")
        st.stop()
    
    st.divider()
    
    # ALL EXISTING VALIDATION CODE HERE - UNCHANGED
    # ... validation logic continues ...
```

---

## ACTUAL CODE LOCATION IN validation_operations.py

### Find This Section

Search for this in `validation_operations.py` (around line 230-270):

```python
def show_validation_operations(credentials):
    """Show validation operations interface"""
    st.header("✅ Enhanced Validation")
    
    # ... some code ...
    
    # File upload section (usually around line 250-300)
    uploaded_file = st.file_uploader(
        "Choose CSV or Excel file for validation",
        type=['csv', 'xlsx', 'xls']
    )
```

### Modify That Section To:

```python
def show_validation_operations(credentials):
    """Show validation operations interface"""
    from ui_components.data_hub.integration import (
        has_data,
        get_data_from_hub,
        show_data_source_info
    )
    
    st.header("✅ Enhanced Validation")
    
    # ... some code ...
    
    # === MODIFIED SECTION ===
    df_original = None
    
    # Try Data Hub first
    if has_data():
        st.info("💡 Data from **Data Hub** is available. Use it?")
        use_hub = st.checkbox("✅ Use Data Hub", value=True)
        
        if use_hub:
            df_original = get_data_from_hub()
            st.success("Using Data Hub data")
            show_data_source_info()
    
    # Alternative: File upload
    if df_original is None:
        uploaded_file = st.file_uploader(
            "Choose CSV or Excel file for validation",
            type=['csv', 'xlsx', 'xls']
        )
        
        if uploaded_file is not None:
            # ... existing file processing code ...
            df_original = processed_df
    
    # === END MODIFIED SECTION ===
    
    # Continue with existing validation logic (NO CHANGES)
    if df_original is not None:
        # ... all existing code continues unchanged ...
```

---

## Testing the Integration

### Test 1: Use Data Hub
1. Go to **📊 Data Hub**
2. Upload a CSV file
3. Go to **1️⃣ Validation**
4. Should see "✅ Using Data Hub" message
5. Should see data metrics

### Test 2: Upload New File
1. Go to **1️⃣ Validation**
2. Skip the Data Hub option
3. Upload a file manually
4. Should proceed with validation as before

### Test 3: Switch Data Hub Datasets
1. Load Dataset A in Data Hub
2. Go to Validation → Uses Dataset A
3. Back to Data Hub → Switch to Dataset B
4. Go to Validation → Now uses Dataset B

---

## Step-by-Step Integration for Validation Module

### Step 1: Add Import
At the top of the file with other imports, add:
```python
from ui_components.data_hub.integration import (
    has_data,
    get_data_from_hub,
    show_data_source_info
)
```

### Step 2: Find the File Upload Section
Search for `st.file_uploader` in the `show_validation_operations` function

### Step 3: Wrap with Data Hub Check
```python
# Before file upload section
df_original = None

if has_data():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("Data from **Data Hub** is available")
    with col2:
        if st.button("Use Hub Data"):
            df_original = get_data_from_hub()

if df_original is not None:
    show_data_source_info()
    st.success("✅ Using Hub Data")
else:
    # Original file upload code
    uploaded_file = st.file_uploader(...)
    # ... rest of original code ...
```

### Step 4: Test
Run the app and test both paths:
- Path 1: Using Data Hub
- Path 2: Uploading file manually

---

## Similar Integration for Other Modules

### Data Operations Module
```python
from ui_components.data_hub.integration import validate_data_available, get_data_from_hub

def show_data_operations(credentials):
    if validate_data_available("Data Operations"):
        df = get_data_from_hub()
        # ... process data ...
```

### Unit Testing Module
```python
from ui_components.data_hub.integration import has_data, get_data_from_hub

def show_unit_testing(credentials):
    if has_data():
        df_test = get_data_from_hub()
        # ... run tests ...
    else:
        st.info("Load test data from Data Hub")
```

### Mapping Module
```python
from ui_components.data_hub.integration import validate_data_available, get_data_from_hub

def show_mapping_operations(credentials):
    if validate_data_available("Mapping"):
        df = get_data_from_hub()
        csv_columns = df.columns.tolist()
        # ... mapping logic ...
```

---

## Key Points

✅ **Non-breaking** - Existing code still works
✅ **Gradual** - Integrate one module at a time
✅ **Simple** - Just a few lines of code
✅ **Flexible** - Users can still upload manually
✅ **Backward Compatible** - All existing functionality preserved

---

## Rollback Plan

If something goes wrong:
1. Remove the Data Hub imports
2. Keep the file upload section as-is
3. Validation continues to work normally

The integration is completely optional!

---

## Complete Before/After Example

### BEFORE (Original Code)
```python
def show_validation_operations(credentials):
    st.header("✅ Enhanced Validation")
    
    # File upload
    uploaded_file = st.file_uploader("Choose file", type=['csv', 'xlsx'])
    
    if uploaded_file is not None:
        df_original = pd.read_csv(uploaded_file)
        
        # Validation logic
        st.write(df_original)
```

### AFTER (With Data Hub)
```python
def show_validation_operations(credentials):
    from ui_components.data_hub.integration import has_data, get_data_from_hub
    
    st.header("✅ Enhanced Validation")
    
    df_original = None
    
    # Try Data Hub first
    if has_data():
        if st.checkbox("Use Data from Hub", value=True):
            df_original = get_data_from_hub()
            st.success("✅ Using Hub data")
    
    # Fallback to file upload
    if df_original is None:
        uploaded_file = st.file_uploader("Choose file", type=['csv', 'xlsx'])
        if uploaded_file is not None:
            df_original = pd.read_csv(uploaded_file)
    
    if df_original is not None:
        # Validation logic (unchanged)
        st.write(df_original)
```

---

## Support

For detailed API documentation, see: **DATA_HUB_INTEGRATION_GUIDE.md**
For quick start guide, see: **DATA_HUB_QUICK_START.md**
