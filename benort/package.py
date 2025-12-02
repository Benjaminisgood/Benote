"""SQLite-backed `.benort` workspace container helpers."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from .template_store import get_default_markdown_template, get_default_template


def _resolve_learning_record_ttl_seconds() -> int:
    """Resolve how long non-favorited learning records should be kept."""

    env_seconds = os.environ.get("BENORT_LEARNING_RECORD_TTL_SECONDS")
    if env_seconds:
        try:
            seconds = int(env_seconds)
            if seconds > 0:
                return seconds
        except ValueError:
            pass
    env_days = os.environ.get("BENORT_LEARNING_RECORD_TTL_DAYS")
    if env_days:
        try:
            days_value = int(env_days)
            if days_value > 0:
                return days_value * 86400
        except ValueError:
            pass
    # Default to 30 days to balance retention and storage.
    return 30 * 24 * 3600


LEARNING_RECORD_TTL_SECONDS = _resolve_learning_record_ttl_seconds()


class WorkspaceVersionConflict(Exception):
    """Raised when a workspace save would overwrite a newer version."""

    pass

DEFAULT_PAGES: list[dict[str, Any]] = [
    {
        "pageId": f"default_{uuid.uuid4().hex[:8]}",
        "content": "\\begin{frame}[plain]\n  \\titlepage\n\\end{frame}",
        "script": "",
        "notes": "",
        "bib": [],
    },
    {
        "pageId": f"default_{uuid.uuid4().hex[:8]}",
        "content": "\\begin{frame}\n  \\frametitle{目录}\n  \\tableofcontents\n\\end{frame}",
        "script": "",
        "notes": "",
        "bib": [],
    },
]

PROJECT_SECURITY_META_KEY = "projectSecurity"
LEGACY_SECURITY_META_KEYS: tuple[str, ...] = ("workspaceSecurity",)


SCHEMA_STATEMENTS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL;",
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);",
    "CREATE TABLE IF NOT EXISTS attachments ("
    "  id TEXT PRIMARY KEY,"
    "  name TEXT NOT NULL,"
    "  page_id TEXT,"
    "  mime TEXT,"
    "  data BLOB NOT NULL,"
    "  metadata TEXT,"
    "  updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))"
    ");",
    "CREATE TABLE IF NOT EXISTS resource_files ("
    "  id TEXT PRIMARY KEY,"
    "  name TEXT NOT NULL,"
    "  page_id TEXT,"
    "  mime TEXT,"
    "  data BLOB NOT NULL,"
    "  metadata TEXT,"
    "  updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))"
    ");",
    "CREATE TABLE IF NOT EXISTS page_latex ("
    "  page_id TEXT PRIMARY KEY,"
    "  idx INTEGER NOT NULL DEFAULT 0,"
    "  meta TEXT NOT NULL DEFAULT '{}',"
    "  content TEXT NOT NULL DEFAULT '',"
    "  updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))"
    ");",
    "CREATE TABLE IF NOT EXISTS page_markdown ("
    "  page_id TEXT PRIMARY KEY,"
    "  content TEXT NOT NULL DEFAULT '',"
    "  updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))"
    ");",
    "CREATE TABLE IF NOT EXISTS page_notes ("
    "  page_id TEXT PRIMARY KEY,"
    "  content TEXT NOT NULL DEFAULT '',"
    "  updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))"
    ");",
    "CREATE TABLE IF NOT EXISTS page_resources ("
    "  page_id TEXT NOT NULL,"
    "  position INTEGER NOT NULL,"
    "  name TEXT NOT NULL,"
    "  PRIMARY KEY(page_id, position)"
    ");",
    "CREATE TABLE IF NOT EXISTS page_references ("
    "  page_id TEXT NOT NULL,"
    "  position INTEGER NOT NULL,"
    "  data TEXT NOT NULL,"
    "  PRIMARY KEY(page_id, position)"
    ");",
    "CREATE TABLE IF NOT EXISTS project_resources ("
    "  idx INTEGER PRIMARY KEY,"
    "  name TEXT NOT NULL"
    ");",
    "CREATE TABLE IF NOT EXISTS project_references ("
    "  idx INTEGER PRIMARY KEY,"
    "  data TEXT NOT NULL"
    ");",
    "CREATE TABLE IF NOT EXISTS settings ("
    "  scope TEXT NOT NULL,"
    "  key TEXT NOT NULL,"
    "  value TEXT NOT NULL,"
    "  PRIMARY KEY(scope, key)"
    ");",
    "CREATE TABLE IF NOT EXISTS templates ("
    "  type TEXT PRIMARY KEY,"
    "  data TEXT NOT NULL"
    ");",
    "CREATE TABLE IF NOT EXISTS learning_prompts ("
    "  id TEXT PRIMARY KEY,"
    "  data TEXT NOT NULL,"
    "  removed INTEGER NOT NULL DEFAULT 0"
    ");",
    "CREATE TABLE IF NOT EXISTS learning_records ("
    "  id TEXT PRIMARY KEY,"
    "  input TEXT NOT NULL,"
    "  context TEXT,"
    "  prompt_id TEXT,"
    "  prompt_name TEXT,"
    "  method TEXT,"
    "  category TEXT,"
    "  favorite INTEGER NOT NULL DEFAULT 0,"
    "  output TEXT NOT NULL,"
    "  review_state TEXT,"
    "  saved_at REAL NOT NULL DEFAULT (strftime('%s','now'))"
    ");",
    "CREATE INDEX IF NOT EXISTS idx_page_latex_ord ON page_latex(idx);",
    "CREATE INDEX IF NOT EXISTS idx_page_resources_page ON page_resources(page_id);",
    "CREATE INDEX IF NOT EXISTS idx_page_references_page ON page_references(page_id);",
    "CREATE INDEX IF NOT EXISTS idx_attachments_name ON attachments(name);",
    "CREATE INDEX IF NOT EXISTS idx_resource_files_name ON resource_files(name);",
    "CREATE INDEX IF NOT EXISTS idx_learning_records_input ON learning_records(input);",
    "CREATE INDEX IF NOT EXISTS idx_learning_records_favorite ON learning_records(favorite, saved_at);",
    "CREATE INDEX IF NOT EXISTS idx_learning_records_category ON learning_records(category);",
)


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _serialize(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _deserialize(payload: str | bytes | memoryview | None) -> Any:
    if payload is None:
        return None
    if isinstance(payload, (bytes, memoryview)):
        payload = bytes(payload).decode("utf-8")
    return json.loads(payload)


def _dedupe_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in items:
        if raw in seen:
            continue
        seen.add(raw)
        ordered.append(raw)
    return ordered


def _normalize_resource_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        iterable: list[Any] = []
    else:
        try:
            iterable = list(values)
        except TypeError:
            iterable = []
    cleaned: list[str] = []
    for raw in iterable:
        if not isinstance(raw, str):
            continue
        name = raw.strip()
        if name:
            cleaned.append(name)
    return _dedupe_preserve(cleaned)


def _coerce_bib_entries(entries: Any) -> list[dict[str, Any]]:
    if entries is None:
        return []
    if isinstance(entries, (str, bytes)):
        iterable: list[Any] = [entries]
    else:
        try:
            iterable = list(entries)
        except TypeError:
            iterable = []
    normalized: list[dict[str, Any]] = []
    for entry in iterable:
        if isinstance(entry, dict):
            normalized.append(dict(entry))
        elif isinstance(entry, str):
            normalized.append({"entry": entry})
    return normalized


_PAGE_CORE_FIELDS: set[str] = {"pageId", "content", "script", "notes", "resources", "bib"}


@dataclass(slots=True)
class PageRecord:
    page_id: str
    order: int
    payload: dict[str, Any]


@dataclass(slots=True)
class AssetRecord:
    asset_id: str
    name: str
    scope: str
    mime: str | None
    data: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    page_id: str | None = None

    @property
    def size(self) -> int:
        if self.data is not None:
            return len(self.data)
        try:
            return int(self.metadata.get("size") or 0)
        except (TypeError, ValueError):
            return 0


class BenortPackage:
    """High-level helper for reading/writing `.benort` SQLite databases."""

    def __init__(self, path: str):
        self.path = Path(path).expanduser().resolve()
        os.makedirs(self.path.parent, exist_ok=True)
        self.conn = _connect(str(self.path))
        self._lock = threading.RLock()
        self._ensure_schema()

    def _row_to_asset(self, row: sqlite3.Row, scope: str) -> AssetRecord:
        metadata = _deserialize(row["metadata"]) or {}
        data_value = row["data"] if "data" in row.keys() else None
        return AssetRecord(
            asset_id=row["id"],
            name=row["name"],
            scope=scope,
            mime=row["mime"],
            data=data_value,
            metadata=metadata if isinstance(metadata, dict) else {},
            page_id=row["page_id"],
        )

    def close(self) -> None:
        with self._lock:
            try:
                self.conn.close()
            except Exception:
                pass

    def _ensure_schema(self) -> None:
        with self._lock:
            cur = self.conn.cursor()
            for stmt in SCHEMA_STATEMENTS:
                cur.execute(stmt)
            self.conn.commit()
        self._migrate_templates_if_needed()
        self._ensure_learning_record_columns()
        self._migrate_learning_meta()
        self._ensure_page_latex_columns()
        self._migrate_page_tables()
        self._migrate_project_resources()
        self._migrate_project_references()
        self._migrate_legacy_assets()
        self._migrate_meta_entries()

    def _set_meta(self, key: str, value: Any) -> None:
        payload = _serialize(value)
        with self._lock:
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, payload),
            )

    def _delete_meta(self, key: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM meta WHERE key = ?", (key,))

    def _get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        return _deserialize(row["value"])

    def set_meta_value(self, key: str, value: Any) -> None:
        """Public helper to store arbitrary metadata."""

        self._set_meta(key, value)

    def get_meta_value(self, key: str, default: Any = None) -> Any:
        """Public helper to read arbitrary metadata."""

        return self._get_meta(key, default)

    # Workspace security ----------------------------------------------------
    def _get_workspace_security_meta(self) -> dict[str, Any]:
        payload = self._get_meta(PROJECT_SECURITY_META_KEY)
        if isinstance(payload, dict):
            return payload
        for legacy_key in LEGACY_SECURITY_META_KEYS:
            legacy_payload = self._get_meta(legacy_key)
            if isinstance(legacy_payload, dict):
                self._set_meta(PROJECT_SECURITY_META_KEY, legacy_payload)
                self._delete_meta(legacy_key)
                return legacy_payload
        return {}

    def _set_workspace_security_meta(self, payload: dict[str, Any]) -> None:
        self._set_meta(PROJECT_SECURITY_META_KEY, payload or {})
        for legacy_key in LEGACY_SECURITY_META_KEYS:
            self._delete_meta(legacy_key)

    def get_workspace_password_hash(self) -> Optional[str]:
        payload = self._get_workspace_security_meta()
        candidate = payload.get("passwordHash")
        if isinstance(candidate, str) and candidate.strip():
            return candidate
        return None

    def has_workspace_password(self) -> bool:
        return self.get_workspace_password_hash() is not None

    def save_workspace_password(self, new_password: str) -> None:
        normalized = (new_password or "").strip()
        if not normalized:
            raise ValueError("密码不能为空")
        password_hash = generate_password_hash(normalized)
        payload = self._get_workspace_security_meta()
        payload["passwordHash"] = password_hash
        payload["updatedAt"] = time.time()
        self._set_workspace_security_meta(payload)

    def clear_workspace_password(self) -> None:
        payload = self._get_workspace_security_meta()
        if "passwordHash" in payload:
            payload.pop("passwordHash", None)
        payload["updatedAt"] = time.time()
        self._set_workspace_security_meta(payload)

    def verify_workspace_password(self, password: str) -> bool:
        password_hash = self.get_workspace_password_hash()
        if not password_hash:
            return True
        candidate = (password or "").strip()
        if not candidate:
            return False
        try:
            return check_password_hash(password_hash, candidate)
        except Exception:
            return False

    def get_template_block(self, template_type: str, default: dict | None = None) -> dict:
        with self._lock:
            row = self.conn.execute("SELECT data FROM templates WHERE type = ?", (template_type,)).fetchone()
        if row:
            data = _deserialize(row["data"]) or {}
            if isinstance(data, dict):
                return data
        fallback = default
        if not isinstance(fallback, dict):
            if template_type == "latex":
                fallback = get_default_template()
            elif template_type == "markdown":
                fallback = get_default_markdown_template()
            else:
                fallback = {}
        self.save_template(template_type, fallback)
        return dict(fallback)

    def save_template(self, template_type: str, data: dict) -> None:
        payload = _serialize(data or {})
        with self._lock:
            self.conn.execute(
                "INSERT INTO templates (type, data) VALUES (?, ?) "
                "ON CONFLICT(type) DO UPDATE SET data = excluded.data",
                (template_type, payload),
            )

    def list_learning_prompts(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT id, data, removed FROM learning_prompts").fetchall()
        prompts: list[dict] = []
        for row in rows:
            data = _deserialize(row["data"]) or {}
            if not isinstance(data, dict):
                data = {}
            data["id"] = row["id"]
            data["removed"] = bool(row["removed"])
            prompts.append(data)
        return prompts

    def save_learning_prompt_entry(self, prompt: dict, removed: bool = False) -> dict:
        prompt_id = str(prompt.get("id") or "").strip()
        if not prompt_id:
            prompt_id = f"custom_{uuid.uuid4().hex[:12]}"
            prompt["id"] = prompt_id
        payload = _serialize(prompt)
        with self._lock:
            self.conn.execute(
                "INSERT INTO learning_prompts (id, data, removed) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data, removed = excluded.removed",
                (prompt_id, payload, 1 if removed else 0),
            )
        return prompt

    def mark_learning_prompt_removed(self, prompt_id: str, removed: bool) -> None:
        prompt_id = prompt_id.strip()
        if not prompt_id:
            return
        with self._lock:
            row = self.conn.execute("SELECT id FROM learning_prompts WHERE id = ?", (prompt_id,)).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE learning_prompts SET removed = ? WHERE id = ?",
                    (1 if removed else 0, prompt_id),
                )
            else:
                placeholder = _serialize({"id": prompt_id, "source": "override"})
                self.conn.execute(
                    "INSERT INTO learning_prompts (id, data, removed) VALUES (?, ?, ?)",
                    (prompt_id, placeholder, 1 if removed else 0),
                )

    def delete_learning_prompt_entry(self, prompt_id: str) -> None:
        prompt_id = prompt_id.strip()
        if not prompt_id:
            return
        with self._lock:
            self.conn.execute("DELETE FROM learning_prompts WHERE id = ?", (prompt_id,))

    def list_learning_records(self) -> list[dict]:
        self._prune_learning_records()
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, input, context, prompt_id, prompt_name, method, category, favorite, output, review_state, saved_at "
                "FROM learning_records ORDER BY saved_at DESC"
            ).fetchall()
        records: list[dict] = []
        for row in rows:
            records.append(
                {
                    "id": row["id"],
                    "input": row["input"],
                    "context": row["context"],
                    "promptId": row["prompt_id"],
                    "promptName": row["prompt_name"],
                    "method": row["method"],
                    "category": row["category"],
                    "favorite": bool(row["favorite"]),
                    "output": row["output"],
                    "review": _deserialize(row["review_state"]) if row["review_state"] else None,
                    "savedAt": row["saved_at"],
                }
            )
        return records

    def get_learning_record_entry(self, record_id: str) -> Optional[dict]:
        record_id = (record_id or "").strip()
        if not record_id:
            return None
        self._prune_learning_records()
        with self._lock:
            row = self.conn.execute(
                "SELECT id, input, context, prompt_id, prompt_name, method, category, favorite, output, review_state, saved_at "
                "FROM learning_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "input": row["input"],
            "context": row["context"],
            "promptId": row["prompt_id"],
            "promptName": row["prompt_name"],
            "method": row["method"],
            "category": row["category"],
            "favorite": bool(row["favorite"]),
            "output": row["output"],
            "review": _deserialize(row["review_state"]) if row["review_state"] else None,
            "savedAt": row["saved_at"],
        }

    def save_learning_record_entry(self, record: dict) -> dict:
        record_id = str(record.get("id") or "").strip() or uuid.uuid4().hex
        saved_at = record.get("savedAt")
        try:
            saved_value = float(saved_at)
        except (TypeError, ValueError):
            saved_value = time.time()
        method_source = record.get("method")
        if method_source is None:
            method_source = record.get("learningMethod")
        method_value = ""
        if method_source is not None:
            method_value = str(method_source).strip()
        category_source = record.get("category")
        if category_source is None:
            category_source = record.get("group") or record.get("classification")
        category_value = ""
        if category_source is not None:
            category_value = str(category_source).strip()
        favorite_raw = record.get("favorite")
        if isinstance(favorite_raw, str):
            favorite_flag = favorite_raw.strip().lower() in {"1", "true", "yes", "on"}
        else:
            favorite_flag = bool(favorite_raw)
        review_state_raw = record.get("review") or record.get("review_state")
        review_state_value: str | None = None
        if isinstance(review_state_raw, (dict, list)):
            review_state_value = _serialize(review_state_raw)
        payload = {
            "id": record_id,
            "input": record.get("input", ""),
            "context": record.get("context"),
            "prompt_id": record.get("promptId") or record.get("prompt_id"),
            "prompt_name": record.get("promptName") or record.get("prompt_name"),
            "method": method_value or None,
            "category": category_value or None,
            "favorite": 1 if favorite_flag else 0,
            "output": record.get("output", ""),
            "review_state": review_state_value,
            "saved_at": saved_value,
        }
        with self._lock:
            self.conn.execute(
                "INSERT INTO learning_records (id, input, context, prompt_id, prompt_name, method, category, favorite, output, review_state, saved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET input = excluded.input, context = excluded.context, "
                "prompt_id = excluded.prompt_id, prompt_name = excluded.prompt_name, "
                "method = excluded.method, category = excluded.category, favorite = excluded.favorite, "
                "output = excluded.output, review_state = excluded.review_state, saved_at = excluded.saved_at",
                (
                    payload["id"],
                    payload["input"],
                    payload["context"],
                    payload["prompt_id"],
                    payload["prompt_name"],
                    payload["method"],
                    payload["category"],
                    payload["favorite"],
                    payload["output"],
                    payload["review_state"],
                    payload["saved_at"],
                ),
            )
        result = dict(record)
        result["id"] = payload["id"]
        result["savedAt"] = payload["saved_at"]
        result["favorite"] = bool(payload["favorite"])
        if payload["method"]:
            result["method"] = payload["method"]
        if payload["category"]:
            result["category"] = payload["category"]
        if payload["review_state"]:
            result["review"] = _deserialize(payload["review_state"])
        self._prune_learning_records()
        return result

    def delete_learning_records_for_input(self, input_value: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM learning_records WHERE input = ?", (input_value,))

    def _prune_learning_records(self, ttl_seconds: Optional[int] = None) -> int:
        """Remove expired non-favorited learning records."""

        ttl = ttl_seconds or LEARNING_RECORD_TTL_SECONDS
        if ttl <= 0:
            return 0
        cutoff = time.time() - ttl
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM learning_records WHERE favorite = 0 AND saved_at < ?",
                (cutoff,),
            )
            deleted = cur.rowcount or 0
        return deleted

    def update_learning_record_entry(self, record_id: str, updates: dict) -> Optional[dict]:
        record_id = (record_id or "").strip()
        if not record_id or not isinstance(updates, dict):
            return None
        columns: dict[str, Any] = {}
        if "method" in updates:
            method_val = updates.get("method")
            if method_val is None:
                columns["method"] = None
            else:
                columns["method"] = str(method_val).strip() or None
        if "category" in updates:
            category_val = updates.get("category")
            if category_val is None:
                columns["category"] = None
            else:
                columns["category"] = str(category_val).strip() or None
        if "favorite" in updates:
            raw = updates.get("favorite")
            if isinstance(raw, str):
                favorite_flag = raw.strip().lower() in {"1", "true", "yes", "on"}
            else:
                favorite_flag = bool(raw)
            columns["favorite"] = 1 if favorite_flag else 0
        if "input" in updates:
            input_val = updates.get("input")
            if input_val is not None:
                columns["input"] = str(input_val)
        if "context" in updates:
            context_val = updates.get("context")
            if context_val is None:
                columns["context"] = None
            else:
                columns["context"] = str(context_val)
        if "output" in updates:
            output_val = updates.get("output")
            if output_val is not None:
                columns["output"] = str(output_val)
        if "review" in updates:
            review_state = updates.get("review")
            if isinstance(review_state, (dict, list)):
                columns["review_state"] = _serialize(review_state)
            elif review_state is None:
                columns["review_state"] = None
        if not columns:
            return None
        set_clause = ", ".join(f"{col} = ?" for col in columns.keys())
        params = list(columns.values())
        params.append(record_id)
        with self._lock:
            cur = self.conn.execute(
                f"UPDATE learning_records SET {set_clause} WHERE id = ?",
                params,
            )
            if cur.rowcount == 0:
                return None
            row = self.conn.execute(
                "SELECT id, input, context, prompt_id, prompt_name, method, category, favorite, output, review_state, saved_at "
                "FROM learning_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "input": row["input"],
            "context": row["context"],
            "promptId": row["prompt_id"],
            "promptName": row["prompt_name"],
            "method": row["method"],
            "category": row["category"],
            "favorite": bool(row["favorite"]),
            "output": row["output"],
            "review": _deserialize(row["review_state"]) if row["review_state"] else None,
            "savedAt": row["saved_at"],
        }

    def delete_learning_record_entry(self, record_id: str) -> bool:
        record_id = (record_id or "").strip()
        if not record_id:
            return False
        with self._lock:
            cur = self.conn.execute("DELETE FROM learning_records WHERE id = ?", (record_id,))
            return cur.rowcount > 0

    def _migrate_templates_if_needed(self) -> None:
        with self._lock:
            row = self.conn.execute("SELECT COUNT(*) AS total FROM templates").fetchone()
        if row and row["total"]:
            return
        self.save_template("latex", get_default_template())
        self.save_template("markdown", get_default_markdown_template())

    def _migrate_learning_meta(self) -> None:
        legacy = self._get_meta("learningData")
        if not isinstance(legacy, dict):
            return
        prompts_meta = legacy.get("prompts") or {}
        for entry in prompts_meta.get("custom", []) or []:
            if isinstance(entry, dict):
                payload = dict(entry)
                payload.setdefault("source", "custom")
                self.save_learning_prompt_entry(payload, removed=False)
        for entry in prompts_meta.get("overrides", []) or []:
            if isinstance(entry, dict):
                payload = dict(entry)
                payload.setdefault("source", "override")
                self.save_learning_prompt_entry(payload, removed=False)
        for prompt_id in prompts_meta.get("removed", []) or []:
            if isinstance(prompt_id, str) and prompt_id.strip():
                self.save_learning_prompt_entry({"id": prompt_id.strip(), "source": "override"}, removed=True)
        for record in legacy.get("records") or []:
            if not isinstance(record, dict):
                continue
            base = str(record.get("input") or "").strip()
            if not base:
                continue
            context = str(record.get("context") or "").strip() or None
            for entry in record.get("entries") or []:
                if not isinstance(entry, dict):
                    continue
                output = str(entry.get("output") or "").strip()
                if not output:
                    continue
                prompt_id = str(entry.get("promptId") or "").strip() or None
                prompt_name = str(entry.get("promptName") or "").strip() or None
                saved_at = entry.get("savedAt")
                try:
                    saved_value = float(saved_at) if saved_at is not None else time.time()
                except (TypeError, ValueError):
                    saved_value = time.time()
                self.save_learning_record_entry(
                    {
                        "input": base,
                        "context": context,
                        "prompt_id": prompt_id,
                        "prompt_name": prompt_name,
                        "output": output,
                        "savedAt": saved_value,
                    }
                )
        self._set_meta("learningData", {})

    def _ensure_learning_record_columns(self) -> None:
        """Ensure optional columns for learning records exist (post v2 schema)."""

        with self._lock:
            rows = self.conn.execute("PRAGMA table_info(learning_records)").fetchall()
            columns = {row["name"] for row in rows}
            if "method" not in columns:
                self.conn.execute("ALTER TABLE learning_records ADD COLUMN method TEXT")
            if "category" not in columns:
                self.conn.execute("ALTER TABLE learning_records ADD COLUMN category TEXT")
            if "favorite" not in columns:
                self.conn.execute("ALTER TABLE learning_records ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0")
            if "review_state" not in columns:
                self.conn.execute("ALTER TABLE learning_records ADD COLUMN review_state TEXT")
            self.conn.commit()

    def _table_exists(self, name: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                (name,),
            ).fetchone()
        return bool(row)

    def _table_columns(self, name: str) -> set[str]:
        with self._lock:
            rows = self.conn.execute(f"PRAGMA table_info({name})").fetchall()
        return {row["name"] for row in rows}

    def _ensure_page_latex_columns(self) -> None:
        if not self._table_exists("page_latex"):
            return
        columns = self._table_columns("page_latex")
        statements: list[str] = []
        if "idx" not in columns:
            statements.append("ALTER TABLE page_latex ADD COLUMN idx INTEGER NOT NULL DEFAULT 0")
        if "meta" not in columns:
            statements.append("ALTER TABLE page_latex ADD COLUMN meta TEXT NOT NULL DEFAULT '{}'")
        for stmt in statements:
            with self._lock:
                self.conn.execute(stmt)
        with self._lock:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_page_latex_ord ON page_latex(idx)")

    def _asset_table_for_scope(self, scope: str) -> str:
        normalized = (scope or "").strip().lower()
        if normalized == "attachment":
            return "attachments"
        if normalized == "resource":
            return "resource_files"
        raise ValueError(f"未知的资源类型: {scope}")

    def _fetch_page_text_map(self, table: str) -> dict[str, str]:
        with self._lock:
            rows = self.conn.execute(f"SELECT page_id, content FROM {table}").fetchall()
        data: dict[str, str] = {}
        for row in rows:
            content = row["content"]
            data[row["page_id"]] = content if isinstance(content, str) else ""
        return data

    def _upsert_page_latex(self, page_id: str, idx: int, body: str, meta: dict[str, Any]) -> None:
        payload = _serialize(meta or {})
        with self._lock:
            self.conn.execute(
                "INSERT INTO page_latex (page_id, idx, meta, content, updated_at) "
                "VALUES (?, ?, ?, ?, strftime('%s','now')) "
                "ON CONFLICT(page_id) DO UPDATE SET "
                "idx = excluded.idx, meta = excluded.meta, content = excluded.content, "
                "updated_at = excluded.updated_at",
                (page_id, idx, payload, body),
            )

    def _upsert_page_text(self, table: str, page_id: str, body: str) -> None:
        with self._lock:
            self.conn.execute(
                f"INSERT INTO {table} (page_id, content, updated_at) VALUES (?, ?, strftime('%s','now')) "
                f"ON CONFLICT(page_id) DO UPDATE SET content = excluded.content, "
                f"updated_at = excluded.updated_at",
                (page_id, body),
            )

    def _rewrite_page_resources(self, page_id: str, resources: list[str]) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM page_resources WHERE page_id = ?", (page_id,))
            if not resources:
                return
            self.conn.executemany(
                "INSERT INTO page_resources (page_id, position, name) VALUES (?, ?, ?)",
                ((page_id, idx, name) for idx, name in enumerate(resources)),
            )

    def _rewrite_page_references(self, page_id: str, entries: list[dict[str, Any]]) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM page_references WHERE page_id = ?", (page_id,))
            if not entries:
                return
            self.conn.executemany(
                "INSERT INTO page_references (page_id, position, data) VALUES (?, ?, ?)",
                ((page_id, idx, _serialize(entry)) for idx, entry in enumerate(entries)),
            )

    def _page_resource_map(self) -> dict[str, list[str]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT page_id, name FROM page_resources ORDER BY page_id, position"
            ).fetchall()
        mapping: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            value = row["name"]
            mapping[row["page_id"]].append(value if isinstance(value, str) else "")
        return mapping

    def _page_reference_map(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT page_id, data FROM page_references ORDER BY page_id, position"
            ).fetchall()
        mapping: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            payload = _deserialize(row["data"])
            if isinstance(payload, dict):
                mapping[row["page_id"]].append(payload)
            elif isinstance(payload, str):
                mapping[row["page_id"]].append({"entry": payload})
        return mapping

    def _normalize_page_payload(self, page: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(page, str):
            payload: dict[str, Any] = {"content": page}
        elif isinstance(page, dict):
            payload = dict(page)
        else:
            payload = {}
        page_id = str(payload.get("pageId") or payload.get("id") or "").strip()
        if not page_id:
            page_id = f"page_{uuid.uuid4().hex[:8]}"
        normalized = {
            "pageId": page_id,
            "content": str(payload.get("content") or ""),
            "script": str(payload.get("script") or ""),
            "notes": str(payload.get("notes") or ""),
            "resources": _normalize_resource_list(payload.get("resources")),
            "bib": _coerce_bib_entries(payload.get("bib")),
        }
        for key, value in payload.items():
            if key in normalized:
                continue
            normalized[key] = value
        return normalized

    def _extract_page_meta(self, payload: dict[str, Any]) -> dict[str, Any]:
        extras: dict[str, Any] = {}
        for key, value in payload.items():
            if key in _PAGE_CORE_FIELDS:
                continue
            extras[key] = value
        return extras

    def _list_project_resources(self) -> list[str]:
        with self._lock:
            rows = self.conn.execute("SELECT idx, name FROM project_resources ORDER BY idx ASC").fetchall()
        ordered = sorted(rows, key=lambda row: row["idx"])
        return [row["name"] for row in ordered if isinstance(row["name"], str)]

    def _replace_project_resources(self, resources: Iterable[str]) -> None:
        cleaned = _normalize_resource_list(resources)
        with self._lock:
            self.conn.execute("DELETE FROM project_resources")
            if not cleaned:
                return
            self.conn.executemany(
                "INSERT INTO project_resources (idx, name) VALUES (?, ?)",
                ((idx, name) for idx, name in enumerate(cleaned)),
            )

    def _list_project_references(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT idx, data FROM project_references ORDER BY idx ASC"
            ).fetchall()
        ordered = sorted(rows, key=lambda row: row["idx"])
        result: list[dict[str, Any]] = []
        for row in ordered:
            payload = _deserialize(row["data"])
            if isinstance(payload, dict):
                result.append(payload)
            elif isinstance(payload, str):
                result.append({"entry": payload})
        return result

    def _replace_project_references(self, entries: Iterable[Any]) -> None:
        normalized = _coerce_bib_entries(entries)
        with self._lock:
            self.conn.execute("DELETE FROM project_references")
            if not normalized:
                return
            self.conn.executemany(
                "INSERT INTO project_references (idx, data) VALUES (?, ?)",
                ((idx, _serialize(entry)) for idx, entry in enumerate(normalized)),
            )

    def _migrate_project_resources(self) -> None:
        legacy = self._get_meta("resources")
        if isinstance(legacy, list) and legacy:
            self._replace_project_resources(legacy)
        with self._lock:
            self.conn.execute("DELETE FROM meta WHERE key = 'resources'")

    def _migrate_project_references(self) -> None:
        legacy = self._get_meta("project")
        bib_entries: list[Any] | None = None
        if isinstance(legacy, dict):
            maybe = legacy.get("bib")
            if isinstance(maybe, list):
                bib_entries = maybe
                legacy = dict(legacy)
                legacy.pop("bib", None)
                self._set_meta("project", legacy)
        if bib_entries:
            self._replace_project_references(bib_entries)

    def _migrate_page_tables(self) -> None:
        if not self._table_exists("pages"):
            return
        with self._lock:
            rows = self.conn.execute("SELECT id, idx, data FROM pages ORDER BY idx ASC").fetchall()
        for row in rows:
            payload = _deserialize(row["data"])
            normalized = self._normalize_page_payload(payload if isinstance(payload, dict) else {})
            page_id = row["id"] or normalized["pageId"]
            normalized["pageId"] = page_id
            extras = self._extract_page_meta(normalized)
            self._upsert_page_latex(page_id, row["idx"], normalized["content"], extras)
            self._upsert_page_text("page_markdown", page_id, normalized["notes"])
            self._upsert_page_text("page_notes", page_id, normalized["script"])
            self._rewrite_page_resources(page_id, normalized.get("resources", []))
            self._rewrite_page_references(page_id, normalized.get("bib", []))
        with self._lock:
            self.conn.execute("DROP TABLE pages")

    def _migrate_legacy_assets(self) -> None:
        if not self._table_exists("assets"):
            return
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, name, scope, page_id, mime, data, metadata, updated_at FROM assets"
            ).fetchall()
        if not rows:
            return
        for row in rows:
            scope = row["scope"]
            try:
                table = self._asset_table_for_scope(scope)
            except ValueError:
                continue
            with self._lock:
                self.conn.execute(
                    f"INSERT INTO {table} (id, name, page_id, mime, data, metadata, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO NOTHING",
                    (
                        row["id"],
                        row["name"],
                        row["page_id"],
                        row["mime"],
                        row["data"],
                        row["metadata"],
                        row["updated_at"],
                    ),
                )

    def _migrate_meta_entries(self) -> None:
        self._migrate_security_meta_key()
        self._purge_template_meta_keys()
        

    def _migrate_security_meta_key(self) -> None:
        current_payload = self._get_meta(PROJECT_SECURITY_META_KEY)
        if isinstance(current_payload, dict):
            return
        for legacy_key in LEGACY_SECURITY_META_KEYS:
            legacy_payload = self._get_meta(legacy_key)
            if isinstance(legacy_payload, dict):
                self._set_meta(PROJECT_SECURITY_META_KEY, legacy_payload)
                self._delete_meta(legacy_key)
                return
        default_payload = {"passwordHash": None, "updatedAt": time.time()}
        self._set_meta(PROJECT_SECURITY_META_KEY, default_payload)

    def _purge_template_meta_keys(self) -> None:
        for key in ("latexTemplate", "markdownTemplate", "template"):
            self._delete_meta(key)

    def initialize_defaults(self, project_name: str) -> None:
        timestamp = time.time()
        self._set_meta(
            "project",
            {
                "name": project_name,
                "createdAt": timestamp,
                "updatedAt": timestamp,
                "version": 1,
            },
        )
        self._set_workspace_security_meta({"passwordHash": None, "updatedAt": timestamp})
        self._replace_project_resources([])
        self._replace_project_references([])
        self.save_pages(DEFAULT_PAGES)
        self.save_template("latex", get_default_template())
        self.save_template("markdown", get_default_markdown_template())

    # Pages -----------------------------------------------------------------
    def list_pages(self) -> list[PageRecord]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT page_id, idx, meta, content FROM page_latex ORDER BY idx ASC, page_id ASC"
            ).fetchall()
            markdown_rows = self.conn.execute("SELECT page_id, content FROM page_markdown").fetchall()
            note_rows = self.conn.execute("SELECT page_id, content FROM page_notes").fetchall()
            resource_rows = self.conn.execute(
                "SELECT page_id, position, name FROM page_resources ORDER BY page_id, position"
            ).fetchall()
            reference_rows = self.conn.execute(
                "SELECT page_id, position, data FROM page_references ORDER BY page_id, position"
            ).fetchall()
        markdown_map = {row["page_id"]: row["content"] or "" for row in markdown_rows}
        notes_map = {row["page_id"]: row["content"] or "" for row in note_rows}
        resources_map: dict[str, list[str]] = defaultdict(list)
        for row in resource_rows:
            page_id = row["page_id"]
            value = row["name"]
            resources_map[page_id].append(value if isinstance(value, str) else "")
        references_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in reference_rows:
            payload = _deserialize(row["data"])
            if isinstance(payload, dict):
                references_map[row["page_id"]].append(payload)
            elif isinstance(payload, str):
                references_map[row["page_id"]].append({"entry": payload})
        records: list[PageRecord] = []
        for row in rows:
            meta = _deserialize(row["meta"])
            payload = dict(meta) if isinstance(meta, dict) else {}
            page_id = row["page_id"]
            payload["pageId"] = payload.get("pageId") or page_id
            payload["content"] = row["content"] or ""
            payload["notes"] = markdown_map.get(page_id, "")
            payload["script"] = notes_map.get(page_id, "")
            payload["resources"] = list(resources_map.get(page_id, []))
            payload["bib"] = list(references_map.get(page_id, []))
            records.append(PageRecord(page_id=page_id, order=row["idx"], payload=payload))
        return records

    def save_pages(self, pages: Iterable[dict[str, Any]]) -> None:
        normalized_pages: list[tuple[int, dict[str, Any]]] = []
        for idx, page in enumerate(pages):
            normalized_pages.append((idx, self._normalize_page_payload(page)))
        with self._lock:
            self.conn.execute("BEGIN IMMEDIATE")
            existing_ids = {row["page_id"] for row in self.conn.execute("SELECT page_id FROM page_latex")}
            desired_ids: set[str] = set()
            for idx, payload in normalized_pages:
                page_id = payload["pageId"]
                desired_ids.add(page_id)
                extras = self._extract_page_meta(payload)
                self._upsert_page_latex(page_id, idx, payload.get("content", ""), extras)
                self._upsert_page_text("page_markdown", page_id, payload.get("notes", ""))
                self._upsert_page_text("page_notes", page_id, payload.get("script", ""))
                self._rewrite_page_resources(page_id, payload.get("resources", []))
                self._rewrite_page_references(page_id, payload.get("bib", []))
            to_delete = existing_ids - desired_ids
            if to_delete:
                doomed = [(pid,) for pid in to_delete]
                for table in ("page_latex", "page_markdown", "page_notes"):
                    self.conn.executemany(f"DELETE FROM {table} WHERE page_id = ?", doomed)
                self.conn.executemany("DELETE FROM page_resources WHERE page_id = ?", doomed)
                self.conn.executemany("DELETE FROM page_references WHERE page_id = ?", doomed)
            self.conn.commit()

    # Assets ----------------------------------------------------------------
    def list_assets(self, scope: str, include_data: bool = False) -> list[AssetRecord]:
        table = self._asset_table_for_scope(scope)
        columns = "id, name, mime, metadata, page_id"
        if include_data:
            columns += ", data"
        with self._lock:
            rows = self.conn.execute(f"SELECT {columns} FROM {table}").fetchall()
        return [self._row_to_asset(row, scope) for row in rows]

    def get_asset(self, asset_id: str, include_data: bool = True) -> AssetRecord | None:
        scopes = ("attachment", "resource")
        for scope in scopes:
            table = self._asset_table_for_scope(scope)
            columns = "id, name, mime, metadata, page_id"
            if include_data:
                columns += ", data"
            with self._lock:
                row = self.conn.execute(
                    f"SELECT {columns} FROM {table} WHERE id = ?",
                    (asset_id,),
                ).fetchone()
            if row:
                return self._row_to_asset(row, scope)
        return None

    def find_asset_by_name(
        self, scope: str, name: str, include_data: bool = False
    ) -> AssetRecord | None:
        table = self._asset_table_for_scope(scope)
        columns = "id, name, mime, metadata, page_id"
        if include_data:
            columns += ", data"
        with self._lock:
            row = self.conn.execute(
                f"SELECT {columns} FROM {table} WHERE name = ?",
                (name,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_asset(row, scope)

    def save_asset(
        self,
        *,
        name: str,
        scope: str,
        data: bytes,
        mime: str | None = None,
        page_id: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AssetRecord:
        asset_id = uuid.uuid4().hex
        payload = _serialize(metadata or {})
        table = self._asset_table_for_scope(scope)
        with self._lock:
            self.conn.execute(
                f"INSERT INTO {table} (id, name, mime, data, page_id, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (asset_id, name, mime, data, page_id, payload),
            )
        return AssetRecord(
            asset_id=asset_id,
            name=name,
            scope=scope,
            mime=mime,
            data=data,
            page_id=page_id,
            metadata=metadata or {},
        )

    def save_or_replace_asset(
        self,
        *,
        name: str,
        scope: str,
        data: bytes,
        mime: str | None = None,
        page_id: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AssetRecord:
        payload = _serialize(metadata or {})
        table = self._asset_table_for_scope(scope)
        with self._lock:
            row = self.conn.execute(
                f"SELECT id FROM {table} WHERE name = ?",
                (name,),
            ).fetchone()
            if row:
                asset_id = row["id"]
                self.conn.execute(
                    f"UPDATE {table} SET data = ?, mime = ?, page_id = ?, metadata = ?, "
                    "updated_at = strftime('%s','now') WHERE id = ?",
                    (data, mime, page_id, payload, asset_id),
                )
            else:
                asset_id = uuid.uuid4().hex
                self.conn.execute(
                    f"INSERT INTO {table} (id, name, mime, data, page_id, metadata) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (asset_id, name, mime, data, page_id, payload),
                )
        return self.get_asset(asset_id, include_data=False) or AssetRecord(
            asset_id=asset_id,
            name=name,
            scope=scope,
            mime=mime,
            data=None,
            metadata=metadata or {},
            page_id=page_id,
        )

    def rename_asset(self, asset_id: str, new_name: str) -> AssetRecord | None:
        for scope in ("attachment", "resource"):
            table = self._asset_table_for_scope(scope)
            with self._lock:
                updated = self.conn.execute(
                    f"UPDATE {table} SET name = ?, updated_at = strftime('%s','now') WHERE id = ?",
                    (new_name, asset_id),
                )
                if updated.rowcount:
                    break
        return self.get_asset(asset_id, include_data=False)

    def delete_asset(self, asset_id: str) -> None:
        for scope in ("attachment", "resource"):
            table = self._asset_table_for_scope(scope)
            with self._lock:
                self.conn.execute(f"DELETE FROM {table} WHERE id = ?", (asset_id,))

    def update_asset_metadata(
        self,
        asset_id: str,
        updates: dict[str, Any],
        *,
        replace: bool = False,
    ) -> AssetRecord | None:
        """Merge new metadata into an asset record."""

        asset = self.get_asset(asset_id, include_data=False)
        if not asset:
            return None
        metadata = {} if replace else dict(asset.metadata or {})
        for key, value in (updates or {}).items():
            if value is None:
                metadata.pop(key, None)
            else:
                metadata[key] = value
        payload = _serialize(metadata)
        table = self._asset_table_for_scope(asset.scope)
        with self._lock:
            self.conn.execute(
                f"UPDATE {table} SET metadata = ?, updated_at = strftime('%s','now') WHERE id = ?",
                (payload, asset.asset_id),
            )
        asset.metadata = metadata
        return asset

    def snapshot_to(self, dest_path: str | Path) -> str:
        """Create a consistent copy of the current `.benort` database."""

        target = Path(dest_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.conn.commit()
            dest_conn = sqlite3.connect(str(target))
            try:
                self.conn.backup(dest_conn)
            finally:
                dest_conn.close()
        return str(target)

    # Composite helpers -----------------------------------------------------
    def export_project(self) -> dict[str, Any]:
        pages = [rec.payload for rec in self.list_pages()]
        template = self.get_template_block("latex", get_default_template())
        md_template = self.get_template_block("markdown", get_default_markdown_template())
        meta = self._get_meta("project", {}) or {}
        if not isinstance(meta, dict):
            meta = {}
        resources_meta = self._list_project_resources()
        references = self._list_project_references()
        llm_meta = meta.get("llm") if isinstance(meta.get("llm"), dict) else {}
        return {
            "project": meta.get("name") or self.path.stem,
            "updatedAt": meta.get("updatedAt"),
            "pages": pages,
            "template": template,
            "markdownTemplate": md_template,
            "resources": resources_meta,
            "bib": references,
            "attachments": [asset.name for asset in self.list_assets("attachment")],
            "llm": llm_meta,
        }

    def save_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        expected_ts_raw = payload.get("clientUpdatedAt") or payload.get("expectedUpdatedAt")
        existing_meta = self._get_meta("project", {}) or {}
        if not isinstance(existing_meta, dict):
            existing_meta = {}
        if expected_ts_raw is not None:
            try:
                expected_ts = float(expected_ts_raw)
            except (TypeError, ValueError):
                expected_ts = None
            else:
                current_ts = existing_meta.get("updatedAt")
                try:
                    current_ts_val = float(current_ts) if current_ts is not None else None
                except (TypeError, ValueError):
                    current_ts_val = None
                if current_ts_val is not None and expected_ts is not None and current_ts_val - expected_ts > 1e-6:
                    raise WorkspaceVersionConflict("工作区已被其他会话更新，请刷新后再保存")

        pages = payload.get("pages") or []
        self.save_pages(pages)
        if "template" in payload:
            self.save_template("latex", payload["template"])
        if "markdownTemplate" in payload:
            self.save_template("markdown", payload["markdownTemplate"])
        if "resources" in payload:
            self._replace_project_resources(payload.get("resources"))
        if "bib" in payload:
            self._replace_project_references(payload.get("bib"))
        meta = existing_meta
        if not isinstance(meta, dict):
            meta = {}
        meta["updatedAt"] = time.time()
        if payload.get("project"):
            meta["name"] = payload["project"]
        if isinstance(payload.get("llm"), dict):
            meta["llm"] = payload.get("llm")
        self._set_meta("project", meta)
        return self.export_project()

    def get_project_meta(self) -> dict[str, Any]:
        """Return lightweight project metadata (name, updatedAt)."""

        meta = self._get_meta("project", {}) or {}
        if not isinstance(meta, dict):
            meta = {}
        return {
            "project": meta.get("name") or self.path.stem,
            "updatedAt": meta.get("updatedAt"),
        }


def create_package(path: str, project_name: Optional[str] = None) -> BenortPackage:
    package = BenortPackage(path)
    project_name = project_name or Path(path).stem
    package.initialize_defaults(project_name)
    return package


__all__ = [
    "AssetRecord",
    "BenortPackage",
    "PageRecord",
    "create_package",
    "WorkspaceVersionConflict",
]
