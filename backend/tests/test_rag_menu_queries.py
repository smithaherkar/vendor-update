"""
Unit tests for the 17 deterministic SQL analytics queries, intent classification,
low-sample-size confidence guards, and response formatting in rag_service.py.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app import models_db, rag_service

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
        # Seed test data
        # Vendor VND-SMALL: 1 invoice (Flagged) -> Low sample (<5)
        db.add(models_db.InvoicePrediction(
            vendor_number="VND-SMALL",
            po_number="PO-101",
            invoice_date="2026-08-01",
            invoice_quantity=100.0,
            invoice_dollars=5000.0,
            freight=500.0,
            total_item_quantity=100.0,
            total_item_dollars=4000.0,
            predicted_flag=1,
            risk_probability=0.85,
            source="MANUAL",
        ))

        # Vendor VND-CLEAN: 6 invoices (0 Flagged) -> High sample (>=5), clean
        for i in range(1, 7):
            db.add(models_db.InvoicePrediction(
                vendor_number="VND-CLEAN",
                po_number=f"PO-CLN-{i}",
                invoice_date=f"2026-08-0{i}",
                invoice_quantity=50.0,
                invoice_dollars=2000.0,
                freight=100.0,
                total_item_quantity=50.0,
                total_item_dollars=2000.0,
                predicted_flag=0,
                risk_probability=0.05,
                source="MANUAL",
            ))

        # Vendor VND-LARGE: 8 invoices (4 Flagged) -> High sample (>=5), 50% rate
        for i in range(1, 9):
            is_flagged = 1 if i % 2 == 0 else 0
            db.add(models_db.InvoicePrediction(
                vendor_number="VND-LARGE",
                po_number=f"PO-LRG-{i}",
                invoice_date=f"2026-08-1{i}",
                invoice_quantity=200.0,
                invoice_dollars=10000.0 + (i * 1000),
                freight=300.0 + (i * 50),
                total_item_quantity=200.0,
                total_item_dollars=10000.0,
                predicted_flag=is_flagged,
                risk_probability=0.90 if is_flagged else 0.10,
                source="MANUAL",
            ))

        db.commit()
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


# =====================================================================
# TEST 1: Low Sample Size Caveats vs High Volume
# =====================================================================

def test_single_vendor_flag_stats_and_sample_guard(db_session):
    """Q1: Confirm low-sample caveat fires for vendor with 1 invoice but not for vendor with 6 invoices."""
    small_stats = rag_service.get_vendor_flag_stats(db_session, "VND-SMALL")
    assert small_stats["found"] is True
    assert small_stats["total_invoices"] == 1
    assert small_stats["flagged_count"] == 1
    assert small_stats["flag_rate_pct"] == 100.0
    assert small_stats["is_low_sample"] is True

    clean_stats = rag_service.get_vendor_flag_stats(db_session, "VND-CLEAN")
    assert clean_stats["found"] is True
    assert clean_stats["total_invoices"] == 6
    assert clean_stats["flagged_count"] == 0
    assert clean_stats["flag_rate_pct"] == 0.0
    assert clean_stats["is_low_sample"] is False


def test_ranked_vendors_by_flag_rate(db_session):
    """Q2: Confirm vendors are ranked by flag rate descending."""
    ranked = rag_service.get_ranked_vendors_by_flag_rate(db_session)
    assert len(ranked) == 3
    # VND-SMALL (100%), VND-LARGE (50%), VND-CLEAN (0%)
    assert ranked[0]["vendor_number"] == "VND-SMALL"
    assert ranked[0]["flag_rate_pct"] == 100.0
    assert ranked[1]["vendor_number"] == "VND-LARGE"
    assert ranked[1]["flag_rate_pct"] == 50.0
    assert ranked[2]["vendor_number"] == "VND-CLEAN"
    assert ranked[2]["flag_rate_pct"] == 0.0


def test_never_flagged_vendors(db_session):
    """Q3: Confirm only VND-CLEAN is returned in 100% clean list."""
    clean_list = rag_service.get_never_flagged_vendors(db_session)
    assert len(clean_list) == 1
    assert clean_list[0]["vendor_number"] == "VND-CLEAN"
    assert clean_list[0]["total_invoices"] == 6


def test_company_overall_flag_rate(db_session):
    """Q4: Confirm global company baseline calculations."""
    company = rag_service.get_company_overall_flag_rate(db_session)
    # Total = 1 (small) + 6 (clean) + 8 (large) = 15 invoices
    # Flagged = 1 (small) + 0 (clean) + 4 (large) = 5 invoices
    assert company["total_invoices"] == 15
    assert company["flagged_count"] == 5
    assert pytest.approx(company["overall_flag_rate_pct"], 0.1) == 33.33
    assert company["total_distinct_vendors"] == 3


def test_riskiest_invoice(db_session):
    """Q5: Confirm single riskiest invoice is identified."""
    riskiest = rag_service.get_riskiest_invoice(db_session)
    assert riskiest is not None
    assert riskiest["risk_probability_pct"] == 90.0
    assert riskiest["vendor_number"] == "VND-LARGE"


def test_total_spend_and_largest_invoice(db_session):
    """Q6 & Q8: Confirm spend aggregations and max invoice."""
    spend = rag_service.get_total_spend_by_vendor(db_session)
    assert spend[0]["vendor_number"] == "VND-LARGE"

    largest = rag_service.get_largest_invoice(db_session)
    assert largest is not None
    assert largest["vendor_number"] == "VND-LARGE"
    assert largest["invoice_dollars"] == 18000.0  # 10000 + 8*1000


def test_vendor_comparison(db_session):
    """Q17: Confirm side-by-side comparison between two vendors."""
    comparison = rag_service.compare_two_vendors(db_session, "VND-CLEAN", "VND-LARGE")
    va = comparison["vendor_a"]
    vb = comparison["vendor_b"]

    assert va["vendor_number"] == "VND-CLEAN"
    assert va["total_invoices"] == 6
    assert va["flag_rate_pct"] == 0.0
    assert va["is_low_sample"] is False

    assert vb["vendor_number"] == "VND-LARGE"
    assert vb["total_invoices"] == 8
    assert vb["flag_rate_pct"] == 50.0
    assert vb["is_low_sample"] is False


def test_low_history_vendors_query(db_session):
    """Q16: Confirm detection of vendors with < 5 invoices."""
    low_hist = rag_service.get_low_history_vendors(db_session, threshold=5)
    assert len(low_hist) == 1
    assert low_hist[0]["vendor_number"] == "VND-SMALL"
    assert low_hist[0]["invoice_count"] == 1


# =====================================================================
# TEST 2: Intent Routing & Endpoints
# =====================================================================

def test_api_ask_assistant_endpoint(client):
    """Test POST /api/rag/ask endpoint with various question intents."""
    # Test Q1
    res1 = client.post("/api/rag/ask", json={"message": "What is the flag rate for VND-SMALL?"})
    assert res1.status_code == 200
    reply1 = res1.json()["reply"]
    assert "VND-SMALL" in reply1
    assert "Low Sample Size Caveat" in reply1  # Guard triggered!

    # Test Q2
    res2 = client.post("/api/rag/ask", json={"message": "Which vendors have the highest flag rate?"})
    assert res2.status_code == 200
    assert "Vendors Ranked by Flag Rate" in res2.json()["reply"]

    # Test Q4
    res3 = client.post("/api/rag/ask", json={"message": "What is the company overall flag rate?"})
    assert res3.status_code == 200
    reply3 = res3.json()["reply"]
    assert "33.33%" in reply3 or "33.3%" in reply3
    assert "15" in reply3  # 15 total invoices

    # Test Delay Gap (Honest unsupported message)
    res_delay = client.post("/api/rag/ask", json={"message": "What is the average shipping delay for VND-1001?"})
    assert res_delay.status_code == 200
    assert "Delivery and delay questions are not supported" in res_delay.json()["reply"]

    # Test Generic Unsupported question
    res_unsupported = client.post("/api/rag/ask", json={"message": "What is the capital of France?"})
    assert res_unsupported.status_code == 200
    assert "Unsupported Query" in res_unsupported.json()["reply"]
