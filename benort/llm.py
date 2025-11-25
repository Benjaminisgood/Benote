"""LLM 提供方配置与调用辅助函数。"""

from __future__ import annotations

import copy
import os
from typing import Any, Dict, List, Optional

from .config import DEFAULT_LLM_PROVIDER, LLM_PROVIDERS


def _normalize_provider_id(provider_id: Optional[str]) -> str:
    """标准化提供方标识，若无效则回退到默认值。"""

    if provider_id:
        cleaned = provider_id.strip().lower()
    else:
        cleaned = ""
    if cleaned and cleaned in LLM_PROVIDERS:
        return cleaned
    return DEFAULT_LLM_PROVIDER if DEFAULT_LLM_PROVIDER in LLM_PROVIDERS else next(iter(LLM_PROVIDERS))


def _normalize_path(path: str) -> str:
    trimmed = (path or "").strip()
    if not trimmed:
        return "/chat/completions"
    if not trimmed.startswith("/"):
        return f"/{trimmed}"
    return trimmed


def _normalize_base_url(url: str) -> str:
    trimmed = (url or "").strip()
    if not trimmed:
        return ""
    return trimmed[:-1] if trimmed.endswith("/") else trimmed


def _copy_provider(provider_id: str) -> Dict[str, Any]:
    """创建配置拷贝，避免修改全局注册表。"""

    base = LLM_PROVIDERS[provider_id]
    copied = {key: copy.deepcopy(value) for key, value in base.items()}
    copied["id"] = provider_id  # 确保 id 存在且准确
    return copied


def _env_is_default_provider(provider_id: str) -> bool:
    """判断当前 provider 是否为环境变量约定的默认 provider。"""

    env_provider = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if env_provider and env_provider in LLM_PROVIDERS:
        return provider_id == env_provider
    return provider_id == DEFAULT_LLM_PROVIDER


