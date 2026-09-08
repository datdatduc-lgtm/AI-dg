"""Local safety helpers for the AI-DG MCP server.

The functions in this module are intentionally deterministic.  They never
return credential values and they reject writes to D: before any filesystem
operation is attempted.
"""

from __future__ import annotations

import ntpath
import re
from typing import Any


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
