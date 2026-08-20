"""
ORM models = the shape of your Postgres tables, described as Python classes.
SQLAlchemy turns these into real `CREATE TABLE` statements for you.
"""
from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class InvoicePrediction(Base):
    """One row per invoice-risk prediction made through the API."""
    __tablename__ = "invoice_predictions"

    id = Column(Integer, primary_key=True, index=True)

    invoice_quantity = Column(Float, nullable=False)
    invoice_dollars = Column(Float, nullable=False)
    freight = Column(Float, nullable=False)
    total_item_quantity = Column(Float, nullable=False)
    total_item_dollars = Column(Float, nullable=False)

    predicted_flag = Column(Integer, nullable=False)       # 0 = clear, 1 = flagged
    risk_probability = Column(Float, nullable=False)       # model confidence 0-1

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FreightPrediction(Base):
    """One row per freight-cost prediction made through the API."""
    __tablename__ = "freight_predictions"

    id = Column(Integer, primary_key=True, index=True)

    dollars = Column(Float, nullable=False)
    predicted_freight = Column(Float, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
