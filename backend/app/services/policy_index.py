"""Policy ingestion and retrieval via ChromaDB + OpenAI embeddings."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI
from pypdf import PdfReader

from app.config import settings

DOC_ID_RE = re.compile(r"Document:\s*([A-Z]+-\d+)", re.I)
SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\.\s", re.M)


def _extract_doc_id(text: str, filename: str) -> str:
    m = DOC_ID_RE.search(text[:800])
    if m:
        return m.group(1).upper()
    return Path(filename).stem.upper()


def _chunk_text(text: str, doc_id: str, source_file: str) -> list[dict]:
    """Split policy text into section-aware chunks (PDFs use single newlines)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    chunks: list[dict] = []
    current_section = "1"
    buffer: list[str] = []
    buf_len = 0
    chunk_idx = 0

    def flush():
        nonlocal buffer, buf_len, chunk_idx
        if not buffer:
            return
        body = "\n".join(buffer)
        if len(body) < 40:
            buffer = []
            buf_len = 0
            return
        chunk_id = hashlib.sha256(
            f"{doc_id}:{current_section}:{chunk_idx}:{body[:120]}".encode()
        ).hexdigest()[:16]
        chunks.append(
            {
                "id": chunk_id,
                "text": body,
                "doc_id": doc_id,
                "section": current_section,
                "source_file": source_file,
            }
        )
        chunk_idx += 1
        buffer = []
        buf_len = 0

    for line in lines:
        sec = re.match(r"^(\d+(?:\.\d+)*)\.\s", line)
        if sec and buf_len > 400:
            flush()
            current_section = sec.group(1)
        buffer.append(line)
        buf_len += len(line) + 1
        if buf_len >= 1400:
            flush()

    flush()
    return chunks


class PolicyIndex:
    def __init__(self):
        chroma_dir = settings.resolve_path(settings.chroma_path)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="northwind_policies",
            metadata={"hnsw:space": "cosine"},
        )
        self._openai: OpenAI | None = None
        if settings.openai_api_key:
            self._openai = OpenAI(api_key=settings.openai_api_key)

    @property
    def chunk_count(self) -> int:
        return self._collection.count()

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not self._openai:
            raise RuntimeError("OPENAI_API_KEY required for embeddings")
        resp = self._openai.embeddings.create(
            model=settings.openai_embed_model,
            input=texts,
        )
        return [d.embedding for d in resp.data]

    def ingest_directory(self, policies_dir: Path) -> int:
        all_chunks: list[dict] = []
        for path in sorted(policies_dir.glob("*")):
            if path.suffix.lower() == ".pdf":
                reader = PdfReader(str(path))
                text = "\n".join(
                    p.extract_text() or "" for p in reader.pages
                ).strip()
            elif path.suffix.lower() in {".txt", ".md"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
            else:
                continue
            if not text:
                continue
            doc_id = _extract_doc_id(text, path.name)
            all_chunks.extend(_chunk_text(text, doc_id, path.name))

        if not all_chunks:
            return 0

        # Rebuild collection when re-ingesting
        try:
            self._client.delete_collection("northwind_policies")
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name="northwind_policies",
            metadata={"hnsw:space": "cosine"},
        )

        batch_size = 64
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i : i + batch_size]
            embeddings = self._embed([c["text"] for c in batch])
            self._collection.add(
                ids=[c["id"] for c in batch],
                documents=[c["text"] for c in batch],
                embeddings=embeddings,
                metadatas=[
                    {
                        "doc_id": c["doc_id"],
                        "section": c["section"],
                        "source_file": c["source_file"],
                    }
                    for c in batch
                ],
            )
        return len(all_chunks)

    def ensure_indexed(self) -> int:
        if self.chunk_count > 0:
            return self.chunk_count
        if not self._openai:
            return 0
        policies_dir = settings.resolve_path(settings.policies_dir)
        if not policies_dir.exists():
            return 0
        try:
            return self.ingest_directory(policies_dir)
        except Exception:
            return 0

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        k = top_k or settings.top_k_policies
        if self.chunk_count == 0:
            self.ensure_indexed()
        if self.chunk_count == 0 or not self._openai:
            return []

        try:
            q_emb = self._embed([query])[0]
        except Exception:
            return []
        results = self._collection.query(
            query_embeddings=[q_emb],
            n_results=min(k, self.chunk_count),
            include=["documents", "metadatas", "distances"],
        )
        out: list[dict] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            # cosine distance: lower is better; convert to similarity
            similarity = 1.0 - float(dist)
            out.append(
                {
                    "text": doc,
                    "doc_id": meta.get("doc_id", ""),
                    "section": meta.get("section", ""),
                    "source_file": meta.get("source_file", ""),
                    "similarity": similarity,
                }
            )
        return out


policy_index = PolicyIndex()
