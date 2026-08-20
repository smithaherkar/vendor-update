"""
Shared prediction service for Invoice Risk scoring and Freight Estimation.
Used by both single-record API endpoints and CSV batch processors.
"""
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app import models_db, ml_models


def score_and_save_invoice(
    payload: Dict[str, Any],
    source: str = "MANUAL",
    batch_id: Optional[int] = None,
    db: Optional[Session] = None,
    commit: bool = True,
) -> models_db.InvoicePrediction:
    """
    Single authoritative entry point to score an invoice for fraud/error risk
    and create an InvoicePrediction ORM object.

    payload must contain:
      - invoice_quantity (float)
      - invoice_dollars (float)
      - Freight (float)
      - total_item_quantity (float)
      - total_item_dollars (float)
    and optional:
      - vendor_number (str)
      - po_number (str)
      - invoice_date (str)
    """
    ml_payload = {
        "invoice_quantity": float(payload["invoice_quantity"]),
        "invoice_dollars": float(payload["invoice_dollars"]),
        "Freight": float(payload.get("Freight", payload.get("freight", 0.0))),
        "total_item_quantity": float(payload["total_item_quantity"]),
        "total_item_dollars": float(payload["total_item_dollars"]),
    }

    predicted_flag, probability = ml_models.predict_invoice_flag(ml_payload)

    record = models_db.InvoicePrediction(
        vendor_number=payload.get("vendor_number"),
        po_number=payload.get("po_number"),
        invoice_date=payload.get("invoice_date"),
        invoice_quantity=ml_payload["invoice_quantity"],
        invoice_dollars=ml_payload["invoice_dollars"],
        freight=ml_payload["Freight"],
        total_item_quantity=ml_payload["total_item_quantity"],
        total_item_dollars=ml_payload["total_item_dollars"],
        predicted_flag=predicted_flag,
        risk_probability=probability,
        source=source,
        batch_id=batch_id,
    )

    if db is not None:
        db.add(record)
        if commit:
            db.commit()
            db.refresh(record)

    return record


def score_and_save_freight(
    dollars: float,
    vendor_number: Optional[str] = None,
    po_number: Optional[str] = None,
    invoice_date: Optional[str] = None,
    source: str = "MANUAL",
    batch_id: Optional[int] = None,
    db: Optional[Session] = None,
    commit: bool = True,
) -> models_db.FreightPrediction:
    """
    Single authoritative entry point to score freight costs and create a FreightPrediction ORM object.
    """
    predicted_freight = ml_models.predict_freight(float(dollars))

    record = models_db.FreightPrediction(
        vendor_number=vendor_number,
        po_number=po_number,
        invoice_date=invoice_date,
        dollars=float(dollars),
        predicted_freight=predicted_freight,
        source=source,
        batch_id=batch_id,
    )

    if db is not None:
        db.add(record)
        if commit:
            db.commit()
            db.refresh(record)

    return record
