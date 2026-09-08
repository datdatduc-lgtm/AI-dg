"""Live acceptance probe for deterministic routing across two SketchUp processes.

The default mode is read-only.  The optional write probe requires two exact
instance IDs, SketchUp write mode, and the native confirmation dialog in each
target.  It verifies isolation by entity counts and undoes every successful
probe before exiting.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
for path in (ROOT_DIR / "OUTPUT" / "mcp_deps", ROOT_DIR, SERVER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import server  # noqa: E402


class AcceptanceFailure(RuntimeError):
    pass


def call_json(function: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    value = json.loads(function(*args, **kwargs))
    if not isinstance(value, dict):
        raise AcceptanceFailure(f"Expected object from {function.__name__}")
    return value


def require_ok(value: dict[str, Any], label: str) -> dict[str, Any]:
    if value.get("status") != "ok":
        raise AcceptanceFailure(f"{label}: {json.dumps(value, ensure_ascii=False)}")
    return value


def select_and_read(instance_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = require_ok(call_json(server.sketchup_select_instance, instance_id), f"select {instance_id}")
    summary = require_ok(call_json(server.sketchup_get_model_summary), f"summary {instance_id}")
    target = summary.get("target") or {}
    if target.get("instance_id") != instance_id:
        raise AcceptanceFailure(f"Target proof mismatch for {instance_id}: {target}")
    return selected["target"], summary


def entity_count(summary: dict[str, Any]) -> int:
    return int((summary.get("data") or {}).get("entities", -1))


def assert_two_exact_online(first_id: str, second_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if first_id == second_id:
        raise AcceptanceFailure("Two distinct instance IDs are required")
    listing = require_ok(call_json(server.sketchup_list_instances), "list instances")
    online = {
        row.get("instance_id"): row
        for row in listing.get("instances", [])
        if row.get("status") == "ONLINE"
    }
    missing = [instance_id for instance_id in (first_id, second_id) if instance_id not in online]
    if missing:
        raise AcceptanceFailure(f"Exact live instances not found: {missing}; online={list(online)}")
    first, second = online[first_id], online[second_id]
    for field in ("instance_id", "boot_id", "port"):
        if first.get(field) == second.get(field):
            raise AcceptanceFailure(f"Instances share {field}: {first.get(field)}")
    return first, second


def verify_fail_closed_with_multiple() -> None:
    require_ok(call_json(server.sketchup_clear_instance), "clear target")
    result = call_json(server.sketchup_get_model_summary)
    if result.get("error_code") != "TARGET_REQUIRED":
        raise AcceptanceFailure(f"Expected TARGET_REQUIRED with two live instances: {result}")


def write_probe(first_id: str, second_id: str) -> None:
    created: list[str] = []
    try:
        for index, (target_id, other_id) in enumerate(((first_id, second_id), (second_id, first_id)), start=1):
            _, target_before = select_and_read(target_id)
            _, other_before = select_and_read(other_id)
            before_target_count = entity_count(target_before)
            before_other_count = entity_count(other_before)

            server.INSTANCE_ROUTER.select(target_id)
            created_result = require_ok(
                call_json(
                    server.sketchup_create_box,
                    111.0,
                    222.0,
                    333.0,
                    f"AI_DG_MULTI_INSTANCE_PROBE_{index}",
                    index * 500.0,
                    0.0,
                    0.0,
                ),
                f"create probe in {target_id}",
            )
            created.append(target_id)
            if not created_result.get("verified"):
                raise AcceptanceFailure(f"Bridge did not verify write in {target_id}: {created_result}")

            _, target_after = select_and_read(target_id)
            _, other_after = select_and_read(other_id)
            if entity_count(target_after) != before_target_count + 1:
                raise AcceptanceFailure(f"Target entity count did not increment in {target_id}")
            if entity_count(other_after) != before_other_count:
                raise AcceptanceFailure(f"Write leaked from {target_id} into {other_id}")
    finally:
        for target_id in reversed(created):
            try:
                server.INSTANCE_ROUTER.select(target_id)
                undo = call_json(server.sketchup_undo, True)
                if undo.get("status") != "ok":
                    print(f"CLEANUP_WARNING {target_id}: {json.dumps(undo, ensure_ascii=False)}", file=sys.stderr)
            except Exception as exc:  # cleanup must continue for the other target
                print(f"CLEANUP_WARNING {target_id}: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first_instance_id")
    parser.add_argument("second_instance_id")
    parser.add_argument("--write-probe", action="store_true")
    args = parser.parse_args()

    started = time.time()
    try:
        first, second = assert_two_exact_online(args.first_instance_id, args.second_instance_id)
        verify_fail_closed_with_multiple()
        first_target, first_summary = select_and_read(args.first_instance_id)
        second_target, second_summary = select_and_read(args.second_instance_id)
        if args.write_probe:
            write_probe(args.first_instance_id, args.second_instance_id)
        result = {
            "status": "PASS",
            "mode": "write-readback-undo" if args.write_probe else "read-only",
            "elapsed_seconds": round(time.time() - started, 3),
            "instances": [
                {"registry": first, "proof": first_target, "entities": entity_count(first_summary)},
                {"registry": second, "proof": second_target, "entities": entity_count(second_summary)},
            ],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except AcceptanceFailure as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
