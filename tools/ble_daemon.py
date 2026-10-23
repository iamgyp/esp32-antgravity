#!/usr/bin/env python3
"""
Persistent BLE Daemon for Antigravity-Buddy (ESP32-S3)
- Automatically connects and stays connected over BLE
- Turns the ESP32-S3 top-left status indicator emerald green
- Listens for touch events from the ESP32-S3 screen
- Watches ble_cmd.json for instant state updates from Antigravity transcript watcher
"""

import asyncio
import json
import os
import time
from bleak import BleakScanner, BleakClient

SERVICE_UUID        = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
CMD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ble_cmd.json")
TOUCH_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "touch_events.log")

def notification_handler(sender, data):
    try:
        text = data.decode("utf-8")
        print(f"[ESP32 -> PC] {text}", flush=True)
        with open(TOUCH_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except Exception as e:
        print(f"[Notify Error] {e}", flush=True)

async def send_state(client, state: str, msg: str = ""):
    payload = json.dumps({"state": state, "msg": msg[:26]})
    await client.write_gatt_char(CHARACTERISTIC_UUID, payload.encode("utf-8"))
    print(f"[PC -> ESP32] {payload}", flush=True)

async def run_daemon():
    last_mtime = os.path.getmtime(CMD_FILE) if os.path.exists(CMD_FILE) else 0.0
    auto_idle_deadline = 0.0
    current_state = "idle"
    current_msg = ""

    while True:
        try:
            print("Scanning for 'Antigravity-Buddy'...", flush=True)
            device = await BleakScanner.find_device_by_filter(
                lambda d, ad: d.name and "Antigravity" in d.name,
                timeout=8.0
            )
            if not device:
                await asyncio.sleep(1.5)
                continue

            print(f"Found {device.name} [{device.address}], connecting...", flush=True)
            async with BleakClient(device) as client:
                print("CONNECTED to Antigravity-Buddy over BLE!", flush=True)
                await client.start_notify(CHARACTERISTIC_UUID, notification_handler)

                # Sync initial state
                await send_state(client, "idle", "Antigravity Ready")
                current_state = "idle"
                current_msg = "Antigravity Ready"

                while client.is_connected:
                    now = time.time()
                    if os.path.exists(CMD_FILE):
                        try:
                            mtime = os.path.getmtime(CMD_FILE)
                            if mtime > last_mtime:
                                last_mtime = mtime
                                with open(CMD_FILE, "r", encoding="utf-8") as f:
                                    cmd_data = json.load(f)
                                new_state = cmd_data.get("state", "idle")
                                new_msg = cmd_data.get("msg", "")
                                idle_after = float(cmd_data.get("auto_idle_sec", 0.0))

                                if new_state != current_state or new_msg != current_msg:
                                    await send_state(client, new_state, new_msg)
                                    current_state = new_state
                                    current_msg = new_msg

                                if idle_after > 0:
                                    auto_idle_deadline = now + idle_after
                                else:
                                    auto_idle_deadline = 0.0
                        except Exception as e:
                            print(f"[Cmd File Error] {e}", flush=True)

                    if auto_idle_deadline > 0 and now >= auto_idle_deadline:
                        auto_idle_deadline = 0.0
                        if current_state != "idle":
                            await send_state(client, "idle", "Antigravity Ready")
                            current_state = "idle"
                            current_msg = "Antigravity Ready"

                    await asyncio.sleep(0.15)

                print("Disconnected from Antigravity-Buddy. Reconnecting...", flush=True)
        except Exception as e:
            print(f"[BLE Loop Error] {e}", flush=True)
            await asyncio.sleep(1.5)

if __name__ == "__main__":
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        pass
