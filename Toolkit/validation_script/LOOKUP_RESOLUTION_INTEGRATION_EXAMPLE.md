# Integration Example: Using Lookup Resolution in Data Loading

This file demonstrates how to integrate the lookup resolution validator into the data loading process.

## Quick Start

### Step 1: Import the Lookup Resolution Module
```python
from validation_script.lookup_resolution_validator import (
    resolve_lookup_value_to_salesforce_id,
    batch_resolve_lookup_values,
    get_lookup_resolution_candidates
)
```

### Step 2: In DataLoader.py - Before Inserting Records

**Location:** `dataload/DataLoader.py` (in the record preparation section)

```python
def prepare_record_for_upload(self, record: dict, sf_conn, object_name: str):
    """
    Prepare a record for upload by resolving lookup fields
    """
    prepared_record = record.copy()
    lookup_fields = self.get_lookup_fields(object_name)  # Get field metadata
    
    for field_name, field_info in lookup_fields.items():
        if field_name in prepared_record:
            value = prepared_record[field_name]
            
            # Skip empty values
            if pd.isna(value) or str(value).strip() == "":
                continue
            
            # Resolve lookup value to Salesforce ID
            resolved_id, error = resolve_lookup_value_to_salesforce_id(
                sf_conn=sf_conn,
                parent_object=field_info.get("reference_to")[0],  # Get parent object name
                lookup_value=str(value)
            )
            
            if error:
                # Log error and mark record as failed
                self.log_record_error(
                    object_name=object_name,
                    record_id=record.get("Id", "NEW"),
                    field_name=field_name,
                    error=error
                )
                prepared_record["_upload_status"] = "FAILED"
                prepared_record["_error_message"] = error
            else:
                # Update record with resolved ID
                prepared_record[field_name] = resolved_id
    
    return prepared_record
```

### Step 3: In transformed.py - Batch Resolution

**Location:** `dataload/transformed.py` (in the data transformation section)

```python
def transform_and_resolve_lookups(self, dataframe: pd.DataFrame, sf_conn, object_name: str):
    """
    Transform data and resolve all lookup fields in batch for efficiency
    """
    df_transformed = dataframe.copy()
    lookup_fields = self.get_lookup_fields(object_name)
    
    for field_name, field_info in lookup_fields.items():
        if field_name not in df_transformed.columns:
            continue
        
        # Get all non-empty values for this field
        values_to_resolve = df_transformed[field_name].dropna().unique().tolist()
        
        if not values_to_resolve:
            continue
        
        # Batch resolve all values
        resolved_values = batch_resolve_lookup_values(
            sf_conn=sf_conn,
            field_name=field_name,
            values=values_to_resolve,
            field_info=field_info
        )
        
        # Update dataframe with resolved IDs
        for idx, row in df_transformed.iterrows():
            if pd.isna(row[field_name]):
                continue
            
            original_value = str(row[field_name])
            resolved_id, error = resolved_values.get(original_value, (None, "Not resolved"))
            
            if error:
                # Mark row as having error
                df_transformed.at[idx, "_resolution_error"] = error
                df_transformed.at[idx, "_original_lookup_value"] = original_value
            else:
                # Update with resolved ID
                df_transformed.at[idx, field_name] = resolved_id
    
    return df_transformed
```

## Real-World Scenario

### Scenario: Loading WOD_2__Claim__c with Dealer Lookup

**Input File:**
```csv
WOD_2__Dealer__c,ClaimAmount,ClaimStatus
914021,5000,Open
914022,3500,Closed
INVALID,2000,Open
```

**Processing Flow:**

