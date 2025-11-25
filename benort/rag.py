"""RAG helpers for indexing workspace Markdown and querying via embeddings."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Tuple

import numpy as np
import requests

from .config import DEFAULT_EMBEDDING_MODEL


class RagUnavailableError(RuntimeError):
    """Raised when RAG cannot be used (missing deps or data)."""


@dataclass(slots=True)
class RagChunk:
    page_id: str
    page_idx: int
    chunk_idx: int
    text: str
    label: str


def _normalize_label(payload: dict[str, Any], order: int) -> str:
    for key in ("title", "name", "label", "pageTitle"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"Page {order + 1}"


def _chunk_markdown(text: str, chunk_size: int = 900, overlap: int = 180) -> list[str]:
    """Split Markdown into overlapped character windows."""

    cleaned = (text or "").strip()
    if not cleaned:
        return []
    normalized = re.sub(r"\n{3,}", "\n\n", cleaned)
    if len(normalized) <= chunk_size:
        return [normalized]
    step = max(1, chunk_size - max(0, overlap))
    chunks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(length, start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start += step
    return chunks


def collect_markdown_chunks(package, *, chunk_size: int = 900, overlap: int = 180) -> tuple[list[RagChunk], str]:
    """Extract Markdown notes from a workspace into chunks and return a source hash."""

    try:
        pages = package.list_pages()
    except Exception as exc:  # pragma: no cover - wrapper for caller
        raise RagUnavailableError(str(exc))

    collected: list[RagChunk] = []
    hasher = hashlib.sha256()
    for order, record in enumerate(pages):
        payload = record.payload if isinstance(record, object) else {}
        markdown = ""
        if isinstance(payload, dict):
            markdown = str(payload.get("notes") or "").strip()
        if not markdown:
            continue
        label = _normalize_label(payload if isinstance(payload, dict) else {}, order)
        chunks = _chunk_markdown(markdown, chunk_size=chunk_size, overlap=overlap)
        for idx, chunk_text in enumerate(chunks):
            text = chunk_text.strip()
            if not text:
                continue
            hasher.update(text.encode("utf-8", errors="ignore"))
            hasher.update(record.page_id.encode("utf-8", errors="ignore"))
            collected.append(RagChunk(record.page_id, order, idx, text, label))
    return collected, hasher.hexdigest()


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def _embedding_vectors(
    endpoint: str,
    headers: dict[str, str],
    model: str,
    texts: list[str],
    *,
    timeout: int,
) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype="float32")
    payload = {"model": model, "input": texts}
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RagUnavailableError(f"Embedding API 错误: {resp.text}")
    try:
        data = resp.json().get("data", [])
    except Exception as exc:
        raise RagUnavailableError(f"解析 Embedding 响应失败: {exc}")
    if not isinstance(data, list) or not data:
        raise RagUnavailableError("Embedding 响应为空")
    sorted_items = sorted(data, key=lambda item: item.get("index", 0))
    vectors: list[list[float]] = []
    for item in sorted_items:
        emb = item.get("embedding")
        if isinstance(emb, list):
            vectors.append(emb)
    if len(vectors) != len(texts):
        raise RagUnavailableError("Embedding 返回数量与输入不一致")
    return np.array(vectors, dtype="float32")


def ensure_markdown_index(
    workspace_id: str,
    package,
    provider_config: dict[str, Any],
    headers: dict[str, str],
    cache_dir: Path,
    *,
    embedding_model: str | None = None,
    chunk_size: int = 900,
    overlap: int = 180,
    force_rebuild: bool = False,
) -> tuple[Any, dict, bool]:
    """Ensure there is a FAISS index for workspace Markdown."""

    try:
        import faiss  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise RagUnavailableError(f"缺少 faiss 依赖：{exc}")

    chunks, source_hash = collect_markdown_chunks(package, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        raise RagUnavailableError("当前工作区没有可索引的 Markdown 笔记")

    emb_model = (embedding_model or "").strip() or DEFAULT_EMBEDDING_MODEL
    provider_id = str(provider_config.get("id") or provider_config.get("label") or "llm").strip()
    meta_path = Path(cache_dir) / "md_manifest.json"
    index_path = Path(cache_dir) / "md_index.faiss"
    manifest = _load_manifest(meta_path)
    if (
        not force_rebuild
        and manifest
        and manifest.get("sourceHash") == source_hash
        and manifest.get("embeddingModel") == emb_model
        and manifest.get("provider") == provider_id
        and index_path.exists()
    ):
        index = faiss.read_index(str(index_path))
        return index, manifest, False

    texts = [chunk.text for chunk in chunks]
    timeout = int(provider_config.get("timeout") or 60)
    endpoint = str(provider_config.get("embedding_endpoint") or "").strip()
    if not endpoint:
        raise RagUnavailableError("未配置 embedding 接口地址")
    vectors = _embedding_vectors(endpoint, headers, emb_model, texts, timeout=timeout)
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
        raise RagUnavailableError("Embedding 维度异常")
    dimension = vectors.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(vectors)

    manifest = {
        "version": 1,
        "builtAt": time.time(),
        "workspaceId": workspace_id,
        "provider": provider_id,
        "embeddingModel": emb_model,
        "sourceHash": source_hash,
        "chunkCount": len(chunks),
        "dimension": dimension,
        "chunks": [
            {
                "pageId": chunk.page_id,
                "pageIdx": chunk.page_idx,
                "chunkIdx": chunk.chunk_idx,
                "text": chunk.text,
                "label": chunk.label,
            }
            for chunk in chunks
        ],
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))
    _write_manifest(meta_path, manifest)
    return index, manifest, True


def search_markdown(
    query: str,
    index: Any,
    manifest: dict,
    provider_config: dict[str, Any],
    headers: dict[str, str],
    *,
    embedding_model: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Search Markdown index with a query string."""

    if not query or not manifest or not hasattr(index, "search"):
        return []
    emb_model = (embedding_model or "").strip() or manifest.get("embeddingModel") or DEFAULT_EMBEDDING_MODEL
    vectors = _embedding_vectors(
        str(provider_config.get("embedding_endpoint") or ""),
        headers,
        emb_model,
        [query],
        timeout=int(provider_config.get("timeout") or 60),
    )
    if vectors.size == 0:
        return []
    k = max(1, min(int(top_k or 5), 12))
    distances, indices = index.search(vectors, k)
    results: list[dict] = []
    chunk_records = manifest.get("chunks") or []
    if len(chunk_records) == 0:
        return []
    for rank, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(chunk_records):
            continue
        chunk = chunk_records[int(idx)]
        results.append(
            {
                "rank": rank + 1,
                "score": float(distances[0][rank]),
                "pageId": chunk.get("pageId"),
                "pageIdx": chunk.get("pageIdx"),
                "chunkIdx": chunk.get("chunkIdx"),
                "label": chunk.get("label") or f"Page {int(chunk.get('pageIdx') or 0) + 1}",
                "text": chunk.get("text") or "",
            }
        )
    return results
