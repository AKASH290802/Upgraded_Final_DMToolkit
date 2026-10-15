# 📊 Data Hub - Quick Start Guide

## What is Data Hub?

**Data Hub** is a new centralized location to load your data **once** and use it across all toolkit modules.

**Before:** Upload file in Validation → Upload again in Data Operations → Upload again in Unit Testing

**After:** Load once in Data Hub → Use everywhere!

---

## Quick Start (5 minutes)

### Step 1: Load Data into Data Hub

1. In the **left sidebar**, click on **📊 Data Hub**

2. You'll see **Load Data** tab with two options:

   **Option A: Upload File**
   - Click "📄 Upload File"
   - Select your CSV or Excel file
   - Give it a name (e.g., "MyDataset")
   - Click "✅ Load into Hub"

   **Option B: Query Salesforce**
   - Click "⚙️ Query Salesforce"
   - Enter Object Name (e.g., `WOD_2__Rates_Details__c`)
   - Write SOQL Query (e.g., `SELECT Id, Name FROM WOD_2__Rates_Details__c LIMIT 1000`)
   - Click "🚀 Execute SOQL"
   - Click "✅ Add to Hub"

### Step 2: Use Data in Other Modules

Your data is now **automatically available** in all modules!

- Go to **1️⃣ Validation** → Data is ready to use
- Go to **2️⃣ Data Operations** → Data is ready to use
- Go to **3️⃣ Unit Testing** → Data is ready to use

### Step 3: Switch Between Datasets

Need to work with a different dataset?

1. Go back to **📊 Data Hub**
2. Click on **💾 Manage Datasets** tab
3. Click "✓ Set Active" on the dataset you want
4. All modules automatically switch to that dataset

---

## Features Overview

### 📥 Load Data
- Upload CSV or Excel files
- Execute SOQL queries directly
- Name your datasets

### 💾 Manage Datasets
- See all loaded datasets
- Preview data
- Download data
- Switch between datasets
- Delete datasets

### 📋 Active Dataset
- See current dataset info
- View data preview
- Download as CSV or Excel
- Check metadata (rows, columns, source)

---

## Example Workflow

### Scenario: Validate Multiple Files

**Traditional Approach:**
1. Upload File 1 → Validate → Download results
2. Upload File 2 → Validate → Download results
3. Upload File 3 → Validate → Download results

**With Data Hub:**
1. **Load File 1** in Data Hub
2. **Go to Validation** → Process file 1 → Download
3. **Back to Data Hub** → Switch to File 2 (one click!)
4. **Back to Validation** → Process file 2 → Download
5. **Back to Data Hub** → Switch to File 3
6. **Back to Validation** → Process file 3 → Download

**Time Saved:** No re-uploading, just switch and validate!

---

## Supported File Types

✅ **CSV** (.csv)
✅ **PSV** (.psv) - Pipe-Separated Values
✅ **Excel** (.xlsx, .xls)

---

## SOQL Query Examples

### Basic Query
```sql
SELECT Id, Name FROM Account LIMIT 100
```

### With Filters
```sql
SELECT Id, Name, Amount__c FROM WOD_2__Rates_Details__c 
WHERE Status__c = 'Active' 
LIMIT 1000
```

### With Multiple Fields
```sql
SELECT Id, Name, Email, Phone FROM Contact 
WHERE Status__c IN ('Active', 'Pending') 
LIMIT 500
```

---

## Common Tasks

### Upload a File
1. Go to **📊 Data Hub**
2. Click **📄 Upload File**
3. Choose your CSV/Excel file
4. Name it
5. Click "✅ Load into Hub"
✅ **Done!** Data is ready to use

### Query Salesforce
1. Go to **📊 Data Hub**
2. Click **⚙️ Query Salesforce**
3. Enter object name
4. Write SOQL query
5. Click "🚀 Execute SOQL"
6. Click "✅ Add to Hub"
✅ **Done!** Data is ready to use

### Switch to Different Data
1. Go to **📊 Data Hub**
2. Click **💾 Manage Datasets**
3. Find the dataset you want
4. Click "✓ Set Active"
✅ **Done!** All modules now use this data

### Download Data
1. Go to **📊 Data Hub**
2. Click **📋 Active Dataset**
3. Scroll down to "Download Active Dataset"
4. Click "📄 Download as CSV" or "📊 Download as Excel"
✅ **Done!** File downloaded

---

## Tips & Tricks

💡 **Name datasets descriptively**
- Instead of "File1", use "WOD_2_Rates_December_2024"
- Makes it easy to find later

💡 **Check data preview before processing**
- Click "📊 Preview" next to dataset
- Verify it's the right data
- Check row count and columns

💡 **Use meaningful SOQL queries**
- Add WHERE clauses to filter
- Use LIMIT to avoid huge datasets
- Test your query first

💡 **Keep datasets organized**
- Delete old/test datasets
- Keep only what you need
- Clean up when done

---

## Troubleshooting

### "No active dataset" Error
**Solution:** Go to Data Hub and load data (file or SOQL query)

### File Won't Upload
**Solution:** 
- Check file is CSV or Excel
- File size should be reasonable (<100MB)
- Try renaming file if it has special characters

### SOQL Query Fails
**Solution:**
- Check object name spelling (case-sensitive for custom objects)
- Verify field names exist in object
- Try adding LIMIT clause
- Test with simple query first: `SELECT Id, Name FROM YourObject LIMIT 10`

### Data Not Showing in Other Modules
**Solution:**
- Check **Active Dataset** shows data
- Refresh the module page (F5)
- Try switching to another dataset and back

---

## Next Steps

After loading data:

1. **Validate Data** → Go to **1️⃣ Validation** tab
2. **Transform Data** → Go to **2️⃣ Data Operations** tab
3. **Test Rules** → Go to **3️⃣ Unit Testing** tab
4. **Map Fields** → Go to **🗺️ Mapping** tab

---

## Keyboard Shortcuts

- **Switch module:** Use sidebar radio buttons or click module name
- **Refresh page:** F5
- **Go to Data Hub:** Click sidebar → **📊 Data Hub**

---

## Video Tutorial

For visual guide, see the Data Hub demo (if available in your toolkit)

---

## Questions?

Refer to **DATA_HUB_INTEGRATION_GUIDE.md** for detailed documentation
