#!/usr/bin/env python3
"""
Antigravity Desktop Buddy (ESP32-S3)
A modern desktop GUI application with System Tray and BLE synchronizer.
Can run in the foreground with full status display or minimize to the background tray.
"""

import sys
import os
import time
import json
import glob
import asyncio
import threading
import subprocess
import urllib.request
from typing import Optional

from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer, QSize
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QAction, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFrame, QPlainTextEdit,
    QSystemTrayIcon, QMenu, QCheckBox, QSizePolicy
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from bleak import BleakScanner, BleakClient

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

SERVICE_UUID        = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

WSL_BRAIN_DIR = r"\\wsl.localhost\Ubuntu-24.04\home\iamgyp\.gemini\antigravity\brain"
FALLBACK_WSL_DIR = r"\\wsl$\Ubuntu-24.04\home\iamgyp\.gemini\antigravity\brain"

# Determine app directory & asset directory
if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    APP_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BASE_DIR

LOG_FILE = os.path.join(APP_DIR, "buddy_app.log")
QUOTA_FILE = os.path.join(APP_DIR, "quota.json")
WEATHER_FILE = os.path.join(APP_DIR, "weather.json")
ICON_ICO = os.path.join(BASE_DIR, "app_icon.ico")
ICON_PNG = os.path.join(BASE_DIR, "app_icon.png")

