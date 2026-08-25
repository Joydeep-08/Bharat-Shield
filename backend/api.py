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

CITIES_FILE = (
    BASE_DIR
    / "data"
    / "india_top150_cities.geojson"
)

FALLBACK_FILE = (
    BASE_DIR
    / "data"
    / "thermal_risk_150.json"
)


# ============================================================
# LIVE CACHE
# ============================================================

CITY_CACHE = []

CACHE_TIME = 0

# Refresh live weather every 30 minutes
CACHE_TTL = 30 * 60

# Prevent two refresh operations from running together
REFRESH_LOCK = threading.Lock()

# Prevent multiple background refresh threads
REFRESH_RUNNING = False

REFRESH_STATE_LOCK = threading.Lock()


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
# RISK HELPERS
# ============================================================

def classify_risk(heat_index):
    """
    Classify thermal risk from a heat-index value.
    """

    if heat_index >= 40:
        return "EXTREME"

    elif heat_index >= 35:
        return "HIGH"

    elif heat_index >= 32:
        return "MODERATE"

    else:
        return "LOW"


def calculate_risk_score(heat_index):
    """
    Convert heat index into the 0-100 score used by frontend.
    """

    return round(
        min(
            100,
            max(
                0,
                (heat_index / 50) * 100
            )
        )
    )


# ============================================================
# FALLBACK CACHE
# ============================================================

def load_fallback_cache():

    global CITY_CACHE
    global CACHE_TIME

    if not FALLBACK_FILE.exists():

        print(
            "[BHARAT-SHIELD] "
            "No fallback cache found."
        )

        return

    try:

        with open(FALLBACK_FILE, "r") as f:
            data = json.load(f)

        results = []

        for city in data:

            heat_index = city.get(
                "heat_index_c"
            )

            risk_score = city.get(
                "risk_score",
                0
            )

            risk_level = city.get(
                "risk_level",
                "LOW"
            )

            results.append({

                "name": city.get(
                    "name",
                    "Unknown"
                ),

                "state": city.get(
                    "state",
                    ""
                ),

                "latitude": float(
                    city.get(
                        "latitude",
                        0
                    )
                ),

                "longitude": float(
                    city.get(
                        "longitude",
                        0
                    )
                ),

                "current": {

                    "risk_level": risk_level,

                    "risk_score": risk_score,

                    "heat_index_c": heat_index,

                    "temperature_c": city.get(
                        "temperature_c"
                    ),

                    "humidity_percent": city.get(
                        "humidity_percent"
                    ),

                    "wind_kmh": city.get(
                        "wind_kmh"
                    ),

                    "solar_wm2": city.get(
                        "solar_wm2"
                    ),
                },

                "peak": {

                    "risk_level": risk_level,

                    "risk_score": risk_score,

                    "heat_index_c": heat_index,

                    "time": None,
                },
            })

        if len(results) > 0:

            CITY_CACHE = results

            # Mark fallback as stale so a live refresh
            # starts immediately in the background.
            CACHE_TIME = (
                time.time()
                - CACHE_TTL
                - 1
            )

            print(
                f"[BHARAT-SHIELD] "
                f"Loaded {len(results)} fallback cities."
            )

    except Exception as e:

        print(
            "[BHARAT-SHIELD] "
            f"Failed to load fallback cache: {e}"
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

        "cities_cached": len(
            CITY_CACHE
        ),

        "cache_age_seconds": (

            round(
                time.time() - CACHE_TIME,
                1
            )

            if CACHE_TIME

            else None
        ),

        "refresh_running":
            REFRESH_RUNNING,
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

            "name": props.get(
                "name",
                "Unknown"
            ),

            "state": props.get(
                "state",
                ""
            ),

            "latitude": float(
                coords[1]
            ),

            "longitude": float(
                coords[0]
            ),
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

            # ------------------------------------------------
            # CURRENT CONDITIONS
            # ------------------------------------------------

            current_hi = float(
                prediction[
                    "current_heat_index"
                ]
            )

            current_risk_level = classify_risk(
                current_hi
            )

            current_risk_score = calculate_risk_score(
                current_hi
            )

            # ------------------------------------------------
            # 72-HOUR PEAK
            # ------------------------------------------------

            peak_hi = float(
                prediction[
                    "prediction_max_heat_index_72h"
                ]
            )

            peak_risk_level = classify_risk(
                peak_hi
            )

            peak_risk_score = calculate_risk_score(
                peak_hi
            )

            # ------------------------------------------------
            # RETURN CITY
            # ------------------------------------------------

            return {

                "name": city["name"],

                "state": city["state"],

                "latitude": city["latitude"],

                "longitude": city["longitude"],

                "current": {

                    "risk_level":
                        current_risk_level,

                    "risk_score":
                        current_risk_score,

                    "heat_index_c":
                        round(
                            current_hi,
                            2
                        ),

                    "temperature_c":
                        prediction.get(
                            "temperature_c"
                        ),

                    "humidity_percent":
                        prediction.get(
                            "humidity_percent"
                        ),

                    "wind_kmh":
                        prediction.get(
                            "wind_kmh"
                        ),

                    "solar_wm2":
                        prediction.get(
                            "solar_wm2"
                        ),
                },

                "peak": {

                    "risk_level":
                        peak_risk_level,

                    "risk_score":
                        peak_risk_score,

                    "heat_index_c":
                        round(
                            peak_hi,
                            2
                        ),

                    "time":
                        prediction[
                            "timestamp"
                        ],
                },
            }

        except Exception as e:

            error_text = str(e)

            if (
                "429" in error_text
                and attempt < max_attempts - 1
            ):

                wait_time = 2 ** attempt

                print(
                    f"[RETRY] "
                    f"{city['name']} "
                    f"rate limited. "
                    f"Retrying in {wait_time}s..."
                )

                time.sleep(
                    wait_time
                )

            else:

                raise


# ============================================================
# REFRESH ALL 150 CITIES
# ============================================================

def refresh_city_cache():

    global CITY_CACHE
    global CACHE_TIME

    # Only one refresh at a time
    if not REFRESH_LOCK.acquire(
        blocking=False
    ):

        print(
            "[BHARAT-SHIELD] "
            "Refresh already running."
        )

        return

    try:

        cities = load_cities()

        results = []

        print(
            f"[BHARAT-SHIELD] "
            f"Refreshing {len(cities)} cities..."
        )

        start = time.time()

        # Moderate concurrency to avoid
        # hammering Open-Meteo.
        with ThreadPoolExecutor(
            max_workers=5
        ) as executor:

            futures = {

                executor.submit(
                    process_city,
                    city
                ): city

                for city in cities
            }

            for future in as_completed(
                futures
            ):

                city = futures[future]

                try:

                    results.append(
                        future.result()
                    )

                except Exception as e:

                    print(
                        f"[ERROR] "
                        f"{city['name']}: {e}"
                    )

        # Preserve original geographic ordering
        order = {

            city["name"]: i

            for i, city in enumerate(
                cities
            )
        }

        results.sort(
            key=lambda x:
            order.get(
                x["name"],
                9999
            )
        )

        # Only replace cache if refresh
        # returned a healthy number of cities.
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
                f"{len(results)} cities "
                f"in {elapsed}s"
            )

        else:

            print(
                f"[WARNING] "
                f"Refresh returned only "
                f"{len(results)} cities. "
                f"Keeping previous cache."
            )

    finally:

        REFRESH_LOCK.release()


