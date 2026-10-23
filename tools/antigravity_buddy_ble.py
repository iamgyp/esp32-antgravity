#!/usr/bin/env python3
"""
Antigravity Desktop Buddy - Host BLE / Serial Bridge
Communicates with ESP32-S3 over Bluetooth Low Energy (or Serial).
Sends:
  - {"state": "idle", "msg": "..."}
  - {"state": "thinking", "msg": "..."}
  - {"state": "approval", "msg": "..."}
  - {"state": "success", "msg": "..."}
  - {"state": "error", "msg": "..."}
Receives:
  - {"event": "approved"}
  - {"event": "denied"}
"""

import asyncio
import json
import sys
from bleak import BleakScanner, BleakClient

SERVICE_UUID        = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

client_instance = None

def notification_handler(sender, data):
    try:
        text = data.decode("utf-8")
        payload = json.loads(text)
        event = payload.get("event")
        if event == "approved":
            print("\n🟢 [TOUCH] User APPROVED action from ESP32 screen!", flush=True)
        elif event == "denied":
            print("\n🔴 [TOUCH] User DENIED action from ESP32 screen!", flush=True)
        else:
            print(f"\n📩 [NOTIFY] {text}", flush=True)
    except Exception as e:
        print(f"Notification error: {e}")

async def send_state(client, state: str, msg: str = ""):
    cmd = json.dumps({"state": state, "msg": msg})
    await client.write_gatt_char(CHARACTERISTIC_UUID, cmd.encode("utf-8"))
    print(f"➡️ Sent: {cmd}")

async def main():
    print("🔍 Scanning for 'Antigravity-Buddy' BLE device...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name and "Antigravity" in d.name,
        timeout=10.0
    )

    if not device:
        print("❌ 'Antigravity-Buddy' not found! Make sure device is powered on.")
        return

    print(f"✅ Found device: {device.name} [{device.address}]")
    async with BleakClient(device) as client:
        print("✨ Connected to Antigravity Buddy over BLE!")
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler)

        # Initial handshake
        await send_state(client, "success", "Connected to PC!")
        await asyncio.sleep(2)
        await send_state(client, "idle", "Ready for Coding")

        print("\n--- Interactive Demo Mode ---")
        print("Demo cycles states automatically. Touch screen buttons to test approval!")
        
        test_sequence = [
            ("thinking", "Analyzing codebase..."),
            ("approval", "Run `git push --force`?"),
            ("success", "Build succeeded! (100%)"),
            ("error", "SyntaxError on line 42"),
            ("idle", "Waiting for Antigravity...")
        ]

        idx = 0
        while True:
            await asyncio.sleep(6)
            state, msg = test_sequence[idx % len(test_sequence)]
            await send_state(client, state, msg)
            idx += 1

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")
