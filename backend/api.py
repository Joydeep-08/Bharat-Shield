from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.inference import predict_city

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import threading
import time


app = FastAPI(
    title="Bharat-Shield API",
    description="National Thermal Risk Early Warning API",
    version="1.0.0",
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CITIES_FILE = BASE_DIR / "data" / "india_top150_cities.geojson"


# ============================================================
# LIVE CACHE
# ============================================================

CITY_CACHE = []
CACHE_TIME = 0

# Refresh every 30 minutes
CACHE_TTL = 30 * 60

CACHE_LOCK = threading.Lock()


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "bharat-shield-api",
        "model": "thermal_72h_xgb",
        "cities_cached": len(CITY_CACHE),
        "cache_age_seconds": (
            round(time.time() - CACHE_TIME, 1)
            if CACHE_TIME
            else None
        ),
    }


# ============================================================
# LOAD CITY COORDINATES
# ============================================================

def load_cities():

    with open(CITIES_FILE, "r") as f:
        geojson = json.load(f)

    cities = []

    for feature in geojson["features"]:

        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]

        cities.append({
            "name": props.get("name", "Unknown"),
            "state": props.get("state", ""),
            "latitude": float(coords[1]),
            "longitude": float(coords[0]),
        })

    return cities


# ============================================================
# PREDICT ONE CITY
# ============================================================

def process_city(city):

    max_attempts = 4

    for attempt in range(max_attempts):

        try:

            prediction = predict_city(
                city["latitude"],
                city["longitude"]
            )

            peak_hi = prediction["prediction_max_heat_index_72h"]
            current_hi = prediction["current_heat_index"]

            risk_level = prediction["risk"]

            risk_score = round(
                min(100, max(0, (peak_hi / 50) * 100))
            )

            return {
                "name": city["name"],
                "state": city["state"],
                "latitude": city["latitude"],
                "longitude": city["longitude"],

                "current": {
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "heat_index_c": current_hi,
                    "temperature_c": prediction.get("temperature_c"),
                    "humidity_percent": prediction.get("humidity_percent"),
                    "wind_kmh": prediction.get("wind_kmh"),
                    "solar_wm2": prediction.get("solar_wm2"),
                },

                "peak": {
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "heat_index_c": peak_hi,
                    "time": prediction["timestamp"],
                },
            }

        except Exception as e:

            error_text = str(e)

            if "429" in error_text and attempt < max_attempts - 1:

                wait_time = 2 ** attempt

                print(
                    f"[RETRY] {city['name']} "
                    f"rate limited. "
                    f"Retrying in {wait_time}s..."
                )

                time.sleep(wait_time)

            else:

                raise


# ============================================================
# REFRESH ALL 150 CITIES
# ============================================================

def refresh_city_cache():

    global CITY_CACHE
    global CACHE_TIME

    cities = load_cities()

    results = []

    print(
        f"[BHARAT-SHIELD] Refreshing {len(cities)} cities..."
    )

    start = time.time()

    # Parallel weather/model inference.
    # Keep this moderate to avoid hammering Open-Meteo.
    with ThreadPoolExecutor(max_workers=5) as executor:

        futures = {
            executor.submit(process_city, city): city
            for city in cities
        }

        for future in as_completed(futures):

            city = futures[future]

            try:
                results.append(
                    future.result()
                )

            except Exception as e:

                print(
                    f"[ERROR] {city['name']}: {e}"
                )

    # Keep original geographic ordering
    order = {
        city["name"]: i
        for i, city in enumerate(cities)
    }

    results.sort(
        key=lambda x: order.get(
            x["name"],
            9999
        )
    )

    # Only replace cache if we got a healthy result
    if len(results) >= 140:

        CITY_CACHE = results
        CACHE_TIME = time.time()

        elapsed = round(
            time.time() - start,
            2
        )

        print(
            f"[BHARAT-SHIELD] "
            f"Live refresh complete: "
            f"{len(results)} cities in {elapsed}s"
        )

    else:

        print(
            f"[WARNING] Refresh returned only "
            f"{len(results)} cities. "
            f"Keeping previous cache."
        )


# ============================================================
# CITIES
# ============================================================

@app.get("/cities")
def cities():

    global CACHE_TIME

    try:

        cache_age = (
            time.time() - CACHE_TIME
            if CACHE_TIME
            else float("inf")
        )

        # First request OR stale cache
        if not CITY_CACHE or cache_age > CACHE_TTL:

            with CACHE_LOCK:

                # Re-check after acquiring lock
                cache_age = (
                    time.time() - CACHE_TIME
                    if CACHE_TIME
                    else float("inf")
                )

                if not CITY_CACHE or cache_age > CACHE_TTL:

                    refresh_city_cache()

        return CITY_CACHE

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# MANUAL REFRESH
# ============================================================

@app.get("/refresh")
def refresh():

    try:

        refresh_city_cache()

        return {
            "status": "ok",
            "cities": len(CITY_CACHE),
            "refreshed_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# PREDICT ONE CITY
# ============================================================

@app.get("/predict")
def predict(
    latitude: float,
    longitude: float
):

    try:

        return predict_city(
            latitude,
            longitude
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )