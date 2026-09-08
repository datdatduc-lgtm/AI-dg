"""Opt-in live runtime probe; no synthetic responses or write approvals."""
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_host.host import AgentHost


async def main():
    host = AgentHost(Path(__file__).resolve().parents[1], auto_install_cline=False)
    responses, events = {}, []

    async def capture(message):
        if message.get("id"):
            responses[message["id"]] = message
        events.append(message)
        name = message.get("event")
        if name == "server/request":
            data = message["data"]
            print(json.dumps({"request": data["method"], "backend": message["backend"]}), flush=True)
            await host.handle({"id": "deny", "method": "approval/respond", "backend": message["backend"], "data": {"request_id": data["request_id"], "approved": False}})
        if name in {"runtime/exited", "error"}:
            print(json.dumps(message, ensure_ascii=False), flush=True)

    host.emit = capture
    results = []
    try:
        for backend in ("codex", "cline"):
            doc = "native-smoke-" + uuid.uuid4().hex
            base = {"backend": backend, "document_key": doc, "cwd": str(host.root)}
            print(backend + ": opening", flush=True)
            await host.handle({**base, "id": "open", "method": "session/open"})
            results.append({"backend": backend, "open": responses.get("open")})
            if responses.get("open", {}).get("status") != "ok":
                continue
            print(backend + ": prompt", flush=True)
            await asyncio.wait_for(host.handle({**base, "id": "turn", "method": "turn/start", "text": "Reply OK. Do not call tools, read files, or modify anything."}), 60)
            if backend == "codex":
                for _ in range(60):
                    if backend not in host.active_turns:
                        break
                    await asyncio.sleep(1)
            results[-1]["turn"] = responses.get("turn")
            if backend in host.active_turns:
                await host.handle({**base, "id": "cancel", "method": "turn/cancel"})
                results[-1]["cancel"] = responses.get("cancel")
            await asyncio.wait_for(host.handle({**base, "id": "second", "method": "turn/start", "text": "Reply OK again. Do not use tools."}), 60)
            if backend == "codex":
                for _ in range(60):
                    if backend not in host.active_turns:
                        break
                    await asyncio.sleep(1)
            second = responses.get("second", {})
            original = responses["open"]["data"]
            key = "thread_id" if backend == "codex" else "session_id"
            assert second.get("status") == "ok", second
            assert second["data"][key] == original[key]
            assert second["data"]["runtime_pid"] == original["runtime_pid"]
            results[-1]["two_turns_same_runtime_and_session"] = True
            await host.handle({**base, "id": "resume", "method": "session/resume"})
            results[-1]["resume"] = responses.get("resume")
    finally:
        await host.shutdown()
    for result in results:
        for name in ("open", "turn", "resume", "cancel"):
            entry = result.get(name)
            if entry and isinstance(entry.get("data"), dict):
                entry["data"].pop("models", None)
                entry["data"].pop("modes", None)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
