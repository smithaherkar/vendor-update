"""
CSV Ingestion & Batch Processor Engine.
Handles file validation, encoding detection, bulk PO lookup, chunked transactions,
row-level validation, duplicate handling, and stuck job cleanup.
"""
import io
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, List, Dict, Any, Optional

import pandas as pd
from sqlalchemy import tuple_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app import models_db, services

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
SANITY_DOLLAR_CEILING = 10_000_000.0   # $10,000,000


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def check_and_create_batch(
    db: Session,
    filename: str,
    content: bytes,
    batch_type: str,
) -> models_db.UploadBatch:
    """
    Validates file format, size, non-emptiness, and whole-file duplicate SHA256 hash.
    Creates and returns a new UploadBatch record in PROCESSING status.
    """
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds the 10MB limit.")

    file_hash = compute_file_hash(content)

    existing = (
        db.query(models_db.UploadBatch)
        .filter(models_db.UploadBatch.file_hash == file_hash)
        .first()
    )
    if existing:
        if existing.status == "FAILED":
            logger.info(f"Removing prior FAILED batch {existing.batch_uuid} for hash {file_hash} to allow retry.")
            db.delete(existing)
            db.commit()
        else:
            uploaded_str = existing.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if existing.uploaded_at else "a prior date"
            raise HTTPException(
                status_code=400,
                detail=f"This exact CSV file was already uploaded as batch {existing.batch_uuid} on {uploaded_str} (Status: {existing.status}).",
            )

    batch_uuid_str = str(uuid.uuid4())
    batch = models_db.UploadBatch(
        batch_uuid=batch_uuid_str,
        batch_type=batch_type,
        filename=filename,
        file_hash=file_hash,
        status="PROCESSING",
    )
    db.add(batch)
    try:
        db.commit()
        db.refresh(batch)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This exact CSV file has already been uploaded previously.",
        )
    return batch


def decode_csv_content(content: bytes) -> str:
    """Tries utf-8-sig, utf-8, and latin-1 encodings sequentially."""
    for enc in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            continue
    raise HTTPException(
        status_code=400,
        detail="Could not decode CSV file. Please ensure the file is UTF-8 or Latin-1 encoded.",
    )


def normalize_and_validate_dataframe(
    csv_text: str,
    required_cols: List[str],
) -> pd.DataFrame:
    """
    Parses CSV text into pandas DataFrame, normalizes headers, and verifies required columns.
    """
    try:
        df = pd.read_csv(io.StringIO(csv_text), dtype=str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV format: {exc}")

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV file contains no data rows.")

    # Strip column names and build map
    col_map = {str(col).strip(): str(col).strip() for col in df.columns}
    df.rename(columns=col_map, inplace=True)

    # Normalize map for case-insensitive matching
    lower_map = {col.lower(): col for col in df.columns}

    canonical_cols = {}
    missing = []
    for req in required_cols:
        req_lower = req.lower()
        if req_lower in lower_map:
            canonical_cols[lower_map[req_lower]] = req
        else:
            missing.append(req)

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required CSV columns: {missing}. Standard columns required: {required_cols}",
        )

    df.rename(columns=canonical_cols, inplace=True)
    return df


def bulk_lookup_purchases(db: Session, vendor_po_pairs: List[Tuple[str, str]]) -> Dict[Tuple[str, str], Tuple[float, float]]:
    """
    Runs a single bulk query against the purchases table for all distinct (vendor_number, po_number) pairs.
    Returns a dictionary mapping (vendor_number, po_number) -> (total_item_quantity, total_item_dollars).
    """
    if not vendor_po_pairs:
        return {}

    po_dict = {}
    chunk_size = 500
    for i in range(0, len(vendor_po_pairs), chunk_size):
        chunk = vendor_po_pairs[i : i + chunk_size]
        query = db.query(models_db.Purchase).filter(
            tuple_(models_db.Purchase.vendor_number, models_db.Purchase.po_number).in_(chunk)
        )
        for row in query.all():
            po_dict[(str(row.vendor_number).strip(), str(row.po_number).strip())] = (
                float(row.total_item_quantity),
                float(row.total_item_dollars),
            )
    return po_dict


