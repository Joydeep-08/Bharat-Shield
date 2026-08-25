import json
import requests
from pathlib import Path

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CITY_FILE = BASE_DIR / "data" / "india_top150_cities.geojson"
OUTPUT_FILE = BASE_DIR / "data" / "weather_150.json"

# -----------------------------
# Load cities
# -----------------------------
with open(CITY_FILE, "r", encoding="utf-8") as f:
    geojson = json.load(f)

cities = geojson["features"]

latitudes = []
longitudes = []

for city in cities:
    lon, lat = city["geometry"]["coordinates"]
    latitudes.append(lat)
    longitudes.append(lon)

# -----------------------------
# Open-Meteo request
# -----------------------------
params = {
    "latitude": ",".join(map(str, latitudes)),
    "longitude": ",".join(map(str, longitudes)),
    "hourly": ",".join([
        "temperature_2m",
        "relative_humidity_2m",
        "wind_speed_10m",
        "shortwave_radiation"
    ]),
    "forecast_days": 3,
    "timezone": "auto",
    "wind_speed_unit": "kmh",
    "temperature_unit": "celsius"
}

print("Fetching weather for 150 cities...")

response = requests.get(
    "https://api.open-meteo.com/v1/forecast",
    params=params,
    timeout=60
)

response.raise_for_status()
weather_data = response.json()

# -----------------------------
# Combine city metadata + weather
# -----------------------------
output = []

for i, city in enumerate(cities):

    weather = weather_data[i]

    output.append({
        "name": city["properties"]["name"],
        "state": city["properties"]["state"],
        "population": city["properties"]["population"],
        "tier": city["properties"]["tier"],
        "latitude": city["geometry"]["coordinates"][1],
        "longitude": city["geometry"]["coordinates"][0],
        "timezone": weather.get("timezone"),
        "hourly": weather["hourly"]
    })

# -----------------------------
# Save
# -----------------------------
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print(f"Done! Saved to: {OUTPUT_FILE}")
print(f"Cities: {len(output)}")