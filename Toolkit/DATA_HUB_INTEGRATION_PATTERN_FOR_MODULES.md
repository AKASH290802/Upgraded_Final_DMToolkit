# 📋 Data Hub Integration Pattern - For Other Modules

**Date:** January 7, 2026
**Audience:** Developers integrating Data Hub into other modules
**Status:** Ready to use

---

## Quick Summary

The pattern to integrate Data Hub into any module is straightforward:

1. **Import** integration functions
2. **Check** if Data Hub has active data
3. **Show** source info to user
4. **Let** user choose: Hub data or upload new
5. **Fallback** to file upload if Hub is empty

---

## Code Template

Here's a reusable pattern for any module that needs data:

```python
def show_my_module(sf_conn):
    """Module that needs data"""
    st.subheader("🔄 My Data Processing Module")
    
    # ==================== STEP 1: IMPORT DATA HUB FUNCTIONS ====================
    try:
        from ui_components.data_hub.integration import (
            get_data_from_hub,
            has_data,
            show_data_source_info
        )
    except ImportError:
        # Fallback if imports fail
        get_data_from_hub = None
        has_data = None
        show_data_source_info = None
    
    # ==================== STEP 2: DATA SOURCE SELECTION ====================
    st.write("#### 📁 Step 1: Data Source")
    
    df = None
    data_source = "none"
    
    # Check if Data Hub has active dataset
    if has_data and has_data():
        st.success("📊 Data Hub has an active dataset available!")
        show_data_source_info()
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✅ Use Data Hub Dataset", use_container_width=True):
                df = get_data_from_hub()
                data_source = "hub"
                if df is not None:
                    st.success(f"✅ **Data loaded from Hub!** {len(df)} rows, {len(df.columns)} columns")
        
        with col2:
            if st.button("📤 Upload Different File", use_container_width=True):
                data_source = "upload"
        
        if data_source == "none":
            return
    else:
        st.info("💡 No data in Data Hub. Upload a file below or load data in the 📊 Data Hub tab first.")
        data_source = "upload"
    
    # ==================== STEP 3: FILE UPLOAD (FALLBACK) ====================
    if data_source == "upload" or df is None:
        st.write("**Upload a File:**")
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['csv', 'xlsx', 'xls', 'psv'],
            key="my_module_upload",
            help="Upload your data file"
        )
        
        if not uploaded_file:
            if data_source == "upload":
                st.info("👆 Please upload a data file to continue")
            return
        
        # Load data from file
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, dtype=str)
            elif uploaded_file.name.endswith('.psv'):
                df = pd.read_csv(uploaded_file, sep='|', dtype=str)
            else:
                df = pd.read_excel(uploaded_file, dtype=str)
            
            if df.empty:
                st.error("❌ The file is empty")
                return
            
            st.success(f"✅ **Data loaded!** {len(df)} rows, {len(df.columns)} columns")
            
        except Exception as e:
            st.error(f"❌ Error loading file: {str(e)}")
            return
    
    # ==================== STEP 4: VALIDATE DATA ====================
    if df is None:
        st.error("❌ No data available to process")
        return
    
    # ==================== STEP 5: YOUR MODULE LOGIC ====================
    st.write("#### 🔄 Step 2: Process Data")
    
    # Now you have df and can process it
    # YOUR CODE HERE
    st.dataframe(df.head())
```

---

## Module-by-Module Examples

### Pattern for Simple Modules

**Use this if your module:**
- Needs to load data
- Processes data
- Shows results

```python
# At start of your module function:
from ui_components.data_hub.integration import (
    get_data_from_hub,
    has_data,
    show_data_source_info
)

# Then use pattern above...
```

### Pattern for Complex Modules

**Use this if your module:**
- Has multiple processing steps
- Transforms or validates data
- Requires specific data format

```python
# Import at top
from ui_components.data_hub.integration import (
    get_data_from_hub,
    has_data,
    show_data_source_info,
    validate_data_available,  # Additional validation helper
    get_data_summary
)

# Use in module
if not validate_data_available("My Complex Module"):
    st.stop()

df = get_data_from_hub()
summary = get_data_summary()
st.info(f"Working with: {summary}")
```

---

## Minimal Integration (3 Lines)

**If you just want minimal Data Hub support:**

