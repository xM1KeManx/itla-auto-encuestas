@echo off
title ITLA - Auto Encuestas
cd /d "%~dp0"

cls
echo.
echo  ================================================
echo   ITLA - Auto Completar Encuestas
echo   Calificacion automatica con nota 5
echo  ================================================
echo.

:: ── Verificar si el script .py existe ─────────────────────────────────────
if not exist "%~dp0itla_encuestas.py" (
    echo  [X] No se encontro itla_encuestas.py
    echo      Pon ambos archivos en la misma carpeta.
    echo.
    pause
    exit /b 1
)

:: ── Buscar Python en PATH ──────────────────────────────────────────────────
set PYTHON=
where python >nul 2>&1 && set PYTHON=python
if not defined PYTHON where python3 >nul 2>&1 && set PYTHON=python3

:: ── Buscar Python en rutas comunes ────────────────────────────────────────
if not defined PYTHON (
    for %%V in (313 312 311 310 39 38) do (
        if not defined PYTHON (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                set PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe
            )
        )
    )
)
if not defined PYTHON (
    for %%V in (313 312 311 310 39 38) do (
        if not defined PYTHON (
            if exist "C:\Python%%V\python.exe" set PYTHON=C:\Python%%V\python.exe
        )
    )
)

:: ── Si no hay Python, descargarlo e instalarlo silenciosamente ─────────────
if not defined PYTHON (
    echo  [!] Python no encontrado. Instalando automaticamente...
    echo      Esto puede tardar 1-2 minutos, por favor espera.
    echo.

    :: Verificar conexion a internet
    ping -n 1 8.8.8.8 >nul 2>&1
    if errorlevel 1 (
        echo  [X] Sin conexion a internet.
        echo      Conéctate a internet y vuelve a ejecutar.
        echo.
        pause
        exit /b 1
    )

    set PY_INSTALLER=%TEMP%\python_installer.exe
    set PY_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe

    :: Descargar instalador con PowerShell
    echo  [*] Descargando Python 3.12...
    powershell -NoProfile -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%' -UseBasicParsing }" >nul 2>&1

    if not exist "%PY_INSTALLER%" (
        echo  [X] Error al descargar Python.
        echo      Intenta descargar manualmente desde:
        echo      https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )

    :: Instalar silenciosamente para el usuario actual (no requiere admin)
    echo  [*] Instalando Python silenciosamente...
    "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1

    :: Esperar que termine
    timeout /t 5 /nobreak >nul

    :: Limpiar instalador
    del "%PY_INSTALLER%" >nul 2>&1

    :: Recargar PATH para esta sesion
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USERPATH=%%B"
    for %%V in (313 312 311 310 39) do (
        if not defined PYTHON (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                set PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe
            )
        )
    )

    if not defined PYTHON (
        echo  [X] La instalacion de Python no se completó correctamente.
        echo      Por favor instala Python manualmente desde:
        echo      https://www.python.org/downloads/
        echo      y marca "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )

    echo  [OK] Python instalado correctamente.
    echo.
)

echo  [OK] Python listo: %PYTHON%
echo.

:: ── Instalar dependencias si faltan ───────────────────────────────────────
echo  [*] Verificando dependencias...
"%PYTHON%" -c "import selenium" >nul 2>&1
if errorlevel 1 (
    echo  [*] Instalando selenium...
    "%PYTHON%" -m pip install selenium --quiet
)
"%PYTHON%" -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo  [*] Instalando requests...
    "%PYTHON%" -m pip install requests --quiet
)
echo  [OK] Dependencias listas.
echo.
echo  ================================================
echo.

:: ── Ejecutar el script ─────────────────────────────────────────────────────
"%PYTHON%" "%~dp0itla_encuestas.py"

echo.
echo  ================================================
echo  Presiona cualquier tecla para cerrar...
pause >nul
