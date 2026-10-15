# Operation Tracking System - Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DM TOOLKIT APPLICATION                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │   Load Data      │  │ Business Rules   │  │  Data Quality    │     │
│  │   • File Upload  │  │  • Validate BR   │  │  • Check Quality │     │
│  │   • SOQL Query   │  │  • Track Result  │  │  • Track Result  │     │
│  │   • Data Load    │  │                  │  │                  │     │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘     │
│           │                     │                     │                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │  Org Migration   │  │ Lookup Resolution│  │  Data Hub        │     │
│  │  • Execute Mig   │  │  • Resolve Refs  │  │  (Central Hub)   │     │
│  │  • Track Result  │  │  • Track Result  │  │                  │     │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘     │
│           │                     │                     │                │
│           └─────────────────────┼─────────────────────┘                │
│                                 │                                      │
│                    ┌────────────────────┐                              │
│                    │ Operation Tracker  │                              │
│                    │ (Integration API)  │                              │
│                    │                    │                              │
│                    │ track_file_upload()│                              │
│                    │ track_soql_query() │                              │
│                    │ track_data_load()  │                              │
│                    │ track_validation_  │ ← NEW                        │
│                    │   check()          │                              │
│                    │ track_migration_   │ ← NEW                        │
│                    │   execution()      │                              │
│                    │ track_lookup_      │ ← NEW                        │
│                    │   resolution()     │                              │
│                    └──────────┬─────────┘                              │
│                               │                                        │
│                    ┌────────────────────┐                              │
│                    │ Operation Manager  │                              │
│                    │ (Persistence Layer)│                              │
│                    │                    │                              │
│                    │ create_operation() │                              │
│                    │ get_operation_     │                              │
│                    │   history()        │                              │
│                    │ retrieve_operation │                              │
│                    │   _data()          │                              │
│                    │ delete_operation() │                              │
│                    │ export_operations()│                              │
│                    └──────────┬─────────┘                              │
│                               │                                        │
│        ┌──────────────────────┼──────────────────────┐                │
│        │                      │                      │                │
│   ┌────▼──────┐      ┌────────▼────┐       ┌────────▼────┐            │
│   │  Async    │      │   JSON      │       │    CSV      │            │
│   │ Processor │      │  Manifest   │       │    Data     │            │
│   │           │      │             │       │             │            │
│   │ Multi-Org │      │ Metadata    │       │ Operation   │            │
│   │ Parallel  │      │ Storage     │       │ Data        │            │
│   └─────┬─────┘      └────────┬────┘       └────────┬────┘            │
│         │                     │                     │                 │
│         │                     └─────────────────────┘                 │
│         │                  DataFiles/operation_history/              │
│         └──────────────────────┬──────────────────────┘               │
│                                │                                      │
│                    ┌───────────────────┐                              │
│                    │ Data Hub UI Tab 4 │                              │
│                    │Operation History  │                              │
│                    │                   │                              │
│                    │ • Statistics      │                              │
│                    │ • Filters         │                              │
│                    │ • Table View      │                              │
│                    │ • Export/Delete   │                              │
│                    └───────────────────┘                              │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER ACTION                              │
│        (Upload File, Run Validation, Execute Migration, etc.)      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Validation &  │
                    │  Processing    │
                    │  (Tab Logic)   │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────────┐
                    │  track_*() call    │
                    │  (operation_tracker)
                    └────────┬───────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
  ┌────────────┐   ┌─────────────────┐   ┌──────────────┐
  │ Prepare    │   │ Extract         │   │ Call          │
  │ DataFrame  │   │ Metadata        │   │ operation_    │
  │            │   │ (timestamps,    │   │ manager.      │
  │ • Filter   │   │  users, etc.)   │   │ create_       │
  │ • Validate │   │                 │   │ operation()   │
  │            │   │ • org name(s)   │   │              │
  │            │   │ • object name   │   │ Pass:        │
  │            │   │ • pass/fail #s  │   │ • operation_ │
  │            │   │ • timestamp     │   │   type       │
  │            │   │ • user          │   │ • metadata   │
  │            │   │ • details       │   │ • dataframe  │
  │            │   │                 │   │              │
  └────────────┘   └─────────────────┘   └──────┬───────┘
         │                │                      │
         └────────────────┴──────────────────────┘
                          │
                          ▼
            ┌──────────────────────────┐
            │ operation_manager.create │
            │     _operation()         │
            │                          │
            │ • Generate operation_id  │
            │ • Timestamp operation    │
            │ • Add user info          │
            │ • Serialize data to CSV  │
            │ • Add to manifest.json   │
            └──────────┬───────────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
         ▼                            ▼
    ┌──────────────┐        ┌────────────────────┐
    │   manifest   │        │  {operation_id}.csv │
    │    .json     │        │  (Operation Data)   │
    │              │        │                    │
    │ [operation1] │        │ Columns:           │
    │ [operation2] │        │ • Field 1, Field 2 │
    │ [operation3] │        │ • Record data      │
    │ ... stored   │        │ • Searchable       │
    │              │        │ • Downloadable     │
    └──────────────┘        └────────────────────┘
         │                            │
         └─────────────┬──────────────┘
                       │
        DataFiles/operation_history/
                       │
                       ▼
         ┌──────────────────────────┐
         │  Return operation_id to  │
         │  calling function        │
         │                          │
         │ Success! Operation       │
         │ recorded                 │
         └──────────────┬───────────┘
                        │
                        ▼
         ┌──────────────────────────┐
         │ Operation History UI     │
         │ automatically updates    │
         │                          │
         │ User sees new operation  │
         │ in Data Hub → Tab 4      │
         │                          │
         │ Filters available:       │
         │ • Org / Object / Type    │
         │ • Status / Date          │
         │ • Export / Delete        │
         └──────────────────────────┘
