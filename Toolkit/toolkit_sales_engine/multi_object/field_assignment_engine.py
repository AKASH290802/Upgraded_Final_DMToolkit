"""
Field Assignment Engine — decides, for every source column, which selected
Salesforce object (and which field on it) it most plausibly belongs to.

Reuses the existing 5-tool MappingEngine cascade (Exact -> Synonym -> Fuzzy ->
Embedding -> LLM) once per candidate object, then keeps whichever object/field
pair scored highest for that column.
"""
import logging
from typing import Optional

import pandas as pd

from ..metadata.registry import MetadataRegistry
from ..mapper.engine import MappingEngine
from .models import FieldAssignment

logger = logging.getLogger(__name__)

# A column is only left truly unassigned when no candidate object/field was
# found at all. Anything below this score is still assigned (best guess) but
# flagged needs_review=True so the user can confirm/correct it instead of
# it silently disappearing from coverage.
REVIEW_CONFIDENCE_THRESHOLD = 0.45

# If the top two candidate objects' scores are within this margin, the pick
# is ambiguous — assign the best one but flag for review with the runner-up
# shown as an alternate.
TIE_BREAK_MARGIN = 0.08

# Source-export artifacts that are never real Salesforce data (e.g. audit/
# checksum columns some export tools add) — excluded from mapping entirely
# rather than counted against coverage.
SYSTEM_COLUMN_MARKERS = ("do not modify", "row checksum")


def is_system_column(column_name: str) -> bool:
    name_lower = column_name.lower()
    return any(marker in name_lower for marker in SYSTEM_COLUMN_MARKERS)


def ensure_objects_synced(sf_conn, registry: MetadataRegistry, object_names: list[str],
                           SFetcher) -> None:
    """Fetch and register schema for any selected object not already cached."""
    for obj_name in object_names:
        if registry.get_all_fields(obj_name):
            continue
        try:
            fetcher = SFetcher(sf_conn=sf_conn)
            obj_meta = fetcher.fetch_object(obj_name)
            registry.register_object(obj_meta)
        except Exception as exc:
            logger.warning("Could not sync schema for %s: %s", obj_name, exc)
    registry.save()


def assign_fields(df: pd.DataFrame, registry: MetadataRegistry, engine: MappingEngine,
                   object_names: list[str]) -> list[FieldAssignment]:
    """
    For every column in df, run the mapping cascade against each candidate
    object and keep the best-scoring (object, field) pair. System/technical
    export columns are excluded outright. Low-confidence or closely-tied
    picks are still assigned (to maximize coverage) but flagged for review.
    """
    per_object_plans = {}
    for obj_name in object_names:
        try:
            per_object_plans[obj_name] = engine.map_dataframe(df, obj_name)
        except Exception as exc:
            logger.warning("Mapping failed for object %s: %s", obj_name, exc)

    assignments: list[FieldAssignment] = []
    for column in df.columns:
        if is_system_column(column):
            assignments.append(FieldAssignment(
                source_column=column,
                assigned_object=None,
                assigned_field=None,
                method="excluded_system_column",
                confidence=0.0,
                reasoning="Detected as a source-export artifact column (e.g. '(Do Not Modify) ...').",
                excluded=True,
            ))
            continue

        # Collect every candidate object's best mapping for this column,
        # ranked so we can also see the runner-up for tie-break detection.
        candidates = []
        for obj_name, plan in per_object_plans.items():
            mapping = next((m for m in plan.mappings if m.source_column == column), None)
            if mapping and mapping.target_field:
                candidates.append((obj_name, mapping))
        candidates.sort(key=lambda c: c[1].score, reverse=True)

        if not candidates:
            assignments.append(FieldAssignment(
                source_column=column,
                assigned_object=None,
                assigned_field=None,
                method="unassigned",
                confidence=0.0,
                reasoning="No candidate object/field found for this column.",
            ))
            continue

        best_obj, best_mapping = candidates[0]
        needs_review = best_mapping.score < REVIEW_CONFIDENCE_THRESHOLD
        alt_obj = alt_field = None
        alt_confidence = 0.0

        if len(candidates) > 1:
            second_obj, second_mapping = candidates[1]
            if (best_mapping.score - second_mapping.score) <= TIE_BREAK_MARGIN:
                needs_review = True
                alt_obj, alt_field = second_obj, second_mapping.target_field
                alt_confidence = round(second_mapping.score, 4)

        assignments.append(FieldAssignment(
            source_column=column,
            assigned_object=best_obj,
            assigned_field=best_mapping.target_field,
            method=best_mapping.method,
            confidence=round(best_mapping.score, 4),
            reasoning=best_mapping.reasoning,
            needs_review=needs_review,
            alternate_object=alt_obj,
            alternate_field=alt_field,
            alternate_confidence=alt_confidence,
        ))
    return assignments


def suggest_field_for_column(engine: MappingEngine, df: pd.DataFrame, column: str,
                              object_name: str) -> Optional[str]:
    """Best-guess target field for a single column just moved onto object_name."""
    try:
        plan = engine.map_dataframe(df[[column]], object_name)
    except Exception as exc:
        logger.warning("Could not suggest field for %s on %s: %s", column, object_name, exc)
        return None
    if plan.mappings and plan.mappings[0].target_field:
        return plan.mappings[0].target_field
    return None
