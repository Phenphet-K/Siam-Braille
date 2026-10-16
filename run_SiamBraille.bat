@echo off
chcp 65001 > nul
title SiamBraille 1.0
if exist "%~dp0SiamBraille.exe" (
    start "" "%~dp0SiamBraille.exe"
) else if exist "%~dp0TBTW3.exe" (
    start "" "%~dp0TBTW3.exe"
) else (
    start "" "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\pythonw.exe" "%~dp0tbtw_app.py"
)
exit

