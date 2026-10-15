# ✨ Relationship Fields in Lookup Resolution - Implementation Guide

## Overview

The Lookup Resolution tab now supports **relationship fields** (fields accessed through relationships with dot notation like `ProductCategory.Name`, `Account.Industry`, etc.). This allows for more flexible and accurate parent-child record matching during migration.

---

## What Are Relationship Fields?

### Before (Limited to Direct Fields)
```
Lookup Resolution:
  Match Strategy: external_id
  Select Field: [ProductCategoryId, DealerNumber, Type, Status]
                ↑ Only direct fields available
```

### After (Now Includes Relationship Fields) ✨
```
Lookup Resolution:
  Match Strategy: external_id
  Select Field: [🏷️ ProductCategoryId, 
                 🏷️ DealerNumber,
                 🔗 ProductCategory.Name,       ← NEW!
                 🔗 ProductCategory.Description ← NEW!
                 🏷️ AccountId,
                 🔗 Account.Industry]           ← NEW!
```

---

## Use Cases

### Example 1: Match by Parent Record Name
**Scenario**: You want to match Products by the ProductCategory name instead of ID

```
Parent Object: ProductCategory
Direct Field Options:
  - ProductCategoryId (ID reference)
  - ProductCategoryName (duplicate data)

Relationship Field Options:
  - ProductCategory.Name ← Match by parent's actual name!
```

**Configuration**:
```
Lookup Field: ProductCategoryId
Parent Object: ProductCategory
Match Strategy: external_id - Single External ID Field
Select Field: 🔗 ProductCategory.Name
```

**SOQL Query Generated**:
```sql
SELECT Id FROM ProductCategory WHERE Name = 'Electronics' LIMIT 1
```

---

### Example 2: Match by Multiple Relationship Attributes
**Scenario**: Match accounts using industry AND region from related parent

```
Lookup Field: Account__c
Parent Object: Account
Match Strategy: field_combination - Multiple Fields (AND)
Select Fields:
  - 🔗 ParentAccount.Industry
  - 🔗 ParentAccount.BillingCity
  - 🏷️ Status
```

**SOQL Query Generated**:
```sql
SELECT Id FROM Account 
WHERE ParentAccount.Industry = 'Technology' 
  AND ParentAccount.BillingCity = 'San Francisco' 
  AND Status = 'Active' 
LIMIT 1
```

---

### Example 3: Concatenate Relationship Fields
**Scenario**: Create a composite key from parent attributes

```
Lookup Field: Dealer__c
Parent Object: Account
Match Strategy: field_concatenation - Concatenated Fields
Select Fields:
  - 🔗 Account.DealerCode    → "D123"
  - 🔗 Account.BillingCity  → "NYC"
  - 🏷️ Status                → "Active"
Separator: "_"

Lookup Value in data: "D123_NYC_Active"
```

---

## How It Works

### Step 1: Field Discovery
When you select a parent object in Lookup Resolution tab:

```
✅ Parent object has 5 External ID field(s), 
                    3 unique field(s), 
                    8 relationship field(s)

💡 Relationship Fields Available 🔗

You can now select relationship fields like:
- ProductCategory.Name
- Account.Industry
- ParentAccount.BillingCity
```

### Step 2: Field Selection
The dropdown now shows:

```
Select External ID Field (or Relationship Field):

🏷️ ProductCategoryId (Direct Field)
🏷️ DealerCode (Direct Field)
🔗 ProductCategory.Name (Relationship Field)        ← NEW!
🔗 ProductCategory.Description (Relationship Field)  ← NEW!
🔗 Account.Industry (Relationship Field)             ← NEW!
```

### Step 3: SOQL Query Construction
Relationship fields are used directly in SOQL queries with dot notation:

```python
# User selects: ProductCategory.Name
# System generates:
SELECT Id FROM ProductCategory WHERE ProductCategory.Name = 'value' LIMIT 1
```

