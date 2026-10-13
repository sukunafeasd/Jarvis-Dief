@echo off
cd /d "%~dp0"
where pyw >nul 2>&1
if not errorlevel 1 (
    start "" pyw -3 "%~dp0launch.py"
    exit /b
)
where py >nul 2>&1
if not errorlevel 1 (
    start "" py -3 "%~dp0launch.py"
    exit /b
)
where python >nul 2>&1
if not errorlevel 1 (
    start "" python "%~dp0launch.py"
    exit /b
)
echo Instale Python 3.12 com o Python Launcher e tente novamente.
pause
