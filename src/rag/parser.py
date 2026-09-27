import re
from pathlib import Path
from html.parser import HTMLParser
from typing import Dict, Any, List

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts: List[str] = []
        self.metadata: Dict[str, str] = {}
        self.in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        attrs_dict = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            name = attrs_dict.get("name", "")
            content = attrs_dict.get("content", "")
            if name and content:
                self.metadata[name] = content
        elif tag in ["p", "h1", "h2", "h3", "h4", "li", "section", "article"]:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag == "title":
            self.in_title = False
        elif tag in ["p", "h1", "h2", "h3", "h4", "li", "section", "article"]:
            self.text_parts.append("\n")

    def handle_data(self, data: str):
        if self.in_title:
            self.title += data.strip()
        cleaned = data.strip()
        if cleaned:
            self.text_parts.append(cleaned + " ")

    def get_text(self) -> str:
        raw = "".join(self.text_parts)
        # Normalize consecutive blank lines
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


class PolicyParser:
    """Parses Markdown, HTML, and Plain Text policy files."""

    @staticmethod
    def parse_file(file_path: Path) -> Dict[str, Any]:
        suffix = file_path.suffix.lower()
        content = file_path.read_text(encoding="utf-8")

        if suffix in [".md", ".markdown"]:
            return PolicyParser._parse_markdown(content, file_path)
        elif suffix in [".html", ".htm"]:
            return PolicyParser._parse_html(content, file_path)
        elif suffix in [".txt", ".text"]:
            return PolicyParser._parse_text(content, file_path)
        else:
            # Fallback
            return PolicyParser._parse_text(content, file_path)

    @staticmethod
    def _parse_markdown(content: str, file_path: Path) -> Dict[str, Any]:
        # Extract title from first # header
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file_path.stem.replace("_", " ").title()

        # Extract Document ID
        doc_id_match = re.search(r"\*\*Document ID:\*\*\s*([A-Za-z0-9_-]+)", content)
        doc_id = doc_id_match.group(1).strip() if doc_id_match else f"DOC-{file_path.stem.upper()}"

        # Extract Category
        cat_match = re.search(r"\*\*Category:\*\*\s*(.+)$", content, re.MULTILINE)
        category = cat_match.group(1).strip() if cat_match else "General Policy"

        return {
            "document_id": doc_id,
            "title": title,
            "category": category,
            "format": "markdown",
            "file_name": file_path.name,
            "raw_content": content
        }

    @staticmethod
    def _parse_html(content: str, file_path: Path) -> Dict[str, Any]:
        parser = HTMLTextExtractor()
        parser.feed(content)
        title = parser.title or parser.metadata.get("title", file_path.stem.replace("_", " ").title())
        doc_id = parser.metadata.get("document_id", f"DOC-{file_path.stem.upper()}")
        category = parser.metadata.get("category", "General Policy")
        text = parser.get_text()

        return {
            "document_id": doc_id,
            "title": title,
            "category": category,
            "format": "html",
            "file_name": file_path.name,
            "raw_content": text
        }

    @staticmethod
    def _parse_text(content: str, file_path: Path) -> Dict[str, Any]:
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        title = lines[0] if lines else file_path.stem.replace("_", " ").title()

        doc_id_match = re.search(r"Document ID:\s*([A-Za-z0-9_-]+)", content)
        doc_id = doc_id_match.group(1).strip() if doc_id_match else f"DOC-{file_path.stem.upper()}"

        cat_match = re.search(r"Category:\s*(.+)$", content, re.MULTILINE)
        category = cat_match.group(1).strip() if cat_match else "General Policy"

        return {
            "document_id": doc_id,
            "title": title,
            "category": category,
            "format": "text",
            "file_name": file_path.name,
            "raw_content": content
        }
