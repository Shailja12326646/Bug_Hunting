"""
detector_agent.py — Bug Detection Agent (Multi-Bug)
-----------------------------------------------------
Finds ALL bugs in a C++ code snippet, not just the primary one.

Returns a list of BugInstance objects, one per distinct bug found.
Each BugInstance has: bug_line (int), bug_type, confidence, bug_summary.

Retries: 3  (accuracy is critical — 40% of hackathon score)
"""

from __future__ import annotations

import json
import re
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agents.models import DetectionResult, BugInstance
from config import HF_TOKEN, HF_MODEL
from huggingface_hub import InferenceClient

_llm = InferenceClient(model=HF_MODEL, token=HF_TOKEN)


def _extract_json(text: str):
    """Robustly extract JSON from LLM response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            obj = json.loads(match.group())
            if "bugs" in obj:
                return obj["bugs"]
        except json.JSONDecodeError:
            pass
    return []


def detect_bugs(
    numbered_code: str,
    context: str,
    documentation: str,
    retries: int = 3,
) -> DetectionResult:
    """
    Run the Detector Agent to find ALL bugs in the code snippet.

    Args:
        numbered_code : Code with line numbers prepended (Line 1: ..., Line 2: ...)
        context       : Code purpose description
        documentation : Infineon docs retrieved from MCP server
        retries       : Number of retry attempts on failure

    Returns:
        DetectionResult with a list of BugInstance objects (one per bug found).
    """
    system = (
        "You are an Infineon SmartRDI C++ bug detection expert. "
        "Always respond with valid JSON only. No markdown, no text outside JSON."
    )

    user = f"""INFINEON DOCUMENTATION:
{documentation}

CODE PURPOSE: {context}

NUMBERED C++ CODE:
{numbered_code}

Find ALL bugs in this code. Return a JSON ARRAY where each element is one bug:
[
  {{
    "bug_line": <int — the 1-indexed line number>,
    "bug_type": "<wrong_method_name|wrong_argument_order|out_of_range_value|wrong_call_chain|lifecycle_order|pin_name_typo|wrong_api_usage|other>",
    "confidence": <float 0.0-1.0>,
    "bug_summary": "<one sentence: what is wrong on this line>"
  }},
  ...
]

Rules:
- Include EVERY bug you find, not just the most obvious one.
- Each bug must be on a DIFFERENT line number.
- If you only find one bug, still return a JSON array with one element.
- Do NOT return any text outside the JSON array.
"""

    for attempt in range(retries):
        try:
            response = _llm.chat.completions.create(
                model=HF_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=600,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            data = _extract_json(raw)

            if isinstance(data, list) and len(data) > 0:
                bug_instances = []
                for item in data:
                    if not isinstance(item, dict) or "bug_line" not in item:
                        continue
                    bug_instances.append(BugInstance(
                        bug_line=int(item["bug_line"]),
                        bug_type=item.get("bug_type", "other"),
                        confidence=float(item.get("confidence", 0.8)),
                        bug_summary=str(item.get("bug_summary", "")),
                    ))
                if bug_instances:
                    return DetectionResult(bugs=bug_instances)

        except Exception as e:
            print(f"    ⚠️  Detector attempt {attempt + 1} failed: {e}")

    # Fallback: return empty detection (no bugs found after retries)
    return DetectionResult(bugs=[
        BugInstance(
            bug_line=-1,
            bug_type="other",
            confidence=0.0,
            bug_summary="Detection failed after all retries.",
        )
    ])
