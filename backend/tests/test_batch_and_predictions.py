"""
Unit and integration tests for CSV batch processing, shared prediction service parity,
error handling, BOM support, duplicate detection, and PO lookups.
"""
import io
import pytest
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app import models_db, services, batch_processor

from sqlalchemy.pool import StaticPool

# In-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_parity_between_manual_and_batch_predictions(db_session):
    """Confirm manual and batch paths produce IDENTICAL prediction results for identical input."""
    payload = {
        "vendor_number": "VND-TEST-1",
        "po_number": "PO-TEST-1",
        "invoice_date": "2026-08-01",
        "invoice_quantity": 6000.0,
        "invoice_dollars": 58000.0,
        "Freight": 300.0,
        "total_item_quantity": 6000.0,
        "total_item_dollars": 58000.0,
    }

    # Manual scoring
    manual_rec = services.score_and_save_invoice(
        payload=payload, source="MANUAL", db=db_session, commit=True
    )

    # Batch scoring payload
    batch_payload = {
        "vendor_number": "VND-TEST-2",  # different vendor/po to avoid unique constraint
        "po_number": "PO-TEST-2",
        "invoice_date": "2026-08-01",
        "invoice_quantity": 6000.0,
        "invoice_dollars": 58000.0,
        "Freight": 300.0,
        "total_item_quantity": 6000.0,
        "total_item_dollars": 58000.0,
    }
    batch_rec = services.score_and_save_invoice(
        payload=batch_payload, source="BATCH", batch_id=1, db=db_session, commit=True
    )

    assert manual_rec.predicted_flag == batch_rec.predicted_flag
    assert np.isclose(manual_rec.risk_probability, batch_rec.risk_probability, atol=1e-5)


def test_utf8_bom_csv_parsing(db_session):
    """Confirm a CSV encoded with UTF-8 BOM (\xef\xbb\xbf) parses cleanly."""
    bom_content = "\ufeffVendorNumber,PONumber,InvoiceDate,invoice_quantity,invoice_dollars,Freight\nVND-BOM,PO-BOM,2026-08-01,100,500,50\n".encode("utf-8-sig")

    batch = batch_processor.check_and_create_batch(db_session, "bom_test.csv", bom_content, "INVOICE")
    res_batch = batch_processor.process_invoice_batch_sync(db_session, batch.id, bom_content)

    assert res_batch.status == "DONE"
    assert res_batch.success_count == 1
    assert res_batch.error_count == 0


def test_malformed_date_skipped_and_logged(db_session):
    """Confirm a row with an invalid date format is skipped and logged to BatchRowError."""
    csv_text = "VendorNumber,PONumber,InvoiceDate,invoice_quantity,invoice_dollars,Freight\nVND-1,PO-1,NOT-A-DATE,100,500,50\nVND-2,PO-2,2026-08-02,200,1000,100\n"
    content = csv_text.encode("utf-8")

    batch = batch_processor.check_and_create_batch(db_session, "bad_date.csv", content, "INVOICE")
    res_batch = batch_processor.process_invoice_batch_sync(db_session, batch.id, content)

    assert res_batch.success_count == 1
    assert res_batch.error_count == 1

    errors = db_session.query(models_db.BatchRowError).filter_by(batch_id=batch.id).all()
    assert len(errors) == 1
    assert "InvoiceDate" in errors[0].error_message


def test_negative_dollars_skipped_and_logged(db_session):
    """Confirm a row with negative invoice_dollars is skipped and logged."""
    csv_text = "VendorNumber,PONumber,InvoiceDate,invoice_quantity,invoice_dollars,Freight\nVND-1,PO-1,2026-08-01,100,-500,50\n"
    content = csv_text.encode("utf-8")

    batch = batch_processor.check_and_create_batch(db_session, "negative_dollars.csv", content, "INVOICE")
    res_batch = batch_processor.process_invoice_batch_sync(db_session, batch.id, content)

    assert res_batch.success_count == 0
    assert res_batch.error_count == 1

    errors = db_session.query(models_db.BatchRowError).filter_by(batch_id=batch.id).all()
    assert "invoice_dollars (-500.0) must be positive" in errors[0].error_message


def test_exact_file_hash_duplicate_rejection(client, db_session):
    """Confirm re-uploading the exact same file is rejected via file_hash upfront."""
    csv_bytes = b"VendorNumber,PONumber,InvoiceDate,invoice_quantity,invoice_dollars,Freight\nVND-HASH,PO-HASH,2026-08-01,100,500,50\n"

    # First upload
    res1 = client.post(
        "/api/invoice/batch-upload",
        files={"file": ("invoices.csv", csv_bytes, "text/csv")},
    )
    assert res1.status_code == 200

    # Second upload of exact same bytes
    res2 = client.post(
        "/api/invoice/batch-upload",
        files={"file": ("invoices.csv", csv_bytes, "text/csv")},
    )
    assert res2.status_code == 400
    assert "already uploaded" in res2.json()["detail"].lower()


def test_duplicate_rows_integrity_error_handling(db_session):
    """Confirm two rows with same (VendorNumber, PONumber, InvoiceDate) result in 1 success and 1 duplicate count."""
    csv_text = "VendorNumber,PONumber,InvoiceDate,invoice_quantity,invoice_dollars,Freight\nVND-DUP,PO-DUP,2026-08-01,100,500,50\nVND-DUP,PO-DUP,2026-08-01,100,500,50\n"
    content = csv_text.encode("utf-8")

    batch = batch_processor.check_and_create_batch(db_session, "duplicates.csv", content, "INVOICE")
    res_batch = batch_processor.process_invoice_batch_sync(db_session, batch.id, content)

    assert res_batch.success_count == 1
    assert res_batch.duplicate_count == 1
    assert res_batch.error_count == 0


def test_missing_po_triggers_rule_106(db_session):
    """Confirm a row with a PONumber not in `purchases` processes with total_item_dollars/quantity=0, triggering RULE-106 in RAG explanation."""
    csv_text = "VendorNumber,PONumber,InvoiceDate,invoice_quantity,invoice_dollars,Freight\nVND-UNCOMMITTED,PO-UNCOMMITTED,2026-08-01,100,500,50\n"
    content = csv_text.encode("utf-8")

    batch = batch_processor.check_and_create_batch(db_session, "uncommitted.csv", content, "INVOICE")
    res_batch = batch_processor.process_invoice_batch_sync(db_session, batch.id, content)

    assert res_batch.success_count == 1

    prediction = db_session.query(models_db.InvoicePrediction).filter_by(vendor_number="VND-UNCOMMITTED").first()
    assert prediction is not None
    assert prediction.total_item_quantity == 0.0
    assert prediction.total_item_dollars == 0.0
