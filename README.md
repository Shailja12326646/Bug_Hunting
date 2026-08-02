# Agentic Bug Hunter — Multi-Agent AI System

An **Enterprise Multi-Agent Pipeline** built to autonomously detect, explain, and fix bugs in Infineon SmartRDI C++ code snippets. 

This solution uses `pydantic-ai`, the HuggingFace Qwen2.5-72B LLM, and the standard Model Context Protocol (MCP) to achieve high-precision, line-level bug detection without hardcoding any proprietary knowledge.

---

## 🏗️ Architecture Overview

Instead of relying on a single prompt to do everything, the problem is split into highly specialized AI Agents. These agents are managed by a central **Orchestrator** that acts like a supervisor. 

### Flow of Data (per code snippet)

1. **`main.py`** and **`workflow.py`** load the CSV and throttle the processing speed.
2. The **Orchestrator Agent** takes a single C++ code snippet.
3. **`code_parser.py`** numbers every line of the code (Line 1, Line 2).
4. **Retriever Agent** asks the MCP server for specific Infineon documentation.
5. **Detector Agent** compares the numbered code against the documentation to find the exact line containing the bug.
6. **Explainer Agent** writes a professional explanation + fix.
7. The **Orchestrator** saves everything to `output.csv`.

---

## 🤖 The Agents Explained

Here is a step-by-step breakdown of every file in the `code/` directory:

### 1. `config.py` (The Settings File)
Loads the HuggingFace token from `.env` and stores the MCP Server URL. If models or URLs change, it only changes here.

### 2. `main.py` & `workflow.py` (CLI & Batch Processor)
`main.py` is the entry point (`python code/main.py`). `workflow.py` uses `asyncio` to process the CSV rows concurrently while avoiding rate limits on the HuggingFace API.

### 3. `agents/models.py` (The Blueprint)
Defines strict rules (Pydantic schemas) for what an agent must output. For example, it forces the Detector to reply with exactly: `bug_line` (int), `bug_type` (str), and `confidence` (float). By forcing JSON, we eliminate parsing errors.

### 4. `agents/code_parser.py` (The Prep Tool)
Takes raw C++ code and adds line numbers (`Line 1: ...`, `Line 2: ...`). This simple step is the secret to getting integer line-level accuracy from the LLM.

### 5. `agents/orchestrator_agent.py` (The Supervisor)
Manages the pipeline. It hands the code to the Retriever, then coordinates the Detector. If the Detector says "I'm only 40% confident," the Orchestrator pauses, asks the Retriever to fetch more specific docs, and tries the Detector again.

### 6. `agents/retriever_agent.py` (The Librarian)
Looks at the buggy C++ code and generates a natural-language search query (e.g., *"How does iClamp work?"*). It sends this to the MCP Server and waits for the official documentation.

### 7. `agents/detector_agent.py` (The Core Engine)
Is given the *numbered code* and the *official documentation*. Its prompt forces it to compare the two. It outputs a strict JSON object with just the exact `bug_line` integer.

### 8. `agents/explainer_agent.py` (The Technical Writer)
Takes the known `bug_line` and reads the documentation again. Writes a professional 2-3 sentence explanation of *why* the code is wrong and suggests the correct code fix.

---

## 🧠 Embeddings & Vector DB: How the MCP Works

**Yes, we are using Embeddings and a Vector Database** — but they are completely encapsulated and hidden inside the **Infineon MCP Server**.

The MCP Server acts as an isolated "Black Box" knowledge engine. Here is what happens under the hood inside the `server/` folder provided by Infineon:

1. **Storage (`server/storage/`)**: This is a local Vector Database (built with `llama-index`). It contains all of the Infineon SmartRDI documentation, pre-chunked and stored as mathematical vectors.
2. **Embedding Model (`server/embedding_model/`)**: This is the BAAI/bge-base-en-v1.5 model. It is responsible for turning English text into vectors.
3. **The Search Process**:
   * When our **Retriever Agent** sends a text query (e.g. *"vForceRange limit"*), it goes over HTTP to port 8003.
   * Inside `server/mcp_server.py`, the query is passed to the **Embedding Model** and turned into a vector.
   * That vector is mathematically compared against all the document vectors in the **Vector DB**.
   * The server finds the closest matching chunks of documentation and returns the raw text back to our Agent.

**Why this is powerful:** 
The Agentic Bug Hunter code does not need to know *how* to do cosine similarity or load gigabytes of PyTorch models. It just asks the MCP Server a question, and the server handles the heavy lifting of Embeddings and Vector Search.

---

## 🚀 How to Run

1. Start the MCP knowledge server:
```bash
python server/mcp_server.py
```

2. Run the Multi-Agent Pipeline:
```bash
python code/main.py
```
*(Produces `output.csv` automatically).*
