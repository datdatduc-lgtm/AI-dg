#!/usr/bin/env python3
"""Portable stdio launcher for AI-DG MCP.

The launcher keeps client configuration independent from whichever Python
installation happens to own the `mcp` package.  It only prepends the local
workspace and its bundled dependency directory to ``sys.path`` and then runs
the MCP server; it does not spawn a shell or access provider credentials.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEPENDENCY_DIR = ROOT_DIR / "OUTPUT" / "mcp_deps"
SERVER_DIR = ROOT_DIR / "mcp_server"

for path in (str(DEPENDENCY_DIR), str(ROOT_DIR), str(SERVER_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

runpy.run_path(str(SERVER_DIR / "server.py"), run_name="__main__")
