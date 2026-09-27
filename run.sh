#!/usr/bin/env bash
set -e

echo "============================================================"
echo "    GlobalTech HR Multi-Agent Automation System (LangGraph)  "
echo "============================================================"

# Check if venv exists
if [ -d ".venv" ]; then
    echo "[*] Activating virtual environment (.venv)..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "[*] Activating virtual environment (venv)..."
    source venv/bin/activate
else
    echo "[*] Creating .venv..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Ensure policy database is indexed
if [ ! -d "chroma_db" ]; then
    echo "[*] Indexing HR policy documents into ChromaDB..."
    python src/rag/ingest.py
fi

echo "[*] Starting MCP Server in background on port 8001..."
python src/mcp/server.py &
MCP_PID=$!

echo "[*] Starting FastAPI Backend on port 8000..."
python src/api/server.py &
API_PID=$!

echo "[*] Starting Streamlit Web Application on port 8501..."
cleanup() {
    echo -e "\n[*] Shutting down HR Multi-Agent services..."
    kill $MCP_PID 2>/dev/null || true
    kill $API_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

streamlit run app.py --server.port 8501 --server.address 0.0.0.0
