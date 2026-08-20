from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app import models_db, schemas

router = APIRouter(prefix="/api/batches", tags=["Upload Batches"])


@router.get("", response_model=List[schemas.UploadBatchOut])
def list_batches(limit: int = 50, db: Session = Depends(get_db)):
    """List all upload batch jobs, newest first."""
    batches = (
        db.query(models_db.UploadBatch)
        .order_by(desc(models_db.UploadBatch.uploaded_at))
        .limit(limit)
        .all()
    )
    return batches


@router.get("/{batch_uuid}/errors", response_model=List[schemas.BatchRowErrorOut])
def get_batch_errors(batch_uuid: str, db: Session = Depends(get_db)):
    """Get all row-level validation and processing errors recorded for a batch."""
    batch = (
        db.query(models_db.UploadBatch)
        .filter(models_db.UploadBatch.batch_uuid == batch_uuid)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_uuid} not found.")

    errors = (
        db.query(models_db.BatchRowError)
        .filter(models_db.BatchRowError.batch_id == batch.id)
        .order_by(models_db.BatchRowError.row_number)
        .all()
    )
    return errors


@router.get("/sample-template/invoice")
def get_invoice_template():
    """Download standard sample CSV template for Invoice Risk batch upload."""
    content = "VendorNumber,PONumber,InvoiceDate,invoice_quantity,invoice_dollars,Freight\nVND-1001,PO-5001,2026-08-01,6000,58000,300\nVND-1002,PO-5002,2026-08-02,1200,14500,150\n"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sample_invoice_batch.csv"'},
    )


@router.get("/sample-template/freight")
def get_freight_template():
    """Download standard sample CSV template for Freight Cost batch upload."""
    content = "VendorNumber,PONumber,InvoiceDate,Dollars\nVND-1001,PO-5001,2026-08-01,25000\nVND-1002,PO-5002,2026-08-02,42000\n"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sample_freight_batch.csv"'},
    )
