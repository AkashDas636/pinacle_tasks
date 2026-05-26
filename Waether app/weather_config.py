# ============================================================
#  weather_config.py  –  Configuration for Weather Forecast App
# ============================================================

# -----------------------------------------------------------
# Replace with your real key from https://openweathermap.org/
# Free tier supports current weather + 5-day forecast
# -----------------------------------------------------------
API_KEY = "YOUR_OPENWEATHERMAP_API_KEY"

BASE_URL        = "https://api.openweathermap.org/data/2.5"
GEO_URL         = "http://api.openweathermap.org/geo/1.0"
IP_GEO_URL      = "http://ip-api.com/json"          # free, no key needed
DEFAULT_UNITS   = "metric"                           # metric | imperial | standard
DEFAULT_CITY    = "London"

UNITS_SYMBOL = {
    "metric":   "°C",
    "imperial": "°F",
    "standard": "K",
}

WIND_UNIT = {
    "metric":   "m/s",
    "imperial": "mph",
    "standard": "m/s",
}

# Weather condition code → friendly emoji
WEATHER_EMOJI = {
    "Clear":        "☀️",
    "Clouds":       "☁️",
    "Rain":         "🌧️",
    "Drizzle":      "🌦️",
    "Thunderstorm": "⛈️",
    "Snow":         "❄️",
    "Mist":         "🌫️",
    "Smoke":        "🌫️",
    "Haze":         "🌫️",
    "Dust":         "🌪️",
    "Fog":          "🌫️",
    "Sand":         "🌪️",
    "Ash":          "🌋",
    "Squall":       "💨",
    "Tornado":      "🌪️",
}
