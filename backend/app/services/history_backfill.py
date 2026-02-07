"""
Historical portfolio value backfill service.

Reconstructs portfolio history from transactions + historical prices.
"""
import yfinance as yf
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
from typing import Dict, List, Optional
import logging
import json

from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models.transaction import Transaction
from ..models.holding import Holding
from ..models.portfolio_snapshot import PortfolioSnapshot
from .currency_service import CurrencyService

logger = logging.getLogger(__name__)

# Symbol to yfinance ticker mapping
SYMBOL_MAP = {
    "XEQT": "XEQT.TO",
    "VDY": "VDY.TO",
    "HXQ": "HXQ.TO",
    "XEF": "XEF.TO",
    "VBAL": "VBAL.TO",
    "KILO": "KILO.TO",
    "ZRE": "ZRE.TO",
    # US symbols work as-is
}

def get_yf_ticker(symbol: str, exchange: str) -> str:
    """Convert our symbol to yfinance ticker."""
    if symbol in SYMBOL_MAP:
        return SYMBOL_MAP[symbol]
    if exchange == "TSX":
        return f"{symbol}.TO"
    if exchange in ["NSE", "BSE"]:
        return f"{symbol}.NS"
    return symbol  # US symbols


def get_historical_prices(symbols: List[str], start_date: date, end_date: date) -> Dict[str, Dict[date, float]]:
    """
    Fetch historical prices for multiple symbols.
    Returns: {symbol: {date: price}}
    """
    prices = defaultdict(dict)
    
    # Convert symbols to yfinance tickers
    tickers = {}
    for sym in symbols:
        # Determine exchange from symbol pattern
        if sym.endswith(".TO") or sym in ["XEQT", "VDY", "HXQ", "XEF", "VBAL", "KILO", "ZRE"]:
            tickers[sym] = SYMBOL_MAP.get(sym, f"{sym}.TO" if not sym.endswith(".TO") else sym)
        elif sym.startswith("FD_") or sym.startswith("PPF_"):
            # Fixed income - no price history, use constant
            continue
        else:
            tickers[sym] = sym
    
    if not tickers:
        return prices
    
    # Fetch in batches
    ticker_list = list(set(tickers.values()))
    try:
        data = yf.download(
            ticker_list,
            start=start_date,
            end=end_date + timedelta(days=1),
            progress=False,
            auto_adjust=True
        )
        
        if len(ticker_list) == 1:
            # Single ticker - different format
            ticker = ticker_list[0]
            for sym, yf_ticker in tickers.items():
                if yf_ticker == ticker and 'Close' in data.columns:
                    for idx, row in data.iterrows():
                        d = idx.date()
                        prices[sym][d] = float(row['Close'])
        else:
            # Multiple tickers
            if 'Close' in data.columns:
                close_data = data['Close']
                for sym, yf_ticker in tickers.items():
                    if yf_ticker in close_data.columns:
                        for idx, val in close_data[yf_ticker].items():
                            if not pd.isna(val):
                                prices[sym][idx.date()] = float(val)
    except Exception as e:
        logger.error(f"Error fetching historical prices: {e}")
    
    return prices


def calculate_holdings_at_date(transactions: List[Transaction], target_date: date) -> Dict[str, Dict]:
    """
    Calculate what holdings existed at a specific date.
    Returns: {symbol: {"quantity": X, "cost_basis": Y, "currency": Z}}
    """
    holdings = defaultdict(lambda: {"quantity": Decimal("0"), "cost_basis": Decimal("0"), "currency": "CAD"})
    
    for tx in transactions:
        if tx.transaction_date > target_date:
            continue
        
        sym = tx.symbol
        qty = Decimal(str(tx.quantity))
        price = Decimal(str(tx.price_per_share))
        
        if tx.transaction_type == "BUY":
            holdings[sym]["quantity"] += qty
            holdings[sym]["cost_basis"] += qty * price
        else:  # SELL
            if holdings[sym]["quantity"] > 0:
                # Reduce cost basis proportionally
                avg_cost = holdings[sym]["cost_basis"] / holdings[sym]["quantity"]
                holdings[sym]["quantity"] -= qty
                holdings[sym]["cost_basis"] -= qty * avg_cost
    
    # Filter out zero holdings
    return {k: v for k, v in holdings.items() if v["quantity"] > 0}


