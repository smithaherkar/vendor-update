"""
Loads the trained model files (.pkl) ONE time when the server starts,
and exposes simple predict_* functions for the routers to call.

Loading models is slow-ish, so we never want to do it on every request -
that's why this happens at import time (module level), not inside a function.
"""
import shap
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

FEATURE_DISPLAY_NAMES = {
    "invoice_quantity": "Invoice Billed Quantity",
    "invoice_dollars": "Invoice Billed Dollars ($)",
    "Freight": "Freight Charges ($)",
    "total_item_quantity": "PO Received Quantity",
    "total_item_dollars": "PO Received Dollars ($)",
}

scaler = joblib.load(settings.scaler_path)
flag_model = joblib.load(settings.flag_model_path)
freight_model = joblib.load(settings.freight_model_path)

# Initialize SHAP TreeExplainer once at startup for instant (<15ms) attribution
shap_explainer = shap.TreeExplainer(flag_model)


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


def explain_invoice_flag(payload: dict) -> dict:
    """
    Computes exact SHAP feature attributions for an invoice classification.
    Explains the mathematical contribution of each feature towards the FLAGGED risk score.
    Returns:
      - base_risk: baseline population risk rate
      - risk_probability: predicted risk probability for this invoice
      - predicted_flag: binary 0/1 prediction
      - features: list of feature attributions ranked by absolute impact
      - summary: plain-English diagnostic summary statement
    """
    row = pd.DataFrame([[payload[col] for col in FLAG_FEATURE_ORDER]], columns=FLAG_FEATURE_ORDER)
    row_scaled = scaler.transform(row)

    predicted_flag = int(flag_model.predict(row_scaled)[0])
    probability = float(flag_model.predict_proba(row_scaled)[0][1])

    # Extract SHAP values for Class 1 (Flagged)
    sv = shap_explainer.shap_values(row_scaled)
    if isinstance(sv, list):
        vals = sv[1][0]
    elif hasattr(sv, "ndim") and sv.ndim == 3:
        vals = sv[0, :, 1]
    else:
        vals = sv[0]

    # Baseline expected value
    expected_val = shap_explainer.expected_value
    if isinstance(expected_val, (list, np.ndarray)) and len(expected_val) > 1:
        base_val = float(expected_val[1])
    else:
        base_val = float(expected_val)

    total_abs_impact = sum(abs(float(v)) for v in vals) or 1e-6

    feature_contributions = []
    for col, shap_v in zip(FLAG_FEATURE_ORDER, vals):
        v = float(shap_v)
        raw_val = float(payload.get(col, 0.0))
        impact_pct = round((abs(v) / total_abs_impact) * 100.0, 1)
        direction = "INCREASES_RISK" if v > 0 else "DECREASES_RISK"

        feature_contributions.append({
            "feature": col,
            "label": FEATURE_DISPLAY_NAMES.get(col, col),
            "raw_value": round(raw_val, 2),
            "shap_value": round(v, 4),
            "impact": direction,
            "impact_pct": impact_pct,
        })

    # Rank by strongest absolute impact first
    feature_contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

    # Synthesize plain-English diagnostic summary
    top_driver = feature_contributions[0]
    if predicted_flag == 1:
        risk_drivers = [f["label"] for f in feature_contributions if f["impact"] == "INCREASES_RISK"]
        summary = (
            f"Flagged as high-risk ({probability * 100:.1f}% probability). "
            f"Primary risk driver is {top_driver['label']} ({'+' if top_driver['shap_value'] > 0 else ''}{top_driver['shap_value']:.3f} impact)."
        )
    else:
        safe_drivers = [f["label"] for f in feature_contributions if f["impact"] == "DECREASES_RISK"]
        summary = (
            f"Cleared as low-risk ({(1.0 - probability) * 100:.1f}% confidence). "
            f"Primary stabilizing factor is {top_driver['label']} ({top_driver['shap_value']:.3f} impact)."
        )

    return {
        "base_risk": round(base_val, 4),
        "risk_probability": round(probability, 4),
        "predicted_flag": predicted_flag,
        "risk_label": "FLAGGED" if predicted_flag == 1 else "CLEARED",
        "features": feature_contributions,
        "summary": summary,
    }



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
