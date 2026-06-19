@echo off
echo ============================================
echo  Cloud Instance Verifier - Instalacao
echo ============================================
echo.

echo [1/2] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: Python nao foi encontrado no PATH.
    echo Instale o Python 3.10+ e marque "Add Python to PATH".
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

echo.
echo [2/2] Instalando dependencias Python...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERRO ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Instalacao concluida!
echo  Execute run.bat para iniciar o servidor.
echo ============================================
pause
