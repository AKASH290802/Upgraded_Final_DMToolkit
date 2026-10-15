"""
Mapping Engine — orchestrates the 5-tool cascade for a full CSV.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from ..config import get_settings
from ..metadata.registry import MetadataRegistry
from ..metadata.models import FieldMeta
from ..profiler.csv_profiler import CSVProfiler, ColumnProfile
from ..tools.exact_match import ExactMatchTool
from ..tools.synonym_match import SynonymMatchTool
from ..tools.fuzzy_match import FuzzyMatchTool
from ..tools.embedding_match import EmbeddingMatchTool
from ..tools.tool_registry import MappingAgent
from ..tools.base import MatchResult

logger = logging.getLogger(__name__)


class ColumnMapping:
    def __init__(self, source_column, target_field, object_name, score, method,
                 reasoning, confidence_level, profile, human_reviewed=False):
        self.source_column = source_column
        self.target_field = target_field
        self.object_name = object_name
        self.score = score
        self.method = method
        self.reasoning = reasoning
        self.confidence_level = confidence_level
        self.profile = profile
        self.human_reviewed = human_reviewed

    def to_dict(self) -> dict:
        return {"source_column": self.source_column, "target_field": self.target_field,
                "object_name": self.object_name, "score": self.score, "method": self.method,
                "confidence_level": self.confidence_level, "reasoning": self.reasoning,
                "human_reviewed": self.human_reviewed, "profile": self.profile.to_dict()}


class MappingPlan:
    def __init__(self, upload_id: str, object_name: str):
        self.upload_id = upload_id
        self.object_name = object_name
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.mappings: list[ColumnMapping] = []

    @property
    def mapped_count(self) -> int:
        return sum(1 for m in self.mappings if m.target_field is not None)

    @property
    def total_columns(self) -> int:
        return len(self.mappings)

    @property
    def unmapped_columns(self) -> list[str]:
        return [m.source_column for m in self.mappings if m.target_field is None]

    @property
    def needs_review(self) -> list[str]:
        return [m.source_column for m in self.mappings if m.confidence_level in ("LOW", "MEDIUM")]

    def to_dict(self) -> dict:
        return {"upload_id": self.upload_id, "object_name": self.object_name,
                "created_at": self.created_at, "total_columns": self.total_columns,
                "mapped_count": self.mapped_count, "unmapped_columns": self.unmapped_columns,
                "needs_review": self.needs_review,
                "mappings": [m.to_dict() for m in self.mappings]}


class MappingEngine:
    HIGH_CONFIDENCE_THRESHOLD = 0.90
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70

    def __init__(self, registry: MetadataRegistry):
        self._registry = registry
        self._profiler = CSVProfiler()
        self._exact = ExactMatchTool(registry)
        self._synonym = SynonymMatchTool(registry)
        self._fuzzy = FuzzyMatchTool(registry)
        self._embedding = EmbeddingMatchTool(registry)
        self._agent = MappingAgent(
            exact_tool=self._exact, synonym_tool=self._synonym,
            fuzzy_tool=self._fuzzy, embedding_tool=self._embedding,
        )
        settings = get_settings()
        self._fuzzy_threshold = settings.fuzzy_match_threshold
        self._embed_threshold = settings.embedding_similarity_threshold

    def map_csv_bytes(self, content: bytes, object_name: str,
                      upload_id: Optional[str] = None,
                      column_descriptions: Optional[dict] = None) -> MappingPlan:
        upload_id = upload_id or str(uuid.uuid4())
        profiles = self._profiler.profile_bytes(content)
        return self._map_profiles(profiles, object_name, upload_id, column_descriptions)

    def map_dataframe(self, df: pd.DataFrame, object_name: str,
                      upload_id: Optional[str] = None,
                      column_descriptions: Optional[dict] = None) -> MappingPlan:
        upload_id = upload_id or str(uuid.uuid4())
        profiles = self._profiler.profile_dataframe(df)
        return self._map_profiles(profiles, object_name, upload_id, column_descriptions)

    def _map_profiles(self, profiles, object_name, upload_id, column_descriptions=None) -> MappingPlan:
        plan = MappingPlan(upload_id=upload_id, object_name=object_name)
        column_descriptions = column_descriptions or {}
        available_fields = [
            {"field_name": f.field_name, "label": f.label,
             "description": f.description[:120], "type": f.data_type, "required": f.required}
            for f in self._registry.get_all_fields(object_name)
        ]
        for profile in profiles:
            file_description = column_descriptions.get(profile.column_name, "")
            mapping = self._map_one_column(profile, object_name, available_fields, file_description)
            plan.mappings.append(mapping)
            logger.info("  %-30s → %-35s [%s %.2f]",
                        profile.column_name, mapping.target_field or "UNMAPPED",
                        mapping.method, mapping.score)
        return plan

    def _map_one_column(self, profile, object_name, available_fields, file_description="") -> ColumnMapping:
        # All four deterministic methods only ever produce a *candidate* now -- none of
        # them are auto-accepted. Whatever the strongest one finds (in Exact -> Synonym
        # -> Fuzzy -> Embedding order), the LLM gets the final say: confirm it if it's
        # genuinely correct, or override it if it finds a field that actually fits
        # better. This exists because label/vector-similarity methods have been proven
        # to confidently pick the wrong field on coincidental text overlap alone (e.g.
        # a date column "Submitted" fuzzy-matching "Submitted By"; "DealerNotes"
        # fuzzy-matching "Deleted" off a shared "de..." prefix).
        candidate = self._exact.run(profile.column_name, object_name)
        if not candidate.matched:
            candidate = self._synonym.run(profile.column_name, object_name)

        if not candidate.matched:
            fuzzy_result = self._fuzzy.run(profile.column_name, object_name, profile.semantic_type)
            candidate = fuzzy_result if (fuzzy_result.matched and fuzzy_result.score >= self._fuzzy_threshold) else None

        if candidate is None:
            context = (f"type={profile.semantic_type}, "
                       f"samples={profile.sample_values[:3]}, nulls={profile.null_pct}%")
            if file_description:
                context = f"source file describes this column as: \"{file_description}\". {context}"
            embed_result = self._embedding.run(profile.column_name, context, object_name)
            if embed_result.matched and embed_result.score >= self._embed_threshold:
                candidate = embed_result

        if candidate is not None:
            agent_result = self._agent.map_column(
                profile, object_name, available_fields, file_description,
                candidate={"target_field": candidate.target_field, "method": candidate.method,
                           "score": candidate.score},
            )
            if agent_result.get("method") in ("llm_agent_unavailable", "llm_agent_error"):
                # Verification itself failed (LLM not configured / call errored) -- keep
                # the deterministic candidate rather than discarding a reasonable match
                # over an infrastructure problem unrelated to whether it's correct.
                return self._build_mapping(profile, candidate)
            if agent_result.get("target_field") == candidate.target_field:
                # Confirmed -- keep the original score/method/reasoning so a genuinely
                # good match (whichever of the four methods found it) still shows as
                # its true confidence level, rather than being downgraded for no reason.
                return self._build_mapping(profile, candidate)
            # Disagreed -- force a clear method tag rather than trust whatever string the
            # LLM self-reports, so this is unambiguous in the mapping table. Distinguish
            # "overrode to a different field" from "rejected the candidate outright"
            # (target_field null) since both are valid, different outcomes.
            forced_method = "llm_override" if agent_result.get("target_field") else "llm_rejected_candidate"
            return self._build_from_agent_result(profile, agent_result, default_method=forced_method,
                                                  force_method=forced_method)

        # Nothing from exact/synonym/fuzzy/embedding -- fall back to the LLM's own
        # cold-start judgment (TASK B).
        agent_result = self._agent.map_column(profile, object_name, available_fields, file_description)
        return self._build_from_agent_result(profile, agent_result, default_method="llm_agent")

    def _build_mapping(self, profile, result: MatchResult) -> ColumnMapping:
        return ColumnMapping(
            source_column=profile.column_name, target_field=result.target_field,
            object_name=result.object_name, score=result.score, method=result.method,
            reasoning=result.reasoning,
            confidence_level=self._score_to_confidence(result.score), profile=profile,
        )

    def _build_from_agent_result(self, profile, agent_result: dict, default_method: str,
                                  force_method: Optional[str] = None) -> ColumnMapping:
        score = float(agent_result.get("score", 0.0))
        return ColumnMapping(
            source_column=profile.column_name,
            target_field=agent_result.get("target_field"),
            object_name=agent_result.get("object_name"),
            score=score,
            method=force_method or agent_result.get("method") or default_method,
            reasoning=agent_result.get("reasoning", ""),
            confidence_level=self._score_to_confidence(score),
            profile=profile,
        )

    def _score_to_confidence(self, score: float) -> str:
        if score >= self.HIGH_CONFIDENCE_THRESHOLD: return "HIGH"
        if score >= self.MEDIUM_CONFIDENCE_THRESHOLD: return "MEDIUM"
        if score > 0: return "LOW"
        return "UNMAPPED"

    def apply_override(self, object_name: str, source_column: str,
                       correct_target_field: str, auto_add_synonym: bool = True) -> None:
        if auto_add_synonym:
            try:
                self._registry.add_synonyms(object_name, correct_target_field, [source_column.lower()])
                self._registry.save()
                self._synonym.refresh()
                self._exact.refresh()
                logger.info("Override: added '%s' as synonym for '%s.%s'",
                            source_column, object_name, correct_target_field)
            except KeyError as exc:
                logger.warning("Override synonym add failed: %s", exc)
