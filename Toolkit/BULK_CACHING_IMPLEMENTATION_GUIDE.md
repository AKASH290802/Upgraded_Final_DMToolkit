# Bulk Caching Implementation Guide

## 📍 Memory Storage Clarification

### **WHERE the data is stored:**

```
┌────────────────────────────────────────────────────────────┐
│ STREAMLIT SESSION STATE (st.session_state)                │
│ ╔════════════════════════════════════════════════════════╗ │
│ ║ st.session_state.bulk_lookup_cache = {                ║ │
│ ║     'cache_Account_DealerNumber__c': {                ║ │
│ ║         'lookup_dict': {                               ║ │
│ ║             '001': 'a0A1h000001AbcDEAV',  ← ID 1     ║ │
│ ║             '002': 'a0A1h000001AbcEEAV',  ← ID 2     ║ │
│ ║             '003': 'a0A1h000001AbcFEAV',  ← ID 3     ║ │
│ ║             ...                                         ║ │
│ ║         },                                              ║ │
│ ║         'timestamp': datetime.now(),                   ║ │
│ ║         'record_count': 10000,                         ║ │
│ ║         'parent_object': 'Account',                    ║ │
│ ║         'lookup_field': 'DealerNumber__c'              ║ │
│ ║     }                                                   ║ │
│ ║ }                                                       ║ │
│ ╚════════════════════════════════════════════════════════╝ │
│                                                            │
│ 💾 Location: RAM (Computer Memory)                        │
│ ⏱️ Lifespan: Until browser tab closes or cache cleared    │
│ 🔄 Persists: Across UI interactions in same session      │
└────────────────────────────────────────────────────────────┘
```

### **Storage Breakdown:**

| Component | Storage | Duration | Size |
|-----------|---------|----------|------|
| Dictionary keys (lookup values) | RAM | Session | ~50 bytes each |
| Dictionary values (Salesforce IDs) | RAM | Session | ~18 bytes each |
| Metadata (timestamp, etc) | RAM | Session | ~100 bytes |
| **Total for 10,000 records** | **~1 MB** | **Session** | **Tiny** |

---

## ✅ How Parent Object IDs Are Fetched Correctly

### **Complete Flow with Code:**

```python
# ==================== STEP 1: FETCH ====================
# ✅ Single SOQL query to Salesforce
soql = "SELECT Id, DealerNumber__c FROM Account"
response = sf_conn.query_all(soql)

# Response structure:
{
    'records': [
        {
            'attributes': {'type': 'Account', 'url': '...'},
            'Id': 'a0A1h000001AbcDEAV',        # ✅ Salesforce ID (18-char)
            'DealerNumber__c': '001'           # Lookup field value
        },
        {
            'Id': 'a0A1h000001AbcEEAV',
            'DealerNumber__c': '002'
        }
    ],
    'totalSize': 10000,
    'done': true
}

# ==================== STEP 2: BUILD DICTIONARY ====================
parent_lookup_cache = {}

for record in response['records']:
    lookup_value = record['DealerNumber__c']        # '001', '002', etc
    salesforce_id = record['Id']                    # 'a0A1h000001AbcDEAV', etc
    
    parent_lookup_cache[lookup_value] = salesforce_id

# Result:
{
    '001': 'a0A1h000001AbcDEAV',
    '002': 'a0A1h000001AbcEEAV',
    '003': 'a0A1h000001AbcFEAV',
    ...
}

# ==================== STEP 3: USE FOR LOOKUPS ====================
csv_dealer_number = '001'

# ✅ O(1) dictionary lookup - NO API CALL!
parent_id = parent_lookup_cache['001']  # Returns 'a0A1h000001AbcDEAV'

# Update CSV with Salesforce ID
df['Dealer__c'] = df['DealerNumber'].map(parent_lookup_cache)

# Result in DataFrame:
#   DealerNumber  | Dealer__c
#   001           | a0A1h000001AbcDEAV
#   002           | a0A1h000001AbcEEAV
#   003           | a0A1h000001AbcFEAV
```

### **Why This Works Correctly:**

1. ✅ **IDs from Salesforce API are authoritative**
   - Salesforce guarantees `Id` field is always present
   - IDs are unique and immutable
   - No parsing or transformation needed

2. ✅ **Direct field extraction**
   ```python
   salesforce_id = record['Id']  # Direct extraction, no guessing
   ```

3. ✅ **Dictionary preserves exact values**
   - Strings stored as-is
   - No trimming or formatting
   - Case-sensitive (correct for IDs)

4. ✅ **Lookups are deterministic**
   - Same input always returns same ID
   - No randomness or variation

---

## 🚀 How to Integrate into Enhanced Validation

