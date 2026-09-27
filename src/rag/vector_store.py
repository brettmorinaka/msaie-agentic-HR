import os
import math
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

from src.config import CHROMA_PERSIST_DIR, DEFAULT_TOP_K
from src.rag.chunker import PolicyChunk

class DeterministicFallbackEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Deterministic embedding function based on normalized token hashing.
    Used if remote model download is unavailable or for ultra-fast deterministic testing.
    Produces 384-dimensional unit vectors.
    """
    def __init__(self, dim: int = 384):
        self.dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            vec = [0.0] * self.dim
            words = text.lower().split()
            if not words:
                embeddings.append(vec)
                continue
            for word in words:
                # 3 different hash seeds to distribute features across dimensions
                for seed in range(3):
                    h = int(hashlib.md5(f"{word}_{seed}".encode("utf-8")).hexdigest(), 16)
                    idx = h % self.dim
                    sign = 1.0 if ((h >> 16) & 1) else -1.0
                    vec[idx] += sign

            # Normalize to unit length
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings


class PolicyVectorStore:
    """Manages ChromaDB vector collection for HR Policy documents."""

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "hr_policies",
        use_fallback_embeddings: bool = False
    ):
        self.persist_dir = str(persist_dir or CHROMA_PERSIST_DIR)
        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection_name = collection_name
        self.use_fallback_embeddings = use_fallback_embeddings

        embedding_fn = None
        if self.use_fallback_embeddings or os.getenv("OFFLINE_MODE", "0") == "1":
            embedding_fn = DeterministicFallbackEmbeddingFunction()

        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=embedding_fn,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            # Fallback if default model download failed
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=DeterministicFallbackEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"}
            )

    def add_chunks(self, chunks: List[PolicyChunk]) -> int:
        if not chunks:
            return 0

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "document_id": c.document_id,
                "document_title": c.document_title,
                "category": c.category,
                "section_title": c.section_title,
                "source_file": c.source_file,
                "snippet": c.snippet
            }
            for c in chunks
        ]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        filter_category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        where_clause = None
        if filter_category:
            where_clause = {"category": filter_category}

        count = self.collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)
        results = self.collection.query(
            query_texts=[query],
            n_results=actual_k,
            where=where_clause
        )

        formatted_results = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metadatas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
            distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
            ids = results["ids"][0] if "ids" in results else [""] * len(docs)

            for i in range(len(docs)):
                meta = metadatas[i] or {}
                # Cosine similarity = 1 - cosine distance
                dist = distances[i] if i < len(distances) else 0.0
                score = round(max(0.0, 1.0 - dist), 4)

                formatted_results.append({
                    "chunk_id": ids[i],
                    "text": docs[i],
                    "document_id": meta.get("document_id", "UNKNOWN"),
                    "document_title": meta.get("document_title", "HR Policy"),
                    "category": meta.get("category", "General"),
                    "section_title": meta.get("section_title", ""),
                    "source_file": meta.get("source_file", ""),
                    "snippet": meta.get("snippet", docs[i][:150]),
                    "similarity_score": score
                })

        return formatted_results

    def get_section(self, document_id: str, section_title: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific section by document ID and section title."""
        results = self.collection.get(
            where={"$and": [{"document_id": document_id}, {"section_title": section_title}]}
        )
        if results and results.get("documents"):
            return {
                "document_id": document_id,
                "section_title": section_title,
                "text": results["documents"][0],
                "metadata": results["metadatas"][0] if results.get("metadatas") else {}
            }
        # Fallback: search by document_id only
        doc_results = self.collection.get(where={"document_id": document_id})
        if doc_results and doc_results.get("documents"):
            for i, meta in enumerate(doc_results["metadatas"]):
                if section_title.lower() in meta.get("section_title", "").lower():
                    return {
                        "document_id": document_id,
                        "section_title": meta.get("section_title"),
                        "text": doc_results["documents"][i],
                        "metadata": meta
                    }
        return None

    def count(self) -> int:
        return self.collection.count()