```

---

## Component Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPERATION TRACKING SYSTEM                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  data_hub_ui.py (Tab 4: Operation History)              │  │
│  │  ✓ Filter UI                                             │  │
│  │  ✓ Table display                                         │  │
│  │  ✓ Export/delete buttons                                │  │
│  │  ✓ Statistics dashboard                                 │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │ imports                                    │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │  operation_manager.py                                    │  │
│  │  ✓ create_operation()                                    │  │
│  │  ✓ get_operation_history()                               │  │
│  │  ✓ retrieve_operation_data()                             │  │
│  │  ✓ delete_operation()                                    │  │
│  │  ✓ get_unique_objects_for_org()                          │  │
│  │  ✓ File I/O (JSON/CSV)                                   │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │ imports                                    │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │  operation_tracker.py                                    │  │
│  │                                                           │  │
│  │  Integration functions:                                  │  │
│  │  ✓ track_file_upload()                                   │  │
│  │  ✓ track_soql_query()                                    │  │
│  │  ✓ track_data_load()                                     │  │
│  │  ✓ track_validation_check()      ← NEW                   │  │
│  │  ✓ track_migration_execution()   ← NEW                   │  │
│  │  ✓ track_lookup_resolution()     ← NEW                   │  │
│  │                                                           │  │
│  │  Helper functions:                                       │  │
│  │  ✓ get_last_operation_data()                             │  │
│  │  ✓ display_operation_summary()                           │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │ imports                                    │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │  async_processor.py                                      │  │
│  │  ✓ fetch_multiple_orgs()                                 │  │
│  │  ✓ load_to_multiple_orgs()                               │  │
│  │  ✓ Parallel execution                                    │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │ uses                                       │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │  Python Standard Library                                 │  │
│  │  ✓ asyncio (parallel processing)                         │  │
│  │  ✓ json (metadata storage)                               │  │
│  │  ✓ pandas (data handling)                                │  │
│  │  ✓ datetime (timestamps)                                 │  │
│  │  ✓ uuid (operation IDs)                                  │  │
│  │  ✓ logging (error tracking)                              │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │ reads/writes                                │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │  File System                                             │  │
│  │  DataFiles/operation_history/                            │  │
│  │  ├── manifest.json      (Operation metadata)             │  │
│  │  └── data/                                               │  │
│  │      ├── op_001.csv     (Operation data)                 │  │
│  │      ├── op_002.csv                                      │  │
│  │      └── ...                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Legend:
→ imports = Direct Python imports
→ uses = Functional dependency
→ reads/writes = File I/O
```