def backfill_history(db: Session, start_date: Optional[date] = None, end_date: Optional[date] = None) -> int:
    """
    Backfill portfolio history from transactions.
    
    Args:
        db: Database session
        start_date: Start date (default: first transaction date)
        end_date: End date (default: today)
    
    Returns: Number of snapshots created
    """
    import pandas as pd
    
    # Get all transactions ordered by date
    transactions = db.query(Transaction).order_by(Transaction.transaction_date).all()
    
    if not transactions:
        logger.warning("No transactions found")
        return 0
    
    # Determine date range
    if start_date is None:
        start_date = min(tx.transaction_date for tx in transactions if tx.transaction_date)
    if end_date is None:
        end_date = date.today()
    
    logger.info(f"Backfilling history from {start_date} to {end_date}")
    
    # Get all unique symbols
    symbols = list(set(tx.symbol for tx in transactions))
    
    # Get holdings info for currency
    holdings_info = {h.symbol: {"exchange": h.exchange, "currency": h.currency} 
                     for h in db.query(Holding).all()}
    
    # Fetch historical prices
    logger.info(f"Fetching historical prices for {len(symbols)} symbols...")
    historical_prices = get_historical_prices(symbols, start_date, end_date)
    
    # Also get current holdings for Indian holdings (no price history)
    indian_holdings = db.query(Holding).filter(
        Holding.account_type.in_(["DEMAT", "MF_INDIA", "FD_INDIA", "PPF_INDIA"])
    ).all()
    
    # Get exchange rates
    inr_rate = CurrencyService.get_exchange_rate_sync("INR", "CAD", db) or Decimal("0.0151")
    usd_rate = CurrencyService.get_exchange_rate_sync("USD", "CAD", db) or Decimal("1.44")
    
    snapshots_created = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Skip weekends for equity holdings (but we still want to capture Indian fixed income)
        is_weekend = current_date.weekday() >= 5
        
        # Calculate holdings at this date
        holdings_at_date = calculate_holdings_at_date(transactions, current_date)
        
        if not holdings_at_date and not indian_holdings:
            current_date += timedelta(days=1)
            continue
        
        total_value = Decimal("0")
        total_cost = Decimal("0")
        value_by_country = {"CA": Decimal("0"), "US": Decimal("0"), "IN": Decimal("0")}
        holdings_count = 0
        
        # Calculate value for traded holdings
        for sym, holding in holdings_at_date.items():
            qty = holding["quantity"]
            cost = holding["cost_basis"]
            
            # Get price for this date (or nearest previous date)
            price = None
            if sym in historical_prices:
                # Find nearest date <= current_date
                for d in sorted(historical_prices[sym].keys(), reverse=True):
                    if d <= current_date:
                        price = Decimal(str(historical_prices[sym][d]))
                        break
            
            if price is None:
                # Use cost basis as fallback
                price = cost / qty if qty > 0 else Decimal("0")
            
            market_value = qty * price
            
            # Convert to CAD
            info = holdings_info.get(sym, {})
            currency = info.get("currency", "CAD")
            if currency == "USD":
                market_value *= usd_rate
                cost *= usd_rate
            elif currency == "INR":
                market_value *= inr_rate
                cost *= inr_rate
            
            total_value += market_value
            total_cost += cost
            holdings_count += 1
            
            # Determine country
            exchange = info.get("exchange", "")
            if exchange in ["TSX"]:
                value_by_country["CA"] += market_value
            elif exchange in ["NSE", "BSE", "MF", "ICICI"]:
                value_by_country["IN"] += market_value
            else:
                value_by_country["US"] += market_value
        
        # Add Indian fixed income (constant value, they existed from their first_purchase_date)
        for h in indian_holdings:
            if h.first_purchase_date and h.first_purchase_date <= current_date:
                value_inr = Decimal(str(h.quantity)) * Decimal(str(h.avg_purchase_price))
                value_cad = value_inr * inr_rate
                total_value += value_cad
                total_cost += value_cad  # For fixed income, cost = value
                value_by_country["IN"] += value_cad
                holdings_count += 1
        
        if total_value > 0:
            unrealized_gain = total_value - total_cost
            unrealized_gain_pct = (unrealized_gain / total_cost * 100) if total_cost > 0 else Decimal("0")
            
            # Check if snapshot already exists
            existing = db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.snapshot_date == current_date
            ).first()
            
            if existing:
                # Update existing
                existing.total_value_cad = total_value
                existing.total_cost_cad = total_cost
                existing.unrealized_gain_cad = unrealized_gain
                existing.unrealized_gain_pct = unrealized_gain_pct
                existing.holdings_count = holdings_count
                existing.value_by_country = json.dumps({k: float(v) for k, v in value_by_country.items()})
            else:
                # Create new
                snapshot = PortfolioSnapshot(
                    snapshot_date=current_date,
                    total_value_cad=total_value,
                    total_cost_cad=total_cost,
                    unrealized_gain_cad=unrealized_gain,
                    unrealized_gain_pct=unrealized_gain_pct,
                    holdings_count=holdings_count,
                    value_by_country=json.dumps({k: float(v) for k, v in value_by_country.items()})
                )
                db.add(snapshot)
                snapshots_created += 1
        
        current_date += timedelta(days=1)
    
    db.commit()
    logger.info(f"Created {snapshots_created} snapshots")
    return snapshots_created


if __name__ == "__main__":
    # For testing
    import pandas as pd
    from ..database import SessionLocal
    
    logging.basicConfig(level=logging.INFO)
    
    db = SessionLocal()
    try:
        count = backfill_history(db)
        print(f"Backfilled {count} snapshots")
    finally:
        db.close()
