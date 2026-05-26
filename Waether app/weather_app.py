#!/usr/bin/env python3
# ============================================================
#  weather_app.py  –  Premium Flask Weather Web App
#
#  Usage:
#      python weather_app.py          # launch web UI on port 5007
#      python weather_app.py --cli    # original terminal interface
#
#  Prerequisites:
#      pip install flask requests rich
# ============================================================
import sys
import os

# Make sure sibling modules are importable when run from any CWD
sys.path.insert(0, os.path.dirname(__file__))

from weather_config import DEFAULT_UNITS, DEFAULT_CITY, API_KEY
from weather_fetcher import (
    detect_location_by_ip, geocode_city,
    get_current_weather, get_forecast,
    parse_current, parse_daily_forecast,
)
from weather_display import (
    show_banner, show_current, show_forecast,
    show_error, show_info, show_menu,
    ask_city, ask_units, console,
)

import json
import time
import math
import requests
import threading
import webbrowser
from datetime import datetime

from flask import Flask, request, jsonify, render_template_string

# ── Flask app ────────────────────────────────────────────────
app = Flask(__name__)

# ── Demo mode data (kept for CLI fallback) ───────────────────
DEMO_CURRENT = {
    "name": "London", "visibility": 10000,
    "main": {"temp": 18.5, "feels_like": 17.2, "temp_min": 14.0,
             "temp_max": 21.0, "humidity": 65, "pressure": 1013},
    "wind": {"speed": 5.2, "deg": 220},
    "weather": [{"main": "Clouds", "description": "scattered clouds"}],
    "sys": {"country": "GB", "sunrise": 1700000000, "sunset": 1700040000},
}

DEMO_FORECAST_LIST = []
for _i in range(40):
    _t = time.time() + _i * 10800
    DEMO_FORECAST_LIST.append({
        "dt": _t,
        "main": {"temp": 15 + 6 * math.sin(_i * 0.4)},
        "weather": [{"main": ["Clear", "Clouds", "Rain", "Drizzle"][_i % 4],
                     "description": ["clear sky", "few clouds", "light rain", "drizzle"][_i % 4]}],
    })
DEMO_FORECAST = {"list": DEMO_FORECAST_LIST}


def _is_demo() -> bool:
    return API_KEY in ("", "YOUR_OPENWEATHERMAP_API_KEY")


# ── WMO Weather Code Mapping ────────────────────────────────
WMO_CODES = {
    0:  {"emoji": "☀️",  "desc": "Clear Sky",        "gradient": "linear-gradient(135deg, #f97316 0%, #f59e0b 50%, #fbbf24 100%)"},
    1:  {"emoji": "🌤️",  "desc": "Mainly Clear",     "gradient": "linear-gradient(135deg, #f59e0b 0%, #60a5fa 100%)"},
    2:  {"emoji": "⛅",  "desc": "Partly Cloudy",    "gradient": "linear-gradient(135deg, #64748b 0%, #60a5fa 50%, #93c5fd 100%)"},
    3:  {"emoji": "☁️",  "desc": "Overcast",          "gradient": "linear-gradient(135deg, #475569 0%, #64748b 50%, #94a3b8 100%)"},
    45: {"emoji": "🌫️",  "desc": "Fog",               "gradient": "linear-gradient(135deg, #6b7280 0%, #9ca3af 100%)"},
    48: {"emoji": "🌫️",  "desc": "Rime Fog",          "gradient": "linear-gradient(135deg, #6b7280 0%, #9ca3af 100%)"},
    51: {"emoji": "🌦️",  "desc": "Light Drizzle",     "gradient": "linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%)"},
    53: {"emoji": "🌦️",  "desc": "Moderate Drizzle",  "gradient": "linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)"},
    55: {"emoji": "🌦️",  "desc": "Dense Drizzle",     "gradient": "linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%)"},
    61: {"emoji": "🌧️",  "desc": "Slight Rain",       "gradient": "linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)"},
    63: {"emoji": "🌧️",  "desc": "Moderate Rain",     "gradient": "linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%)"},
    65: {"emoji": "🌧️",  "desc": "Heavy Rain",        "gradient": "linear-gradient(135deg, #172554 0%, #1e3a8a 100%)"},
    71: {"emoji": "🌨️",  "desc": "Slight Snow",       "gradient": "linear-gradient(135deg, #e2e8f0 0%, #94a3b8 100%)"},
    73: {"emoji": "❄️",  "desc": "Moderate Snow",     "gradient": "linear-gradient(135deg, #cbd5e1 0%, #64748b 100%)"},
    75: {"emoji": "❄️",  "desc": "Heavy Snow",        "gradient": "linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)"},
    80: {"emoji": "🌦️",  "desc": "Slight Showers",    "gradient": "linear-gradient(135deg, #0ea5e9 0%, #38bdf8 100%)"},
    81: {"emoji": "🌧️",  "desc": "Moderate Showers",  "gradient": "linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%)"},
    82: {"emoji": "⛈️",  "desc": "Violent Showers",   "gradient": "linear-gradient(135deg, #0369a1 0%, #0284c7 100%)"},
    95: {"emoji": "⛈️",  "desc": "Thunderstorm",      "gradient": "linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4c1d95 100%)"},
    96: {"emoji": "⛈️",  "desc": "T-storm w/ Hail",   "gradient": "linear-gradient(135deg, #1e1b4b 0%, #4c1d95 100%)"},
    99: {"emoji": "⛈️",  "desc": "T-storm w/ Heavy Hail", "gradient": "linear-gradient(135deg, #0f0a2e 0%, #1e1b4b 100%)"},
}