---

## Integration Points

```
┌──────────────────────────────────────────────────────────────────┐
│                    TAB INTEGRATION POINTS                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Tab: Load Data ✅ ALREADY INTEGRATED                      │ │
│  │ Location: ui_components/org_migration.py                  │ │
│  │                                                            │ │
│  │ Operations tracked:                                        │ │
│  │ • File uploads → track_file_upload()                      │ │
│  │ • SOQL queries → track_soql_query()                       │ │
│  │ • Data loads   → track_data_load()                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Tab: Business Rules ⏳ READY FOR INTEGRATION              │ │
│  │ Location: ui_components/org_migration.py                  │ │
│  │                                                            │ │
│  │ To integrate, add this AFTER validation:                  │ │
│  │ from ui_components.data_hub.operation_tracker import \    │ │
│  │   track_validation_check                                  │ │
│  │                                                            │ │
│  │ operation_id = track_validation_check(                    │ │
│  │     data=df,                                              │ │
│  │     object_name=selected_object,                          │ │
│  │     source_org=selected_org,                              │ │
│  │     validation_type="Business_Rules",                     │ │
│  │     total_records=total_count,                            │ │
│  │     passed_records=passed_count,                          │ │
│  │     failed_records=failed_count                           │ │
│  │ )                                                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Tab: Data Quality ⏳ READY FOR INTEGRATION                │ │
│  │ Location: ui_components/org_migration.py                  │ │
│  │                                                            │ │
│  │ To integrate, add this AFTER quality check:               │ │
│  │ from ui_components.data_hub.operation_tracker import \    │ │
│  │   track_validation_check                                  │ │
│  │                                                            │ │
│  │ operation_id = track_validation_check(                    │ │
│  │     data=df,                                              │ │
│  │     object_name=selected_object,                          │ │
│  │     source_org=selected_org,                              │ │
│  │     validation_type="Data_Quality",    ← Changed           │ │
│  │     total_records=total_count,                            │ │
│  │     passed_records=passed_count,                          │ │
│  │     failed_records=failed_count                           │ │
│  │ )                                                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Tab: Org Migration Execute ⏳ READY FOR INTEGRATION       │ │
│  │ Location: ui_components/org_migration.py                  │ │
│  │                                                            │ │
│  │ To integrate, add this AFTER migration:                   │ │
│  │ from ui_components.data_hub.operation_tracker import \    │ │
│  │   track_migration_execution                               │ │
│  │                                                            │ │
│  │ operation_id = track_migration_execution(                 │ │
│  │     source_org=source_org,                                │ │
│  │     target_org=target_org,                                │ │
│  │     object_name=object_name,                              │ │
│  │     total_records=total_count,                            │ │
│  │     successful_records=success_count,                     │ │
│  │     failed_records=fail_count                             │ │
│  │ )                                                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Tab: Lookup Resolution ⏳ READY FOR INTEGRATION           │ │
│  │ Location: ui_components/org_migration.py                  │ │
│  │                                                            │ │
│  │ To integrate, add this AFTER lookup resolution:           │ │
│  │ from ui_components.data_hub.operation_tracker import \    │ │
│  │   track_lookup_resolution                                 │ │
│  │                                                            │ │
│  │ operation_id = track_lookup_resolution(                   │ │
│  │     source_org=source_org,                                │ │
│  │     target_org=target_org,                                │ │
│  │     object_name=object_name,                              │ │
│  │     total_lookups=total_count,                            │ │
│  │     resolved_lookups=resolved_count,                      │ │
│  │     unresolved_lookups=unresolved_count                   │ │
│  │ )                                                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Tab: Data Hub ✅ ALREADY INTEGRATED                        │ │
│  │ Location: ui_components/data_hub/data_hub_ui.py           │ │
│  │                                                            │ │
│  │ Tab 4: Operation History                                   │ │
│  │ • Shows all 8 operation types                              │ │
│  │ • Cascading filters (org → object)                         │ │
│  │ • Statistics dashboard                                     │ │
│  │ • Export/download/delete                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

Legend:
✅ ALREADY INTEGRATED = Tracking calls already in place
⏳ READY FOR INTEGRATION = Functions available, need to add calls
```

