"""Static contract for the headless SketchUp extension package."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge_sketchup" / "ai_dg_bridge"


def main() -> int:
    forbidden_files = [
        BRIDGE / "toolbar.rb",
        BRIDGE / "control_center.rb",
        BRIDGE / "agent_host_client.rb",
        BRIDGE / "ui" / "control_center.html",
        BRIDGE / "ui" / "control_center.css",
        BRIDGE / "ui" / "control_center.js",
        BRIDGE / "icons" / "ai_dg_mcp.svg",
    ]
    unexpected = [str(path.relative_to(ROOT)) for path in forbidden_files if path.exists()]
    main_source = (BRIDGE / "main_safe.rb").read_text(encoding="utf-8")
    forbidden_source_tokens = [
        "UI::HtmlDialog",
        "UI::Toolbar",
        "UI.menu(",
        "ControlCenter",
        "AgentHostClient",
        "require_relative 'toolbar'",
    ]
    source_hits = [token for token in forbidden_source_tokens if token in main_source]
    deploy_source = (ROOT / "deploy_bridge.ps1").read_text(encoding="utf-8")
    installer_source = (ROOT / "install_all.py").read_text(encoding="utf-8")
    copied_extras = [
        token
        for token in ("@{ Source = Join-Path $source 'ai_dg_bridge\\toolbar.rb'", "@{ Source = Join-Path $source 'ai_dg_bridge\\control_center.rb'", "@{ Source = Join-Path $PSScriptRoot 'agent_host\\host.py'")
        if token in deploy_source
    ]
    installer_ok = "shutil.copytree(src_dir" not in installer_source and '"main.rb": src_dir / "main_safe.rb"' in installer_source
    ok = not unexpected and not source_hits and not copied_extras and installer_ok
    report = {
        "status": "PASS" if ok else "FAIL",
        "unexpected_plugin_files": unexpected,
        "forbidden_source_tokens": source_hits,
        "forbidden_deploy_entries": copied_extras,
        "headless_installer": installer_ok,
        "deployed_payload": ["ai_dg_bridge.rb", "ai_dg_bridge/main.rb", "ai_dg_bridge/geometry_builder.rb"],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
