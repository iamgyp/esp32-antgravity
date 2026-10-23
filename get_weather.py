#!/usr/bin/env python3
"""
Antigravity Weather Fetcher
Fetches live local weather for Hangzhou (or configured city) via Open-Meteo
and writes to weather.json for Buddy Service & ESP32 screen.
"""

import json
import os
import time
import urllib.request

WEATHER_FILE = "/mnt/c/Users/iamgyp/AppData/Local/esp32_buddy/weather.json"
CITY_FILE    = "/mnt/c/Users/iamgyp/AppData/Local/esp32_buddy/weather_city.json"

DEFAULT_CITY = {
    "name": "Hangzhou",
    "cn": "杭州",
    "lat": 30.2741,
    "lon": 120.1551
}

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

def fetch_weather():
    city = DEFAULT_CITY
    if os.path.exists(CITY_FILE):
        try:
            with open(CITY_FILE, "r", encoding="utf-8") as f:
                city = json.load(f)
        except Exception:
            pass

    lat = city.get("lat", 30.2741)
    lon = city.get("lon", 120.1551)
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
            "updated": time.time(),
            "city": city.get("name", "Hangzhou"),
            "city_cn": city.get("cn", "杭州"),
            "temp": f"{temp_c}C",
            "temp_num": temp_c,
            "text": text_en,
            "text_cn": text_cn,
            "range": f"{min_c}~{max_c}C",
            "humidity": f"{hum_pct}%",
            "icon": icon_code,
        }

        os.makedirs(os.path.dirname(WEATHER_FILE), exist_ok=True)
        tmp = WEATHER_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        os.replace(tmp, WEATHER_FILE)
        print(f"[Weather] Saved: {summary['city']} {summary['temp']} {summary['text']}")
        return summary
    except Exception as e:
        print(f"[Weather Error] {e}")
        return None

if __name__ == "__main__":
    fetch_weather()
