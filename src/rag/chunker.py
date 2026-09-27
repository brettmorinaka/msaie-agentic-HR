import re
from typing import List, Dict, Any

class PolicyChunk:
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        document_title: str,
        category: str,
        section_title: str,
        source_file: str,
        text: str,
        snippet: str
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_title = document_title
        self.category = category
        self.section_title = section_title
        self.source_file = source_file
        self.text = text
        self.snippet = snippet

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "category": self.category,
            "section_title": self.section_title,
            "source_file": self.source_file,
            "text": self.text,
            "snippet": self.snippet
        }


class HeadingAwareChunker:
    """
    Heading-aware chunker that divides documents into coherent sections based on
    markdown headers or numbered sections, and splits long sections with overlap.
    """

    def __init__(self, max_words: int = 250, overlap_words: int = 40):
        self.max_words = max_words
        self.overlap_words = overlap_words

    def chunk_document(self, parsed_doc: Dict[str, Any]) -> List[PolicyChunk]:
        raw_content = parsed_doc["raw_content"]
        doc_id = parsed_doc["document_id"]
        doc_title = parsed_doc["title"]
        category = parsed_doc["category"]
        file_name = parsed_doc["file_name"]

        # Regex for headings: markdown # or numbered uppercase titles like '1. PURPOSE'
        heading_pattern = re.compile(
            r"^(?:#{1,4}\s+([^\n]+)|(?:[0-9]+\.\s+[A-Z][^\n]+))$",
            re.MULTILINE
        )

        matches = list(heading_pattern.finditer(raw_content))
        sections = []

        if not matches:
            sections.append(("General Overview", raw_content.strip()))
        else:
            # Preamble before first header
            first_start = matches[0].start()
            if first_start > 0:
                preamble = raw_content[:first_start].strip()
                if preamble:
                    sections.append(("Metadata & Overview", preamble))

            for i, match in enumerate(matches):
                raw_title = match.group(0).strip()
                # Clean header formatting (remove leading # and whitespace)
                clean_title = re.sub(r"^#{1,4}\s*", "", raw_title).strip()
                start_idx = match.end()
                end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(raw_content)
                sec_body = raw_content[start_idx:end_idx].strip()
                if sec_body:
                    sections.append((clean_title, sec_body))

        chunks: List[PolicyChunk] = []
        for sec_idx, (sec_title, sec_text) in enumerate(sections):
            words = sec_text.split()
            if not words:
                continue

            if len(words) <= self.max_words:
                chunk_text = f"[{doc_title} | {sec_title}]\n{sec_text}"
                snippet = sec_text[:160].replace("\n", " ") + ("..." if len(sec_text) > 160 else "")
                chunk_id = f"{doc_id}-sec{sec_idx}-c0"
                chunks.append(PolicyChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    document_title=doc_title,
                    category=category,
                    section_title=sec_title,
                    source_file=file_name,
                    text=chunk_text,
                    snippet=snippet
                ))
            else:
                start = 0
                sub_idx = 0
                while start < len(words):
                    end = min(start + self.max_words, len(words))
                    window_words = words[start:end]
                    window_text = " ".join(window_words)
                    chunk_text = f"[{doc_title} | {sec_title} (Part {sub_idx+1})]\n{window_text}"
                    snippet = window_text[:160].replace("\n", " ") + ("..." if len(window_text) > 160 else "")
                    chunk_id = f"{doc_id}-sec{sec_idx}-c{sub_idx}"

                    chunks.append(PolicyChunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        document_title=doc_title,
                        category=category,
                        section_title=f"{sec_title} (Part {sub_idx+1})",
                        source_file=file_name,
                        text=chunk_text,
                        snippet=snippet
                    ))

                    if end == len(words):
                        break
                    start += (self.max_words - self.overlap_words)
                    sub_idx += 1

        return chunks
