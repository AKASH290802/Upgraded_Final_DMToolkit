# 📊 Data Hub Integration - Visual Architecture

**Date:** January 7, 2026
**Purpose:** Understanding how Data Hub integrates with other modules

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     STREAMLIT APPLICATION                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Session State (st.session_state)                                   │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  data_hub: DataHub                                         │    │
│  │  ├─ active_dataset_id: "uuid-123"                         │    │
│  │  ├─ cached_datasets:                                       │    │
│  │  │  ├─ "uuid-123": Account Data (5000 rows)               │    │
│  │  │  ├─ "uuid-456": Contact Data (1000 rows)               │    │
│  │  │  └─ "uuid-789": Opportunity Data (2500 rows)           │    │
│  │  └─ methods:                                              │    │
│  │     ├─ get_active_dataset()                               │    │
│  │     ├─ set_active_dataset()                               │    │
│  │     └─ add_dataset()                                      │    │
│  │                                                             │    │
│  └────────────────────────────────────────────────────────────┘    │
│              ↑ Shared across all tabs                               │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                          TAB NAVIGATION                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌────────────┐ │
│  │  📊 Data Hub        │  │ ✅ Enhanced         │  │  Other     │ │
│  │                     │  │    Validation       │  │  Modules   │ │
│  │ • Load Data         │  │                     │  │            │ │
│  │ • Manage Datasets   │  │ • Step 1: Data      │  │ • Data Ops │ │
│  │ • Active Dataset    │  │   Source            │  │ • Unit Test│ │
│  │                     │  │ • Step 2: Object    │  │ • Reports  │ │
│  │ (PRODUCER)          │  │ • Step 3: Mapping   │  │            │ │
│  │                     │  │ • Step 4: Validate  │  │ (CONSUMERS)│ │
│  │                     │  │                     │  │            │ │
│  │                     │  │ (CONSUMER)          │  │            │ │
│  └─────────────────────┘  └──────────────────────┘  └────────────┘ │
│         ↑                            ↑                      ↑        │
│         └────────────────────────────┴──────────────────────┘        │
│                 All access session_state.data_hub                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
USER ACTION IN DATA HUB
        ↓
┌──────────────────────────┐
│  Upload File             │
│  (CSV/Excel/PSV)         │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│  DataSourceHandler       │
│  .load_from_file()       │
│  ├─ Parse file           │
│  └─ Return DataFrame     │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│  DataHub.add_dataset()   │
│  ├─ Create UUID          │
│  ├─ Store metadata       │
│  ├─ Cache DataFrame      │
│  └─ Set as active        │
└────────┬─────────────────┘
         ↓
  Stored in Session State
         ↓
         ✅ Data is now available
         ↓
    USER ACTION IN VALIDATION
         ↓
┌──────────────────────────┐
│  Validation checks:      │
│  has_data()?             │
│  ├─ YES → Show Hub data  │
│  │  button               │
│  └─ NO → Show upload     │
│          prompt          │
└────────┬─────────────────┘
         ↓
    USER CLICKS BUTTON
         ↓
┌──────────────────────────┐
│  get_data_from_hub()     │
│  ├─ Gets active_dataset  │
│  │  _id                  │
│  ├─ Retrieves DataFrame  │
│  │  from cache           │
│  └─ Returns copy         │
└────────┬─────────────────┘
         ↓
  ✅ Data loaded in Validation
         ↓
    Continue with validation
```

---

## Integration Points

```
┌──────────────────────────────────────────────────────────────────┐
│              Module Integration Pattern                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Module Function:                                               │
│  def show_my_module(sf_conn):                                   │
│      │                                                           │
│      ├─ STEP 1: Import Integration Functions                   │
│      │  from ui_components.data_hub.integration import (       │
│      │      get_data_from_hub,                                 │
│      │      has_data,                                          │
│      │      show_data_source_info                              │
│      │  )                                                       │
│      │                                                          │
│      ├─ STEP 2: Check for Data                                │
│      │  if has_data():                                         │
│      │      show_data_source_info()                            │
│      │      df = get_data_from_hub()                           │
│      │                                                          │
│      ├─ STEP 3: Fallback Option                               │
│      │  else:                                                  │
│      │      uploaded_file = st.file_uploader(...)             │
│      │      df = load_from_file(uploaded_file)                │
│      │                                                          │
│      └─ STEP 4: Process Data                                  │
│         # Your module logic here                               │
│         process_data(df)                                        │
│                                                                  │
│  Result: Module now uses Data Hub! ✅                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## State Diagram: "Set as Active" Feature

