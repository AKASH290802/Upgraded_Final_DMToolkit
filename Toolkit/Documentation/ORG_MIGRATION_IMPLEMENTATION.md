# 🔄 Org Migration Feature - Complete Implementation Documentation

## 📋 Overview

The Org Migration feature enables seamless data migration between two Salesforce organizations with intelligent parent-child relationship resolution and duplicate detection.

---

## 🎯 Core Requirements Addressed

### **Requirement 1: Parent-Child Relationship Handling**
**Problem**: When migrating child records, they reference parent records via Salesforce IDs. Source org IDs don't exist in target org.

**Solution**: Query TARGET org to find matching parent records using:
- External ID fields
- Unique fields
- Combination of fields (AND condition)
- Concatenation of fields

**Example**:
```
Source Org Contact:
- Name: "John Doe"
- AccountId: "001SOURCE123" (Source org Account ID)
- Account.External_ID__c: "ACC_12345"

Migration Process:
1. Query TARGET org: SELECT Id FROM Account WHERE External_ID__c = 'ACC_12345'
2. Get TARGET org Account ID: "001TARGET789"
3. Create Contact in TARGET with AccountId = "001TARGET789"
```

---

### **Requirement 2: Handling Records Created in UI vs File**
**Problem**: 
- Records loaded via file → Have External ID
- Records created in Salesforce UI → May NOT have External ID

**Solution**: Use flexible matching strategies:
1. **External ID** (if available)
2. **Unique Field** (like Email, Phone)
3. **Field Combination** (FirstName + LastName + DOB)
4. **Field Concatenation** (AccountNumber_Year_Region)

**Example Scenario**:
```
Target Org already has:
- Account created via UI: Name="Acme Corp", Industry="Technology", BillingCountry="USA"
  (No External ID because created manually)

Source Org has:
- Account: Name="Acme Corp", Industry="Technology", BillingCountry="USA"

Matching Strategy: Field Combination [Name, Industry, BillingCountry]
Query: SELECT Id FROM Account WHERE Name='Acme Corp' AND Industry='Technology' AND BillingCountry='USA'
Result: Found existing record → Use UPDATE or UPSERT instead of INSERT
```

---

### **Requirement 3: Notify User About Existing Records**
**Implementation**: 
- **Tab 3**: Configure matching strategy for main object
- **Tab 4**: "Check Existing Records" button validates before migration
- Shows count: New records, Existing records, Invalid records
- Lists Salesforce IDs of existing records

**User sees**:
```
✅ Validation Results:
   • 150 New Records → Will be INSERTED
   • 50 Existing Records → Will be UPDATED (if UPSERT)
   • 5 Invalid Records → Missing match field values

📋 Existing Records (50):
   Salesforce ID       Match Values
   001TARGET001       {Email: 'john@ex.com'}
   001TARGET002       {Email: 'jane@ex.com'}
   ...
```

---

## 🏗️ Architecture

### **File Structure**
```
c:\DM_toolkit\
├── ui_components/
│   └── org_migration.py (Main module - 1416 lines)
├── migration_configs/     (New directory)
│   └── [saved mapping templates]
├── streamlit_app.py       (Tab already integrated)
└── Documentation/
    └── ORG_MIGRATION_IMPLEMENTATION.md (This file)
```

---

## 🔧 Implementation Details

### **1. Connection Management**

**Function**: `connect_to_salesforce_org(credentials, org_name)`

**Purpose**: Establishes connection to source AND target orgs simultaneously

**Session State**:
```python
st.session_state.source_sf_conn      # Source org connection
st.session_state.target_sf_conn      # Target org connection
st.session_state.migration_source_org
st.session_state.migration_target_org
st.session_state.migration_object
```

---

### **2. Field Mapping**

**Function**: `get_object_fields(sf_conn, object_name)`

**Returns**:
```python
{
    'Name': {
        'label': 'Account Name',
        'type': 'string',
        'externalId': False,
        'unique': False
    },
    'External_ID__c': {
        'label': 'External ID',
        'type': 'string',
        'externalId': True,
        'unique': True
    }
}
```

**Auto-Mapping Logic**:
```python
# Maps fields with identical names automatically
for src_field in source_fields:
    if src_field in target_fields:
        field_mappings[src_field] = src_field
```

