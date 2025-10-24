@echo off
REM Windows batch file launcher for GNS3 MCP Server
REM This replaces the Unix shell script for Windows compatibility

echo Starting GNS3 MCP Server...

REM Change to script directory
cd /d "%~dp0"

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    echo Installing dependencies...
    call .venv\Scripts\activate
    pip install fastmcp httpx pydantic
)

REM Activate virtual environment and start server
call .venv\Scripts\activate
python server.py

pause