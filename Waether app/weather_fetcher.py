# ============================================================
#  weather_fetcher.py  –  API calls & data helpers
# ============================================================
import requests
from datetime import datetime
from weather_config import (
    API_KEY, BASE_URL, GEO_URL, IP_GEO_URL,
    DEFAULT_UNITS, UNITS_SYMBOL, WIND_UNIT, WEATHER_EMOJI,
)


# ── helpers ─────────────────────────────────────────────────

def _get(url: str, params: dict) -> dict | None:
    """Thin wrapper around requests.get with timeout handling."""
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        print("  ✗ No internet connection.")
    except requests.exceptions.Timeout:
        print("  ✗ Request timed out.")
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code
        if code == 401:
            print("  ✗ Invalid API key – check weather_config.py.")
        elif code == 404:
            print("  ✗ City not found.")
        else:
            print(f"  ✗ HTTP error {code}.")
    except Exception as exc:
        print(f"  ✗ Unexpected error: {exc}")
    return None


# ── location detection ───────────────────────────────────────

def detect_location_by_ip() -> dict | None:
    """Return city/country via IP geolocation (no API key needed)."""
    data = _get(IP_GEO_URL, {})
    if data and data.get("status") == "success":
        return {
            "city":    data.get("city", ""),
            "country": data.get("country", ""),
            "lat":     data.get("lat"),
            "lon":     data.get("lon"),
        }
    return None


def geocode_city(city: str) -> dict | None:
    """Convert a city name to lat/lon using OpenWeatherMap Geocoding API."""
    data = _get(f"{GEO_URL}/direct", {"q": city, "limit": 1, "appid": API_KEY})
    if data:
        loc = data[0]
        return {
            "city":    loc.get("name", city),
            "country": loc.get("country", ""),
            "lat":     loc["lat"],
            "lon":     loc["lon"],
        }
    return None


# ── weather data ─────────────────────────────────────────────

def get_current_weather(lat: float, lon: float, units: str = DEFAULT_UNITS) -> dict | None:
    return _get(f"{BASE_URL}/weather", {
        "lat":   lat, "lon": lon,
        "units": units, "appid": API_KEY,
    })


def get_forecast(lat: float, lon: float, units: str = DEFAULT_UNITS) -> dict | None:
    """5-day / 3-hour forecast."""
    return _get(f"{BASE_URL}/forecast", {
        "lat":   lat, "lon": lon,
        "units": units, "appid": API_KEY,
    })


# ── parsing helpers ──────────────────────────────────────────

def parse_current(data: dict, units: str = DEFAULT_UNITS) -> dict:
    main     = data.get("main", {})
    wind     = data.get("wind", {})
    weather  = data.get("weather", [{}])[0]
    sys      = data.get("sys", {})
    cond     = weather.get("main", "")
    return {
        "city":        data.get("name", ""),
        "country":     sys.get("country", ""),
        "temp":        main.get("temp"),
        "feels_like":  main.get("feels_like"),
        "temp_min":    main.get("temp_min"),
        "temp_max":    main.get("temp_max"),
        "humidity":    main.get("humidity"),
        "pressure":    main.get("pressure"),
        "visibility":  data.get("visibility", 0) / 1000,  # metres → km
        "wind_speed":  wind.get("speed"),
        "wind_dir":    wind.get("deg", 0),
        "description": weather.get("description", "").title(),
        "condition":   cond,
        "emoji":       WEATHER_EMOJI.get(cond, "🌡️"),
        "sunrise":     datetime.fromtimestamp(sys.get("sunrise", 0)).strftime("%H:%M"),
        "sunset":      datetime.fromtimestamp(sys.get("sunset",  0)).strftime("%H:%M"),
        "unit_sym":    UNITS_SYMBOL[units],
        "wind_unit":   WIND_UNIT[units],
        "updated_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def parse_daily_forecast(data: dict, units: str = DEFAULT_UNITS) -> list[dict]:
    """Group 3-hour slots into daily summaries (next 5 days)."""
    days: dict[str, list] = {}
    for item in data.get("list", []):
        day = datetime.fromtimestamp(item["dt"]).strftime("%Y-%m-%d")
        days.setdefault(day, []).append(item)

    result = []
    for day, slots in list(days.items())[:6]:          # up to 6 days
        temps   = [s["main"]["temp"] for s in slots]
        cond    = slots[len(slots)//2]["weather"][0]["main"]
        desc    = slots[len(slots)//2]["weather"][0]["description"].title()
        result.append({
            "date":      datetime.strptime(day, "%Y-%m-%d").strftime("%a, %d %b"),
            "temp_min":  round(min(temps), 1),
            "temp_max":  round(max(temps), 1),
            "condition": cond,
            "emoji":     WEATHER_EMOJI.get(cond, "🌡️"),
            "description": desc,
            "unit_sym":  UNITS_SYMBOL[units],
        })
    return result
