"""Runtime workspace registry for `.benort` packages."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from werkzeug.utils import secure_filename

from .oss_client import (
    download_workspace_package,
    list_workspace_packages as oss_list_workspace_packages,
    upload_workspace_package,
    workspace_package_exists,
)
from .package import BenortPackage, create_package
from .oss_client import is_configured as oss_is_configured

WorkspaceMode = Literal["local", "cloud"]


@dataclass(slots=True)
class WorkspaceHandle:
    workspace_id: str
    mode: WorkspaceMode
    display_name: str
    source: str
    local_path: str
    package: BenortPackage
    remote_key: Optional[str] = None
    locked: bool = False
    unlocked: bool = True

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "mode": self.mode,
            "source": self.source,
            "display_name": self.display_name,
            "localPath": self.local_path,
            "remote_key": self.remote_key,
            "locked": self.locked,
            "unlocked": self.unlocked,
        }


class WorkspaceNotFoundError(KeyError):
    pass


class WorkspaceLockedError(PermissionError):
    pass


_REGISTRY: Dict[str, WorkspaceHandle] = {}
_LOCK = threading.RLock()
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PORTABLE_HANDLE_ID: Optional[str] = None
_PORTABLE_ERROR: Optional[str] = None
_SHARED_REGISTRY_DIR = Path(tempfile.gettempdir()) / "benort_workspace_registry"


def _ensure_suffix(path: str) -> str:
    if path.endswith(".benort"):
        return path
    return f"{path}.benort"


def _derive_display_name(path: Path) -> str:
    return path.name.replace(".benort", "")


def _sanitize_remote_name(name: str) -> str:
    return _normalize_remote_name_for_open(name)


def _normalize_remote_name_for_open(name: str) -> str:
    cleaned = str(name or "").strip().strip("/")
    if not cleaned:
        raise ValueError("无效的工作区名")
    parts = []
    for segment in cleaned.split("/"):
        seg = segment.strip()
        if not seg or seg in {".", ".."}:
            continue
        safe = secure_filename(seg) or "workspace"
        parts.append(safe)
    if not parts:
        raise ValueError("无效的工作区名")
    normalized = "/".join(parts)
    if not normalized.lower().endswith(".benort"):
        normalized = f"{normalized}.benort"
    return normalized


def _default_local_workspace_dir() -> Path:
    return _PROJECT_ROOT


def _resolve_local_search_dir(base_dir: Optional[str]) -> Path:
    return _default_local_workspace_dir()


def _shared_registry_path(workspace_id: str) -> Path:
    safe = secure_filename(workspace_id) or "workspace"
    return _SHARED_REGISTRY_DIR / f"{safe}.json"


def _persist_workspace_record(handle: WorkspaceHandle) -> None:
    payload = {
        "workspace_id": handle.workspace_id,
        "mode": handle.mode,
        "display_name": handle.display_name,
        "source": handle.source,
        "local_path": handle.local_path,
        "remote_key": handle.remote_key,
        "locked": handle.locked,
        "unlocked": handle.unlocked,
    }
    try:
        _SHARED_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        path = _shared_registry_path(handle.workspace_id)
        temp_path = path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp)
        temp_path.replace(path)
    except Exception:
        # Registry persistence is best-effort; ignore if the temp dir is unavailable.
        pass


def _load_workspace_record(workspace_id: str) -> Optional[dict]:
    path = _shared_registry_path(workspace_id)
    try:
        with path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _remove_workspace_record(workspace_id: str) -> None:
    path = _shared_registry_path(workspace_id)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _recover_workspace(workspace_id: str) -> WorkspaceHandle:
    """Re-open a workspace in the current process using the shared registry."""

    record = _load_workspace_record(workspace_id)
    if not record:
        raise WorkspaceNotFoundError(workspace_id)

    mode = record.get("mode") or "local"
    if mode == "cloud":
        remote_key = record.get("remote_key") or record.get("source")
        if not remote_key:
            raise WorkspaceNotFoundError(workspace_id)
        local_hint = record.get("local_path") or ""
        temp_path = Path(local_hint) if local_hint else Path(_remote_tempfile(remote_key))
        try:
            if not temp_path.exists():
                download_workspace_package(remote_key, str(temp_path))
        except Exception:
            temp_path = Path(_remote_tempfile(remote_key))
            download_workspace_package(remote_key, str(temp_path))
        package = BenortPackage(str(temp_path))
        handle = WorkspaceHandle(
            workspace_id=workspace_id,
            mode="cloud",
            display_name=record.get("display_name") or Path(remote_key).stem,
            source=remote_key,
            local_path=str(temp_path),
            package=package,
            remote_key=remote_key,
        )
    else:
        local_path = record.get("local_path") or record.get("source")
        if not local_path:
            raise WorkspaceNotFoundError(workspace_id)
        normalized = Path(_ensure_suffix(local_path)).expanduser().resolve()
        if not normalized.exists():
            raise WorkspaceNotFoundError(workspace_id)
        package = BenortPackage(str(normalized))
        handle = WorkspaceHandle(
            workspace_id=workspace_id,
            mode="local",
            source=str(normalized),
            local_path=str(normalized),
            display_name=record.get("display_name") or _derive_display_name(normalized),
            package=package,
        )
    handle.locked = bool(record.get("locked"))
    handle.unlocked = bool(record.get("unlocked", True))
    _refresh_handle_security(handle, preserve_unlock=True, persist=True)
    return handle


def discover_local_workspaces(
    base_dir: Optional[str] = None,
    *,
    recursive: bool = False,
    limit: int = 200,
) -> dict:
    target = _resolve_local_search_dir(base_dir)
    exists = target.exists()
    workspaces: List[dict] = []
    if exists:
        iterator = target.rglob("*.benort") if recursive else target.glob("*.benort")
        for path in iterator:
            if not path.is_file():
                continue
            try:
                stat_result = path.stat()
            except OSError:
                continue
            workspaces.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "displayName": _derive_display_name(path),
                    "size": stat_result.st_size,
                    "lastModified": datetime.fromtimestamp(stat_result.st_mtime).isoformat(),
                }
            )
            if len(workspaces) >= limit:
                break
    parent = None
    try:
        candidate_parent = target.parent
        if candidate_parent != target:
            parent = str(candidate_parent)
    except Exception:
        parent = None
    return {
        "base": str(target),
        "root": str(target),
        "parent": parent,
        "directories": [],
        "workspaces": workspaces,
        "exists": exists,
        "recursive": recursive,
        "limit": limit,
        "limited": len(workspaces) >= limit,
    }


def _remote_tempfile(name: str) -> str:
    safe = secure_filename(name or "") or "workspace"
    safe = safe.replace(".benort", "")
    temp_dir = Path(tempfile.gettempdir()) / "benort_remote_workspaces"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{safe}_{uuid.uuid4().hex[:6]}.benort"
    return str(temp_path)


def _register(handle: WorkspaceHandle) -> WorkspaceHandle:
    with _LOCK:
        _REGISTRY[handle.workspace_id] = handle
    _persist_workspace_record(handle)
    return handle


def _refresh_handle_security(
    handle: WorkspaceHandle,
    *,
    preserve_unlock: bool = False,
    persist: bool = False,
) -> WorkspaceHandle:
    prev_locked = handle.locked
    prev_unlocked = getattr(handle, "unlocked", False)
    has_password = handle.package.has_workspace_password()
    handle.locked = has_password
    if not has_password:
        handle.unlocked = True
    else:
        if preserve_unlock and getattr(handle, "unlocked", False):
            handle.unlocked = True
        else:
            handle.unlocked = False
    if persist and (handle.locked != prev_locked or handle.unlocked != prev_unlocked):
        _persist_workspace_record(handle)
    return handle


def list_workspaces() -> list[dict]:
    with _LOCK:
        handles = list(_REGISTRY.values())
        for handle in handles:
            _refresh_handle_security(handle, preserve_unlock=True, persist=True)
        return [handle.to_dict() for handle in handles]


def create_local_workspace(path: str, project_name: Optional[str] = None) -> WorkspaceHandle:
    normalized = Path(_ensure_suffix(path)).expanduser().resolve()
    os.makedirs(normalized.parent, exist_ok=True)
    package = create_package(str(normalized), project_name or normalized.stem)
    workspace_id = uuid.uuid4().hex
    handle = WorkspaceHandle(
        workspace_id=workspace_id,
        mode="local",
        source=str(normalized),
        local_path=str(normalized),
        display_name=project_name or _derive_display_name(normalized),
        package=package,
    )
    _refresh_handle_security(handle)
    return _register(handle)


def open_local_workspace(path: str) -> WorkspaceHandle:
    normalized = Path(_ensure_suffix(path)).expanduser().resolve()
    if not normalized.exists():
        raise FileNotFoundError(f"Workspace file not found: {normalized}")
    package = BenortPackage(str(normalized))
    workspace_id = uuid.uuid4().hex
    handle = WorkspaceHandle(
        workspace_id=workspace_id,
        mode="local",
        source=str(normalized),
        local_path=str(normalized),
        display_name=_derive_display_name(normalized),
        package=package,
    )
    _refresh_handle_security(handle)
    return _register(handle)


def list_remote_workspaces() -> dict:
    if not oss_is_configured():
        return {"workspaces": [], "directories": [], "dir": ""}
    listing = oss_list_workspace_packages(None)
    listing["dir"] = ""
    listing["directories"] = []
    return listing


def create_remote_workspace(path: str, project_name: Optional[str] = None) -> WorkspaceHandle:
    if not oss_is_configured():
        raise RuntimeError("未配置 OSS，无法创建远程工作区")
    remote_name = _sanitize_remote_name(path)
    if workspace_package_exists(remote_name):
        raise FileExistsError("远程工作区已存在")
    temp_path = Path(_remote_tempfile(remote_name))
    package = create_package(str(temp_path), project_name or temp_path.stem)
    upload_workspace_package(str(temp_path), remote_name, overwrite=False)
    workspace_id = uuid.uuid4().hex
    handle = WorkspaceHandle(
        workspace_id=workspace_id,
        mode="cloud",
        display_name=project_name or Path(remote_name).stem,
        source=remote_name,
        local_path=str(temp_path),
        package=package,
        remote_key=remote_name,
    )
    _refresh_handle_security(handle)
    return _register(handle)


def open_remote_workspace(path: str) -> WorkspaceHandle:
    if not oss_is_configured():
        raise RuntimeError("未配置 OSS，无法打开远程工作区")
    remote_name = _normalize_remote_name_for_open(path)
    temp_path = Path(_remote_tempfile(remote_name))
    download_workspace_package(remote_name, str(temp_path))
    package = BenortPackage(str(temp_path))
    workspace_id = uuid.uuid4().hex
    handle = WorkspaceHandle(
        workspace_id=workspace_id,
        mode="cloud",
        display_name=Path(remote_name).stem,
        source=remote_name,
        local_path=str(temp_path),
        package=package,
        remote_key=remote_name,
    )
    _refresh_handle_security(handle)
    return _register(handle)


def sync_remote_workspace(handle: WorkspaceHandle) -> None:
    if handle.mode != "cloud" or not handle.remote_key:
        return
    upload_workspace_package(str(handle.package.path), handle.remote_key, overwrite=True)


def close_workspace(workspace_id: str) -> None:
    _remove_workspace_record(workspace_id)
    with _LOCK:
        handle = _REGISTRY.pop(workspace_id, None)
    global _PORTABLE_HANDLE_ID
    if handle and _PORTABLE_HANDLE_ID and handle.workspace_id == _PORTABLE_HANDLE_ID:
        _PORTABLE_HANDLE_ID = None
    if handle:
        local_path = getattr(handle, "local_path", None) or getattr(handle.package, "path", None)
        handle.package.close()
        if handle.mode == "cloud" and local_path:
            try:
                os.remove(str(local_path))
            except Exception:
                pass


def get_workspace(workspace_id: str) -> WorkspaceHandle:
    with _LOCK:
        handle = _REGISTRY.get(workspace_id)
    if not handle:
        try:
            recovered = _recover_workspace(workspace_id)
        except WorkspaceNotFoundError:
            raise
        return _register(recovered)
    return handle


def get_workspace_package(workspace_id: str) -> BenortPackage:
    handle = get_workspace(workspace_id)
    if handle.locked and not handle.unlocked:
        raise WorkspaceLockedError(workspace_id)
    return handle.package


def _ensure_password_permission(handle: WorkspaceHandle, current_password: Optional[str]) -> None:
    if not handle.package.has_workspace_password():
        return
    normalized = (current_password or "").strip()
    if normalized:
        if handle.package.verify_workspace_password(normalized):
            return
        raise PermissionError("当前密码不正确")
    if handle.unlocked:
        return
    raise PermissionError("需要提供当前密码")


def set_workspace_password(workspace_id: str, new_password: str, current_password: Optional[str] = None) -> WorkspaceHandle:
    if not (new_password or "").strip():
        raise ValueError("新密码不能为空")
    handle = get_workspace(workspace_id)
    _ensure_password_permission(handle, current_password)
    handle.package.save_workspace_password(new_password)
    handle.unlocked = True
    return _refresh_handle_security(handle, preserve_unlock=True, persist=True)


def clear_workspace_password(workspace_id: str, current_password: Optional[str] = None) -> WorkspaceHandle:
    handle = get_workspace(workspace_id)
    _ensure_password_permission(handle, current_password)
    handle.package.clear_workspace_password()
    handle.unlocked = True
    return _refresh_handle_security(handle, preserve_unlock=True, persist=True)


def unlock_workspace(workspace_id: str, password: str) -> WorkspaceHandle:
    handle = get_workspace(workspace_id)
    normalized = (password or "").strip()
    if not normalized:
        raise ValueError("密码不能为空")
    if not handle.package.verify_workspace_password(normalized):
        raise PermissionError("密码不正确")
    handle.unlocked = True
    return _refresh_handle_security(handle, preserve_unlock=True, persist=True)


def ensure_portable_workspace_loaded() -> Optional[WorkspaceHandle]:
    """Ensure env-configured portable workspaces are registered."""

    global _PORTABLE_HANDLE_ID, _PORTABLE_ERROR
    path = (os.environ.get("BENORT_PORTABLE_WORKSPACE") or "").strip()
    if not path:
        return None
    with _LOCK:
        if _PORTABLE_HANDLE_ID and _PORTABLE_HANDLE_ID in _REGISTRY:
            return _REGISTRY[_PORTABLE_HANDLE_ID]
    try:
        handle = open_local_workspace(path)
    except Exception as exc:
        _PORTABLE_ERROR = str(exc)
        return None
    display_name = (os.environ.get("BENORT_PORTABLE_WORKSPACE_NAME") or "").strip()
    if display_name:
        handle.display_name = display_name
    _PORTABLE_HANDLE_ID = handle.workspace_id
    _PORTABLE_ERROR = None
    return handle


def portable_workspace_context() -> dict[str, Optional[object]]:
    handle = ensure_portable_workspace_loaded()
    if handle:
        payload = handle.to_dict()
        payload["source"] = handle.source
        payload["localPath"] = handle.local_path
        return {"workspace": payload, "error": None}
    if _PORTABLE_ERROR:
        return {"workspace": None, "error": _PORTABLE_ERROR}
    if (os.environ.get("BENORT_PORTABLE_WORKSPACE") or "").strip():
        return {"workspace": None, "error": "无法打开内置工作区，请检查文件路径是否存在"}
    return {"workspace": None, "error": None}


__all__ = [
    "WorkspaceHandle",
    "WorkspaceNotFoundError",
    "WorkspaceLockedError",
    "close_workspace",
    "discover_local_workspaces",
    "create_local_workspace",
    "create_remote_workspace",
    "get_workspace",
    "get_workspace_package",
    "list_workspaces",
    "list_remote_workspaces",
    "open_local_workspace",
    "open_remote_workspace",
    "sync_remote_workspace",
    "set_workspace_password",
    "clear_workspace_password",
    "unlock_workspace",
    "ensure_portable_workspace_loaded",
    "portable_workspace_context",
]

if os.environ.get("BENORT_PORTABLE_WORKSPACE"):
    ensure_portable_workspace_loaded()
