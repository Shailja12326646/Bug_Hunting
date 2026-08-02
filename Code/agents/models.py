"""
models.py — Shared Pydantic Schemas & HuggingFace Model Factory
----------------------------------------------------------------
All agents import from here to ensure a single source of truth
for data contracts and model configuration.
"""

from __future__ import annotations

import sys, os
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import HF_TOKEN, HF_MODEL


# ── Shared Pydantic output schemas ──────────────────────────────────────────

class ParsedCode(BaseModel):
    """Output of the Code Parser (pure Python, no LLM)."""
    formatted: str  = Field(description="Code formatted as 'Line N: ...' for each line")
    total_lines: int = Field(description="Total number of lines in the code")


class RetrievalResult(BaseModel):
    """Output of the MCP Retriever Agent."""
    documentation: str = Field(
        description="Concatenated relevant documentation chunks from the Infineon MCP server"
    )
    queries_used: list[str] = Field(
        description="The queries that were sent to the MCP server"
    )


class BugInstance(BaseModel):
    """A single detected bug instance."""
    bug_line: int = Field(
        description="Exact 1-indexed line number where this bug occurs"
    )
    bug_type: Literal[
        "wrong_method_name",
        "wrong_argument_order",
        "out_of_range_value",
        "wrong_call_chain",
        "lifecycle_order",
        "pin_name_typo",
        "wrong_api_usage",
        "other",
    ] = Field(description="Category of the bug")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score from 0.0 (uncertain) to 1.0 (certain)"
    )
    bug_summary: str = Field(
        description="One sentence: what exactly is wrong on this line"
    )


class DetectionResult(BaseModel):
    """Output of the Bug Detector Agent — all bugs found in the snippet."""
    bugs: list[BugInstance] = Field(
        description="List of ALL bugs found. Each entry is a distinct bug on a distinct line."
    )


class ExplanationResult(BaseModel):
    """Output of the Explainer Agent."""
    explanation: str = Field(
        description="2-4 sentence professional explanation referencing Infineon documentation"
    )
    fix_suggestion: str = Field(
        description="Concrete suggestion for the correct code fix"
    )
    doc_reference: str = Field(
        description="The specific documentation excerpt that proves this is a bug"
    )


class FinalBugReport(BaseModel):
    """Output of the Orchestrator Agent — the final merged result."""
    code_id:        str   = Field(description="ID of the code snippet")
    bug_line:       int   = Field(description="Final agreed-upon bug line number")
    bug_type:       str   = Field(description="Bug category")
    confidence:     float = Field(description="Final confidence score")
    explanation:    str   = Field(description="Full explanation for output.csv")
    fix_suggestion: str   = Field(description="Suggested fix")


# ── Model Factory ────────────────────────────────────────────────────────────

def create_hf_model():
    """
    Factory function for pydantic-ai model targeting HuggingFace Inference Endpoint.
    """
    from pydantic_ai.providers.openai import OpenAIProvider
    from pydantic_ai.models.openai import OpenAIChatModel

    provider = OpenAIProvider(
        base_url="https://api-inference.huggingface.co/v1/",
        api_key=HF_TOKEN or "dummy_key",
    )
    return OpenAIChatModel(HF_MODEL, provider=provider)

