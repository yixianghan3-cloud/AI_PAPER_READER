@echo off
REM ============================================================
REM  AI Paper Reader - one-click launcher (Windows)
REM ------------------------------------------------------------
REM  Injects the conda env dirs into PATH (same effect as
REM  conda activate) BEFORE launching Streamlit, so the bare
REM  "mineru" command spawned by pdf_parser.py is always found.
REM  Change machines / env: edit CONDA_ENV_DIR below only.
REM ============================================================
setlocal
cd /d "%~dp0"

REM ===== machine-specific: point to your conda env dir ========
set "CONDA_ENV_DIR=D:\miniconda3\envs\mineru_new"
REM ============================================================

set "PATH=%CONDA_ENV_DIR%;%CONDA_ENV_DIR%\Scripts;%CONDA_ENV_DIR%\Library\bin;%PATH%"

REM Remove broken SSL_CERT_FILE: conda sets it to a non-existent
REM cacert.pem; MinerU 3.1 mineru-api (httpx) reads it and crashes
REM with FileNotFoundError. Clearing it here cleans the whole tree.
set "SSL_CERT_FILE="

REM ===== search enhancement: Chinese/NL query rewrite + OpenAlex =====
REM   Set to 0 to fall back to plain arXiv (English keywords only).
set "USE_QUERY_REWRITE=1"
set "USE_OPENALEX=1"
set "OPENALEX_MAILTO=yixianghan3@gmail.com"

REM self-check 1: mineru must be resolvable (else parsing fails)
where mineru >nul 2>nul
if errorlevel 1 (
  echo [WARN] mineru not found. Check CONDA_ENV_DIR: %CONDA_ENV_DIR%
  echo.
)

REM self-check 2: DEEPSEEK_API_KEY must be set (summary + rewrite need it)
if "%DEEPSEEK_API_KEY%"=="" (
  echo [WARN] DEEPSEEK_API_KEY not set - summarization and query rewrite will fail.
  echo        PowerShell:  $env:DEEPSEEK_API_KEY="your_key"
  echo.
)

echo Starting Streamlit (Ctrl+C to quit)...
"%CONDA_ENV_DIR%\python.exe" -m streamlit run app.py

endlocal
