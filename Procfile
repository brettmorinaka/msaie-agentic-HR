web: streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
api: uvicorn src.api.server:app --host 0.0.0.0 --port $PORT
mcp: python src/mcp/server.py
