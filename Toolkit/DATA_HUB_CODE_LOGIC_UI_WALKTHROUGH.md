# 🔍 Data Hub File Check - Code Logic & UI Walkthrough

**Date:** January 7, 2026
**Purpose:** Show exactly where to see the uploaded file and how the code checks for it

---

## How the Code Checks for Uploaded Files

### The Logic Flow (In validation_operations.py)

```python
# Line 7563-7565: Check if Data Hub has an active dataset
if has_data and has_data():
    # File WAS uploaded to Data Hub
    st.success("📊 Data Hub has an active dataset available!")
```

**What `has_data()` function does:**
```python
# From: ui_components/data_hub/integration.py
def has_data() -> bool:
    """Check if active dataset exists"""
    if 'data_hub' in st.session_state:
        return st.session_state.data_hub.has_active_dataset()
    return False
```

**Translation:** 
- Checks if Data Hub exists in session memory
- Checks if you have set a dataset as "active"
- Returns `True` if YES, `False` if NO

---

## In the Validation Tab - The UI You'll See

### Scenario 1: File IS in Data Hub (After Upload & Set Active)

**Code: Lines 7563-7580**

**What You'll See:**

```
⚡ Enhanced Transform Validation

#### 📁 Step 1: Data Source

✅ 📊 Data Hub has an active dataset available!

📊 Dataset: Account Data
📦 Rows: 5000
📋 Columns: 35

[✅ Use Data Hub Dataset] [📤 Upload Different File]
```

**What's Happening in Code:**
```python
if has_data and has_data():  # TRUE - File is in Hub
    st.success("📊 Data Hub has an active dataset available!")  # ← You see this
    show_data_source_info()  # ← Shows Dataset name, rows, columns
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("✅ Use Data Hub Dataset", use_container_width=True):
            # ← THIS BUTTON - Click to use file from Hub
            df_original = get_data_from_hub()  # Gets the file
    
    with col2:
        if st.button("📤 Upload Different File", use_container_width=True):
            # ← THIS BUTTON - Click to upload different file
```

**What It Does When You Click:**
1. Click `✅ Use Data Hub Dataset`
2. Code calls `get_data_from_hub()` 
3. File loads from Data Hub cache
4. You see: `✅ **Data loaded from Hub!** 5000 rows, 35 columns`
5. Continue with validation (no upload needed!)

---

### Scenario 2: File NOT in Data Hub (Empty Hub)

**Code: Lines 7581-7587**

**What You'll See:**

```
⚡ Enhanced Transform Validation

#### 📁 Step 1: Data Source

💡 No data in Data Hub. Upload a file below or load data in the 📊 Data Hub tab first.

Upload a File:
Choose a file: [Upload]
```

**What's Happening in Code:**
```python
else:  # FALSE - No file in Hub
    st.info("💡 No data in Data Hub...")  # ← You see this message
    data_source = "upload"  # Set to use file upload instead
```

**What to Do:**
- Option 1: Upload file directly (shows file picker)
- Option 2: Go to `📊 Data Hub` tab and load file first

---

## Code Logic Breakdown - Step by Step

### Step 1: Import Functions (Lines 7556-7562)
```python
try:
    from ui_components.data_hub.integration import (
        get_data_from_hub,      # ← Gets the file from Hub
        has_data,               # ← Checks if file exists
        show_data_source_info   # ← Shows file info
    )
except ImportError:
    # If imports fail, set these to None (fallback)
    get_data_from_hub = None
    has_data = None
    show_data_source_info = None
```

### Step 2: Check for Data Hub File (Lines 7567-7580)
```python
if has_data and has_data():  # Check if file exists
    # FILE EXISTS IN HUB - Show this UI:
    st.success("📊 Data Hub has an active dataset available!")
    show_data_source_info()  # Display: Name, Rows, Columns
    
    # Show two buttons:
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("✅ Use Data Hub Dataset"):  # ← Option 1
            df_original = get_data_from_hub()
    with col2:
        if st.button("📤 Upload Different File"):  # ← Option 2
            data_source = "upload"
```

### Step 3: Handle No Data (Lines 7581-7587)
```python
else:  # NO FILE IN HUB
    st.info("💡 No data in Data Hub...")
    data_source = "upload"  # Force file upload
```

