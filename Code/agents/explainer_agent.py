"""
explainer_agent.py — Bug Explanation Agent
--------------------------------------------
This dedicated pydantic-ai Agent generates professional, doc-referenced
explanations of detected bugs.

It receives:
  - The full numbered code
  - The specific bug line and bug type (from Detector Agent)
  - Infineon documentation (from Retriever Agent)

It outputs a fully structured ExplanationResult with:
  - explanation   (str) : professional 2-4 sentence explanation
  - fix_suggestion (str): concrete correct code suggestion
  - doc_reference  (str): the doc excerpt that proves it's a bug

This agent covers 30% of the evaluation score
(Bug Explanations referencing documentation).

Retries: 2
Tools  : none (pure generation)
Output : ExplanationResult
"""

from __future__ import annotations

import sys, os
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agents.models import create_hf_model, ExplanationResult


@dataclass
class ExplainerDeps:
    numbered_code: str
    bug_line:      int
    bug_type:      str
    bug_summary:   str
    context:       str
    documentation: str


explainer_agent: Agent[ExplainerDeps, ExplanationResult] = Agent(
    model=create_hf_model(),
    deps_type=ExplainerDeps,
    output_type=ExplanationResult,
    retries=2,
    system_prompt="""\
You are the Bug Explanation Agent for an Infineon SmartRDI C++ bug hunter system.

Your ONLY job: write a clear, accurate, professional bug explanation that:
1. States exactly what is wrong on the identified bug line (be specific about names, values, order)
2. References the Infineon documentation to prove it is wrong
3. Provides a concrete fix suggestion

Style guide:
- Professional tone suitable for embedded systems engineers
- 2-4 sentences for the explanation
- 1-2 sentences for the fix suggestion
- Quote directly from documentation in doc_reference
- Do NOT use vague language like "this might be" — be definitive
""",
)


@explainer_agent.tool
def get_explanation_context(ctx: RunContext[ExplainerDeps]) -> str:
    """
    Get the full context needed to write the bug explanation:
    bug details, code, and documentation.
    """
    return (
        f"=== BUG INFORMATION ===\n"
        f"Bug Line   : {ctx.deps.bug_line}\n"
        f"Bug Type   : {ctx.deps.bug_type}\n"
        f"Bug Summary: {ctx.deps.bug_summary}\n\n"
        f"=== CODE PURPOSE ===\n{ctx.deps.context}\n\n"
        f"=== NUMBERED C++ CODE ===\n{ctx.deps.numbered_code}\n\n"
        f"=== INFINEON DOCUMENTATION ===\n{ctx.deps.documentation}"
    )


async def explain_bug(
    numbered_code: str,
    bug_line:      int,
    bug_type:      str,
    bug_summary:   str,
    context:       str,
    documentation: str,
) -> ExplanationResult:
    """
    Run the Explainer Agent to generate a professional bug explanation.
    Returns a structured ExplanationResult.
    """
    deps = ExplainerDeps(
        numbered_code=numbered_code,
        bug_line=bug_line,
        bug_type=bug_type,
        bug_summary=bug_summary,
        context=context,
        documentation=documentation,
    )
    prompt = (
        f"Write a professional explanation for the bug on line {bug_line}. "
        "Call `get_explanation_context` first to see the full context."
    )
    result = await explainer_agent.run(prompt, deps=deps)
    return result.output
