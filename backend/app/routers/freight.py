from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app import models_db, schemas, ml_models

router = APIRouter(prefix="/api/freight", tags=["Freight Cost"])


@router.post("/predict", response_model=schemas.FreightPredictionOut)
def predict_freight(payload: schemas.FreightInput, db: Session = Depends(get_db)):
    """
    Estimate freight cost for a given invoice dollar amount and save it.
    """
    try:
        predicted_freight = ml_models.predict_freight(payload.Dollars)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model prediction failed: {exc}")

    record = models_db.FreightPrediction(
        dollars=payload.Dollars,
        predicted_freight=predicted_freight,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@router.get("/history", response_model=list[schemas.FreightPredictionOut])
def get_freight_history(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(models_db.FreightPrediction)
        .order_by(desc(models_db.FreightPrediction.created_at))
        .limit(limit)
        .all()
    )
    return rows
