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

@app.get("/cities")
def cities():

    try:

        with open(CITIES_FILE, "r") as f:
            geojson = json.load(f)

        results = []

        for feature in geojson["features"]:

            props = feature["properties"]

            coords = feature["geometry"]["coordinates"]

            longitude = float(coords[0])
            latitude = float(coords[1])

            name = props.get("name", "Unknown")
            state = props.get("state", "")

            prediction = predict_city(
                latitude,
                longitude
            )

            risk_level = prediction["risk"]

            peak_hi = prediction["prediction_max_heat_index_72h"]
            current_hi = prediction["current_heat_index"]

            # Risk score used by the existing frontend.
            # Map thermal severity onto a 0-100 scale.
            risk_score = round(
                min(100, max(0, (peak_hi / 50) * 100))
            )

            results.append({
                "name": name,
                "state": state,
                "latitude": latitude,
                "longitude": longitude,

                "current": {
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "heat_index_c": current_hi,
                    "temperature_c": None,
                    "humidity_percent": None,
                    "wind_kmh": None,
                    "solar_wm2": None,
                },

                "peak": {
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                    "heat_index_c": peak_hi,
                    "time": prediction["timestamp"],
                },
            })

        return results

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )