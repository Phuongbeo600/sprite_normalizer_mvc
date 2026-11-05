@echo off
title Sprite AI Normalizer (MVC)
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Co loi xay ra khi chay chuong trinh.
    pause
)