---

### **3. Main Object Matching Strategy Configuration**

**NEW FEATURE** - Tab 3, Section 1

**Purpose**: Define how to identify if records already exist in TARGET org

**Options**:
1. **External ID** - Single External ID field
2. **Unique Field** - Single unique field (Email, Phone)
3. **Field Combination** - Multiple fields with AND (FirstName + LastName + DOB)
4. **Field Concatenation** - Fields joined with separator (AccountNum_Year)

**Session State**:
```python
st.session_state.migration_main_match_strategy   # 'external_id' | 'field_combination' | 'field_concatenation'
st.session_state.migration_main_match_fields     # ['Email'] or ['FirstName', 'LastName', 'DOB']
st.session_state.migration_main_concat_separator # '_'
```

**SOQL Queries Generated**:
```sql
-- External ID:
SELECT Id FROM Account WHERE External_ID__c = 'ACC123'

-- Field Combination:
SELECT Id FROM Account WHERE FirstName = 'John' AND LastName = 'Doe' AND BirthDate = '1990-01-01'

-- Field Concatenation (checks component fields):
SELECT Id FROM Account WHERE AccountNumber = 'ACC123' AND Year = '2025'
```

---

### **4. Lookup Resolution Configuration**

**Function**: `identify_lookup_fields(fields_info)`

**Purpose**: Find all lookup/reference fields in the object

**Returns**:
```python
[
    {
        'field_name': 'ParentAccountId',
        'reference_to': ['Account'],
        'type': 'reference'
    },
    {
        'field_name': 'OwnerId',
        'reference_to': ['User'],
        'type': 'reference'
    }
]
```

**Configuration**:
Each lookup field gets its own matching strategy:
```python
st.session_state.migration_lookup_configs = {
    'ParentAccountId': {
        'parent_object': 'Account',
        'match_strategy': 'external_id',
        'match_fields': ['External_Account_ID__c']
    },
    'OwnerId': {
        'parent_object': 'User',
        'match_strategy': 'field_combination',
        'match_fields': ['Email']
    }
}
```

---

### **5. Target Org Parent ID Resolution**

**Function**: `query_target_org_for_parent_id()`

**⭐ CRITICAL LOGIC** - This is the HEART of the migration feature

**Purpose**: For each child record, find parent's Salesforce ID in TARGET org

**Process**:
```python
def query_target_org_for_parent_id(
    target_sf,              # TARGET org connection (not source!)
    parent_object,          # 'Account'
    match_strategy,         # 'external_id' | 'field_combination' | 'field_concatenation'
    match_fields,           # ['External_ID__c'] or ['Name', 'Industry']
    match_values,           # {'External_ID__c': 'ACC123'} from source record
    concat_separator='_'
):
    # Build WHERE clause
    if match_strategy == 'external_id':
        query = f"SELECT Id FROM {parent_object} WHERE {match_fields[0]} = '{match_values[match_fields[0]]}'"
    
    elif match_strategy == 'field_combination':
        conditions = [f"{field} = '{match_values[field]}'" for field in match_fields]
        query = f"SELECT Id FROM {parent_object} WHERE {' AND '.join(conditions)}"
    
    # Execute query on TARGET org
    result = target_sf.query(query)
    
    if result['totalSize'] > 0:
        return result['records'][0]['Id']  # TARGET org Salesforce ID!
    
    return None
```

**Example Flow**:
```
Source Record:
  Name: "John Doe"
  ParentAccount_External_ID: "ACC_12345"  (from source org)

Step 1: Extract match value
  match_values = {'External_ID__c': 'ACC_12345'}

Step 2: Query TARGET org
  SELECT Id FROM Account WHERE External_ID__c = 'ACC_12345'

Step 3: Get TARGET org ID
  Result: '001TARGET789'

Step 4: Set lookup field
  child_record['ParentAccountId'] = '001TARGET789'
```

---

### **6. Bulk Lookup Resolution**

**Function**: `resolve_lookup_relationships_for_migration()`

**Purpose**: Resolve ALL lookups for ALL records before loading

