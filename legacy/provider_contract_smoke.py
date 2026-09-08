# Archived migration reference; not imported by the production runtime.
#!/usr/bin/env python3
"""Local contract test for the 9Router adapter; no external network is used."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "OUTPUT" / "mcp_deps"))
sys.path.insert(0, str(ROOT_DIR / "mcp_server"))

import provider  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    observed_path = ""
    observed_post_path = ""
    auth_seen = False
    post_count = 0

    def do_GET(self):  # noqa: N802
        type(self).observed_path = self.path
        type(self).auth_seen = bool(self.headers.get("Authorization"))
        payload = {"data": [
            {"id": "9router/test-model", "name": "Contract model", "context_length": 8192, "supports_tools": True, "supports_vision": False},
            {"id": "bad model id", "name": "Must be filtered"},
        ]}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        type(self).observed_post_path = self.path
        type(self).post_count += 1
        type(self).auth_seen = type(self).auth_seen and bool(self.headers.get("Authorization"))
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.dumps({
            "choices": [{"message": {"role": "assistant", "content": "OK"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def main() -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="ai-dg-provider-contract-") as temp_dir:
            catalog = Path(temp_dir) / "model-catalog.json"
            state = Path(temp_dir) / "provider-state.json"
            manager_config = Path(temp_dir) / "provider-config.json"
            model_state = Path(temp_dir) / "model-state.json"
            prior_gate = os.environ.get("AI_DG_ALLOW_PROVIDER_TEST")
            os.environ.pop("AI_DG_ALLOW_PROVIDER_TEST", None)
            provider.MODEL_CATALOG_PATH = catalog
            provider.PROVIDER_STATE_PATH = state
            provider.PROVIDER_CONFIG_PATH = manager_config
            provider.MODEL_STATE_PATH = model_state

            class MemoryKeyring:
                secret = None

                @classmethod
                def set_password(cls, _service, _username, value):
                    cls.secret = value

                @classmethod
                def get_password(cls, _service, _username):
                    return cls.secret

                @classmethod
                def delete_password(cls, _service, _username):
                    cls.secret = None

            provider._keyring = lambda: MemoryKeyring
            configured = provider.configure_provider(
                provider_name="Contract Provider",
                provider_type="openai_compatible",
                base_url="http://127.0.0.1:12345/v1",
                model_id="contract/model",
                api_key="synthetic-secret-not-real",
                enabled=True,
            )
            metadata_text = manager_config.read_text(encoding="utf-8") if manager_config.is_file() else ""
            manager_status = provider.status()
            disconnected = provider.disconnect_provider()
            disconnected_status = provider.status()
            config_ok = (
                configured.get("status") == "ok"
                and manager_status.get("provider") == "Contract Provider"
                and manager_status.get("credential_present") is True
                and "synthetic-secret-not-real" not in metadata_text
                and disconnected.get("status") == "ok"
                and disconnected_status.get("status") == "UNCONFIGURED"
            )
            local_cache = Path(temp_dir) / "9router-model-catalog-raw.json"
            local_cache.write_text(json.dumps({
                "orcarouter": {
                    "orcarouter/fusion": {"c": 1000000, "o": 128000, "i": ["image"], "r": True},
                    "not a valid model id": {"c": 1},
                }
            }), encoding="utf-8")
            provider.LOCAL_9ROUTER_CATALOG_PATHS = (local_cache,)
            local_configured = provider.configure_provider(
                provider_name="Local 9Router",
                provider_type="9router",
                base_url="http://127.0.0.1:12345/v1",
                model_id="",
                api_key="synthetic-secret-not-real",
                enabled=True,
            )
            model_state.write_text(json.dumps({"model": "", "mode": "AUTO"}), encoding="utf-8")
            local_status = provider.model_status()
            local_cache_ok = (
                local_configured.get("status") == "ok"
                and local_status.get("models_source") == "LOCAL_9ROUTER_CACHE"
                and local_status.get("available_models", [{}])[0].get("id") == "orcarouter/fusion"
                and local_status.get("available_models", [{}])[0].get("status") == "LOCAL_CACHE_UNVERIFIED"
            )
            provider._read_config = lambda: ("synthetic-secret-not-real", [f"http://127.0.0.1:{httpd.server_port}/v1/chat/completions"])
            blocked = provider.sync_models(timeout=2.0)
            os.environ["AI_DG_ALLOW_PROVIDER_TEST"] = "1"
            synced = provider.sync_models(timeout=2.0)
            completion = provider.chat_completion(
                model="9router/test-model",
                messages=[{"role": "user", "content": "Trả lời duy nhất: OK"}],
                timeout=2.0,
            )
            response_normalization_ok = (
                provider._content_text([{"type": "text", "text": "Xin "}, {"type": "text", "text": "chào"}]) == "Xin chào"
                and provider._response_message({"choices": [{"message": {"content": "OK"}}]}) == {"content": "OK"}
                and provider._response_message({"choices": []}) is None
            )
            status = provider.model_status()
            telemetry_text = state.read_text(encoding="utf-8") if state.is_file() else ""
            telemetry_safe = (
                "synthetic-secret-not-real" not in telemetry_text
                and not any(key in telemetry_text.lower() for key in ("api_key", "authorization", '"prompt"', '"content"'))
            )
            ok = (
                synced.get("status") == "ok"
                and blocked.get("status") == "blocked"
                and blocked.get("request_count") == 0
                and synced.get("model_count") == 1
                and Handler.observed_path == "/v1/models"
                and Handler.auth_seen
                and completion.get("status") == "ok"
                and completion.get("message", {}).get("content") == "OK"
                and Handler.observed_post_path == "/v1/chat/completions"
                and Handler.post_count == 1
                and status.get("models_source") == "SYNCED_LOCAL"
                and status.get("available_models", [{}])[0].get("id") == "9router/test-model"
                and local_cache_ok
                and telemetry_safe
                and config_ok
                and response_normalization_ok
            )
            report = {
                "status": "PASS" if ok else "FAIL",
                "endpoint_path": Handler.observed_path,
                "auth_header_seen": Handler.auth_seen,
                "chat_endpoint_path": Handler.observed_post_path,
                "chat_request_count": Handler.post_count,
                "chat_status": completion.get("status"),
                "model_count": synced.get("model_count"),
                "models_source": status.get("models_source"),
                "local_cache": "PASS" if local_cache_ok else "FAIL",
                "adapter_network_guard": blocked.get("error"),
                "telemetry_safe": telemetry_safe,
                "provider_manager_config": "PASS" if config_ok else "FAIL",
                "response_normalization": "PASS" if response_normalization_ok else "FAIL",
            }
            if prior_gate is None:
                os.environ.pop("AI_DG_ALLOW_PROVIDER_TEST", None)
            else:
                os.environ["AI_DG_ALLOW_PROVIDER_TEST"] = prior_gate
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
