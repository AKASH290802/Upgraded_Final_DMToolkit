"""Semantic Type Detector — deterministic heuristics, no LLM needed."""
import re
from enum import Enum
import pandas as pd


class SemanticType(str, Enum):
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    PHONE = "phone"
    CURRENCY = "currency"
    PERCENT = "percent"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    IDENTIFIER = "identifier"
    NAME = "name"
    ADDRESS = "address"
    TEXT = "text"
    PICKLIST = "picklist"
    UNKNOWN = "unknown"


_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[a-z]{2,}$", re.IGNORECASE)
_PHONE_RE = re.compile(r"^[\d\s\-+().]{7,20}$")
_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}$|^\d{1,2}/\d{1,2}/\d{2,4}$|^\d{1,2}-\d{1,2}-\d{2,4}$|^\d{8}$"
)
_CURRENCY_RE = re.compile(
    r"^[$£€₹][\d,]+(\.\d{1,4})?$"          # leading currency symbol, e.g. "$1,234.56"
    r"|^\d{1,3}(,\d{3})+(\.\d{1,4})?$"      # comma thousands separator, e.g. "1,234"
    r"|^\d+\.\d{1,4}$"                      # decimal amount, e.g. "19.99"
)
_PERCENT_RE = re.compile(r"^\d+(\.\d+)?%$")
_BOOL_VALUES = {"true", "false", "yes", "no", "y", "n", "1", "0", "t", "f"}

_NAME_HINTS: dict[SemanticType, list[str]] = {
    SemanticType.DATE: ["date", "dt", "dob", "birth", "effective", "expiry", "created", "updated", "filed", "loss", "incident"],
    SemanticType.DATETIME: ["timestamp", "datetime", "created_at", "updated_at"],
    SemanticType.EMAIL: ["email", "mail", "e_mail"],
    SemanticType.PHONE: ["phone", "mobile", "cell", "fax", "tel", "contact_no"],
    SemanticType.CURRENCY: ["amount", "amt", "premium", "deductible", "settlement", "price", "cost", "value", "bal", "balance", "total", "sum"],
    SemanticType.PERCENT: ["pct", "percent", "rate", "ratio"],
    SemanticType.IDENTIFIER: ["id", "no", "num", "number", "code", "ref", "key", "policy", "claim", "member", "acct", "account"],
    SemanticType.NAME: ["name", "nm", "first", "last", "fname", "lname", "full_name"],
    SemanticType.ADDRESS: ["address", "addr", "street", "city", "zip", "postal"],
}

_PICKLIST_MAX_UNIQUE_RATIO = 0.05
_PICKLIST_MAX_DISTINCT = 20


def detect_semantic_type(column_name: str, series: pd.Series) -> str:
    col_lower = column_name.lower()
    non_null = series.dropna()
    for sem_type, keywords in _NAME_HINTS.items():
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword)}\b|_{re.escape(keyword)}$|^{re.escape(keyword)}_", col_lower):
                return sem_type.value
    if not non_null.empty:
        sample = non_null.head(30).astype(str).str.strip()
        sem_type = _infer_from_values(sample)
        if sem_type != SemanticType.UNKNOWN:
            return sem_type.value
        unique_ratio = series.nunique() / len(series) if len(series) > 0 else 1.0
        if unique_ratio <= _PICKLIST_MAX_UNIQUE_RATIO and series.nunique() <= _PICKLIST_MAX_DISTINCT:
            return SemanticType.PICKLIST.value
    return SemanticType.UNKNOWN.value


def _infer_from_values(sample: pd.Series) -> SemanticType:
    votes: dict[SemanticType, int] = {}
    for val in sample:
        val = str(val).strip()
        if not val or val.lower() in ("nan", "none", "null", ""):
            continue
        if _EMAIL_RE.match(val):
            votes[SemanticType.EMAIL] = votes.get(SemanticType.EMAIL, 0) + 1
        elif _PERCENT_RE.match(val):
            votes[SemanticType.PERCENT] = votes.get(SemanticType.PERCENT, 0) + 1
        elif _DATE_RE.match(val):
            votes[SemanticType.DATE] = votes.get(SemanticType.DATE, 0) + 1
        elif _CURRENCY_RE.match(val):
            votes[SemanticType.CURRENCY] = votes.get(SemanticType.CURRENCY, 0) + 1
        elif _PHONE_RE.match(val) and len(val) >= 7:
            votes[SemanticType.PHONE] = votes.get(SemanticType.PHONE, 0) + 1
        elif val.lower() in _BOOL_VALUES:
            votes[SemanticType.BOOLEAN] = votes.get(SemanticType.BOOLEAN, 0) + 1
    if not votes:
        return SemanticType.UNKNOWN
    best_type, best_count = max(votes.items(), key=lambda x: x[1])
    if best_count / len(sample) > 0.5:
        return best_type
    return SemanticType.UNKNOWN