**Process**:
```python
for lookup_field, config in lookup_configs.items():
    parent_object = config['parent_object']
    match_strategy = config['match_strategy']
    match_fields = config['match_fields']
    
    for idx, row in source_df.iterrows():
        # Extract parent identifying values from source record
        match_values = {field: row[field] for field in match_fields}
        
        # Query TARGET org for parent ID
        target_parent_id = query_target_org_for_parent_id(
            target_sf=target_sf,  # TARGET org connection
            parent_object=parent_object,
            match_strategy=match_strategy,
            match_fields=match_fields,
            match_values=match_values
        )
        
        # Update record with TARGET org parent ID
        resolved_df.at[idx, lookup_field] = target_parent_id
```

**Statistics Tracked**:
```python
{
    'total_lookups': 2,
    'resolved': {
        'ParentAccountId': 450,  # Successfully found parent IDs
        'OwnerId': 500
    },
    'unresolved': {
        'ParentAccountId': 50,   # Parent not found in target
        'OwnerId': 0
    }
}
```

---

### **7. Existing Record Validation (NEW)**

**Function**: `check_record_exists_in_target()`

**Purpose**: Check if a SINGLE record already exists in target org

**Returns**: `(exists: bool, salesforce_id: Optional[str])`

**Example**:
```python
exists, sf_id = check_record_exists_in_target(
    target_sf=target_sf,
    object_name='Account',
    match_strategy='field_combination',
    match_fields=['Name', 'Industry', 'BillingCountry'],
    record_values={
        'Name': 'Acme Corp',
        'Industry': 'Technology',
        'BillingCountry': 'USA'
    }
)

# Result: exists=True, sf_id='001TARGET456'
# User notified: "This record already exists with ID 001TARGET456"
```

---

### **8. Bulk Validation (NEW)**

**Function**: `validate_existing_records_in_target()`

**Purpose**: Validate ALL source records against target org BEFORE migration

**Process**:
```python
results = {
    'total_records': 500,
    'existing_records': [],   # Records that already exist
    'new_records': [],        # Records that don't exist
    'invalid_records': [],    # Missing match field values
    'existing_count': 50,
    'new_count': 445,
    'invalid_count': 5
}

for each source record:
    1. Extract match field values
    2. Check if all match fields have values
    3. If incomplete → mark as invalid
    4. If complete → query target org
    5. If exists → add to existing_records with Salesforce ID
    6. If not exists → add to new_records
```

**User Display**:
```
📊 Validation Results:
   🆕 New Records: 445        (Will be INSERTED)
   ♻️ Existing Records: 50    (Will be UPDATED if UPSERT)
   ⚠️ Invalid Records: 5      (Missing match values)

📋 Existing Records Details:
   Index  Salesforce ID    Match Values
   0      001TARGET001     {'Email': 'john@example.com'}
   1      001TARGET002     {'Email': 'jane@example.com'}
   ...
```

---

### **9. Migration Execution Flow**

**Enhanced 5-Step Process**:

**Step 1: Extract from Source Org**
```python
# Extract all required fields including match fields
field_list = list(field_mappings.keys()) + main_match_fields + lookup_match_fields
soql = f"SELECT {', '.join(field_list)} FROM {object_name}"
source_data = source_sf.query(soql)
```

**Step 2: Apply Field Mappings**
```python
# Rename source fields to target field names
for source_field, target_field in field_mappings.items():
    if source_field != target_field:
        mapped_data.rename(columns={source_field: target_field}, inplace=True)
```

**Step 3: Final Validation (NEW)**
```python
# Check one more time before loading
final_validation = validate_existing_records_in_target(
    target_sf, object_name, match_strategy, match_fields, mapped_data
)

if migration_operation == "INSERT" and final_validation['existing_count'] > 0:
    st.error("Cannot INSERT - records already exist. Use UPSERT.")
    STOP()
```

**Step 4: Resolve Lookups**
```python
# For each lookup field, query TARGET org for parent IDs
resolved_data, stats = resolve_lookup_relationships_for_migration(
    source_df=mapped_data,
    target_sf=target_sf,
    lookup_configs=lookup_configs
)
# Result: All lookup fields now contain TARGET org Salesforce IDs
```

**Step 5: Load to Target**
```python
# Execute bulk operation
if operation == "INSERT":
    result = target_sf.bulk.Account.insert(records)
elif operation == "UPSERT":
    result = target_sf.bulk.Account.upsert(records, external_id_field)
elif operation == "UPDATE":
    result = target_sf.bulk.Account.update(records)
```

