"""
Import schemas for CSV file parsing and transaction import.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import date
from decimal import Decimal
from enum import Enum


class ImportPlatform(str, Enum):
    """Supported import platforms."""
    TD_DIRECT = "td_direct"
    WEALTHSIMPLE = "wealthsimple"
    KITE = "kite"  # Zerodha Kite - Indian stocks
    GROWW = "groww"  # Groww - Indian mutual funds


class ParsedTransaction(BaseModel):
    """A single parsed transaction from CSV."""
    date: date
    symbol: str
    company_name: Optional[str] = None
    exchange: str
    country: str
    transaction_type: Literal["BUY", "SELL"]
    quantity: Decimal = Field(..., gt=0, decimal_places=4)
    price_per_share: Decimal = Field(..., gt=0, decimal_places=4)
    fees: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=4)
    currency: str = "CAD"
    source: str
    account_type: Optional[str] = None
    raw_description: Optional[str] = None

    # For deduplication
    @property
    def dedup_key(self) -> str:
        """Generate a unique key for deduplication.

        Normalizes decimal values to remove trailing zeros for consistent comparison
        with database values (which may have trailing zeros from Numeric columns).
        """
        return f"{self.date}|{self.symbol}|{self.transaction_type}|{self.quantity.normalize()}|{self.price_per_share.normalize()}"


class ImportPreviewRequest(BaseModel):
    """Request to preview import without saving."""
    platform: ImportPlatform
    file_content: str  # Base64 encoded or raw CSV content
    account_type: Optional[str] = None


class ImportRequest(BaseModel):
    """Request to import transactions."""
    platform: ImportPlatform
    file_content: str  # Base64 encoded or raw CSV content
    account_type: Optional[str] = None
    skip_duplicates: bool = True


class ImportPreviewResponse(BaseModel):
    """Preview of what will be imported."""
    platform: str
    total_transactions: int
    buy_transactions: int
    sell_transactions: int
    transactions: List[ParsedTransaction]
    new_symbols: List[str]  # Symbols not in existing holdings
    existing_symbols: List[str]  # Symbols already in holdings
    potential_duplicates: int
    warnings: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class ImportResult(BaseModel):
    """Result of import operation."""
    success: bool
    transactions_imported: int
    holdings_created: int
    holdings_updated: int
    duplicates_skipped: int
    account_types_updated: int = 0
    errors: List[str] = []
    warnings: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class SupportedFormat(BaseModel):
    """Information about a supported import format."""
    platform: str
    name: str
    description: str
    file_types: List[str]
    date_format: str
    example_fields: List[str]
    notes: Optional[str] = None
