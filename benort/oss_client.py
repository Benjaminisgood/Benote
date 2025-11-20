from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from werkzeug.utils import secure_filename

from flask import current_app

try:  # pragma: no cover - optional dependency guard
    import oss2  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    oss2 = None  # type: ignore


@dataclass(slots=True)
class OSSSettings:
    endpoint: str
    access_key_id: str
    access_key_secret: str
    bucket_name: str
    prefix: str
    public_base_url: Optional[str]

DEFAULT_CATEGORY = "attachments"
DEFAULT_WORKSPACE_PREFIX = "workspaces"


def _clean_prefix(prefix: str) -> str:
    if not prefix:
        return DEFAULT_CATEGORY
    cleaned = prefix.strip().strip("/")
    return cleaned or DEFAULT_CATEGORY


def _normalize_category(category: Optional[str]) -> str:
    if category is None:
        return DEFAULT_CATEGORY
    normalized = category.strip().strip("/")
    return normalized or DEFAULT_CATEGORY


def _category_segments(category: str) -> list[str]:
    if category == "yaml":
        return [".yaml"]
    if category in {"attachments", "resources"}:
        return [category]
    return [category]


def _base_segments(settings: OSSSettings, project_name: str) -> list[str]:
    prefix = settings.prefix.strip("/")
    project = project_name.strip().strip("/")
    segments: list[str] = []
    if prefix:
        segments.append(prefix)
    if project:
        segments.append(project)
    return segments


def _legacy_object_keys(
    settings: OSSSettings, project_name: str, filename: str, category: Optional[str]
) -> list[str]:
    name = filename.strip().lstrip("/")
    if not name:
        return []
    normalized_category = _normalize_category(category)
    prefix = settings.prefix.strip("/")
    project = project_name.strip().strip("/")

    segments: list[str] = []
    if prefix:
        segments.append(prefix)

    legacy_category = None if normalized_category == "attachments" else normalized_category
    if legacy_category == "yaml":
        legacy_category = "yaml"

    if legacy_category:
        segments.append(legacy_category)
    if project:
        segments.append(project)
    segments.append(name)

    key = "/".join(filter(None, segments))
    return [key] if key else []


def get_settings() -> Optional[OSSSettings]:
    """Read OSS configuration from the Flask app context."""

    app = current_app._get_current_object()  # type: ignore[attr-defined]
    endpoint = app.config.get("ALIYUN_OSS_ENDPOINT") or os.environ.get("ALIYUN_OSS_ENDPOINT")
    access_key_id = app.config.get("ALIYUN_OSS_ACCESS_KEY_ID") or os.environ.get("ALIYUN_OSS_ACCESS_KEY_ID")
    access_key_secret = app.config.get("ALIYUN_OSS_ACCESS_KEY_SECRET") or os.environ.get("ALIYUN_OSS_ACCESS_KEY_SECRET")
    bucket_name = app.config.get("ALIYUN_OSS_BUCKET") or os.environ.get("ALIYUN_OSS_BUCKET")
    prefix = app.config.get("ALIYUN_OSS_PREFIX") or os.environ.get("ALIYUN_OSS_PREFIX") or "attachments"
    public_base_url = app.config.get("ALIYUN_OSS_PUBLIC_BASE_URL") or os.environ.get("ALIYUN_OSS_PUBLIC_BASE_URL")

    if not all([endpoint, access_key_id, access_key_secret, bucket_name]):
        return None
    if oss2 is None:
        raise RuntimeError("oss2 库未安装，无法使用 OSS 同步功能")

    return OSSSettings(
        endpoint=str(endpoint),
        access_key_id=str(access_key_id),
        access_key_secret=str(access_key_secret),
        bucket_name=str(bucket_name),
        prefix=_clean_prefix(str(prefix)),
        public_base_url=str(public_base_url) if public_base_url else None,
    )


def is_configured() -> bool:
    """Return True when OSS sync can be used."""

    try:
        return get_settings() is not None
    except RuntimeError:
        return False


def _get_bucket(settings: OSSSettings):
    auth = oss2.Auth(settings.access_key_id, settings.access_key_secret)
    return oss2.Bucket(auth, settings.endpoint, settings.bucket_name)