---

## 📊 UI/UX Flow

### **Tab 1: Configuration**
```
[Source Org: Production ▼]  →  [Target Org: Sandbox_UAT ▼]
                ↓
      [Object: Account ▼]
```

**User Actions**:
1. Select source org
2. Select target org (different from source)
3. Choose object to migrate

**System Actions**:
- Connects to both orgs simultaneously
- Validates connections
- Stores connections in session state

---

### **Tab 2: Field Mapping**
```
Source Field          →    Target Field
─────────────              ────────────
Name                  →    Name ✅
Custom_Email__c       →    Email ▼
Old_Industry__c       →    Industry ▼
BillingStreet         →    BillingStreet ✅

[🤖 Auto-Map]  [💾 Save Template]  [📂 Load Template]
```

**Features**:
- Auto-mapping for identical field names
- Data type compatibility checking
- Save/load mapping templates
- Filter: Show mapped/unmapped only

---

### **Tab 3: Lookup Resolution & Record Matching**

**Section 1: Main Object Matching (NEW)**
```
🎯 Main Object Matching Strategy

How to match records in target org:
  ⚫ external_id - Single External ID Field
  ○ unique_field - Single Unique Field
  ○ field_combination - Multiple Fields (AND)
  ○ field_concatenation - Concatenated Fields

Selected: External_ID__c

💡 Will query: SELECT Id FROM Account WHERE External_ID__c = <value>
```

**Purpose**: 
- Define how to check if records already exist
- Used for validation and duplicate detection
- Critical for INSERT vs UPSERT decision

**Section 2: Lookup Field Resolution**
```
🔗 Lookup Fields (2 found)

┌─────────────────────────────────────────┐
│ ParentAccountId → Account               │
├─────────────────────────────────────────┤
│ Match Strategy: ⚫ external_id          │
│ External ID Field: [External_ID__c ▼]  │
│                                         │
│ 💡 Will query TARGET org:               │
│ SELECT Id FROM Account                  │
│ WHERE External_ID__c = <value>          │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ OwnerId → User                          │
├─────────────────────────────────────────┤
│ Match Strategy: ⚫ field_combination    │
│ Fields: [Email, Username]               │
│                                         │
│ 💡 Will query TARGET org:               │
│ SELECT Id FROM User                     │
│ WHERE Email = <value>                   │
│   AND Username = <value>                │
└─────────────────────────────────────────┘
```

---

### **Tab 4: Execute Migration**

**Pre-Migration Validation**
```
✅ Source and Target orgs connected
✅ 15 fields mapped
✅ All 2 lookup field(s) configured
```

**Migration Options**
```
Operation: ⚫ INSERT  ○ UPSERT  ○ UPDATE
Batch Size: [500]

Extract Filter: Type != 'Test' AND CreatedDate > 2024-01-01
Max Records: [10000]
```

**Check Existing Records (NEW)**
```
[🔍 Check Existing Records in Target Org]
```
**→ Runs validation, shows**:
```
📊 Validation Results:
   🆕 New Records: 450        (Will be INSERTED)
   ♻️ Existing Records: 50    (Will be UPDATED)
   ⚠️ Invalid Records: 0

📋 View 50 Existing Records ▼
   Salesforce ID    Match Values
   001TARGET001     {'External_ID__c': 'ACC001'}
   001TARGET002     {'External_ID__c': 'ACC002'}
   ...
```

**Start Migration**
```
[🚀 Start Migration]
```
**→ Executes with progress**:
```
📊 Migration Progress:
✅ Step 1/5: Extracting data from source org... (500 records)
✅ Step 2/5: Applying field mappings... (15 mappings)
✅ Step 3/5: Final check for existing records... (450 new, 50 existing)
✅ Step 4/5: Resolving lookup relationships... 
     • ParentAccountId: 495 resolved, 5 unresolved
     • OwnerId: 500 resolved, 0 unresolved
✅ Step 5/5: Loading data to target org...
     Batch 1/1 completed

📊 Migration Results:
   ✅ Success: 495
   ❌ Failed: 5
   📊 Total: 500

🎉 Migration completed! 495/500 records migrated successfully
```

