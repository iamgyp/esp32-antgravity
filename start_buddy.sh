#!/usr/bin/env bash
# Antigravity Buddy - Start Script
/home/iamgyp/claude/esp32/stop_buddy.sh > /dev/null 2>&1
powershell.exe -NoProfile -NonInteractive -Command "Start-Process 'C:\Users\iamgyp\AppData\Local\esp32_buddy\AntigravityBuddy.exe'" < /dev/null 2>/dev/null
echo "✨ Antigravity 桌面伴侣已启动！"
