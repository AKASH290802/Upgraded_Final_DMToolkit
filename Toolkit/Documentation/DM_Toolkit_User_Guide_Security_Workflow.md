# DM Toolkit - Complete User Guide & Workflow Hierarchy

## 🔒 **SECURE DATA MIGRATION WORKFLOW - Step-by-Step Guide**

### **🚨 CRITICAL PRINCIPLE: Data Loading ONLY After Complete Validation**

This guide provides a detailed, hierarchical workflow that ensures data integrity and security. **Follow each step in sequence - never skip validation before loading data!**

---

## 🏗️ **Application Overview** {#application-overview}

### **🔄 DM Toolkit Modules & Their Purpose**

```
📋 MODULE HIERARCHY & PURPOSE:
├── 🏠 Dashboard           → System overview & health monitoring
├── ⚙️ Configuration       → Setup organizations & connections
├── 📥 Data Operations     → Extract data & Load data (after validation only)
├── 🗺️ Mapping            → View & analyze field mappings for objects
├── ✅ Validation          → Validate data BEFORE loading (MANDATORY)
├── 🧪 Unit Testing        → Generate/Execute tests for quality assurance
└── 📋 Logs & Reports      → Monitor activities & audit trails
```

### **🔐 Security Flow Control**

```
SECURE WORKFLOW CONTROL:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Extract  │───▶│  Mapping View  │───▶│   Validation    │
│   (Safe - Read  │    │   (Analysis)    │    │   (MANDATORY)   │
│   Only)         │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Unit Testing  │◀───│   Data Loading │◀───│   Validation    │
│   (Quality      │    │   (Only After   │    │   PASSED ✅     │ 
│   Assurance)    │    │   Validation)   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```
Note: If any data fails the Validation Rules, then check with the Client or the user who provided the CSV/Excel data file and ask to provide valid data.

---

## ⚙️ **Initial Setup & Configuration** {#initial-setup}

### **Step 0: Application Launch**

1. **Start the Application**:
   ```
   Will be given with a document on how to install the application in your local. 
   ```
### **Step 1: Organization Selection (MANDATORY FIRST STEP)**

**🏢 BEFORE ANYTHING ELSE: Select Your Salesforce Organization**

1. **Look at the Sidebar** → Find "🏢 Select Organization"
2. **Choose Your Target Org** from the dropdown
3. **Verify Connection Status** → Should show green checkmark
4. **Note**: All subsequent operations will use this organization

*** You can either add a new salesforce org or establish a SQL Server connection by giving the credentials--> For that go to Configuration tab and proceed with ➕ Add New Salesforce Organization or ➕ Add New SQL Server Database Connection as per your requirement.

**🔒 Security Check:**
- [ ] Correct organization selected
- [ ] Connection established successfully
- [ ] User has appropriate permissions

---

## 🚀 **Complete Workflow Hierarchy** {#workflow-hierarchy}

### **📊 PHASE 1: DATA DISCOVERY & PREPARATION**

#### **Step 1.1: Navigate to 📥 Data Operations → Data Extraction**

**PURPOSE**: Extract data to understand structure and prepare for validation

**What You Can Do Here:**
```
🔍 DATA EXTRACTION OPTIONS:

Option A: Extract from Salesforce (Recommended First)
├── Purpose: See existing data structure in your org
├── Action: Run SOQL queries to extract current data
├── Security: Read-only operation - completely safe
└── Result: CSV/Excel files for analysis

Option B: Extract from SQL Server
├── Purpose: Get data from legacy database systems
├── Action: Connect to SQL database and extract
├── Security: External system - verify credentials
└── Result: Data files ready for Salesforce migration

Option C: Upload File (CSV/Excel)
├── Purpose: Prepare external data files for migration
├── Action: Upload your prepared data files
├── Security: Local file processing only
└── Result: Data ready for mapping and validation
```

**🎯 What Happens After Extraction:**
- Data is analyzed for structure and quality
- Column types and formats are identified
- Sample data is displayed for review
- **NO DATA IS LOADED TO SALESFORCE YET**

**Next Step**: Proceed to Mapping to understand field relationships

---

### **📊 PHASE 2: FIELD MAPPING ANALYSIS**

#### **Step 2.1: Navigate to 🗺️ Mapping**

**PURPOSE**: Understand how your data fields map to Salesforce object fields

