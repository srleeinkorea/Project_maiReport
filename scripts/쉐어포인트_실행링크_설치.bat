@echo off
chcp 65001 >nul
title SharePoint 반영 실행 링크 설치
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-sync-link.ps1"
echo.
pause
