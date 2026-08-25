import json
import glob
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# BHARAT-SHIELD
# HISTORICAL FEATURE ENGINE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "data" / "historical"
OUTPUT_FILE = BASE_DIR / "data" / "ml_features.csv"

# Start with a manageable test
TEST_MODE = False
TEST_CITIES = 3


# ============================================================
# HEAT INDEX
# ============================================================

def calculate_heat_index(temp_c, humidity):
    """
    NOAA-style heat index approximation.

    For cooler conditions, apparent temperature is a better
    representation than forcing the heat-index equation.
    """

    temp_f = temp_c * 9 / 5 + 32

    # Simple approximation below heat-index applicability range
    simple_hi = (
        0.5
        * (
            temp_f
            + 61.0
            + ((temp_f - 68.0) * 1.2)
            + (humidity * 0.094)
        )
    )

    # Rothfusz regression
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

    # Only use full HI formula where applicable
    use_hi = (temp_f >= 80) & (humidity >= 40)

    result = np.where(
        use_hi,
        hi,
        simple_hi
    )

    return (result - 32) * 5 / 9


# ============================================================
# PROCESS ONE CITY
# ============================================================

def process_city(path):

    with open(path, "r") as f:
        city = json.load(f)

    hourly = city["hourly"]

    df = pd.DataFrame(hourly)

    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    df["time"] = pd.to_datetime(
        df["time"]
    )

    df = df.sort_values(
        "time"
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # City metadata
    # --------------------------------------------------------

    df["city"] = city["name"]
    df["state"] = city["state"]

    df["latitude"] = city["latitude"]
    df["longitude"] = city["longitude"]

    # --------------------------------------------------------
    # Rename weather columns
    # --------------------------------------------------------

    df = df.rename(columns={
        "temperature_2m": "temperature",
        "relative_humidity_2m": "humidity",
        "dew_point_2m": "dew_point",
        "apparent_temperature": "apparent_temperature",
        "wind_speed_10m": "wind_speed",
        "shortwave_radiation": "solar_radiation",
        "pressure_msl": "pressure",
    })

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

    df["day_of_year"] = (
        df["time"].dt.dayofyear
    )

    df["month"] = (
        df["time"].dt.month
    )

    # Cyclic encoding
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
    # LAG FEATURES
    # --------------------------------------------------------

    for lag in [
        1,
        3,
        6,
        12,
        24,
        48,
    ]:

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
        df["temperature"]
        .rolling(6)
        .mean()
    )

    df["temperature_mean_24h"] = (
        df["temperature"]
        .rolling(24)
        .mean()
    )

    df["temperature_max_24h"] = (
        df["temperature"]
        .rolling(24)
        .max()
    )

    df["temperature_max_72h"] = (
        df["temperature"]
        .rolling(72)
        .max()
    )

    df["humidity_mean_24h"] = (
        df["humidity"]
        .rolling(24)
        .mean()
    )

    df["humidity_max_24h"] = (
        df["humidity"]
        .rolling(24)
        .max()
    )

    df["heat_index_mean_6h"] = (
        df["heat_index"]
        .rolling(6)
        .mean()
    )

    df["heat_index_mean_24h"] = (
        df["heat_index"]
        .rolling(24)
        .mean()
    )

    df["heat_index_max_24h"] = (
        df["heat_index"]
        .rolling(24)
        .max()
    )

    df["heat_index_max_48h"] = (
        df["heat_index"]
        .rolling(48)
        .max()
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

    # Rate of thermal change
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

    # --------------------------------------------------------
    # FUTURE TARGET
    #
    # Maximum heat index during the NEXT 72 HOURS.
    #
    # IMPORTANT:
    # Future values are ONLY used for the target.
    # They never enter the input features.
    # --------------------------------------------------------

    future_heat_indexes = []

    for i in range(1, 73):

        future_heat_indexes.append(
            df["heat_index"].shift(-i)
        )

    future_matrix = pd.concat(
        future_heat_indexes,
        axis=1
    )

    df["target_max_heat_index_72h"] = (
        future_matrix.max(axis=1)
    )

    # --------------------------------------------------------
    # FUTURE EXCESS HEAT
    # --------------------------------------------------------

    df["target_heat_excess"] = (
        df["target_max_heat_index_72h"]
        - df["heat_index"]
    )

    # --------------------------------------------------------
    # DROP ROWS WITH INCOMPLETE WINDOWS
    # --------------------------------------------------------

    df = df.dropna()

    return df


# ============================================================
# MAIN
# ============================================================

files = sorted(
    glob.glob(
        str(INPUT_DIR / "*.json")
    )
)

if TEST_MODE:

    files = files[:TEST_CITIES]

    print(
        f"TEST MODE: processing {len(files)} cities"
    )

else:

    print(
        f"FULL MODE: processing {len(files)} cities"
    )


all_frames = []

for i, path in enumerate(files, 1):

    print(
        f"[{i}/{len(files)}] "
        f"{Path(path).stem}"
    )

    try:

        df = process_city(path)

        print(
            f"    {len(df):,} training rows"
        )

        all_frames.append(df)

    except Exception as e:

        print(
            f"    ERROR: {e}"
        )


# ============================================================
# COMBINE
# ============================================================

if not all_frames:

    raise RuntimeError(
        "No cities were successfully processed."
    )


final_df = pd.concat(
    all_frames,
    ignore_index=True
)


# ============================================================
# SAVE
# ============================================================

final_df.to_csv(
    OUTPUT_FILE,
    index=False
)


print()
print("=" * 60)
print("BHARAT-SHIELD FEATURE ENGINE")
print("=" * 60)

print(
    f"Cities processed : {len(all_frames)}"
)

print(
    f"Training rows    : {len(final_df):,}"
)

print(
    f"Features         : {len(final_df.columns)}"
)

print(
    f"Output           : {OUTPUT_FILE}"
)

print("=" * 60)