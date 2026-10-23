#!/usr/bin/env bash
# Antigravity Buddy - Stop Script
powershell.exe -NoProfile -NonInteractive -Command "
Stop-Process -Name AntigravityBuddy -Force -ErrorAction SilentlyContinue
\$p = Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%' AND CommandLine LIKE '%buddy_service.py%'\"
if (\$p) { \$p | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force } }
" < /dev/null 2>/dev/null
echo "🛑 已停止 Antigravity 桌面伴侣服务。"
