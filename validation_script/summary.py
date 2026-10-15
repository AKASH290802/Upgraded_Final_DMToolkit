import sys
sys.path.append(r"C:\DM_toolkit")  # Add project root to sys.path
import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import dataset.Org_selection as Org_selection

rootfolder="DataFiles"
object_name=input("Enter object name:   ")
selected_org=Org_selection.org_select()
object_folder = os.path.join(rootfolder, selected_org, object_name)
mapping_paths=os.path.join(object_folder,"details.csv")
data_path=os.path.join(object_folder,f'sql_{selected_org}__{object_name}.csv')

mapping_df=pd.read_csv(mapping_paths)
data_df=pd.read_csv(data_path)
df=data_df.copy()
total_records = len(df)

summary = []

# Loop through columns to check for issues
for col in df.columns:
    # Count duplicates (excluding first occurrence)
    duplicate_count = df.duplicated(subset=[col]).sum()
    null_count = df[col].isnull().sum()

    if duplicate_count > 0:
        summary.append({
            'Column Name': col,
            'Issue': 'Duplicate',
            'Count': duplicate_count,
            'Total Records': total_records
        })

    if null_count > 0:
        summary.append({
            'Column Name': col,
            'Issue': 'Null',
            'Count': null_count,
            'Total Records': total_records
        })

# Convert to DataFrame
summary_df = pd.DataFrame(summary)

# Save to Excel
output_file = os.path.join(object_folder, 'column_issues_summary.xlsx')
summary_df.to_excel(output_file, index=False)

print(f"Summary saved to: {output_file}")
