import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import xgboost as xgb


BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_FILE = BASE_DIR / "backend" / "models" / "thermal_72h_xgb.json"
FEATURE_FILE = BASE_DIR / "backend" / "models" / "feature_columns.json"


# ============================================================
# HEAT INDEX
# Same implementation used during training
# ============================================================

def calculate_heat_index(temp_c, humidity):
    temp_f = temp_c * 9 / 5 + 32

    simple_hi = (
        0.5
        * (
            temp_f
            + 61.0
            + ((temp_f - 68.0) * 1.2)
            + (humidity * 0.094)
        )
    )

    hi = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * humidity
        - 0.22475541 * temp_f * humidity
        - 0.00683783 * temp_f**2
        - 0.05481717 * humidity**2
        + 0.00122874 * temp_f**2 * humidity
        + 0.00085282 * temp_f * humidity**2
        - 0.00000199 * temp_f**2 * humidity**2
    )

    use_hi = (temp_f >= 80) & (humidity >= 40)

    result = np.where(
        use_hi,
        hi,
        simple_hi
    )

    return (result - 32) * 5 / 9


# ============================================================
# LOAD MODEL
# ============================================================

MODEL = xgb.XGBRegressor()
MODEL.load_model(str(MODEL_FILE))

with open(FEATURE_FILE, "r") as f:
    FEATURE_COLUMNS = json.load(f)


# ============================================================
# FETCH LIVE WEATHER
# ============================================================

def fetch_weather(latitude, longitude, timezone="auto"):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "dew_point_2m",
            "apparent_temperature",
            "wind_speed_10m",
            "shortwave_radiation",
            "pressure_msl",
        ]),
        "past_days": 4,
        "forecast_days": 1,
        "timezone": timezone,
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# BUILD FEATURES
# ============================================================