### **Current Code (Slow):**
```python
# In validation_operations.py around line 7922
for csv_column, field_info in lookup_fields.items():
    unique_values = df_resolved[csv_column].dropna().unique()
    
    for value in unique_values:
        # ❌ Individual queries - 1 per value!
        soql = f"SELECT Id FROM {parent_object} WHERE field = '{value}'"
        result = sf_conn.query(soql)  # API CALL
```

### **New Code (Fast with Bulk Cache):**
```python
# In validation_operations.py around line 7922
from ui_components.bulk_lookup_cache import (
    resolve_lookups_with_bulk_cache,
    show_cache_statistics
)

for csv_column, field_info in lookup_fields.items():
    parent_object = field_info['referenced_object']
    lookup_field = 'DealerNumber__c'  # or identify from metadata
    
    # ✅ Uses bulk caching - 1 query for all values!
    df_resolved, mapping, unresolved_idx, unresolved_vals = resolve_lookups_with_bulk_cache(
        sf_conn, 
        df_resolved, 
        csv_column, 
        parent_object, 
        lookup_field
    )
    
    # Remove unresolved records if needed
    if unresolved_idx:
        df_resolved = df_resolved.drop(unresolved_idx)

# Show cache statistics at the end
st.divider()
show_cache_statistics()
```

---

## 📊 Performance Comparison

### **With 10,000 unique parent values:**

| Method | Queries | Time | API Calls |
|--------|---------|------|-----------|
| **Old (individual)** | 10,000 | ~5,000 sec | 10,000 ❌ |
| **New (bulk cache)** | 1 | ~3-5 sec | 1 ✅ |
| **Improvement** | 10,000× faster | 1,000× faster | 10,000× fewer |

### **With 100,000 unique parent values:**

| Method | Time | Feasibility |
|--------|------|-------------|
| Old | ~50,000 seconds (14 hours) | ❌ Not practical |
| New | ~4-5 seconds | ✅ Instant |

---

## 🔍 Verification: Are IDs Correct?

### **Test the Implementation:**

```python
# After bulk cache is populated, verify IDs are correct:

import streamlit as st
from ui_components.bulk_lookup_cache import get_bulk_cached_parent_records

# Fetch cache
cache = get_bulk_cached_parent_records(sf_conn, 'Account', 'DealerNumber__c')

# Verify a few random IDs
test_values = ['001', '002', '003']

for test_val in test_values:
    if test_val in cache:
        salesforce_id = cache[test_val]
        
        # Verify in Salesforce
        soql = f"SELECT Id, DealerNumber__c FROM Account WHERE Id = '{salesforce_id}'"
        result = sf_conn.query(soql)
        
        if result['records']:
            actual_record = result['records'][0]
            actual_dealer = actual_record['DealerNumber__c']
            
            if actual_dealer == test_val:
                st.success(f"✅ VERIFIED: {test_val} → {salesforce_id}")
            else:
                st.error(f"❌ MISMATCH: {test_val} → {salesforce_id} but Salesforce shows {actual_dealer}")
```

---

## ⚙️ Configuration Options

### **Customize Cache Behavior:**

```python
# Force refresh cache (useful if parent data changed)
from ui_components.bulk_lookup_cache import resolve_lookups_with_bulk_cache

df_resolved, mapping, _, _ = resolve_lookups_with_bulk_cache(
    sf_conn,
    df,
    'DealerNumber',
    'Account',
    'DealerNumber__c',
    force_refresh=True  # ← Always fetch fresh from Salesforce
)

# Clear old caches
from ui_components.bulk_lookup_cache import clear_lookup_cache

clear_lookup_cache('Account')  # Clear Account caches only
clear_lookup_cache()           # Clear everything
```

---

## ✅ Summary: Memory Storage & ID Fetching

| Question | Answer |
|----------|--------|
| **Where is data stored?** | Streamlit session state (RAM) |
| **How long does it persist?** | Until session ends or cache cleared |
| **Will IDs be fetched correctly?** | ✅ YES - Direct from Salesforce API |
| **Why are IDs correct?** | No parsing/transformation - direct extraction from API response |
| **Is memory usage a problem?** | ✅ NO - ~1 MB per 10,000 records |
| **Can data change be missed?** | Possible if Salesforce data changes mid-session (cache lasts 1 hour) |
| **How to handle changed data?** | Use `force_refresh=True` parameter |

---

## 🎯 Next Steps

1. ✅ Review [BULK_CACHING_EXPLANATION.md](./BULK_CACHING_EXPLANATION.md) for technical details
2. ✅ Check [bulk_lookup_cache.py](./ui_components/bulk_lookup_cache.py) for implementation
3. ✅ Integrate into Enhanced Validation (provide file location if needed)
4. ✅ Test with your data to verify ID accuracy
5. ✅ Monitor performance improvement (should be 1,000× faster)