**What You Can Do Here:**
```
🗺️ MAPPING OPERATIONS:

Tab 1: Generate Mapping
├── Purpose: Create new field mapping for a Salesforce object
├── Action: Select object → Choose mapping strategy → Generate
├── Strategies Available:
│   ├── 🤖 Auto-detect: AI analyzes your data and suggests mappings
│   ├── 📋 Standard: Use common field patterns (Name→Name, Email→Email)
│   └── ✏️ Custom: Manually define each field mapping
└── Result: Mapping file showing Source Field → Salesforce Field

Tab 2: View Mappings
├── Purpose: Browse existing mapping configurations
├── Action: Select org → Select object → View mapping details
└── Result: See all previously created mappings

Tab 3: Edit Mapping
├── Purpose: Modify existing field mappings
├── Action: Load mapping → Make changes → Save updated version
└── Result: Updated mapping configuration

Tab 4: Mapping Analytics
├── Purpose: Analyze mapping quality and coverage
├── Action: Review mapping statistics and recommendations
└── Result: Quality score and improvement suggestions
```

**🔍 Detailed Mapping Process:**

1. **Select Target Object**: Choose the Salesforce object (Account, Contact, Custom Object, etc.)
2. **Choose Mapping Strategy**:
   - **Auto-detect**: Upload your data file, system analyzes and suggests mappings
   - **Standard**: System uses common field name patterns
   - **Custom**: You manually select each mapping
3. **Review Generated Mapping**: See how your CSV columns map to Salesforce fields
4. **Download Mapping File**: Save as JSON for future use

**🔒 Security Note**: This is analysis only to check with the mapping of Fields like which fields of source gets mapped to which fields of salesforce.

**Next Step**: Proceed to Validation to ensure data quality

---

### **📊 PHASE 3: COMPREHENSIVE VALIDATION (MANDATORY GATE)**

#### **Step 3.1: Navigate to ✅ Validation**

**🚨 CRITICAL: This is your SECURITY GATE - No data loading without passing validation!**

**What You Can Do Here:**
```
✅ VALIDATION OPERATIONS (All Must Pass):

Tab 1: Schema Validation
├── Purpose: Validate data structure and field compatibility
├── Checks Performed:
│   ├── ✓ Required fields have data
│   ├── ✓ Data types match Salesforce field types
│   ├── ✓ Field lengths within limits
│   ├── ✓ Email formats are valid
│   ├── ✓ Date formats are correct
│   ├── ✓ Picklist values are valid
│   └── ✓ Reference fields exist in related objects
├── Action: Upload data file → Select object → Run validation
└── Result: Pass/Fail report with detailed issues

Tab 2: Custom Validation
├── Purpose: Validate against Salesforce business rules
├── Checks Performed:
│   ├── ✓ Salesforce validation rules compliance
│   ├── ✓ Workflow rule requirements
│   ├── ✓ Custom business logic validation
│   └── ✓ Territory and assignment rules
├── Action: Extract SF rules → Apply to your data → Review results
└── Result: Business rule compliance report

Tab 3: GenAI Validation (Advanced)
├── Purpose: AI-powered validation using natural language rules
├── Checks Performed:
│   ├── ✓ Pattern recognition and anomaly detection
│   ├── ✓ Complex business logic validation
│   ├── ✓ Data quality scoring
│   └── ✓ Intelligent error detection
├── Action: Define AI rules → Generate validation bundle → Run validation
└── Result: AI-powered quality assessment

Tab 4: Validation Reports
├── Purpose: Review all validation results and history
├── Information Available:
│   ├── 📊 Summary of all validation runs
│   ├── 📈 Success/failure rates over time
│   ├── 🔍 Detailed error analysis
│   └── 📋 Recommendations for improvement
└── Result: Comprehensive validation dashboard
```

**🔍 Detailed Validation Process:**

1. **Schema Validation (Start Here)**:
   - Upload your data file
   - Select target Salesforce object
   - System checks every field for compatibility
   - Review detailed validation report
   - Fix any issues in your source data

2. **Custom Validation**:
   - System extracts Salesforce validation rules for your object
   - Your data is tested against these business rules
   - Only on basis of error message defined it analyzes the error message or description and gives valid and Invalid records--> if error messages are complex it might consider that also as Valid. So GenAI Validation is essential.

3. **GenAI Validation (Mandatory & Recommended)**:
   - Gets the validation rules along with their apex formulas
   - AI converts rules to executable validation code
   - Against the Validation code generated, it will validated the data in the uploaded file.


