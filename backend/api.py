from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.inference import predict_city

import json
from pathlib import Path


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
    }


# ============================================================
# PREDICT ONE CITY
# ============================================================

@app.get("/predict")
def predict(
    latitude: float,
    longitude: float
):

    try:

        result = predict_city(
            latitude,
            longitude
        )

        return result

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# ALL 150 CITIES
# ============================================================

# ============================================================
# ALL 150 CITIES
# FAST NATIONAL SNAPSHOT
# ============================================================

# ============================================================
# ALL 150 CITIES
# ============================================================

THERMAL_RISK_FILE = BASE_DIR / "data" / "thermal_risk_150.json"


@app.get("/cities")
def cities():

    try:

        with open(THERMAL_RISK_FILE, "r") as f:
            data = json.load(f)

        results = []

        for city in data:

            results.append({
                "name": city["name"],
                "state": city["state"],
                "latitude": city["latitude"],
                "longitude": city["longitude"],

                "current": {
                    "risk_level": city["risk_level"],
                    "risk_score": city["risk_score"],
                    "heat_index_c": city["heat_index_c"],
                    "temperature_c": city["temperature_c"],
                    "humidity_percent": city["humidity_percent"],
                    "wind_kmh": city["wind_kmh"],
                    "solar_wm2": city["solar_wm2"],
                },

                "peak": {
                    "risk_level": city["risk_level"],
                    "risk_score": city["risk_score"],
                    "heat_index_c": city["heat_index_c"],
                    "time": None,
                },
            })

        return results

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )