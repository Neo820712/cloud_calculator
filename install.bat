@echo off
echo ============================================
echo  Cloud Instance Verifier - Instalacao
echo ============================================
echo.

echo [1/2] Instalando dependencias Python...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERRO ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo [2/2] Instalando navegador Chromium para Playwright...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo ERRO ao instalar Chromium.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Instalacao concluida!
echo  Execute run.bat para iniciar o servidor.
echo ============================================
pause
