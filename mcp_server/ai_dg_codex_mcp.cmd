@echo off
setlocal

if not "%AI_DG_PYTHON%"=="" if exist "%AI_DG_PYTHON%" goto run_configured
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  set "AI_DG_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  goto run_configured
)
if exist "%~dp0..\OUTPUT\runtime\python.exe" (
  set "AI_DG_PYTHON=%~dp0..\OUTPUT\runtime\python.exe"
  goto run_configured
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  set "AI_DG_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  goto run_configured
)

py -3.12 "%~dp0launcher.py"
exit /b %ERRORLEVEL%

:run_configured
"%AI_DG_PYTHON%" "%~dp0launcher.py"
exit /b %ERRORLEVEL%