# ============================================================
# BACKGROUND REFRESH
# ============================================================

def start_background_refresh():

    global REFRESH_RUNNING

    with REFRESH_STATE_LOCK:

        if REFRESH_RUNNING:

            return

        REFRESH_RUNNING = True

    def worker():

        global REFRESH_RUNNING

        try:

            refresh_city_cache()

        finally:

            with REFRESH_STATE_LOCK:

                REFRESH_RUNNING = False

    thread = threading.Thread(
        target=worker,
        daemon=True
    )

    thread.start()


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup_event():

    # Load instant fallback data
    load_fallback_cache()

    # Start live refresh without blocking startup
    start_background_refresh()

    print(
        "[BHARAT-SHIELD] "
        "API ready. "
        "Live refresh running in background."
    )


# ============================================================
# CITIES
# ============================================================

@app.get("/cities")
def cities():

    try:

        cache_age = (

            time.time() - CACHE_TIME

            if CACHE_TIME

            else float("inf")
        )

        # ----------------------------------------------------
        # STALE CACHE
        # ----------------------------------------------------
        #
        # NEVER wait for the live refresh here.
        #
        # Return cached data immediately and let the
        # background thread update it.
        #

        if (
            cache_age > CACHE_TTL
            and not REFRESH_RUNNING
        ):

            start_background_refresh()

        # ----------------------------------------------------
        # IMMEDIATE RESPONSE
        # ----------------------------------------------------

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

        # This endpoint intentionally waits.
        # It is for manual/admin refresh only.
        refresh_city_cache()

        return {

            "status": "ok",

            "cities": len(
                CITY_CACHE
            ),

            "refreshed_at":
                datetime.now(
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