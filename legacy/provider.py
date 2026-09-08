# Archived migration reference; not imported by the production runtime.
"""Redacted 9Router adapter.

Configuration is discovered from E:/api-key.properties.  Key values remain in
process memory only and are never returned or logged.  Network calls are
explicit tool calls, never background retries.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from logging_utils import log_event


CONFIG_PATH = Path("E:/api-key.properties")
PROVIDER_CONFIG_PATH = Path("E:/AI-DG/OUTPUT/runtime/provider-config.json")
KEYRING_SERVICE = "AI-DG/Provider"
MODEL_STATE_PATH = Path("E:/AI-DG/OUTPUT/runtime/model-state.json")
MODEL_CATALOG_PATH = Path("E:/AI-DG/OUTPUT/runtime/model-catalog.json")
PROVIDER_STATE_PATH = Path("E:/AI-DG/OUTPUT/runtime/provider-state.json")
LOCAL_9ROUTER_CATALOG_PATHS = tuple(
    path for path in (
        Path(os.environ["APPDATA"]) / "9router" / "model-catalog-raw.json"
        if os.environ.get("APPDATA") else None,
        Path.home() / "AppData" / "Roaming" / "9router" / "model-catalog-raw.json",
    ) if path is not None
)
KEY_NAMES = re.compile(r"(?:9router|orcarouter|openrouter)", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s\"\\]+", re.IGNORECASE)
DEFAULT_PROMPT = "Trả lời duy nhất: OK"
NETWORK_GATE_ERROR = "PROVIDER_NETWORK_TEST_REQUIRES_EXPLICIT_ENABLE"
PROVIDER_STATES = {
    "UNCONFIGURED",
    "TESTING",
    "CONNECTED",
    "AUTH_ERROR",
    "RATE_LIMITED",
    "NO_CREDIT",
    "OFFLINE",
    "MODEL_ERROR",
}

PROVIDER_TYPES = {
    "9router",
    "openai_compatible",
    "openrouter_compatible",
    "custom_compatible",
}


def _content_text(value: Any) -> str:
    """Normalize OpenAI-compatible string or text-part content safely."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return ""


def _response_message(payload: Any) -> dict[str, Any] | None:
    """Return the first assistant message only when the response shape is valid."""
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    return message if isinstance(message, dict) else None


def _network_enabled() -> bool:
    """Require an explicit process opt-in at the adapter boundary as well as MCP."""
    return os.environ.get("AI_DG_ALLOW_PROVIDER_TEST", "0") == "1"


def _network_blocked() -> dict[str, Any]:
    return {
        "status": "blocked",
        "error": NETWORK_GATE_ERROR,
        "request_count": 0,
        "hint": "Set AI_DG_ALLOW_PROVIDER_TEST=1 before starting the provider operation.",
    }


def _http_state(code: int) -> str:
    if code in {401, 403}:
        return "AUTH_ERROR"
    if code in {402, 409}:
        return "NO_CREDIT"
    if code == 429:
        return "RATE_LIMITED"
    if code >= 500:
        return "OFFLINE"
    return "MODEL_ERROR"


