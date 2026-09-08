"""Offline contract checks for the persistent Agent Host.

These tests use a fake JSON-RPC child only to verify the host boundary. They do
not pretend that the fake is Codex or Cline and never contact a model service.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from agent_host.host import AgentHost, RpcFailure


class FakeRuntime:
    def __init__(self, backend: str):
        self.backend = backend
        self.pid = 4242 if backend == "codex" else 4343
        self.alive = True
        self.requests: list[tuple[str, dict]] = []
        self.responses: list[tuple[object, object, object]] = []
        self._resume_count = 0
        self.fail_resume = False

    async def request(self, method: str, params: dict | None = None, timeout: float = 0) -> dict:
        params = params or {}
        self.requests.append((method, params))
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}}
        if method == "thread/resume":
            self._resume_count += 1
            if self.fail_resume:
                raise RpcFailure("THREAD_NOT_FOUND", "thread không tồn tại")
            return {"thread": {"id": "thread-1"}}
        if method == "session/new":
            return {"sessionId": "session-1", "modes": {"currentModeId": "plan"}}
        if method == "session/load":
            return {"sessionId": "session-1"}
        if method == "turn/start":
            return {"turn": {"id": "turn-1"}}
        if method == "session/prompt":
            return {"stopReason": "end_turn"}
        if method in {"turn/interrupt", "session/cancel"}:
            return {"ok": True}
        if method == "model/list":
            return {"data": []}
        return {}

    async def respond(self, request_id: object, result: object = None, error: object = None) -> None:
        self.responses.append((request_id, result, error))


class AgentHostContractTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ai-dg-agent-host-test-")
        self.host = AgentHost(Path(self.temp.name), auto_install_cline=False)
        self.codex = FakeRuntime("codex")
        self.cline = FakeRuntime("cline")
        self.host.runtimes = {"codex": self.codex, "cline": self.cline}  # type: ignore[assignment]
        self.emitted: list[dict] = []

        async def capture(message: dict) -> None:
            self.emitted.append(message)

        self.host.emit = capture  # type: ignore[method-assign]

    async def asyncTearDown(self) -> None:
        self.temp.cleanup()

    async def test_codex_thread_mapping_is_persistent(self) -> None:
        first = await self.host.open_session("codex", "doc-1", Path(self.temp.name))
        second = await self.host.open_session("codex", "doc-1", Path(self.temp.name), force_resume=True)

        self.assertEqual(first["thread_id"], "thread-1")
        self.assertEqual(second["thread_id"], "thread-1")
        self.assertEqual(self.codex._resume_count, 1)
        mapping = json.loads(self.host.mapping_path.read_text(encoding="utf-8"))
        self.assertEqual(mapping["schema_version"], 1)
        self.assertEqual(mapping["documents"]["doc-1"]["codex"]["thread_id"], "thread-1")
        self.assertNotIn("messages", mapping["documents"]["doc-1"]["codex"])

    async def test_cline_session_mapping_uses_load(self) -> None:
        first = await self.host.open_session("cline", "doc-2", Path(self.temp.name))
        second = await self.host.open_session("cline", "doc-2", Path(self.temp.name), force_resume=True)

        self.assertEqual(first["session_id"], "session-1")
        self.assertEqual(second["session_id"], "session-1")
        self.assertIn(("session/load", {"sessionId": "session-1", "cwd": self.temp.name, "mcpServers": self.host.acp_mcp_servers()}), self.cline.requests)

    async def test_turn_and_approval_stay_on_native_boundary(self) -> None:
        await self.host.handle({
            "id": "turn-req",
            "method": "turn/start",
            "backend": "codex",
            "document_key": "doc-3",
            "cwd": self.temp.name,
            "text": "read selection",
        })
        self.assertIn("turn/start", [method for method, _params in self.codex.requests])
        self.assertEqual(self.host.active_turns["codex"], "turn-1")

        self.host.pending_child_requests["cline:perm-1"] = ("cline", "perm-1")
        self.host.pending_request_details["cline:perm-1"] = {"method": "session/request_permission", "params": {"options": [{"kind": "allow_once", "optionId": "allow-one"}]}}
        await self.host.handle({
            "id": "approval-req",
            "method": "approval/respond",
            "backend": "cline",
            "data": {
                "request_id": "perm-1",
                "method": "request_permission",
                "approved": True,
            },
        })
        self.assertEqual(self.cline.responses[-1], ("perm-1", {"outcome": {"outcome": "selected", "optionId": "allow-one"}}, None))

    async def test_stale_document_mapping_is_not_reused_for_new_cwd(self) -> None:
        await self.host.open_session("codex", "doc-4", Path(self.temp.name))
        other = Path(self.temp.name) / "other"
        other.mkdir()
        await self.host.open_session("codex", "doc-4", other)
        self.assertEqual([method for method, _params in self.codex.requests].count("thread/start"), 2)

    async def test_resume_failure_preserves_mapping_and_reports_real_error(self) -> None:
        await self.host.open_session("codex", "doc-5", Path(self.temp.name))
        self.codex.fail_resume = True
        with self.assertRaises(RpcFailure) as raised:
            await self.host.open_session("codex", "doc-5", Path(self.temp.name), force_resume=True)
        self.assertEqual(raised.exception.code, "SESSION_RESUME_FAILED")
        mapping = json.loads(self.host.mapping_path.read_text(encoding="utf-8"))
        self.assertEqual(mapping["documents"]["doc-5"]["codex"]["thread_id"], "thread-1")
        self.assertTrue(any(event.get("event") == "session/resume_failed" for event in self.emitted))


if __name__ == "__main__":
    unittest.main()
