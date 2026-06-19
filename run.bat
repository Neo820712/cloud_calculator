@echo off
echo ============================================
echo  Cloud Instance Verifier
echo  Acesse: http://localhost:5000
echo  Pressione Ctrl+C para parar
echo ============================================
echo.
cd /d "%~dp0"
start "" http://localhost:5000
python src\app.py
pause