**🚫 IF VALIDATION FAILS**: 
- **DO NOT PROCEED** to data loading
- Fix issues in source data
- Re-run validation until all checks pass

---

### **📊 PHASE 4: AUTHORIZED DATA LOADING (POST-VALIDATION ONLY)**

#### **Step 4.1: Return to 📥 Data Operations → Data Loading**

**🔐 NOW UNLOCKED: Data loading operations after successful validation**

**What You Can Do Here:**
```
📥 DATA LOADING OPERATIONS (VALIDATION-AUTHORIZED):

✅ PRE-LOADING VERIFICATION:
├── ✓ Schema validation passed
├── ✓ Custom validation completed
├── ✓ Unit tests executed successfully
├── ✓ All quality gates satisfied
└── ✓ Stakeholder approval obtained

Loading Options Available:

Option A: Load to Salesforce (Primary Function)
├── Purpose: Load validated data to your Salesforce org
├── What It Does:
│   ├── 🔍 Verifies target object selection
│   ├── 📊 Analyzes data quality one final time
│   ├── 🗺️ Applies field mappings from validation
│   ├── ⚙️ Configures batch processing options
│   ├── 🔄 Performs controlled data loading
│   └── 📈 Provides real-time progress monitoring
├── Loading Configuration:
│   ├── Operation Type: Insert (new records) or Upsert (insert/update)
│   ├── Batch Size: 200 records recommended for safety
│   ├── Error Handling: Stop on error vs Continue processing
│   └── Duplicate Handling: Based on business rules
├── Action: Upload validated data → Configure options → Execute load
└── Result: Successful data loading with comprehensive reports

Option B: Load to SQL Server
├── Purpose: Load data to SQL database for backup or integration
├── Action: Configure SQL connection → Map tables → Load data
└── Result: Data successfully loaded to SQL database
```

**🔍 Detailed Data Loading Process:**

1. **Final Verification**:
   - Confirm all validations passed
   - Verify correct target object selected
   - Review field mappings one final time

2. **Upload Validated Data**:
   - Use ONLY the data files that passed validation
   - System verifies data integrity before loading

3. **Configure Loading Options**:
   - **Insert vs Upsert**: Choose based on whether records might already exist
   - **Batch Size**: 200 records recommended for monitoring and rollback capability
   - **Error Handling**: Stop on first error recommended for safety

4. **Monitor Loading Process**:
   - Real-time progress tracking
   - Immediate error notifications
   - Success/failure counts per batch
   - Governor limit monitoring

5. **Post-Load Verification**:
   - Verify record counts match expectations
   - Sample check loaded data for accuracy
   - Confirm no data corruption occurred

**🔒 Security During Loading:**
- Continuous monitoring for errors
- Automatic rollback capability if critical issues
- Complete audit trail of all operations
- Performance monitoring to prevent system impact

**Next Step**: After successful data loading, you can proceed to generate test cases.

---

### **📊 PHASE 5: QUALITY ASSURANCE TESTING**

#### **Step 5.1: Navigate to 🧪 Unit Testing**

**PURPOSE**: Generate and execute comprehensive tests to ensure system reliability

**What You Can Do Here:**
```
🧪 UNIT TESTING OPERATIONS:

Tab 1: Generate Tests
├── Purpose: Create comprehensive test cases for your object
├── What It Does:
│   ├── 🔍 Analyzes your selected Salesforce object
│   ├── 🧪 Generates test cases for all field types
│   ├── ✅ Creates validation tests for business rules
│   ├── ⚡ Builds performance tests for data loading
│   ├── 🔒 Includes security and error handling tests
│   └── 📊 Provides comprehensive test documentation
├── Configuration Options:
│   ├── Test Types: Data Loading, Schema, Business Rules, Integration
│   ├── Coverage Level: Basic, Comprehensive, Full Coverage
│   ├── Include Negative Tests: Error scenarios and edge cases
│   └── Sample Size: Number of test records to generate
├── Action: Select object → Configure tests → Generate test suite
└── Result: Professional test suite with detailed documentation

Tab 2: Execute Tests
├── Purpose: Run existing test suites to verify system quality
├── What It Does:
│   ├── 🏃 Executes all test cases in selected test suite
│   ├── 📊 Provides real-time progress monitoring
│   ├── ✅ Shows pass/fail results for each test
│   ├── 📈 Generates performance metrics
│   ├── 🔍 Identifies any system issues
│   └── 📋 Creates detailed execution reports
├── Execution Options:
│   ├── Parallel Execution: Run tests simultaneously for speed
│   ├── Fail Fast: Stop on first failure for quick feedback
│   ├── Log Level: Control detail level of execution logs
│   └── Timeout: Set maximum execution time
├── Action: Select test suite → Configure execution → Run tests
└── Result: Comprehensive test execution report with recommendations

Tab 3: Test Reports
├── Purpose: Review test history and analyze trends
├── Information Available:
│   ├── 📊 Test execution history and trends
│   ├── 📈 Success rates over time
│   ├── 🔍 Failed test analysis and patterns
│   ├── 📋 Test coverage analysis
│   └── 💡 Recommendations for improvement
└── Result: Complete testing dashboard and insights
```

