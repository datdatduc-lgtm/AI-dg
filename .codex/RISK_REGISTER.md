# AI-DG MCP-SU Risk Register

| Risk | Level | Mitigation | State |
|---|---|---|---|
| Writing or deleting user data on D: | CRITICAL | Guard before filesystem access; read-only analyzer contract | MITIGATED IN CODE |
| Deleting a SketchUp file | CRITICAL | `.skp`/`.skb` delete guard | MITIGATED IN CODE |
| Arbitrary Ruby execution | HIGH | `eval_ruby` Developer Mode only | IMPLEMENTED, VERIFY DEPLOY |
| UI freeze from socket I/O | HIGH | background accept/read + UI queue | VERIFIED |
| Corrupt model from writes | HIGH | SketchUp transaction commit/abort | IMPLEMENTED, VERIFY GUARD |
| Secret leakage | HIGH | redacted provider audit; no raw key in logs/UI | MITIGATED IN CODE |
| Third-party toolbar damage | HIGH | AI-DG owns one toolbar and never enumerates others | VERIFIED BY SOURCE/SCREEN |
| Unbounded agent loop | HIGH | provider-backed gateway max two calls/steps and one read-only tool; no production scripted fallback | IMPLEMENTED |
| Stale in-process Ruby/UI source | MEDIUM | source hash + explicit graceful reload; reloadable tool catalog; open HtmlDialog refresh | MITIGATED IN CURRENT PROCESS — generation 21 |
| Provider credential or endpoint leakage | HIGH | sanitized status/logging; no network test without explicit authorization | MITIGATED IN CODE |
| Client cannot locate MCP dependencies | MEDIUM | portable `mcp_server/launcher.py` and config | MITIGATED |
| External provider sends credential/prompt unexpectedly | CRITICAL | opt-in gate, bounded calls, redacted state, fake-localhost contract | MITIGATED — real 9Router test not run |
| Provider-backed agent escapes read-only scope | HIGH | configured model, read-only system prompt, allow-list, max 2 calls/steps | CONTRACT-TESTED |
| Factory SketchUp system file modified | CRITICAL | Python system-file policy plus Ruby deployment guard and hash check | MITIGATED IN CODE |
| OCR promotes an uncertain scan to geometry | HIGH | local OCR adapter reports status/confidence; OCR candidates remain review-gated | MITIGATED IN CODE — binary not installed |
| Semantic build mutates unsaved model | HIGH | APPROVED + write_enabled + confirm_write; per-item transaction/read-back | MITIGATED IN CODE — no write issued |
| Build/codegen drift between Python, Ruby and MCP | HIGH | Deterministic central Build IR; readable JSON/Python/Ruby representations; controlled executor consumes semantic operations | MITIGATED IN CODE — fixture verified |
| Large MCP schema obscures safe capabilities | MEDIUM | Explicit process-level minimal/drawing/build/full exposure profiles and `ai_dg_list_tools` metadata | MITIGATED IN CODE — 21/77 default profile |
| Fresh SketchUp process has no bridge listener | HIGH | Wait for visible cold-start; do not force-kill/restart; re-run read-only acceptance only when `127.0.0.1:9876` is online | MITIGATED — current PID 48576, acceptance 27/27 PASS |
| Previously exposed provider credential | CRITICAL | Do not print/reuse the value; rotate/revoke before any real provider request; keep network gate off | OPEN — user action required |
| Provider chat has no concrete model | HIGH | local preflight blocks Chat with `MODEL_REQUIRED`; user must sync or enter canonical model ID before real test | OPEN — user action required |
| Chat UI can obscure provider readiness | MEDIUM | provider/model chips, actionable readiness banner, direct Model Manager/quick picks, helper-error guidance, Enter/Shift+Enter semantics and duplicate-send guards | MITIGATED IN CURRENT DEPLOY — generation 21 |
| Codex CLI can make an external turn | HIGH | separate backend, separate explicit network gate, `--ephemeral`, `--sandbox read-only`, bounded 60-second subprocess, sanitized JSONL parsing | IMPLEMENTED — REAL TURN NOT RUN |
| Codex CLI may run without SketchUp tools | HIGH | inject workspace-local AI-DG MCP wrapper per invocation; minimal profile; direct stdio initialize contract | MITIGATED IN CODE — REAL TURN NOT RUN |
| Local 9Router cache can be mistaken for provider verification | MEDIUM | cache is suggestion-only, labeled `LOCAL_CACHE_UNVERIFIED`, no auto-selection; real `/models` sync remains opt-in | MITIGATED IN CODE |
| Conversation context leaks secrets or grows without bound | HIGH | last 6 turns only, 500-character per-message cap, common key/token redaction, last 200 persisted messages, successful-answer persistence only | MITIGATED IN CODE — external prompt not run |
