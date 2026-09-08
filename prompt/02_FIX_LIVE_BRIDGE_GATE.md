# P0 — FIX LIVE BRIDGE GATE

Required final state:
```text
1 visible SketchUp window
→ viewport normal
→ axes visible
→ 127.0.0.1:9876 LISTENING
→ sketchup_health PASS
→ sketchup_ping PASS
```

Preserve architecture:
```text
safe delayed start
→ background socket thread
→ non-blocking UI timer
→ SketchUp API only on UI thread
```

Do not regress to blocking `gets/read/accept` in UI timer.

Smoke test:
1. viewport gray
2. axes
3. orbit/zoom/select
4. port 9876
5. owner PID = visible SketchUp PID
6. health
7. ping
8. 5 repeated pings
9. partial socket request
10. reconnect
11. no duplicate timer/thread/listener

If AI-DG OFF passes but ON fails, bisect AI-DG.
If OFF also fails, stop changing bridge blindly.

Do not proceed to provider/live agent until this gate passes.
