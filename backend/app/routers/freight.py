from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db, SessionLocal
from app import models_db, schemas, services, batch_processor

router = APIRouter(prefix="/api/freight", tags=["Freight Cost"])


@router.post("/predict", response_model=schemas.FreightPredictionOut)
def predict_freight(payload: schemas.FreightInput, db: Session = Depends(get_db)):
    """
    Estimate freight cost for a given invoice dollar amount and save it.
    Shared implementation using services.score_and_save_freight.
    """
    try:
        record = services.score_and_save_freight(
            dollars=payload.Dollars,
            vendor_number=payload.vendor_number,
            po_number=payload.po_number,
            invoice_date=payload.invoice_date,
            source="MANUAL",
            db=db,
            commit=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model prediction failed: {exc}")

    return record


@router.post("/batch-upload", response_model=schemas.BatchUploadResponse)
async def batch_upload_freight(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV file for batch freight cost estimation.
    """
    content = await file.read()
    batch = batch_processor.check_and_create_batch(
        db=db,
        filename=file.filename or "freight.csv",
        content=content,
        batch_type="FREIGHT",
    )

    line_count = content.count(b"\n")

    if line_count > 500:
        def run_bg(batch_id: int, file_bytes: bytes):
            bg_db = SessionLocal()
            try:
                batch_processor.process_freight_batch_sync(bg_db, batch_id, file_bytes)
            finally:
                bg_db.close()

        background_tasks.add_task(run_bg, batch.id, content)
        return schemas.BatchUploadResponse(
            message="Freight batch processing started in background.",
            batch_uuid=batch.batch_uuid,
            filename=batch.filename,
            status="PROCESSING",
            is_async=True,
        )
    else:
        batch = batch_processor.process_freight_batch_sync(db, batch.id, content)
        return schemas.BatchUploadResponse(
            message="Freight batch processing completed.",
            batch_uuid=batch.batch_uuid,
            filename=batch.filename,
            status=batch.status,
            is_async=False,
            row_count=batch.row_count,
            success_count=batch.success_count,
            duplicate_count=batch.duplicate_count,
            error_count=batch.error_count,
        )


@router.get("/batch-status/{batch_uuid}", response_model=schemas.UploadBatchOut)
def get_freight_batch_status(batch_uuid: str, db: Session = Depends(get_db)):
    """Check status of a freight batch upload."""
    batch = (
        db.query(models_db.UploadBatch)
        .filter(models_db.UploadBatch.batch_uuid == batch_uuid)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_uuid} not found.")
    return batch


@router.get("/history", response_model=list[schemas.FreightPredictionOut])
def get_freight_history(
    limit: int = 50,
    source: Optional[str] = None,
    batch_uuid: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return freight predictions with optional source and batch_uuid filters."""
    query = db.query(models_db.FreightPrediction)

    if source:
        query = query.filter(models_db.FreightPrediction.source == source.upper())

    if batch_uuid:
        batch = (
            db.query(models_db.UploadBatch)
            .filter(models_db.UploadBatch.batch_uuid == batch_uuid)
            .first()
        )
        if batch:
            query = query.filter(models_db.FreightPrediction.batch_id == batch.id)
        else:
            return []

    rows = query.order_by(desc(models_db.FreightPrediction.created_at)).limit(limit).all()

    batch_ids = {r.batch_id for r in rows if r.batch_id}
    batch_uuid_map = {}
    if batch_ids:
        batches = db.query(models_db.UploadBatch).filter(models_db.UploadBatch.id.in_(batch_ids)).all()
        batch_uuid_map = {b.id: b.batch_uuid for b in batches}

    return [
        schemas.FreightPredictionOut(
            id=r.id,
            vendor_number=r.vendor_number,
            po_number=r.po_number,
            invoice_date=r.invoice_date,
            dollars=r.dollars,
            predicted_freight=r.predicted_freight,
            source=r.source,
            batch_id=r.batch_id,
            batch_uuid=batch_uuid_map.get(r.batch_id),
            created_at=r.created_at,
        )
        for r in rows
    ]

