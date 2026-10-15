"""Tool 3 — Fuzzy Match via Jaro-Winkler (threshold ≥ 0.80)."""
import logging
from ..config import get_settings
from ..metadata.registry import MetadataRegistry
from ..metadata.models import FieldMeta
from .base import MatchResult
from .exact_match import normalise
from .type_compat import is_type_compatible

logger = logging.getLogger(__name__)


class FuzzyMatchTool:
    METHOD = "fuzzy_match"

    def __init__(self, registry: MetadataRegistry):
        self._registry = registry
        self._threshold = get_settings().fuzzy_match_threshold

    def run(self, source_column: str, object_name: str | None = None,
            semantic_type: str | None = None) -> MatchResult:
        try:
            from jellyfish import jaro_winkler_similarity
        except ImportError:
            return MatchResult(
                source_column=source_column, target_field=None, object_name=None,
                score=0.0, method=self.METHOD, matched=False,
                reasoning="jellyfish not installed — fuzzy match unavailable",
            )

        source_norm = normalise(source_column)
        best_score = 0.0
        best_field: FieldMeta | None = None
        best_obj: str | None = None
        best_match_against: str = ""

        objects = [object_name] if object_name else self._registry.get_all_objects()
        for obj_name in objects:
            for field in self._registry.get_all_fields(obj_name):
                # Skip fields whose Salesforce data type can't plausibly hold this
                # column's data at all -- otherwise a clearly date-valued column
                # like "Submitted" can fuzzy-match a Reference field like
                # "Submitted By" purely on label similarity (score 0.96) despite
                # being the wrong field entirely.
                if not is_type_compatible(semantic_type, field.data_type):
                    continue
                score, matched_against = self._best_score_for_field(source_norm, field, jaro_winkler_similarity)
                if score > best_score:
                    best_score = score
                    best_field = field
                    best_obj = obj_name
                    best_match_against = matched_against

        if best_field and best_score >= self._threshold:
            return MatchResult(
                source_column=source_column,
                target_field=best_field.field_name,
                object_name=best_obj,
                score=round(best_score, 4),
                method=self.METHOD,
                matched=True,
                reasoning=(
                    f"Jaro-Winkler similarity {best_score:.2f} between "
                    f"'{source_column}' and '{best_match_against}' "
                    f"(field: '{best_field.field_name}')"
                ),
            )
        return MatchResult(
            source_column=source_column, target_field=None, object_name=None,
            score=round(best_score, 4), method=self.METHOD, matched=False,
            reasoning=f"Best fuzzy score {best_score:.2f} below threshold {self._threshold}",
        )

    def _best_score_for_field(self, source_norm: str, field: FieldMeta, jaro_fn) -> tuple[float, str]:
        candidates = [
            (normalise(field.field_name), field.field_name),
            (normalise(field.label), field.label),
        ]
        for syn in field.synonyms:
            candidates.append((normalise(syn), syn))
        best = 0.0
        best_against = ""
        for norm_target, original in candidates:
            s = jaro_fn(source_norm, norm_target)
            if s > best:
                best = s
                best_against = original
        return best, best_against
