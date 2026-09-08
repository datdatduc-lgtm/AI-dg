"""Fail-closed routing for multiple live SketchUp bridge instances.

Each SketchUp process owns one small heartbeat file.  MCP processes only read
those files and keep their selected target in memory, so one client can never
silently move to a different SketchUp process after its target disappears.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INSTANCE_ID_RE = re.compile(r"^su-[0-9]+-[a-f0-9]{8,32}$", re.IGNORECASE)
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_HEARTBEAT_TIMEOUT = 8.0


@dataclass(frozen=True)
class RouterFailure(Exception):
    code: str
    message: str
    detail: dict[str, Any] | None = None

    def as_result(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "error",
            "error_code": self.code,
            "error": self.message,
        }
        if self.detail:
            result["detail"] = self.detail
        return result


class SketchUpInstanceRouter:
    def __init__(self, root: Path, heartbeat_timeout: float | None = None):
        self.root = root.resolve()
        self.registry_dir = self.root / "OUTPUT" / "runtime" / "sketchup-instances"
        configured_timeout = os.environ.get("AI_DG_INSTANCE_HEARTBEAT_TIMEOUT", "").strip()
        if heartbeat_timeout is None:
            try:
                heartbeat_timeout = float(configured_timeout) if configured_timeout else DEFAULT_HEARTBEAT_TIMEOUT
            except ValueError:
                heartbeat_timeout = DEFAULT_HEARTBEAT_TIMEOUT
        self.heartbeat_timeout = max(2.0, min(float(heartbeat_timeout), 60.0))
        self.selected_instance_id = os.environ.get("AI_DG_SKETCHUP_INSTANCE_ID", "").strip() or None

    @staticmethod
    def public_target(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "instance_id": record.get("instance_id"),
            "pid": record.get("pid"),
            "boot_id": record.get("boot_id"),
            "host": record.get("host"),
            "port": record.get("port"),
            "sketchup_version": record.get("sketchup_version"),
            "model_title": record.get("model_title"),
            "model_path": record.get("model_path"),
            "bridge_generation": record.get("bridge_generation"),
            "write_mode": record.get("write_mode"),
            "last_seen": record.get("last_seen"),
            "status": record.get("status"),
        }

    def _read_record(self, path: Path, now: float) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            return None
        if not isinstance(payload, dict):
            return None
        instance_id = str(payload.get("instance_id", ""))
        host = str(payload.get("host", ""))
        try:
            pid = int(payload.get("pid"))
            port = int(payload.get("port"))
            last_seen_epoch = float(payload.get("last_seen_epoch"))
        except (TypeError, ValueError):
            return None
        if (
            path.stem != instance_id
            or not INSTANCE_ID_RE.fullmatch(instance_id)
            or host not in LOOPBACK_HOSTS
            or pid <= 0
            or not 1 <= port <= 65535
            or last_seen_epoch > now + 30.0
        ):
            return None
        age_seconds = max(0.0, now - last_seen_epoch)
        record = dict(payload)
        record.update(
            {
                "instance_id": instance_id,
                "pid": pid,
                "port": port,
                "last_seen_epoch": last_seen_epoch,
                "age_seconds": round(age_seconds, 3),
                "status": "ONLINE" if age_seconds <= self.heartbeat_timeout else "OFFLINE",
            }
        )
        return record

    def list_instances(self, include_offline: bool = True) -> list[dict[str, Any]]:
        now = time.time()
        rows: list[dict[str, Any]] = []
        try:
            paths = sorted(self.registry_dir.glob("su-*.json"))
        except OSError:
            paths = []
        for path in paths:
            record = self._read_record(path, now)
            if record and (include_offline or record["status"] == "ONLINE"):
                rows.append(record)
        rows.sort(key=lambda row: (row["status"] != "ONLINE", str(row.get("model_title", "")), row["instance_id"]))
        return rows

    def selected(self) -> dict[str, Any] | None:
        if not self.selected_instance_id:
            return None
        return next(
            (row for row in self.list_instances(include_offline=True) if row["instance_id"] == self.selected_instance_id),
            None,
        )

    def select(self, instance_id: str) -> dict[str, Any]:
        requested = str(instance_id).strip()
        record = next(
            (row for row in self.list_instances(include_offline=True) if row["instance_id"] == requested),
            None,
        )
        if not record or record["status"] != "ONLINE":
            # Keep an already-selected missing target sticky.  Losing a target
            # must never cause the next request to fall through to another SU.
            if self.selected_instance_id == requested:
                raise RouterFailure("TARGET_OFFLINE", "SketchUp target is offline", {"instance_id": requested})
            raise RouterFailure("INSTANCE_NOT_ONLINE", "SketchUp instance is not online", {"instance_id": requested})
        self.selected_instance_id = requested
        return record

    def clear(self) -> str | None:
        previous = self.selected_instance_id
        self.selected_instance_id = None
        return previous

    def resolve(self, require_explicit: bool = False) -> dict[str, Any]:
        if self.selected_instance_id:
            record = self.selected()
            if not record or record["status"] != "ONLINE":
                raise RouterFailure(
                    "TARGET_OFFLINE",
                    "Selected SketchUp target is offline; target was not changed",
                    {"instance_id": self.selected_instance_id},
                )
            return record

        online = self.list_instances(include_offline=False)
        if not online:
            raise RouterFailure("NO_SKETCHUP_INSTANCES", "No live SketchUp bridge instance was found")
        if require_explicit:
            raise RouterFailure(
                "TARGET_REQUIRED",
                "Select an exact SketchUp instance before a write request",
                {"online_count": len(online), "instances": [row["instance_id"] for row in online]},
            )
        if len(online) != 1:
            raise RouterFailure(
                "TARGET_REQUIRED",
                "Multiple SketchUp instances are online; select one before continuing",
                {
                    "reason": "MULTIPLE_SKETCHUP_INSTANCES",
                    "online_count": len(online),
                    "instances": [row["instance_id"] for row in online],
                },
            )
        # Auto-routing a unique read target also makes it sticky. If that
        # process dies before the next tool call, resolve() returns
        # TARGET_OFFLINE instead of silently switching to a newcomer.
        self.selected_instance_id = online[0]["instance_id"]
        return online[0]
