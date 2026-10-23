#!/usr/bin/env python3
"""
Antigravity Quota Extractor
Extracts account-level model usage & quota limits from language_server
and writes formatted summary to quota.json for Buddy Service & ESP32.
"""

import json
import os
import re
import ssl
import subprocess
import time
import urllib.request

QUOTA_FILE = "/mnt/c/Users/iamgyp/AppData/Local/esp32_buddy/quota.json"

def fetch_quota():
    try:
        cmd = "ps -ef | grep language_server | grep -v grep"
        out = subprocess.check_output(cmd, shell=True, text=True)
        m_csrf = re.search(r'--csrf_token\s+([a-f0-9-]+)', out)
        m_pid = re.search(r'^\S+\s+(\d+)', out)
        if not m_csrf or not m_pid:
            return None
        csrf_token = m_csrf.group(1)
        pid = m_pid.group(1)

        out_ss = subprocess.check_output(f"ss -tlpn | grep pid={pid},", shell=True, text=True)
        ports = re.findall(r'127\.0\.0\.1:(\d+)', out_ss)

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for port in ports:
            url = f"https://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
            req = urllib.request.Request(
                url,
                data=b"{}",
                headers={"Content-Type": "application/json", "x-codeium-csrf-token": csrf_token}
            )
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=1.5) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception:
                continue
    except Exception as e:
        print(f"[Quota Fetch Error] {e}")
    return None

def main():
    raw = fetch_quota()
    if not raw:
        return

    groups = raw.get("response", {}).get("groups", [])
    
    # Defaults
    gem_5h = 93
    gem_wk = 84
    cla_5h = 100
    cla_wk = 100
    arg_wk = 84

    for g in groups:
        dname = g.get("displayName", "")
        buckets = g.get("buckets", [])
        if "Gemini Models" in dname:
            for b in buckets:
                pct = int(round(b.get("remainingFraction", 1.0) * 100))
                if b.get("window") == "5h": gem_5h = pct
                elif b.get("window") == "weekly": gem_wk = pct
        elif "Claude" in dname:
            for b in buckets:
                pct = int(round(b.get("remainingFraction", 1.0) * 100))
                if b.get("window") == "5h": cla_5h = pct
                elif b.get("window") == "weekly": cla_wk = pct
        elif "Argon" in dname:
            for b in buckets:
                pct = int(round(b.get("remainingFraction", 1.0) * 100))
                if b.get("window") == "weekly": arg_wk = pct

    # Current model quota (default to Gemini unless specified)
    cur_quota_pct = gem_5h
    cur_quota_str = f"GEMINI {gem_5h}%"

    summary = {
        "updated": time.time(),
        "q_pct": cur_quota_pct,
        "q_str": cur_quota_str,
        "q_gem": f"{gem_5h}% / {gem_wk}%",
        "q_cla": f"{cla_5h}% / {cla_wk}%",
        "q_arg": f"{arg_wk}%",
        "gem_5h": gem_5h,
        "gem_wk": gem_wk,
        "cla_5h": cla_5h,
        "cla_wk": cla_wk,
        "arg_wk": arg_wk,
    }

    try:
        os.makedirs(os.path.dirname(QUOTA_FILE), exist_ok=True)
        tmp = QUOTA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        os.replace(tmp, QUOTA_FILE)
        print(f"[Quota] Saved to {QUOTA_FILE}: {summary['q_str']}")
    except Exception as e:
        print(f"[Quota Save Error] {e}")

if __name__ == "__main__":
    main()
