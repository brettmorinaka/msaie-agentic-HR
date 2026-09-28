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
    """
    Ingests all policy documents from policies_dir into the Chroma vector database.

    Pipeline Overview:
    1. Validate directory existence.
    2. Initialize ChromaDB vector store with the designated embedding function.
    3. Initialize the HeadingAwareChunker with token window and overlap limits.
    4. Discover all supported multi-format policy documents (.md, .html, .txt).
    5. Parse each document to extract metadata (Document ID, title, category) and content.
    6. Segment parsed documents into heading-aware semantic chunks with source snippets.
    7. Batch upsert all chunks and metadata into ChromaDB.
    8. Report summary statistics and return ingestion metadata.
    """
    print(f"[*] Starting Policy Corpus Ingestion from: {policies_dir}")

    # Step 1: Validate that the policies source directory exists
    if not policies_dir.exists():
        raise FileNotFoundError(f"Policies directory not found: {policies_dir}")

    # Step 2: Initialize or connect to the persistent ChromaDB collection
    # Uses deterministic fallback embeddings if offline or during testing to avoid download stalls
    vector_store = PolicyVectorStore(
        persist_dir=str(persist_dir),
        use_fallback_embeddings=use_fallback_embeddings
    )

    # Step 3: Initialize the semantic chunker
    # Uses heading-aware chunking (max 250 words per chunk with 40-word overlap)
    # to keep policy rules and their respective eligibility conditions intact
    chunker = HeadingAwareChunker(max_words=250, overlap_words=40)
    all_chunks: List[PolicyChunk] = []
    file_stats = []

    # Step 4: Discover all policy files matching supported formats (.md, .html, .htm, .txt)
    # Sorted alphabetically to guarantee deterministic indexing across runs
    supported_extensions = [".md", ".html", ".htm", ".txt"]
    policy_files = sorted([
        f for f in policies_dir.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ])

    # Guard clause: verify that at least one policy file was located
    if not policy_files:
        print("[!] No policy documents found to ingest!")
        return {"total_files": 0, "total_chunks": 0}

    # Step 5: Process each policy document
    for p_file in policy_files:
        try:
            # 5a. Parse document using format-specific extractors (Markdown frontmatter, HTML DOM, or text headers)
            parsed = PolicyParser.parse_file(p_file)

            # 5b. Chunk document while preserving section titles, Document IDs, and source snippets
            chunks = chunker.chunk_document(parsed)
            all_chunks.extend(chunks)

            # 5c. Record individual file ingestion telemetry
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

    # Step 6: Upsert all generated chunks into the Chroma vector store
    # Chunks are stored with full text and metadata (doc_id, section_title, snippet, file_name)
    added_count = vector_store.add_chunks(all_chunks)
    total_stored = vector_store.count()

    print(f"\n[+] Ingestion Complete! Successfully indexed {added_count} chunks across {len(policy_files)} documents.")
    print(f"[+] Total items in Chroma collection: {total_stored}")

    # Step 7: Return comprehensive ingestion summary dictionary
    return {
        "total_files": len(policy_files),
        "total_chunks": added_count,
        "collection_count": total_stored,
        "files": file_stats
    }


if __name__ == "__main__":
    # Command-line entrypoint for manual or script-triggered re-indexing
    ingest_policies()
