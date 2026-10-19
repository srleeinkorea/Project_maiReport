@echo off
chcp 65001 >nul
title SharePoint 식이 엑셀 반영
cd /d "%~dp0"
echo.
echo [1/2] 미리보기 - 아무것도 바꾸지 않고 바뀔 곳만 보여 줍니다
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sharepoint-live-sync.ps1"
if errorlevel 2 goto end
echo.
choice /c YNP /n /m "웹에 반영할까요? [Y] 반영  [N] 그만  [P] 웹에서만 바뀐 곳을 로컬로 가져오기 : "
if errorlevel 3 goto pull
if errorlevel 2 goto end
echo.
echo [2/2] 반영 중...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sharepoint-live-sync.ps1" -Apply
goto end
:pull
echo.
echo [2/2] 웹에서만 바뀐 곳을 로컬로 가져오는 중...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sharepoint-live-sync.ps1" -Pull
:end
echo.
pause
