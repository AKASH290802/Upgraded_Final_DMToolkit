"""
Tool 4 — Embedding Similarity Match via ChromaDB (threshold ≥ 0.75).
Only active when Azure OpenAI / OpenAI embed keys are configured.
"""
import logging
from typing import Optional

from ..config import get_settings
from ..metadata.registry import MetadataRegistry
from ..metadata.models import FieldMeta
from .base import MatchResult

logger = logging.getLogger(__name__)


def _field_to_embed_text(field: FieldMeta) -> str:
    parts = [f"{field.label}: {field.description}"]
    if field.synonyms:
        parts.append(f"Also known as: {', '.join(field.synonyms)}")
    if field.example_values:
        parts.append(f"Example values: {', '.join(str(e) for e in field.example_values[:5])}")
    parts.append(f"Data type: {field.data_type}")
    return ". ".join(parts)


class EmbeddingMatchTool:
    METHOD = "embedding_match"

    def __init__(self, registry: MetadataRegistry):
        self._registry = registry
        settings = get_settings()
        self._threshold = settings.embedding_similarity_threshold
        self._available = False
        self._collection = None
        self._openai = None

        if not settings.ai_available:
            logger.info("EmbeddingMatchTool: no AI keys configured — tool disabled.")
            return

        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            from openai import AzureOpenAI

            chroma = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = chroma.get_or_create_collection(
                name=settings.chroma_collection,
                metadata={"hnsw:space": "cosine"},
            )
            self._openai = AzureOpenAI(
                api_key=settings.embed_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.embed_api_version,
            )
            self._embed_model = settings.embed_deployment
            self._available = True
            logger.info("EmbeddingMatchTool: ChromaDB ready.")
        except Exception as exc:
            logger.warning("EmbeddingMatchTool: could not initialise — %s", exc)

    def build_index(self, object_name: Optional[str] = None) -> int:
        if not self._available:
            return 0
        fields_to_index: list[tuple[str, FieldMeta]] = []
        objects = [object_name] if object_name else self._registry.get_all_objects()
        for obj_name in objects:
            for field in self._registry.get_all_fields(obj_name):
                fields_to_index.append((obj_name, field))
        if not fields_to_index:
            return 0
        texts = [_field_to_embed_text(f) for _, f in fields_to_index]
        doc_ids = [f"{obj}.{f.field_name}" for obj, f in fields_to_index]
        metadatas = [
            {"object_name": obj, "field_name": f.field_name,
             "label": f.label, "data_type": f.data_type, "required": str(f.required)}
            for obj, f in fields_to_index
        ]
        embeddings = self._get_embeddings(texts)
        self._collection.upsert(ids=doc_ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        for (obj, field), doc_id in zip(fields_to_index, doc_ids):
            self._registry.set_embedding_id(obj, field.field_name, doc_id)
        return len(texts)

    def run(self, source_column: str, column_context: str = "",
            object_name: Optional[str] = None, top_k: int = 3) -> MatchResult:
        if not self._available or not self._collection or self._collection.count() == 0:
            return self._no_match(source_column)
        query_text = f"{source_column}: {column_context}" if column_context else source_column
        try:
            query_embedding = self._get_embeddings([query_text])[0]
            where = {"object_name": object_name} if object_name else None
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._collection.count() or 1),
                where=where,
                include=["metadatas", "distances", "documents"],
            )
        except Exception as exc:
            logger.warning("Embedding query failed: %s", exc)
            return self._no_match(source_column)

        if not results["ids"][0]:
            return self._no_match(source_column)

        best_distance = results["distances"][0][0]
        best_similarity = round(1.0 - (best_distance / 2.0), 4)
        best_meta = results["metadatas"][0][0]
        target_field = best_meta["field_name"]
        obj = best_meta["object_name"]

        if best_similarity >= self._threshold:
            return MatchResult(
                source_column=source_column, target_field=target_field, object_name=obj,
                score=best_similarity, method=self.METHOD, matched=True,
                reasoning=f"Semantic similarity {best_similarity:.3f} for '{source_column}' → '{target_field}'",
            )
        return self._no_match(source_column)

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        response = self._openai.embeddings.create(model=self._embed_model, input=texts)
        return [item.embedding for item in response.data]

    def _no_match(self, source_column: str) -> MatchResult:
        return MatchResult(
            source_column=source_column, target_field=None, object_name=None,
            score=0.0, method=self.METHOD, matched=False,
            reasoning="No embedding match found",
        )
