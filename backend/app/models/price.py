from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, BigInteger, UniqueConstraint
from sqlalchemy.sql import func
from ..database import Base


class CurrentPriceCache(Base):
    """
    Fast-access cache for current prices.
    Updated whenever prices are fetched from yfinance.
    Enables instant page loads with slightly stale prices.
    """
    __tablename__ = "current_price_cache"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False)
    price = Column(Numeric(15, 4), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('symbol', 'exchange', name='uix_cache_symbol_exchange'),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Numeric(15, 4))
    high = Column(Numeric(15, 4))
    low = Column(Numeric(15, 4))
    close = Column(Numeric(15, 4), nullable=False)
    volume = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('symbol', 'exchange', 'date', name='uix_symbol_exchange_date'),
    )


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    from_currency = Column(String(3), nullable=False)
    to_currency = Column(String(3), nullable=False)
    rate = Column(Numeric(15, 6), nullable=False)
    date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('from_currency', 'to_currency', 'date', name='uix_currencies_date'),
    )