---

## Data Flow: From Operation to History

```
User Action
    │
    ├─ File Upload
    │  │
    │  └─→ track_file_upload()
    │      │
    │      └─→ Create operation object
    │          │
    │          ├─ operation_id: UUID
    │          ├─ operation_type: "File_Upload"
    │          ├─ timestamp: ISO 8601
    │          ├─ source_org: "HeraQA"
    │          ├─ target_org: "TestDev"
    │          ├─ object_name: "Account"
    │          ├─ record_count: 100
    │          ├─ validation_status: "PASSED"
    │          ├─ validation_passed: 100
    │          ├─ validation_failed: 0
    │          └─ created_by: "user@example.com"
    │
    ├─ SOQL Query
    │  │
    │  └─→ track_soql_query()
    │      │
    │      └─→ Create operation object
    │          │
    │          ├─ operation_type: "SOQL_Query"
    │          ├─ query: "SELECT Id, Name FROM Account"
    │          ├─ source_org: "HeraQA"
    │          └─ ... (metadata)
    │
    ├─ Data Load
    │  │
    │  └─→ track_data_load()
    │      │
    │      └─→ Create operation object
    │          │
    │          ├─ operation_type: "Data_Load"
    │          ├─ target_org: "TestDev"
    │          └─ ... (metadata)
    │
    ├─ Business Rules Validation [NEW]
    │  │
    │  └─→ track_validation_check(..., validation_type="Business_Rules")
    │      │
    │      └─→ Create operation object
    │          │
    │          ├─ operation_type: "Validation_Check_Business_Rules"
    │          ├─ validation_details: {...}
    │          └─ ... (metadata)
    │
    ├─ Data Quality Check [NEW]
    │  │
    │  └─→ track_validation_check(..., validation_type="Data_Quality")
    │      │
    │      └─→ Create operation object
    │          │
    │          ├─ operation_type: "Validation_Check_Data_Quality"
    │          ├─ validation_details: {...}
    │          └─ ... (metadata)
    │
    ├─ Migration [NEW]
    │  │
    │  └─→ track_migration_execution()
    │      │
    │      └─→ Create operation object
    │          │
    │          ├─ operation_type: "Migration_Execute"
    │          ├─ source_org: "HeraQA"
    │          ├─ target_org: "TestDev"
    │          └─ ... (metadata)
    │
    └─ Lookup Resolution [NEW]
       │
       └─→ track_lookup_resolution()
           │
           └─→ Create operation object
               │
               ├─ operation_type: "Lookup_Resolution"
               ├─ resolved_lookups: 98
               ├─ unresolved_lookups: 2
               └─ ... (metadata)

ALL operations flow to:
    │
    └─→ operation_manager.create_operation()
        │
        ├─→ Serialize operation metadata
        │
        ├─→ Save to manifest.json
        │   (Fast metadata queries)
        │
        ├─→ Save operation data to {operation_id}.csv
        │   (Downloadable data)
        │
        └─→ Return operation_id
            │
            └─→ Operation History UI automatically updates
                │
                ├─ Statistics recalculated
                ├─ Table refreshed
                ├─ Filters updated
                └─ User sees new operation in Tab 4
```