### Step 4: File Upload Fallback (Lines 7589-7620)
```python
if data_source == "upload" or df_original is None:
    # Show file uploader
    uploaded_file = st.file_uploader(
        "Choose a CSV, Excel, or PSV file",
        type=['csv', 'xlsx', 'xls', 'psv']
    )
    # ... load file
```

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────┐
│ User Opens Validation Tab                   │
└────────────┬────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────┐
│ Code checks: has_data() ?                   │
├─────────────────────────────────────────────┤
│ if 'data_hub' in st.session_state AND       │
│    data_hub.has_active_dataset()            │
└────┬────────────────────────────────────────┘
     │
     ├─── YES (File in Hub)
     │     ↓
     │  ┌───────────────────────────────────┐
     │  │ Show: "Data Hub has active data"  │
     │  │ Display: Name, Rows, Columns      │
     │  │ Buttons:                          │
     │  │  [✅ Use Hub Data]                │
     │  │  [📤 Upload Different]            │
     │  └───────────────────────────────────┘
     │     │ User clicks button
     │     ├─ "Use Hub Data" → Load from Hub
     │     └─ "Upload Different" → Show uploader
     │
     └─── NO (File NOT in Hub)
           ↓
        ┌───────────────────────────────────┐
        │ Show: "No data in Data Hub"       │
        │ Display: File uploader            │
        │ Button: [Upload]                  │
        └───────────────────────────────────┘
           │ User uploads file
           ↓
        Data loads from upload
```

---

## Where to Find the UI Option

### In Validation Tab:

```
📊 Enhanced Transform Validation (page title)
├─ Advanced data transformation validation... (subtitle)
│
├─ #### 📁 Step 1: Data Source  ← YOU ARE HERE
│  │
│  └─ [SECTION 1] If file in Hub:
│     ├─ ✅ 📊 Data Hub has an active dataset available!
│     ├─ 📊 Dataset: Account Data
│     ├─ 📦 Rows: 5000
│     ├─ 📋 Columns: 35
│     ├─ [✅ Use Data Hub Dataset]  ← CLICK THIS to use Hub file
│     └─ [📤 Upload Different File]  ← CLICK THIS to upload new
│
│  [SECTION 2] If Hub is empty:
│     ├─ 💡 No data in Data Hub...
│     └─ Choose a file: [Upload]  ← CLICK THIS to upload
│
├─ #### 🎯 Step 2: Select Target Salesforce Object
├─ #### 🔗 Step 3: Field Mapping Configuration
└─ ... more steps
```

---

## How to Check if Your File is There

### Method 1: Look at the UI (Easiest)

1. **Go to Validation tab**
2. **Look at Step 1: Data Source section**
3. If you see:
   - ✅ "Data Hub has an active dataset available!" → **File IS there**
   - 💡 "No data in Data Hub" → **File NOT there**

### Method 2: Check Data Hub Tab

1. **Go to Data Hub tab**
2. **Click "💾 Manage Datasets"**
3. **Look for your file with ⭐ icon** → **File IS there**

### Method 3: Check the Code (Advanced)

The code that checks is at [validation_operations.py](validation_operations.py#L7563):
```python
if has_data and has_data():  # If TRUE, file exists
    # Show the UI
```

---

## In Data Operations Tab (When Ready)

**Note:** Data Operations isn't integrated yet, but when it is, it will follow the same pattern:

```
Expected UI in Data Operations:

🔄 Data Operations

#### 📁 Step 1: Data Source

[SAME AS VALIDATION]
├─ ✅ Data Hub has an active dataset available! (if file uploaded)
├─ [✅ Use Data Hub Dataset]
├─ [📤 Upload Different File]
OR
├─ 💡 No data in Data Hub... (if hub empty)
└─ Choose a file: [Upload]

#### Step 2: Clean Data
#### Step 3: Transform Data
```

---

## Step-by-Step: Upload File and See the UI Option

### Step 1: Upload to Data Hub
```
1. Go to 📊 Data Hub tab
2. Click 📥 Load Data
3. Click 📄 Upload File
4. Upload your file
5. Name it (e.g., "Account Data")
6. Click ✅ Load into Hub
   ↓
   ✅ File now in Data Hub (cached)