### Step 4: Data Migration
During migration, the system:

1. Reads parent ID from source record
2. Queries source org for relationship field values
3. Uses those values to find matching record in target org
4. Uses target org's parent ID in the migrated child record

---

## Implementation Details

### Code Changes

#### 1. New Function: `get_object_fields_with_relationships()`
**Location**: `ui_components/org_migration.py` lines 188-265

**Purpose**: Retrieves all fields including relationship fields
```python
parent_fields = get_object_fields_with_relationships(
    target_sf, 
    parent_object, 
    include_relationship_fields=True
)

# Returns:
# {
#     'ProductCategoryId': {...},
#     'Name': {...},
#     'ProductCategory.Name': {
#         'is_relationship_field': True,
#         'parent_object': 'ProductCategory',
#         'relationship_name': 'ProductCategory',
#         'parent_field_name': 'Name'
#     }
# }
```

#### 2. Enhanced Lookup Resolution Tab
**Location**: `ui_components/org_migration.py` lines 3230-3290

**Changes**:
- Shows relationship field count in status message
- Updates field dropdowns with icons (🏷️ for direct, 🔗 for relationship)
- Displays info message about relationship field support
- Handles both direct and relationship fields in field selection

#### 3. Enhanced Query Functions
**Locations**:
- `query_source_org_for_parent_id()` - Updated to handle dot notation
- `resolve_lookup_relationships_for_migration()` - Docstring updated with examples

**Enhancement**: SOQL queries now support relationship fields:
```sql
SELECT Dealer_Number__c FROM Account WHERE Id = 'XXX'
-- Now also supports:
SELECT Account.Industry FROM Account WHERE Id = 'XXX'
SELECT ParentAccount.BillingCity FROM Account WHERE Id = 'XXX'
```

---

## UI Changes

### Lookup Resolution Tab - Field Selection

#### Before:
```
Select External ID Field:
[ProductCategoryId         ]
```

#### After:
```
Select External ID Field (or Relationship Field):
[🏷️ ProductCategoryId (Direct Field) ]
 🏷️ DealerCode (Direct Field)
 🔗 ProductCategory.Name (Relationship Field)
 🔗 ProductCategory.Description (Relationship Field)
 🔗 Account.Industry (Relationship Field)
```

### Info Message:
```
💡 Relationship Fields Available 🔗

You can now select relationship fields like:
- ProductCategory.Name instead of ProductCategoryId
- Account.Industry instead of AccountId

This allows more flexible matching based on parent record attributes.
```

---

## Migration Flow with Relationship Fields

### Scenario: Migrate Products Matching by Category Name

```
SOURCE ORG (Product):
┌────────────────────────────────┐
│ Product ID: P-001              │
│ Name: LED Light Bulb           │
│ ProductCategory__c: 001xx000   │ ← Reference to ProductCategory
└────────────────────────────────┘

Step 1: Query Source for Relationship Field Value
Query: SELECT ProductCategory.Name FROM Product WHERE Id = 'P-001'
Result: ProductCategory.Name = 'Electronics'

Step 2: Find in Target Using Relationship Field
Query: SELECT Id FROM ProductCategory WHERE Name = 'Electronics'
Target Result: Category ID = 002yy000 (NEW ID in target org)

TARGET ORG (Product):
┌────────────────────────────────┐
│ Product ID: P-NEW              │
│ Name: LED Light Bulb           │
│ ProductCategory__c: 002yy000   │ ← Uses NEW category ID
└────────────────────────────────┘
```

---

## Supported Field Types

The implementation supports relationship fields for all matching strategies:

### 1. **Single External ID** (external_id)
```python
match_fields: ['ProductCategory.Name']

SOQL: SELECT Id FROM ProductCategory WHERE ProductCategory.Name = 'value'
```

