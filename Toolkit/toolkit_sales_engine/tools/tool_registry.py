"""
Tool 5 — LLM Agent (GPT-4o via Azure OpenAI).
Only active when gpt4o_api_key is configured.
"""
import json
import logging
from typing import Any, Callable, Optional

from ..config import get_settings
from ..metadata.registry import MetadataRegistry
from .base import MatchResult
from .exact_match import ExactMatchTool
from .synonym_match import SynonymMatchTool
from .fuzzy_match import FuzzyMatchTool
from .embedding_match import EmbeddingMatchTool

logger = logging.getLogger(__name__)

_TOOL_DEFINITIONS = [
    {"type": "function", "function": {
        "name": "exact_match",
        "description": "Check exact case-insensitive match. Use first. Returns score=1.0 if matched.",
        "parameters": {"type": "object", "properties": {
            "source_column": {"type": "string"},
            "object_name": {"type": "string"},
        }, "required": ["source_column"]},
    }},
    {"type": "function", "function": {
        "name": "synonym_match",
        "description": "Check registered synonyms. Returns score=0.95 if matched.",
        "parameters": {"type": "object", "properties": {
            "source_column": {"type": "string"},
            "object_name": {"type": "string"},
        }, "required": ["source_column"]},
    }},
    {"type": "function", "function": {
        "name": "fuzzy_match",
        "description": "Jaro-Winkler similarity. Use when exact and synonym fail.",
        "parameters": {"type": "object", "properties": {
            "source_column": {"type": "string"},
            "object_name": {"type": "string"},
        }, "required": ["source_column"]},
    }},
    {"type": "function", "function": {
        "name": "embedding_match",
        "description": "Semantic embedding similarity. Use when fuzzy is also inconclusive.",
        "parameters": {"type": "object", "properties": {
            "source_column": {"type": "string"},
            "column_context": {"type": "string"},
            "object_name": {"type": "string"},
        }, "required": ["source_column"]},
    }},
]

