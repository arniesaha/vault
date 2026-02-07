from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class TransactionBase(BaseModel):
    holding_id: int
    symbol: str = Field(..., max_length=50)
    transaction_type: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: Decimal = Field(..., gt=0, decimal_places=4)
    price_per_share: Decimal = Field(..., gt=0, decimal_places=4)
    fees: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=4)
    transaction_date: date
    notes: Optional[str] = None


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
