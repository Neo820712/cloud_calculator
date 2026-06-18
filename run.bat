@echo off
echo ============================================
echo  Cloud Instance Verifier
echo  Acesse: http://localhost:5000
echo  Pressione Ctrl+C para parar
echo ============================================
echo.
start "" http://localhost:5000
python app.py
pause
