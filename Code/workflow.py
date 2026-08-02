"""
workflow.py — Batch CSV Processor
-----------------------------------
Runs the Orchestrator Agent pipeline over a full DataFrame with
concurrency control. 

The orchestrator returns exactly one dictionary per row: 
{"ID": "...", "Bug Line": "5, 10", "Explanation": "..."}
"""

from __future__ import annotations

import asyncio
import pandas as pd

from agents.orchestrator_agent import run_pipeline


async def process_dataframe(
    df:             pd.DataFrame,
    id_col:         str = "ID",
    code_col:       str = "Code",
    context_col:    str = "Context",
    max_concurrent: int = 2,
) -> list[dict]:
    """
    Process a full DataFrame through the multi-bug enterprise agent pipeline.

    Args:
        df             : Input DataFrame
        id_col         : Column containing the code ID
        code_col       : Column containing the C++ code
        context_col    : Column containing code context/description
        max_concurrent : Max parallel agent pipelines (default: 2)

    Returns:
        Flat list of dicts: [{"ID", "Bug Line", "Explanation"}, ...]
        Each ID produces exactly ONE row. "Bug Line" may be a comma-separated string if multiple bugs exist.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_run(row):
        async with semaphore:
            code_id = str(row[id_col])
            code    = str(row.get(code_col, ""))
            context = str(row.get(context_col, ""))
            print(f"\n  🤖 Orchestrator → Code ID {code_id}")
            
            # Returns exactly one dict per snippet
            result = await run_pipeline(code_id, code, context)
            
            return result

    # Gather results for all rows
    results = await asyncio.gather(*[bounded_run(row) for _, row in df.iterrows()])
    return list(results)