```
1. VALIDATION PHASE (validation_operations.py)
   └─ Check field "WOD_2__Dealer__c"
   └─ Type: reference
   └─ NEW: Accepts "914021", "914022", "INVALID" (no format rejection)
   └─ Passes validation ✅

2. TRANSFORMATION PHASE (transformed.py)
   └─ Extract unique dealer values: ["914021", "914022", "INVALID"]
   └─ Batch resolve all values
      ├─ Query: SELECT Id FROM Dealer WHERE Name IN ('914021', '914022', 'INVALID')
      ├─ Results:
      │  ├─ "914021" → "001D000000ABC123XYZ" ✅
      │  ├─ "914022" → "001D000000DEF456XYZ" ✅
      │  └─ "INVALID" → ERROR: Not found ❌
      └─ Update dataframe

3. DATA PREPARATION PHASE (DataLoader.py)
   └─ For each row:
      ├─ Row 1: WOD_2__Dealer__c = "001D000000ABC123XYZ" → Ready ✅
      ├─ Row 2: WOD_2__Dealer__c = "001D000000DEF456XYZ" → Ready ✅
      └─ Row 3: _resolution_error = "Could not find Dealer..." → Marked failed ❌

4. UPLOAD PHASE
   └─ Insert 2 records successfully
   └─ Log 1 record failure with reason
```

## Error Handling Best Practices

### Handle Resolution Failures Gracefully

```python
def process_with_fallback(self, sf_conn, value, parent_object):
    """
    Try resolution, fall back to validation if it fails
    """
    # Try intelligent resolution first
    resolved_id, error = resolve_lookup_value_to_salesforce_id(
        sf_conn=sf_conn,
        parent_object=parent_object,
        lookup_value=value
    )
    
    if resolved_id:
        return resolved_id, None  # Success
    
    # Resolution failed - provide helpful feedback
    candidates = get_lookup_resolution_candidates(parent_object)
    detailed_error = f"""
    Could not resolve lookup value '{value}' to {parent_object}.
    
    Searched fields: {', '.join(candidates)}
    
    Please verify:
    1. Value '{value}' exists in {parent_object} object
    2. Check spelling and case
    3. Consider using Salesforce ID directly if available
    4. Contact admin if the record should exist but doesn't
    """
    
    return None, detailed_error
```

## Configuration Example

### Custom Candidate Fields for Your Objects

**File to modify:** `validation_script/lookup_resolution_validator.py`

```python
# Customize this dictionary for your organization
LOOKUP_RESOLUTION_CANDIDATES = {
    # Standard Objects
    "Account": [
        "Name",                    # Most lookups use Name
        "AccountNumber",           # Try account number
        "BillingCity",            # Geographic match
        "CustomerIdFromERP",      # Custom field
    ],
    "Contact": [
        "Name",
        "Email",                  # Email unique identifier
        "Phone",
        "EmployeeId__c",          # Custom field
    ],
    
    # Custom Objects (Critical for your orgs)
    "Dealer": [
        "Name",                   # Primary: Dealer name
        "Code",                   # Secondary: Dealer code (your 914021 format)
        "DealerNumber",           # Alternative: Dealer number
        "ExternalId__c",          # Standard: External ID field
        "PartnerCode",            # Custom: Partner code
    ],
    
    "Warranty_Type": [
        "Name",
        "Code",
        "WarrantyCode__c",
        "ExternalId__c",
    ],
    
    "WOD_2__Claim__c": [
        "Name",
        "ClaimNumber__c",
        "ExternalClaimId__c",
    ],
}
```

## Performance Optimization

### For Large Files with Many Lookups

```python
def optimize_batch_resolution(self, sf_conn, dataframe, lookup_fields):
    """
    Optimized batch resolution for large datasets
    """
    import concurrent.futures
    
    # Group by field to parallelize
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        
        for field_name, field_info in lookup_fields.items():
            values = dataframe[field_name].dropna().unique().tolist()
            
            # Submit each field resolution as separate task
            future = executor.submit(
                batch_resolve_lookup_values,
                sf_conn=sf_conn,
                field_name=field_name,
                values=values,
                field_info=field_info
            )
            futures[field_name] = future
        
        # Collect results
        resolution_results = {}
        for field_name, future in futures.items():
            resolution_results[field_name] = future.result()
    
    return resolution_results
```

## Testing Lookup Resolution

### Unit Test Example

