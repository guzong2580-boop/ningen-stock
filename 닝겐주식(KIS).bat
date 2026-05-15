@echo off
chcp 65001 >nul
echo.
echo   닝겐주식 KIS API 버전 시작 중...
echo.

cd /d "%~dp0"

:: 기존 서버 정리
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5502.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: 브라우저 KIS 버전으로 자동 오픈
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5502/kis.html"

:: 서버 실행
python server.py

pause
