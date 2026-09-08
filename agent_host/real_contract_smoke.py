#!/usr/bin/env python3
"""Live Agent Host contract probe.

This starts the real host and real Codex App Server when available. It never
uses a model fallback and disables automatic Cline installation so the probe
cannot change the machine's npm installation. Cline's absence is reported as
PARTIAL, not as a fake success.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]


async def send(process: asyncio.subprocess.Process, payload: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    await process.stdin.drain()


async def read_until(process: asyncio.subprocess.Process, request_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    assert process.stdout is not None
    while True:
        raw = await asyncio.wait_for(process.stdout.readline(), timeout=45.0)
        if not raw:
            raise RuntimeError("AGENT_HOST_EXITED_BEFORE_RESPONSE")
        message = json.loads(raw.decode("utf-8"))
        print(json.dumps({"progress": message.get("event") or message.get("id"), "status": message.get("status")}), file=sys.stderr, flush=True)
        if isinstance(message, dict) and message.get("type") == "agent/event":
            events.append(message)
            if message.get("event") == "server/request":
                data = message.get("data", {})
                print(json.dumps({"native_request": data.get("method"), "tool_title": data.get("params", {}).get("toolCall", {}).get("title")}), file=sys.stderr, flush=True)
                tool = data.get("params", {}).get("toolCall", {})
                read_selection = str(tool.get("title", "")) == 'ai-dg__sketchup_get_selection: {}'
                await send(process, {"id": "probe-permission-" + str(data.get("request_id")), "method": "approval/respond", "backend": message.get("backend"), "data": {"request_id": data.get("request_id"), "approved": read_selection, "method": data.get("method")}})
        if isinstance(message, dict) and message.get("id") == request_id:
            return message


async def main() -> int:
    env = os.environ.copy()
    env["AI_DG_ROOT"] = str(ROOT_DIR)
    env["PYTHONPATH"] = os.pathsep.join(
        str(path) for path in (ROOT_DIR / "OUTPUT" / "mcp_deps", ROOT_DIR, ROOT_DIR / "mcp_server")
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(ROOT_DIR / "agent_host" / "host.py"),
        "--root",
        str(ROOT_DIR),
        "--no-auto-install-cline",
        cwd=str(ROOT_DIR),
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=1_048_576,
    )
    events: list[dict[str, Any]] = []
    report: dict[str, Any] = {"status": "PASS", "tests": []}
    cleanup_ok = True
    try:
        await send(process, {"id": "host-status", "method": "host/status"})
        status = await read_until(process, "host-status", events)
        status_data = status.get("data", {})
        report["tests"].append({
            "name": "host_status",
            "status": "PASS" if status.get("status") == "ok" and status_data.get("host") == "READY" else "FAIL",
            "codex_available": status_data.get("codex", {}).get("available"),
            "cline_available": status_data.get("cline", {}).get("available"),
        })

        await send(process, {"id": "codex-open", "method": "agent/open", "backend": "codex", "cwd": str(ROOT_DIR)})
        codex = await read_until(process, "codex-open", events)
        codex_ok = codex.get("status") == "ok" and codex.get("data", {}).get("backend") == "codex"
        report["tests"].append({
            "name": "codex_app_server_handshake",
            "status": "PASS" if codex_ok else "FAIL",
            "runtime_pid": codex.get("data", {}).get("pid"),
            "error": codex.get("error"),
            "detail": codex.get("detail"),
            "runtime_ready_event": any(event.get("backend") == "codex" and event.get("event") == "runtime/ready" for event in events),
        })

        session_key = "contract-smoke-" + uuid.uuid4().hex
        await send(process, {"id": "codex-session-open", "method": "session/open", "backend": "codex", "document_key": session_key, "cwd": str(ROOT_DIR)})
        codex_session = await read_until(process, "codex-session-open", events)
        codex_session_data = codex_session.get("data", {})
        codex_session_ok = codex_session.get("status") == "ok" and bool(codex_session_data.get("thread_id"))
        report["tests"].append({
            "name": "codex_session_open",
            "status": "PASS" if codex_session_ok else "FAIL",
            "thread_id": codex_session_data.get("thread_id"),
            "error": codex_session.get("error"),
        })
        await send(process, {"id": "codex-turn", "method": "turn/start", "backend": "codex", "document_key": session_key, "cwd": str(ROOT_DIR), "text": "Call ai-dg sketchup_get_selection once and report its result. Read only. Do not edit files or model."})
        turn = await read_until(process, "codex-turn", events)
        report["tests"].append({"name": "codex_turn_start", "status": "PASS" if turn.get("status") == "ok" else "FAIL", "detail": turn.get("detail")})
        if turn.get("status") == "ok":
            while True:
                try:
                    event = json.loads((await asyncio.wait_for(process.stdout.readline(), 45)).decode())
                except asyncio.TimeoutError:
                    report["tests"].append({"name": "codex_turn_completed", "status": "FAIL", "detail": "NO_EVENT_WITHIN_45_SECONDS"})
                    await send(process, {"id": "cancel-timeout", "method": "turn/cancel", "backend": "codex", "document_key": session_key})
                    await read_until(process, "cancel-timeout", events)
                    break
                print(json.dumps({"progress": event.get("event"), "data": event.get("data") if event.get("event") in {"error", "runtime/exited"} else None}), file=sys.stderr, flush=True)
                events.append(event)
                if event.get("event") == "runtime/exited":
                    report["tests"].append({"name": "codex_turn_completed", "status": "FAIL", "detail": event.get("data")})
                    break
                if event.get("event") == "server/request":
                    params = event["data"].get("params", {})
                    allow = params.get("serverName") == "ai-dg" and params.get("message") == 'Allow the ai-dg MCP server to run tool "sketchup_get_selection"?'
                    await send(process, {"id": "permission", "method": "approval/respond", "backend": "codex", "data": {"request_id": event["data"]["request_id"], "approved": allow}})
                if event.get("event") == "turn/completed":
                    report["tests"].append({"name": "codex_turn_completed", "status": "PASS" if event.get("data", {}).get("turn", {}).get("status") == "completed" else "FAIL", "detail": event.get("data", {}).get("turn", {}).get("error")})
                    break
        await send(process, {"id": "codex-session-resume", "method": "session/resume", "backend": "codex", "document_key": session_key, "cwd": str(ROOT_DIR)})
        codex_resume = await read_until(process, "codex-session-resume", events)
        codex_resume_data = codex_resume.get("data", {})
        codex_resume_ok = codex_resume.get("status") == "ok" and codex_resume_data.get("thread_id") == codex_session_data.get("thread_id")
        report["tests"].append({
            "name": "codex_session_resume_same_thread",
            "status": "PASS" if codex_resume_ok else "FAIL",
            "thread_id": codex_resume_data.get("thread_id"),
            "error": codex_resume.get("error"),
            "detail": codex_resume.get("detail"),
        })

        await send(process, {"id": "cline-open", "method": "agent/open", "backend": "cline", "cwd": str(ROOT_DIR)})
        cline = await read_until(process, "cline-open", events)
        cline_error = cline.get("error")
        cline_ok = cline.get("status") == "ok" or cline_error in {"CLINE_NOT_FOUND", "CLINE_INSTALLING"}
        report["tests"].append({
            "name": "cline_acp_availability_gate",
            "status": "PASS" if cline.get("status") == "ok" else "PARTIAL" if cline_ok else "FAIL",
            "runtime_pid": cline.get("data", {}).get("pid"),
            "error": cline_error,
        })
        if cline.get("status") == "ok":
            await send(process, {"id": "cline-session-open", "method": "session/open", "backend": "cline", "document_key": session_key, "cwd": str(ROOT_DIR)})
            cline_session = await read_until(process, "cline-session-open", events)
            cline_session_data = cline_session.get("data", {})
            cline_session_ok = cline_session.get("status") == "ok" and bool(cline_session_data.get("session_id"))
            report["tests"].append({
                "name": "cline_session_open",
                "status": "PASS" if cline_session_ok else "FAIL",
                "session_id": cline_session_data.get("session_id"),
                "error": cline_session.get("error"),
                "detail": cline_session.get("detail"),
            })
            await send(process, {"id": "cline-turn", "method": "turn/start", "backend": "cline", "document_key": session_key, "cwd": str(ROOT_DIR), "text": "Call ai-dg sketchup_get_selection once and report its result. Read only. Do not edit files or model."})
            cline_turn = await read_until(process, "cline-turn", events)
            report["tests"].append({"name": "cline_turn", "status": "PASS" if cline_turn.get("status") == "ok" else "FAIL", "detail": cline_turn.get("detail")})
            await send(process, {"id": "cline-session-resume", "method": "session/resume", "backend": "cline", "document_key": session_key, "cwd": str(ROOT_DIR)})
            cline_resume = await read_until(process, "cline-session-resume", events)
            cline_resume_data = cline_resume.get("data", {})
            cline_resume_ok = cline_resume.get("status") == "ok" and cline_resume_data.get("session_id") == cline_session_data.get("session_id")
            report["tests"].append({
                "name": "cline_session_resume_same_session",
                "status": "PASS" if cline_resume_ok else "FAIL",
                "session_id": cline_resume_data.get("session_id"),
                "error": cline_resume.get("error"),
                "detail": cline_resume.get("detail"),
            })
    finally:
        try:
            await send(process, {"id": "host-shutdown", "method": "host/shutdown"})
            await read_until(process, "host-shutdown", events)
        except (BrokenPipeError, RuntimeError, asyncio.TimeoutError):
            try:
                process.kill()
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            cleanup_ok = False
            try:
                process.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

    statuses = [test["status"] for test in report["tests"]]
    if "FAIL" in statuses:
        report["status"] = "FAIL"
    elif "PARTIAL" in statuses:
        report["status"] = "PARTIAL"
    stderr_text = ""
    if process.stderr is not None:
        stderr_text = (await process.stderr.read()).decode("utf-8", errors="replace")[-4000:]
    report["events"] = sorted(set(str(event.get("backend")) + ":" + str(event.get("event")) for event in events))
    report["tool_evidence"] = []
    for event in events:
        data = event.get("data", {})
        if event.get("event") == "item/completed":
            item = data.get("item", {})
            if item.get("type") == "mcpToolCall":
                report["tool_evidence"].append({"backend": "codex", "tool": item.get("tool"), "server": item.get("server"), "status": item.get("status"), "result": item.get("result"), "error": item.get("error")})
        if event.get("event") == "session/update":
            update = data.get("update", {})
            if update.get("sessionUpdate") in {"tool_call", "tool_call_update"}:
                report["tool_evidence"].append({"backend": "cline", "title": update.get("title"), "status": update.get("status"), "content": update.get("content")})
    report["cleanup"] = "PASS" if cleanup_ok else "TIMEOUT"
    for backend in ("codex", "cline"):
        success = any(item.get("backend") == backend and item.get("status") == "completed" for item in report["tool_evidence"])
        report["tests"].append({"name": backend + "_native_selection_tool", "status": "PASS" if success else "FAIL"})
        if not success:
            report["status"] = "FAIL"
    if not cleanup_ok:
        report["status"] = "FAIL"
    if stderr_text.strip():
        report["runtime_stderr_tail"] = stderr_text.strip()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
