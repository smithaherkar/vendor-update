from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db, SessionLocal
from app import models_db, schemas, services, rag_service, batch_processor

router = APIRouter(prefix="/api/invoice", tags=["Invoice Risk"])


@router.post("/predict", response_model=schemas.InvoicePredictionOut)
def predict_invoice(payload: schemas.InvoiceInput, db: Session = Depends(get_db)):
    """
    Score one invoice for fraud/error risk and save the result to Postgres/SQLite.
    Shared implementation using services.score_and_save_invoice.
    """
    try:
        record = services.score_and_save_invoice(
            payload=payload.model_dump(),
            source="MANUAL",
            db=db,
            commit=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model prediction failed: {exc}")

    return schemas.InvoicePredictionOut(
        id=record.id,
        vendor_number=record.vendor_number,
        po_number=record.po_number,
        invoice_date=record.invoice_date,
        invoice_dollars=record.invoice_dollars,
        freight=record.freight,
        predicted_flag=record.predicted_flag,
        risk_label="FLAGGED" if record.predicted_flag == 1 else "CLEARED",
        risk_probability=record.risk_probability,
        source=record.source,
        batch_id=record.batch_id,
        created_at=record.created_at,
    )


@router.post("/batch-upload", response_model=schemas.BatchUploadResponse)
async def batch_upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV file of invoices.
    Files > 500 rows are processed asynchronously via BackgroundTasks.
    """
    content = await file.read()
    batch = batch_processor.check_and_create_batch(
        db=db,
        filename=file.filename or "invoices.csv",
        content=content,
        batch_type="INVOICE",
    )

    # Quick estimate of line count
    line_count = content.count(b"\n")

    if line_count > 500:
        # Background task needs its own Session
        def run_bg(batch_id: int, file_bytes: bytes):
            bg_db = SessionLocal()
            try:
                batch_processor.process_invoice_batch_sync(bg_db, batch_id, file_bytes)
            finally:
                bg_db.close()

        background_tasks.add_task(run_bg, batch.id, content)
        return schemas.BatchUploadResponse(
            message="Batch processing started in background.",
            batch_uuid=batch.batch_uuid,
            filename=batch.filename,
            status="PROCESSING",
            is_async=True,
        )
    else:
        # Synchronous processing for smaller files
        batch = batch_processor.process_invoice_batch_sync(db, batch.id, content)
        return schemas.BatchUploadResponse(
            message="Batch processing completed.",
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
def get_invoice_batch_status(batch_uuid: str, db: Session = Depends(get_db)):
    """Check current status and row counters for an invoice batch upload."""
    batch = (
        db.query(models_db.UploadBatch)
        .filter(models_db.UploadBatch.batch_uuid == batch_uuid)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_uuid} not found.")
    return batch


@router.get("/{invoice_id}/explain", response_model=schemas.InvoiceExplainOut)
def explain_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """
    RAG-style audit explanation for a saved prediction:
    discrepancy math + RULE-101..106 + a Gemini-written Markdown summary.
    """
    record = (
        db.query(models_db.InvoicePrediction)
        .filter(models_db.InvoicePrediction.id == invoice_id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"Invoice prediction #{invoice_id} not found")

    payload = {
        "invoice_quantity": record.invoice_quantity,
        "invoice_dollars": record.invoice_dollars,
        "Freight": record.freight,
        "total_item_quantity": record.total_item_quantity,
        "total_item_dollars": record.total_item_dollars,
    }
    result = rag_service.explain_invoice_flag(
        payload, record.predicted_flag, record.risk_probability
    )

    return schemas.InvoiceExplainOut(id=record.id, **result)


@router.get("/history", response_model=list[schemas.InvoicePredictionOut])
def get_invoice_history(
    limit: int = 50,
    source: Optional[str] = None,
    batch_uuid: Optional[str] = None,
    flagged_only: bool = False,
    db: Session = Depends(get_db),
):
    """
    Return invoice predictions with optional source, batch_uuid, and flagged_only filters.
    """
    query = db.query(models_db.InvoicePrediction)

    if source:
        query = query.filter(models_db.InvoicePrediction.source == source.upper())

    if batch_uuid:
        batch = (
            db.query(models_db.UploadBatch)
            .filter(models_db.UploadBatch.batch_uuid == batch_uuid)
            .first()
        )
        if batch:
            query = query.filter(models_db.InvoicePrediction.batch_id == batch.id)
        else:
            return []

    if flagged_only:
        query = query.filter(models_db.InvoicePrediction.predicted_flag == 1)

    rows = query.order_by(desc(models_db.InvoicePrediction.created_at)).limit(limit).all()

    # Map batch_id -> batch_uuid for output
    batch_ids = {r.batch_id for r in rows if r.batch_id}
    batch_uuid_map = {}
    if batch_ids:
        batches = db.query(models_db.UploadBatch).filter(models_db.UploadBatch.id.in_(batch_ids)).all()
        batch_uuid_map = {b.id: b.batch_uuid for b in batches}

    return [
        schemas.InvoicePredictionOut(
            id=r.id,
            vendor_number=r.vendor_number,
            po_number=r.po_number,
            invoice_date=r.invoice_date,
            invoice_dollars=r.invoice_dollars,
            freight=r.freight,
            predicted_flag=r.predicted_flag,
            risk_label="FLAGGED" if r.predicted_flag == 1 else "CLEARED",
            risk_probability=r.risk_probability,
            source=r.source,
            batch_id=r.batch_id,
            batch_uuid=batch_uuid_map.get(r.batch_id),
            created_at=r.created_at,
        )
        for r in rows
    ]