def _object_key(
    settings: OSSSettings,
    project_name: str,
    filename: str,
    category: Optional[str] = None,
) -> str:
    name = filename.strip().lstrip("/")
    normalized_category = _normalize_category(category)
    segments = _base_segments(settings, project_name)
    segments.extend(_category_segments(normalized_category))
    if name:
        segments.append(name)
    key = "/".join(filter(None, segments))
    return key


def _object_prefix(settings: OSSSettings, project_name: str, category: Optional[str] = None) -> str:
    key = _object_key(settings, project_name, "", category)
    if key and not key.endswith("/"):
        key = f"{key}/"
    return key


def _workspace_dir() -> str:
    app = current_app._get_current_object()  # type: ignore[attr-defined]
    value = (
        app.config.get("OSS_WORKSPACE_PREFIX")
        or os.environ.get("OSS_WORKSPACE_PREFIX")
        or DEFAULT_WORKSPACE_PREFIX
    )
    cleaned = str(value).strip().strip("/")
    return cleaned or DEFAULT_WORKSPACE_PREFIX


def _workspace_root_prefix(settings: OSSSettings) -> str:
    root = settings.prefix.strip("/")
    if root and not root.endswith("/"):
        root = f"{root}/"
    return root


def _normalize_workspace_listing_dir(name: Optional[str]) -> str:
    if not name:
        return ""
    raw = str(name).replace("\\", "/").strip().strip("/")
    if not raw:
        return ""
    segments: List[str] = []
    for segment in raw.split("/"):
        seg = segment.strip()
        if not seg or seg in {".", ".."}:
            continue
        segments.append(seg)
    return "/".join(segments)


def _sanitize_workspace_name(name: str) -> str:
    base = secure_filename(name or "") or "workspace"
    if not base.lower().endswith(".benort"):
        base = f"{base}.benort"
    return base


def _workspace_object_key(settings: OSSSettings, name: str) -> str:
    sanitized = _sanitize_workspace_name(name)
    root = _workspace_root_prefix(settings)
    return f"{root}{sanitized}"


def build_public_url(settings: OSSSettings, key: str) -> str:
    if settings.public_base_url:
        base = settings.public_base_url.rstrip("/")
        return f"{base}/{key}"
    endpoint = settings.endpoint.lstrip("http://").lstrip("https://")
    return f"https://{settings.bucket_name}.{endpoint}/{key}"


def upload_file(project_name: str, filename: str, local_path: str, category: Optional[str] = None) -> Optional[str]:
    """Upload a local file to OSS and return its public URL."""

    settings = get_settings()
    if not settings:
        return None
    bucket = _get_bucket(settings)
    key = _object_key(settings, project_name, filename, category)

    with open(local_path, "rb") as fh:
        bucket.put_object(key, fh)

    for legacy_key in _legacy_object_keys(settings, project_name, filename, category):
        if legacy_key == key:
            continue
        try:  # pragma: no cover - best effort cleanup
            bucket.delete_object(legacy_key)
        except Exception:
            pass
    return build_public_url(settings, key)


def upload_bytes(
    project_name: str,
    filename: str,
    data: bytes | bytearray | memoryview,
    category: Optional[str] = None,
) -> Optional[dict[str, object]]:
    """Upload in-memory data to OSS and return metadata for the object."""

    settings = get_settings()
    if not settings:
        return None
    bucket = _get_bucket(settings)
    key = _object_key(settings, project_name, filename, category)
    payload = bytes(data)
    result = bucket.put_object(key, payload)
    for legacy_key in _legacy_object_keys(settings, project_name, filename, category):
        if legacy_key == key:
            continue
        try:  # pragma: no cover - best effort cleanup
            bucket.delete_object(legacy_key)
        except Exception:
            pass
    return {
        "url": build_public_url(settings, key),
        "key": key,
        "etag": getattr(result, "etag", None),
        "bucket": settings.bucket_name,
        "size": len(payload),
    }


def delete_file(project_name: str, filename: str, category: Optional[str] = None) -> None:
    """Delete an attachment from OSS."""

    settings = get_settings()
    if not settings:
        return
    bucket = _get_bucket(settings)
    key = _object_key(settings, project_name, filename, category)
    bucket.delete_object(key)
    for legacy_key in _legacy_object_keys(settings, project_name, filename, category):
        if legacy_key == key:
            continue
        try:  # pragma: no cover - best effort cleanup
            bucket.delete_object(legacy_key)
        except Exception:
            pass


