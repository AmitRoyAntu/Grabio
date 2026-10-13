@echo off
:: start.bat — one-command launcher for Grabio (Windows)
:: Double-click or run from any terminal: start.bat [port]
setlocal enabledelayedexpansion

cd /d "%~dp0"

set PORT=5000
if not "%~1"=="" set PORT=%~1

set VENV=.venv
set PYTHON_VENV=%VENV%\Scripts\python.exe
set PIP_VENV=%VENV%\Scripts\pip.exe

:: ── 1. Find Python 3.9+ ──────────────────────────────────────────────────
set PYTHON=
for %%c in (python3.12 python3.11 python3.10 python3.9 python3 python) do (
  if "!PYTHON!"=="" (
    where %%c >nul 2>&1 && (
      for /f %%v in ('%%c -c "import sys; print(sys.version_info >= (3,9))" 2^>nul') do (
        if "%%v"=="True" set PYTHON=%%c
      )
    )
  )
)
if "!PYTHON!"=="" (
  echo.
  echo [ERROR] Python 3.9 or newer is required.
  echo         Download from https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)
for /f "tokens=*" %%v in ('!PYTHON! --version') do echo [OK] %%v

:: ── 2. Create / reuse venv ───────────────────────────────────────────────
if not exist "%PYTHON_VENV%" (
  echo [->] Creating virtual environment...
  !PYTHON! -m venv "%VENV%"
)

:: Prefer uv if available
where uv >nul 2>&1
if %errorlevel%==0 (
  echo [->] Installing / updating packages (uv^)...
  uv pip install --quiet -r requirements.txt
) else (
  echo [->] Installing / updating packages (pip^)...
  "%PIP_VENV%" install --quiet --upgrade pip
  "%PIP_VENV%" install --quiet -r requirements.txt
)
echo [OK] Packages ready

:: ── 3. Open browser after a short delay ─────────────────────────────────
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:%PORT%"

:: ── 4. Launch ────────────────────────────────────────────────────────────
echo.
echo   Grabio ^-^> http://127.0.0.1:%PORT%
echo   Press Ctrl-C to quit
echo.
"%PYTHON_VENV%" app.py
