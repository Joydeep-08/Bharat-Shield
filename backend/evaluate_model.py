import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    confusion_matrix,
    classification_report,
)


# ============================================================
# BHARAT-SHIELD
# MODEL EVALUATION ENGINE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = BASE_DIR / "data" / "ml_features.csv"

MODEL_FILE = (
    BASE_DIR
    / "backend"
    / "models"
    / "thermal_72h_xgb.json"
)

FEATURE_FILE = (
    BASE_DIR
    / "backend"
    / "models"
    / "feature_columns.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "backend"
    / "models"
    / "evaluation_results.json"
)

TARGET = "target_max_heat_index_72h"


# ============================================================
# RISK CATEGORIES
# ============================================================

def risk_level(value):

    if value < 27:
        return "LOW"

    elif value < 32:
        return "MODERATE"

    elif value < 41:
        return "HIGH"

    else:
        return "EXTREME"


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 70)
print("             BHARAT-SHIELD MODEL EVALUATION")
print("=" * 70)

print(
    f"Dataset : {DATA_FILE}"
)

print(
    f"Model   : {MODEL_FILE}"
)

print(
    f"Target  : {TARGET}"
)

print("=" * 70)


# ============================================================
# LOAD MODEL
# ============================================================

print()
print("Loading trained XGBoost model...")

from xgboost import XGBRegressor

model = XGBRegressor()

model.load_model(
    MODEL_FILE
)

print("Model loaded.")


# ============================================================
# LOAD FEATURES
# ============================================================

print()
print("Loading feature list...")

with open(
    FEATURE_FILE,
    "r"
) as f:

    feature_columns = json.load(f)

print(
    f"Features loaded : {len(feature_columns)}"
)


# ============================================================
# LOAD DATA
# ============================================================

print()
print("Loading dataset...")

df = pd.read_csv(
    DATA_FILE
)

df["time"] = pd.to_datetime(
    df["time"]
)

df = df.sort_values(
    "time"
).reset_index(drop=True)


print(
    f"Total rows : {len(df):,}"
)


# ============================================================
# CLEAN DATA
# ============================================================

X = df[
    feature_columns
]

y = df[
    TARGET
]

valid_mask = (
    X.notna().all(axis=1)
    &
    y.notna()
    &
    np.isfinite(X).all(axis=1)
    &
    np.isfinite(y)
)

X = X.loc[
    valid_mask
].reset_index(drop=True)

y = y.loc[
    valid_mask
].reset_index(drop=True)

times = df.loc[
    valid_mask,
    "time"
].reset_index(drop=True)

# Keep city information for city-wise analysis

cities = df.loc[
    valid_mask,
    "city"
].reset_index(drop=True)


# ============================================================
# 2025 HOLDOUT
# ============================================================

test_mask = (
    times.dt.year == 2025
)

X_test = X.loc[
    test_mask
].reset_index(drop=True)

y_test = y.loc[
    test_mask
].reset_index(drop=True)

cities_test = cities.loc[
    test_mask
].reset_index(drop=True)

times_test = times.loc[
    test_mask
].reset_index(drop=True)


print()
print("=" * 70)
print("2025 HOLDOUT")
print("=" * 70)

print(
    f"Testing rows : {len(X_test):,}"
)

print(
    f"Cities       : {cities_test.nunique()}"
)

print(
    f"Period       : "
    f"{times_test.min()} → {times_test.max()}"
)

print("=" * 70)


# ============================================================
# PREDICTIONS
# ============================================================

print()
print("Generating predictions...")

predictions = model.predict(
    X_test
)


# ============================================================
# REGRESSION METRICS
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

errors = (
    predictions
    - y_test.values
)

absolute_errors = np.abs(
    errors
)


within_1 = (
    absolute_errors <= 1
).mean() * 100

within_2 = (
    absolute_errors <= 2
).mean() * 100

within_3 = (
    absolute_errors <= 3
).mean() * 100


