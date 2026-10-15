"""Tool 2 — Synonym Match (score 0.95)."""
import re
import logging
from ..metadata.registry import MetadataRegistry
from .base import MatchResult

logger = logging.getLogger(__name__)
_STRIP_RE = re.compile(r"[\s_\-\.]+")


def normalise(text: str) -> str:
    return _STRIP_RE.sub("", text.lower())


class SynonymMatchTool:
    METHOD = "synonym_match"
    SCORE = 0.95

    def __init__(self, registry: MetadataRegistry):
        self._registry = registry
        self._synonym_map: dict[str, list[tuple[str, str]]] = {}
        self._build_map()

    def _build_map(self) -> None:
        self._synonym_map.clear()
        for obj_name in self._registry.get_all_objects():
            for field in self._registry.get_all_fields(obj_name):
                for syn in field.synonyms:
                    key = normalise(syn)
                    if key not in self._synonym_map:
                        self._synonym_map[key] = []
                    self._synonym_map[key].append((obj_name, field.field_name))

    def refresh(self) -> None:
        self._build_map()

    def run(self, source_column: str, object_name: str | None = None) -> MatchResult:
        key = normalise(source_column)
        candidates = self._synonym_map.get(key, [])
        if object_name:
            candidates = [(o, f) for o, f in candidates if o == object_name]
        if candidates:
            obj, field = candidates[0]
            return MatchResult(
                source_column=source_column,
                target_field=field,
                object_name=obj,
                score=self.SCORE,
                method=self.METHOD,
                matched=True,
                reasoning=f"Column '{source_column}' matches synonym for '{field}' in '{obj}'",
            )
        return MatchResult(
            source_column=source_column,
            target_field=None,
            object_name=None,
            score=0.0,
            method=self.METHOD,
            matched=False,
            reasoning=f"No synonym match found for '{source_column}'",
        )
