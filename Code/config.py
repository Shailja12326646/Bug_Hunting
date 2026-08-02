import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# HuggingFace config
HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-72B-Instruct")

# MCP Server config
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8003/sse")

# File paths (relative to A14 root)
A14_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CSV_INPUT  = os.path.join(A14_ROOT, "samples.csv")
CSV_OUTPUT = os.path.join(A14_ROOT, "output.csv")