def process_invoice_batch_sync(db: Session, batch_id: int, content: bytes) -> models_db.UploadBatch:
    """
    Processes an Invoice CSV batch synchronously or within a background task.
    """
    batch = db.get(models_db.UploadBatch, batch_id)
    if not batch:
        return None

    try:
        csv_text = decode_csv_content(content)
        required_cols = ["VendorNumber", "PONumber", "InvoiceDate", "invoice_quantity", "invoice_dollars", "Freight"]
        
        # Flexibly accept capitalized column names as well
        try:
            df = normalize_and_validate_dataframe(csv_text, required_cols)
        except HTTPException:
            # Try alternate standard naming
            alt_cols = ["VendorNumber", "PONumber", "InvoiceDate", "InvoiceQuantity", "InvoiceDollars", "Freight"]
            df = normalize_and_validate_dataframe(csv_text, alt_cols)
            df.rename(
                columns={
                    "InvoiceQuantity": "invoice_quantity",
                    "InvoiceDollars": "invoice_dollars",
                },
                inplace=True,
            )

        df["parsed_date"] = pd.to_datetime(df["InvoiceDate"], format="%Y-%m-%d", errors="coerce")

        batch.row_count = len(df)
        db.commit()

        # Step 1: Collect pairs for bulk PO lookup
        valid_rows = []
        pairs_set = set()

        for idx, row in df.iterrows():
            row_num = idx + 1
            raw_json = json.dumps(row.to_dict(), default=str)
            vendor_num = str(row.get("VendorNumber", "")).strip() if pd.notna(row.get("VendorNumber")) else ""
            po_num = str(row.get("PONumber", "")).strip() if pd.notna(row.get("PONumber")) else ""
            parsed_dt = row.get("parsed_date")

            # Validation checks
            if not vendor_num or not po_num or vendor_num.lower() == "nan" or po_num.lower() == "nan":
                log_row_error(db, batch.id, row_num, raw_json, "VendorNumber or PONumber is missing or null.")
                batch.error_count += 1
                continue

            if pd.isna(parsed_dt):
                log_row_error(db, batch.id, row_num, raw_json, f"InvoiceDate '{row.get('InvoiceDate')}' is not a valid YYYY-MM-DD date.")
                batch.error_count += 1
                continue

            try:
                inv_qty = float(row.get("invoice_quantity"))
                inv_dlr = float(row.get("invoice_dollars"))
                frt = float(row.get("Freight"))
            except (ValueError, TypeError):
                log_row_error(db, batch.id, row_num, raw_json, "Numeric conversion failed for invoice_quantity, invoice_dollars, or Freight.")
                batch.error_count += 1
                continue

            if inv_qty <= 0:
                log_row_error(db, batch.id, row_num, raw_json, f"invoice_quantity ({inv_qty}) must be positive.")
                batch.error_count += 1
                continue

            if inv_dlr <= 0:
                log_row_error(db, batch.id, row_num, raw_json, f"invoice_dollars ({inv_dlr}) must be positive.")
                batch.error_count += 1
                continue

            if frt < 0:
                log_row_error(db, batch.id, row_num, raw_json, f"Freight ({frt}) cannot be negative.")
                batch.error_count += 1
                continue

            if inv_dlr > SANITY_DOLLAR_CEILING or frt > SANITY_DOLLAR_CEILING:
                log_row_error(db, batch.id, row_num, raw_json, f"Amount exceeds safety ceiling ${SANITY_DOLLAR_CEILING:,.2f}.")
                batch.error_count += 1
                continue

            inv_date_str = parsed_dt.strftime("%Y-%m-%d")
            pairs_set.add((vendor_num, po_num))
            valid_rows.append({
                "row_num": row_num,
                "raw_json": raw_json,
                "vendor_number": vendor_num,
                "po_number": po_num,
                "invoice_date": inv_date_str,
                "invoice_quantity": inv_qty,
                "invoice_dollars": inv_dlr,
                "Freight": frt,
                "total_item_quantity": row.get("total_item_quantity"),
                "total_item_dollars": row.get("total_item_dollars"),
            })

        # Bulk PO Lookup
        po_lookup = bulk_lookup_purchases(db, list(pairs_set))

        # Chunked database insertions (100 rows per chunk)
        chunk_size = 100
        for i in range(0, len(valid_rows), chunk_size):
            chunk = valid_rows[i : i + chunk_size]
            for item in chunk:
                v_num = item["vendor_number"]
                p_num = item["po_number"]

                # Total PO amounts from lookup or explicit payload
                if item["total_item_quantity"] is not None and pd.notna(item["total_item_quantity"]):
                    tot_qty = float(item["total_item_quantity"])
                    tot_dlr = float(item["total_item_dollars"])
                else:
                    tot_qty, tot_dlr = po_lookup.get((v_num, p_num), (0.0, 0.0))

                payload = {
                    "vendor_number": v_num,
                    "po_number": p_num,
                    "invoice_date": item["invoice_date"],
                    "invoice_quantity": item["invoice_quantity"],
                    "invoice_dollars": item["invoice_dollars"],
                    "Freight": item["Freight"],
                    "total_item_quantity": tot_qty,
                    "total_item_dollars": tot_dlr,
                }

                nested = db.begin_nested()
                try:
                    services.score_and_save_invoice(
                        payload=payload,
                        source="BATCH",
                        batch_id=batch.id,
                        db=db,
                        commit=False,
                    )
                    nested.commit()
                    batch.success_count += 1
                except IntegrityError:
                    nested.rollback()
                    batch.duplicate_count += 1
                except Exception as exc:
                    nested.rollback()
                    log_row_error(db, batch.id, item["row_num"], item["raw_json"], f"Unexpected processing error: {exc}")
                    batch.error_count += 1

            db.commit()

        batch.status = "DONE"
        batch.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        logger.error(f"Batch {batch.batch_uuid} failed with top-level error: {exc}", exc_info=True)
        batch.status = "FAILED"
        batch.completed_at = datetime.now(timezone.utc)
        db.commit()

    return batch


