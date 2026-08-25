from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.inference import predict_city


app = FastAPI(
    title="Bharat-Shield API",
    description="National Thermal Risk Early Warning API",
    version="1.0.0",
)


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
# PREDICT
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