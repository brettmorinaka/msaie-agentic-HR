import pytest
from pathlib import Path
from src.config import POLICIES_DIR, CHROMA_PERSIST_DIR
from src.rag.parser import PolicyParser
from src.rag.chunker import HeadingAwareChunker
from src.rag.vector_store import PolicyVectorStore

def test_policy_parser_markdown():
    md_file = POLICIES_DIR / "remote_work_policy.md"
    assert md_file.exists()
    parsed = PolicyParser.parse_file(md_file)
    assert parsed["format"] == "markdown"
    assert parsed["document_id"] == "POL-REMOTE-2024"
    assert "Remote & Hybrid" in parsed["title"]
    assert len(parsed["raw_content"]) > 100

def test_policy_parser_html():
    html_file = POLICIES_DIR / "benefits_health_policy.html"
    assert html_file.exists()
    parsed = PolicyParser.parse_file(html_file)
    assert parsed["format"] == "html"
    assert parsed["document_id"] == "POL-BEN-2024"
    assert "Health" in parsed["title"]
    assert "Premier PPO Plan" in parsed["raw_content"]

def test_policy_parser_text():
    txt_file = POLICIES_DIR / "code_of_conduct.txt"
    assert txt_file.exists()
    parsed = PolicyParser.parse_file(txt_file)
    assert parsed["format"] == "text"
    assert parsed["document_id"] == "POL-ETHICS-2024"
    assert "CODE OF BUSINESS ETHICS" in parsed["raw_content"]

def test_heading_aware_chunker():
    md_file = POLICIES_DIR / "pto_leave_policy.md"
    parsed = PolicyParser.parse_file(md_file)
    chunker = HeadingAwareChunker(max_words=250, overlap_words=40)
    chunks = chunker.chunk_document(parsed)

    assert len(chunks) >= 5
    for chk in chunks:
        assert chk.document_id == "POL-PTO-2024"
        assert chk.section_title != ""
        assert chk.snippet != ""
        assert len(chk.text) > 20

def test_vector_store_search():
    vs = PolicyVectorStore(persist_dir=str(CHROMA_PERSIST_DIR), use_fallback_embeddings=True)
    assert vs.count() > 0

    results = vs.search("What is the equipment allowance for remote work?", top_k=3)
    assert len(results) > 0
    assert results[0]["document_id"] in ["POL-REMOTE-2024", "POL-BEN-2024", "POL-EXP-2024"]
    assert "snippet" in results[0]
    assert results[0]["similarity_score"] >= 0.0
