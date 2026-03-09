import mimetypes
import os
import requests
import re
import tempfile
from html import unescape
from pathlib import Path
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
)

from .docling_adapter import parse_pdf_with_docling


class ContentLoader:
    """
    Unified ingestion entrypoint supporting:
    - HTML (URL)
    - PDF (local path or URL)
    - DOCX (local path)
    """

    @staticmethod
    def load(source: str, parser_config: dict | None = None) -> List[Document]:
        if source.startswith("http"):
            return ContentLoader._load_from_url(source, parser_config=parser_config)

        path = Path(source)
        if not path.exists():
            raise ValueError(f"Source not found: {source}")

        return ContentLoader._load_from_file(path, parser_config=parser_config)

    @staticmethod
    def _resolve_pdf_parser(parser_config: dict | None) -> Tuple[str, str]:
        cfg = parser_config or {}
        provider = str(
            cfg.get("pdf_parser")
            or cfg.get("parser_provider")
            or os.getenv("PDF_PARSER_PROVIDER", "pypdf")
        ).lower()

        device = str(
            cfg.get("docling_device")
            or os.getenv("DOCLING_DEVICE")
            or ("cuda" if provider.endswith("gpu") else "cpu")
        ).lower()

        if provider.startswith("docling"):
            return "docling", device
        return "pypdf", device

    @staticmethod
    def _load_from_url(url: str, parser_config: dict | None = None) -> List[Document]:
        verify_ssl = os.getenv("REQUESTS_VERIFY_SSL", "1") not in {
            "0",
            "false",
            "False",
        }
        headers = {"User-Agent": os.getenv("USER_AGENT", "fastlang-web-rag/0.1")}

        # Try content-type detection
        resp = requests.head(
            url,
            allow_redirects=True,
            timeout=10,
            verify=verify_ssl,
            headers=headers,
        )
        content_type = resp.headers.get("content-type", "")

        if "pdf" in content_type:
            # Download and parse as PDF
            tmp = requests.get(
                url,
                timeout=30,
                verify=verify_ssl,
                headers=headers,
            )
            tmp.raise_for_status()
            parser, device = ContentLoader._resolve_pdf_parser(parser_config)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(tmp.content)
                tmp_path = Path(tmp_file.name)

            if parser == "docling":
                return parse_pdf_with_docling(tmp_path, source=url, device=device)

            loader = PyPDFLoader(str(tmp_path))
            return loader.load()

        # Default: fetch HTML/text and parse without external bs4 dependency
        page = requests.get(
            url,
            timeout=30,
            verify=verify_ssl,
            headers=headers,
        )
        page.raise_for_status()
        text = ContentLoader._html_to_text(page.text)
        return [Document(page_content=text, metadata={"source": url})]

    @staticmethod
    def _load_from_file(
        path: Path, parser_config: dict | None = None
    ) -> List[Document]:
        mime, _ = mimetypes.guess_type(str(path))

        if mime and "pdf" in mime:
            parser, device = ContentLoader._resolve_pdf_parser(parser_config)
            if parser == "docling":
                return parse_pdf_with_docling(path, source=str(path), device=device)
            loader = PyPDFLoader(str(path))
            return loader.load()

        if mime and ("word" in mime or path.suffix.lower() == ".docx"):
            loader = Docx2txtLoader(str(path))
            return loader.load()

        # Fallback: read as plain text
        text = path.read_text()
        return [Document(page_content=text, metadata={"source": str(path)})]

    @staticmethod
    def _html_to_text(html: str) -> str:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(" ", strip=True)
        except Exception:
            # Fallback without bs4
            no_script = re.sub(
                r"<script[\\s\\S]*?</script>|<style[\\s\\S]*?</style>",
                " ",
                html,
                flags=re.IGNORECASE,
            )
            no_tags = re.sub(r"<[^>]+>", " ", no_script)
            return re.sub(r"\\s+", " ", unescape(no_tags)).strip()
