import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
POLICIES_DIR = DATA_DIR / "policies"
EMPLOYEES_FILE = DATA_DIR / "employees.json"
TICKETS_FILE = DATA_DIR / "tickets.json"
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_db")))

# MCP Configuration
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", f"http://localhost:{MCP_SERVER_PORT}/mcp")
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http")

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))

# LLM Configuration (OpenRouter is the chosen primary LLM provider)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter" if os.getenv("OPENROUTER_API_KEY") else "auto")
LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free"))

# RAG & Chunking
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "3"))
CHUNK_SIZE_TOKENS = int(os.getenv("CHUNK_SIZE_TOKENS", "400"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "60"))
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
