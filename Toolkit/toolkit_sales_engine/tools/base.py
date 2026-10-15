"""Shared MatchResult model returned by every matching tool."""
from pydantic import BaseModel
from typing import Optional


class MatchResult(BaseModel):
    source_column: str
    target_field: Optional[str]
    object_name: Optional[str]
    score: float
    method: str
    matched: bool
    reasoning: str

    model_config = {"extra": "allow"}