def process_freight_batch_sync(db: Session, batch_id: int, content: bytes) -> models_db.UploadBatch:
    """
    Processes a Freight CSV batch synchronously or within a background task.
    """
    batch = db.get(models_db.UploadBatch, batch_id)
    if not batch:
        return None

    try:
        csv_text = decode_csv_content(content)
        required_cols = ["Dollars"]
        
        # Try dataframe normalization
        try:
            df = normalize_and_validate_dataframe(csv_text, required_cols)
        except HTTPException:
            alt_cols = ["invoice_dollars"]
            df = normalize_and_validate_dataframe(csv_text, alt_cols)
            df.rename(columns={"invoice_dollars": "Dollars"}, inplace=True)

        batch.row_count = len(df)
        db.commit()

        if "InvoiceDate" in df.columns:
            df["parsed_date"] = pd.to_datetime(df["InvoiceDate"], format="%Y-%m-%d", errors="coerce")
        else:
            df["parsed_date"] = None

        chunk_size = 100
        valid_rows = []

        for idx, row in df.iterrows():
            row_num = idx + 1
            raw_json = json.dumps(row.to_dict(), default=str)
            
            vendor_num = str(row.get("VendorNumber", "")).strip() if pd.notna(row.get("VendorNumber")) else None
            po_num = str(row.get("PONumber", "")).strip() if pd.notna(row.get("PONumber")) else None
            
            if vendor_num == "nan" or vendor_num == "":
                vendor_num = None
            if po_num == "nan" or po_num == "":
                po_num = None

            parsed_dt = row.get("parsed_date")
            inv_date_str = parsed_dt.strftime("%Y-%m-%d") if (parsed_dt is not None and pd.notna(parsed_dt)) else None

            try:
                dlrs = float(row.get("Dollars"))
            except (ValueError, TypeError):
                log_row_error(db, batch.id, row_num, raw_json, "Dollars must be a valid number.")
                batch.error_count += 1
                continue

            if dlrs <= 0:
                log_row_error(db, batch.id, row_num, raw_json, f"Dollars ({dlrs}) must be positive.")
                batch.error_count += 1
                continue

            if dlrs > SANITY_DOLLAR_CEILING:
                log_row_error(db, batch.id, row_num, raw_json, f"Dollars exceeds safety ceiling ${SANITY_DOLLAR_CEILING:,.2f}.")
                batch.error_count += 1
                continue

            valid_rows.append({
                "row_num": row_num,
                "raw_json": raw_json,
                "vendor_number": vendor_num,
                "po_number": po_num,
                "invoice_date": inv_date_str,
                "dollars": dlrs,
            })

        for i in range(0, len(valid_rows), chunk_size):
            chunk = valid_rows[i : i + chunk_size]
            for item in chunk:
                nested = db.begin_nested()
                try:
                    services.score_and_save_freight(
                        dollars=item["dollars"],
                        vendor_number=item["vendor_number"],
                        po_number=item["po_number"],
                        invoice_date=item["invoice_date"],
                        source="BATCH",
                        batch_id=batch.id,
                        db=db,
                        commit=False,
                    )
                    nested.commit()
                    batch.success_count += 1
                except IntegrityError:
                    nested.rollback()
                    batch.duplicate_count += 1
                except Exception as exc:
                    nested.rollback()
                    log_row_error(db, batch.id, item["row_num"], item["raw_json"], f"Unexpected error: {exc}")
                    batch.error_count += 1

            db.commit()

        batch.status = "DONE"
        batch.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as exc:
        logger.error(f"Freight batch {batch.batch_uuid} failed: {exc}", exc_info=True)
        batch.status = "FAILED"
        batch.completed_at = datetime.now(timezone.utc)
        db.commit()

    return batch


def log_row_error(db: Session, batch_id: int, row_number: int, raw_json: str, message: str):
    """Utility to persist a BatchRowError record."""
    err_record = models_db.BatchRowError(
        batch_id=batch_id,
        row_number=row_number,
        raw_row_json=raw_json,
        error_message=message,
    )
    db.add(err_record)


def cleanup_stuck_batches(db: Session, max_minutes: int = 30):
    """
    Marks any UploadBatch still in PROCESSING status after max_minutes as FAILED — timed out.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_minutes)
    stuck_batches = (
        db.query(models_db.UploadBatch)
        .filter(models_db.UploadBatch.status == "PROCESSING")
        .filter(models_db.UploadBatch.uploaded_at <= cutoff)
        .all()
    )
    for b in stuck_batches:
        b.status = "FAILED — timed out"
        b.completed_at = datetime.now(timezone.utc)
        logger.warning(f"Batch {b.batch_uuid} marked as timed out after {max_minutes} minutes.")
    if stuck_batches:
        db.commit()
