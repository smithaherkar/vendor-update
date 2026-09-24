"""
Pydantic schemas define exactly what shape of data the API accepts (requests)
and returns (responses). FastAPI uses these to auto-validate everything and
to auto-generate the /docs page.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Optional


# ---------- Invoice risk ----------

class InvoiceInput(BaseModel):
    """What the frontend sends for manual invoice risk scoring."""
    vendor_number: Optional[str] = Field(None, description="Optional vendor identifier")
    po_number: Optional[str] = Field(None, description="Optional purchase order number")
    invoice_date: Optional[str] = Field(None, description="Optional invoice date YYYY-MM-DD")

    invoice_quantity: float = Field(..., ge=0, description="Units billed on the invoice")
    invoice_dollars: float = Field(..., ge=0, description="Dollar amount on the invoice")
    Freight: float = Field(..., ge=0, description="Freight charge on the invoice")
    total_item_quantity: float = Field(..., ge=0, description="Total units received on the PO")
    total_item_dollars: float = Field(..., ge=0, description="Total dollars received on the PO")

    class Config:
        json_schema_extra = {
            "example": {
                "vendor_number": "VND-1001",
                "po_number": "PO-9901",
                "invoice_date": "2026-08-01",
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
    vendor_number: Optional[str] = None
    po_number: Optional[str] = None
    invoice_date: Optional[str] = None

    invoice_dollars: float
    freight: float
    predicted_flag: int
    risk_label: str
    risk_probability: float

    source: str = "MANUAL"
    batch_id: Optional[int] = None
    batch_uuid: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True




# ---------- Freight cost ----------

class FreightInput(BaseModel):
    vendor_number: Optional[str] = Field(None, description="Optional vendor identifier")
    po_number: Optional[str] = Field(None, description="Optional purchase order number")
    invoice_date: Optional[str] = Field(None, description="Optional invoice date YYYY-MM-DD")
    Dollars: float = Field(..., ge=0, description="Invoice dollar amount")

    class Config:
        json_schema_extra = {
            "example": {
                "vendor_number": "VND-1001",
                "po_number": "PO-9901",
                "invoice_date": "2026-08-01",
                "Dollars": 25000,
            }
        }


class FreightPredictionOut(BaseModel):
    id: int
    vendor_number: Optional[str] = None
    po_number: Optional[str] = None
    invoice_date: Optional[str] = None

    dollars: float
    predicted_freight: float

    source: str = "MANUAL"
    batch_id: Optional[int] = None
    batch_uuid: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Upload Batch & Row Error Schemas ----------

class BatchRowErrorOut(BaseModel):
    id: int
    batch_id: int
    row_number: int
    raw_row_json: Optional[str] = None
    error_message: str
    created_at: datetime

    class Config:
        from_attributes = True


class UploadBatchOut(BaseModel):
    id: int
    batch_uuid: str
    batch_type: str
    filename: str
    file_hash: str
    row_count: int
    success_count: int
    duplicate_count: int
    error_count: int
    status: str
    uploaded_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchUploadResponse(BaseModel):
    message: str
    batch_uuid: str
    filename: str
    status: str
    is_async: bool = False
    row_count: int = 0
    success_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0


# ---------- Vendor AI Assistant ----------

class AssistantAsk(BaseModel):
    message: str = Field(..., description="Natural language question for the Vendor AI Assistant")

    class Config:
        json_schema_extra = {"example": {"message": "Estimate freight for a $45,000 invoice."}}


class AssistantReply(BaseModel):
    reply: str = Field(..., description="Assistant response text")