```python
# 1. Import
from ui_components.data_hub.integration import get_data_from_hub, has_data

# 2. Check
if has_data():
    df = get_data_from_hub()
    st.info("Using data from Data Hub")
else:
    # Your existing file upload code
    uploaded_file = st.file_uploader(...)
    df = pd.read_csv(uploaded_file)

# 3. Process
st.dataframe(df)
```

---

## Integration Functions Reference

### `has_data()` - Check If Hub Has Data
```python
from ui_components.data_hub.integration import has_data

if has_data():
    # Data is available in Data Hub
    st.write("✅ Data is ready to use")
else:
    # No data loaded
    st.write("❌ Please load data first")
```
| Property | Value |
|----------|-------|
| **Returns** | `bool` |
| **Usage** | Check before calling `get_data_from_hub()` |
| **Example** | `if has_data():` |

---

### `get_data_from_hub()` - Get The Data
```python
from ui_components.data_hub.integration import get_data_from_hub

df = get_data_from_hub()
if df is not None:
    st.dataframe(df)
```
| Property | Value |
|----------|-------|
| **Returns** | `pd.DataFrame` or `None` |
| **Usage** | Get the active dataset |
| **Example** | `df = get_data_from_hub()` |

---

### `show_data_source_info()` - Display Info
```python
from ui_components.data_hub.integration import show_data_source_info

show_data_source_info()
# Shows: Dataset name, rows, columns in nice format
```
| Property | Value |
|----------|-------|
| **Returns** | `None` (displays in Streamlit) |
| **Usage** | Show user where data comes from |
| **Output** | 3-column metric display |

---

### `get_data_info()` - Get Info Dict
```python
from ui_components.data_hub.integration import get_data_info

info = get_data_info()
if info:
    print(f"Dataset: {info['name']}")
    print(f"Rows: {info['metadata']['row_count']}")
```
| Property | Value |
|----------|-------|
| **Returns** | `dict` with 'name' and 'metadata' keys |
| **Usage** | Get data info programmatically |
| **Structure** | `{'name': '...', 'metadata': {...}}` |

---

### `validate_data_available(module_name)` - Validate & Error
```python
from ui_components.data_hub.integration import validate_data_available

if not validate_data_available("My Module"):
    st.stop()

# Code here only runs if data is available
df = get_data_from_hub()
```
| Property | Value |
|----------|-------|
| **Returns** | `bool` |
| **Usage** | Validate data + show error message if not |
| **Behavior** | Shows helpful steps if data missing |

---

### `get_data_summary()` - Get Summary String
```python
from ui_components.data_hub.integration import get_data_summary

summary = get_data_summary()
st.info(f"Working with: {summary}")
# Output: "Account Data (5000 rows, 35 columns, loaded at 14:30:45)"
```
| Property | Value |
|----------|-------|
| **Returns** | `str` - Formatted summary |
| **Usage** | Display to user in info messages |
| **Format** | `"Name (rows, cols, timestamp)"` |

---

## Step-by-Step Example: Data Operations Module

Here's a real example for a "Data Operations" module:

```python
def show_data_operations(sf_conn):
    """Data Operations - Transform, clean, prepare data"""
    st.subheader("🔄 Data Operations")
    
    # Import Data Hub integration
    try:
        from ui_components.data_hub.integration import (
            get_data_from_hub,
            has_data,
            show_data_source_info,
            get_data_summary
        )
    except ImportError:
        get_data_from_hub = None
        has_data = None
        show_data_source_info = None
        get_data_summary = None
    
    # ========== SECTION 1: Data Selection ==========
    st.write("### 1️⃣ Select Data Source")
    
    df = None
    
    if has_data and has_data():
        st.success("✅ Data is available in Data Hub!")
        show_data_source_info()
        
        if st.button("Use Data Hub Data"):
            df = get_data_from_hub()
            st.info(f"📊 {get_data_summary()}")
    
    # Fallback: File upload
    if df is None:
        uploaded_file = st.file_uploader(
            "Or upload a file",
            type=['csv', 'xlsx', 'xls', 'psv'],
            key="data_ops_upload"
        )
        
        if uploaded_file:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith('.psv'):
                df = pd.read_csv(uploaded_file, sep='|')
            else:
                df = pd.read_excel(uploaded_file)
    
    # Stop if no data
    if df is None:
        st.info("👆 Load data to continue")
        return
    
    # ========== SECTION 2: Data Cleaning ==========
    st.write("### 2️⃣ Clean Data")
    
    # Remove duplicates
    if st.checkbox("Remove Duplicates"):
        df = df.drop_duplicates()
        st.success(f"Removed duplicates! Now {len(df)} rows")
    
    # Remove nulls
    if st.checkbox("Remove Null Rows"):
        df = df.dropna(how='any')
        st.success(f"Removed nulls! Now {len(df)} rows")
    
    # ========== SECTION 3: Preview & Download ==========
    st.write("### 3️⃣ Preview & Export")
    
    st.dataframe(df.head(20), use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        csv = df.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, "data.csv", "text/csv")
    
    with col2:
        from io import BytesIO
        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        st.download_button("📥 Download Excel", buffer.getvalue(), "data.xlsx")
```

