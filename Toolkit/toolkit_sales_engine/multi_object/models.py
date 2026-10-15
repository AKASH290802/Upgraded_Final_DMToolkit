"""Data structures for the Multi Data File (multi-object) workflow."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd


@dataclass
class ObjectSelection:
    object_name: str
    priority: int  # 1 = validate/load first (parent)


@dataclass
class FieldAssignment:
    source_column: str
    assigned_object: Optional[str]
    assigned_field: Optional[str]
    method: str  # exact | synonym | fuzzy | embedding | llm_agent | manual | unassigned | excluded_system_column
    confidence: float
    reasoning: str = ""
    user_overridden: bool = False
    excluded: bool = False       # system/technical column (e.g. "(Do Not Modify) ...") — never a mapping target
    needs_review: bool = False  # low confidence or tied with another candidate object
    alternate_object: Optional[str] = None
    alternate_field: Optional[str] = None
    alternate_confidence: float = 0.0


@dataclass
class MultiObjectPlan:
    upload_id: str
    selected_objects: list[ObjectSelection]
    field_assignments: list[FieldAssignment]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def assignments_for(self, object_name: str) -> list[FieldAssignment]:
        return [a for a in self.field_assignments if a.assigned_object == object_name and not a.excluded]

    def unassigned(self) -> list[FieldAssignment]:
        return [a for a in self.field_assignments if a.assigned_object is None and not a.excluded]

    def excluded_columns(self) -> list[FieldAssignment]:
        return [a for a in self.field_assignments if a.excluded]

    def needs_review_items(self) -> list[FieldAssignment]:
        return [a for a in self.field_assignments if a.needs_review and not a.excluded]

    def coverage_stats(self) -> dict:
        mappable = [a for a in self.field_assignments if not a.excluded]
        mapped = [a for a in mappable if a.assigned_object]
        pct = round(100 * len(mapped) / len(mappable), 1) if mappable else 0.0
        return {
            "total": len(self.field_assignments),
            "mappable": len(mappable),
            "mapped": len(mapped),
            "coverage_pct": pct,
            "needs_review": len(self.needs_review_items()),
            "excluded": len(self.excluded_columns()),
        }


@dataclass
class ObjectValidationResult:
    object_name: str
    total_records: int
    passed: int
    failed: int
    warnings: int
    error_rows: list[dict]
    validated_df: Optional[pd.DataFrame] = None