_SYSTEM_PROMPT = """You are a data mapping agent. Map a source CSV column to the correct
Salesforce field for the given target object.

The user message includes the full list of that object's available fields — API name,
label, type, and (when Salesforce has one) that field's Description/Help Text. It may
also include a line describing what the source file's own data dictionary says this
column means (e.g. an abbreviation like "HIN" explained as "Boat Serial#") — treat that
as a strong, authoritative signal of the column's true meaning, since it comes directly
from the people who built the source file.

You will be asked to do one of two tasks, depending on what the user message contains:

TASK A — VERIFY A CANDIDATE (a "Candidate to verify" line is present): a deterministic
tool (exact name match, a previously-taught synonym, fuzzy label-similarity, or
embedding/vector similarity) already proposed a field for this column. A similarity
score alone is NOT evidence of correctness — fuzzy matching in particular compares raw
character sequences and is easily fooled by coincidental overlap that has nothing to do
with meaning (e.g. "DealerNotes" vs "Deleted" share a "de..." prefix; "AltCountry" vs
"Appeal Count" both contain "count"-like text — neither pair means the same thing).
Never let a high score by itself persuade you a candidate is right.

Independently judge whether the candidate field's label and description describe the
same real-world concept as the column name (read it the way a person would — expand
likely abbreviations, e.g. "TechNotes" = technician's notes, "AltCountry" = an alternate
country). Use sample values as a bonus signal only when present; if the column is
mostly or entirely null, you have no data to check against, so rely on the name-vs-label
comparison alone — do not treat "no data to contradict it" as a reason to accept a weak
candidate, if anything be more cautious without it.

When judging fit, tell apart two different situations:
- WRONG KIND OF FIELD (reject outright, never confirm or force this): the candidate is
  fundamentally a different kind of thing than the column, regardless of any text
  overlap — e.g. a boolean/system-audit field (IsDeleted, CreatedDate, SystemModstamp,
  OwnerId, ...) or a numeric/count field proposed for free-text content. Be especially
  suspicious of a text/notes/comments-sounding column being proposed against one of
  these — it is almost never a legitimate match.
- REASONABLY FITTING BUT GENERIC (this is an acceptable match — do not reject it just
  because the wording isn't a perfect echo of the column name): a general-purpose field
  of the right KIND for this data is a legitimate destination even if its label is less
  specific than the column — e.g. a plain "Comments" or "Internal Comments" field is a
  normal, sensible home for a column like "DealerNotes" or "TechNotes" even though the
  field's label doesn't say "dealer" or "technician." The test is "is this the same KIND
  of information" (free-text notes -> any comments/notes field; a person's name -> any
  name field; a date -> any date field serving the right purpose), not "does the field's
  wording echo the column's wording."

If the candidate genuinely represents the same real-world concept, confirm it by
returning its exact field name as target_field. If a different field in the Available
Fields list represents the column's meaning at least as well — whether an exact
conceptual match or a reasonably-fitting generic field per above — use that field
instead; if more than one generic field of the right kind exists and you can't tell
which is intended, pick the best-fitting one and score it on the lower end (0.60-0.70)
to flag it clearly for review, rather than leaving it unmapped just because you're
unsure *which* field of the right kind it is. Only return target_field: null and
score: 0.0 when nothing in the list is even the right kind of field for this data at
all — not merely because no field's exact wording matches the column name. Score a
confirmed-but-uncertain or overridden match between 0.60 and 0.85 (never 0.90+, which
would imply a certainty this verification step doesn't have).

TASK B — FIND A MATCH FROM SCRATCH (no candidate given — nothing else found one). Use
the tools below as a fast, precise first pass, then fall back to your own judgment:
RULES:
1. Call exact_match first. If matched=true, use it immediately (score 1.0).
2. If not, call synonym_match (score 0.95).
3. If not, call fuzzy_match (accept if score >= 0.80).
4. If still no match, call embedding_match with column_context (accept if score >= 0.75).
5. If none of the tools found a confident match, use your own judgment: compare the
   column name, its data-dictionary description (if given), and its sample values
   against each candidate field's label and description in the Available Fields list,
   and choose whichever field most plausibly represents the same real-world concept
   (e.g. "Qty", "Quantity", and "# of Units" all mean the same thing, even with no
   shared substring — and a data-dictionary line like "HIN: Boat Serial#" should be
   weighed at least as strongly as label text). As in TASK A, distinguish a wrong KIND
   of field (a boolean/system/count field for free-text content — reject) from a
   reasonably-fitting generic field of the right kind (a plain "Comments" field for a
   column like "DealerNotes" — accept, even though the wording isn't a perfect echo of
   the column name). If more than one generic field of the right kind fits and you
   can't tell which is intended, pick the best one and score it 0.60-0.70 to flag it for
   review, rather than leaving it unmapped. Score a solid conceptual match higher within
   0.60-0.85 (never 0.90+, reserved for the deterministic tools above) so it's flagged
   for human review instead of being silently auto-accepted.
6. Only return target_field: null and score: 0.0 when nothing in the list is even the
   right kind of field for this data — not merely because no field's exact wording
   matches the column name, and not by forcing a guess onto an unrelated field just
   because it's the least-dissimilar option available.

In both tasks, you MUST only choose a target_field API name that appears in the
Available Fields list — never invent one that isn't there.
Return final answer as JSON: {"target_field": "...", "object_name": "...",
"score": 0.0, "method": "...", "reasoning": "..."}"""