def build_live_features(weather, latitude, longitude):

    hourly = weather["hourly"]

    df = pd.DataFrame({
        "time": pd.to_datetime(hourly["time"]),
        "temperature": hourly["temperature_2m"],
        "humidity": hourly["relative_humidity_2m"],
        "dew_point": hourly["dew_point_2m"],
        "apparent_temperature": hourly["apparent_temperature"],
        "wind_speed": hourly["wind_speed_10m"],
        "solar_radiation": hourly["shortwave_radiation"],
        "pressure": hourly["pressure_msl"],
    })

    df = df.sort_values("time").reset_index(drop=True)

    df["latitude"] = latitude
    df["longitude"] = longitude

    # --------------------------------------------------------
    # HEAT INDEX
    # --------------------------------------------------------

    df["heat_index"] = calculate_heat_index(
        df["temperature"],
        df["humidity"]
    )

    # --------------------------------------------------------
    # TIME FEATURES
    # --------------------------------------------------------

    df["hour"] = df["time"].dt.hour

    df["day_of_year"] = df["time"].dt.dayofyear

    df["month"] = df["time"].dt.month

    df["hour_sin"] = np.sin(
        2 * np.pi * df["hour"] / 24
    )

    df["hour_cos"] = np.cos(
        2 * np.pi * df["hour"] / 24
    )

    df["day_sin"] = np.sin(
        2 * np.pi * df["day_of_year"] / 365
    )

    df["day_cos"] = np.cos(
        2 * np.pi * df["day_of_year"] / 365
    )

    # --------------------------------------------------------
    # LAGS
    # --------------------------------------------------------

    for lag in [1, 3, 6, 12, 24, 48]:

        df[f"temperature_lag_{lag}h"] = (
            df["temperature"].shift(lag)
        )

        df[f"humidity_lag_{lag}h"] = (
            df["humidity"].shift(lag)
        )

        df[f"heat_index_lag_{lag}h"] = (
            df["heat_index"].shift(lag)
        )

    # --------------------------------------------------------
    # ROLLING FEATURES
    # --------------------------------------------------------

    df["temperature_mean_6h"] = (
        df["temperature"].rolling(6).mean()
    )

    df["temperature_mean_24h"] = (
        df["temperature"].rolling(24).mean()
    )

    df["temperature_max_24h"] = (
        df["temperature"].rolling(24).max()
    )

    df["temperature_max_72h"] = (
        df["temperature"].rolling(72).max()
    )

    df["humidity_mean_24h"] = (
        df["humidity"].rolling(24).mean()
    )

    df["humidity_max_24h"] = (
        df["humidity"].rolling(24).max()
    )

    df["heat_index_mean_6h"] = (
        df["heat_index"].rolling(6).mean()
    )

    df["heat_index_mean_24h"] = (
        df["heat_index"].rolling(24).mean()
    )

    df["heat_index_max_24h"] = (
        df["heat_index"].rolling(24).max()
    )

    df["heat_index_max_48h"] = (
        df["heat_index"].rolling(48).max()
    )

    # --------------------------------------------------------
    # THERMAL TRAJECTORY
    # --------------------------------------------------------

    df["temperature_change_3h"] = (
        df["temperature"]
        - df["temperature"].shift(3)
    )

    df["temperature_change_6h"] = (
        df["temperature"]
        - df["temperature"].shift(6)
    )

    df["temperature_change_12h"] = (
        df["temperature"]
        - df["temperature"].shift(12)
    )

    df["temperature_change_24h"] = (
        df["temperature"]
        - df["temperature"].shift(24)
    )

    df["humidity_change_3h"] = (
        df["humidity"]
        - df["humidity"].shift(3)
    )

    df["humidity_change_6h"] = (
        df["humidity"]
        - df["humidity"].shift(6)
    )

    df["humidity_change_24h"] = (
        df["humidity"]
        - df["humidity"].shift(24)
    )

    df["heat_index_change_3h"] = (
        df["heat_index"]
        - df["heat_index"].shift(3)
    )

    df["heat_index_change_6h"] = (
        df["heat_index"]
        - df["heat_index"].shift(6)
    )

    df["heat_index_change_12h"] = (
        df["heat_index"]
        - df["heat_index"].shift(12)
    )

    df["heat_index_change_24h"] = (
        df["heat_index"]
        - df["heat_index"].shift(24)
    )

    df["heat_index_trend_6h"] = (
        df["heat_index_change_6h"] / 6
    )

    df["heat_index_trend_24h"] = (
        df["heat_index_change_24h"] / 24
    )

    # --------------------------------------------------------
    # THERMAL PERSISTENCE
    # --------------------------------------------------------

    df["hours_above_32"] = (
        (df["heat_index"] >= 32)
        .rolling(24)
        .sum()
    )

    df["hours_above_35"] = (
        (df["heat_index"] >= 35)
        .rolling(24)
        .sum()
    )

    df["hours_above_40"] = (
        (df["heat_index"] >= 40)
        .rolling(72)
        .sum()
    )

    return df


# ============================================================
# PREDICT
# ============================================================

def predict_city(latitude, longitude):

    weather = fetch_weather(
        latitude,
        longitude
    )

    df = build_live_features(
        weather,
        latitude,
        longitude
    )

    # Latest row with all 61 features available
    row = df.dropna(
        subset=FEATURE_COLUMNS
    ).iloc[-1]

    X = pd.DataFrame(
        [[row[col] for col in FEATURE_COLUMNS]],
        columns=FEATURE_COLUMNS
    )

    prediction = float(
        MODEL.predict(X)[0]
    )

    current_heat_index = float(
        row["heat_index"]
    )

    # --------------------------------------------------------
    # RISK CLASSIFICATION
    # --------------------------------------------------------

    if prediction >= 40:
        risk = "EXTREME"
    elif prediction >= 35:
        risk = "HIGH"
    elif prediction >= 32:
        risk = "MODERATE"
    else:
        risk = "LOW"

    return {
        "prediction_max_heat_index_72h": round(
            prediction,
            2
        ),
        "current_heat_index": round(
            current_heat_index,
            2
        ),
        "risk": risk,
        "timestamp": str(row["time"]),
        "latitude": latitude,
        "longitude": longitude,
    }