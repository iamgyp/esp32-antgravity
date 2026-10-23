#!/usr/bin/env python3
"""
Antigravity 3D Desktop Buddy Service
Single unified daemon running on Windows:
1. Auto-connects & reconnects to ESP32-S3 over BLE 5.0
2. Monitors Antigravity transcripts in real-time directly via WSL UNC path
3. Fetches account-level Model Quota (Gemini, Claude, Argon) periodically
4. Pushes live emotion states & quota telemetry to ESP32 screen
5. Listens for screen touch events (approved, denied, touched)
"""

import asyncio
import glob
import json
import os
import sys
import time
import urllib.request
from bleak import BleakScanner, BleakClient

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

SERVICE_UUID        = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

WSL_BRAIN_DIR = r"\\wsl.localhost\Ubuntu-24.04\home\iamgyp\.gemini\antigravity\brain"
FALLBACK_WSL_DIR = r"\\wsl$\Ubuntu-24.04\home\iamgyp\.gemini\antigravity\brain"
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
TOUCH_LOG = os.path.join(LOG_DIR, "touch_events.log")
SERVICE_LOG = os.path.join(LOG_DIR, "buddy_service.log")
QUOTA_FILE = os.path.join(LOG_DIR, "quota.json")
WEATHER_FILE = os.path.join(LOG_DIR, "weather.json")

def log(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry, flush=True)
    try:
        with open(SERVICE_LOG, "a", encoding="utf-8") as f:
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
        log(f"Weather direct fetch error: {e}")
        return None

class BuddyService:
    def __init__(self):
        self.client = None
        self.current_state = "idle"
        self.current_msg = "Antigravity Ready"
        self.auto_idle_deadline = 0.0
        self.current_transcript = None
        self.transcript_offset = 0

    def notification_handler(self, sender, data):
        try:
            text = data.decode("utf-8")
            log(f"[ESP32 -> PC] {text}")
            with open(TOUCH_LOG, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
        except Exception as e:
            log(f"[Notify Error] {e}")

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
            log(f"[PC -> ESP32] {payload}")
            self.current_state = state
            self.current_msg = msg_trimmed
            if auto_idle_sec > 0:
                self.auto_idle_deadline = time.time() + auto_idle_sec
            else:
                self.auto_idle_deadline = 0.0
        except Exception as e:
            log(f"[Send Error] {e}")

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
                log(f"Tracking new transcript: {latest}")
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
        except Exception as e:
            pass

    async def quota_loop(self):
        last_sig = None
        while True:
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
                    sig = (q.get("q_str"), q.get("q_gem"), q.get("q_cla"), q.get("q_arg"))
                    if sig != last_sig:
                        last_sig = sig
                        log(f"Refreshed quota: {q.get('q_str')} | pushing to screen...")
                        await self.send_state(self.current_state, self.current_msg)
            except Exception:
                pass
            await asyncio.sleep(30.0)

    async def weather_loop(self):
        last_sig = None
        while True:
            try:
                w = await asyncio.to_thread(fetch_weather_direct)
                if w:
                    sig = (w.get("temp"), w.get("text"), w.get("range"), w.get("humidity"))
                    if sig != last_sig:
                        last_sig = sig
                        log(f"Refreshed weather: {w.get('temp')} {w.get('text')} | pushing to screen...")
                        await self.send_state(self.current_state, self.current_msg)
            except Exception:
                pass
            await asyncio.sleep(600.0)

    async def run(self):
        log("=== Antigravity Unified Buddy Service Starting ===")
        asyncio.create_task(self.quota_loop())
        asyncio.create_task(self.weather_loop())

        while True:
            try:
                log("Scanning for 'Antigravity-Buddy' BLE device...")
                device = await BleakScanner.find_device_by_filter(
                    lambda d, ad: d.name and "Antigravity" in d.name,
                    timeout=8.0
                )
                if not device:
                    await asyncio.sleep(2.0)
                    continue

                log(f"Found {device.name} [{device.address}], connecting...")
                async with BleakClient(device) as client:
                    self.client = client
                    log("CONNECTED to Antigravity-Buddy!")
                    await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)

                    # Handshake
                    await self.send_state("idle", "Antigravity Ready")

                    while client.is_connected:
                        now = time.time()
                        if self.auto_idle_deadline > 0 and now >= self.auto_idle_deadline:
                            self.auto_idle_deadline = 0.0
                            if self.current_state != "idle":
                                await self.send_state("idle", "Antigravity Ready")

                        await self.poll_transcript()
                        await asyncio.sleep(0.15)

                    log("Disconnected from Antigravity-Buddy. Reconnecting in 2s...")
            except Exception as e:
                log(f"Connection loop error: {e}")
                await asyncio.sleep(2.0)

if __name__ == "__main__":
    service = BuddyService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        log("Buddy service terminated by user.")
