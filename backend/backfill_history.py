#!/usr/bin/env python3
"""
Backfill portfolio history from transactions + historical prices.
Run inside the pod: python backfill_history.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
import json
import logging

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.transaction import Transaction
from app.models.holding import Holding
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.services.currency_service import CurrencyService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Symbol to yfinance ticker mapping for TSX
TSX_SYMBOLS = {"XEQT", "VDY", "HXQ", "XEF", "VBAL", "KILO", "ZRE"}


def get_yf_ticker(symbol: str, exchange: str) -> str:
    """Convert our symbol to yfinance ticker."""
    if exchange == "TSX" or symbol in TSX_SYMBOLS:
        return f"{symbol}.TO"
    if exchange in ["NSE", "BSE"]:
        return f"{symbol}.NS"
    return symbol


def fetch_historical_prices(symbols_with_exchange: list, start_date: date, end_date: date):
    """Fetch historical prices for symbols."""
    prices = {}  # {symbol: {date: price}}
    
    # Group by ticker
    tickers = {}
    for sym, exchange in symbols_with_exchange:
        if sym.startswith("FD_") or sym.startswith("PPF_") or sym.endswith("_"):
            continue  # Skip fixed income
        ticker = get_yf_ticker(sym, exchange)
        tickers[sym] = ticker
    
    if not tickers:
        return prices
    
    logger.info(f"Fetching prices for {len(tickers)} symbols from {start_date} to {end_date}")
    
    try:
        ticker_list = list(set(tickers.values()))
        data = yf.download(
            ticker_list,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=True,
            threads=True
        )
        
        if data.empty:
            logger.warning("No price data returned")
            return prices
        
        # Handle single vs multiple tickers
        if len(ticker_list) == 1:
            ticker = ticker_list[0]
            sym = [s for s, t in tickers.items() if t == ticker][0]
            prices[sym] = {}
            for idx in data.index:
                if 'Close' in data.columns:
                    val = data.loc[idx, 'Close']
                    if not pd.isna(val):
                        prices[sym][idx.date()] = float(val)
        else:
            close = data['Close'] if 'Close' in data.columns else data
            for sym, ticker in tickers.items():
                if ticker in close.columns:
                    prices[sym] = {}
                    for idx in close.index:
                        val = close.loc[idx, ticker]
                        if not pd.isna(val):
                            prices[sym][idx.date()] = float(val)
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")
    
    logger.info(f"Got prices for {len(prices)} symbols")
    return prices


def calculate_holdings_at_date(transactions: list, target_date: date) -> dict:
    """Calculate holdings at a specific date from transactions."""
    holdings = defaultdict(lambda: {"qty": Decimal("0"), "cost": Decimal("0")})
    
    for tx in transactions:
        if tx.transaction_date is None or tx.transaction_date > target_date:
            continue
        
        sym = tx.symbol
        qty = Decimal(str(tx.quantity))
        price = Decimal(str(tx.price_per_share))
        
        if tx.transaction_type == "BUY":
            holdings[sym]["qty"] += qty
            holdings[sym]["cost"] += qty * price
        else:
            if holdings[sym]["qty"] > 0:
                avg = holdings[sym]["cost"] / holdings[sym]["qty"]
                holdings[sym]["qty"] -= qty
                holdings[sym]["cost"] -= qty * avg
    
    return {k: v for k, v in holdings.items() if v["qty"] > 0}


def backfill(db: Session, start_date: date = None, end_date: date = None):
    """Main backfill function."""
    
    # Get all transactions
    transactions = db.query(Transaction).filter(
        Transaction.transaction_date.isnot(None)
    ).order_by(Transaction.transaction_date).all()
    
    if not transactions:
        logger.warning("No transactions with dates found")
        return 0
    
    # Get date range
    tx_dates = [tx.transaction_date for tx in transactions if tx.transaction_date]
    if not start_date:
        start_date = min(tx_dates)
    if not end_date:
        end_date = date.today()
    
    logger.info(f"Backfilling from {start_date} to {end_date}")
    
    # Get holding info
    holdings_info = {}
    for h in db.query(Holding).all():
        holdings_info[h.symbol] = {
            "exchange": h.exchange,
            "currency": h.currency,
            "account_type": h.account_type,
            "avg_price": float(h.avg_purchase_price),
            "qty": float(h.quantity)
        }
    
    # Get unique symbols with exchange
    symbols_with_exchange = list(set(
        (tx.symbol, holdings_info.get(tx.symbol, {}).get("exchange", ""))
        for tx in transactions
    ))
    
    # Fetch all historical prices
    historical_prices = fetch_historical_prices(symbols_with_exchange, start_date, end_date)
    
    # Get exchange rates (use current rates - could improve with historical)
    usd_rate = CurrencyService.get_exchange_rate_sync("USD", "CAD", db) or Decimal("1.44")
    inr_rate = CurrencyService.get_exchange_rate_sync("INR", "CAD", db) or Decimal("0.0151")
    
    logger.info(f"Exchange rates: USD={usd_rate}, INR={inr_rate}")
    
    # Get Indian holdings (fixed income) - they have constant value
    indian_fi = db.query(Holding).filter(
        Holding.account_type.in_(["DEMAT", "MF_INDIA", "FD_INDIA", "PPF_INDIA"])
    ).all()
    
    # Clear existing snapshots in range
    db.query(PortfolioSnapshot).filter(
        PortfolioSnapshot.snapshot_date >= start_date,
        PortfolioSnapshot.snapshot_date <= end_date
    ).delete()
    db.commit()
    
    snapshots_created = 0
    current = start_date
    last_prices = {}  # Cache last known price for each symbol
    
    while current <= end_date:
        # Calculate holdings at this date
        holdings_at_date = calculate_holdings_at_date(transactions, current)
        
        total_value = Decimal("0")
        total_cost = Decimal("0")
        holdings_count = 0
        by_country = {"CA": 0.0, "US": 0.0, "IN": 0.0}
        
        # Value traded holdings
        for sym, data in holdings_at_date.items():
            qty = data["qty"]
            cost = data["cost"]
            
            # Get price
            price = None
            if sym in historical_prices and current in historical_prices[sym]:
                price = Decimal(str(historical_prices[sym][current]))
                last_prices[sym] = price
            elif sym in last_prices:
                price = last_prices[sym]  # Use last known price
            
            if price is None:
                # Use cost basis
                price = cost / qty if qty > 0 else Decimal("0")
            
            value = qty * price
            
            # Convert to CAD
            info = holdings_info.get(sym, {})
            currency = info.get("currency", "CAD")
            if currency == "USD":
                value *= usd_rate
                cost *= usd_rate
            
            total_value += value
            total_cost += cost
            holdings_count += 1
            
            # Country
            exchange = info.get("exchange", "")
            if exchange == "TSX":
                by_country["CA"] += float(value)
            elif exchange in ["NSE", "BSE", "MF", "ICICI"]:
                by_country["IN"] += float(value)
            else:
                by_country["US"] += float(value)
        
        # Add Indian holdings
        for h in indian_fi:
            if h.first_purchase_date and h.first_purchase_date <= current:
                val = Decimal(str(h.quantity)) * Decimal(str(h.avg_purchase_price)) * inr_rate
                total_value += val
                total_cost += val
                by_country["IN"] += float(val)
                holdings_count += 1
        
        if total_value > 0:
            gain = total_value - total_cost
            gain_pct = (gain / total_cost * 100) if total_cost > 0 else Decimal("0")
            
            snapshot = PortfolioSnapshot(
                snapshot_date=current,
                total_value_cad=float(total_value),
                total_cost_cad=float(total_cost),
                unrealized_gain_cad=float(gain),
                unrealized_gain_pct=float(gain_pct),
                holdings_count=holdings_count,
                value_by_country=json.dumps(by_country)
            )
            db.add(snapshot)
            snapshots_created += 1
            
            if snapshots_created % 30 == 0:
                logger.info(f"Progress: {current} - ${float(total_value):,.2f}")
        
        current += timedelta(days=1)
    
    db.commit()
    logger.info(f"Created {snapshots_created} snapshots")
    return snapshots_created


if __name__ == "__main__":
    db = SessionLocal()
    try:
        # Default: backfill from first transaction to today
        count = backfill(db)
        print(f"\n✅ Backfilled {count} snapshots")
    finally:
        db.close()
