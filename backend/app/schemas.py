"""
Pydantic schemas define exactly what shape of data the API accepts (requests)
and returns (responses). FastAPI uses these to auto-validate everything and
to auto-generate the /docs page.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any


# ---------- Invoice risk ----------

class InvoiceInput(BaseModel):
    """What the frontend must send to check an invoice."""
    invoice_quantity: float = Field(..., ge=0, description="Units billed on the invoice")
    invoice_dollars: float = Field(..., ge=0, description="Dollar amount on the invoice")
    Freight: float = Field(..., ge=0, description="Freight charge on the invoice")
    total_item_quantity: float = Field(..., ge=0, description="Total units received on the PO")
    total_item_dollars: float = Field(..., ge=0, description="Total dollars received on the PO")

    class Config:
        json_schema_extra = {
            "example": {
                "invoice_quantity": 6000,
                "invoice_dollars": 58000,
                "Freight": 300,
                "total_item_quantity": 6000,
                "total_item_dollars": 58000,
            }
        }


class InvoicePredictionOut(BaseModel):
    """What the API sends back after scoring an invoice."""
    id: int
    invoice_dollars: float
    freight: float
    predicted_flag: int
    risk_label: str
    risk_probability: float
    created_at: datetime

    class Config:
        from_attributes = True  # lets us build this directly from an ORM object


class InvoiceExplainOut(BaseModel):
    """What the API sends back for a RAG audit explanation."""
    id: int
    discrepancies: dict[str, Any]
    triggered_rules: list[str]
    explanation_markdown: str
    used_fallback: bool


# ---------- Freight cost ----------

class FreightInput(BaseModel):
    Dollars: float = Field(..., ge=0, description="Invoice dollar amount")

    class Config:
        json_schema_extra = {"example": {"Dollars": 25000}}


class FreightPredictionOut(BaseModel):
    id: int
    dollars: float
    predicted_freight: float
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Vendor AI Assistant ----------

class AssistantAsk(BaseModel):
    message: str = Field(..., description="Natural language question for the Vendor AI Assistant")

    class Config:
        json_schema_extra = {"example": {"message": "Estimate freight for a $45,000 invoice."}}


class AssistantReply(BaseModel):
    reply: str = Field(..., description="Assistant response text")
