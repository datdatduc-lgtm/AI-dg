# P0 — DIAGNOSE COLD-START

Goal: identify the first failing stage causing:
- SketchUp PID without visible window
- no listener on 9876
- BRIDGE_NOT_READY

Do not fix blindly.

Audit:
```powershell
Get-Process SketchUp -ErrorAction SilentlyContinue |
Select Id,MainWindowTitle,MainWindowHandle,Responding,Path,StartTime

Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" |
Select ProcessId,ParentProcessId,ExecutablePath,CommandLine
```

Inspect:
`E:\AI-DG\OUTPUT\bridge_runtime.log`

Find first missing event:
```text
loader_enter
extension_registered
main_safe_loaded
start_scheduled
start_enter
socket_bind_enter
socket_bind_success
timer_created
server_thread_started
```

Check port:
```powershell
Get-NetTCPConnection -LocalPort 9876 -ErrorAction SilentlyContinue |
Select LocalAddress,LocalPort,State,OwningProcess
```

Classify only with evidence:
- PROCESS_ORPHAN
- SKETCHUP_STARTUP_STUCK
- EXTENSION_NOT_LOADED
- EXTENSION_DISABLED
- BRIDGE_START_EXCEPTION
- PORT_CONFLICT
- STARTUP_TIMING_ISSUE
- UNKNOWN

Never use force-kill if a production `.skp` may be attached.

Output:
- first failing stage
- evidence
- likely root cause
- safe next action
- risk level
