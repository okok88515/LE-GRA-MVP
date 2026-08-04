@echo off
setlocal
set "RUNTIME_PYTHON=C:\Users\Weber\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
"%RUNTIME_PYTHON%" "%~dp0le_gra_mvp.py" %*
