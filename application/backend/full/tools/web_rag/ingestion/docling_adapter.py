from pathlib import Path
from typing import List

from langchain_core.documents import Document


def _extract_text_from_docling_result(result) -> str:
    candidates = []

    doc = getattr(result, "document", None)
    if doc is not None:
        for method_name in ("export_to_markdown", "export_to_text"):
            method = getattr(doc, method_name, None)
            if callable(method):
                try:
                    candidates.append(method())
                except Exception:
                    pass

    text_attr = getattr(result, "text", None)
    if isinstance(text_attr, str):
        candidates.append(text_attr)

    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c

    return ""


def parse_pdf_with_docling(
    pdf_path: Path, source: str, device: str = "cpu"
) -> List[Document]:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as e:
        raise RuntimeError(
            "Docling is not installed. Install backend with docling extras (docling-cpu or docling-gpu)."
        ) from e

    # Best-effort device selection for future compatibility.
    # Not all Docling versions expose runtime device settings in the same way.
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    text = _extract_text_from_docling_result(result)

    if not text.strip():
        raise RuntimeError("Docling conversion produced empty text.")

    return [
        Document(
            page_content=text,
            metadata={"source": source, "parser": "docling", "device": device},
        )
    ]
