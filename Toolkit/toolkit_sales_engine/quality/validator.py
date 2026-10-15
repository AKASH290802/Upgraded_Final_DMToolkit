"""
Data Quality Validator — 10 deterministic checks per cell.
No LLM involved.
"""
import re
import logging
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from ..metadata.models import FieldMeta, DataType

logger = logging.getLogger(__name__)


class FieldViolation:
    def __init__(self, row_index: int, field_name: str, value: Any, rule: str, message: str):
        self.row_index = row_index
        self.field_name = field_name
        self.value = str(value) if value is not None else "NULL"
        self.rule = rule
        self.message = message

    def to_dict(self) -> dict:
        return {"row": self.row_index, "field": self.field_name,
                "value": self.value, "rule": self.rule, "message": self.message}


class FieldQualityResult:
    def __init__(self, source_column: str, target_field: str):
        self.source_column = source_column
        self.target_field = target_field
        self.total_rows = 0
        self.passed = 0
        self.failed = 0
        self.violations: list[FieldViolation] = []

    @property
    def pass_rate(self) -> float:
        if self.total_rows == 0: return 1.0
        return round(self.passed / self.total_rows, 4)

    def to_dict(self) -> dict:
        return {"source_column": self.source_column, "target_field": self.target_field,
                "total_rows": self.total_rows, "passed": self.passed, "failed": self.failed,
                "pass_rate": self.pass_rate,
                "violations": [v.to_dict() for v in self.violations[:50]]}


class QualityReport:
    def __init__(self, upload_id: str, object_name: str):
        self.upload_id = upload_id
        self.object_name = object_name
        self.field_results: list[FieldQualityResult] = []

    @property
    def total_violations(self) -> int:
        return sum(r.failed for r in self.field_results)

    @property
    def is_clean(self) -> bool:
        return self.total_violations == 0

    def to_dict(self) -> dict:
        return {"upload_id": self.upload_id, "object_name": self.object_name,
                "is_clean": self.is_clean, "total_violations": self.total_violations,
                "fields_checked": len(self.field_results),
                "field_results": [r.to_dict() for r in self.field_results]}


