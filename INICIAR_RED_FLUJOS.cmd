@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0iniciar_red_flujos.pyw"
    exit /b
)
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 "%~dp0iniciar_red_flujos.pyw"
    exit /b
)
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0iniciar_red_flujos.pyw"
    exit /b
)
echo Se requiere Python 3.10 o superior para abrir el proyecto.
pause
