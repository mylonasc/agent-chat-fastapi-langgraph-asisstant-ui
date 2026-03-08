import mimetypes
import requests
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    WebBaseLoader,
    PyPDFLoader,
    Docx2txtLoader,
)


class ContentLoader:
    """
    Unified ingestion entrypoint supporting:
    - HTML (URL)
    - PDF (local path or URL)
    - DOCX (local path)
    """

    @staticmethod
    def load(source: str) -> List[Document]:
        if source.startswith("http"):
            return ContentLoader._load_from_url(source)

        path = Path(source)
        if not path.exists():
            raise ValueError(f"Source not found: {source}")

        return ContentLoader._load_from_file(path)

    @staticmethod
    def _load_from_url(url: str) -> List[Document]:
        # Try content-type detection
        resp = requests.head(url, allow_redirects=True, timeout=10)
        content_type = resp.headers.get("content-type", "")

        if "pdf" in content_type:
            # Download and parse as PDF
            tmp = requests.get(url, timeout=30)
            tmp.raise_for_status()
            tmp_path = Path("/tmp/temp_ingest.pdf")
            tmp_path.write_bytes(tmp.content)
            loader = PyPDFLoader(str(tmp_path))
            return loader.load()

        # Default: treat as HTML
        loader = WebBaseLoader(url)
        return loader.load()

    @staticmethod
    def _load_from_file(path: Path) -> List[Document]:
        mime, _ = mimetypes.guess_type(str(path))

        if mime and "pdf" in mime:
            loader = PyPDFLoader(str(path))
            return loader.load()

        if mime and ("word" in mime or path.suffix.lower() == ".docx"):
            loader = Docx2txtLoader(str(path))
            return loader.load()

        # Fallback: read as plain text
        text = path.read_text()
        return [Document(page_content=text, metadata={"source": str(path)})]
