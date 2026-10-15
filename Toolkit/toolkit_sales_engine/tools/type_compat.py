"""
Type-compatibility check between a source column's detected semantic type (from
the CSV/Excel profiler) and a Salesforce field's data type.

Used by FuzzyMatchTool to stop label-similarity matching from accepting a field
purely because its text is close to the column name, when the underlying data
is fundamentally incompatible -- e.g. a clearly date-valued column ("Submitted":
2023-01-05, 2023-02-10...) fuzzy-matching a Reference/lookup field ("Submitted
By") at a very high score just because the label text is close.
"""

_TEMPORAL = {"date", "datetime"}
_NUMERIC = {"integer", "float", "currency", "percent"}
_BOOLEAN = {"boolean"}
_TEXTY = {"string", "email", "phone", "url", "picklist", "reference"}

# Maps a profiler-detected semantic type to the Salesforce data types it's
# plausibly compatible with. A semantic type not listed here (e.g. "unknown",
# "identifier", "name", "address", "text", "picklist") is left unrestricted --
# those are inherently ambiguous, and being strict there would create more
# false negatives than the false positives this is meant to prevent. Numeric
# and boolean source types are kept permissive toward text-like targets too,
# since IDs/flags are frequently stored in Salesforce as text/picklist fields;
# date/currency/percent detections come from strong pattern matches (explicit
# date formats, "$"/"%" formatting) so are trusted enough to exclude them.
_SOURCE_TYPE_COMPATIBLE_TARGETS = {
    "date": _TEMPORAL,
    "datetime": _TEMPORAL,
    "currency": _NUMERIC,
    "percent": _NUMERIC,
    "integer": _NUMERIC | _TEXTY,
    "float": _NUMERIC | _TEXTY,
    "boolean": _BOOLEAN | _TEXTY,
    "email": _TEXTY,
    "phone": _TEXTY,
}


def is_type_compatible(semantic_type: str, target_data_type: str) -> bool:
    """True if a source column of `semantic_type` may plausibly map to a field
    of `target_data_type`. Permissive (True) by default for any semantic type
    not explicitly restricted above."""
    allowed = _SOURCE_TYPE_COMPATIBLE_TARGETS.get((semantic_type or "").lower())
    if allowed is None:
        return True
    return (target_data_type or "").lower() in allowed
