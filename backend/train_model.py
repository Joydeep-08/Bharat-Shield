import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from xgboost import XGBRegressor


# ============================================================
# BHARAT-SHIELD
# 72-HOUR THERMAL STRESS PREDICTION MODEL
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = BASE_DIR / "data" / "ml_features.csv"
MODEL_DIR = BASE_DIR / "backend" / "models"

MODEL_FILE = MODEL_DIR / "thermal_72h_xgb.json"
FEATURE_FILE = MODEL_DIR / "feature_columns.json"
METRICS_FILE = MODEL_DIR / "model_metrics.json"


TARGET = "target_max_heat_index_72h"


# ============================================================
# SETUP
# ============================================================

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)


print()
print("=" * 65)
print("        BHARAT-SHIELD ML TRAINING")
print("=" * 65)

print(f"Dataset : {DATA_FILE}")
print(f"Target  : {TARGET}")
print("=" * 65)


# ============================================================
# LOAD DATA
# ============================================================

print()
print("Loading feature dataset...")

df = pd.read_csv(DATA_FILE)

print(
    f"Rows    : {len(df):,}"
)

print(
    f"Columns : {len(df.columns)}"
)


# ============================================================
# SORT BY TIME
# ============================================================

df["time"] = pd.to_datetime(
    df["time"]
)

df = df.sort_values(
    "time"
).reset_index(drop=True)


# ============================================================
# REMOVE LEAKAGE / NON-MODEL COLUMNS
# ============================================================

# These columns must NEVER be model inputs.
#
# target_max_heat_index_72h
#     = what we are predicting
#
# target_heat_excess
#     = calculated using the future target
#
# city/state
#     = categorical identifiers. We already provide
#       latitude/longitude, which generalize better.
#
# time
#     = represented through engineered time features.

EXCLUDE = [
    TARGET,
    "target_heat_excess",
    "city",
    "state",
    "time",
]


feature_columns = [
    col
    for col in df.columns
    if col not in EXCLUDE
]


print()
print(
    f"Input features : {len(feature_columns)}"
)


# ============================================================
# NUMERIC DATA ONLY
# ============================================================

X = df[feature_columns]

y = df[TARGET]


# Remove any remaining invalid values

valid_mask = (
    X.notna().all(axis=1)
    & y.notna()
    & np.isfinite(X).all(axis=1)
    & np.isfinite(y)
)


X = X.loc[valid_mask].reset_index(drop=True)

y = y.loc[valid_mask].reset_index(drop=True)

times = df.loc[
    valid_mask,
    "time"
].reset_index(drop=True)


print(
    f"Valid rows     : {len(X):,}"
)


# ============================================================
# TIME-BASED SPLIT
# ============================================================

# IMPORTANT:
#
# We do NOT randomly split weather data.
#
# Training:
#   2022 → 2024
#
# Testing:
#   2025
#
# This simulates the real-world situation:
#
#       PAST --------------> FUTURE
#       TRAIN                TEST

train_mask = (
    times.dt.year <= 2024
)

test_mask = (
    times.dt.year == 2025
)


X_train = X.loc[
    train_mask
]

y_train = y.loc[
    train_mask
]

X_test = X.loc[
    test_mask
]

y_test = y.loc[
    test_mask
]


print()
print("=" * 65)
print("TIME-BASED DATA SPLIT")
print("=" * 65)

print(
    f"Training rows : {len(X_train):,}"
)

print(
    f"Testing rows  : {len(X_test):,}"
)

print(
    f"Train period  : 2022 → 2024"
)

print(
    f"Test period   : 2025"
)

print("=" * 65)


# ============================================================
# MODEL
# ============================================================

print()
print("Creating XGBoost model...")

model = XGBRegressor(

    objective="reg:squarederror",

    n_estimators=400,

    learning_rate=0.08,

    max_depth=8,

    min_child_weight=5,

    subsample=0.8,

    colsample_bytree=0.8,

    reg_alpha=0.05,

    reg_lambda=1.0,

    tree_method="hist",

    n_jobs=-1,

    random_state=42,

)


# ============================================================
# TRAIN
# ============================================================

print()
print("=" * 65)
print("TRAINING")
print("=" * 65)

print(
    "XGBoost training started..."
)

model.fit(
    X_train,
    y_train,
    eval_set=[
        (X_test, y_test)
    ],
    verbose=False,
)

print(
    "Training complete."
)


# ============================================================
# PREDICTION
# ============================================================

print()
print("Generating 2025 predictions...")

predictions = model.predict(
    X_test
)


# ============================================================
# METRICS
# ============================================================

