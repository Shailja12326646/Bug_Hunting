"""
orchestrator_agent.py — Orchestrator Agent
-------------------------------------------
Coordinates the full multi-bug pipeline using dedicated agent functions.
Uses HuggingFace InferenceClient directly.

Pipeline per CSV row:
  1. Retriever  → queries MCP server for docs (1 API call)
  2. Detector   → finds ALL bugs (list of BugInstance) (1 API call)
  3. Explainer  → generates ONE combined explanation for all bugs (1 API call)
  4. Output     → ONE dictionary per CSV row (combined bugs with newlines)

Total: 3 LLM calls per snippet (max). This cuts latency by 50% for multi-bugs.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys, os

from huggingface_hub import InferenceClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import HF_TOKEN, HF_MODEL, MCP_SERVER_URL
from agents.code_parser import parse_code, format_numbered_code
from agents.detector_agent import detect_bugs

_llm = InferenceClient(model=HF_MODEL, token=HF_TOKEN)


# ── Helper: call LLM ─────────────────────────────────────────────────────────
def _call_llm(system: str, user: str, max_tokens: int = 512) -> str:
    response = _llm.chat.completions.create(
        model=HF_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*?\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


# ── Agent 1: Retriever ────────────────────────────────────────────────────────
async def _retriever_agent(code: str, context: str) -> str:
    """Query MCP server directly using the context. Eliminates the LLM query generation step to save latency."""
    try:
        from fastmcp import Client
        
        docs = []
        for query in [context]:
            if not query.strip():
                continue
            async with Client(MCP_SERVER_URL) as client:
                result = await client.call_tool("search_documents", {"query": query})
            for content in result:
                raw = getattr(content, "text", str(content))
                try:
                    items = json.loads(raw)
                    if isinstance(items, list):
                        for item in items[:4]:
                            if isinstance(item, dict) and "text" in item:
                                docs.append(item["text"].strip())
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass
                if raw.strip():
                    docs.append(raw.strip())

        return "\n\n---\n\n".join(docs[:6]) if docs else "No documentation retrieved."

    except Exception as e:
        print(f"    ⚠️  Retriever fallback: {e}")
        return "MCP unavailable. Using internal Infineon SmartRDI knowledge."


# ── Agent 3: Explainer (Combined for all bugs) ──────────────────────────────
def _explainer_agent_combined(
    numbered_code: str,
    bugs: list,
    context: str,
    documentation: str,
    retries: int = 2,
) -> str:
    """
    Generate a formatted multi-line explanation + fix for all bug instances at once.
    Drastically reduces latency by avoiding a loop of LLM calls.
    """
    if not bugs or (len(bugs) == 1 and bugs[0].bug_line == -1):
        return "Detection failed — please review code manually."

    bug_details = "\n".join([f"- BUG on Line {b.bug_line}: {b.bug_summary} (type: {b.bug_type})" for b in bugs])

    system = (
        "You are an Infineon SmartRDI C++ technical writer. "
        "Always respond with valid JSON only. No markdown outside JSON."
    )
    user = f"""INFINEON DOCUMENTATION:
{documentation}

CODE PURPOSE: {context}

NUMBERED CODE:
{numbered_code}

DETECTED BUGS:
{bug_details}

Write a professional summary individually explaining each bug and providing the fixed code.
Return ONLY this JSON containing an array of explanations:
{{
  "explanations": [
    {{
      "bug_line": <int>,
      "explanation": "<sentences explaining what is wrong for this line>",
      "fix_suggestion": "<concrete correct code fixing this line>"
    }},
    ...
  ]
}}"""

    for attempt in range(retries):
        try:
            raw = _call_llm(system, user, max_tokens=800)
            data = _extract_json(raw)
            if "explanations" in data and isinstance(data["explanations"], list):
                formatted_parts = []
                for exp in data["explanations"]:
                    line = exp.get("bug_line", "?")
                    txt = exp.get("explanation", "")
                    fix = exp.get("fix_suggestion", "")
                    formatted_parts.append(f"Line {line}: {txt} Fix: {fix}")
                return "\n\n".join(formatted_parts)
                
        except Exception as e:
            print(f"    ⚠️  Explainer attempt {attempt+1} failed: {e}")

    # Fallback formatting if JSON parsing fails
    fallback_parts = []
    for b in bugs:
        fallback_parts.append(f"Line {b.bug_line}: {b.bug_summary}")
    return "\n\n".join(fallback_parts)


# ── Orchestrator: Full Multi-Bug Pipeline ────────────────────────────────────
async def run_pipeline(code_id: str, code: str, context: str) -> dict:
    """
    Run the full multi-bug agent pipeline for ONE code snippet.

    Returns:
        dict: ONE row per ID -> {"ID", "Bug Line", "Explanation"}
              (Bug Line will be newline-separated like "5\\n10" if multiple bugs exist)
    """
    numbered_code = format_numbered_code(parse_code(code))

    # Step 1: Retriever Agent — get documentation from MCP
    print(f"    📚 [Retriever] Querying MCP...")
    documentation = await _retriever_agent(code, context)

    # Step 2: Detector Agent — find ALL bugs at once
    print(f"    🔍 [Detector] Finding all bugs...")
    detection = detect_bugs(numbered_code, context, documentation)
    
    valid_bugs = [b for b in detection.bugs if b.bug_line != -1]
    
    if not valid_bugs:
        print(f"    ✓  No valid bugs found")
        return {
            "ID":          str(code_id),
            "Bug Line":    str(-1),
            "Explanation": "Detection failed — please review manually.",
        }

    # Format bug lines with NEWLINES (e.g. "5\n10")
    bug_lines_str = "\n".join(str(b.bug_line) for b in valid_bugs)
    print(f"    ✓  Found bugs on lines: {bug_lines_str.replace(chr(10), ', ')}")

    # Step 3: Explainer Agent — explain ALL bugs in ONE prompt to save time
    print(f"    📝 [Explainer] Explaining combined bugs...")
    full_explanation = _explainer_agent_combined(
        numbered_code=numbered_code,
        bugs=valid_bugs,
        context=context,
        documentation=documentation,
    )
    print(f"    ✓  Explanation generated")

    return {
        "ID":          str(code_id),
        "Bug Line":    bug_lines_str,
        "Explanation": full_explanation,
    }