---

## Common Patterns

### Pattern 1: Simple Check
```python
if has_data():
    df = get_data_from_hub()
else:
    df = pd.read_csv(uploaded_file)
```

### Pattern 2: With Override
```python
df = None
if has_data():
    if st.button("Use Hub Data"):
        df = get_data_from_hub()
    elif st.button("Upload New"):
        df = load_from_file()
else:
    df = load_from_file()
```

### Pattern 3: With Fallback
```python
df = get_data_from_hub() if has_data() else None

if df is None:
    uploaded_file = st.file_uploader(...)
    if uploaded_file:
        df = load_from_file(uploaded_file)
```

### Pattern 4: With Validation
```python
from ui_components.data_hub.integration import validate_data_available

if not validate_data_available("My Module"):
    st.stop()  # Don't continue if no data

df = get_data_from_hub()  # Safe to call now
```

---

## Files to Update

**Current Implementation:**
- ✅ `show_enhanced_validation()` - Already updated in validation_operations.py

**Recommended for Update:**
- [ ] `show_data_operations()` - Use same pattern
- [ ] `show_unit_testing()` - Use same pattern
- [ ] Any other data-consuming modules

**No Changes Needed:**
- ✅ `data_hub.py` - Core implementation correct
- ✅ `integration.py` - Helper functions correct
- ✅ `data_hub_ui.py` - UI correct
- ✅ `data_source_handler.py` - File handling correct

---

## Testing Your Integration

### Test 1: With Hub Data
```
1. Load data to Data Hub
2. Go to your module
3. Should see "Data Hub has an active dataset"
4. Click "Use Hub Data"
5. Data should load instantly ✅
```

### Test 2: Without Hub Data
```
1. Don't load data to Data Hub
2. Go to your module
3. Should see "No data in Data Hub" message
4. Upload file
5. Data should load from file ✅
```

### Test 3: Override
```
1. Load data to Data Hub
2. Go to your module
3. Click "Use different file"
4. Upload different file
5. Module should use uploaded file, not Hub data ✅
```

---

## Troubleshooting

### Issue: `ImportError: cannot import name 'get_data_from_hub'`
**Solution:** Check file path is correct:
```python
from ui_components.data_hub.integration import get_data_from_hub
```

### Issue: `has_data()` always returns False
**Solution:** Make sure Data Hub is initialized in main app:
```python
# In streamlit_app.py
if 'data_hub' not in st.session_state:
    st.session_state.data_hub = DataHub()
```

### Issue: Data loads but changes don't persist across tabs
**Solution:** Use session state properly:
```python
# Correct: Data stored in session_state
if 'data_hub' in st.session_state:
    df = st.session_state.data_hub.get_active_dataset()

# Wrong: Creating new DataHub instance
from ui_components.data_hub import DataHub
data_hub = DataHub()  # ❌ Wrong! Creates new instance
```

---

## Best Practices

✅ **DO:**
- Check `has_data()` before calling `get_data_from_hub()`
- Show `show_data_source_info()` to let user know where data comes from
- Provide file upload as fallback
- Allow user to upload different file if they want
- Use the integration helpers (don't re-implement)

❌ **DON'T:**
- Create new DataHub instances (use session_state)
- Skip the fallback file upload (breaks backward compatibility)
- Force users to use Data Hub (give them choice)
- Ignore errors from file loading

---

## Summary

**To integrate Data Hub into any module:**

1. **Copy the template** above
2. **Add imports** at the start
3. **Add data source selection** logic
4. **Add file upload fallback**
5. **Test** with and without Hub data
6. **Done!** ✅

The pattern is identical for every module - just customize the processing logic.

---

**Template Complexity:** 50 lines of boilerplate
**Integration Time:** ~10 minutes per module
**Testing Time:** ~5 minutes per module
**Total:** ~1 hour to integrate all modules

