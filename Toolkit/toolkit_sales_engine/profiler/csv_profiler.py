"""
CSV Data Profiler — column-level analysis, pure pandas + heuristics.
"""
import re
import io
import logging
from typing import Any

import pandas as pd

from .type_detector import detect_semantic_type, SemanticType

logger = logging.getLogger(__name__)
SAMPLE_SIZE = 5


class ColumnProfile:
    def __init__(self, column_name, row_count, null_count, null_pct, unique_count, unique_pct,
                 inferred_type, semantic_type, sample_values, min_length, max_length,
                 avg_length, detected_format):
        self.column_name = column_name
        self.row_count = row_count
        self.null_count = null_count
        self.null_pct = round(null_pct, 2)
        self.unique_count = unique_count
        self.unique_pct = round(unique_pct, 2)
        self.inferred_type = inferred_type
        self.semantic_type = semantic_type
        self.sample_values = sample_values
        self.min_length = min_length
        self.max_length = max_length
        self.avg_length = round(avg_length, 1) if avg_length is not None else None
        self.detected_format = detected_format

    def to_dict(self) -> dict:
        return {
            "column_name": self.column_name,
            "row_count": self.row_count,
            "null_count": self.null_count,
            "null_pct": self.null_pct,
            "unique_count": self.unique_count,
            "unique_pct": self.unique_pct,
            "inferred_type": self.inferred_type,
            "semantic_type": self.semantic_type,
            "sample_values": [str(v) for v in self.sample_values],
            "min_length": self.min_length,
            "max_length": self.max_length,
            "avg_length": self.avg_length,
            "detected_format": self.detected_format,
        }

    def __repr__(self):
        return f"<ColumnProfile '{self.column_name}' type={self.semantic_type} nulls={self.null_pct}%>"


class CSVProfiler:
    def profile_file(self, file_path: str, encoding: str = "utf-8") -> list[ColumnProfile]:
        try:
            df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding="latin-1", low_memory=False)
        return self.profile_dataframe(df)

    def profile_bytes(self, content: bytes) -> list[ColumnProfile]:
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), encoding="latin-1", low_memory=False)
        return self.profile_dataframe(df)

    def profile_dataframe(self, df: pd.DataFrame) -> list[ColumnProfile]:
        return [self._profile_column(col, df[col], len(df)) for col in df.columns]

    def _profile_column(self, col_name: str, series: pd.Series, total_rows: int) -> ColumnProfile:
        null_count = int(series.isna().sum())
        null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0.0
        non_null = series.dropna()
        unique_count = int(non_null.nunique())
        unique_pct = (unique_count / len(non_null) * 100) if len(non_null) > 0 else 0.0
        inferred_type = self._infer_pandas_type(non_null)
        semantic_type = detect_semantic_type(col_name, non_null)
        sample_values = self._get_samples(non_null, SAMPLE_SIZE)
        min_len = max_len = avg_len = None
        if inferred_type == "string":
            str_series = non_null.astype(str)
            lengths = str_series.str.len()
            if len(lengths) > 0:
                min_len = int(lengths.min())
                max_len = int(lengths.max())
                avg_len = float(lengths.mean())
        detected_format = self._detect_format(semantic_type, non_null)
        return ColumnProfile(
            column_name=col_name, row_count=total_rows, null_count=null_count, null_pct=null_pct,
            unique_count=unique_count, unique_pct=unique_pct, inferred_type=inferred_type,
            semantic_type=semantic_type, sample_values=sample_values, min_length=min_len,
            max_length=max_len, avg_length=avg_len, detected_format=detected_format,
        )

    def _infer_pandas_type(self, series: pd.Series) -> str:
        dtype = str(series.dtype)
        if "int" in dtype: return "integer"
        if "float" in dtype: return "float"
        if "bool" in dtype: return "boolean"
        if "datetime" in dtype: return "datetime"
        if series.dtype == object:
            try:
                pd.to_numeric(series.dropna().head(100), errors="raise")
                return "float"
            except (ValueError, TypeError):
                pass
            try:
                pd.to_datetime(series.dropna().head(50).astype(str), errors="raise")
                return "datetime"
            except (ValueError, TypeError):
                pass
        return "string"

    def _get_samples(self, series: pd.Series, n: int) -> list:
        unique_vals = series.dropna().unique()
        chosen = unique_vals[:n]
        return [v.item() if hasattr(v, "item") else v for v in chosen]

    def _detect_format(self, semantic_type: str, series: pd.Series) -> str | None:
        if series.empty:
            return None
        sample = series.dropna().astype(str).head(20).tolist()
        if semantic_type == SemanticType.DATE:
            return self._detect_date_format(sample)
        if semantic_type == SemanticType.CURRENCY:
            for val in sample:
                v = val.strip()
                if v.startswith("$"): return "USD"
                if v.startswith("£"): return "GBP"
                if v.startswith("€"): return "EUR"
            return "NUMERIC_CURRENCY"
        if semantic_type == SemanticType.PHONE:
            return "PHONE"
        return None

    def _detect_date_format(self, sample: list[str]) -> str | None:
        patterns = [
            (r"^\d{4}-\d{2}-\d{2}$", "YYYY-MM-DD"),
            (r"^\d{2}/\d{2}/\d{4}$", "MM/DD/YYYY"),
            (r"^\d{2}-\d{2}-\d{4}$", "MM-DD-YYYY"),
            (r"^\d{8}$", "YYYYMMDD"),
        ]
        for val in sample:
            val = val.strip()
            for pattern, fmt in patterns:
                if re.match(pattern, val):
                    return fmt
        return None