class DataQualityValidator:
    #: how many distinct values to pack into a single SOQL IN() clause
    _LOOKUP_BATCH_SIZE = 200

    def validate(self, df: pd.DataFrame, mapping: dict[str, FieldMeta],
                 upload_id: str, object_name: str = "unknown", sf_conn=None) -> QualityReport:
        report = QualityReport(upload_id=upload_id, object_name=object_name)
        for source_col, field_meta in mapping.items():
            if source_col not in df.columns:
                continue
            lookup_cache = None
            if field_meta.data_type == DataType.REFERENCE:
                reference_to = getattr(field_meta, "reference_to", None) or []
                if reference_to:
                    lookup_cache = self._resolve_reference_values(
                        sf_conn, reference_to, df[source_col])
                else:
                    # We know it's a lookup field but don't yet know which object it
                    # points to — the cached schema predates capturing referenceTo.
                    lookup_cache = {"unknown_target": True}
            result = self._validate_column(df, source_col, field_meta, lookup_cache)
            report.field_results.append(result)
        logger.info("Quality check: %d violations across %d fields.",
                    report.total_violations, len(report.field_results))
        return report

    def _resolve_reference_values(self, sf_conn, reference_to: list[str],
                                   series: pd.Series) -> Optional[dict]:
        """
        Query Salesforce for each referenced object to find out which of the
        column's distinct values actually resolve to a real record — either
        by 15/18-char Id, or by Name (the common case when source data holds
        a human-readable label instead of the raw Id).

        Returns None if we have no live connection to check against (caller
        falls back to a pure Id-format check); otherwise returns
        {"ids": set[str], "names_lower": set[str], "query_error": bool}.
        """
        if sf_conn is None:
            return None

        distinct_vals = sorted({str(v).strip() for v in series.dropna() if str(v).strip() != ""})
        if not distinct_vals:
            return {"ids": set(), "names_lower": set(), "query_error": False}

        id_pattern = re.compile(r"^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$")
        id_like = [v for v in distinct_vals if id_pattern.match(v)]
        name_like = [v for v in distinct_vals if not id_pattern.match(v)]

        found_ids: set[str] = set()
        found_names_lower: set[str] = set()
        any_query_ok = False

        for target_object in reference_to:
            for field, values in (("Id", id_like), ("Name", name_like)):
                for batch in self._chunk(values, self._LOOKUP_BATCH_SIZE):
                    if not batch:
                        continue
                    literals = ",".join(f"'{self._soql_escape(v)}'" for v in batch)
                    soql = f"SELECT Id, Name FROM {target_object} WHERE {field} IN ({literals})"
                    try:
                        res = sf_conn.query_all(soql)
                        any_query_ok = True
                        for rec in res.get("records", []):
                            if rec.get("Id"):
                                found_ids.add(rec["Id"])
                            if rec.get("Name"):
                                found_names_lower.add(str(rec["Name"]).strip().lower())
                    except Exception as exc:
                        logger.warning("Lookup resolution query failed for %s.%s: %s",
                                       target_object, field, exc)

        return {"ids": found_ids, "names_lower": found_names_lower,
                "query_error": not any_query_ok}

    @staticmethod
    def _soql_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    @staticmethod
    def _chunk(items: list, size: int):
        for i in range(0, len(items), size):
            yield items[i:i + size]

    def _validate_column(self, df, source_col, meta, lookup_cache=None) -> FieldQualityResult:
        result = FieldQualityResult(source_column=source_col, target_field=meta.field_name)
        result.total_rows = len(df)
        series = df[source_col]
        for idx, value in series.items():
            row_violations = self._check_cell(idx, value, meta, lookup_cache)
            if row_violations:
                result.failed += 1
                result.violations.extend(row_violations)
            else:
                result.passed += 1
        return result

    def _check_cell(self, idx: int, value: Any, meta: FieldMeta,
                     lookup_cache: Optional[dict] = None) -> list[FieldViolation]:
        violations: list[FieldViolation] = []
        raw_str = str(value) if value is not None else ""
        is_pandas_null = value is None or (isinstance(value, float) and pd.isna(value))
        is_null = is_pandas_null or raw_str.strip() == ""
        is_empty_string = (not is_pandas_null) and raw_str == ""

        if meta.required and is_null:
            violations.append(FieldViolation(idx, meta.field_name, value, "required_check",
                f"Field '{meta.field_name}' is required but value is null/empty"))
            return violations

        if meta.required and is_empty_string:
            violations.append(FieldViolation(idx, meta.field_name, "", "empty_string_check",
                f"Field '{meta.field_name}' contains empty string. Use null instead."))
            return violations

        if is_null:
            return []

        str_val = raw_str.strip()

        if raw_str != raw_str.strip():
            violations.append(FieldViolation(idx, meta.field_name, raw_str, "whitespace_check",
                f"Value has leading/trailing whitespace — will cause picklist/ID mismatches."))

        try:
            str_val.encode("ascii")
        except UnicodeEncodeError:
            non_ascii = [c for c in str_val if ord(c) > 127]
            violations.append(FieldViolation(idx, meta.field_name, str_val, "encoding_check",
                f"Non-ASCII characters {non_ascii[:5]} may be rejected by Salesforce."))

        type_v = self._check_type(idx, str_val, meta)
        if type_v:
            violations.append(type_v)

        if meta.max_length and len(str_val) > meta.max_length:
            violations.append(FieldViolation(idx, meta.field_name, str_val, "length_check",
                f"Length {len(str_val)} exceeds max {meta.max_length}."))

        if meta.picklist_values and meta.data_type == DataType.PICKLIST:
            if str_val not in meta.picklist_values:
                violations.append(FieldViolation(idx, meta.field_name, str_val, "picklist_check",
                    f"'{str_val}' not in allowed values: {meta.picklist_values}"))

        if meta.data_type == DataType.DATE and not type_v:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str_val):
                violations.append(FieldViolation(idx, meta.field_name, str_val, "date_format_check",
                    f"Date '{str_val}' must be ISO 8601 (YYYY-MM-DD) for Salesforce Data Loader."))

        if meta.data_type == DataType.REFERENCE:
            meta_reference_to = getattr(meta, "reference_to", None) or []
            if lookup_cache is not None and lookup_cache.get("unknown_target"):
                violations.append(FieldViolation(idx, meta.field_name, str_val, "reference_target_unknown",
                    f"'{meta.field_name}' is a lookup field, but the cached schema doesn't record "
                    f"which object it points to yet. Go to the SF Schema Sync tab, re-sync "
                    f"'{meta.object_name}', then re-run mapping and this report."))
            elif lookup_cache is None:
                # No live Salesforce connection was available — fall back to a
                # pure Id-format check (best effort only).
                if not re.match(r"^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$", str_val):
                    violations.append(FieldViolation(idx, meta.field_name, str_val, "reference_format_check",
                        f"'{str_val}' is not a 15/18-char Salesforce Id, and no Salesforce "
                        f"connection was available to look it up by Name."))
            elif lookup_cache.get("query_error"):
                violations.append(FieldViolation(idx, meta.field_name, str_val, "reference_lookup_check",
                    f"Could not verify '{str_val}' against Salesforce — the lookup query failed "
                    f"(check object/field access for {', '.join(meta_reference_to)})."))
            else:
                is_known_id = str_val in lookup_cache["ids"]
                is_known_name = str_val.lower() in lookup_cache["names_lower"]
                if not (is_known_id or is_known_name):
                    violations.append(FieldViolation(idx, meta.field_name, str_val, "reference_lookup_check",
                        f"No matching record found in {'/'.join(meta_reference_to)} with "
                        f"Id or Name = '{str_val}'. This lookup will fail to resolve during load."))

        if meta.data_type in (DataType.CURRENCY, DataType.PERCENT):
            try:
                clean = re.sub(r"[$£€₹,%\s]", "", str_val)
                if float(clean) < 0:
                    violations.append(FieldViolation(idx, meta.field_name, str_val, "numeric_range_check",
                        f"Negative value in '{meta.field_name}' — verify this is intentional."))
            except (ValueError, TypeError):
                pass

        return violations

    def _check_type(self, idx, str_val, meta) -> FieldViolation | None:
        dtype = meta.data_type
        try:
            if dtype == DataType.INTEGER:
                int(str_val.replace(",", ""))
            elif dtype in (DataType.FLOAT, DataType.CURRENCY, DataType.PERCENT):
                float(re.sub(r"[$£€₹,%\s]", "", str_val).strip())
            elif dtype == DataType.BOOLEAN:
                if str_val.lower() not in {"true","false","yes","no","1","0","t","f","y","n"}:
                    raise ValueError(f"Not boolean: '{str_val}'")
            elif dtype == DataType.DATE:
                self._parse_date(str_val)
            elif dtype == DataType.DATETIME:
                pd.to_datetime(str_val)
            elif dtype == DataType.EMAIL:
                if not re.match(r"^[\w.+-]+@([\w-]+\.)+[a-z]{2,}$", str_val, re.IGNORECASE):
                    raise ValueError(f"Invalid email: '{str_val}'")
            elif dtype == DataType.PHONE:
                if not re.match(r"^[\d\s\-+().]{7,20}$", str_val):
                    raise ValueError(f"Invalid phone: '{str_val}'")
        except (ValueError, TypeError):
            return FieldViolation(idx, meta.field_name, str_val, "type_check",
                f"Cannot convert '{str_val}' to expected type '{dtype}'")
        return None

    def _parse_date(self, val: str) -> datetime:
        for fmt in ["%Y-%m-%d","%m/%d/%Y","%d/%m/%Y","%m-%d-%Y","%Y/%m/%d","%d-%m-%Y","%Y%m%d","%m/%d/%y"]:
            try:
                return datetime.strptime(val.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse '{val}' as date")

    def check_duplicates(self, df: pd.DataFrame, key_fields: list[str]) -> dict:
        valid_keys = [f for f in key_fields if f in df.columns]
        if not valid_keys:
            return {"key_fields_used": key_fields, "error": "Key fields not found in CSV.",
                    "duplicate_group_count": 0, "total_duplicate_rows": 0,
                    "sample_duplicate_keys": [], "duplicate_row_indices": []}
        dupe_mask = df.duplicated(subset=valid_keys, keep=False)
        dupe_df = df[dupe_mask]
        # groupby(dropna=False) hits a pandas internal bug ("Categorical categories
        # cannot be null") when real NaNs are present across multiple key columns.
        # Fill them with a sentinel first so grouping never needs dropna=False.
        _NULL = "�__DUPCHECK_NULL_SENTINEL__�"
        groups = dupe_df[valid_keys].fillna(_NULL).groupby(valid_keys)
        sample_keys = []
        for key, _ in list(groups)[:10]:
            key_tuple = key if isinstance(key, tuple) else (key,)
            sample_keys.append(["" if k == _NULL else str(k) for k in key_tuple])
        return {"key_fields_used": valid_keys,
                "duplicate_group_count": int(len(groups)),
                "total_duplicate_rows": int(dupe_mask.sum()),
                "sample_duplicate_keys": sample_keys,
                "duplicate_row_indices": [int(i) for i in dupe_df.index]}

    def check_coverage(self, source_columns: list[str], mapped_columns: list[str],
                       all_sf_fields: list[FieldMeta], source_hints: dict = None) -> list[dict]:
        source_hints = source_hints or {}
        mapped_sf_set = set(f.lower() for f in mapped_columns)
        missing = []
        for field in all_sf_fields:
            if field.required and field.field_name.lower() not in mapped_sf_set:
                hint_match = any(
                    h.get("csv_api_name", "").lower() == field.field_name.lower()
                    for h in source_hints.values()
                )
                if not hint_match:
                    missing.append({"field_name": field.field_name, "label": field.label,
                                    "data_type": field.data_type, "required": field.required})
        return missing
