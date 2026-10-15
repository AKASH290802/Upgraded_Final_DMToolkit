# 📺 Visual UI Guide - Where the Option Appears

**Date:** January 7, 2026
**Purpose:** Show EXACTLY what you'll see in the UI when a file is uploaded

---

## The Exact UI You'll See in Validation Tab

### Scenario A: FILE IS UPLOADED TO DATA HUB ✅

**What appears on screen:**

```
┌────────────────────────────────────────────────────────────┐
│ ⚡ Enhanced Transform Validation                           │
│ Advanced data transformation validation with success/     │
│ failure categorization, lookup validation, and...         │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ #### 📁 Step 1: Data Source                               │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ✅ 📊 Data Hub has an active dataset available!           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │                                                      │ │
│  │  📊 Dataset         Account Data                    │ │
│  │  📦 Rows            5000                            │ │
│  │  📋 Columns         35                              │ │
│  │                                                      │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────┬──────────────────────────────┐  │
│  │                      │                              │  │
│  │ ✅ Use Data Hub      │  📤 Upload Different       │  │
│  │    Dataset           │     File                    │  │
│  │                      │                              │  │
│  └──────────────────────┴──────────────────────────────┘  │
│                                                             │
│                                                             │
└────────────────────────────────────────────────────────────┘

[After clicking "✅ Use Data Hub Dataset"]

┌────────────────────────────────────────────────────────────┐
│                                                             │
│  ✅ **Data loaded from Hub!** 5000 rows, 35 columns       │
│                                                             │
│  📊 Data Preview                                          │  ← You can expand this
│                                                             │
│                                                             │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ #### 🎯 Step 2: Select Target Salesforce Object           │
├────────────────────────────────────────────────────────────┤
│ [Continue with validation...]                             │
└────────────────────────────────────────────────────────────┘
```

---

### Scenario B: FILE NOT IN DATA HUB ❌

**What appears on screen:**

```
┌────────────────────────────────────────────────────────────┐
│ ⚡ Enhanced Transform Validation                           │
│ Advanced data transformation validation with success/     │
│ failure categorization, lookup validation, and...         │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ #### 📁 Step 1: Data Source                               │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  💡 No data in Data Hub. Upload a file below or load      │
│     data in the 📊 Data Hub tab first.                    │
│                                                             │
│  Upload a File:                                            │
│                                                             │
│  Choose a file: [Upload]                                  │
│                                                             │
│  ⓘ Upload the data you want to validate and transform.   │
│    Supported formats: CSV, Excel, PSV...                  │
│                                                             │
│                                                             │
└────────────────────────────────────────────────────────────┘

[After selecting file in uploader]

┌────────────────────────────────────────────────────────────┐
│                                                             │
│  ✅ **Data loaded successfully!** 5000 rows, 35 columns   │
│                                                             │
│  📊 Data Preview                                          │  ← You can expand this
│                                                             │
│                                                             │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ #### 🎯 Step 2: Select Target Salesforce Object           │
├────────────────────────────────────────────────────────────┤
│ [Continue with validation...]                             │
└────────────────────────────────────────────────────────────┘
```

---

## The Two Paths

```
┌─────────────────────────────────────┐
│  Open Validation Tab                │
└────────────┬────────────────────────┘
             │
             ↓
    ┌────────────────────┐
    │ Check: Is file     │
    │ in Data Hub?       │
    └────┬───────────────┘
         │
    ┌────┴─────────┐
    │              │
   YES            NO
    │              │
    ↓              ↓
┌──────────┐   ┌──────────────┐
│ PATH A   │   │ PATH B       │
│ SHOWS:   │   │ SHOWS:       │
│          │   │              │
│ ✅ Data  │   │ 💡 No data   │
│ Hub has  │   │ in Data Hub  │
│ active   │   │              │
│ dataset  │   │ Choose file: │
│          │   │ [Upload]     │
│ [✅ Use  │   │              │
│  Data    │   │ [Select file]│
│  Hub]    │   │              │
│ [📤 Upl  │   └──────────────┘
│  Diff]   │        │
│          │        ↓
│          │    [File loads]
│          │        │
│          │        ↓
│  [Click  │    [Continue]
│   button]│
│    │     │
└────┼─────┘
     │
     ↓
  [Data loads from appropriate source]
     ↓
  #### Step 2: Object Selection
     ↓
  [Continue validation...]
```

---

## Key Points - Where Is the Option?

### Location 1: In Validation Tab

**Section:** `#### 📁 Step 1: Data Source`

**Button Name:** `✅ Use Data Hub Dataset`

**When It Appears:** Only when you have a file uploaded AND set as active in Data Hub

**What It Does:** Loads the file from Data Hub cache (no upload needed)

### Location 2: In Validation Tab (Override)

**Section:** `#### 📁 Step 1: Data Source`

**Button Name:** `📤 Upload Different File`

**When It Appears:** Only when you have a file in Data Hub (lets you override)

**What It Does:** Allows you to upload a different file instead of using Hub data

### Location 3: In Validation Tab (Fallback)

**Section:** `#### 📁 Step 1: Data Source`

**File Uploader:** `Choose a file: [Upload]`

**When It Appears:** When Hub is empty OR user clicked "Upload Different File"

**What It Does:** Lets you upload file directly

---

## The Three Options Explained

### Option 1: "✅ Use Data Hub Dataset" ← This is what you asked about!

```python
# Code location: validation_operations.py, line 7569-7572
if st.button("✅ Use Data Hub Dataset", use_container_width=True):
    df_original = get_data_from_hub()  # Gets file from Hub
    data_source = "hub"
    if df_original is not None:
        st.success(f"✅ **Data loaded from Hub!** {len(df_original)} rows...")
```