def resolve_llm_config(
    provider_id: Optional[str] = None,
    *,
    project: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    embedding_model: Optional[str] = None,
    tts_model: Optional[str] = None,
    usage: str = "chat",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """根据项目与参数解析最终 LLM 配置。"""

    project_provider = None
    project_model = None
    project_embedding = None
    project_tts = None
    if isinstance(project, dict):
        project_llm = project.get("llm")
        if isinstance(project_llm, dict):
            chat_block = project_llm.get("chat") if isinstance(project_llm.get("chat"), dict) else {}
            embed_block = project_llm.get("embedding") if isinstance(project_llm.get("embedding"), dict) else {}
            tts_block = project_llm.get("tts") if isinstance(project_llm.get("tts"), dict) else {}
            if usage == "embedding":
                project_provider = embed_block.get("provider") or project_llm.get("provider")
                project_model = embed_block.get("model")
            elif usage == "tts":
                project_provider = tts_block.get("provider") or project_llm.get("provider")
                project_model = tts_block.get("model")
            else:
                project_provider = chat_block.get("provider") or project_llm.get("provider")
                project_model = chat_block.get("model") or project_llm.get("model")
            project_embedding = (
                embed_block.get("model")
                or project_llm.get("embeddingModel")
                or project_llm.get("embedding_model")
            )
            project_tts = tts_block.get("model") or project_llm.get("ttsModel") or project_llm.get("tts_model")

    resolved_id = _normalize_provider_id(provider_id or project_provider)
    provider = _copy_provider(resolved_id)

    # 应用环境变量覆盖（仅作用于默认 provider）
    if _env_is_default_provider(resolved_id):
        env_base_url = os.environ.get("LLM_BASE_URL")
        env_chat_path = os.environ.get("LLM_CHAT_PATH")
        env_embedding_path = os.environ.get("LLM_EMBEDDING_PATH")
        env_api_key_env = os.environ.get("LLM_API_KEY_ENV")
        if env_base_url:
            provider["base_url"] = env_base_url
        if env_chat_path:
            provider["chat_path"] = env_chat_path
        if env_embedding_path:
            provider["embedding_path"] = env_embedding_path
        if env_api_key_env:
            provider["api_key_env"] = env_api_key_env
        env_model = os.environ.get("LLM_MODEL")
        if env_model:
            provider["default_model"] = env_model
        env_embedding_model = os.environ.get("LLM_EMBEDDING_MODEL")
        if env_embedding_model:
            provider["default_embedding_model"] = env_embedding_model
        env_tts_model = os.environ.get("LLM_TTS_MODEL")
        if env_tts_model:
            provider["default_tts_model"] = env_tts_model

    if overrides:
        provider.update(overrides)

    provider["base_url"] = _normalize_base_url(str(provider.get("base_url") or ""))
    provider["chat_path"] = _normalize_path(str(provider.get("chat_path") or ""))
    provider["embedding_path"] = _normalize_path(str(provider.get("embedding_path") or "/embeddings"))
    provider["tts_path"] = _normalize_path(str(provider.get("tts_path") or "/audio/speech"))
    embedding_base = _normalize_base_url(str(provider.get("embedding_base_url") or provider["base_url"]))
    tts_base = _normalize_base_url(str(provider.get("tts_base_url") or provider["base_url"]))
    endpoint = f"{provider['base_url']}{provider['chat_path']}" if provider["base_url"] else provider["chat_path"]
    provider["endpoint"] = endpoint
    embedding_endpoint = (
        f"{embedding_base}{provider['embedding_path']}" if embedding_base else provider["embedding_path"]
    )
    provider["embedding_endpoint"] = embedding_endpoint
    tts_endpoint = f"{tts_base}{provider['tts_path']}" if tts_base else provider["tts_path"]
    provider["tts_endpoint"] = tts_endpoint

    chosen_model = model or project_model or provider.get("default_model")
    provider["model"] = chosen_model
    provider["embedding_model"] = (
        embedding_model
        or project_embedding
        or provider.get("embedding_model")
        or provider.get("default_embedding_model")
    )
    provider["tts_model"] = tts_model or project_tts or provider.get("tts_model") or provider.get("default_tts_model")

    api_key_env = str(provider.get("api_key_env") or "").strip()
    api_key = os.environ.get(api_key_env) if api_key_env else None
    provider["api_key_env"] = api_key_env
    provider["api_key"] = api_key

    return provider


def list_llm_providers() -> List[Dict[str, Any]]:
    """返回所有注册的 LLM 提供方信息（去除敏感字段）。"""

    providers: List[Dict[str, Any]] = []
    for provider_id, info in LLM_PROVIDERS.items():
        api_key_env = info.get("api_key_env")
        entry = {
            "id": provider_id,
            "label": info.get("label", provider_id.title()),
            "defaultModel": info.get("default_model"),
            "defaultEmbeddingModel": info.get("default_embedding_model"),
            "defaultTtsModel": info.get("default_tts_model"),
            "models": list(info.get("models") or []),
            "embeddingModels": list(info.get("embedding_models") or []),
            "ttsModels": list(info.get("tts_models") or []),
            "baseUrl": info.get("base_url"),
            "chatPath": info.get("chat_path"),
            "embeddingPath": info.get("embedding_path"),
            "ttsPath": info.get("tts_path"),
            "apiKeyEnv": api_key_env,
            "hasApiKey": bool(api_key_env and os.environ.get(str(api_key_env))),
        }
        providers.append(entry)
    return providers


def get_default_llm_state() -> Dict[str, Optional[str]]:
    """返回默认选中的 LLM 状态（chat/embedding/tts）。"""

    chat_config = resolve_llm_config()
    embedding_config = resolve_llm_config(usage="embedding")
    tts_config = resolve_llm_config(usage="tts")
    return {
        "chatProvider": chat_config.get("id"),
        "chatModel": chat_config.get("model"),
        "embeddingProvider": embedding_config.get("id"),
        "embeddingModel": embedding_config.get("embedding_model"),
        "ttsProvider": tts_config.get("id"),
        "ttsModel": tts_config.get("tts_model"),
    }


def build_chat_headers(provider_config: Dict[str, Any]) -> Dict[str, str]:
    """根据 provider 配置生成请求头。"""

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    api_key = provider_config.get("api_key")
    header_name = str(provider_config.get("api_key_header") or "Authorization")
    prefix = provider_config.get("api_key_prefix")
    if api_key:
        if prefix:
            headers[header_name] = f"{prefix}{api_key}"
        else:
            headers[header_name] = str(api_key)
    extra = provider_config.get("extra_headers")
    if isinstance(extra, dict):
        for key, value in extra.items():
            headers[str(key)] = str(value)
    return headers


def is_valid_provider(provider_id: Optional[str]) -> bool:
    """判断 provider 是否在注册表中。"""

    if not provider_id:
        return False
    return provider_id.strip().lower() in LLM_PROVIDERS


__all__ = [
    "resolve_llm_config",
    "list_llm_providers",
    "get_default_llm_state",
    "build_chat_headers",
    "is_valid_provider",
]