---

## Cascading Filter Logic

```
┌──────────────────────────────────────────────────────┐
│  Operation History UI - Filter Workflow              │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Step 1: Load All Orgs                              │
│  ┌────────────────────────────────────────────┐     │
│  │ Org Dropdown shows:                        │     │
│  │ • "All" (default)                          │     │
│  │ • "HeraQA" (has operations)                │     │
│  │ • "TestDev" (has operations)               │     │
│  │ • "deployement" (has operations)           │     │
│  │ • ... others with operations               │     │
│  │                                            │     │
│  │ User selects: "HeraQA"                     │     │
│  └────────────────────────────────────────────┘     │
│           │                                          │
│           ▼                                          │
│  Step 2: Filter Objects by Selected Org             │
│  ┌────────────────────────────────────────────┐     │
│  │ If "All" selected:                         │     │
│  │   Show ALL objects from ALL operations     │     │
│  │                                            │     │
│  │ If "HeraQA" selected:                      │     │
│  │   Show ONLY objects from HeraQA            │     │
│  │   • "All"                                  │     │
│  │   • "Account"                              │     │
│  │   • "WOD_2__Warranty_Code__c"              │     │
│  │   • ... others that appear in HeraQA       │     │
│  │                                            │     │
│  │ User selects: "Account"                    │     │
│  └────────────────────────────────────────────┘     │
│           │                                          │
│           ▼                                          │
│  Step 3: Filter by Operation Type                   │
│  ┌────────────────────────────────────────────┐     │
│  │ Show ALL operation types:                  │     │
│  │ • "All"                                    │     │
│  │ • "SOQL_Query"                             │     │
│  │ • "File_Upload"                            │     │
│  │ • "Data_Load"                              │     │
│  │ • "Validation_Check_Business_Rules"        │     │
│  │ • "Validation_Check_Data_Quality"          │     │
│  │ • "Migration_Execute"                      │     │
│  │ • "Lookup_Resolution"                      │     │
│  │                                            │     │
│  │ User selects: "Data_Load"                  │     │
│  └────────────────────────────────────────────┘     │
│           │                                          │
│           ▼                                          │
│  Step 4: Filter by Status                           │
│  ┌────────────────────────────────────────────┐     │
│  │ • "All" (default)                          │     │
│  │ • "PASSED" (validation passed)              │     │
│  │ • "FAILED" (validation failed)              │     │
│  │ • "PARTIAL" (some passed/some failed)       │     │
│  │                                            │     │
│  │ User selects: "PASSED"                     │     │
│  └────────────────────────────────────────────┘     │
│           │                                          │
│           ▼                                          │
│  Step 5: Filter by Date Range                       │
│  ┌────────────────────────────────────────────┐     │
│  │ From: 2024-01-01                           │     │
│  │ To: 2024-12-31                             │     │
│  │                                            │     │
│  │ Filter applied                             │     │
│  └────────────────────────────────────────────┘     │
│           │                                          │
│           ▼                                          │
│  FINAL RESULT                                       │
│  ┌────────────────────────────────────────────┐     │
│  │ Table shows:                               │     │
│  │ • HeraQA org                               │     │
│  │ • Account object                           │     │
│  │ • Data_Load operations only                │     │
│  │ • PASSED status only                       │     │
│  │ • 2024 dates only                          │     │
│  │                                            │     │
│  │ Statistics updated:                        │     │
│  │ • 25 total operations (matching filters)   │     │
│  │ • 25 successful (100%)                     │     │
│  │ • 0 failed                                 │     │
│  └────────────────────────────────────────────┘     │
│                                                      │
│  Auto-Reset Logic:                                  │
│  If user changes Org dropdown:                      │
│    → Object filter auto-resets to "All"             │
│  Why? Objects are different for each org,           │
│       so previous selection might be invalid        │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

**This diagram shows the complete architecture, data flow, component dependencies, integration points, and filter logic of the Operation Tracking System.**