**🔍 Detailed Unit Testing Process:**

1. **Generate Tests (Recommended for New Objects)**:
   - Select your Salesforce object
   - Choose test coverage level (Comprehensive recommended)
   - Include negative tests and edge cases
   - System generates 15-25 professional test cases
   - Download test suite for documentation

2. **Execute Tests (For Quality Verification)**:
   - Select appropriate test suite for your object
   - Configure execution parameters
   - Monitor real-time test execution
   - Review pass/fail results (>95% pass rate required)
   - Download execution reports

**🎯 Testing Success Criteria:**
- ✅ Test generation completed successfully
- ✅ Test execution shows >95% pass rate
- ✅ No critical failures detected
- ✅ Performance tests within acceptable limits

----

### **📊 PHASE 6: MONITORING & AUDIT REVIEW**

#### **Step 6.1: Navigate to 📋 Logs & Reports**

**PURPOSE**: Monitor all activities and maintain comprehensive audit trails

**What You Can Do Here:**
```
📋 MONITORING & REPORTING OPERATIONS:

Tab 1: Processing Logs
├── Purpose: Review detailed logs of all system operations
├── Information Available:
│   ├── 📤 Data extraction activities and results
│   ├── 🗺️ Mapping generation and modifications
│   ├── ✅ Validation execution results and issues
│   ├── 🧪 Unit testing generation and execution
│   ├── 📥 Data loading operations and outcomes
│   └── 🔍 Error details and resolution steps
├── Filtering Options:
│   ├── By Date Range: Focus on specific time periods
│   ├── By Module: See logs from specific operations
│   ├── By Log Level: Info, Warning, Error, Critical
│   └── By Organization: Filter by target Salesforce org
└── Result: Detailed operational history and audit trail

Tab 2: Activity Reports
├── Purpose: Analyze system usage and performance metrics
├── Reports Available:
│   ├── 📊 Operation success/failure rates over time
│   ├── 👥 User activity and access patterns
│   ├── ⚡ System performance and response times
│   ├── 📈 Data volume processing trends
│   └── 🎯 Quality metrics and improvements
└── Result: Business intelligence and performance insights

Tab 3: Error Analysis
├── Purpose: Analyze errors and identify improvement opportunities
├── Analysis Available:
│   ├── 🔍 Error categorization and frequency
│   ├── 📊 Root cause analysis and patterns
│   ├── 💡 Resolution recommendations
│   ├── 🛡️ Preventive measures suggestions
│   └── 📈 Error trend analysis over time
└── Result: Proactive error prevention and system improvement

Tab 4: File Management
├── Purpose: Manage all data files and generated reports
├── Functions Available:
│   ├── 📁 Browse all generated files by organization
│   ├── 📥 Download any file for external use
│   ├── 🔍 Preview file contents without downloading
│   ├── 🗑️ Clean up old files to save space
│   └── 📊 File usage statistics and storage metrics
└── Result: Organized file management and storage optimization

Tab 5: System Diagnostics
├── Purpose: Monitor system health and performance
├── Diagnostics Available:
│   ├── 🔧 System resource utilization monitoring
│   ├── 🌐 Network connectivity and API health checks
│   ├── 💾 Database connection and performance status
│   ├── 🔒 Security monitoring and access controls
│   └── ⚠️ Alert conditions and thresholds
└── Result: Proactive system health management
```

**🔍 What to Monitor After Data Loading:**

