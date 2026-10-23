#!/usr/bin/env python3
"""
Antigravity Live Transcript Watcher -> ESP32-S3 3D Robot Companion
Monitors ~/.gemini/antigravity/brain/<conv-id>/.system_generated/logs/transcript.jsonl
in real time and pushes state transitions to ble_cmd.json:
  1. USER_INPUT          -> state: "thinking", msg: "Thinking..."
  2. PLANNER_RESPONSE w/ tool_calls:
     - ask_question      -> state: "approval", msg: "Confirm Action?"
     - edit_file/write   -> state: "thinking", msg: "Coding <file>..."
     - run_command       -> state: "thinking", msg: "<toolSummary>"
     - read_file/search  -> state: "thinking", msg: "Analyzing Code..."
  3. status == "ERROR"   -> state: "error",    msg: "Error Detected!", auto_idle_sec: 5
  4. Final PLANNER_RESPONSE (no tool_calls):
                         -> state: "success",  msg: "Task Done! ^_^", auto_idle_sec: 4
"""

import glob
import json
import os
import time

BRAIN_DIR = "/home/iamgyp/.gemini/antigravity/brain"
CMD_FILE  = "/mnt/c/Users/iamgyp/AppData/Local/esp32_buddy/ble_cmd.json"

def write_cmd(state: str, msg: str, auto_idle_sec: float = 0.0):
    payload = {
        "state": state,
        "msg": msg[:26],
        "auto_idle_sec": auto_idle_sec,
        "ts": time.time(),
    }
    tmp_file = CMD_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp_file, CMD_FILE)
    print(f"[Watcher -> BLE] state={state} | msg='{msg}' | auto_idle={auto_idle_sec}s", flush=True)

def clean_arg(val):
    if not isinstance(val, str):
        return ""
    return val.strip().strip('"').strip("'")

def find_latest_transcript():
    pattern = os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def process_step(step: dict):
    step_type = step.get("type", "")
    status    = step.get("status", "")
    tools     = step.get("tool_calls") or []

    if status == "ERROR":
        write_cmd("error", "Error Detected!", auto_idle_sec=5.0)
        return

    if step_type == "USER_INPUT":
        write_cmd("thinking", "Antigravity Thinking...")
        return

    if step_type == "PLANNER_RESPONSE":
        if tools:
            first_tool = tools[0]
            t_name = first_tool.get("name", "")
            t_args = first_tool.get("args") or {}

            if t_name == "ask_question":
                write_cmd("approval", "Input Needed!")
            elif t_name in ("edit_file", "write_file"):
                path = clean_arg(t_args.get("Path", ""))
                fname = os.path.basename(path) if path else "File"
                write_cmd("thinking", f"Coding: {fname}")
            elif t_name == "run_command":
                summary = clean_arg(t_args.get("toolSummary", "")) or "Running Cmd..."
                write_cmd("thinking", summary)
            elif t_name == "read_file":
                path = clean_arg(t_args.get("Path", ""))
                fname = os.path.basename(path) if path else "File"
                write_cmd("thinking", f"Reading: {fname}")
            elif t_name == "search_web":
                write_cmd("thinking", "Searching Web...")
            elif t_name == "invoke_subagent":
                role = clean_arg(t_args.get("Role", "")) or "Subagent"
                write_cmd("thinking", f"Agent: {role}")
            else:
                write_cmd("thinking", f"Tool: {t_name}")
        else:
            # Model finished responding to the user!
            write_cmd("success", "Done! ^_^", auto_idle_sec=4.5)

def main():
    print("Starting Antigravity Live Transcript Watcher...", flush=True)
    current_file = find_latest_transcript()
    last_size = os.path.getsize(current_file) if current_file and os.path.exists(current_file) else 0
    if current_file:
        print(f"Watching transcript: {current_file} (offset {last_size})", flush=True)

    while True:
        try:
            latest = find_latest_transcript()
            if latest != current_file and latest is not None:
                current_file = latest
                last_size = max(0, os.path.getsize(current_file) - 4096)
                print(f"Switched to latest transcript: {current_file}", flush=True)

            if current_file and os.path.exists(current_file):
                size = os.path.getsize(current_file)
                if size > last_size:
                    with open(current_file, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_size)
                        new_data = f.read()
                        last_size = f.tell()

                    lines = [ln.strip() for ln in new_data.splitlines() if ln.strip()]
                    for ln in lines:
                        try:
                            step = json.loads(ln)
                            process_step(step)
                        except json.JSONDecodeError:
                            pass
                elif size < last_size:
                    last_size = size
        except Exception as e:
            print(f"[Watcher Error] {e}", flush=True)

        time.sleep(0.15)

if __name__ == "__main__":
    main()
