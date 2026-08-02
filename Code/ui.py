"""
ui.py — Agentic Bug Hunter Interactive Streamlit UI (Bonus Feature)
--------------------------------------------------------------------
Launch with:
    streamlit run code/ui.py

Features:
  - Paste any C++ code → click Analyze → see bug line highlighted in red
  - Shows retrieved documentation context
  - Download output.csv
"""

import streamlit as st
import pandas as pd
import sys
import os
import io

# Ensure code/ is on path
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
from config import CSV_INPUT, CSV_OUTPUT
from agents.code_parser import parse_code, format_numbered_code
from agents.orchestrator_agent import run_pipeline, _retriever_agent


# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic Bug Hunter | Infineon",
    page_icon="🐛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS (Premium Dark Theme) ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark background */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1321 50%, #0a0e1a 100%);
    color: #e2e8f0;
}

/* Header */
.main-header {
    background: linear-gradient(90deg, #1a0533 0%, #0d1b4b 50%, #001a3a 100%);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 28px;
    box-shadow: 0 8px 32px rgba(99, 102, 241, 0.15);
}
.main-header h1 { 
    font-size: 2.2rem; 
    font-weight: 700; 
    background: linear-gradient(90deg, #818cf8, #38bdf8, #34d399);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0 0 6px 0;
}
.main-header p { color: #94a3b8; margin: 0; font-size: 0.95rem; }

/* Cards */
.card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}

/* Bug line highlight */
.code-line { 
    font-family: 'JetBrains Mono', monospace; 
    font-size: 0.82rem; 
    padding: 3px 10px; 
    border-radius: 4px;
    line-height: 1.7;
    white-space: pre;
}
.code-line.bug-line {
    background: rgba(239, 68, 68, 0.18);
    border-left: 3px solid #ef4444;
    color: #fca5a5;
    font-weight: 500;
}
.code-line.normal-line { color: #94a3b8; }

/* Result badges */
.badge-red   { background: rgba(239,68,68,0.15);  color: #f87171; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(239,68,68,0.3); }
.badge-blue  { background: rgba(59,130,246,0.15); color: #60a5fa; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(59,130,246,0.3); }
.badge-green { background: rgba(52,211,153,0.15); color: #34d399; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(52,211,153,0.3); }

/* Explanation box */
.explanation-box {
    background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(56,189,248,0.08));
    border: 1px solid rgba(99,102,241,0.25);
    border-radius: 12px;
    padding: 20px;
    font-size: 0.95rem;
    line-height: 1.7;
    color: #e2e8f0;
}

/* Docs box */
.docs-box {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 14px;
    font-size: 0.78rem;
    font-family: 'JetBrains Mono', monospace;
    color: #64748b;
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 10px 28px !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #818cf8, #6366f1) !important;
    box-shadow: 0 0 20px rgba(99,102,241,0.4) !important;
    transform: translateY(-1px) !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: rgba(10, 14, 26, 0.95) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}

/* Inputs */
.stTextArea textarea, .stSelectbox select {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
}

/* Remove Streamlit default padding */
.block-container { padding-top: 1rem !important; }

/* Status pills */
.status-running { color: #fbbf24; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🐛 Agentic Bug Hunter</h1>
    <p>Infineon SmartRDI C++ Bug Detection · Powered by Qwen2.5-72B + MCP Knowledge Server</p>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    mcp_status = st.empty()
    mcp_status.info("🔌 MCP Server: localhost:8003")

    st.markdown("---")
    st.markdown("### 📖 How it works")
    st.markdown("""
1. **Code Parser** — Numbers every line  
2. **MCP Retriever** — Searches Infineon docs  
3. **Bug Detector** — LLM finds exact bug line  
4. **Explainer** — LLM writes explanation  
    """)

    st.markdown("---")
    st.markdown("### 📂 Batch Process (samples.csv)")
    if st.button("🚀 Run on Entire Dataset"):
        st.session_state['run_batch'] = True

    st.markdown("---")
    st.markdown("### 📊 Download Output")
    if os.path.exists(CSV_OUTPUT):
        with open(CSV_OUTPUT, 'rb') as f:
            st.download_button(
                label="⬇️ Download output.csv",
                data=f.read(),
                file_name="output.csv",
                mime="text/csv"
            )
    else:
        st.caption("Run analysis first to generate output.csv")


# ── Main UI – Tabs ────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🔍 Single Analysis", "📋 Batch Results", "📚 Dataset Viewer"])


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — Single Code Analysis
# ═══════════════════════════════════════════════════════════════════
with tab1:
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("#### 📝 Paste C++ Code")

        # Pre-fill with a sample from CSV
        sample_options = {"(Blank)": ""}
        try:
            df_samples = pd.read_csv(CSV_INPUT)
            for _, r in df_samples.iterrows():
                sample_options[f"Sample ID {r['ID']}"] = r['Code']
        except Exception:
            pass

        selected_sample = st.selectbox("Quick-load a sample:", list(sample_options.keys()))
        default_code = sample_options.get(selected_sample, "")

        code_input = st.text_area(
            label="C++ Code",
            value=default_code,
            height=280,
            placeholder="Paste your Infineon RDI C++ code here...",
            label_visibility="collapsed",
        )

        context_input = st.text_input(
            "Code Context (optional):",
            placeholder="e.g. 'Reading humidity sensor from PMUX card'",
        )

        analyze_btn = st.button("🔍 Analyze Bug", use_container_width=True)

    with col_right:
        st.markdown("#### 📊 Analysis Result")

        if analyze_btn and code_input.strip():
            with st.spinner("🔄 Running agent pipeline..."):
                numbered_lines = parse_code(code_input)

                status_ph = st.empty()
                status_ph.markdown('<p class="status-running">🤖 Running Orchestrator Agent pipeline...</p>', unsafe_allow_html=True)
                
                pipeline_res = asyncio.run(run_pipeline("UI_SAMPLE", code_input, context_input))
                retrieved_docs = asyncio.run(_retriever_agent(code_input, context_input))
                
                bug_lines_str = pipeline_res.get("Bug Line", "-1")
                explanation   = pipeline_res.get("Explanation", "")
                status_ph.empty()

                # Parse bug lines into set of ints
                bug_line_nums = set()
                for line_part in str(bug_lines_str).splitlines():
                    for token in line_part.split(','):
                        if token.strip().lstrip('-').isdigit():
                            bug_line_nums.add(int(token.strip()))

            # ── Results display ───────────────────────────────────────────
            st.markdown(
                f'<span class="badge-red">🐛 Bug Line(s): {bug_lines_str.replace(chr(10), ", ")}</span>&nbsp;&nbsp;'
                f'<span class="badge-blue">🤖 Qwen2.5-72B</span>&nbsp;&nbsp;'
                f'<span class="badge-green">📚 MCP Docs Retrieved</span>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)

            # Highlighted code
            st.markdown("**Code with Bug Highlighted:**")
            code_html = ""
            for num, line in numbered_lines:
                css_class = "bug-line" if num in bug_line_nums else "normal-line"
                prefix    = "🔴 " if num in bug_line_nums else "   "
                escaped   = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                code_html += f'<div class="code-line {css_class}">{prefix}Line {num:>3}: {escaped}</div>'
            st.markdown(f'<div class="card">{code_html}</div>', unsafe_allow_html=True)

            # Explanation
            st.markdown("**Bug Explanation:**")
            st.markdown(f'<div class="explanation-box">{explanation}</div>', unsafe_allow_html=True)

            # MCP docs (expandable)
            with st.expander("📚 View Retrieved Documentation Context"):
                st.markdown(f'<div class="docs-box">{retrieved_docs[:2000]}...</div>', unsafe_allow_html=True)

        elif analyze_btn:
            st.warning("Please paste some C++ code first.")
        else:
            st.markdown("""
<div class="card" style="text-align:center; padding: 60px 20px; color: #475569;">
    <div style="font-size: 3rem; margin-bottom: 12px;">🐛</div>
    <div style="font-size: 1.1rem; font-weight: 500; color: #64748b;">Paste code and click Analyze</div>
    <div style="font-size: 0.85rem; margin-top: 8px; color: #475569;">The agent will find the exact bug line and explain it</div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — Batch Results
# ═══════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("#### 📋 Batch Output (output.csv)")

    if os.path.exists(CSV_OUTPUT):
        result_df = pd.read_csv(CSV_OUTPUT)
        st.markdown(
            f'<span class="badge-green">✅ {len(result_df)} samples processed</span>',
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(
            result_df,
            use_container_width=True,
            height=500,
            column_config={
                "ID":          st.column_config.NumberColumn("ID", width="small"),
                "Bug Line":    st.column_config.NumberColumn("Bug Line", width="small"),
                "Explanation": st.column_config.TextColumn("Explanation", width="large"),
            },
        )
    else:
        st.info("No output.csv found yet. Run `python code/main.py` or use the sidebar batch button.")
        if st.session_state.get('run_batch'):
            st.warning("Batch run via sidebar is not yet supported in UI — please use the CLI: `python code/main.py`")


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — Dataset Viewer
# ═══════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### 📚 samples.csv Dataset")
    try:
        df_view = pd.read_csv(CSV_INPUT)
        st.markdown(f'<span class="badge-blue">📂 {len(df_view)} code samples loaded</span>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(
            df_view[["ID", "Context", "Explanation"]],
            use_container_width=True,
            height=400,
        )
        selected_id = st.selectbox("View full code for ID:", df_view["ID"].tolist())
        row = df_view[df_view["ID"] == selected_id].iloc[0]
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Buggy Code**")
            st.code(row['Code'], language="cpp")
        with col_b:
            st.markdown("**Correct Code**")
            st.code(row['Correct Code'], language="cpp")
    except Exception as e:
        st.error(f"Could not load dataset: {e}")
