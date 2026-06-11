@echo off
REM ============================================================
REM  AI Paper Reader - one-click launcher (Windows)
REM ------------------------------------------------------------
REM  Injects the conda env dirs into PATH (same effect as
REM  conda activate) BEFORE launching Streamlit, so that the
REM  bare "mineru" command spawned by pdf_parser.py is always
REM  found. Without this, PDF parsing silently fails per paper.
REM
REM  Change machines / env: edit CONDA_ENV_DIR below only.
REM  Usage: double-click this file, or run  .\start.bat
REM ============================================================
setlocal
cd /d "%~dp0"

REM ===== machine-specific: point to your conda env dir ========
set "CONDA_ENV_DIR=D:\miniconda3\envs\mineru_new"
REM ============================================================

set "PATH=%CONDA_ENV_DIR%;%CONDA_ENV_DIR%\Scripts;%CONDA_ENV_DIR%\Library\bin;%PATH%"

REM self-check 1: mineru must be resolvable (else parsing fails)
where mineru >nul 2>nul
if errorlevel 1 (
  echo [WARN] mineru not found. Check CONDA_ENV_DIR: %CONDA_ENV_DIR%
  echo.
)

REM self-check 2: DEEPSEEK_API_KEY must be set (else summary fails)
if "%DEEPSEEK_API_KEY%"=="" (
  echo [WARN] DEEPSEEK_API_KEY not set - summarization will fail.
  echo        CMD:         set DEEPSEEK_API_KEY=your_key
  echo        PowerShell:  $env:DEEPSEEK_API_KEY="your_key"
  echo.
)

echo Starting Streamlit (Ctrl+C to quit)...
"%CONDA_ENV_DIR%\python.exe" -m streamlit run app.py

endlocal
