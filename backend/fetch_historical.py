import json
import time
import requests
from pathlib import Path

# ==========================================
# BHARAT-SHIELD
# BATCH HISTORICAL WEATHER DOWNLOADER
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

CITY_FILE = BASE_DIR / "data" / "india_top150_cities.geojson"
OUTPUT_DIR = BASE_DIR / "data" / "historical"

START_DATE = "2022-01-01"
END_DATE = "2025-12-31"

BATCH_SIZE = 10

VARIABLES = ",".join([
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "wind_speed_10m",
    "shortwave_radiation",
    "pressure_msl",
])

API_URL = "https://archive-api.open-meteo.com/v1/archive"


# ==========================================
# SETUP
# ==========================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================
# LOAD CITIES
# ==========================================

with open(CITY_FILE, "r") as f:
    geojson = json.load(f)


cities = []

for feature in geojson["features"]:

    props = feature["properties"]
    coords = feature["geometry"]["coordinates"]

    cities.append({
        "name": props["name"],
        "state": props["state"],
        "latitude": coords[1],
        "longitude": coords[0],
    })


# ==========================================
# SAFE FILE NAME
# ==========================================

def filename(city):

    name = city["name"].lower()

    name = (
        name
        .replace(" ", "_")
        .replace("/", "_")
        .replace(".", "")
    )

    return OUTPUT_DIR / f"{name}.json"


# ==========================================
# FIND ALREADY DOWNLOADED CITIES
# ==========================================

remaining = []

for city in cities:

    path = filename(city)

    if path.exists():

        print(
            f"✓ {city['name']} already downloaded"
        )

    else:

        remaining.append(city)


print()
print("=" * 65)
print("       BHARAT-SHIELD HISTORICAL WEATHER")
print("=" * 65)

print(
    f"Total cities      : {len(cities)}"
)

print(
    f"Already downloaded: {len(cities) - len(remaining)}"
)

print(
    f"Remaining         : {len(remaining)}"
)

print(
    f"Period            : {START_DATE} → {END_DATE}"
)

print(
    f"Batch size        : {BATCH_SIZE}"
)

print("=" * 65)


# ==========================================
# PROCESS BATCHES
# ==========================================

for batch_start in range(
    0,
    len(remaining),
    BATCH_SIZE
):

    batch = remaining[
        batch_start:
        batch_start + BATCH_SIZE
    ]

    print()
    print(
        f"--- BATCH "
        f"{batch_start // BATCH_SIZE + 1}"
        f" ---"
    )

    print(
        ", ".join(
            c["name"]
            for c in batch
        )
    )


    # --------------------------------------
    # Coordinates
    # --------------------------------------

    latitudes = ",".join(
        str(c["latitude"])
        for c in batch
    )

    longitudes = ",".join(
        str(c["longitude"])
        for c in batch
    )


    params = {

        "latitude": latitudes,

        "longitude": longitudes,

        "start_date": START_DATE,

        "end_date": END_DATE,

        "hourly": VARIABLES,

        "timezone": "GMT",

        "temperature_unit": "celsius",

        "wind_speed_unit": "kmh",
    }


    # --------------------------------------
    # Request with retries
    # --------------------------------------

    data = None

    for attempt in range(1, 6):

        try:

            print(
                f"Request attempt {attempt}/5..."
            )

            response = requests.get(
                API_URL,
                params=params,
                timeout=180,
            )


            if response.status_code == 429:

                wait = 60 * attempt

                print(
                    f"Rate limited. "
                    f"Waiting {wait}s..."
                )

                time.sleep(wait)

                continue


            response.raise_for_status()

            data = response.json()

            break


        except Exception as e:

            print(
                f"Request failed: {e}"
            )

            if attempt < 5:

                wait = 20 * attempt

                print(
                    f"Waiting {wait}s..."
                )

                time.sleep(wait)


    # --------------------------------------
    # Failed batch
    # --------------------------------------

    if data is None:

        print(
            "❌ Batch failed."
        )

        print(
            "Waiting 2 minutes before continuing..."
        )

        time.sleep(120)

        continue


    # ======================================
    # MULTI-LOCATION RESPONSE
    # ======================================

    if isinstance(data, dict):

        results = [data]

    else:

        results = data


    print(
        f"Received {len(results)} locations"
    )


    # ======================================
    # SAVE EACH CITY INDEPENDENTLY
    # ======================================

    for city, weather in zip(
        batch,
        results
    ):

        path = filename(city)


        output = {

            "name": city["name"],

            "state": city["state"],

            "latitude": city["latitude"],

            "longitude": city["longitude"],

            "timezone": weather.get(
                "timezone",
                "GMT"
            ),

            "hourly": weather.get(
                "hourly",
                {}
            ),

        }


        # Atomic write
        temp_path = path.with_suffix(
            ".tmp"
        )


        with open(
            temp_path,
            "w"
        ) as f:

            json.dump(
                output,
                f,
                separators=(",", ":")
            )


        temp_path.replace(path)


        hours = len(
            output["hourly"].get(
                "time",
                []
            )
        )


        print(
            f"  ✓ {city['name']:<25} "
            f"{hours:,} hours"
        )


    print(
        "Batch saved successfully."
    )


    # Don't hammer the API
    print(
        "Waiting 10 seconds..."
    )

    time.sleep(10)


# ==========================================
# FINISHED
# ==========================================

downloaded = 0

for city in cities:

    if filename(city).exists():

        downloaded += 1


print()
print("=" * 65)
print("DOWNLOAD STATUS")
print("=" * 65)

print(
    f"Cities downloaded : "
    f"{downloaded}/{len(cities)}"
)

print(
    f"Storage directory : "
    f"{OUTPUT_DIR}"
)

print("=" * 65)