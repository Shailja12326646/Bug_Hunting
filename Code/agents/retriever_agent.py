"""
retriever_agent.py — MCP Documentation Retriever Agent
-------------------------------------------------------
This dedicated pydantic-ai Agent is responsible for one thing only:
intelligently querying the Infineon MCP knowledge server to retrieve
the most relevant documentation for a given C++ code snippet.

The agent decides which queries to send (can call MCP multiple times),
collects results, and returns a clean RetrievalResult.

Retries: 2  (on network or parse failure)
Tools  : search_mcp (calls FastMCP SSE server on port 8003)
Output : RetrievalResult { documentation, queries_used }
"""

from __future__ import annotations

import asyncio
import json
import sys, os

from pydantic_ai import Agent, RunContext
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import MCP_SERVER_URL
from agents.models import create_hf_model, RetrievalResult


# ── Agent-level state (tracks queries used across tool calls) ────────────────
@dataclass
class RetrieverDeps:
    queries_made: list[str] = field(default_factory=list)


# ── Agent Definition ─────────────────────────────────────────────────────────
retriever_agent: Agent[RetrieverDeps, RetrievalResult] = Agent(
    model=create_hf_model(),
    deps_type=RetrieverDeps,
    output_type=RetrievalResult,
    retries=2,
    system_prompt="""\
You are the Documentation Retrieval Agent for an Infineon SmartRDI C++ bug hunter system.

Your ONLY job: search the Infineon documentation MCP server and return relevant API documentation.

Strategy:
1. Analyze the code to identify which RDI APIs are being used (e.g. rdi.dc(), rdi.smartVec(), iClamp, vForce).
2. Call `search_mcp` with a focused query about those APIs and their correct usage.
3. If the first result seems insufficient, call `search_mcp` again with a more specific query.
4. You may call `search_mcp` up to 3 times. Each call should use a DIFFERENT, more specific query.
5. Return ALL collected documentation as your `documentation` field, along with `queries_used`.

Do NOT try to detect the bug yourself — just retrieve thorough documentation.
""",
)


# ── Tool: MCP Search ─────────────────────────────────────────────────────────
@retriever_agent.tool
async def search_mcp(ctx: RunContext[RetrieverDeps], query: str) -> str:
    """
    Search the Infineon MCP knowledge server for documentation.

    Args:
        query: A focused query about a specific RDI API, parameter, or usage pattern.
               Example: "iClamp argument order low high", "vecEditMode VTT VECD copyLabel",
               "RDI_BEGIN RDI_END lifecycle order", "vForceRange allowed values AVI64"

    Returns:
        Relevant documentation text chunks.
    """
    ctx.deps.queries_made.append(query)
    try:
        from fastmcp import Client
        async with Client(MCP_SERVER_URL) as client:
            result = await client.call_tool("search_documents", {"query": query})

        docs = []
        for content in result:
            raw = getattr(content, "text", str(content))
            try:
                items = json.loads(raw)
                if isinstance(items, list):
                    for item in items[:5]:
                        if isinstance(item, dict) and "text" in item:
                            docs.append(item["text"].strip())
                    continue
            except (json.JSONDecodeError, TypeError):
                pass
            if raw.strip():
                docs.append(raw.strip())

        return "\n\n---\n\n".join(docs[:5]) if docs else "No results found."

    except Exception as e:
        return f"MCP unavailable: {e}. Use internal SmartRDI knowledge."


# ── Entry function ────────────────────────────────────────────────────────────
async def retrieve_documentation(code: str, context: str) -> RetrievalResult:
    """
    Run the Retriever Agent on a code snippet.
    Returns RetrievalResult with relevant Infineon documentation.
    """
    deps   = RetrieverDeps()
    prompt = (
        f"Find Infineon SmartRDI documentation relevant to this C++ code.\n\n"
        f"Code Purpose: {context}\n\n"
        f"Code (first 400 chars):\n{code[:400]}"
    )
    result = await retriever_agent.run(prompt, deps=deps)
    return result.output
