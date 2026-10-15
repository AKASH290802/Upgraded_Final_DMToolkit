"""
Metadata Registry — persists to toolkit_sales_engine/registry.json
"""
import json
import logging
from pathlib import Path
from typing import Optional

from .models import FieldMeta, ObjectMeta

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent.parent / "registry.json"


class MetadataRegistry:
    def __init__(self, path: Path = REGISTRY_PATH):
        self._path = path
        self._store: dict[str, dict[str, FieldMeta]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        if self._path.stat().st_size == 0:
            return
        with open(self._path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for obj_name, fields in raw.items():
            self._store[obj_name] = {}
            for field_name, field_data in fields.items():
                self._store[obj_name][field_name] = FieldMeta(**field_data)
        total = sum(len(v) for v in self._store.values())
        logger.info("Registry loaded: %d objects, %d fields.", len(self._store), total)

    def save(self) -> None:
        raw: dict[str, dict] = {}
        for obj_name, fields in self._store.items():
            raw[obj_name] = {fname: fmeta.model_dump() for fname, fmeta in fields.items()}
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, default=str)
        logger.info("Registry saved to %s", self._path)

    def register_object(self, obj_meta: ObjectMeta) -> None:
        # Re-syncing a schema fetches fresh labels/types/picklists from Salesforce,
        # but must not discard synonyms a user has taught the system, or embedding
        # IDs from a previously built index, for fields that still exist.
        existing = self._store.get(obj_meta.object_name, {})
        merged: dict[str, FieldMeta] = {}
        for f in obj_meta.fields:
            old = existing.get(f.field_name)
            if old:
                f.synonyms = list(dict.fromkeys(old.synonyms + f.synonyms))
                if f.embedding_id is None:
                    f.embedding_id = old.embedding_id
            merged[f.field_name] = f
        self._store[obj_meta.object_name] = merged

    def register_field(self, field: FieldMeta) -> None:
        if field.object_name not in self._store:
            self._store[field.object_name] = {}
        self._store[field.object_name][field.field_name] = field

    def get_field(self, object_name: str, field_name: str) -> Optional[FieldMeta]:
        return self._store.get(object_name, {}).get(field_name)

    def get_all_fields(self, object_name: str) -> list[FieldMeta]:
        return list(self._store.get(object_name, {}).values())

    def get_all_objects(self) -> list[str]:
        return list(self._store.keys())

    def add_synonyms(self, object_name: str, field_name: str, synonyms: list[str]) -> None:
        field = self.get_field(object_name, field_name)
        if not field:
            raise KeyError(f"Field '{field_name}' not found in object '{object_name}'")
        existing = set(field.synonyms)
        for s in synonyms:
            if s.lower() not in existing:
                field.synonyms.append(s.lower())
                existing.add(s.lower())

    def set_embedding_id(self, object_name: str, field_name: str, embedding_id: str) -> None:
        field = self.get_field(object_name, field_name)
        if field:
            field.embedding_id = embedding_id

    def __repr__(self) -> str:
        counts = {obj: len(fields) for obj, fields in self._store.items()}
        return f"MetadataRegistry({counts})"


# Module-level singleton
registry = MetadataRegistry()
