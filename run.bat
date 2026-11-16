@echo off
rem ComponentLib 物料入库台启动脚本（pywebview 原生窗口）
cd /d %~dp0
python app\desktop.py
if errorlevel 1 pause
