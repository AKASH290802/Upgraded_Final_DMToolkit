"""
Engine Settings
===============
Reads OpenAI / Azure OpenAI config from DM-Toolkit's linkedservices.json
(key: "openai_config").  If the key is absent, AI tools degrade gracefully
to zeros / disabled, meaning Tools 1-3 (exact, synonym, fuzzy) still work.

Salesforce credentials are NOT read here — DM-Toolkit passes the live
`simple_salesforce.Salesforce` connection object directly.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LINKED_SERVICES = os.path.join(_PROJECT_ROOT, "Services", "linkedservices.json")
_CHROMA_DEFAULT = os.path.join(_PROJECT_ROOT, "chroma_store")


@dataclass
class EngineSettings:
    # ── Azure OpenAI ─────────────────────────────────────────────────────────
    azure_openai_endpoint: str = ""

    # GPT-4o (LLM Agent — Tool 5)
    gpt4o_api_key: str = ""
    gpt4o_deployment: str = "GPT4O_GLOBAL"
    gpt4o_model: str = "GPT4O_GLOBAL"
    gpt4o_api_version: str = "2025-01-01-preview"

    # Embeddings (Tool 4)
    embed_api_key: str = ""
    embed_deployment: str = "embeddingada003"
    embed_model: str = "text-embedding-3-large"
    embed_api_version: str = "2023-05-15"

    # Standard OpenAI fallback
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_persist_dir: str = _CHROMA_DEFAULT
    chroma_collection: str = "field_embeddings"

    # ── Matching thresholds ───────────────────────────────────────────────────
    fuzzy_match_threshold: float = 0.80
    embedding_similarity_threshold: float = 0.75
    exact_match_boost: float = 1.0
    synonym_match_boost: float = 0.95

    @property
    def ai_available(self) -> bool:
        """True if at least one OpenAI key is configured."""
        return bool(self.gpt4o_api_key or self.embed_api_key or self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> EngineSettings:
    """Load settings once; reads openai_config from linkedservices.json."""
    s = EngineSettings()
    try:
        if os.path.exists(_LINKED_SERVICES):
            with open(_LINKED_SERVICES, encoding="utf-8") as f:
                creds = json.load(f)
            oai = creds.get("openai_config", {})
            if oai:
                s.azure_openai_endpoint = oai.get("azure_openai_endpoint", "")
                s.gpt4o_api_key = oai.get("gpt4o_api_key", "")
                s.gpt4o_deployment = oai.get("gpt4o_deployment", s.gpt4o_deployment)
                s.gpt4o_model = oai.get("gpt4o_model", s.gpt4o_model)
                s.gpt4o_api_version = oai.get("gpt4o_api_version", s.gpt4o_api_version)
                s.embed_api_key = oai.get("embed_api_key", "")
                s.embed_deployment = oai.get("embed_deployment", s.embed_deployment)
                s.embed_model = oai.get("embed_model", s.embed_model)
                s.embed_api_version = oai.get("embed_api_version", s.embed_api_version)
                s.openai_api_key = oai.get("openai_api_key", "")
    except Exception:
        pass
    return s


def reload_settings() -> EngineSettings:
    """Force a fresh read (call after user updates linkedservices.json)."""
    get_settings.cache_clear()
    return get_settings()
