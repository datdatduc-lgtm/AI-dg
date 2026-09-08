from __future__ import annotations

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
for path in (ROOT_DIR / "OUTPUT" / "mcp_deps", ROOT_DIR, SERVER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from instance_router import RouterFailure, SketchUpInstanceRouter  # noqa: E402
import server  # noqa: E402


class InstanceRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ai-dg-router-")
        self.root = Path(self.temp.name)
        self.registry = self.root / "OUTPUT" / "runtime" / "sketchup-instances"
        self.registry.mkdir(parents=True)
        self.router = SketchUpInstanceRouter(self.root, heartbeat_timeout=3.0)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_instance(
        self,
        instance_id: str,
        *,
        pid: int,
        port: int,
        boot_id: str,
        age: float = 0.0,
        model: str = "Test",
    ) -> None:
        payload = {
            "instance_id": instance_id,
            "pid": pid,
            "boot_id": boot_id,
            "host": "127.0.0.1",
            "port": port,
            "sketchup_version": "23.1.340",
            "model_title": model,
            "model_path": "",
            "bridge_generation": 1,
            "write_mode": "read_only",
            "last_seen": "test",
            "last_seen_epoch": time.time() - age,
        }
        (self.registry / f"{instance_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_multiple_instances_require_selection(self) -> None:
        self.write_instance("su-100-a1b2c3d4", pid=100, port=49100, boot_id="a")
        self.write_instance("su-200-b1c2d3e4", pid=200, port=49200, boot_id="b")
        with self.assertRaises(RouterFailure) as raised:
            self.router.resolve()
        self.assertEqual(raised.exception.code, "TARGET_REQUIRED")
        self.assertEqual(raised.exception.detail["reason"], "MULTIPLE_SKETCHUP_INSTANCES")

    def test_write_requires_explicit_target_even_with_one_instance(self) -> None:
        self.write_instance("su-100-a1b2c3d4", pid=100, port=49100, boot_id="a")
        self.assertEqual(self.router.resolve()["instance_id"], "su-100-a1b2c3d4")
        self.assertEqual(self.router.selected_instance_id, "su-100-a1b2c3d4")
        self.router.clear()
        with self.assertRaises(RouterFailure) as raised:
            self.router.resolve(require_explicit=True)
        self.assertEqual(raised.exception.code, "TARGET_REQUIRED")

    def test_offline_target_does_not_fallback_to_reused_pid(self) -> None:
        old_id = "su-100-a1b2c3d4"
        self.write_instance(old_id, pid=100, port=49100, boot_id="old", age=10.0)
        self.write_instance("su-100-b1c2d3e4", pid=100, port=49200, boot_id="new")
        self.router.selected_instance_id = old_id
        with self.assertRaises(RouterFailure) as raised:
            self.router.resolve()
        self.assertEqual(raised.exception.code, "TARGET_OFFLINE")
        self.assertEqual(self.router.selected_instance_id, old_id)

    def test_selected_request_reaches_only_exact_endpoint(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        instance_id = "su-300-c1d2e3f4"
        self.write_instance(instance_id, pid=300, port=port, boot_id="boot-c", model="TARGET_A")
        self.router.select(instance_id)
        received: list[dict] = []

        def bridge() -> None:
            connection, _ = listener.accept()
            with connection:
                line = b""
                while b"\n" not in line:
                    line += connection.recv(4096)
                request = json.loads(line.split(b"\n", 1)[0])
                received.append(request)
                connection.sendall(
                    (json.dumps({"status": "ok", "data": {"marker": "TARGET_A"}, "target": request["target"]}) + "\n").encode("utf-8")
                )
            listener.close()

        thread = threading.Thread(target=bridge, daemon=True)
        thread.start()
        previous = server.INSTANCE_ROUTER
        server.INSTANCE_ROUTER = self.router
        try:
            result = server.send_sketchup_cmd("get_selection", timeout=2.0)
        finally:
            server.INSTANCE_ROUTER = previous
        thread.join(2.0)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["target"]["instance_id"], instance_id)
        self.assertEqual(received[0]["target"]["boot_id"], "boot-c")
        self.assertEqual(received[0]["target"]["port"], port)

    def test_bridge_response_with_wrong_identity_is_rejected(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        instance_id = "su-400-d1e2f3a4"
        self.write_instance(instance_id, pid=400, port=port, boot_id="boot-d")
        self.router.select(instance_id)

        def bridge() -> None:
            connection, _ = listener.accept()
            with connection:
                line = b""
                while b"\n" not in line:
                    line += connection.recv(4096)
                request = json.loads(line.split(b"\n", 1)[0])
                wrong_target = dict(request["target"])
                wrong_target["boot_id"] = "different-boot"
                connection.sendall((json.dumps({"status": "ok", "target": wrong_target}) + "\n").encode("utf-8"))
            listener.close()

        thread = threading.Thread(target=bridge, daemon=True)
        thread.start()
        previous = server.INSTANCE_ROUTER
        server.INSTANCE_ROUTER = self.router
        try:
            result = server.send_sketchup_cmd("get_selection", timeout=2.0)
        finally:
            server.INSTANCE_ROUTER = previous
        thread.join(2.0)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "TARGET_IDENTITY_MISMATCH")
        self.assertEqual(self.router.selected_instance_id, instance_id)


if __name__ == "__main__":
    unittest.main()