```
┌─────────────────┐
│  No Data Hub    │  (Initial state)
│  loaded yet     │
└────────┬────────┘
         │ User uploads file to Data Hub
         ↓
┌─────────────────────────────────────┐
│  Data in Cache                      │
│  active_dataset_id = None           │
│  (Multiple datasets can exist)      │
└────────┬────────────────────────────┘
         │ User clicks "Set as Active"
         ↓
┌─────────────────────────────────────┐
│  Data in Cache + Marked Active      │
│  active_dataset_id = "uuid-123"     │
│  (Only ONE can be active at a time) │
└────────┬────────────────────────────┘
         │ User goes to Validation tab
         ↓
┌─────────────────────────────────────┐
│  Validation Reads from Data Hub     │
│  has_data() → TRUE                  │
│  Show "Use Data Hub Dataset" button  │
└────────┬────────────────────────────┘
         │ User clicks button
         ↓
┌─────────────────────────────────────┐
│  Data Loaded in Validation          │
│  df = get_data_from_hub()           │
│  Ready for validation               │
└─────────────────────────────────────┘
```

---

## Function Call Chain

```
Validation Module
    │
    ├─ import has_data
    │  │
    │  └─ Checks: st.session_state.data_hub.has_active_dataset()
    │     │
    │     └─ Returns: True/False
    │
    ├─ import show_data_source_info
    │  │
    │  └─ Gets: st.session_state.data_hub.get_active_dataset_info()
    │     │
    │     └─ Displays: Dataset name, rows, columns in UI
    │
    └─ import get_data_from_hub
       │
       └─ Calls: st.session_state.data_hub.get_active_dataset()
          │
          └─ Returns: Copy of DataFrame

Data Hub Core
    │
    ├─ DataHub class
    │  │
    │  ├─ add_dataset()
    │  │  ├─ Create UUID
    │  │  ├─ Store in cached_datasets
    │  │  └─ Set active_dataset_id
    │  │
    │  ├─ set_active_dataset(uuid)
    │  │  └─ Update active_dataset_id
    │  │
    │  ├─ get_active_dataset()
    │  │  └─ Return cached_datasets[active_dataset_id].df
    │  │
    │  └─ has_active_dataset()
    │     └─ Check if active_dataset_id exists and is valid
    │
    └─ Stored in: st.session_state.data_hub
```

---

## Before vs After Comparison

```
╔════════════════════════════════════════════════════════════════╗
║                    BEFORE FIX                                  ║
╠════════════════════════════════════════════════════════════════╣
║                                                                 ║
║  Data Hub Tab          Validation Tab                          ║
║  ┌──────────────┐      ┌──────────────┐                        ║
║  │ Upload File  │      │ Upload File  │                        ║
║  │ Set Active ✓ │      │   (required) │                        ║
║  └──────────────┘      └──────────────┘                        ║
║        │ Data            │ File                                 ║
║        ↓ stored          ↓ upload                               ║
║                                                                 ║
║  Problem: Data is isolated!                                    ║
║  - Set Active has no effect                                    ║
║  - Validation doesn't check Hub                                ║
║  - Users must re-upload                                        ║
║  - "Set Active" appears to be broken                           ║
║                                                                 ║
╚════════════════════════════════════════════════════════════════╝

                            ↓↓↓ FIX APPLIED ↓↓↓

╔════════════════════════════════════════════════════════════════╗
║                     AFTER FIX                                  ║
╠════════════════════════════════════════════════════════════════╣
║                                                                 ║
║  Data Hub Tab          Validation Tab                          ║
║  ┌──────────────┐      ┌───────────────────┐                   ║
║  │ Upload File  │      │ Check Hub ✓       │                   ║
║  │ Set Active ✓ │ ────→│ Show Hub Data ✓   │                   ║
║  └──────────────┘      │ Use/Override ✓    │                   ║
║        │ Data            └───────────────────┘                   ║
║        │ stored                  ↓                              ║
║        └──────────────────────────┘                             ║
║           Shared via session_state                              ║
║                                                                 ║
║  Solution: Data is integrated!                                 ║
║  ✓ Set Active has real effect                                  ║
║  ✓ Validation checks Hub first                                 ║
║  ✓ Users don't re-upload                                       ║
║  ✓ "Set Active" now works perfectly                            ║
║                                                                 ║
╚════════════════════════════════════════════════════════════════╝
```

