from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Date, Text
from sqlalchemy.sql import func
from ..database import Base


# Canadian registered account types
ACCOUNT_TYPES = {
    "TFSA": "Tax-Free Savings Account",
    "RRSP": "Registered Retirement Savings Plan",
    "FHSA": "First Home Savings Account",
    "RESP": "Registered Education Savings Plan",
    "LIRA": "Locked-In Retirement Account",
    "RRIF": "Registered Retirement Income Fund",
    "NON_REG": "Non-Registered (Taxable)",
    "MARGIN": "Margin Account",
}


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200))
    exchange = Column(String(20), nullable=False)
    country = Column(String(2), nullable=False)  # CA, IN, US
    quantity = Column(Numeric(15, 4), nullable=False)
    avg_purchase_price = Column(Numeric(15, 4), nullable=False)
    currency = Column(String(3), default="CAD")
    account_type = Column(String(20), nullable=True, index=True)  # TFSA, RRSP, FHSA, NON_REG, etc.
    first_purchase_date = Column(Date)
    notes = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
