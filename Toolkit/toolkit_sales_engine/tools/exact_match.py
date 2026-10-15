"""Tool 1 — Exact Match (case-insensitive, separator-stripped)."""
import re
import logging
from ..metadata.registry import MetadataRegistry
from .base import MatchResult

logger = logging.getLogger(__name__)
_STRIP_RE = re.compile(r"[\s_\-\.]+")


def normalise(text: str) -> str:
    return _STRIP_RE.sub("", text.lower())


class ExactMatchTool:
    METHOD = "exact_match"

    def __init__(self, registry: MetadataRegistry):
        self._registry = registry
        # Scoped per-object: {object_name: {normalised_key: field_name}}. A flat,
        # object-agnostic dict previously let one object's field labels (e.g. a demo
        # "Claim__c" seed) shadow another object's identical labels (e.g. the real
        # "WOD_2__Claim__c"), silently blocking otherwise-obvious exact matches.
        self._lookup: dict[str, dict[str, str]] = {}
        self._build_lookup()

    def _build_lookup(self) -> None:
        self._lookup.clear()
        for obj_name in self._registry.get_all_objects():
            obj_map = self._lookup.setdefault(obj_name, {})
            for field in self._registry.get_all_fields(obj_name):
                obj_map[normalise(field.field_name)] = field.field_name
                obj_map.setdefault(normalise(field.label), field.field_name)

    def refresh(self) -> None:
        self._build_lookup()

    def run(self, source_column: str, object_name: str | None = None) -> MatchResult:
        key = normalise(source_column)

        if object_name:
            field = self._lookup.get(object_name, {}).get(key)
            if field:
                return self._match(source_column, object_name, field)
            return self._no_match(source_column)

        for obj_name, obj_map in self._lookup.items():
            field = obj_map.get(key)
            if field:
                return self._match(source_column, obj_name, field)
        return self._no_match(source_column)

    def _match(self, source_column: str, obj: str, field: str) -> MatchResult:
        return MatchResult(
            source_column=source_column,
            target_field=field,
            object_name=obj,
            score=1.0,
            method=self.METHOD,
            matched=True,
            reasoning=f"Column '{source_column}' exactly matches field '{field}' in '{obj}'",
        )

    def _no_match(self, source_column: str) -> MatchResult:
        return MatchResult(
            source_column=source_column,
            target_field=None,
            object_name=None,
            score=0.0,
            method=self.METHOD,
            matched=False,
            reasoning=f"No exact match found for '{source_column}'",
        )
