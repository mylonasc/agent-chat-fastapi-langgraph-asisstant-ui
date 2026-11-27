import json
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS


class FAISSStore:
    """
    Production FAISS-backed vector store with per-user persistence.
    """

    def __init__(self, base_path: str, user_id: str, embeddings):
        self.embeddings = embeddings
        self.path = Path(base_path) / f"user_{user_id}"
        self.path.mkdir(parents=True, exist_ok=True)

        self.docs_path = self.path / "documents.json"
        self.store = None
        self.documents: List[Document] = []

        # Load FAISS index if exists
        if (self.path / "index.faiss").exists():
            self.store = FAISS.load_local(
                str(self.path),
                self.embeddings,
                allow_dangerous_deserialization=True,
            )

        # Load raw docs if exist
        if self.docs_path.exists():
            raw = json.loads(self.docs_path.read_text())
            self.documents = [
                Document(page_content=d["content"], metadata=d["metadata"]) for d in raw
            ]

    def add_documents(self, docs: List[Document]):
        if self.store is None:
            self.store = FAISS.from_documents(docs, self.embeddings)
        else:
            self.store.add_documents(docs)

        self.documents.extend(docs)

    def save(self):
        if self.store is None:
            return

        self.store.save_local(str(self.path))

        self.docs_path.write_text(
            json.dumps(
                [
                    {"content": d.page_content, "metadata": d.metadata}
                    for d in self.documents
                ]
            )
        )

    def as_dense_retriever(self, k=5):
        if self.store is None:
            raise ValueError("Vector store empty.")
        return self.store.as_retriever(search_kwargs={"k": k})

    def get_all_documents(self):
        return self.documents