def _wmo(code):
    return WMO_CODES.get(code, {"emoji": "🌡️", "desc": "Unknown", "gradient": "linear-gradient(135deg, #334155 0%, #1e293b 100%)"})


# ── API helpers (Open-Meteo + Nominatim) ─────────────────────

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
IP_GEO_URL = "http://ip-api.com/json"
HEADERS = {"User-Agent": "PinacleWeatherApp/1.0 (student-project)"}


def _geocode_nominatim(city: str):
    """Geocode city via OpenStreetMap Nominatim."""
    try:
        resp = requests.get(NOMINATIM_URL, params={
            "q": city, "format": "json", "limit": 1
        }, headers=HEADERS, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if data:
            loc = data[0]
            display = loc.get("display_name", city)
            parts = display.split(",")
            city_name = parts[0].strip() if parts else city
            country = parts[-1].strip() if len(parts) > 1 else ""
            return {
                "city": city_name,
                "country": country,
                "lat": float(loc["lat"]),
                "lon": float(loc["lon"]),
                "display": display,
            }
    except Exception as e:
        print(f"  Geocode error: {e}")
    return None


def _fetch_open_meteo(lat: float, lon: float, units: str = "celsius"):
    """Fetch weather from Open-Meteo API."""
    temp_unit = "fahrenheit" if units == "fahrenheit" else "celsius"
    wind_unit = "mph" if units == "fahrenheit" else "kmh"
    try:
        resp = requests.get(OPEN_METEO_URL, params={
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "daily": "temperature_2m_max,temperature_2m_min,weathercode,windspeed_10m_max,sunrise,sunset",
            "hourly": "relativehumidity_2m,pressure_msl,visibility",
            "temperature_unit": temp_unit,
            "windspeed_unit": wind_unit,
            "timezone": "auto",
            "forecast_days": 5,
        }, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Open-Meteo error: {e}")
    return None


def _detect_ip_location():
    """Auto-detect location via IP."""
    try:
        resp = requests.get(IP_GEO_URL, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return {
                "city": data.get("city", "Unknown"),
                "country": data.get("country", ""),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
            }
    except Exception as e:
        print(f"  IP geo error: {e}")
    return None


def _build_weather_response(location, meteo_data, units="celsius"):
    """Parse Open-Meteo response into structured JSON."""
    cw = meteo_data.get("current_weather", {})
    daily = meteo_data.get("daily", {})
    hourly = meteo_data.get("hourly", {})
    unit_sym = "°F" if units == "fahrenheit" else "°C"
    wind_unit = "mph" if units == "fahrenheit" else "km/h"
    wcode = cw.get("weathercode", 0)
    wmo = _wmo(wcode)

    # Get current hour index for hourly data
    now_iso = cw.get("time", "")
    hour_idx = 0
    hourly_times = hourly.get("time", [])
    for i, t in enumerate(hourly_times):
        if t <= now_iso:
            hour_idx = i

    humidity = hourly.get("relativehumidity_2m", [65])[hour_idx] if hourly.get("relativehumidity_2m") else 65
    pressure = hourly.get("pressure_msl", [1013])[hour_idx] if hourly.get("pressure_msl") else 1013
    visibility_m = hourly.get("visibility", [10000])[hour_idx] if hourly.get("visibility") else 10000
    visibility_km = round(visibility_m / 1000, 1) if visibility_m else 10.0

    sunrise_list = daily.get("sunrise", [])
    sunset_list = daily.get("sunset", [])
    sunrise_today = sunrise_list[0] if sunrise_list else ""
    sunset_today = sunset_list[0] if sunset_list else ""

    # Format sunrise/sunset to just time
    sunrise_time = sunrise_today.split("T")[1] if "T" in sunrise_today else sunrise_today
    sunset_time = sunset_today.split("T")[1] if "T" in sunset_today else sunset_today

    current = {
        "city": location.get("city", "Unknown"),
        "country": location.get("country", ""),
        "temp": cw.get("temperature", 0),
        "wind_speed": cw.get("windspeed", 0),
        "wind_dir": cw.get("winddirection", 0),
        "weathercode": wcode,
        "emoji": wmo["emoji"],
        "description": wmo["desc"],
        "gradient": wmo["gradient"],
        "humidity": humidity,
        "pressure": round(pressure, 1) if pressure else 1013,
        "visibility": visibility_km,
        "sunrise": sunrise_time,
        "sunset": sunset_time,
        "unit_sym": unit_sym,
        "wind_unit": wind_unit,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Build forecast
    forecast = []
    dates = daily.get("time", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    w_codes = daily.get("weathercode", [])
    w_speeds = daily.get("windspeed_10m_max", [])

    for i in range(min(5, len(dates))):
        fc_wmo = _wmo(w_codes[i] if i < len(w_codes) else 0)
        day_name = datetime.strptime(dates[i], "%Y-%m-%d").strftime("%a")
        day_date = datetime.strptime(dates[i], "%Y-%m-%d").strftime("%d %b")
        forecast.append({
            "day": day_name,
            "date": day_date,
            "temp_max": round(t_max[i], 1) if i < len(t_max) else 0,
            "temp_min": round(t_min[i], 1) if i < len(t_min) else 0,
            "weathercode": w_codes[i] if i < len(w_codes) else 0,
            "emoji": fc_wmo["emoji"],
            "description": fc_wmo["desc"],
            "wind_max": round(w_speeds[i], 1) if i < len(w_speeds) else 0,
            "unit_sym": unit_sym,
            "wind_unit": wind_unit,
        })

    return {"current": current, "forecast": forecast}


# ── Flask Routes ─────────────────────────────────────────────

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⛅ Pinacle Weather</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        /* ── CSS Reset & Custom Properties ── */
        *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
        :root {
            --bg: #070d15;
            --bg-card: rgba(15, 23, 35, 0.65);
            --bg-card-hover: rgba(20, 30, 50, 0.8);
            --glass-border: rgba(56, 189, 248, 0.12);
            --glass-border-hover: rgba(56, 189, 248, 0.3);
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.25);
            --accent-dim: rgba(56, 189, 248, 0.08);
            --text: #e2e8f0;
            --text-dim: #94a3b8;
            --text-muted: #64748b;
            --danger: #f87171;
            --success: #4ade80;
            --warm: #fbbf24;
            --font: 'Outfit', -apple-system, sans-serif;
            --mono: 'JetBrains Mono', monospace;
            --radius: 18px;
            --radius-sm: 12px;
            --blur: 22px;
            --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        html { font-size: 16px; }
        body {
            font-family: var(--font);
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }

        /* ── Animated Background ── */
        body::before {
            content: '';
            position: fixed; inset: 0;
            background:
                radial-gradient(ellipse 600px 400px at 20% 20%, rgba(56,189,248,0.07) 0%, transparent 70%),
                radial-gradient(ellipse 500px 500px at 80% 80%, rgba(139,92,246,0.05) 0%, transparent 70%),
                radial-gradient(ellipse 400px 300px at 60% 10%, rgba(251,191,36,0.04) 0%, transparent 70%);
            z-index: 0;
            pointer-events: none;
            animation: bgShift 20s ease-in-out infinite alternate;
        }
        @keyframes bgShift {
            0% { opacity: 0.8; transform: scale(1); }
            100% { opacity: 1; transform: scale(1.05); }
        }

        /* ── Glass Card Mixin ── */
        .glass {
            background: var(--bg-card);
            backdrop-filter: blur(var(--blur));
            -webkit-backdrop-filter: blur(var(--blur));
            border: 1px solid var(--glass-border);
            border-radius: var(--radius);
            transition: all var(--transition);
        }
        .glass:hover {
            border-color: var(--glass-border-hover);
            box-shadow: 0 0 30px rgba(56,189,248,0.06);
        }

        /* ── Layout ── */
        .app-container {
            position: relative;
            z-index: 1;
            max-width: 1280px;
            margin: 0 auto;
            padding: 24px 20px 40px;
        }

        /* ── Header / Brand ── */
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 28px;
            flex-wrap: wrap;
            gap: 16px;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .brand-icon {
            font-size: 2rem;
            filter: drop-shadow(0 0 12px rgba(56,189,248,0.4));
            animation: float 3s ease-in-out infinite;
        }
        @keyframes float {
            0%,100% { transform: translateY(0); }
            50% { transform: translateY(-6px); }
        }
        .brand h1 {
            font-size: 1.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -0.5px;
        }
        .brand-tag {
            font-size: 0.7rem;
            color: var(--text-muted);
            font-weight: 400;
            letter-spacing: 2px;
            text-transform: uppercase;
        }

        /* ── Search Bar ── */
        .search-area {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .search-box {
            display: flex;
            align-items: center;
            background: rgba(15,23,42,0.7);
            border: 1px solid var(--glass-border);
            border-radius: 50px;
            padding: 4px 6px 4px 20px;
            transition: all var(--transition);
            min-width: 300px;
        }
        .search-box:focus-within {
            border-color: var(--accent);
            box-shadow: 0 0 20px var(--accent-glow);
        }
        .search-box input {
            background: none;
            border: none;
            outline: none;
            color: var(--text);
            font-family: var(--font);
            font-size: 0.95rem;
            font-weight: 400;
            padding: 10px 8px;
            flex: 1;
            min-width: 150px;
        }
        .search-box input::placeholder { color: var(--text-muted); }
        .btn {
            font-family: var(--font);
            font-weight: 600;
            font-size: 0.85rem;
            border: none;
            border-radius: 50px;
            padding: 10px 20px;
            cursor: pointer;
            transition: all var(--transition);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }
        .btn-primary {
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            color: #0f172a;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(56,189,248,0.35);
        }
        .btn-secondary {
            background: rgba(56,189,248,0.1);
            color: var(--accent);
            border: 1px solid rgba(56,189,248,0.2);
        }
        .btn-secondary:hover {
            background: rgba(56,189,248,0.2);
            transform: translateY(-2px);
        }
        .btn-toggle {
            background: rgba(56,189,248,0.08);
            color: var(--text-dim);
            border: 1px solid rgba(56,189,248,0.15);
            font-family: var(--mono);
            font-size: 0.8rem;
            padding: 10px 16px;
        }
        .btn-toggle.active {
            background: rgba(56,189,248,0.2);
            color: var(--accent);
            border-color: var(--accent);
        }

        /* ── Loading Spinner ── */
        .loader {
            display: none;
            align-items: center;
            justify-content: center;
            gap: 12px;
            padding: 60px 20px;
            font-size: 1rem;
            color: var(--text-dim);
        }
        .loader.active { display: flex; }
        .spinner {
            width: 28px; height: 28px;
            border: 3px solid rgba(56,189,248,0.15);
            border-top: 3px solid var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* ── Error ── */
        .error-msg {
            display: none;
            padding: 16px 24px;
            border-radius: var(--radius-sm);
            background: rgba(248,113,113,0.1);
            border: 1px solid rgba(248,113,113,0.25);
            color: var(--danger);
            font-size: 0.9rem;
            margin-bottom: 20px;
            animation: slideDown 0.3s ease;
        }
        .error-msg.active { display: block; }

        /* ── Weather Content Grid ── */
        .weather-grid {
            display: none;
            gap: 24px;
            animation: fadeSlide 0.5s ease;
        }
        .weather-grid.active { display: grid; grid-template-columns: 1fr; }
        @keyframes fadeSlide {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* ── Main Weather Card ── */
        .main-card {
            border-radius: var(--radius);
            padding: 40px;
            position: relative;
            overflow: hidden;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            align-items: center;
            min-height: 320px;
        }
        .main-card::before {
            content: '';
            position: absolute; inset: 0;
            background: inherit;
            opacity: 0.5;
            z-index: 0;
        }
        .main-card::after {
            content: '';
            position: absolute; inset: 0;
            background: rgba(7,13,21,0.4);
            backdrop-filter: blur(8px);
            z-index: 0;
        }
        .main-card > * { position: relative; z-index: 1; }

        .weather-hero {
            text-align: center;
        }
        .weather-emoji {
            font-size: 6rem;
            line-height: 1;
            filter: drop-shadow(0 8px 30px rgba(0,0,0,0.3));
            animation: float 4s ease-in-out infinite;
            margin-bottom: 10px;
        }
        .temp-display {
            font-family: var(--mono);
            font-size: 4.5rem;
            font-weight: 700;
            line-height: 1.1;
            background: linear-gradient(180deg, #ffffff 20%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .temp-unit {
            font-size: 2rem;
            font-weight: 400;
            opacity: 0.6;
        }
        .weather-desc {
            font-size: 1.25rem;
            color: rgba(255,255,255,0.8);
            font-weight: 500;
            margin-top: 4px;
        }
        .weather-location {
            font-size: 1rem;
            color: rgba(255,255,255,0.55);
            margin-top: 8px;
            font-weight: 400;
        }

        .weather-details {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .detail-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .detail-item {
            background: rgba(255,255,255,0.06);
            border-radius: var(--radius-sm);
            padding: 14px 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: all var(--transition);
        }
        .detail-item:hover {
            background: rgba(255,255,255,0.1);
            transform: translateY(-2px);
        }
        .detail-icon {
            font-size: 1.4rem;
            width: 36px;
            text-align: center;
        }
        .detail-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: rgba(255,255,255,0.45);
            font-weight: 500;
        }
        .detail-value {
            font-family: var(--mono);
            font-size: 1rem;
            font-weight: 600;
            color: rgba(255,255,255,0.9);
        }
        .sun-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 2px;
        }
        .sun-item {
            background: rgba(255,255,255,0.06);
            border-radius: var(--radius-sm);
            padding: 12px 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* ── Wind Arrow ── */
        .wind-arrow {
            display: inline-block;
            transition: transform 0.8s cubic-bezier(0.4,0,0.2,1);
            font-size: 1.2rem;
        }

        /* ── Forecast Cards ── */
        .forecast-section {
            margin-top: 4px;
        }
        .section-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-dim);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-title span { font-size: 1.1rem; }
        .forecast-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 14px;
        }
        .forecast-card {
            text-align: center;
            padding: 24px 14px;
            cursor: default;
            position: relative;
            overflow: hidden;
        }
        .forecast-card::before {
            content: '';
            position: absolute; inset: 0;
            background: linear-gradient(180deg, rgba(56,189,248,0.04) 0%, transparent 100%);
            opacity: 0;
            transition: opacity var(--transition);
        }
        .forecast-card:hover::before { opacity: 1; }
        .forecast-card:hover {
            transform: translateY(-4px);
            border-color: var(--glass-border-hover);
            box-shadow: 0 8px 32px rgba(56,189,248,0.08);
        }
        .fc-day {
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--accent);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .fc-date {
            font-size: 0.7rem;
            color: var(--text-muted);
            margin-top: 2px;
        }
        .fc-emoji {
            font-size: 2.8rem;
            margin: 14px 0 10px;
            filter: drop-shadow(0 4px 12px rgba(0,0,0,0.2));
        }
        .fc-temps {
            font-family: var(--mono);
            font-size: 0.95rem;
            font-weight: 600;
        }
        .fc-high { color: #fbbf24; }
        .fc-low { color: #60a5fa; }
        .fc-sep { color: var(--text-muted); margin: 0 4px; }
        .fc-desc {
            font-size: 0.72rem;
            color: var(--text-muted);
            margin-top: 8px;
            font-weight: 400;
        }

        /* ── Bottom Info Card ── */
        .bottom-card {
            margin-top: 4px;
            padding: 20px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
        }
        .bottom-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .bottom-icon { font-size: 1.5rem; }
        .bottom-text {
            font-size: 0.85rem;
            color: var(--text-dim);
        }
        .bottom-text strong {
            color: var(--text);
            font-weight: 600;
        }
        .timestamp {
            font-family: var(--mono);
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        /* ── Welcome State ── */
        .welcome {
            text-align: center;
            padding: 80px 20px;
        }
        .welcome-emoji {
            font-size: 5rem;
            margin-bottom: 20px;
            animation: float 3s ease-in-out infinite;
        }
        .welcome h2 {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #38bdf8, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .welcome p {
            color: var(--text-muted);
            font-size: 1rem;
            max-width: 400px;
            margin: 0 auto;
            line-height: 1.6;
        }

        /* ── Audio Context Visual Indicator ── */
        .sound-on::after {
            content: '🔊';
            font-size: 0.6rem;
            margin-left: 4px;
        }

        /* ── Responsive ── */
        @media (max-width: 900px) {
            .main-card {
                grid-template-columns: 1fr;
                padding: 28px 20px;
            }
            .forecast-grid {
                grid-template-columns: repeat(5, 1fr);
                gap: 8px;
            }
            .forecast-card { padding: 16px 8px; }
            .fc-emoji { font-size: 2rem; }
            .search-box { min-width: 220px; }
        }
        @media (max-width: 640px) {
            .header { justify-content: center; text-align: center; }
            .search-area { justify-content: center; }
            .forecast-grid {
                grid-template-columns: repeat(3, 1fr);
            }
            .weather-emoji { font-size: 4rem; }
            .temp-display { font-size: 3rem; }
            .detail-grid { grid-template-columns: 1fr; }
            .bottom-card { justify-content: center; text-align: center; }
        }

        /* ── Animations ── */
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.04); }
        }
        .pulse { animation: pulse 2s ease-in-out infinite; }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- ── Header ── -->
        <header class="header">
            <div class="brand">
                <div class="brand-icon">⛅</div>
                <div>
                    <h1>Pinacle Weather</h1>
                    <div class="brand-tag">Real-time Forecast</div>
                </div>
            </div>
            <div class="search-area">
                <div class="search-box">
                    <input type="text" id="cityInput" placeholder="Search city..." autocomplete="off"
                           onkeydown="if(event.key==='Enter') searchWeather()">
                    <button class="btn btn-primary" onclick="searchWeather()">
                        🔍 Search
                    </button>
                </div>
                <button class="btn btn-secondary" onclick="autoDetect()">
                    📍 Auto-detect
                </button>
                <div style="display:flex; gap:4px;">
                    <button class="btn btn-toggle active" id="btnC" onclick="setUnits('celsius')">°C</button>
                    <button class="btn btn-toggle" id="btnF" onclick="setUnits('fahrenheit')">°F</button>
                </div>
            </div>
        </header>

        <!-- ── Error ── -->
        <div class="error-msg" id="errorMsg"></div>

        <!-- ── Welcome ── -->
        <div class="welcome glass" id="welcomeCard">
            <div class="welcome-emoji">🌍</div>
            <h2>Welcome to Pinacle Weather</h2>
            <p>Search for any city or auto-detect your location to get a beautiful real-time weather forecast.</p>
        </div>

        <!-- ── Loader ── -->
        <div class="loader" id="loader">
            <div class="spinner"></div>
            Fetching weather data...
        </div>

        <!-- ── Weather Content ── -->
        <div class="weather-grid" id="weatherGrid">
            <!-- Main Card -->
            <div class="main-card" id="mainCard">
                <div class="weather-hero">
                    <div class="weather-emoji" id="wEmoji"></div>
                    <div class="temp-display">
                        <span id="wTemp"></span><span class="temp-unit" id="wUnit"></span>
                    </div>
                    <div class="weather-desc" id="wDesc"></div>
                    <div class="weather-location" id="wLocation"></div>
                </div>
                <div class="weather-details">
                    <div class="detail-grid">
                        <div class="detail-item">
                            <div class="detail-icon">
                                <span class="wind-arrow" id="windArrow">➤</span>
                            </div>
                            <div>
                                <div class="detail-label">Wind</div>
                                <div class="detail-value" id="wWind"></div>
                            </div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-icon">💧</div>
                            <div>
                                <div class="detail-label">Humidity</div>
                                <div class="detail-value" id="wHumidity"></div>
                            </div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-icon">🔵</div>
                            <div>
                                <div class="detail-label">Pressure</div>
                                <div class="detail-value" id="wPressure"></div>
                            </div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-icon">👁️</div>
                            <div>
                                <div class="detail-label">Visibility</div>
                                <div class="detail-value" id="wVisibility"></div>
                            </div>
                        </div>
                    </div>
                    <div class="sun-row">
                        <div class="sun-item">
                            <div class="detail-icon">🌅</div>
                            <div>
                                <div class="detail-label">Sunrise</div>
                                <div class="detail-value" id="wSunrise"></div>
                            </div>
                        </div>
                        <div class="sun-item">
                            <div class="detail-icon">🌇</div>
                            <div>
                                <div class="detail-label">Sunset</div>
                                <div class="detail-value" id="wSunset"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Forecast -->
            <div class="forecast-section">
                <div class="section-title"><span>📅</span> 5-Day Forecast</div>
                <div class="forecast-grid" id="forecastGrid"></div>
            </div>

            <!-- Bottom Info -->
            <div class="bottom-card glass">
                <div class="bottom-left">
                    <div class="bottom-icon">🌐</div>
                    <div class="bottom-text">
                        Powered by <strong>Open-Meteo</strong> &amp; <strong>OpenStreetMap</strong> — Free, no API key needed
                    </div>
                </div>
                <div class="timestamp" id="wTimestamp"></div>
            </div>
        </div>
    </div>

    <script>
        // ── State ──
        let currentUnits = 'celsius';
        let lastCity = '';
        let audioCtx = null;

        // ── Audio Feedback ──
        function initAudio() {
            if (!audioCtx) {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
        }
        function playTone(freq, duration, type='sine') {
            try {
                initAudio();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = type;
                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start();
                osc.stop(audioCtx.currentTime + duration);
            } catch(e) {}
        }
        function playSuccess() {
            playTone(523, 0.12);
            setTimeout(() => playTone(659, 0.12), 80);
            setTimeout(() => playTone(784, 0.18), 160);
        }
        function playError() {
            playTone(330, 0.15, 'square');
            setTimeout(() => playTone(262, 0.25, 'square'), 120);
        }
        function playClick() {
            playTone(880, 0.05);
        }

        // ── Units ──
        function setUnits(u) {
            playClick();
            currentUnits = u;
            document.getElementById('btnC').classList.toggle('active', u === 'celsius');
            document.getElementById('btnF').classList.toggle('active', u === 'fahrenheit');
            if (lastCity) searchWeather(lastCity);
        }

        // ── UI helpers ──
        function showEl(id, cls='active') { document.getElementById(id).classList.add(cls); }
        function hideEl(id, cls='active') { document.getElementById(id).classList.remove(cls); }
        function setErr(msg) {
            const el = document.getElementById('errorMsg');
            el.textContent = msg;
            if (msg) showEl('errorMsg'); else hideEl('errorMsg');
        }

        // ── Search ──
        async function searchWeather(city) {
            city = city || document.getElementById('cityInput').value.trim();
            if (!city) { setErr('Please enter a city name.'); playError(); return; }
            lastCity = city;
            setErr('');
            hideEl('welcomeCard', 'glass');
            document.getElementById('welcomeCard').style.display = 'none';
            hideEl('weatherGrid');
            showEl('loader');

            try {
                const resp = await fetch(`/api/weather?city=${encodeURIComponent(city)}&units=${currentUnits}`);
                const data = await resp.json();
                if (data.error) {
                    hideEl('loader');
                    setErr(data.error);
                    playError();
                    return;
                }
                hideEl('loader');
                renderWeather(data);
                playSuccess();
            } catch(e) {
                hideEl('loader');
                setErr('Network error. Please try again.');
                playError();
            }
        }

        // ── Auto-detect ──
        async function autoDetect() {
            playClick();
            setErr('');
            document.getElementById('welcomeCard').style.display = 'none';
            hideEl('weatherGrid');
            showEl('loader');

            try {
                const resp = await fetch(`/api/weather/auto?units=${currentUnits}`);
                const data = await resp.json();
                if (data.error) {
                    hideEl('loader');
                    setErr(data.error);
                    playError();
                    return;
                }
                hideEl('loader');
                lastCity = data.current.city;
                document.getElementById('cityInput').value = data.current.city;
                renderWeather(data);
                playSuccess();
            } catch(e) {
                hideEl('loader');
                setErr('Could not detect location. Try searching manually.');
                playError();
            }
        }

        // ── Render ──
        function renderWeather(data) {
            const c = data.current;
            const f = data.forecast;

            // Main card gradient
            const mainCard = document.getElementById('mainCard');
            mainCard.style.background = c.gradient;

            // Hero
            document.getElementById('wEmoji').textContent = c.emoji;
            document.getElementById('wTemp').textContent = Math.round(c.temp);
            document.getElementById('wUnit').textContent = c.unit_sym;
            document.getElementById('wDesc').textContent = c.description;
            document.getElementById('wLocation').textContent = `📍 ${c.city}${c.country ? ', ' + c.country : ''}`;

            // Details
            document.getElementById('wWind').textContent = `${c.wind_speed} ${c.wind_unit}`;
            document.getElementById('wHumidity').textContent = `${c.humidity}%`;
            document.getElementById('wPressure').textContent = `${c.pressure} hPa`;
            document.getElementById('wVisibility').textContent = `${c.visibility} km`;
            document.getElementById('wSunrise').textContent = c.sunrise;
            document.getElementById('wSunset').textContent = c.sunset;
            document.getElementById('wTimestamp').textContent = `Updated: ${c.updated_at}`;

            // Wind arrow rotation
            const arrow = document.getElementById('windArrow');
            arrow.style.transform = `rotate(${c.wind_dir}deg)`;

            // Forecast
            const grid = document.getElementById('forecastGrid');
            grid.innerHTML = '';
            f.forEach((day, i) => {
                const card = document.createElement('div');
                card.className = 'forecast-card glass';
                card.style.animationDelay = `${i * 0.08}s`;
                card.innerHTML = `
                    <div class="fc-day">${day.day}</div>
                    <div class="fc-date">${day.date}</div>
                    <div class="fc-emoji">${day.emoji}</div>
                    <div class="fc-temps">
                        <span class="fc-high">${Math.round(day.temp_max)}°</span>
                        <span class="fc-sep">/</span>
                        <span class="fc-low">${Math.round(day.temp_min)}°</span>
                    </div>
                    <div class="fc-desc">${day.description}</div>
                `;
                grid.appendChild(card);
            });

            showEl('weatherGrid');
        }

        // ── Init: focus search ──
        document.getElementById('cityInput').focus();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/weather")
def api_weather():
    city = request.args.get("city", "").strip()
    units = request.args.get("units", "celsius").strip()
    if not city:
        return jsonify({"error": "Missing 'city' parameter."}), 400

    location = _geocode_nominatim(city)
    if not location:
        return jsonify({"error": f"Could not find '{city}'. Try a different spelling."}), 404

    meteo = _fetch_open_meteo(location["lat"], location["lon"], units)
    if not meteo:
        return jsonify({"error": "Weather data unavailable. Please try again."}), 502

    result = _build_weather_response(location, meteo, units)
    return jsonify(result)


@app.route("/api/weather/auto")
def api_weather_auto():
    units = request.args.get("units", "celsius").strip()

    location = _detect_ip_location()
    if not location:
        return jsonify({"error": "Could not detect your location. Try searching manually."}), 500

    meteo = _fetch_open_meteo(location["lat"], location["lon"], units)
    if not meteo:
        return jsonify({"error": "Weather data unavailable. Please try again."}), 502

    result = _build_weather_response(location, meteo, units)
    return jsonify(result)


# ── CLI mode (original) ──────────────────────────────────────

def fetch_and_display(location: dict, units: str):
    """Given a resolved location dict, fetch weather and show it."""
    lat, lon = location["lat"], location["lon"]

    if _is_demo():
        show_info(
            "⚠  Running in DEMO MODE – add your API key to weather_config.py "
            "for live data."
        )
        current_raw = DEMO_CURRENT
        forecast_raw = DEMO_FORECAST
    else:
        show_info("Fetching current weather …")
        current_raw = get_current_weather(lat, lon, units)
        if not current_raw:
            show_error("Could not retrieve current weather.")
            return

        show_info("Fetching 5-day forecast …")
        forecast_raw = get_forecast(lat, lon, units)

    current_parsed = parse_current(current_raw, units)
    show_current(current_parsed)

    if forecast_raw:
        forecast_days = parse_daily_forecast(forecast_raw, units)
        show_forecast(forecast_days)


def resolve_location(city_name: str) -> dict | None:
    """Geocode a city name; in demo mode return mock coords."""
    if _is_demo():
        return {"city": city_name or "London", "country": "GB",
                "lat": 51.5074, "lon": -0.1278}
    return geocode_city(city_name)


def cli_main():
    """Original terminal interface."""
    show_banner()

    if _is_demo():
        console.print(
            "[bold yellow]DEMO MODE active.[/]  "
            "Edit [bold]weather_config.py[/] and set your free "
            "[bold]API_KEY[/] from [link]https://openweathermap.org/api[/link] "
            "to fetch live weather.\n"
        )

    units = DEFAULT_UNITS
    location = None

    while True:
        choice = show_menu()

        if choice == "1":
            city = ask_city()
            if not city:
                show_error("City name cannot be empty.")
                continue
            show_info(f"Resolving '{city}' …")
            location = resolve_location(city)
            if not location:
                show_error(f"Could not find '{city}'. Try a different spelling.")
                continue
            fetch_and_display(location, units)

        elif choice == "2":
            show_info("Detecting your location via IP …")
            if _is_demo():
                location = {"city": "Your City (demo)", "country": "XX",
                            "lat": 51.5074, "lon": -0.1278}
                show_info(f"Detected (demo): {location['city']}, {location['country']}")
            else:
                location = detect_location_by_ip()
                if not location:
                    show_error("Auto-detection failed. Try entering a city manually.")
                    continue
                show_info(f"Detected: {location['city']}, {location['country']}")
            fetch_and_display(location, units)

        elif choice == "3":
            units = ask_units()
            console.print(f"[green]Units switched to:[/] {units}\n")
            if location:
                fetch_and_display(location, units)

        elif choice in ("4", "q", "exit", "quit"):
            console.print("[bold cyan]Goodbye! Stay weather-aware! 🌤[/]")
            break

        else:
            show_error("Invalid option. Please enter 1–4.")


# ── Entry Point ──────────────────────────────────────────────

def _print_banner():
    banner = r"""
    ╔══════════════════════════════════════════════════════════╗
    ║           ⛅  PINACLE WEATHER  ·  Flask UI              ║
    ║──────────────────────────────────────────────────────────║
    ║   Port  : 5007                                          ║
    ║   URL   : http://localhost:5007                         ║
    ║   API   : Open-Meteo (free, no key)                     ║
    ║   Stop  : Ctrl+C                                        ║
    ╚══════════════════════════════════════════════════════════╝
    """
    print(banner)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        try:
            cli_main()
        except KeyboardInterrupt:
            console.print("\n[bold cyan]Goodbye![/]")
            sys.exit(0)
    else:
        _print_banner()
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5007")).start()
        app.run(host="0.0.0.0", port=5007, debug=False)