def _error_state(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return _http_state(int(exc.code))
    if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
        return "OFFLINE"
    return "MODEL_ERROR"


def _read_provider_state() -> dict[str, Any]:
    if not PROVIDER_STATE_PATH.is_file():
        return {}
    try:
        value = json.loads(PROVIDER_STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_provider_metadata() -> dict[str, Any]:
    """Read non-secret provider metadata saved by the provider manager."""
    if not PROVIDER_CONFIG_PATH.is_file():
        return {}
    try:
        value = json.loads(PROVIDER_CONFIG_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _keyring():
    """Load the OS credential-store adapter without making it mandatory at import time."""
    try:
        import keyring  # type: ignore

        return keyring
    except (ImportError, RuntimeError):
        return None


def _credential_ref(metadata: dict[str, Any]) -> str:
    value = str(metadata.get("credential_ref") or "provider:default").strip()
    return value[:200]


def _stored_secret(metadata: dict[str, Any]) -> str | None:
    """Return a key only from the OS secret store; never from metadata JSON."""
    if not metadata.get("enabled", True):
        return None
    keyring = _keyring()
    if keyring is None:
        return None
    try:
        value = keyring.get_password(KEYRING_SERVICE, _credential_ref(metadata))
    except Exception:
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _write_provider_metadata(metadata: dict[str, Any]) -> None:
    PROVIDER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = PROVIDER_CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(PROVIDER_CONFIG_PATH)


def _validate_provider_endpoint(value: str) -> str:
    endpoint = value.strip().rstrip("/")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("INVALID_PROVIDER_BASE_URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("INVALID_PROVIDER_BASE_URL")
    if parsed.scheme == "http" and parsed.hostname.lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("INSECURE_PROVIDER_URL_REQUIRES_LOCALHOST")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _validate_model_id(value: str) -> str:
    model = value.strip()
    if model and (len(model) > 200 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model)):
        raise ValueError("INVALID_MODEL_ID")
    return model


def configure_provider(
    provider_name: str,
    provider_type: str,
    base_url: str,
    model_id: str = "",
    api_key: str = "",
    enabled: bool = True,
) -> dict[str, Any]:
    """Save provider metadata and the API key in the OS credential store.

    The returned object is deliberately redacted.  A plaintext key is never
    written to the workspace, telemetry, or provider-state file.
    """
    name = provider_name.strip()[:100]
    kind = provider_type.strip().lower()
    endpoint = _validate_provider_endpoint(base_url)
    model = _validate_model_id(model_id)
    if not name:
        raise ValueError("PROVIDER_NAME_REQUIRED")
    if kind not in PROVIDER_TYPES:
        raise ValueError("INVALID_PROVIDER_TYPE")

    existing = _read_provider_metadata()
    credential_ref = _credential_ref(existing) if existing else "provider:default"
    secret = api_key.strip()
    if secret:
        if len(secret) < 8:
            raise ValueError("API_KEY_TOO_SHORT")
        keyring = _keyring()
        if keyring is None:
            return {
                "status": "error",
                "error": "SECRET_STORE_UNAVAILABLE",
                "detail": "Install/enable the Windows Credential Manager keyring backend before saving a provider key.",
            }
        try:
            keyring.set_password(KEYRING_SERVICE, credential_ref, secret)
        except Exception as exc:
            return {"status": "error", "error": "SECRET_STORE_WRITE_FAILED", "detail": exc.__class__.__name__}
    elif not _stored_secret({**existing, "credential_ref": credential_ref, "enabled": True}):
        return {"status": "error", "error": "API_KEY_REQUIRED", "detail": "Provide the key once; it is stored only in the OS credential store."}

    metadata = {
        "schema_version": "0.1",
        "provider_name": name,
        "provider_type": kind,
        "base_url": endpoint,
        "model_id": model,
        "enabled": bool(enabled),
        "credential_backend": "windows_credential_manager",
        "credential_ref": credential_ref,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _write_provider_metadata(metadata)
        if model:
            MODEL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            MODEL_STATE_PATH.write_text(json.dumps({
                "model": model,
                "mode": "MANUAL",
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        return {"status": "error", "error": "PROVIDER_CONFIG_WRITE_FAILED", "detail": exc.__class__.__name__}
    return {
        "status": "ok",
        "provider": name,
        "provider_type": kind,
        "base_url": _redacted_endpoint(endpoint),
        "model_id": model or None,
        "enabled": bool(enabled),
        "credential_present": True,
        "credential_backend": "windows_credential_manager",
        "network_test": "NOT_RUN",
    }


def disconnect_provider() -> dict[str, Any]:
    """Disable the configured provider and remove its OS-stored secret."""
    metadata = _read_provider_metadata()
    if not metadata:
        # Keep the legacy properties file untouched, but place a local
        # disabled marker in front of it so Disconnect really stops adapter
        # use until the user explicitly configures the provider again.
        try:
            _write_provider_metadata({
                "schema_version": "0.1",
                "provider_name": "9Router",
                "provider_type": "9router",
                "enabled": False,
                "credential_backend": "legacy_properties_file",
                "credential_ref": "provider:default",
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            })
        except OSError as exc:
            return {"status": "error", "error": "PROVIDER_CONFIG_WRITE_FAILED", "detail": exc.__class__.__name__}
        return {"status": "ok", "provider_status": "UNCONFIGURED", "credential_removed": False, "legacy_config_preserved": True}
    credential_removed = False
    keyring = _keyring()
    if keyring is not None:
        try:
            keyring.delete_password(KEYRING_SERVICE, _credential_ref(metadata))
            credential_removed = True
        except Exception:
            credential_removed = False
    metadata["enabled"] = False
    metadata["credential_present"] = False
    metadata["updated_utc"] = datetime.now(timezone.utc).isoformat()
    try:
        _write_provider_metadata(metadata)
    except OSError as exc:
        return {"status": "error", "error": "PROVIDER_CONFIG_WRITE_FAILED", "detail": exc.__class__.__name__}
    return {"status": "ok", "provider_status": "UNCONFIGURED", "credential_removed": credential_removed}
def _record_provider_state(**fields: Any) -> None:
    """Persist redacted provider telemetry only; never persist keys or prompts."""
    payload = {key: value for key, value in fields.items() if key not in {"secret", "api_key", "authorization", "prompt", "content"}}
    payload["updated_utc"] = datetime.now(timezone.utc).isoformat()
    try:
        PROVIDER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROVIDER_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def _read_config() -> tuple[str | None, list[str]]:
    metadata = _read_provider_metadata()
    if metadata:
        if not metadata.get("enabled", True):
            return None, []
        secret = _stored_secret(metadata)
        endpoint = str(metadata.get("base_url") or "").strip()
        return (secret, [endpoint]) if secret and endpoint else (None, [])
    if not CONFIG_PATH.is_file():
        return None, []
    candidates: list[tuple[int, int, str]] = []
    endpoints: list[str] = []
    for index, raw_line in enumerate(CONFIG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()):
        line = raw_line.strip()
        match = re.match(r"^([^=:#]+?)\s*[:=]\s*(.*)$", line)
        if match and KEY_NAMES.search(match.group(1)) and len(match.group(2).strip()) >= 16:
            key_name = match.group(1).strip().lower().replace("_", "").replace("-", "")
            # Prefer the key explicitly belonging to Orca/9Router.  A shared
            # properties file may also contain OpenRouter and other keys.
            priority = 0 if "orcarouter" in key_name else 1 if "9router" in key_name else 2
            candidates.append((priority, index, match.group(2).strip().strip('"').strip("'")))
        for url in URL_RE.findall(line):
            if "orcarouter" in url.lower() or "9router" in url.lower():
                endpoints.append(url.rstrip("'\""))
    secret = sorted(candidates, key=lambda row: (row[0], row[1]))[0][2] if candidates else None
    ordered_endpoints = sorted(set(endpoints), key=lambda value: (
        0 if "chat/completions" in value.lower() else 1 if "orcarouter" in value.lower() or "9router" in value.lower() else 2,
        value,
    ))
    return secret, ordered_endpoints


def _redacted_endpoint(value: str) -> str:
    """Remove URL credentials, query strings, and fragments from diagnostics."""
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.hostname:
        return "(invalid-endpoint)"
    netloc = parsed.hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port:
        netloc = f"{netloc}:{port}"
    return f"{parsed.scheme}://{netloc}{parsed.path}"


def status() -> dict[str, Any]:
    secret, endpoints = _read_config()
    metadata = _read_provider_metadata()
    configured = bool(secret and endpoints and metadata.get("enabled", True)) or (not metadata and bool(secret and endpoints))
    provider_name = str(metadata.get("provider_name") or "9Router")
    provider_type = str(metadata.get("provider_type") or "9router")
    model_id = str(metadata.get("model_id") or "").strip()
    result = {
        "provider": provider_name,
        "provider_type": provider_type,
        "config_path": str(CONFIG_PATH),
        "manager_config_path": str(PROVIDER_CONFIG_PATH),
        "credential_present": bool(secret),
        "credential_length": len(secret) if secret else 0,
        "endpoint_candidates": sorted(set(_redacted_endpoint(endpoint) for endpoint in endpoints)),
        "configured_model": model_id or None,
        "enabled": bool(metadata.get("enabled", True)) if metadata else configured,
        "credential_backend": metadata.get("credential_backend") if metadata else "legacy_properties_file",
        "network_test": "NOT_RUN",
        "status": "OFFLINE" if configured else "UNCONFIGURED",
        "configuration_present": configured,
        "verification_required": configured,
    }
    prior = _read_provider_state()
    if prior:
        prior_state = str(prior.get("status") or "")
        if prior_state in PROVIDER_STATES:
            result["status"] = prior_state
        result["last_test"] = {key: prior[key] for key in ("operation", "status", "latency_ms", "request_count", "error", "updated_utc") if key in prior}
    log_event("provider", "status_read", credential_present=bool(secret), endpoint_count=len(endpoints), network_test="NOT_RUN")
    return result


def _local_model_catalog() -> list[dict[str, Any]]:
    """Read only the sanitized model catalog produced by an explicit sync."""
    if MODEL_CATALOG_PATH.is_file():
        try:
            payload = json.loads(MODEL_CATALOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        rows = payload.get("models") if isinstance(payload, dict) else payload
        if isinstance(rows, list):
            allowed = {"id", "name", "context", "tool_support", "vision", "reasoning", "cost", "status", "latency_ms", "source"}
            safe: list[dict[str, Any]] = []
            for row in rows[:200]:
                if not isinstance(row, dict) or not str(row.get("id", "")).strip():
                    continue
                item = {key: row[key] for key in allowed if key in row}
                item.setdefault("source", "SYNCED_LOCAL")
                safe.append(item)
            if safe:
                return safe

    # The installed 9Router app keeps a non-secret provider/model cache.  It
    # is only a manual-ID suggestion source: it does not prove the current
    # endpoint or credential can use any of these models.
    metadata = _read_provider_metadata()
    if str(metadata.get("provider_type") or "9router").strip().lower() != "9router":
        return []
    for cache_path in LOCAL_9ROUTER_CATALOG_PATHS:
        if not cache_path.is_file():
            continue
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        catalog = payload.get("orcarouter") if isinstance(payload, dict) else None
        if not isinstance(catalog, dict):
            continue
        rows: list[dict[str, Any]] = []
        for raw_id, raw_meta in catalog.items():
            model_id = str(raw_id).strip()
            if not model_id or len(model_id) > 200 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model_id):
                continue
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            capabilities = meta.get("i") if isinstance(meta.get("i"), list) else []
            rows.append({
                "id": model_id,
                "name": model_id,
                "context": meta.get("c"),
                "vision": "image" in capabilities,
                "reasoning": meta.get("r"),
                "status": "LOCAL_CACHE_UNVERIFIED",
                "source": "LOCAL_9ROUTER_CACHE",
            })
        if rows:
            preferred = {
                "orcarouter/fusion": 0,
                "orcarouter/fusion-mini": 1,
                "orcarouter/fusion-flash": 2,
                "orcarouter/auto": 3,
                "orcarouter/free": 4,
            }
            rows.sort(key=lambda row: (preferred.get(row["id"], 10), row["id"]))
            return rows[:200]
    return []


def model_status() -> dict[str, Any]:
    """Return model-manager metadata without probing the network."""
    metadata = _read_provider_metadata()
    configured = str(metadata.get("model_id") or "").strip()
    if MODEL_STATE_PATH.is_file():
        try:
            state = json.loads(MODEL_STATE_PATH.read_text(encoding="utf-8"))
            configured = str(state.get("model", "")).strip() if isinstance(state, dict) else ""
        except (OSError, json.JSONDecodeError):
            configured = ""
    configured = configured or __import__("os").environ.get("AI_DG_MODEL", "").strip()
    models = _local_model_catalog()
    source = "NOT_QUERIED"
    if models:
        source = "LOCAL_9ROUTER_CACHE" if models[0].get("source") == "LOCAL_9ROUTER_CACHE" else "SYNCED_LOCAL"
    result = {
        "status": "ok",
        "provider": str(metadata.get("provider_name") or "9Router"),
        "mode": "MANUAL" if configured else "AUTO",
        "configured_model": configured or None,
        "available_models": models,
        "models_source": source,
        "network_test": "NOT_RUN",
        "catalog_path": str(MODEL_CATALOG_PATH),
    }
    log_event("provider", "model_status_read", configured=bool(configured), network_test="NOT_RUN")
    return result


def _models_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    path = parsed.path.rstrip("/")
    lowered = path.lower()
    if lowered.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")] + "/models"
    elif lowered.endswith("/responses"):
        path = path[: -len("/responses")] + "/models"
    elif not lowered.endswith("/models"):
        path = (path or "") + "/models"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _chat_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    path = parsed.path.rstrip("/")
    lowered = path.lower()
    if lowered.endswith("/models"):
        path = path[:-len("/models")] + "/chat/completions"
    elif lowered.endswith("/responses"):
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    elif not lowered.endswith("/chat/completions"):
        path = (path or "") + "/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _sanitize_models(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    safe: list[dict[str, Any]] = []
    for row in rows[:200]:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("id", "")).strip()
        if not model_id or len(model_id) > 200 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model_id):
            continue
        safe.append({
            "id": model_id,
            "name": str(row.get("name") or model_id)[:200],
            "context": row.get("context_length") or row.get("context_window"),
            "tool_support": row.get("supports_tools") if "supports_tools" in row else row.get("tool_support"),
            "vision": row.get("supports_vision") if "supports_vision" in row else row.get("vision"),
            "reasoning": row.get("reasoning"),
            "cost": row.get("pricing") or row.get("cost"),
            "status": "AVAILABLE",
        })
    return safe


def sync_models(timeout: float = 20.0) -> dict[str, Any]:
    """Perform one explicit OpenAI-compatible GET /models and persist safe metadata."""
    if not _network_enabled():
        result = _network_blocked()
        log_event("provider", "model_sync_blocked", reason=NETWORK_GATE_ERROR, request_count=0)
        return result
    secret, endpoints = _read_config()
    if not secret:
        result = {"status": "error", "error": "9ROUTER_CREDENTIAL_NOT_FOUND", "request_count": 0}
        log_event("provider", "model_sync_blocked", reason=result["error"])
        return result
    if not endpoints:
        result = {"status": "error", "error": "9ROUTER_ENDPOINT_NOT_FOUND", "request_count": 0}
        log_event("provider", "model_sync_blocked", reason=result["error"])
        return result

    request = urllib.request.Request(
        _models_endpoint(endpoints[0]),
        headers={"Authorization": f"Bearer {secret}", "Accept": "application/json"},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        models = _sanitize_models(payload)
        MODEL_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODEL_CATALOG_PATH.write_text(json.dumps({
            "schema_version": "0.1",
            "provider": "9Router",
            "synced_utc": datetime.now(timezone.utc).isoformat(),
            "models": models,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        result = {"status": "ok", "provider": "9Router", "models": models, "model_count": len(models), "request_count": 1, "latency_ms": latency_ms, "persisted_path": str(MODEL_CATALOG_PATH)}
        _record_provider_state(operation="sync_models", status="CONNECTED", request_count=1, latency_ms=latency_ms, model_count=len(models))
        log_event("provider", "model_sync_finished", status="SUCCESS", model_count=len(models), request_count=1, latency_ms=latency_ms)
        return result
    except urllib.error.HTTPError as exc:
        state = _http_state(int(exc.code))
        result = {"status": "error", "provider_state": state, "error": f"9ROUTER_HTTP_{exc.code}", "request_count": 1}
        _record_provider_state(operation="sync_models", status=state, request_count=1, error=result["error"])
        log_event("provider", "model_sync_finished", status="ERROR", error=result["error"], request_count=1)
        return result
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        state = _error_state(exc)
        result = {"status": "error", "provider_state": state, "error": f"9ROUTER_UNAVAILABLE: {exc.__class__.__name__}", "request_count": 1}
        _record_provider_state(operation="sync_models", status=state, request_count=1, error=result["error"])
        log_event("provider", "model_sync_finished", status="ERROR", error=result["error"], request_count=1)
        return result


def test_chat(model: str, prompt: str = DEFAULT_PROMPT, timeout: float = 20.0) -> dict[str, Any]:
    if not _network_enabled():
        result = _network_blocked()
        log_event("provider", "test_blocked", reason=NETWORK_GATE_ERROR, request_count=0)
        return result
    secret, endpoints = _read_config()
    if not secret:
        result = {"status": "error", "error": "9ROUTER_CREDENTIAL_NOT_FOUND"}
        log_event("provider", "test_blocked", reason=result["error"])
        return result
    if not endpoints:
        result = {"status": "error", "error": "9ROUTER_ENDPOINT_NOT_FOUND"}
        log_event("provider", "test_blocked", reason=result["error"])
        return result
    if not model.strip():
        result = {"status": "error", "error": "MODEL_REQUIRED"}
        log_event("provider", "test_blocked", reason=result["error"])
        return result

    bounded_prompt = prompt.strip()[:200]
    if not bounded_prompt:
        bounded_prompt = DEFAULT_PROMPT
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": bounded_prompt}],
        "max_tokens": 8,
        "temperature": 0,
    }).encode("utf-8")
    request = urllib.request.Request(
        _chat_endpoint(endpoints[0]),
        data=body,
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        message = _response_message(payload)
        answer = _content_text(message.get("content")) if message else ""
        if not message or not answer:
            result = {"status": "error", "provider_state": "MODEL_ERROR", "error": "9ROUTER_INVALID_RESPONSE", "request_count": 1, "latency_ms": latency_ms}
            _record_provider_state(operation="test_chat", status="MODEL_ERROR", model=model, request_count=1, latency_ms=latency_ms, error=result["error"])
            log_event("provider", "test_finished", status="ERROR", model=model, error=result["error"], request_count=1, latency_ms=latency_ms)
            return result
        result = {"status": "ok", "provider": "9Router", "model": model, "answer": answer[:1000], "request_count": 1, "latency_ms": latency_ms}
        result["provider_state"] = "CONNECTED"
        _record_provider_state(operation="test_chat", status="CONNECTED", model=model, request_count=1, latency_ms=latency_ms)
        log_event("provider", "test_finished", status="SUCCESS", model=model, request_count=1, latency_ms=latency_ms)
        return result
    except urllib.error.HTTPError as exc:
        state = _http_state(int(exc.code))
        result = {"status": "error", "provider_state": state, "error": f"9ROUTER_HTTP_{exc.code}", "request_count": 1}
        _record_provider_state(operation="test_chat", status=state, model=model, request_count=1, error=result["error"])
        log_event("provider", "test_finished", status="ERROR", model=model, error=result["error"], request_count=1)
        return result
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        state = _error_state(exc)
        result = {"status": "error", "provider_state": state, "error": f"9ROUTER_UNAVAILABLE: {exc.__class__.__name__}", "request_count": 1}
        _record_provider_state(operation="test_chat", status=state, model=model, request_count=1, error=result["error"])
        log_event("provider", "test_finished", status="ERROR", model=model, error=result["error"], request_count=1)
        return result


def chat_completion(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 512,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Run one bounded OpenAI-compatible chat completion for the agent gateway."""
    if not _network_enabled():
        result = _network_blocked()
        log_event("provider", "agent_completion_blocked", reason=NETWORK_GATE_ERROR, request_count=0)
        return result
    secret, endpoints = _read_config()
    if not secret:
        return {"status": "error", "error": "9ROUTER_CREDENTIAL_NOT_FOUND", "request_count": 0}
    if not endpoints:
        return {"status": "error", "error": "9ROUTER_ENDPOINT_NOT_FOUND", "request_count": 0}
    if not model.strip():
        return {"status": "error", "error": "MODEL_REQUIRED", "request_count": 0}
    bounded_messages = messages[:20]
    body_payload: dict[str, Any] = {
        "model": model,
        "messages": bounded_messages,
        "max_tokens": max(1, min(int(max_tokens), 2048)),
        "temperature": 0,
    }
    if tools:
        body_payload["tools"] = tools[:8]
        body_payload["tool_choice"] = "auto"
    request = urllib.request.Request(
        _chat_endpoint(endpoints[0]),
        data=json.dumps(body_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        message = _response_message(payload)
        if not message:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            result = {"status": "error", "provider_state": "MODEL_ERROR", "error": "9ROUTER_INVALID_RESPONSE", "request_count": 1, "latency_ms": latency_ms}
            _record_provider_state(operation="chat_completion", status="MODEL_ERROR", model=model, request_count=1, latency_ms=latency_ms, error=result["error"])
            log_event("provider", "agent_completion_finished", status="ERROR", model=model, error=result["error"], request_count=1, latency_ms=latency_ms)
            return result
        tool_calls = message.get("tool_calls")
        if not _content_text(message.get("content")) and not (isinstance(tool_calls, list) and tool_calls):
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            result = {"status": "error", "provider_state": "MODEL_ERROR", "error": "9ROUTER_INVALID_RESPONSE", "request_count": 1, "latency_ms": latency_ms}
            _record_provider_state(operation="chat_completion", status="MODEL_ERROR", model=model, request_count=1, latency_ms=latency_ms, error=result["error"])
            log_event("provider", "agent_completion_finished", status="ERROR", model=model, error=result["error"], request_count=1, latency_ms=latency_ms)
            return result
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        result = {
            "status": "ok",
            "provider": "9Router",
            "model": model,
            "message": message,
            "usage": {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens") if key in usage},
            "request_count": 1,
            "latency_ms": latency_ms,
        }
        _record_provider_state(
            operation="chat_completion",
            status="CONNECTED",
            model=model,
            request_count=1,
            latency_ms=latency_ms,
            total_tokens=result["usage"].get("total_tokens"),
        )
        log_event("provider", "agent_completion_finished", status="SUCCESS", model=model, request_count=1, latency_ms=latency_ms, total_tokens=result["usage"].get("total_tokens"))
        return result
    except urllib.error.HTTPError as exc:
        state = _http_state(int(exc.code))
        result = {"status": "error", "provider_state": state, "error": f"9ROUTER_HTTP_{exc.code}", "request_count": 1}
        _record_provider_state(operation="chat_completion", status=state, model=model, request_count=1, error=result["error"])
        log_event("provider", "agent_completion_finished", status="ERROR", model=model, error=result["error"], request_count=1)
        return result
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        state = _error_state(exc)
        result = {"status": "error", "provider_state": state, "error": f"9ROUTER_UNAVAILABLE: {exc.__class__.__name__}", "request_count": 1}
        _record_provider_state(operation="chat_completion", status=state, model=model, request_count=1, error=result["error"])
        log_event("provider", "agent_completion_finished", status="ERROR", model=model, error=result["error"], request_count=1)
        return result