```

### Step 2: Set as Active
```
7. Click 💾 Manage Datasets
8. Find your file
9. Click ⭐ Set as Active
   ↓
   ✅ File marked as "active"
```

### Step 3: Go to Validation and See the Option
```
10. Go to ✅ Enhanced Validation tab
    ↓
    YOU SEE:
    ┌─────────────────────────────────┐
    │ ✅ 📊 Data Hub has an active    │
    │    dataset available!           │
    │                                 │
    │ 📊 Dataset: Account Data        │
    │ 📦 Rows: 5000                   │
    │ 📋 Columns: 35                  │
    │                                 │
    │ [✅ Use Data Hub Dataset]   ← CLICK THIS!
    │ [📤 Upload Different File]      │
    └─────────────────────────────────┘

11. Click [✅ Use Data Hub Dataset]
    ↓
    ✅ File loads from Data Hub
    ✅ Continue with validation
    ✅ NO RE-UPLOAD NEEDED!
```

---

## Code Location Reference

| What | File | Lines | Code |
|------|------|-------|------|
| Check for file | validation_operations.py | 7563 | `if has_data and has_data():` |
| Show success message | validation_operations.py | 7564 | `st.success("📊 Data Hub has...")` |
| Show file info | validation_operations.py | 7567 | `show_data_source_info()` |
| Use Hub Data button | validation_operations.py | 7569-7572 | `if st.button("✅ Use Data Hub...")` |
| Upload Different button | validation_operations.py | 7573-7575 | `if st.button("📤 Upload...")` |
| No Hub message | validation_operations.py | 7581-7582 | `st.info("💡 No data in Data Hub...")` |

---

## What Each UI Element Does

### "✅ Use Data Hub Dataset" Button
```python
if st.button("✅ Use Data Hub Dataset"):
    df_original = get_data_from_hub()  # Gets file from cache
    data_source = "hub"  # Remember source
    if df_original is not None:
        st.success(f"✅ **Data loaded from Hub!** {rows} rows")
```

**Result:** File is loaded from Data Hub into Validation module

### "📤 Upload Different File" Button
```python
if st.button("📤 Upload Different File"):
    data_source = "upload"  # Switch to file uploader
```

**Result:** Shows file uploader to upload different file

### File Uploader (if Hub empty or user chooses upload)
```python
uploaded_file = st.file_uploader(
    "Choose a CSV, Excel, or PSV file",
    type=['csv', 'xlsx', 'xls', 'psv']
)
```

**Result:** User can upload file directly

---

## Summary

### To Check if File is Uploaded:

| Where | How | What You See |
|-------|-----|--------------|
| **Validation Tab** | Look at Step 1 | "Data Hub has active data" = YES<br>"No data in Data Hub" = NO |
| **Data Hub Tab** | Manage Datasets | ⭐ next to your file = YES |
| **Code** | Check `has_data()` | Returns True = YES, False = NO |

### To Use the Uploaded File:

| Location | Option | Action |
|----------|--------|--------|
| **Validation Tab** | Button 1 | Click `✅ Use Data Hub Dataset` |
| **Validation Tab** | Button 2 | Click `📤 Upload Different File` |
| **Validation Tab** | Fallback | Upload directly if Hub empty |

---

## Code Logic Summary

```
VALIDATION TAB OPENS
    ↓
CHECK: has_data() function
    ├─ Checks st.session_state.data_hub
    ├─ Checks if active_dataset_id is set
    └─ Returns True/False
    ↓
IF TRUE (File in Hub):
    │ Show: ✅ "Data Hub has active data"
    │ Show: Dataset info (name, rows, cols)
    │ Show: TWO BUTTONS
    │   ├─ ✅ Use Data Hub Dataset → Load from Hub
    │   └─ 📤 Upload Different File → Allow override
    ↓
IF FALSE (Hub empty):
    │ Show: 💡 "No data in Data Hub"
    │ Show: File uploader
    │ User: Upload file directly
    ↓
CONTINUE WITH VALIDATION
```

---

This is the exact UI logic I wrote. The "UI option" to use your uploaded file is the **"✅ Use Data Hub Dataset" button** that appears in Step 1 of the Validation tab when you have a file uploaded and set as active in Data Hub.

