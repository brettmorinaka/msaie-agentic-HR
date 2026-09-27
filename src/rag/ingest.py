import sys
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import POLICIES_DIR, CHROMA_PERSIST_DIR
from src.rag.parser import PolicyParser
from src.rag.chunker import HeadingAwareChunker, PolicyChunk
from src.rag.vector_store import PolicyVectorStore


def ingest_policies(
    policies_dir: Path = POLICIES_DIR,
    persist_dir: Path = CHROMA_PERSIST_DIR,
    use_fallback_embeddings: bool = True
) -> Dict[str, Any]:
    """Ingests all policy documents in policies_dir into the vector database."""
    print(f"[*] Starting Policy Corpus Ingestion from: {policies_dir}")

    if not policies_dir.exists():
        raise FileNotFoundError(f"Policies directory not found: {policies_dir}")

    vector_store = PolicyVectorStore(
        persist_dir=str(persist_dir),
        use_fallback_embeddings=use_fallback_embeddings
    )

    chunker = HeadingAwareChunker(max_words=250, overlap_words=40)
    all_chunks: List[PolicyChunk] = []
    file_stats = []

    # Find supported policy files
    supported_extensions = [".md", ".html", ".htm", ".txt"]
    policy_files = sorted([
        f for f in policies_dir.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ])

    if not policy_files:
        print("[!] No policy documents found to ingest!")
        return {"total_files": 0, "total_chunks": 0}

    for p_file in policy_files:
        try:
            parsed = PolicyParser.parse_file(p_file)
            chunks = chunker.chunk_document(parsed)
            all_chunks.extend(chunks)
            file_stats.append({
                "file": p_file.name,
                "document_id": parsed["document_id"],
                "format": parsed["format"],
                "title": parsed["title"],
                "chunks_count": len(chunks)
            })
            print(f"  + Parsed '{p_file.name}' ({parsed['format']}): {len(chunks)} chunks, ID: {parsed['document_id']}")
        except Exception as e:
            print(f"  [!] Error parsing {p_file.name}: {e}")

    # Add chunks to vector store
    added_count = vector_store.add_chunks(all_chunks)
    total_stored = vector_store.count()

    print(f"\n[+] Ingestion Complete! Successfully indexed {added_count} chunks across {len(policy_files)} documents.")
    print(f"[+] Total items in Chroma collection: {total_stored}")

    return {
        "total_files": len(policy_files),
        "total_chunks": added_count,
        "collection_count": total_stored,
        "files": file_stats
    }


if __name__ == "__main__":
    ingest_policies()
