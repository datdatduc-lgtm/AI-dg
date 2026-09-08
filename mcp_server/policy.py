"""Local safety and provider-configuration helpers for the AI-DG MCP server.

The functions in this module are intentionally deterministic.  They never
return credential values and they reject writes to D: before any filesystem
operation is attempted.
"""

from __future__ import annotations

import ntpath
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


API_KEY_FILE = Path("E:/api-key.properties")


def drive_of(path: str | Path) -> str:
    normalized = str(path).replace("/", "\\")
    normalized = re.sub(r"^(?:\\\\\?\\|\\\?\\)", "", normalized)
    return ntpath.splitdrive(normalized)[0].upper()


def suffix_of(path: str | Path) -> str:
    """Read a Windows extension reliably even when tests run with POSIX Path semantics."""
    return ntpath.splitext(str(path).rstrip("\\/"))[1].lower()


def system_file_guard(path: str | Path) -> dict[str, Any] | None:
    """Reject mutation of SketchUp's factory/system Ruby file at the tool layer."""
    normalized = ntpath.normcase(ntpath.normpath(str(path).replace("/", "\\")))
    if normalized.endswith("\\tools\\sketchup.rb") and "\\sketchup" in normalized:
        return {
            "status": "error",
            "error": "SKETCHUP_SYSTEM_FILE_WRITE_DENIED",
            "path": str(path),
        }
    return None


def protected_drive(path: str | Path) -> bool:
    return drive_of(path) == "D:"


def write_guard(path: str | Path) -> dict[str, Any] | None:
    system_denied = system_file_guard(path)
    if system_denied:
        return system_denied
    if protected_drive(path):
        return {
            "status": "error",
            "error": "PROTECTED_DRIVE_WRITE_DENIED",
            "path": str(path),
        }
    if suffix_of(path) in {".skp", ".skb"}:
        return {
            "status": "error",
            "error": "SKETCHUP_FILE_WRITE_DENIED",
            "path": str(path),
        }
    return None


def delete_guard(path: str | Path) -> dict[str, Any] | None:
    system_denied = system_file_guard(path)
    if system_denied:
        return system_denied
    suffix = suffix_of(path)
    if suffix in {".skp", ".skb"}:
        return {
            "status": "error",
            "error": "SKETCHUP_FILE_DELETE_DENIED",
            "path": str(path),
        }
    if protected_drive(path):
        return {
            "status": "error",
            "error": "PROTECTED_DRIVE_WRITE_DENIED",
            "path": str(path),
        }
    return None


def _safe_length(value: str) -> int:
    return len(value.strip().strip('"').strip("'"))


def provider_config_summary(path: Path = API_KEY_FILE) -> dict[str, Any]:
    """Return redacted 9Router/provider configuration metadata only."""

    summary: dict[str, Any] = {
        "provider": "9Router",
        "config_path": str(path),
        "config_exists": path.is_file(),
        "candidate_key_names": [],
        "candidate_key_count": 0,
        "endpoint_candidate_count": 0,
        "endpoint_candidates": [],
        "status": "UNCONFIGURED",
    }
    if not path.is_file():
        return summary

    key_names: list[str] = []
    endpoint_count = 0
    endpoints: list[str] = []
    try:
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([^=:#]+?)\s*[:=]\s*(.*)$", line)
            if match:
                name, value = match.groups()
                if re.search(r"9router|orca|router", name, re.IGNORECASE):
                    key_names.append(f"{name.strip()} (length={_safe_length(value)})")
            if re.search(r"https?://", line, re.IGNORECASE) and re.search(r"router|openai|chat|api", line, re.IGNORECASE):
                endpoint_count += 1
                for match in re.findall(r"https?://[^\s\"\\]+", line, flags=re.IGNORECASE):
                    parsed = urlsplit(match.rstrip("'"), allow_fragments=True)
                    if parsed.netloc:
                        endpoints.append(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
    except OSError:
        summary["status"] = "OFFLINE"
        return summary

    summary["candidate_key_names"] = sorted(set(key_names))
    summary["candidate_key_count"] = len(summary["candidate_key_names"])
    summary["endpoint_candidate_count"] = endpoint_count
    summary["endpoint_candidates"] = sorted(set(endpoints))
    summary["status"] = "OFFLINE" if key_names and endpoints else "UNCONFIGURED"
    return summary