```python
import unittest
from validation_script.lookup_resolution_validator import resolve_lookup_value_to_salesforce_id

class TestLookupResolution(unittest.TestCase):
    
    def setUp(self):
        self.sf_conn = mock_salesforce_connection()  # Your test connection
    
    def test_resolve_external_id(self):
        """Test resolving external ID to Salesforce ID"""
        resolved_id, error = resolve_lookup_value_to_salesforce_id(
            sf_conn=self.sf_conn,
            parent_object="Dealer",
            lookup_value="914021"
        )
        
        self.assertIsNone(error)
        self.assertTrue(len(resolved_id) in [15, 18])  # Valid Salesforce ID
        self.assertEqual(resolved_id, "001D000000ABC123XYZ")
    
    def test_resolve_nonexistent_value(self):
        """Test error handling for non-existent value"""
        resolved_id, error = resolve_lookup_value_to_salesforce_id(
            sf_conn=self.sf_conn,
            parent_object="Dealer",
            lookup_value="NONEXISTENT"
        )
        
        self.assertIsNone(resolved_id)
        self.assertIsNotNone(error)
        self.assertIn("Could not find Dealer", error)
    
    def test_resolve_actual_salesforce_id(self):
        """Test that actual Salesforce IDs are passed through"""
        resolved_id, error = resolve_lookup_value_to_salesforce_id(
            sf_conn=self.sf_conn,
            parent_object="Dealer",
            lookup_value="001D000000ABC123XYZ"
        )
        
        self.assertIsNone(error)
        self.assertEqual(resolved_id, "001D000000ABC123XYZ")
```

## Integration Checklist

- [ ] Import lookup_resolution_validator in validation_operations.py ✅
- [ ] Update reference field validation logic in validation_operations.py ✅
- [ ] Modify DataLoader.py to call `resolve_lookup_value_to_salesforce_id()`
- [ ] Modify transformed.py to call `batch_resolve_lookup_values()`
- [ ] Add custom candidate fields for your objects
- [ ] Test with sample data containing external IDs
- [ ] Test error scenarios (missing records, invalid values)
- [ ] Performance test with large files
- [ ] Update user documentation
- [ ] Add unit tests for resolution logic

## Troubleshooting Guide

### Error: "Could not find Dealer matching value 'INVALID'"

**Root Causes:**
1. Value doesn't exist in parent object - verify in Salesforce
2. Candidate field not available - check field exists in Dealer object
3. Wrong parent object - verify reference_to in field metadata

**Solution:**
```python
# Debug: List what was searched
from validation_script.lookup_resolution_validator import get_lookup_resolution_candidates

candidates = get_lookup_resolution_candidates("Dealer")
print(f"Searched fields: {candidates}")  # Name, Code, ExternalId__c, etc.
```

### Error: "Multiple matches found for value 'Test'"

**Root Cause:** Value matches multiple records (common for generic names)

**Solution:**
1. Use more specific external ID or code
2. Refine candidate fields list
3. Use actual Salesforce ID instead

### Performance Issue: Resolution taking > 5 seconds per record

**Root Cause:** Too many SOQL queries, network latency

**Solution:**
1. Use batch_resolve_lookup_values instead of resolving one by one
2. Implement caching for repeated values
3. Consider parallel processing with ThreadPoolExecutor

## Monitoring and Logging

### Add Resolution Logging

```python
def log_resolution_result(field_name, original_value, resolved_id, error=None):
    """Log lookup resolution for audit trail"""
    log_entry = {
        "timestamp": datetime.now(),
        "field_name": field_name,
        "original_value": original_value,
        "resolved_id": resolved_id,
        "success": error is None,
        "error_message": error
    }
    
    # Save to resolution_log.json for audit
    with open("resolution_log.json", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
```

---

**For more information, see:**
- [LOOKUP_RESOLUTION_IMPLEMENTATION.md](LOOKUP_RESOLUTION_IMPLEMENTATION.md)
- [DataLoader.py](../dataload/DataLoader.py)
- [transformed.py](../dataload/transformed.py)
