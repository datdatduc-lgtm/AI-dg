"""Golden VN-1 adapter: validate the real PDF, then run normalized expected facts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pipeline.stages.reconstruction_v2 import run_reconstruction_v2


def run(source_pdf: Path, fixture_json: Path, output_root: Path):
    payload = json.loads(fixture_json.read_text(encoding="utf-8"))
    digest = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    if digest.lower() != str(payload.get("source_sha256", "")).lower():
        raise ValueError("VN1_SOURCE_HASH_MISMATCH")
    return run_reconstruction_v2(payload, output_root, "vn1-golden-v2")
