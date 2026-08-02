"""
main.py — Agentic Bug Hunter CLI Entry Point
--------------------------------------------
Uses the pydantic-ai agentic workflow in workflow.py.
Works with ANY CSV file that has columns for ID, Code, and Context.

Usage (from A14 root):
    # Default — uses samples.csv
    python code/main.py

    # Custom CSV with custom column names
    python code/main.py --csv my_file.csv --id-col CodeID --code-col Script --context-col Description

    # Control concurrency (parallel agent calls)
    python code/main.py --concurrent 3

Output:
    output.csv  (in A14 root, OUTSIDE code/ folder)
"""

import sys
import os
import time
import argparse
import asyncio
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from config   import CSV_INPUT, CSV_OUTPUT
from workflow import process_dataframe


BANNER = """
╔═══════════════════════════════════════════════════════════╗
║          🐛  AGENTIC BUG HUNTER  🐛                      ║
║   Pydantic-AI Agent · Qwen2.5-72B · MCP Knowledge Server ║
╚═══════════════════════════════════════════════════════════╝
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Agentic Bug Hunter — analyze C++ code CSV for bugs")
    parser.add_argument("--csv",         default=None,      help="Path to input CSV (default: samples.csv)")
    parser.add_argument("--output",      default=None,      help="Path to output CSV (default: output.csv in A14/)")
    parser.add_argument("--id-col",      default="ID",      help="Column name for code ID (default: ID)")
    parser.add_argument("--code-col",    default="Code",    help="Column name for C++ code (default: Code)")
    parser.add_argument("--context-col", default="Context", help="Column name for code context (default: Context)")
    parser.add_argument("--concurrent",  default=2, type=int, help="Max concurrent agent calls (default: 2)")
    return parser.parse_args()


async def run(args):
    print(BANNER)

    # ── Resolve paths ─────────────────────────────────────────────────────
    csv_path    = os.path.abspath(args.csv)    if args.csv    else CSV_INPUT
    output_path = os.path.abspath(args.output) if args.output else CSV_OUTPUT

    if not os.path.exists(csv_path):
        print(f"❌ ERROR: Input CSV not found: {csv_path}")
        sys.exit(1)

    # ── Load DataFrame ────────────────────────────────────────────────────
    df = pd.read_csv(csv_path)
    print(f"📂 Loaded {len(df)} rows from: {csv_path}")
    print(f"   Columns detected: {list(df.columns)}")

    # Validate required columns
    missing = [c for c in [args.id_col, args.code_col] if c not in df.columns]
    if missing:
        print(f"❌ ERROR: Missing required columns: {missing}")
        print(f"   Available columns: {list(df.columns)}")
        print(f"   Use --id-col and --code-col to specify the correct column names.")
        sys.exit(1)

    if args.context_col not in df.columns:
        print(f"⚠️  Context column '{args.context_col}' not found — using empty context.")
        df[args.context_col] = ""

    print(f"\n🤖 Starting pydantic-ai agent (max {args.concurrent} concurrent calls)...\n")
    start = time.time()

    # ── Run the agentic workflow ──────────────────────────────────────────
    results = await process_dataframe(
        df,
        id_col=args.id_col,
        code_col=args.code_col,
        context_col=args.context_col,
        max_concurrent=args.concurrent,
    )

    # ── Write output CSV ──────────────────────────────────────────────────
    output_df = pd.DataFrame(results, columns=["ID", "Bug Line", "Explanation"])
    output_df.to_csv(output_path, index=False)

    elapsed = time.time() - start
    success  = sum(1 for r in results if r["Bug Line"] != -1)
    failed   = len(results) - success

    print(f"\n{'═'*60}")
    print(f"✅ COMPLETE in {elapsed:.1f}s")
    print(f"   ✔ {success} samples processed successfully")
    if failed:
        print(f"   ✘ {failed} sample(s) failed (check explanation column)")
    print(f"📄 Output → {output_path}")
    print(f"{'═'*60}\n")


def main():
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
