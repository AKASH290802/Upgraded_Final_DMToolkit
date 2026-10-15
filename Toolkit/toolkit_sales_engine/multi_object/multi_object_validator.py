"""
Multi Object Validator — lightweight, self-contained schema validation for
per-object datasets produced by the Multi Data File workflow.

Re-implements the core checks (required fields, max length, picklist values)
directly against Salesforce describe() metadata, rather than importing the
large validation_operations.py Streamlit page module, to keep this package
UI-independent and avoid coupling to other tabs.
"""
import pandas as pd

from .models import ObjectValidationResult
from .object_dataset_builder import SOURCE_ROW_ID_COL


def validate_object_dataset(sf_conn, object_name: str, df: pd.DataFrame) -> ObjectValidationResult:
    if df is None or df.empty:
        return ObjectValidationResult(object_name, 0, 0, 0, 0, [])

    try:
        describe = getattr(sf_conn, object_name).describe()
    except Exception as exc:
        return ObjectValidationResult(object_name, len(df), 0, len(df), 0,
                                       [{"source_row_id": None, "errors": [f"Could not describe object: {exc}"]}])

    field_meta = {f["name"]: f for f in describe.get("fields", [])}
    mapped_fields = [c for c in df.columns if c != SOURCE_ROW_ID_COL]

    required_fields = [
        name for name, f in field_meta.items()
        if not f.get("nillable", True) and f.get("createable", False) and name in mapped_fields
    ]

    error_rows: list[dict] = []

    for _, row in df.iterrows():
        row_errors = []
        source_row_id = row.get(SOURCE_ROW_ID_COL)

        for req_field in required_fields:
            value = row.get(req_field)
            if pd.isna(value) or str(value).strip() == "":
                row_errors.append(f"Required field '{req_field}' is missing")

        for col in mapped_fields:
            meta = field_meta.get(col)
            if not meta:
                continue
            value = row.get(col)
            if pd.isna(value) or str(value).strip() == "":
                continue

            max_len = meta.get("length")
            if max_len and meta.get("type") in ("string", "textarea") and len(str(value)) > max_len:
                row_errors.append(f"'{col}' exceeds max length {max_len}")

            if meta.get("type") == "picklist":
                picklist_values = [pv["value"] for pv in meta.get("picklistValues", []) if pv.get("active", True)]
                if picklist_values and str(value) not in picklist_values:
                    row_errors.append(f"'{col}' value '{value}' is not a valid picklist option")

        if row_errors:
            error_rows.append({"source_row_id": source_row_id, "errors": "; ".join(row_errors)})

    failed = len(error_rows)
    passed = len(df) - failed

    return ObjectValidationResult(
        object_name=object_name,
        total_records=len(df),
        passed=passed,
        failed=failed,
        warnings=0,
        error_rows=error_rows,
        validated_df=df,
    )