class MappingAgent:
    def __init__(self, exact_tool, synonym_tool, fuzzy_tool, embedding_tool):
        self._tools: dict[str, Callable] = {
            "exact_match":     lambda **kw: exact_tool.run(**kw),
            "synonym_match":   lambda **kw: synonym_tool.run(**kw),
            "fuzzy_match":     lambda **kw: fuzzy_tool.run(**kw),
            "embedding_match": lambda **kw: embedding_tool.run(**kw),
        }
        settings = get_settings()
        self._available = bool(settings.gpt4o_api_key and settings.azure_openai_endpoint)
        if self._available:
            try:
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    api_key=settings.gpt4o_api_key,
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_version=settings.gpt4o_api_version,
                )
                self._model = settings.gpt4o_deployment
            except Exception as exc:
                logger.warning("MappingAgent: could not init OpenAI client — %s", exc)
                self._available = False

    def map_column(self, profile, object_name: str, available_fields: list[dict],
                   file_description: str = "", candidate: Optional[dict] = None) -> dict:
        """Returns mapping dict. Falls back to best deterministic result if LLM unavailable.

        `candidate`, when given (a matched result's target_field/method/score from any
        of the four deterministic tools), puts the agent into TASK A (verify-or-override)
        instead of TASK B (cold search) — see _SYSTEM_PROMPT.
        """
        if not self._available:
            return {"target_field": None, "object_name": None, "score": 0.0,
                    "method": "llm_agent_unavailable",
                    "reasoning": "LLM not configured — no confident match found."}
        try:
            return self._run_agent(profile, object_name, available_fields, file_description, candidate)
        except Exception as exc:
            logger.warning("LLM agent failed: %s", exc)
            return {"target_field": None, "object_name": None, "score": 0.0,
                    "method": "llm_agent_error", "reasoning": str(exc)}

    def _run_agent(self, profile, object_name: str, available_fields: list[dict],
                    file_description: str = "", candidate: Optional[dict] = None) -> dict:
        # No cap here: objects like Account (280+ fields) or WOD_2__Claim__c (180+)
        # previously had fields past #40 silently invisible to the LLM, so a
        # correct target field beyond that point could never be chosen.
        # Each field's Salesforce Description + Help Text (already fetched into
        # `available_fields`, see engine.py) is included below so the LLM can reason
        # about meaning, not just field_name/label/type.
        fields_summary = "\n".join(
            f"  - {f['field_name']} ({f['label']}, {f['type']})"
            + (f" — {f['description']}" if f.get("description") else "")
            for f in available_fields
        )
        file_desc_line = (
            f"The source file's own data dictionary describes this column as: \"{file_description}\"\n"
            if file_description else ""
        )
        candidate_line = ""
        if candidate:
            candidate_line = (
                f"Candidate to verify: {candidate['target_field']} "
                f"(proposed via {candidate['method']}, similarity score {candidate['score']:.2f}). "
                f"This is TASK A — verify or override it.\n"
            )
        user_msg = (
            f"Map CSV column: {profile.column_name}\n"
            f"Type: {profile.semantic_type} | Samples: {profile.sample_values[:3]} | Nulls: {profile.null_pct}%\n"
            f"{file_desc_line}"
            f"{candidate_line}"
            f"Target object: {object_name}\nAvailable fields:\n{fields_summary}"
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        for _ in range(5):  # max tool rounds
            response = self._client.chat.completions.create(
                model=self._model, messages=messages,
                tools=_TOOL_DEFINITIONS, tool_choice="auto", temperature=0,
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                # Final answer
                try:
                    content = msg.content or "{}"
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    return json.loads(content[start:end])
                except Exception:
                    return {"target_field": None, "object_name": None, "score": 0.0,
                            "method": "llm_agent", "reasoning": msg.content or ""}
            # Execute tool calls
            messages.append({"role": "assistant", "content": None, "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]})
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                kwargs = json.loads(tc.function.arguments)
                if fn_name in self._tools:
                    result: MatchResult = self._tools[fn_name](**kwargs)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result.model_dump_json()})
                else:
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": '{"error": "unknown tool"}'})
        return {"target_field": None, "object_name": None, "score": 0.0,
                "method": "llm_agent", "reasoning": "Max iterations reached"}
