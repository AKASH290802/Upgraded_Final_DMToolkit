"""
Object Dataset Builder — derives one DataFrame per selected Salesforce object
from the single uploaded source file, using the finalized field assignments.
"""
import pandas as pd

from .models import MultiObjectPlan

# Kept on every derived dataset so validation errors can be traced back to
# the exact row in the client's original uploaded file.
SOURCE_ROW_ID_COL = "_source_row_id"


def add_source_row_id(df: pd.DataFrame) -> pd.DataFrame:
    if SOURCE_ROW_ID_COL not in df.columns:
        df = df.copy()
        df.insert(0, SOURCE_ROW_ID_COL, range(1, len(df) + 1))
    return df


def build_object_dataset(df: pd.DataFrame, plan: MultiObjectPlan, object_name: str) -> pd.DataFrame:
    """Select and rename the columns assigned to `object_name`."""
    assignments = [a for a in plan.assignments_for(object_name) if a.assigned_field]
    if not assignments:
        return pd.DataFrame()

    rename_map = {a.source_column: a.assigned_field for a in assignments}
    cols_to_take = [c for c in ([SOURCE_ROW_ID_COL] + list(rename_map.keys())) if c in df.columns]

    return df[cols_to_take].rename(columns=rename_map)


def build_all_object_datasets(df: pd.DataFrame, plan: MultiObjectPlan) -> dict[str, pd.DataFrame]:
    df = add_source_row_id(df)
    return {
        obj.object_name: build_object_dataset(df, plan, obj.object_name)
        for obj in plan.selected_objects
    }