**When you see it:** After uploading file to Data Hub and setting as active

**What you'll see on UI:**
```
┌────────────────────────────────┐
│ [✅ Use Data Hub Dataset]      │ ← Click this button
└────────────────────────────────┘
```

**Result:** File loads instantly from Data Hub

---

### Option 2: "📤 Upload Different File"

```python
# Code location: validation_operations.py, line 7573-7575
if st.button("📤 Upload Different File", use_container_width=True):
    data_source = "upload"  # Switch to file uploader mode
```

**When you see it:** Same time as Option 1 (when Hub has data)

**What you'll see on UI:**
```
┌────────────────────────────────┐
│ [📤 Upload Different File]     │ ← Click to override
└────────────────────────────────┘
```

**Result:** Shows file uploader for different file

---

### Option 3: "Choose a file: [Upload]" (File Uploader)

```python
# Code location: validation_operations.py, line 7598-7603
uploaded_file = st.file_uploader(
    "Choose a CSV, Excel, or PSV file",
    type=['csv', 'xlsx', 'xls', 'psv']
)
```

**When you see it:** When Hub is empty OR user chose "Upload Different File"

**What you'll see on UI:**
```
┌─────────────────────────────────┐
│ Choose a file: [Upload]         │ ← Click to select
└─────────────────────────────────┘
```

**Result:** Opens file browser to upload

---

## How to Verify Each Scenario

### Check if File is in Hub:

1. **Open Validation tab**
2. **Look at Step 1: Data Source**
3. **You see:**
   - Option 1 (✅ Use Data Hub Dataset) = **File IS in Hub** ✅
   - Option 3 (Choose a file: [Upload]) = **File NOT in Hub** ❌

---

## Code Logic Visualization

```
WHEN VALIDATION TAB OPENS:

Line 7563: if has_data and has_data():
           ├─ TRUE:  Show [Option 1: Use Hub] + [Option 2: Upload Diff]
           └─ FALSE: Show [Option 3: File uploader]

WHEN USER CLICKS [Option 1: Use Hub]:
Line 7571:  df_original = get_data_from_hub()
           ├─ Gets file from cache
           ├─ Shows: "✅ Data loaded from Hub!"
           └─ Continue to Step 2

WHEN USER CLICKS [Option 2: Upload Diff]:
Line 7575:  data_source = "upload"
           └─ Shows [Option 3: File uploader]

WHEN USER USES [Option 3: File uploader]:
Line 7598:  uploaded_file = st.file_uploader(...)
           ├─ Loads file from user
           ├─ Shows: "✅ Data loaded successfully!"
           └─ Continue to Step 2
```

---

## Summary - Where Is The Option?

| Question | Answer |
|----------|--------|
| **Where is the option?** | In the **Validation Tab**, under **Step 1: Data Source** |
| **What button do I click?** | **✅ Use Data Hub Dataset** |
| **When does it appear?** | After you upload file to Data Hub and set as active |
| **What does it do?** | Loads your uploaded file from Data Hub cache |
| **Is there an alternative?** | Yes - **📤 Upload Different File** to override |
| **What if Hub is empty?** | Shows **Choose a file: [Upload]** instead |

---

## Real Example - Step by Step

### Step 1: Upload file to Data Hub
```
📊 Data Hub tab → 📥 Load Data → 📄 Upload File
   → Upload "Account.csv"
   → Name it "Account Data"
   → Click ✅ Load into Hub
   ↓ File is now in Data Hub
```

### Step 2: Set as Active
```
📊 Data Hub tab → 💾 Manage Datasets
   → Find "Account Data"
   → Click ⭐ Set as Active
   ↓ File marked as "active"
```

### Step 3: Open Validation
```
✅ Enhanced Validation tab
   ↓ YOU SEE:
   
   #### 📁 Step 1: Data Source
   
   ✅ 📊 Data Hub has an active dataset available!
   
   📊 Dataset: Account Data
   📦 Rows: 5000
   📋 Columns: 35
   
   [✅ Use Data Hub Dataset]  ← THIS IS THE OPTION!
   [📤 Upload Different File]
```

### Step 4: Click the button
```
Click: [✅ Use Data Hub Dataset]
   ↓ YOU SEE:
   
   ✅ **Data loaded from Hub!** 5000 rows, 35 columns
   
   📊 Data Preview [Click to expand]
   
   #### 🎯 Step 2: Select Target Salesforce Object
   [Continue with validation...]
```

---

## For Data Operations Tab (Future)

When Data Operations is integrated, you'll see the exact same UI:

```
🔄 Data Operations

#### 📁 Step 1: Data Source

[IDENTICAL TO VALIDATION]
├─ ✅ 📊 Data Hub has an active dataset available!
├─ 📊 Dataset: Account Data
├─ 📦 Rows: 5000
├─ 📋 Columns: 35
├─ [✅ Use Data Hub Dataset]  ← SAME OPTION
└─ [📤 Upload Different File]
```

---

## Answer to Your Question

**"If I upload a file in Data Hub, where in the UI is the option to use it?"**

✅ **Answer:**

**Location:** `✅ Enhanced Validation` tab → `Step 1: Data Source` section

**Option:** `[✅ Use Data Hub Dataset]` button

**When:** Appears automatically when you have file uploaded + set active in Data Hub

**Result:** Click button → File loads instantly from Data Hub → Continue validation

**No re-upload needed!** ✅