# ============================================================
# RISK CLASSIFICATION
# ============================================================

actual_levels = np.array([
    risk_level(v)
    for v in y_test
])

predicted_levels = np.array([
    risk_level(v)
    for v in predictions
])


labels = [
    "LOW",
    "MODERATE",
    "HIGH",
    "EXTREME",
]


print()
print("=" * 70)
print("REGRESSION PERFORMANCE")
print("=" * 70)

print(
    f"MAE              : {mae:.3f} °C"
)

print(
    f"RMSE             : {rmse:.3f} °C"
)

print(
    f"R²               : {r2:.4f}"
)

print()

print(
    f"Within ±1°C      : {within_1:.2f}%"
)

print(
    f"Within ±2°C      : {within_2:.2f}%"
)

print(
    f"Within ±3°C      : {within_3:.2f}%"
)

print("=" * 70)


# ============================================================
# CLASSIFICATION REPORT
# ============================================================

print()
print("=" * 70)
print("THERMAL RISK CLASSIFICATION")
print("=" * 70)

print(
    classification_report(
        actual_levels,
        predicted_levels,
        labels=labels,
        zero_division=0
    )
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

cm = confusion_matrix(
    actual_levels,
    predicted_levels,
    labels=labels
)


print("CONFUSION MATRIX")
print()

print(
    f"{'':12}"
    + "".join(
        f"{label:>12}"
        for label in labels
    )
)

for i, label in enumerate(labels):

    print(
        f"{label:12}"
        + "".join(
            f"{cm[i][j]:>12}"
            for j in range(len(labels))
        )
    )


# ============================================================
# EXTREME EVENT ANALYSIS
# ============================================================

EXTREME_THRESHOLD = 40.0

actual_extreme = (
    y_test.values
    >= EXTREME_THRESHOLD
)

predicted_extreme = (
    predictions
    >= EXTREME_THRESHOLD
)


tp = (
    actual_extreme
    & predicted_extreme
).sum()

tn = (
    (~actual_extreme)
    & (~predicted_extreme)
).sum()

fp = (
    (~actual_extreme)
    & predicted_extreme
).sum()

fn = (
    actual_extreme
    & (~predicted_extreme)
).sum()


if tp + fn > 0:

    extreme_recall = (
        tp / (tp + fn)
    )

else:

    extreme_recall = 0


if tp + fp > 0:

    extreme_precision = (
        tp / (tp + fp)
    )

else:

    extreme_precision = 0


if (
    extreme_precision
    + extreme_recall
) > 0:

    extreme_f1 = (
        2
        * extreme_precision
        * extreme_recall
        /
        (
            extreme_precision
            + extreme_recall
        )
    )

else:

    extreme_f1 = 0


print()
print("=" * 70)
print("EXTREME EVENT DETECTION")
print("=" * 70)

print(
    f"Threshold        : {EXTREME_THRESHOLD}°C"
)

print(
    f"Actual extreme   : {actual_extreme.sum():,}"
)

print(
    f"Predicted extreme: {predicted_extreme.sum():,}"
)

print()

print(
    f"True positives   : {tp:,}"
)

print(
    f"False positives  : {fp:,}"
)

print(
    f"False negatives  : {fn:,}"
)

print()

print(
    f"Precision        : "
    f"{extreme_precision * 100:.2f}%"
)

print(
    f"Recall           : "
    f"{extreme_recall * 100:.2f}%"
)

print(
    f"F1 Score         : "
    f"{extreme_f1 * 100:.2f}%"
)

print("=" * 70)


# ============================================================
# WORST PREDICTIONS
# ============================================================

results = pd.DataFrame({

    "city": cities_test,

    "time": times_test,

    "actual": y_test,

    "predicted": predictions,

    "error": errors,

    "absolute_error": absolute_errors,

})

results = results.sort_values(
    "absolute_error",
    ascending=False
)


print()
print("=" * 70)
print("20 WORST PREDICTIONS")
print("=" * 70)

for _, row in results.head(20).iterrows():

    print(
        f"{row['city']:<20}"
        f" Actual: {row['actual']:>6.2f}°C"
        f"  Pred: {row['predicted']:>6.2f}°C"
        f"  Error: {row['error']:>+6.2f}°C"
    )


# ============================================================
# CITY-WISE PERFORMANCE
# ============================================================

print()
print("=" * 70)
print("CITY-WISE PERFORMANCE")
print("=" * 70)

city_results = []

for city, group in results.groupby(
    "city"
):

    city_mae = np.mean(
        group["absolute_error"]
    )

    city_rmse = np.sqrt(
        np.mean(
            group["error"] ** 2
        )
    )

    city_results.append({

        "city": city,

        "rows": len(group),

        "mae": city_mae,

        "rmse": city_rmse,

    })


city_df = pd.DataFrame(
    city_results
).sort_values(
    "mae",
    ascending=False
)


print()
print("10 cities with highest MAE:")

for _, row in city_df.head(10).iterrows():

    print(
        f"{row['city']:<20}"
        f" MAE: {row['mae']:.2f}°C"
        f" RMSE: {row['rmse']:.2f}°C"
    )


print()
print("10 cities with lowest MAE:")

for _, row in city_df.tail(10).iterrows():

    print(
        f"{row['city']:<20}"
        f" MAE: {row['mae']:.2f}°C"
        f" RMSE: {row['rmse']:.2f}°C"
    )


# ============================================================
# ERROR BY RISK LEVEL
# ============================================================

level_errors = {}

for level in labels:

    mask = (
        actual_levels
        == level
    )

    if mask.sum() > 0:

        level_errors[level] = {

            "samples": int(
                mask.sum()
            ),

            "mae": float(
                mean_absolute_error(
                    y_test.values[mask],
                    predictions[mask]
                )
            ),

            "mean_error": float(
                np.mean(
                    errors[mask]
                )
            ),

        }


print()
print("=" * 70)
print("ERROR BY ACTUAL RISK LEVEL")
print("=" * 70)

for level in labels:

    if level in level_errors:

        item = level_errors[level]

        print(
            f"{level:<10}"
            f" Samples: {item['samples']:>7,}"
            f"  MAE: {item['mae']:.3f}°C"
            f"  Bias: {item['mean_error']:+.3f}°C"
        )


# ============================================================
# SAVE RESULTS
# ============================================================

evaluation = {

    "model": "XGBoost",

    "dataset": str(
        DATA_FILE
    ),

    "test_period": "2025",

    "test_rows": int(
        len(X_test)
    ),

    "cities": int(
        cities_test.nunique()
    ),

    "features": int(
        len(feature_columns)
    ),

    "regression": {

        "mae_c": float(mae),

        "rmse_c": float(rmse),

        "r2": float(r2),

        "within_1c_percent": float(
            within_1
        ),

        "within_2c_percent": float(
            within_2
        ),

        "within_3c_percent": float(
            within_3
        ),

    },

    "extreme_detection": {

        "threshold_c": EXTREME_THRESHOLD,

        "true_positive": int(tp),

        "true_negative": int(tn),

        "false_positive": int(fp),

        "false_negative": int(fn),

        "precision": float(
            extreme_precision
        ),

        "recall": float(
            extreme_recall
        ),

        "f1": float(
            extreme_f1
        ),

    },

    "risk_level_errors":
        level_errors,

    "city_wise": city_results,

}


with open(
    OUTPUT_FILE,
    "w"
) as f:

    json.dump(
        evaluation,
        f,
        indent=2
    )


# ============================================================
# FINAL
# ============================================================

print()
print("=" * 70)
print("        EVALUATION COMPLETE")
print("=" * 70)

print(
    f"Results saved to:"
)

print(
    OUTPUT_FILE
)

print("=" * 70)