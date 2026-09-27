FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ingest policy documents into ChromaDB
RUN python src/rag/ingest.py

# Expose ports for Streamlit (8501) and API/MCP (8000)
EXPOSE 8501 8000 8001

ENV PYTHONUNBUFFERED=1
ENV PORT=8501

# Start script
CMD ["sh", "-c", "uvicorn src.api.server:app --host 0.0.0.0 --port 8000 & streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"]