mae = mean_absolute_error(
    y_test,
    predictions
)

rmse = np.sqrt(
    mean_squared_error(
        y_test,
        predictions
    )
)

r2 = r2_score(
    y_test,
    predictions
)


# ============================================================
# EXTREME ERROR ANALYSIS
# ============================================================

errors = np.abs(
    y_test.values
    - predictions
)

within_1c = (
    errors <= 1.0
).mean() * 100

within_2c = (
    errors <= 2.0
).mean() * 100

within_3c = (
    errors <= 3.0
).mean() * 100


# ============================================================
# EXTREME THERMAL EVENT DETECTION
# ============================================================

# Define extreme thermal stress using the same target
# variable that the model predicts.

EXTREME_THRESHOLD = 40.0

actual_extreme = (
    y_test >= EXTREME_THRESHOLD
)

predicted_extreme = (
    predictions >= EXTREME_THRESHOLD
)


true_positive = (
    actual_extreme
    & predicted_extreme
).sum()

false_positive = (
    (~actual_extreme)
    & predicted_extreme
).sum()

false_negative = (
    actual_extreme
    & (~predicted_extreme)
).sum()


if (
    true_positive
    + false_negative
) > 0:

    extreme_recall = (
        true_positive
        /
        (
            true_positive
            + false_negative
        )
    )

else:

    extreme_recall = 0.0


if (
    true_positive
    + false_positive
) > 0:

    extreme_precision = (
        true_positive
        /
        (
            true_positive
            + false_positive
        )
    )

else:

    extreme_precision = 0.0


# ============================================================
# PRINT RESULTS
# ============================================================

print()
print("=" * 65)
print("MODEL RESULTS")
print("=" * 65)

print(
    f"MAE                 : {mae:.3f} °C"
)

print(
    f"RMSE                : {rmse:.3f} °C"
)

print(
    f"R²                  : {r2:.4f}"
)

print()

print(
    f"Predictions ±1°C    : {within_1c:.2f}%"
)

print(
    f"Predictions ±2°C    : {within_2c:.2f}%"
)

print(
    f"Predictions ±3°C    : {within_3c:.2f}%"
)

print()

print(
    "EXTREME EVENT DETECTION"
)

print(
    f"Extreme threshold   : {EXTREME_THRESHOLD}°C"
)

print(
    f"Extreme precision   : "
    f"{extreme_precision * 100:.2f}%"
)

print(
    f"Extreme recall      : "
    f"{extreme_recall * 100:.2f}%"
)

print("=" * 65)


# ============================================================
# FEATURE IMPORTANCE
# ============================================================

importance = (
    model.feature_importances_
)

importance_df = pd.DataFrame({

    "feature": feature_columns,

    "importance": importance,

}).sort_values(
    "importance",
    ascending=False
)


print()
print("=" * 65)
print("TOP 20 FEATURES")
print("=" * 65)

for _, row in importance_df.head(20).iterrows():

    print(
        f"{row['feature']:<35}"
        f"{row['importance']:.5f}"
    )


# ============================================================
# SAVE MODEL
# ============================================================

print()
print("Saving model...")

model.save_model(
    MODEL_FILE
)


# ============================================================
# SAVE FEATURE LIST
# ============================================================

with open(
    FEATURE_FILE,
    "w"
) as f:

    json.dump(
        feature_columns,
        f,
        indent=2
    )


# ============================================================
# SAVE METRICS
# ============================================================

metrics = {

    "model": "XGBoost",

    "target": TARGET,

    "train_period": "2022-2024",

    "test_period": "2025",

    "training_rows": int(
        len(X_train)
    ),

    "testing_rows": int(
        len(X_test)
    ),

    "features": int(
        len(feature_columns)
    ),

    "mae_c": float(mae),

    "rmse_c": float(rmse),

    "r2": float(r2),

    "within_1c_percent": float(
        within_1c
    ),

    "within_2c_percent": float(
        within_2c
    ),

    "within_3c_percent": float(
        within_3c
    ),

    "extreme_precision": float(
        extreme_precision
    ),

    "extreme_recall": float(
        extreme_recall
    ),
}


with open(
    METRICS_FILE,
    "w"
) as f:

    json.dump(
        metrics,
        f,
        indent=2
    )


# ============================================================
# DONE
# ============================================================

print()
print("=" * 65)
print("        BHARAT-SHIELD MODEL READY")
print("=" * 65)

print(
    f"Model   : {MODEL_FILE}"
)

print(
    f"Features: {FEATURE_FILE}"
)

print(
    f"Metrics : {METRICS_FILE}"
)

print("=" * 65)