def list_files(project_name: str, category: Optional[str] = None, with_meta: bool = False) -> Dict[str, object]:
    """Return a map of filename to public URL for OSS objects under the project."""

    settings = get_settings()
    if not settings:
        return {}
    bucket = _get_bucket(settings)
    prefix = _object_prefix(settings, project_name, category)
    results: Dict[str, object] = {}
    for obj in oss2.ObjectIterator(bucket, prefix=prefix):
        if not obj.key or obj.key.endswith("/"):
            continue
        rel = obj.key[len(prefix) :]
        if not rel:
            continue
        if with_meta:
            results[rel] = {
                "url": build_public_url(settings, obj.key),
                "etag": getattr(obj, "etag", None),
                "size": getattr(obj, "size", None),
                "last_modified": getattr(obj, "last_modified", None),
            }
        else:
            results[rel] = build_public_url(settings, obj.key)
    return results


def list_workspace_packages(subdir: Optional[str] = None) -> Dict[str, object]:
    settings = get_settings()
    if not settings:
        return {"workspaces": [], "directories": [], "dir": "", "prefix": "", "bucket": None}
    bucket = _get_bucket(settings)
    root_prefix = _workspace_root_prefix(settings)
    normalized_dir = _normalize_workspace_listing_dir(subdir)
    rel_prefix = f"{normalized_dir}/" if normalized_dir else ""
    search_prefix = f"{root_prefix}{rel_prefix}"
    package_entries: List[tuple[int, dict]] = []
    for obj in oss2.ObjectIterator(bucket, prefix=search_prefix):
        key = getattr(obj, "key", "")
        if not key or key.endswith("/"):
            continue
        rel = key[len(root_prefix) :]
        if rel_prefix:
            if not rel.startswith(rel_prefix):
                continue
            rel_inside_dir = rel[len(rel_prefix) :]
        else:
            rel_inside_dir = rel
        if not rel_inside_dir:
            continue
        cleaned_rel = rel_inside_dir.strip("/")
        if not cleaned_rel or not cleaned_rel.lower().endswith(".benort"):
            continue
        ts_raw = getattr(obj, "last_modified", None)
        iso_ts = None
        sort_ts = 0
        if ts_raw is not None:
            try:
                sort_ts = int(ts_raw)
                iso_ts = datetime.fromtimestamp(sort_ts, tz=timezone.utc).isoformat()
            except Exception:
                sort_ts = 0
                iso_ts = None
        display_name = cleaned_rel.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        package_entries.append(
            (
                sort_ts,
                {
                    "name": rel,
                    "relativeName": cleaned_rel,
                    "displayName": display_name,
                    "size": getattr(obj, "size", None),
                    "lastModified": iso_ts,
                    "key": key,
                    "url": build_public_url(settings, key),
                },
            )
        )
    packages = [entry for _, entry in sorted(package_entries, key=lambda item: item[0], reverse=True)]
    return {
        "workspaces": packages,
        "directories": [],
        "dir": normalized_dir,
        "prefix": root_prefix.rstrip("/"),
        "bucket": settings.bucket_name,
    }


def workspace_package_exists(name: str) -> bool:
    settings = get_settings()
    if not settings:
        return False
    bucket = _get_bucket(settings)
    key = _workspace_object_key(settings, name)
    try:
        bucket.head_object(key)
        return True
    except Exception:
        return False


def download_workspace_package(name: str, dest_path: str) -> None:
    settings = get_settings()
    if not settings:
        raise RuntimeError("OSS 未配置")
    bucket = _get_bucket(settings)
    key = _workspace_object_key(settings, name)
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    bucket.get_object_to_file(key, dest_path)


def upload_workspace_package(local_path: str, name: str, *, overwrite: bool = True) -> None:
    settings = get_settings()
    if not settings:
        raise RuntimeError("OSS 未配置")
    if not overwrite and workspace_package_exists(name):
        raise FileExistsError("远程工作区已存在")
    bucket = _get_bucket(settings)
    key = _workspace_object_key(settings, name)
    bucket.put_object_from_file(key, local_path)