1. **Processing Logs**: Verify all operations completed successfully
2. **Activity Reports**: Confirm data loading metrics are within expectations
3. **Error Analysis**: Review any errors and implement preventive measures
4. **File Management**: Organize and archive all related files
5. **System Diagnostics**: Ensure system remains healthy after operations

---

## 🚨 **Common User Questions & Answers** {#troubleshooting}

### **Q: When should I use each module?**

**A: Follow this exact sequence:**

1. **🏠 Dashboard**: Start here to check system status
2. **⚙️ Configuration**: Select your Salesforce organization
3. **📥 Data Operations (Extract)**: Get your data for analysis
4. **🗺️ Mapping**: Understand field relationships (can skip if not needed)
5. **✅ Validation**: MANDATORY - validate all data quality
6. **🧪 Unit Testing**: Verify system reliability
7. **📥 Data Operations (Load)**: NOW authorized for data loading.
8. **📋 Logs & Reports**: Monitor and audit all activities

### **Q: What's the difference between Mapping and Validation?**

**A: Different purposes entirely:**

**🗺️ Mapping**:
- **Purpose**: Analyze and understand field relationships
- **Action**: Shows how CSV columns map to Salesforce fields
- **Security**: Read-only analysis, no data movement
- **Result**: Mapping configuration file for reference

**✅ Validation**:
- **Purpose**: Quality gate to ensure data is safe to load
- **Action**: Tests data against schema and business rules
- **Security**: Prevents bad data from reaching Salesforce
- **Result**: Pass/fail determination for data loading authorization

### **Q: Can I skip validation and go straight to loading?**

**A: NO! Absolutely not!**
- Validation is a security gate that cannot be bypassed
- Loading operations are locked until validation passes
- This prevents data corruption and system damage
- Always validate first, then load

### **Q: What if validation fails?**

**A: Fix the issues and re-validate:**
1. **Review validation report** to understand specific failures
2. **Fix issues in source data** (correct formats, fill required fields, etc.)
3. **Re-run validation** with corrected data
4. **Only proceed to loading** when validation shows >95% pass rate

### **Q: Generate Tests vs Execute Tests - what's the difference?**

**A: Two different functions:**

**🔧 Generate Tests**:
- **Purpose**: Create new test cases for an object
- **When to Use**: First time working with an object, or need comprehensive tests
- **Result**: Professional test suite with detailed documentation

**🏃 Execute Tests**:
- **Purpose**: Run existing test cases to verify quality
- **When to Use**: Have existing test suite, want to verify system reliability
- **Result**: Pass/fail results and performance metrics

### **Q: How do I know if my data is ready for loading?**

**A: Check these indicators:**

```
✅ READY FOR LOADING:
├── ✅ Schema validation >95% pass rate
├── ✅ Custom validation all rules passed
├── ✅ Unit tests >95% pass rate
├── ✅ No critical errors in any validation
├── ✅ Stakeholder approval obtained
└── ✅ Target environment verified

❌ NOT READY FOR LOADING:
├── ❌ Any validation <95% pass rate
├── ❌ Critical errors detected
├── ❌ Business rules violated
├── ❌ Test failures present
└── ❌ Missing approvals or verifications
```

---

## 📞 **Support & Best Practices**

### **Best Practices for Success**

1. **Always Start Small**: Test with 100-500 records first
2. **Use Sandbox First**: Never test in production
3. **Validate Everything**: Don't skip any validation steps
4. **Monitor Continuously**: Watch for errors and performance issues
5. **Document Everything**: Keep records of all mappings and validations
6. **Plan for Rollback**: Always have a backup and recovery plan

### **Performance Optimization**

- **Batch Size**: Use 200 records for safety, 500-1000 for speed
- **Off-Peak Hours**: Schedule large loads during low-usage times
- **Governor Limits**: Monitor API usage and stay under limits
- **Error Handling**: Stop on first error for data integrity

### **Security Best Practices**

- **Least Privilege**: Use minimum required permissions
- **Audit Trail**: Maintain complete logs of all operations
- **Data Classification**: Identify and protect sensitive data
- **Validation First**: Never compromise on validation requirements

---

**🔒 Remember: Validation is your safety net - never bypass it for convenience!**

*This documentation provides your complete guide to secure, validated, and successful data operations using the DM Toolkit. Follow the hierarchy, respect the validation gates, and maintain comprehensive audit trails.*

---

**Document Version**: 2.0  
**Last Updated**: October 30, 2025  
**Next Review**: December 30, 2025