---

## Module Interaction Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                    CURRENT ARCHITECTURE                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│                    📊 Data Hub                                 │
│                    ┌──────────────┐                            │
│                    │ Load Data    │                            │
│                    │ Manage Data  │                            │
│                    │ Set Active   │                            │
│                    └──────┬───────┘                            │
│                           │                                    │
│                           │ st.session_state                   │
│                           │ .data_hub                          │
│                           │                                    │
│         ┌─────────────────┼─────────────────┐                 │
│         │                 │                 │                 │
│         ↓                 ↓                 ↓                 │
│    ✅ Validation    🔄 Data Ops      📋 Other                 │
│    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│    │ Check Hub ✓  │ │ Check Hub    │ │ Check Hub    │        │
│    │ Use Data ✓   │ │ (when ready) │ │ (when ready) │        │
│    │ Or Upload    │ │              │ │              │        │
│    └──────────────┘ └──────────────┘ └──────────────┘        │
│         ↑                 ↑                 ↑                 │
│         └─────────────────┼─────────────────┘                 │
│                           │                                    │
│                    All use integration helpers               │
│                    (has_data, get_data_from_hub, etc.)        │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Legend:
  ✓ = Already integrated
  (when ready) = Ready for same integration pattern
```

---

## Session State Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ STREAMLIT SESSION STARTS                                    │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ streamlit_app.py initialization                             │
│                                                             │
│ if 'data_hub' not in st.session_state:                      │
│     st.session_state.data_hub = DataHub()                   │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ DataHub instance created:                                   │
│   - active_dataset_id = None                                │
│   - cached_datasets = {}                                    │
│   - creation_time = now                                     │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ USER NAVIGATES TO DATA HUB TAB                              │
│ User uploads file                                           │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ data_hub.add_dataset(df, "Account Data", ...)               │
│   - Generate UUID: "abc-123"                                │
│   - Store in cached_datasets["abc-123"]                     │
│   - Set active_dataset_id = "abc-123"                       │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ st.session_state.data_hub now contains:                     │
│   - active_dataset_id = "abc-123"                           │
│   - cached_datasets = {                                     │
│       "abc-123": {name, df, metadata}                       │
│     }                                                       │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ USER NAVIGATES TO VALIDATION TAB                            │
│ Validation calls: has_data()                                │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ has_data() checks:                                          │
│   if 'data_hub' in st.session_state:  ✓ YES                │
│       data_hub.has_active_dataset()   ✓ YES                │
│ Returns: True                                               │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ Validation shows:                                           │
│   "📊 Data Hub has an active dataset available!"            │
│   [✅ Use Data Hub Dataset] [📤 Upload Different File]      │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ USER CLICKS "✅ Use Data Hub Dataset"                       │
│ get_data_from_hub() called                                  │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ get_data_from_hub():                                        │
│   - Gets active_dataset_id = "abc-123"                      │
│   - Gets cached_datasets["abc-123"]["df"]                   │
│   - Returns copy of DataFrame                               │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ DATA LOADED IN VALIDATION ✅                                │
│ Ready for validation processing                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

**Key Points:**

1. **Session State is Shared:** Data stored in `st.session_state.data_hub` is accessible from ALL tabs

2. **Hub is Producer:** Data Hub loads and caches data, sets which one is "active"

3. **Modules are Consumers:** Validation and other modules call integration functions to retrieve active data

4. **Integration is Simple:** 6 helper functions handle all the complexity

5. **Flow is One-Way:** Hub → All Modules (hub is source of truth)

6. **Fallback Available:** File upload still works if Hub is empty

7. **Override Possible:** Users can always upload different file

