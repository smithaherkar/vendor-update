"""
ORM models = the shape of your Postgres/SQLite tables, described as Python classes.
SQLAlchemy turns these into real `CREATE TABLE` statements for you.
"""
import enum
from sqlalchemy import Column, Integer, Float, String, DateTime, Text, ForeignKey, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SourceEnum(str, enum.Enum):
    MANUAL = "MANUAL"
    BATCH = "BATCH"


class BatchStatusEnum(str, enum.Enum):
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class BatchTypeEnum(str, enum.Enum):
    INVOICE = "INVOICE"
    FREIGHT = "FREIGHT"


class UploadBatch(Base):
    """Tracks a single uploaded CSV batch job and its execution statistics."""
    __tablename__ = "upload_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_uuid = Column(String(36), unique=True, index=True, nullable=False)
    batch_type = Column(String(20), nullable=False, default="INVOICE")  # INVOICE or FREIGHT
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), unique=True, index=True, nullable=False)

    row_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    duplicate_count = Column(Integer, default=0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)

    status = Column(String(30), default="PROCESSING", nullable=False)  # PROCESSING, DONE, FAILED

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    errors = relationship("BatchRowError", back_populates="batch", cascade="all, delete-orphan")


class BatchRowError(Base):
    """Detailed error log per failed row in a batch."""
    __tablename__ = "batch_row_errors"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("upload_batches.id"), index=True, nullable=False)
    row_number = Column(Integer, nullable=False)
    raw_row_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("UploadBatch", back_populates="errors")


class Purchase(Base):
    """Purchase Order catalog table used for bulk PO lookup during batch scoring."""
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    vendor_number = Column(String(50), index=True, nullable=False)
    po_number = Column(String(50), index=True, nullable=False)
    total_item_quantity = Column(Float, nullable=False)
    total_item_dollars = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("vendor_number", "po_number", name="uq_purchase_vendor_po"),
    )


class InvoicePrediction(Base):
    """One row per invoice-risk prediction made through manual entry or CSV batch."""
    __tablename__ = "invoice_predictions"

    id = Column(Integer, primary_key=True, index=True)

    vendor_number = Column(String(50), nullable=True)
    po_number = Column(String(50), nullable=True)
    invoice_date = Column(String(10), nullable=True)  # YYYY-MM-DD

    invoice_quantity = Column(Float, nullable=False)
    invoice_dollars = Column(Float, nullable=False)
    freight = Column(Float, nullable=False)
    total_item_quantity = Column(Float, nullable=False)
    total_item_dollars = Column(Float, nullable=False)

    predicted_flag = Column(Integer, nullable=False)       # 0 = clear, 1 = flagged
    risk_probability = Column(Float, nullable=False)       # model confidence 0-1

    source = Column(String(20), nullable=False, default="MANUAL")
    batch_id = Column(Integer, ForeignKey("upload_batches.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("vendor_number", "po_number", "invoice_date", name="uq_invoice_vendor_po_date"),
    )


class FreightPrediction(Base):
    """One row per freight-cost prediction made through manual entry or CSV batch."""
    __tablename__ = "freight_predictions"

    id = Column(Integer, primary_key=True, index=True)

    vendor_number = Column(String(50), nullable=True)
    po_number = Column(String(50), nullable=True)
    invoice_date = Column(String(10), nullable=True)  # YYYY-MM-DD

    dollars = Column(Float, nullable=False)
    predicted_freight = Column(Float, nullable=False)

    source = Column(String(20), nullable=False, default="MANUAL")
    batch_id = Column(Integer, ForeignKey("upload_batches.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("vendor_number", "po_number", "invoice_date", name="uq_freight_vendor_po_date"),
    )

