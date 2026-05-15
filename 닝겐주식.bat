@echo off
chcp 65001 >nul
echo.
echo   닝겐주식 대시보드 시작 중...
echo.

cd /d "%~dp0"

:: 기존 서버 정리 (5502 포트 사용 중인 프로세스 종료)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5502.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: 브라우저 2초 후 자동 오픈
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5502"

:: 서버 실행
python server.py

pause
