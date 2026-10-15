# RecordType Selection Feature - Quick Reference

## ✨ What Changed?

**Before**: All Warranty Code data loaded as "Failure Code" (default)
**After**: You select which RecordType each file should load as

---

## 🚀 How to Use

### Step 1: Open Data Loading
- Go to **Data Operations** tab
- Scroll to **Load to Salesforce** section

### Step 2: Select Object
```
Target Object: [Warranty Code]
✅ Target Object: Warranty Code
```

### Step 3: **[NEW]** Select Record Type
```
📋 Select Record Type (Optional)

Record Type: [-- Use Default -- ▼]
              - Failure Code
              - Resolution Code
              - Failure - Resolution Code
              - -- Use Default --
```

### Step 4: Choose Your RecordType
**Example - For Failure Code Data:**
```
Record Type: [Failure Code]
✅ Will load data with Record Type: Failure Code
   (ID: 0121x0000123ABC)
```

### Step 5: Upload and Load as Normal
- Upload your CSV file
- Map fields
- Click "Start Loading"
- ✅ All records created with selected RecordType!

---

## 📊 Use Cases

### ✅ Load Failure Code Data
```
1. Select Target Object: Warranty Code
2. Select Record Type: Failure Code
3. Upload failure_code_data.csv
4. Load normally
Result: All records = Failure Code RecordType
```

### ✅ Load Resolution Code Data
```
1. Select Target Object: Warranty Code
2. Select Record Type: Resolution Code
3. Upload resolution_code_data.csv
4. Load normally
Result: All records = Resolution Code RecordType
```

### ✅ Load Combination Data
```
1. Select Target Object: Warranty Code
2. Select Record Type: Failure - Resolution Code
3. Upload combination_data.csv
4. Load normally
Result: All records = Combination RecordType
```

### ✅ Use Default RecordType
```
1. Select Target Object: Warranty Code
2. Select Record Type: -- Use Default --
3. Upload any_data.csv
4. Load normally
Result: Uses Salesforce's backend default
```

---

## 💡 Key Points

| Item | Details |
|------|---------|
| **Location** | Data Loading Tab |
| **When to Use** | When your object has multiple RecordTypes |
| **Selection** | Before uploading data |
| **Effect** | All records in file get same RecordType |
| **Optional** | Yes - can leave as "Use Default" |
| **Files Changed** | Only data_operations.py |
| **Other Tabs** | Unchanged ✅ |

---

## ⚠️ Important Notes

### Only One RecordType Per File
- Each file upload uses ONE RecordType
- If you have mixed RecordType data, upload separate files
- Each file: Select RecordType → Upload → Load

### RecordType is Added Automatically
- You don't add it manually
- System adds RecordTypeId field automatically
- Your CSV stays as-is (Name, Description, Business_Unit)

### What Gets Added
```
Your CSV columns:
Name, Description, Business_Unit

System adds:
Name, Description, Business_Unit, RecordTypeId

Salesforce receives all fields
```

---

## ✅ Verification

After loading, verify in Salesforce:
1. Go to Warranty Code object
2. View loaded records
3. Check "Record Type" column
4. Should show: "Failure Code" or "Resolution Code" or "Failure - Resolution Code"

---

## 🆘 Troubleshooting

### Issue: Don't see RecordType dropdown
- Make sure you selected the target object first
- Try refreshing the page

### Issue: No RecordTypes shown in dropdown
- The object might not have custom RecordTypes
- Check Salesforce org configuration
- Can still use "-- Use Default --"

### Issue: Want to load multiple RecordTypes
- Upload separate files for each RecordType
- Select appropriate RecordType for each file
- Load them sequentially

---

## 🎯 Summary

**You can now:**
- ✅ Load Failure Code data → Failure Code RecordType
- ✅ Load Resolution Code data → Resolution Code RecordType
- ✅ Load Combination data → Failure-Resolution Code RecordType
- ✅ No more unexpected default RecordTypes
- ✅ Simplified, one-step RecordType selection

**That's it!** The feature is ready to use.