---

## 🔍 Key Implementation Highlights

### **1. Dual Connection Management**
```python
# Source org connection
source_sf = st.session_state.source_sf_conn

# Target org connection (DIFFERENT org)
target_sf = st.session_state.target_sf_conn

# CRITICAL: Always query TARGET org for IDs
target_id = target_sf.query("SELECT Id FROM...")  # ← TARGET org!
```

### **2. Match Strategy Abstraction**
```python
# Same function handles all three strategies
strategy = 'external_id' | 'field_combination' | 'field_concatenation'

# Logic adapts based on strategy
if strategy == 'external_id':
    WHERE field = value
elif strategy == 'field_combination':
    WHERE field1 = value1 AND field2 = value2
elif strategy == 'field_concatenation':
    WHERE field1 = value1 AND field2 = value2  # Same as combination
```

### **3. Pre-Migration Validation**
```python
# NEW: Check before migrating
validation_results = validate_existing_records_in_target(...)

# User sees what will happen
if INSERT and existing_count > 0:
    ERROR("Cannot INSERT - use UPSERT")
elif UPSERT:
    INFO(f"{new_count} will INSERT, {existing_count} will UPDATE")
```

### **4. Parent ID Resolution**
```python
# For EACH child record:
source_record = {'Name': 'John', 'Parent_External_ID': 'ACC123'}

# Query TARGET org
target_parent_id = query_target_org(
    "SELECT Id FROM Account WHERE External_ID__c = 'ACC123'"
)  # Returns: '001TARGET789'

# Use TARGET org ID in child record
child_record['ParentAccountId'] = '001TARGET789'
```

---

## 🚨 Critical Error Handling

### **1. Missing Match Field Values**
```python
# Record: {Name: 'John', External_ID__c: ''}
# External ID is empty!

→ Mark as INVALID
→ Show in validation results
→ Skip during migration
```

### **2. Parent Not Found in Target**
```python
# Query: SELECT Id FROM Account WHERE External_ID__c = 'ACC999'
# Result: No records found

→ Set lookup field to NULL
→ Track in unresolved statistics
→ Continue migration (lookup will be empty)
```

### **3. Duplicate Detection for INSERT**
```python
# Operation: INSERT
# Validation: 50 records already exist

→ BLOCK migration
→ Show error: "Cannot INSERT - use UPSERT"
→ Display existing record IDs
```

---

## 📈 Performance Considerations

### **1. Batch Processing**
```python
# Process in batches to avoid timeout
batch_size = 500  # Configurable

for batch in batches:
    # Check each record
    for record in batch:
        exists, sf_id = check_record_exists(...)
```

### **2. Query Optimization**
```sql
-- Always use LIMIT 1 (only need to know IF exists)
SELECT Id FROM Account WHERE Email = 'john@example.com' LIMIT 1

-- Use indexed fields (External ID, Unique fields)
-- Faster than non-indexed fields
```

### **3. Progress Indicators**
```python
# Show progress during validation
progress_bar = st.progress(0)
for idx, row in enumerate(data):
    validate(row)
    progress_bar.progress((idx + 1) / total)
```

---

## 🎓 Usage Examples

### **Example 1: Simple Migration with External ID**

**Scenario**: Migrate Accounts from Production to Sandbox, both have External_ID__c

**Configuration**:
```
Tab 1: 
  Source: Production
  Target: Sandbox_UAT
  Object: Account

Tab 2:
  Name → Name
  External_ID__c → External_ID__c
  Industry → Industry

Tab 3:
  Main Matching: external_id (External_ID__c)
  No lookup fields

Tab 4:
  Operation: UPSERT
  Execute
```

**Result**:
- Existing records updated by External ID
- New records inserted
- No duplicates

---

### **Example 2: Complex Parent-Child Migration**

**Scenario**: Migrate Contacts with Account lookups, using field combinations

**Configuration**:
```
Tab 1:
  Source: Production
  Target: Sandbox_UAT
  Object: Contact

Tab 2:
  FirstName → FirstName
  LastName → LastName
  Email → Email
  Account_Name → ParentAccount_Name (for matching)

Tab 3:
  Main Matching: field_combination [FirstName, LastName, Email]
  
  Lookup: AccountId
    Parent Object: Account
    Strategy: field_combination
    Match Fields: [Name, Industry, BillingCountry]

Tab 4:
  Check Existing: Shows 200 new, 50 existing
  Operation: UPSERT
  Execute
```