def log(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass

def get_brain_dir():
    if os.path.exists(WSL_BRAIN_DIR):
        return WSL_BRAIN_DIR
    if os.path.exists(FALLBACK_WSL_DIR):
        return FALLBACK_WSL_DIR
    return None

def find_latest_transcript():
    bdir = get_brain_dir()
    if not bdir:
        return None
    try:
        pattern = os.path.join(bdir, "*", ".system_generated", "logs", "transcript.jsonl")
        files = glob.glob(pattern)
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception:
        return None

def clean_arg(val):
    if not isinstance(val, str):
        return ""
    return val.strip().strip('"').strip("'")

def load_quota():
    if os.path.exists(QUOTA_FILE):
        try:
            with open(QUOTA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def load_weather():
    if os.path.exists(WEATHER_FILE):
        try:
            with open(WEATHER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

WMO_MAP = {
    0: ("Sunny", "晴", 0),
    1: ("Mainly Clear", "多云", 1),
    2: ("Partly Cloudy", "多云", 1),
    3: ("Overcast", "阴天", 1),
    45: ("Foggy", "雾", 2),
    48: ("Rime Fog", "浓雾", 2),
    51: ("Light Drizzle", "细雨", 3),
    53: ("Drizzle", "小雨", 3),
    55: ("Dense Drizzle", "小雨", 3),
    61: ("Slight Rain", "小雨", 3),
    63: ("Moderate Rain", "中雨", 3),
    65: ("Heavy Rain", "大雨", 3),
    71: ("Light Snow", "小雪", 4),
    73: ("Moderate Snow", "中雪", 4),
    75: ("Heavy Snow", "大雪", 4),
    80: ("Rain Showers", "阵雨", 3),
    81: ("Moderate Showers", "雷雨", 3),
    82: ("Violent Showers", "暴雨", 3),
    95: ("Thunderstorm", "雷暴", 5),
    96: ("Thunder & Hail", "雷雨冰雹", 5),
    99: ("Severe Storm", "强雷暴", 5),
}

def fetch_weather_direct():
    lat, lon = 30.2741, 120.1551
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=Asia%2FShanghai"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Antigravity-Buddy/1.0"})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        cur = data.get("current", {})
        daily = data.get("daily", {})
        temp_c = int(round(cur.get("temperature_2m", 20.0)))
        hum_pct = int(round(cur.get("relative_humidity_2m", 60.0)))
        w_code = int(cur.get("weather_code", 0))
        min_c = int(round(daily.get("temperature_2m_min", [15])[0]))
        max_c = int(round(daily.get("temperature_2m_max", [22])[0]))
        text_en, text_cn, icon_code = WMO_MAP.get(w_code, ("Clear", "晴", 0))

        summary = {
            "city": "Hangzhou",
            "city_cn": "杭州",
            "temp": f"{temp_c}C",
            "temp_num": temp_c,
            "text": text_en,
            "text_cn": text_cn,
            "range": f"{min_c}~{max_c}C",
            "humidity": f"{hum_pct}%",
            "icon": icon_code,
        }
        with open(WEATHER_FILE, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        return summary
    except Exception as e:
        log(f"Weather fetch error: {e}")
        return None

# ==================== QT SIGNALS ====================
class BackendSignals(QObject):
    ble_status_changed = Signal(str, str) # status_key, message ("connected", "已连接: Antigravity-Buddy")
    state_updated      = Signal(str, str) # state ("idle", "thinking", ...), msg
    quota_updated      = Signal(dict)    # quota dict
    weather_updated    = Signal(dict)    # weather dict
    log_received       = Signal(str)     # line of log
    touch_received     = Signal(str)     # touch event

# ==================== ASYNC BACKEND ====================
class BuddyBackend:
    def __init__(self, signals: BackendSignals):
        self.signals = signals
        self.client = None
        self.current_state = "idle"
        self.current_msg = "Antigravity Ready"
        self.auto_idle_deadline = 0.0
        self.current_transcript = None
        self.transcript_offset = 0
        self.loop = None
        self.reconnect_requested = False

    def emit_log(self, text: str):
        log(text)
        self.signals.log_received.emit(text)

    def notification_handler(self, sender, data):
        try:
            text = data.decode("utf-8")
            self.emit_log(f"[ESP32 -> PC] {text}")
            self.signals.touch_received.emit(text)
        except Exception as e:
            self.emit_log(f"[Notify Error] {e}")

    async def send_state(self, state: str, msg: str = "", auto_idle_sec: float = 0.0):
        if not self.client or not self.client.is_connected:
            return
        msg_trimmed = msg[:26]

        payload_dict = {"state": state, "msg": msg_trimmed}
        quota = load_quota()
        if quota:
            payload_dict["q_pct"] = quota.get("q_pct", 93)
            payload_dict["q_str"] = quota.get("q_str", "GEMINI 93%")
            payload_dict["q_gem"] = quota.get("q_gem", "93% / 84%")
            payload_dict["q_cla"] = quota.get("q_cla", "100% / 100%")
            payload_dict["q_arg"] = quota.get("q_arg", "84%")

        weather = load_weather()
        if weather:
            payload_dict["w_city"] = weather.get("city", "Hangzhou")
            payload_dict["w_temp"] = weather.get("temp", "")
            payload_dict["w_text"] = weather.get("text", "")
            payload_dict["w_range"] = weather.get("range", "")
            payload_dict["w_hum"] = weather.get("humidity", weather.get("hum", ""))
            payload_dict["w_icon"] = weather.get("icon", 0)

        payload = json.dumps(payload_dict)
        try:
            await self.client.write_gatt_char(CHARACTERISTIC_UUID, payload.encode("utf-8"))
            self.emit_log(f"[PC -> ESP32] {payload}")
            self.current_state = state
            self.current_msg = msg_trimmed
            self.signals.state_updated.emit(state, msg_trimmed)
            if auto_idle_sec > 0:
                self.auto_idle_deadline = time.time() + auto_idle_sec
            else:
                self.auto_idle_deadline = 0.0
        except Exception as e:
            self.emit_log(f"[Send Error] {e}")

    def parse_step(self, step: dict):
        step_type = step.get("type", "")
        status    = step.get("status", "")
        tools     = step.get("tool_calls") or []

        if status == "ERROR":
            return ("error", "Error Detected!", 5.0)

        if step_type == "USER_INPUT":
            return ("thinking", "Antigravity Thinking...", 0.0)

        if step_type == "PLANNER_RESPONSE":
            if tools:
                first_tool = tools[0]
                t_name = first_tool.get("name", "")
                t_args = first_tool.get("args") or {}

                if t_name == "ask_question":
                    return ("approval", "Input Needed!", 0.0)
                elif t_name in ("edit_file", "write_file"):
                    path = clean_arg(t_args.get("Path", ""))
                    fname = os.path.basename(path) if path else "Code"
                    return ("thinking", f"Coding: {fname}", 0.0)
                elif t_name == "run_command":
                    summary = clean_arg(t_args.get("toolSummary", "")) or "Running Cmd..."
                    return ("thinking", summary, 0.0)
                elif t_name == "read_file":
                    path = clean_arg(t_args.get("Path", ""))
                    fname = os.path.basename(path) if path else "File"
                    return ("thinking", f"Reading: {fname}", 0.0)
                elif t_name == "search_web":
                    return ("thinking", "Searching Web...", 0.0)
                elif t_name == "invoke_subagent":
                    role = clean_arg(t_args.get("Role", "")) or "Subagent"
                    return ("thinking", f"Agent: {role}", 0.0)
                else:
                    return ("thinking", f"Tool: {t_name}", 0.0)
            else:
                return ("success", "Done! ^_^", 4.5)

        return None

    async def poll_transcript(self):
        latest = find_latest_transcript()
        if not latest:
            return

        if latest != self.current_transcript:
            self.current_transcript = latest
            try:
                self.transcript_offset = max(0, os.path.getsize(latest) - 4096)
                self.emit_log(f"Tracking transcript: {os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(latest))))}")
            except Exception:
                self.transcript_offset = 0

        try:
            size = os.path.getsize(self.current_transcript)
            if size > self.transcript_offset:
                with open(self.current_transcript, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self.transcript_offset)
                    chunk = f.read()
                    self.transcript_offset = f.tell()

                lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
                for ln in lines:
                    try:
                        step = json.loads(ln)
                        result = self.parse_step(step)
                        if result:
                            state, msg, auto_idle = result
                            await self.send_state(state, msg, auto_idle)
                    except json.JSONDecodeError:
                        pass
            elif size < self.transcript_offset:
                self.transcript_offset = size
        except Exception:
            pass

    async def run_quota_once(self):
        try:
            proc = await asyncio.create_subprocess_exec(
                "wsl.exe", "-d", "Ubuntu-24.04", "-u", "iamgyp", "python3", "/home/iamgyp/claude/esp32/get_quota.py",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )
            await proc.wait()
            q = load_quota()
            if q:
                self.signals.quota_updated.emit(q)
                self.emit_log(f"Quota refreshed: {q.get('q_str')}")
                if self.client and self.client.is_connected:
                    await self.send_state(self.current_state, self.current_msg)
        except Exception as e:
            self.emit_log(f"Quota refresh error: {e}")

    async def run_weather_once(self):
        try:
            w = await asyncio.to_thread(fetch_weather_direct)
            if w:
                self.signals.weather_updated.emit(w)
                self.emit_log(f"Weather refreshed: {w.get('temp')} {w.get('text')}")
                if self.client and self.client.is_connected:
                    await self.send_state(self.current_state, self.current_msg)
        except Exception as e:
            self.emit_log(f"Weather refresh error: {e}")

    async def quota_loop(self):
        while True:
            await self.run_quota_once()
            await asyncio.sleep(30.0)

    async def weather_loop(self):
        while True:
            await self.run_weather_once()
            await asyncio.sleep(600.0)

    async def main_loop(self):
        self.emit_log("=== Antigravity Buddy Backend Starting ===")
        asyncio.create_task(self.quota_loop())
        asyncio.create_task(self.weather_loop())

        while True:
            try:
                self.signals.ble_status_changed.emit("scanning", "正在扫描 Antigravity-Buddy 设备...")
                device = await BleakScanner.find_device_by_filter(
                    lambda d, ad: d.name and "Antigravity" in d.name,
                    timeout=6.0
                )
                if not device:
                    self.signals.ble_status_changed.emit("disconnected", "未搜索到设备，2秒后重试...")
                    await asyncio.sleep(2.0)
                    continue

                self.signals.ble_status_changed.emit("connecting", f"找到设备 [{device.name}], 正在连接...")
                async with BleakClient(device) as client:
                    self.client = client
                    self.signals.ble_status_changed.emit("connected", f"已连接: {device.name} ({device.address})")
                    self.emit_log(f"CONNECTED to {device.name} [{device.address}]")
                    await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)

                    # Initial push
                    await self.send_state("idle", "Antigravity Ready")

                    while client.is_connected and not self.reconnect_requested:
                        now = time.time()
                        if self.auto_idle_deadline > 0 and now >= self.auto_idle_deadline:
                            self.auto_idle_deadline = 0.0
                            if self.current_state != "idle":
                                await self.send_state("idle", "Antigravity Ready")

                        await self.poll_transcript()
                        await asyncio.sleep(0.15)

                    if self.reconnect_requested:
                        self.reconnect_requested = False
                        self.emit_log("User requested reconnect. Disconnecting...")

                    self.signals.ble_status_changed.emit("disconnected", "蓝牙连接已断开，正在重新连接...")
            except Exception as e:
                self.emit_log(f"BLE loop exception: {e}")
                self.signals.ble_status_changed.emit("disconnected", f"连接异常: {e}")
                await asyncio.sleep(2.0)


# ==================== MAIN WINDOW ====================
class MainWindow(QMainWindow):
    def __init__(self, signals: BackendSignals, backend: BuddyBackend):
        super().__init__()
        self.signals = signals
        self.backend = backend
        self.has_shown_tray_hint = False

        self.setWindowTitle("Antigravity 桌面伴侣 (ESP32-S3)")
        self.setMinimumSize(540, 720)
        self.resize(560, 760)

        if os.path.exists(ICON_PNG):
            self.setWindowIcon(QIcon(ICON_PNG))
        elif os.path.exists(ICON_ICO):
            self.setWindowIcon(QIcon(ICON_ICO))

        self.setup_ui()
        self.setup_tray()
        self.connect_signals()

        # Load cached quota and weather
        q = load_quota()
        if q:
            self.update_quota_ui(q)
        w = load_weather()
        if w:
            self.update_weather_ui(w)

    def setup_ui(self):
        # Dark style palette
        self.setStyleSheet("""
            QMainWindow {
                background-color: #12131a;
            }
            QWidget {
                color: #e2e8f0;
                font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            }
            QFrame.card {
                background-color: #1a1c27;
                border: 1px solid #2d3142;
                border-radius: 12px;
                padding: 12px;
            }
            QLabel.title {
                font-size: 18px;
                font-weight: bold;
                color: #f8fafc;
            }
            QLabel.card-header {
                font-size: 13px;
                font-weight: bold;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QLabel.status-pill {
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QProgressBar {
                background-color: #12131c;
                border: 1px solid #2d3142;
                border-radius: 6px;
                height: 12px;
                text-align: right;
                font-size: 10px;
                color: transparent;
            }
            QProgressBar::chunk {
                border-radius: 5px;
            }
            QPushButton {
                background-color: #272a3a;
                border: 1px solid #3c425c;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: 600;
                color: #e2e8f0;
            }
            QPushButton:hover {
                background-color: #32374b;
                border-color: #4f577a;
            }
            QPushButton:pressed {
                background-color: #1e212e;
            }
            QPushButton.primary {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
                color: #ffffff;
            }
            QPushButton.primary:hover {
                background-color: #0369a1;
            }
            QPlainTextEdit {
                background-color: #0f1016;
                border: 1px solid #242735;
                border-radius: 8px;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 11px;
                color: #94a3b8;
                padding: 6px;
            }
            QCheckBox {
                font-size: 13px;
                color: #94a3b8;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #3c425c;
                background-color: #1a1c27;
            }
            QCheckBox::indicator:checked {
                background-color: #38bdf8;
                border-color: #38bdf8;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # 1. Header with App Title & BLE Status
        header_layout = QHBoxLayout()
        title_label = QLabel("Antigravity 桌面伴侣")
        title_label.setProperty("class", "title")
        version_label = QLabel("v2.0")
        version_label.setStyleSheet("color: #64748b; font-size: 12px; margin-left: 4px;")
        
        self.ble_status_badge = QLabel("正在初始化...")
        self.ble_status_badge.setProperty("class", "status-pill")
        self.set_badge_status("scanning", "正在启动...")

        header_layout.addWidget(title_label)
        header_layout.addWidget(version_label)
        header_layout.addStretch()
        header_layout.addWidget(self.ble_status_badge)
        main_layout.addLayout(header_layout)

        # 2. Card: Live Status & Emotion
        state_card = QFrame()
        state_card.setProperty("class", "card")
        state_layout = QVBoxLayout(state_card)
        state_layout.setSpacing(8)

        card_title = QLabel("AI 实时状态 (Antigravity Emotion)")
        card_title.setProperty("class", "card-header")
        state_layout.addWidget(card_title)

        status_row = QHBoxLayout()
        self.state_badge = QLabel("待机 (IDLE)")
        self.state_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            font-size: 14px;
            font-weight: bold;
            padding: 6px 12px;
            border-radius: 8px;
            border: 1px solid #334155;
        """)
        self.state_msg_label = QLabel("Antigravity Ready")
        self.state_msg_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #f1f5f9;")
        status_row.addWidget(self.state_badge)
        status_row.addWidget(self.state_msg_label, 1)
        state_layout.addLayout(status_row)
        main_layout.addWidget(state_card)

        # 3. Card: Model Quotas
        quota_card = QFrame()
        quota_card.setProperty("class", "card")
        quota_layout = QVBoxLayout(quota_card)
        quota_layout.setSpacing(10)

        q_head_row = QHBoxLayout()
        q_title = QLabel("模型配额看板 (Model Quotas)")
        q_title.setProperty("class", "card-header")
        self.q_time_label = QLabel("同步就绪")
        self.q_time_label.setStyleSheet("font-size: 11px; color: #64748b;")
        q_head_row.addWidget(q_title)
        q_head_row.addStretch()
        q_head_row.addWidget(self.q_time_label)
        quota_layout.addLayout(q_head_row)

        # Gemini
        gem_row = QHBoxLayout()
        gem_name = QLabel("Gemini")
        gem_name.setStyleSheet("font-weight: 600; font-size: 13px; min-width: 110px;")
        self.gem_bar = QProgressBar()
        self.gem_bar.setRange(0, 100)
        self.gem_bar.setValue(86)
        self.gem_bar.setStyleSheet("QProgressBar::chunk { background-color: #38bdf8; }")
        self.gem_val = QLabel("--")
        self.gem_val.setStyleSheet("font-weight: bold; color: #38bdf8; min-width: 90px; text-align: right;")
        self.gem_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gem_row.addWidget(gem_name)
        gem_row.addWidget(self.gem_bar, 1)
        gem_row.addWidget(self.gem_val)
        quota_layout.addLayout(gem_row)

        # Claude & GPT
        cla_row = QHBoxLayout()
        cla_name = QLabel("Claude & GPT")
        cla_name.setStyleSheet("font-weight: 600; font-size: 13px; min-width: 110px;")
        self.cla_bar = QProgressBar()
        self.cla_bar.setRange(0, 100)
        self.cla_bar.setValue(100)
        self.cla_bar.setStyleSheet("QProgressBar::chunk { background-color: #10b981; }")
        self.cla_val = QLabel("--")
        self.cla_val.setStyleSheet("font-weight: bold; color: #10b981; min-width: 90px; text-align: right;")
        self.cla_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cla_row.addWidget(cla_name)
        cla_row.addWidget(self.cla_bar, 1)
        cla_row.addWidget(self.cla_val)
        quota_layout.addLayout(cla_row)

        # Argon
        arg_row = QHBoxLayout()
        arg_name = QLabel("Argon")
        arg_name.setStyleSheet("font-weight: 600; font-size: 13px; min-width: 110px;")
        self.arg_bar = QProgressBar()
        self.arg_bar.setRange(0, 100)
        self.arg_bar.setValue(85)
        self.arg_bar.setStyleSheet("QProgressBar::chunk { background-color: #a855f7; }")
        self.arg_val = QLabel("--")
        self.arg_val.setStyleSheet("font-weight: bold; color: #a855f7; min-width: 90px; text-align: right;")
        self.arg_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        arg_row.addWidget(arg_name)
        arg_row.addWidget(self.arg_bar, 1)
        arg_row.addWidget(self.arg_val)
        quota_layout.addLayout(arg_row)

        main_layout.addWidget(quota_card)

        # 4. Card: Weather & Environment
        weather_card = QFrame()
        weather_card.setProperty("class", "card")
        weather_layout = QVBoxLayout(weather_card)
        weather_layout.setSpacing(6)

        w_title = QLabel("天气与环境 (Weather & Time)")
        w_title.setProperty("class", "card-header")
        weather_layout.addWidget(w_title)

        w_content = QHBoxLayout()
        self.w_temp_label = QLabel("18°C")
        self.w_temp_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #f8fafc;")
        
        w_details = QVBoxLayout()
        w_details.setSpacing(2)
        self.w_desc_label = QLabel("杭州 · 晴 (Sunny)")
        self.w_desc_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #e2e8f0;")
        self.w_range_label = QLabel("气温 13~21°C  ·  湿度 68%")
        self.w_range_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        w_details.addWidget(self.w_desc_label)
        w_details.addWidget(self.w_range_label)

        w_content.addWidget(self.w_temp_label)
        w_content.addSpacing(16)
        w_content.addLayout(w_details)
        w_content.addStretch()
        weather_layout.addLayout(w_content)
        main_layout.addWidget(weather_card)

        # 5. Card: Activity Log & Touch
        log_card = QFrame()
        log_card.setProperty("class", "card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setSpacing(6)

        log_head = QHBoxLayout()
        log_title = QLabel("硬件通信与触控日志 (BLE Logs & Touch)")
        log_title.setProperty("class", "card-header")
        self.touch_status = QLabel("待机中")
        self.touch_status.setStyleSheet("font-size: 11px; color: #38bdf8;")
        log_head.addWidget(log_title)
        log_head.addStretch()
        log_head.addWidget(self.touch_status)
        log_layout.addLayout(log_head)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(130)
        log_layout.addWidget(self.log_box)
        main_layout.addWidget(log_card)

        # 6. Bottom Action Bar
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        self.chk_startup = QCheckBox("开机自动启动")
        self.chk_startup.setChecked(self.is_startup_enabled())
        self.chk_startup.toggled.connect(self.on_toggle_startup)

        self.btn_refresh = QPushButton("刷新配额")
        self.btn_refresh.clicked.connect(self.on_click_refresh_quota)

        self.btn_reconnect = QPushButton("重连蓝牙")
        self.btn_reconnect.clicked.connect(self.on_click_reconnect)

        self.btn_hide = QPushButton("最小化到托盘")
        self.btn_hide.setProperty("class", "primary")
        self.btn_hide.clicked.connect(self.hide)

        action_layout.addWidget(self.chk_startup)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_refresh)
        action_layout.addWidget(self.btn_reconnect)
        action_layout.addWidget(self.btn_hide)
        main_layout.addLayout(action_layout)

    def set_badge_status(self, status: str, text: str):
        if status == "connected":
            self.ble_status_badge.setText(f"● {text}")
            self.ble_status_badge.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #059669;")
        elif status == "scanning" or status == "connecting":
            self.ble_status_badge.setText(f"○ {text}")
            self.ble_status_badge.setStyleSheet("background-color: #78350f; color: #fbbf24; border: 1px solid #d97706;")
        else:
            self.ble_status_badge.setText(f"● {text}")
            self.ble_status_badge.setStyleSheet("background-color: #450a0a; color: #f87171; border: 1px solid #dc2626;")

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(ICON_PNG):
            self.tray_icon.setIcon(QIcon(ICON_PNG))
        elif os.path.exists(ICON_ICO):
            self.tray_icon.setIcon(QIcon(ICON_ICO))
        self.tray_icon.setToolTip("Antigravity 桌面伴侣")

        tray_menu = QMenu()
        show_action = QAction("显示主界面", self)
        show_action.triggered.connect(self.show_and_activate)
        tray_menu.addAction(show_action)

        refresh_action = QAction("刷新配额", self)
        refresh_action.triggered.connect(self.on_click_refresh_quota)
        tray_menu.addAction(refresh_action)

        reconnect_action = QAction("重连蓝牙", self)
        reconnect_action.triggered.connect(self.on_click_reconnect)
        tray_menu.addAction(reconnect_action)

        tray_menu.addSeparator()

        self.tray_startup_action = QAction("开机自动启动", self, checkable=True)
        self.tray_startup_action.setChecked(self.is_startup_enabled())
        self.tray_startup_action.toggled.connect(self.on_toggle_startup)
        tray_menu.addAction(self.tray_startup_action)

        tray_menu.addSeparator()

        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self.real_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible():
                self.hide()
            else:
                self.show_and_activate()

    def show_and_activate(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            if not self.has_shown_tray_hint:
                self.tray_icon.showMessage(
                    "Antigravity 桌面伴侣",
                    "程序已最小化到系统托盘，将在后台继续保持蓝牙与数据同步。",
                    QSystemTrayIcon.Information,
                    2500
                )
                self.has_shown_tray_hint = True
        else:
            event.accept()

    def real_quit(self):
        self.tray_icon.hide()
        QApplication.quit()

    def connect_signals(self):
        self.signals.ble_status_changed.connect(self.on_ble_status)
        self.signals.state_updated.connect(self.on_state_updated)
        self.signals.quota_updated.connect(self.update_quota_ui)
        self.signals.weather_updated.connect(self.update_weather_ui)
        self.signals.log_received.connect(self.append_log)
        self.signals.touch_received.connect(self.on_touch)

    @Slot(str, str)
    def on_ble_status(self, status: str, detail: str):
        self.set_badge_status(status, detail)
        self.append_log(f"[BLE Status] {detail}")

    @Slot(str, str)
    def on_state_updated(self, state: str, msg: str):
        state_map = {
            "idle": ("待机 (IDLE)", "#1e293b", "#38bdf8", "#334155"),
            "thinking": ("思考/执行 (THINKING)", "#312e81", "#818cf8", "#4338ca"),
            "approval": ("等待批准 (APPROVAL)", "#78350f", "#fbbf24", "#d97706"),
            "success": ("完成任务 (SUCCESS)", "#064e3b", "#34d399", "#059669"),
            "error": ("异常报错 (ERROR)", "#450a0a", "#f87171", "#dc2626"),
        }
        text, bg, fg, border = state_map.get(state, ("待机", "#1e293b", "#38bdf8", "#334155"))
        self.state_badge.setText(text)
        self.state_badge.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            font-size: 13px;
            font-weight: bold;
            padding: 6px 12px;
            border-radius: 8px;
            border: 1px solid {border};
        """)
        self.state_msg_label.setText(msg)

    @Slot(dict)
    def update_quota_ui(self, q: dict):
        gem_str = q.get("q_gem", "86% / 78%")
        cla_str = q.get("q_cla", "100% / 100%")
        arg_str = q.get("q_arg", "85%")

        self.gem_val.setText(gem_str)
        self.cla_val.setText(cla_str)
        self.arg_val.setText(arg_str)

        try:
            # Extract first percentage
            gem_p = int(gem_str.split("%")[0].strip())
            self.gem_bar.setValue(gem_p)
        except Exception:
            pass

        try:
            cla_p = int(cla_str.split("%")[0].strip())
            self.cla_bar.setValue(cla_p)
        except Exception:
            pass

        try:
            arg_p = int(arg_str.replace("%", "").strip())
            self.arg_bar.setValue(arg_p)
        except Exception:
            pass

        self.q_time_label.setText(f"最后刷新: {time.strftime('%H:%M:%S')}")

    @Slot(dict)
    def update_weather_ui(self, w: dict):
        temp = w.get("temp", "18C").replace("C", "°C")
        city_cn = w.get("city_cn", "杭州")
        text_cn = w.get("text_cn", "晴")
        text_en = w.get("text", "Sunny")
        w_range = w.get("range", "13~21C").replace("C", "°C")
        humidity = w.get("humidity", "68%")

        self.w_temp_label.setText(temp)
        self.w_desc_label.setText(f"{city_cn} · {text_cn} ({text_en})")
        self.w_range_label.setText(f"气温 {w_range}  ·  湿度 {humidity}")

    @Slot(str)
    def append_log(self, text: str):
        self.log_box.appendPlainText(text)
        # Keep log size reasonable
        if self.log_box.blockCount() > 150:
            cursor = self.log_box.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 50)
            cursor.removeSelectedText()

    @Slot(str)
    def on_touch(self, text: str):
        self.touch_status.setText(f"⚡ 收到触控: {text}")
        QTimer.singleShot(4000, lambda: self.touch_status.setText("待机中"))

    def on_click_refresh_quota(self):
        self.append_log("[User Action] Manual quota refresh requested.")
        if self.backend.loop:
            asyncio.run_coroutine_threadsafe(self.backend.run_quota_once(), self.backend.loop)

    def on_click_reconnect(self):
        self.append_log("[User Action] Reconnect requested.")
        self.backend.reconnect_requested = True

    # ---------- Startup Management ----------
    def get_startup_lnk_path(self):
        startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        return os.path.join(startup_dir, "AntigravityBuddy.lnk")

    def is_startup_enabled(self):
        lnk = self.get_startup_lnk_path()
        return os.path.exists(lnk)

    def on_toggle_startup(self, checked: bool):
        lnk = self.get_startup_lnk_path()
        target_exe = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        work_dir = APP_DIR

        # Keep checkbox and tray menu item in sync
        self.chk_startup.blockSignals(True)
        self.tray_startup_action.blockSignals(True)
        self.chk_startup.setChecked(checked)
        self.tray_startup_action.setChecked(checked)
        self.chk_startup.blockSignals(False)
        self.tray_startup_action.blockSignals(False)

        if checked:
            # Remove legacy vbs if exists
            vbs = os.path.join(os.path.dirname(lnk), "start_buddy.vbs")
            if os.path.exists(vbs):
                try:
                    os.remove(vbs)
                except Exception:
                    pass

            # Create shortcut with --tray
            ps_cmd = f"""
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut('{lnk}')
            $Shortcut.TargetPath = '{target_exe}'
            $Shortcut.Arguments = '--tray'
            $Shortcut.WorkingDirectory = '{work_dir}'
            $Shortcut.Save()
            """
            try:
                subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW
                )
                self.append_log("开机自启已设置成功 (以托盘静默模式启动)。")
            except Exception as e:
                self.append_log(f"设置开机自启失败: {e}")
        else:
            try:
                if os.path.exists(lnk):
                    os.remove(lnk)
                self.append_log("开机自启已取消。")
            except Exception as e:
                self.append_log(f"取消开机自启失败: {e}")


# ==================== MAIN ENTRY POINT ====================
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    server_name = "AntigravityBuddySingleInstanceServer"

    # Single-instance check
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(500):
        # Already running: tell instance to show window and exit
        socket.write(b"SHOW\n")
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        sys.exit(0)

    # Start local server for this instance
    local_server = QLocalServer()
    # Remove stale server if crash occurred
    QLocalServer.removeServer(server_name)
    local_server.listen(server_name)

    signals = BackendSignals()
    backend = BuddyBackend(signals)
    window = MainWindow(signals, backend)

    def on_new_connection():
        client_sock = local_server.nextPendingConnection()
        if client_sock:
            client_sock.readyRead.connect(lambda: handle_client_msg(client_sock))

    def handle_client_msg(client_sock):
        data = client_sock.readAll().data().decode("utf-8").strip()
        if "SHOW" in data:
            window.show_and_activate()
        client_sock.disconnectFromServer()

    local_server.newConnection.connect(on_new_connection)

    # Launch Asyncio in background daemon thread
    def start_asyncio_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        backend.loop = loop
        loop.run_until_complete(backend.main_loop())

    t = threading.Thread(target=start_asyncio_thread, daemon=True)
    t.start()

    # If --tray or --minimized flag passed, start in background
    if "--tray" in sys.argv or "--minimized" in sys.argv:
        pass
    else:
        window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
