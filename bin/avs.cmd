@echo off
set "ROOT=%~dp0.."
set "PYTHONPATH=%ROOT%\lib;%PYTHONPATH%"
set PYTHONIOENCODING=utf-8
python -m avs.cli %*
