"""
Loads the trained model files (.pkl) ONE time when the server starts,
and exposes simple predict_* functions for the routers to call.

Loading models is slow-ish, so we never want to do it on every request -
that's why this happens at import time (module level), not inside a function.
"""
import joblib
import numpy as np
import pandas as pd

from app.config import settings

# Order matters! This must match the column order used when the scaler
# and the flag model were trained (see data_preprocessing.py / train.py).
FLAG_FEATURE_ORDER = [
    "invoice_quantity",
    "invoice_dollars",
    "Freight",
    "total_item_quantity",
    "total_item_dollars",
]

scaler = joblib.load(settings.scaler_path)
flag_model = joblib.load(settings.flag_model_path)
freight_model = joblib.load(settings.freight_model_path)


def predict_invoice_flag(payload: dict) -> tuple[int, float]:
    """
    payload: dict with the 5 FLAG_FEATURE_ORDER keys.
    Returns: (predicted_flag 0/1, probability_of_being_flagged)
    """
    row = pd.DataFrame([[payload[col] for col in FLAG_FEATURE_ORDER]], columns=FLAG_FEATURE_ORDER)
    row_scaled = scaler.transform(row)

    predicted_flag = int(flag_model.predict(row_scaled)[0])
    # predict_proba returns [[P(class 0), P(class 1)]]
    probability = float(flag_model.predict_proba(row_scaled)[0][1])

    return predicted_flag, probability


def predict_freight(dollars: float) -> float:
    """
    dollars: invoice dollar amount.
    Returns: predicted freight cost.
    """
    row = pd.DataFrame([[dollars]], columns=["Dollars"])
    prediction = freight_model.predict(row)
    # The model was trained with a 2-D target, so predict() can return
    # a shape like (1, 1) instead of (1,) - flatten handles both safely.
    raw = float(np.asarray(prediction).flatten()[0])
    # Sanity clamp: a single-feature LinearRegression can extrapolate to
    # negative freight (small dollars) or freight bigger than the invoice
    # itself (large dollars). Neither is physically meaningful.
    return max(0.0, min(raw, dollars))