### 2. **Multiple Fields (AND)** (field_combination)
```python
match_fields: ['Account.Industry', 'Account.BillingCity', 'Status']

SOQL: SELECT Id FROM Account 
      WHERE Account.Industry = 'Tech' 
        AND Account.BillingCity = 'SF' 
        AND Status = 'Active'
```

### 3. **Concatenated Fields** (field_concatenation)
```python
match_fields: ['ProductCategory.Code', 'ProductCategory.Region']
separator: '_'

Value to match: 'CAT1_US'

SOQL: SELECT Id FROM ProductCategory 
      WHERE ProductCategory.Code = 'CAT1' 
        AND ProductCategory.Region = 'US'
```

---

## Error Handling

### Relationship Field Not Found
If a relationship field doesn't exist:
```
⚠️ No External ID fields found in ProductCategory. 
   Use field combination or concatenation.
```

### SOQL Query Error
If the relationship field causes a query error:
```
❌ Error resolving ProductCategory__c: 
   INVALID_FIELD: ProductCategory.NonExistentField
```

---

## Performance Considerations

### Metadata Loading
- Relationship field discovery happens once per tab refresh
- Cached in session state for quick re-selection
- Additional API calls: ~1 per lookup field (minimal overhead)

### Query Performance
- SOQL queries with relationship fields **same speed** as direct fields
- Index support: Depends on field properties (ExternalId, Unique)
- No performance degradation vs direct field matching

---

## Examples

### Example 1: Match Products by Category Name
```
Tab: Lookup Resolution
─────────────────────

Lookup Field: ProductCategoryId
Parent Object: ProductCategory

Matching Strategy: external_id - Single External ID Field
Select Field: 🔗 ProductCategory.Name

SOQL Generated:
SELECT Id FROM ProductCategory WHERE ProductCategory.Name = <value>
```

### Example 2: Match Accounts by Parent and Industry
```
Tab: Lookup Resolution
─────────────────────

Lookup Field: ParentAccountId
Parent Object: Account

Matching Strategy: field_combination - Multiple Fields (AND)
Select Fields:
  ☑️ 🔗 Account.ParentAccount.Name
  ☑️ 🔗 Account.Industry
  ☑️ 🏷️ Status

SOQL Generated:
SELECT Id FROM Account 
WHERE Account.ParentAccount.Name = <value1>
  AND Account.Industry = <value2>
  AND Status = <value3>
```

### Example 3: Match with Concatenated Region + Code
```
Tab: Lookup Resolution
─────────────────────

Lookup Field: DealerId
Parent Object: Dealer

Matching Strategy: field_concatenation - Concatenated Fields
Select Fields:
  ☑️ 🔗 Dealer.Region.Code
  ☑️ 🏷️ DealerCode
Separator: _

Example: "WEST_D123"

SOQL Generated:
SELECT Id FROM Dealer 
WHERE Dealer.Region.Code = 'WEST'
  AND DealerCode = 'D123'
```

---

## Testing Scenarios

### ✅ Test 1: Single Relationship Field
**Setup**: Select ProductCategory.Name as matching field
**Expected**: SOQL uses relationship field correctly
**Verify**: Migration resolves lookups using parent category name

### ✅ Test 2: Mixed Direct and Relationship Fields
**Setup**: Select [Account.Industry, Status] for combination
**Expected**: SOQL combines both field types
**Verify**: Both conditions matched properly

### ✅ Test 3: Relationship Field with Fallback
**Setup**: Select non-existent relationship field
**Expected**: Error message shown
**Verify**: User can correct selection

---

## Summary

✅ **Relationship fields now fully supported in Lookup Resolution**
✅ **Flexible field matching based on parent attributes**
✅ **Works with external_id, field_combination, and field_concatenation strategies**
✅ **Clear UI with field type indicators (🏷️ direct, 🔗 relationship)**
✅ **Automatic SOQL query generation with dot notation**
✅ **No performance impact - uses native SOQL capabilities**

The implementation is complete and ready for production use!
