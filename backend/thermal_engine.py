import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data" / "weather_150.json"
OUTPUT_FILE = BASE_DIR / "data" / "thermal_forecast_150.json"


# =========================================================
# HEAT INDEX
# NWS / Rothfusz regression
# =========================================================

def celsius_to_fahrenheit(c):
    return (c * 9 / 5) + 32


def fahrenheit_to_celsius(f):
    return (f - 32) * 5 / 9


def calculate_heat_index(temp_c, rh):

    T = celsius_to_fahrenheit(temp_c)
    R = rh

    # Simple approximation used for lower heat-index conditions
    simple_hi = (
        0.5 * (
            T
            + 61.0
            + ((T - 68.0) * 1.2)
            + (R * 0.094)
        )
    )

    simple_hi = (simple_hi + T) / 2

    if simple_hi < 80:
        return round(fahrenheit_to_celsius(simple_hi), 2)

    # Rothfusz regression
    HI = (
        -42.379
        + 2.04901523 * T
        + 10.14333127 * R
        - 0.22475541 * T * R
        - 0.00683783 * T * T
        - 0.05481717 * R * R
        + 0.00122874 * T * T * R
        + 0.00085282 * T * R * R
        - 0.00000199 * T * T * R * R
    )

    # Low humidity adjustment
    if R < 13 and 80 <= T <= 112:

        adjustment = (
            ((13 - R) / 4)
            * ((17 - abs(T - 95)) / 17) ** 0.5
        )

        HI -= adjustment

    # High humidity adjustment
    elif R > 85 and 80 <= T <= 87:

        adjustment = (
            ((R - 85) / 10)
            * ((87 - T) / 5)
        )

        HI += adjustment

    return round(fahrenheit_to_celsius(HI), 2)


# =========================================================
# HEAT-INDEX BASE RISK
# =========================================================

def heat_index_risk(hi):

    """
    Converts apparent temperature into a 0-100
    relative thermal-risk score.

    This is NOT probability of illness or death.
    """

    if hi < 27:
        return 5

    if hi < 32:
        # 27 -> 32 gives 5 -> 35
        return 5 + ((hi - 27) / 5) * 30

    if hi < 39:
        # 32 -> 39 gives 35 -> 70
        return 35 + ((hi - 32) / 7) * 35

    if hi < 51:
        # 39 -> 51 gives 70 -> 95
        return 70 + ((hi - 39) / 12) * 25

    return 100


# =========================================================
# ENVIRONMENTAL MODIFIER
# =========================================================

def environmental_modifier(
    temp_c,
    humidity,
    wind_kmh,
    solar_wm2
):

    modifier = 0

    # High humidity makes heat harder to dissipate.
    if humidity >= 70:
        modifier += 5
    elif humidity >= 60:
        modifier += 3

    # Very low wind reduces convective cooling.
    if wind_kmh < 5:
        modifier += 4
    elif wind_kmh < 10:
        modifier += 2

    # Strong solar load.
    if solar_wm2 >= 800:
        modifier += 3
    elif solar_wm2 >= 500:
        modifier += 1

    return modifier


# =========================================================
# FINAL BHARAT-SHIELD RISK
# =========================================================

def calculate_risk(
    temp_c,
    humidity,
    wind_kmh,
    solar_wm2,
    heat_index
):

    # Heat Index is already derived from
    # temperature + relative humidity.
    # Do not double-count humidity.

    score = heat_index_risk(heat_index)

    return round(score, 1)

# =========================================================
# RISK LEVEL
# =========================================================

def risk_level(score):

    if score >= 75:
        return "EXTREME"

    if score >= 50:
        return "HIGH"

    if score >= 25:
        return "MODERATE"

    return "LOW"


# =========================================================
# LOAD WEATHER
# =========================================================

print("Loading 150-city weather forecast...")

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    cities = json.load(f)


results = []


# =========================================================
# PROCESS EACH CITY
# =========================================================

for city in cities:

    hourly = city["hourly"]

    times = hourly["time"]
    temperatures = hourly["temperature_2m"]
    humidities = hourly["relative_humidity_2m"]
    winds = hourly["wind_speed_10m"]
    solar = hourly["shortwave_radiation"]

    forecast = []

    for i in range(len(times)):

        temp = temperatures[i]
        humidity = humidities[i]
        wind = winds[i]
        radiation = solar[i]

        if any(
            value is None
            for value in [
                temp,
                humidity,
                wind,
                radiation
            ]
        ):
            continue

        hi = calculate_heat_index(
            temp,
            humidity
        )

        risk = calculate_risk(
            temp,
            humidity,
            wind,
            radiation,
            hi
        )

        forecast.append({
            "time": times[i],

            "temperature_c": round(temp, 2),
            "humidity_percent": round(humidity, 2),
            "wind_kmh": round(wind, 2),
            "solar_wm2": round(radiation, 2),

            "heat_index_c": hi,

            "risk_score": risk,
            "risk_level": risk_level(risk)
        })


    if not forecast:
        continue


    # Current = first available forecast point
    current = forecast[0]

    # Find maximum-risk period
    peak = max(
        forecast,
        key=lambda x: x["risk_score"]
    )


    results.append({

        "name": city["name"],
        "state": city["state"],

        "latitude": city["latitude"],
        "longitude": city["longitude"],

        "current": current,

        "peak": peak,

        "forecast": forecast
    })


# =========================================================
# SAVE
# =========================================================

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)


print()
print("============================================")
print("       BHARAT-SHIELD THERMAL ENGINE")
print("============================================")
print(f"Cities processed : {len(results)}")
print(f"Forecast hours   : 72")
print(f"Output           : {OUTPUT_FILE}")
print("============================================")