**Process**:
```
For each Contact:
1. Query TARGET Sandbox for Account:
   SELECT Id FROM Account 
   WHERE Name = <value> 
   AND Industry = <value> 
   AND BillingCountry = <value>

2. Get Account ID from Sandbox: '001SANDBOX123'

3. Create/Update Contact with:
   - FirstName, LastName, Email (fields)
   - AccountId = '001SANDBOX123' (from Sandbox!)
```

**Result**:
- 200 new Contacts inserted
- 50 existing Contacts updated
- All linked to correct Accounts in Sandbox

---

### **Example 3: UI-Created Records (No External ID)**

**Scenario**: Client created records in UI (no External ID), need to migrate without duplicates

**Configuration**:
```
Tab 3:
  Main Matching: field_combination
  Fields: [Name, Phone, BillingCountry]
  
  Explanation: These 3 fields uniquely identify a record
  even without External ID
```

**Validation Result**:
```
🔍 Checking Existing Records...

✅ Validation Complete:
   📋 Record: "Acme Corp | 555-1234 | USA"
   ⚠️ Already exists in target org!
   🔑 Salesforce ID: 001TARGET456
   💡 Will UPDATE this record (not INSERT)

   📋 Record: "TechCo | 555-5678 | Canada"
   🆕 Not found in target org
   💡 Will INSERT as new record
```

**User Action**:
- Sees which records already exist
- Can choose UPSERT to update existing + insert new
- Or filter out existing records and INSERT only new ones

---

## ✅ Testing Checklist

- [x] Connect to two different orgs simultaneously
- [x] Field mapping with auto-detection
- [x] Save/load mapping templates
- [x] External ID matching strategy
- [x] Field combination matching strategy
- [x] Field concatenation matching strategy
- [x] Lookup resolution with External ID
- [x] Lookup resolution with field combination
- [x] Lookup resolution with field concatenation
- [x] Validate existing records before migration
- [x] Show Salesforce IDs of existing records
- [x] Block INSERT if records exist
- [x] Allow UPSERT with existing records
- [x] Handle missing match field values
- [x] Handle unresolved parent lookups
- [x] Batch processing with progress indicators
- [x] Migration statistics (success/failed)

---

## 📞 Support & Troubleshooting

### **Common Issues**

**Issue 1**: "Cannot connect to org"
- **Solution**: Check credentials in Services/linkedservices.json
- Verify security token is correct
- Check domain (login vs test)

**Issue 2**: "No External ID fields found"
- **Solution**: Use field combination or concatenation strategy
- Select unique fields that identify records

**Issue 3**: "Parent record not found in target"
- **Solution**: Migrate parent objects first
- Check parent matching strategy
- Verify parent data exists in target

**Issue 4**: "Cannot INSERT - records exist"
- **Solution**: Use UPSERT operation instead
- Or filter out existing records from source data

---

## 🎯 Summary

**What Was Implemented**:

1. ✅ **Dual Org Connection**: Connect to source and target orgs simultaneously
2. ✅ **Field Mapping**: Auto-detect and manually map fields between orgs
3. ✅ **Main Object Matching**: Configure how to identify existing records
4. ✅ **Lookup Resolution**: Query TARGET org for parent IDs using flexible strategies
5. ✅ **Existing Record Validation**: Check and notify before migration
6. ✅ **Duplicate Prevention**: Block INSERT if records exist, allow UPSERT
7. ✅ **Flexible Matching**: External ID, unique field, combination, concatenation
8. ✅ **UI-Created Record Support**: Handle records without External ID
9. ✅ **Progress Tracking**: Visual feedback during validation and migration
10. ✅ **Error Handling**: Graceful handling of missing parents and invalid data

**Key Innovation**:
The system intelligently queries the **TARGET org** (not source) to find Salesforce IDs, enabling seamless parent-child migrations regardless of how records were created (file or UI).

---

**Document Version**: 1.0
**Last Updated**: December 3, 2025
**Implementation Status**: ✅ Complete and Tested
