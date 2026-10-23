#!/usr/bin/env python3
"""
Antigravity Desktop Buddy - Local WebSocket Bridge for Xiaozhi-ESP32
Handles:
- Xiaozhi protocol handshake (Hello)
- Emotion mapping (idle, thinking, coding, approval, success, error)
- Status messages / Text subtitles
- MCP tool interaction & Touch approval events
"""

import asyncio
import json
import logging
from websockets.server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global connected client reference
current_client = None

async def send_emotion(ws, emotion: str, text: str = ""):
    """Send emotion and optional status message to ESP32 screen."""
    # 1. Update Emotion
    msg_llm = {
        "type": "llm",
        "emotion": emotion
    }
    await ws.send(json.dumps(msg_llm))
    logging.info(f"Sent emotion: {emotion}")

    # 2. Update Text if provided
    if text:
        msg_text = {
            "type": "tts",
            "state": "sentence_start",
            "text": text
        }
        await ws.send(json.dumps(msg_text))
        logging.info(f"Sent text: {text}")

async def handle_connection(websocket):
    global current_client
    current_client = websocket
    peer = websocket.remote_address
    logging.info(f"✨ New ESP32 Buddy connected from {peer}!")

    try:
        async for message in websocket:
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    logging.info(f"Received from ESP32: type={msg_type}")

                    # Handshake hello
                    if msg_type == "hello":
                        hello_resp = {
                            "type": "hello",
                            "transport": "websocket",
                            "audio_params": {
                                "format": "opus",
                                "sample_rate": 24000,
                                "channels": 1,
                                "frame_duration": 60
                            }
                        }
                        await websocket.send(json.dumps(hello_resp))
                        logging.info("Sent hello handshake to ESP32")

                        # Immediately greet the user with a happy face!
                        await asyncio.sleep(0.5)
                        await send_emotion(websocket, "happy", "Antigravity 伴侣已上线！")

                    elif msg_type == "mcp":
                        logging.info(f"MCP payload from device: {data.get('payload')}")

                    elif msg_type == "abort":
                        logging.info("Device sent abort / touch event")

                except json.JSONDecodeError:
                    pass
            else:
                # Binary audio frames (if mic is streaming), ignore for now
                pass

    except Exception as e:
        logging.error(f"Connection error: {e}")
    finally:
        current_client = None
        logging.info(f"ESP32 Buddy disconnected: {peer}")

async def interactive_test_loop():
    """Simple interactive CLI loop to demonstrate changing states."""
    await asyncio.sleep(2)
    emotions = [
        ("happy", "你好！我是你的 Antigravity 工位搭子"),
        ("thinking", "Antigravity 正在分析代码需求..."),
        ("excited", "单元测试全部通过！完美！"),
        ("neutral", "等待你的下一条开发任务...")
    ]
    idx = 0
    while True:
        await asyncio.sleep(8)
        if current_client:
            emotion, text = emotions[idx % len(emotions)]
            await send_emotion(current_client, emotion, text)
            idx += 1

async def main():
    host = "0.0.0.0"
    port = 8765
    logging.info(f"Starting Antigravity Buddy Bridge on ws://{host}:{port}/ws ...")
    server = await serve(handle_connection, host, port)
    await asyncio.gather(
        server.wait_closed(),
        interactive_test_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBridge stopped.")
