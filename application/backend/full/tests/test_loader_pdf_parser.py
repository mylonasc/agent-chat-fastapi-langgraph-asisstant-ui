from pathlib import Path

from langchain_core.documents import Document

from tools.web_rag.ingestion.loader import ContentLoader


def test_loader_uses_docling_for_pdf_when_configured(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("not real pdf", encoding="utf-8")

    monkeypatch.setattr(
        "tools.web_rag.ingestion.loader.parse_pdf_with_docling",
        lambda path, source, device: [
            Document(page_content=f"docling:{device}", metadata={"source": source})
        ],
    )

    docs = ContentLoader.load(
        str(pdf_path),
        parser_config={"pdf_parser": "docling", "docling_device": "cpu"},
    )

    assert docs[0].page_content == "docling:cpu"


def test_loader_uses_pypdf_for_pdf_by_default(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("not real pdf", encoding="utf-8")

    class DummyLoader:
        def __init__(self, path: str):
            self.path = path

        def load(self):
            return [Document(page_content="pypdf", metadata={"source": self.path})]

    monkeypatch.setattr("tools.web_rag.ingestion.loader.PyPDFLoader", DummyLoader)

    docs = ContentLoader.load(str(pdf_path), parser_config={})

    assert docs[0].page_content == "pypdf"
    assert Path(docs[0].metadata["source"]).name == "sample.pdf"
