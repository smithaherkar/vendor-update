import joblib
import pandas as pd

MODEL_PATH = "models/predict_flag_invoice.pkl"


def load_model(model_path: str = MODEL_PATH):
    """
    Load trained classifier model.
    """
    with open(model_path, "rb") as f:
        model = joblib.load(f)
    return model


def predict_invoice_flag(input_data):
    """
    Predict invoice flag for new vendor invoices.

    Parameters
    ----------
    input_data : dict

    Returns
    -------
    pd.DataFrame with predicted flag
    """

    model = load_model()

    input_df = pd.DataFrame(input_data)

    input_df["Predicted_Flag"] = model.predict(input_df).round()

    return input_df


if __name__ == "__main__":

    # Example inference run (local testing)
    sample_data = {
        "invoice_quantity": [120, 200, 150],
        "invoice_dollars": [18500, 9000, 3000],
        "Freight": [550, 250, 120],
        "total_item_quantity": [120, 198, 150],
        "total_item_dollars": [18490, 8995, 2995]
    }

    prediction = predict_invoice_flag(sample_data)

    print(prediction)