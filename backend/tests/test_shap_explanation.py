"""
Unit tests for SHAP Explainability in the Vendor Intelligence & Performance System.
Covers:
1. ML TreeExplainer calculation, additivity, and mathematical consistency in ml_models.py
2. API endpoints: GET /api/invoice/{id}/explain and POST /api/invoice/explain
3. RAG AI Assistant Q18_EXPLAIN_INVOICE_ANOMALY intent classification and deterministic report formatting
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app import models_db, ml_models, rag_service

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
        # Seed test invoice #1: High risk flagged invoice (matches model flag=1)
        inv1 = models_db.InvoicePrediction(
            id=1,
            vendor_number="VND-RISK",
            po_number="PO-9999",
            invoice_date="2026-09-15",
            invoice_quantity=8000.0,
            invoice_dollars=95000.0,
            freight=5000.0,
            total_item_quantity=2000.0,
            total_item_dollars=15000.0,
            predicted_flag=1,
            risk_probability=0.88,
            source="MANUAL",
        )
        db.add(inv1)

        # Seed test invoice #2: Clean cleared invoice
        inv2 = models_db.InvoicePrediction(
            id=2,
            vendor_number="VND-SAFE",
            po_number="PO-1001",
            invoice_date="2026-09-16",
            invoice_quantity=50.0,
            invoice_dollars=1200.0,
            freight=40.0,
            total_item_quantity=50.0,
            total_item_dollars=1200.0,
            predicted_flag=0,
            risk_probability=0.02,
            source="MANUAL",
        )
        db.add(inv2)
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


# ==============================================================================
# 1. ML Layer (TreeExplainer) Tests
# ==============================================================================

def test_shap_explanation_structure():
    """Verify explain_invoice_flag returns exact keys and 5 feature attributions."""
    payload = {
        "invoice_quantity": 6000.0,
        "invoice_dollars": 58000.0,
        "Freight": 300.0,
        "total_item_quantity": 6000.0,
        "total_item_dollars": 58000.0,
    }
    result = ml_models.explain_invoice_flag(payload)

    assert "predicted_flag" in result
    assert result["predicted_flag"] in [0, 1]
    assert "risk_label" in result
    assert result["risk_label"] in ["FLAGGED", "CLEARED"]
    assert "risk_probability" in result
    assert 0.0 <= result["risk_probability"] <= 1.0
    assert "base_risk" in result
    assert 0.0 <= result["base_risk"] <= 1.0
    assert "summary" in result
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 0

    features = result["features"]
    assert len(features) == 5
    feature_names = {f["feature"] for f in features}
    expected_names = {
        "invoice_quantity",
        "invoice_dollars",
        "Freight",
        "total_item_quantity",
        "total_item_dollars",
    }
    assert feature_names == expected_names


def test_shap_additivity_and_bounds():
    """
    Shapley values must satisfy the efficiency property:
    base_risk + sum(shap_values) == risk_probability (within floating point precision).
    """
    payload = {
        "invoice_quantity": 1200.0,
        "invoice_dollars": 35000.0,
        "Freight": 450.0,
        "total_item_quantity": 1000.0,
        "total_item_dollars": 28000.0,
    }
    result = ml_models.explain_invoice_flag(payload)
    base_risk = result["base_risk"]
    sum_shap = sum(f["shap_value"] for f in result["features"])
    reconstructed_prob = base_risk + sum_shap

    assert abs(reconstructed_prob - result["risk_probability"]) < 0.01


def test_shap_high_vs_low_risk_contrast():
    """Verify that a high discrepancy invoice shows positive risk impact."""
    high_risk_payload = {
        "invoice_quantity": 8000.0,
        "invoice_dollars": 95000.0,
        "Freight": 5000.0,
        "total_item_quantity": 2000.0,
        "total_item_dollars": 15000.0,
    }
    result = ml_models.explain_invoice_flag(high_risk_payload)
    assert result["predicted_flag"] == 1
    assert result["risk_label"] == "FLAGGED"
    assert result["risk_probability"] > 0.5

    # Check that at least one feature has INCREASES_RISK
    increases = [f for f in result["features"] if f["impact"] == "INCREASES_RISK"]
    assert len(increases) >= 1


# ==============================================================================
# 2. REST API Endpoint Tests
# ==============================================================================

def test_api_explain_persisted_invoice(client):
    """GET /api/invoice/{id}/explain should return full SHAP attribution for seeded invoice #1."""
    res = client.get("/api/invoice/1/explain")
    assert res.status_code == 200
    data = res.json()

    assert data["invoice_id"] == 1
    assert data["vendor_number"] == "VND-RISK"
    assert data["po_number"] == "PO-9999"
    assert data["invoice_dollars"] == 95000.0
    assert data["total_item_dollars"] == 15000.0
    assert data["dollar_mismatch"] == 80000.0
    assert data["predicted_flag"] == 1
    assert data["risk_label"] == "FLAGGED"
    assert len(data["features"]) == 5


def test_api_explain_nonexistent_invoice(client):
    """GET /api/invoice/{id}/explain for missing invoice should return 404."""
    res = client.get("/api/invoice/99999/explain")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_api_explain_ad_hoc_payload(client):
    """POST /api/invoice/explain should score and explain an unpersisted payload."""
    payload = {
        "vendor_number": "VND-TEST",
        "po_number": "PO-TEST",
        "invoice_date": "2026-10-01",
        "invoice_quantity": 100.0,
        "invoice_dollars": 5000.0,
        "Freight": 150.0,
        "total_item_quantity": 100.0,
        "total_item_dollars": 5000.0,
    }
    res = client.post("/api/invoice/explain", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["invoice_id"] is None
    assert data["vendor_number"] == "VND-TEST"
    assert data["dollar_mismatch"] == 0.0
    assert len(data["features"]) == 5
    assert "summary" in data


# ==============================================================================
# 3. RAG Assistant (Q18) Tests
# ==============================================================================

def test_rag_classify_intent_q18():
    """Verify various natural language phrasings route to Q18_EXPLAIN_INVOICE_ANOMALY with invoice_id."""
    test_queries = [
        ("Why was invoice #1 flagged?", 1),
        ("Why was invoice 45 flagged?", 45),
        ("Explain anomaly for invoice #2", 2),
        ("Why is invoice 100 flagged as an anomaly?", 100),
        ("Explain why invoice #8 was flagged", 8),
    ]

    for q, expected_id in test_queries:
        intent, params = rag_service.classify_intent(q)
        assert intent == "Q18_EXPLAIN_INVOICE_ANOMALY", f"Failed on query: {q}"
        assert params.get("invoice_id") == expected_id, f"Failed extracting id from: {q}"


def test_rag_ask_assistant_q18_success(db_session):
    """ask_assistant with Q18 query should return rich SHAP markdown breakdown."""
    reply = rag_service.ask_assistant("Why was invoice #1 flagged?", db=db_session)
    assert isinstance(reply, str)

    assert "Invoice #1" in reply
    assert "SHAP" in reply or "Shapley" in reply
    assert "FLAGGED" in reply
    assert "VND-RISK" in reply
    assert "PO-9999" in reply
    assert "$95,000" in reply or "95000" in reply


def test_rag_ask_assistant_q18_not_found(db_session):
    """ask_assistant with Q18 query for non-existent invoice should return clean notice."""
    reply = rag_service.ask_assistant("Why was invoice #8888 flagged?", db=db_session)
    assert isinstance(reply, str)
    assert "Invoice #8888 not found" in reply
