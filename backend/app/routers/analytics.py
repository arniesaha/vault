from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
from collections import defaultdict
import asyncio
import threading
from ..database import get_db
from ..models.holding import Holding
from ..models.transaction import Transaction
from ..models.price import PriceHistory, CurrentPriceCache
from ..services.price_service import PriceService
from ..services.currency_service import CurrencyService
from ..services.snapshot_service import SnapshotService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Lock to prevent multiple concurrent yfinance requests
_price_fetch_lock = threading.Lock()
_cached_live_prices = {}  # symbol -> {price, timestamp}
_cached_change_data = {}  # symbol -> {price, previous_close, change, change_pct, timestamp}
_cache_ttl_seconds = 60  # Cache live prices for 60 seconds to prevent duplicate fetches


def get_prices_from_cache(db: Session, holdings: list) -> Dict[str, Optional[Decimal]]:
    """
    Get prices from the cache table - instant, no external API calls.
    Returns dict mapping symbol to price (or None if not cached).
    """
    cached = db.query(CurrentPriceCache).filter(
        CurrentPriceCache.symbol.in_([h.symbol for h in holdings])
    ).all()

    cache_lookup = {(c.symbol, c.exchange): Decimal(str(c.price)) for c in cached}

    result = {}
    for holding in holdings:
        result[holding.symbol] = cache_lookup.get((holding.symbol, holding.exchange))

    return result


def save_prices_to_db_cache(db: Session, holdings: list, prices: Dict[str, Decimal]) -> None:
    """
    Save fetched prices to the CurrentPriceCache table for instant future loads.
    This enables fast=true queries to return data immediately.
    """
    now = datetime.now()
    saved_count = 0

    for holding in holdings:
        price = prices.get(holding.symbol)
        if price is None:
            continue

        try:
            existing = db.query(CurrentPriceCache).filter(
                CurrentPriceCache.symbol == holding.symbol,
                CurrentPriceCache.exchange == holding.exchange
            ).first()

            if existing:
                existing.price = price
                existing.currency = holding.currency
                existing.updated_at = now
            else:
                cache_entry = CurrentPriceCache(
                    symbol=holding.symbol,
                    exchange=holding.exchange,
                    price=price,
                    currency=holding.currency
                )
                db.add(cache_entry)
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving price for {holding.symbol}: {e}")

    try:
        db.commit()
        if saved_count > 0:
            logger.info(f"Saved {saved_count} prices to DB cache")
    except Exception as e:
        logger.error(f"Failed to commit price cache: {e}")
        db.rollback()


def get_prices_with_dedup(symbols: list, with_change: bool = False) -> Dict:
    """
    Fetch prices with request deduplication.
    Multiple concurrent requests will share the same yfinance call.
    """
    global _cached_live_prices, _cached_change_data

    now = datetime.now()
    cache = _cached_change_data if with_change else _cached_live_prices

    # Check if we have fresh cached data for all symbols
    results = {}
    symbols_to_fetch = []

    for symbol, exchange in symbols:
        cache_key = f"{symbol}:{exchange}"
        if cache_key in cache:
            cached = cache[cache_key]
            age = (now - cached['timestamp']).total_seconds()
            if age < _cache_ttl_seconds:
                if with_change:
                    results[symbol] = {
                        'price': cached['price'],
                        'previous_close': cached.get('previous_close'),
                        'change': cached.get('change'),
                        'change_pct': cached.get('change_pct')
                    }
                else:
                    results[symbol] = cached['price']
                continue
        symbols_to_fetch.append((symbol, exchange))

    if not symbols_to_fetch:
        logger.info("All prices served from in-memory dedup cache")
        return results

    # Acquire lock to prevent duplicate fetches
    with _price_fetch_lock:
        # Double-check cache after acquiring lock (another thread may have fetched)
        final_to_fetch = []
        for symbol, exchange in symbols_to_fetch:
            cache_key = f"{symbol}:{exchange}"
            if cache_key in cache:
                cached = cache[cache_key]
                age = (now - cached['timestamp']).total_seconds()
                if age < _cache_ttl_seconds:
                    if with_change:
                        results[symbol] = {
                            'price': cached['price'],
                            'previous_close': cached.get('previous_close'),
                            'change': cached.get('change'),
                            'change_pct': cached.get('change_pct')
                        }
                    else:
                        results[symbol] = cached['price']
                    continue
            final_to_fetch.append((symbol, exchange))

        if not final_to_fetch:
            return results

        # Actually fetch from yfinance
        logger.info(f"Fetching {len(final_to_fetch)} symbols from yfinance (with_change={with_change})")

        if with_change:
            fetched = PriceService.get_prices_with_change_bulk(final_to_fetch)
            for symbol, data in fetched.items():
                exchange = next((e for s, e in final_to_fetch if s == symbol), '')
                cache_key = f"{symbol}:{exchange}"
                _cached_change_data[cache_key] = {
                    'price': data.get('price'),
                    'previous_close': data.get('previous_close'),
                    'change': data.get('change'),
                    'change_pct': data.get('change_pct'),
                    'timestamp': now
                }
                results[symbol] = data
        else:
            fetched = PriceService.get_prices_bulk(final_to_fetch)
            for symbol, price in fetched.items():
                exchange = next((e for s, e in final_to_fetch if s == symbol), '')
                cache_key = f"{symbol}:{exchange}"
                _cached_live_prices[cache_key] = {
                    'price': price,
                    'timestamp': now
                }
                results[symbol] = price

    return results


async def calculate_portfolio_summary(db: Session, fast: bool = False) -> Dict:
    """
    Internal function to calculate portfolio summary.
    Can be called from routes or other modules.

    Args:
        db: Database session
        fast: If True, use cached prices for instant response (no daily change data)
    """
    holdings = db.query(Holding).filter(Holding.is_active == True).all()

    if not holdings:
        return {
            "total_value_cad": 0,
            "total_cost_cad": 0,
            "unrealized_gain_cad": 0,
            "unrealized_gain_pct": 0,
            "today_change_cad": 0,
            "today_change_pct": 0,
            "holdings_count": 0,
            "countries": {},
            "last_updated": datetime.now(),
            "source": "cache" if fast else "live"
        }

    symbols = [(h.symbol, h.exchange) for h in holdings]

    # Fetch prices - from cache if fast mode, otherwise from API with change data
    if fast:
        current_prices = get_prices_from_cache(db, holdings)
        price_data = None  # No change data in fast mode
        logger.info(f"Using cached prices for {len(holdings)} holdings")
    else:
        # Use dedup helper to prevent multiple concurrent yfinance calls
        price_data = get_prices_with_dedup(symbols, with_change=True)
        current_prices = {sym: data['price'] for sym, data in price_data.items()}

        # Save fetched prices to DB cache for future fast=true requests
        save_prices_to_db_cache(db, holdings, current_prices)

    # Calculate totals in CAD
    total_value_cad = Decimal("0")
    total_cost_cad = Decimal("0")
    total_previous_value_cad = Decimal("0")  # For accurate daily change
    countries = defaultdict(int)

    for holding in holdings:
        countries[holding.country] += 1

        # Get current price
        current_price = current_prices.get(holding.symbol)
        if current_price is None:
            logger.warning(f"No price available for {holding.symbol}")
            continue

        # Calculate market value in holding's currency
        market_value = holding.quantity * current_price
        total_cost = holding.quantity * holding.avg_purchase_price
        
        # Calculate previous value for daily change (if we have the data)
        previous_value = Decimal("0")
        if price_data and holding.symbol in price_data:
            prev_close = price_data[holding.symbol].get('previous_close')
            if prev_close:
                previous_value = holding.quantity * prev_close

        # Convert to CAD
        if holding.currency != "CAD":
            rate = CurrencyService.get_exchange_rate_sync(holding.currency, "CAD", db)
            if rate:
                market_value = market_value * rate
                total_cost = total_cost * rate
                previous_value = previous_value * rate

        total_value_cad += market_value
        total_cost_cad += total_cost
        total_previous_value_cad += previous_value

    # Calculate gains
    unrealized_gain_cad = total_value_cad - total_cost_cad
    unrealized_gain_pct = (unrealized_gain_cad / total_cost_cad * 100) if total_cost_cad > 0 else Decimal("0")

    # Calculate today's change - use accurate method if we have price data, else snapshot-based
    if price_data and total_previous_value_cad > 0:
        # Accurate daily change from previous close prices
        today_change_cad = total_value_cad - total_previous_value_cad
        today_change_pct = (today_change_cad / total_previous_value_cad * 100)
        logger.info(f"Daily change (accurate): {today_change_cad:.2f} CAD ({today_change_pct:.2f}%)")
    else:
        # Fall back to snapshot-based change (for fast mode or if no change data)
        today_change_cad, today_change_pct = SnapshotService.calculate_change_from_previous(
            db, total_value_cad
        )

    return {
        "total_value_cad": float(total_value_cad),
        "total_cost_cad": float(total_cost_cad),
        "unrealized_gain_cad": float(unrealized_gain_cad),
        "unrealized_gain_pct": float(unrealized_gain_pct),
        "today_change_cad": float(today_change_cad),
        "today_change_pct": float(today_change_pct),
        "holdings_count": len(holdings),
        "countries": dict(countries),
        "source": "cache" if fast else "live",
        "last_updated": datetime.now()
    }


@router.get("/portfolio/summary")
async def get_portfolio_summary(
    db: Session = Depends(get_db),
    fast: bool = Query(False, description="Use cached prices for instant response")
) -> Dict:
    """
    Get portfolio summary with total value, gains, and distribution.
    
    Use fast=true for instant response with cached prices (may be slightly stale).
    Use fast=false (default) for fresh prices from market data API.
    """
    return await calculate_portfolio_summary(db, fast)


@router.get("/allocation")
async def get_allocation(
    db: Session = Depends(get_db),
    fast: bool = Query(False, description="Use cached prices for instant response")
) -> Dict:
    """Get portfolio allocation by country, exchange, and top holdings"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()

    if not holdings:
        return {
            "by_country": {},
            "by_exchange": {},
            "top_holdings": [],
            "source": "cache" if fast else "live"
        }

    # Fetch prices - from cache if fast mode, otherwise from API
    if fast:
        current_prices = get_prices_from_cache(db, holdings)
    else:
        symbols = [(h.symbol, h.exchange) for h in holdings]
        # Use dedup helper to prevent multiple concurrent yfinance calls
        current_prices = get_prices_with_dedup(symbols, with_change=False)

        # Save fetched prices to DB cache for future fast=true requests
        save_prices_to_db_cache(db, holdings, current_prices)

    # Calculate allocations
    by_country = defaultdict(lambda: Decimal("0"))
    by_exchange = defaultdict(lambda: Decimal("0"))
    holdings_with_value = []

    total_portfolio_value = Decimal("0")

    for holding in holdings:
        current_price = current_prices.get(holding.symbol)
        if current_price is None:
            continue

        # Calculate market value in CAD
        market_value = holding.quantity * current_price

        # Convert to CAD
        if holding.currency != "CAD":
            rate = CurrencyService.get_exchange_rate_sync(holding.currency, "CAD", db)
            if rate:
                market_value = market_value * rate

        total_portfolio_value += market_value

        by_country[holding.country] += market_value
        by_exchange[holding.exchange] += market_value

        holdings_with_value.append({
            "symbol": holding.symbol,
            "company_name": holding.company_name,
            "market_value": float(market_value),
            "quantity": float(holding.quantity),
            "current_price": float(current_price),
            "currency": holding.currency
        })

    # Convert to percentages
    by_country_pct = {
        country: float(value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
        for country, value in by_country.items()
    }

    by_exchange_pct = {
        exchange: float(value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
        for exchange, value in by_exchange.items()
    }

    # Sort and get top 10 holdings
    holdings_with_value.sort(key=lambda x: x['market_value'], reverse=True)
    top_holdings = holdings_with_value[:10]

    # Add percentage to top holdings
    for holding in top_holdings:
        holding['percentage'] = float(
            Decimal(str(holding['market_value'])) / total_portfolio_value * 100
        ) if total_portfolio_value > 0 else 0

    return {
        "by_country": by_country_pct,
        "by_exchange": by_exchange_pct,
        "top_holdings": top_holdings,
        "total_value_cad": float(total_portfolio_value),
        "source": "cache" if fast else "live"
    }


@router.get("/performance")
async def get_performance(
    db: Session = Depends(get_db),
    fast: bool = Query(False, description="Use cached prices for instant response")
) -> Dict:
    """Get performance metrics for the portfolio"""
    holdings = db.query(Holding).filter(Holding.is_active == True).all()

    if not holdings:
        return {
            "best_performers": [],
            "worst_performers": [],
            "overall_return_pct": 0,
            "source": "cache" if fast else "live"
        }

    # Fetch prices - from cache if fast mode, otherwise from API
    if fast:
        current_prices = get_prices_from_cache(db, holdings)
    else:
        symbols = [(h.symbol, h.exchange) for h in holdings]
        # Use dedup helper to prevent multiple concurrent yfinance calls
        current_prices = get_prices_with_dedup(symbols, with_change=False)

        # Save fetched prices to DB cache for future fast=true requests
        save_prices_to_db_cache(db, holdings, current_prices)

    # Calculate performance for each holding
    holdings_performance = []

    for holding in holdings:
        current_price = current_prices.get(holding.symbol)
        if current_price is None:
            continue

        gain = current_price - holding.avg_purchase_price
        gain_pct = (gain / holding.avg_purchase_price * 100) if holding.avg_purchase_price > 0 else Decimal("0")

        holdings_performance.append({
            "symbol": holding.symbol,
            "company_name": holding.company_name,
            "current_price": float(current_price),
            "avg_cost": float(holding.avg_purchase_price),
            "gain": float(gain),
            "gain_pct": float(gain_pct),
            "currency": holding.currency
        })

    # Sort by performance
    holdings_performance.sort(key=lambda x: x['gain_pct'], reverse=True)

    best_performers = holdings_performance[:5]
    worst_performers = holdings_performance[-5:][::-1]  # Reverse to show worst first

    return {
        "best_performers": best_performers,
        "worst_performers": worst_performers,
        "total_holdings": len(holdings_performance),
        "source": "cache" if fast else "live"
    }


@router.get("/portfolio-value")
async def get_portfolio_value_history(days: int = 30, db: Session = Depends(get_db)) -> Dict:
    """Get portfolio value over time"""
    # This is a simplified version
    # In a real implementation, you'd calculate historical portfolio value
    # using historical prices and holdings at each point in time

    return {
        "message": "Portfolio value history coming soon",
        "note": "This requires storing historical portfolio snapshots"
    }


@router.get("/daily-movers")
async def get_daily_movers(
    db: Session = Depends(get_db),
    limit: int = Query(5, description="Number of top movers to return per direction")
) -> Dict:
    """
    Get today's biggest movers (gainers and losers) with daily change data.
    
    Returns all holdings sorted by daily change, plus top gainers/losers lists.
    Uses live price data with previous close for accurate daily change calculation.
    """
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    
    if not holdings:
        return {
            "all_holdings": [],
            "top_gainers": [],
            "top_losers": [],
            "market_open": True,
            "last_updated": datetime.now()
        }
    
    symbols = [(h.symbol, h.exchange) for h in holdings]
    
    # Get prices with daily change data
    price_data = PriceService.get_prices_with_change_bulk(symbols)
    
    holdings_with_change = []
    
    for holding in holdings:
        data = price_data.get(holding.symbol)
        if not data or data.get('price') is None:
            continue
        
        current_price = data['price']
        previous_close = data.get('previous_close')
        change = data.get('change', Decimal('0'))
        change_pct = data.get('change_pct', Decimal('0'))
        
        # Calculate market value and change in CAD
        market_value = holding.quantity * current_price
        day_change_value = holding.quantity * change if change else Decimal('0')
        
        # Convert to CAD
        if holding.currency != "CAD":
            rate = CurrencyService.get_exchange_rate_sync(holding.currency, "CAD", db)
            if rate:
                market_value = market_value * rate
                day_change_value = day_change_value * rate
        
        # Calculate unrealized gain
        cost_basis = holding.quantity * holding.avg_purchase_price
        if holding.currency != "CAD":
            rate = CurrencyService.get_exchange_rate_sync(holding.currency, "CAD", db)
            if rate:
                cost_basis = cost_basis * rate
        
        unrealized_gain = market_value - cost_basis
        unrealized_gain_pct = (unrealized_gain / cost_basis * 100) if cost_basis > 0 else Decimal('0')
        
        holdings_with_change.append({
            "symbol": holding.symbol,
            "company_name": holding.company_name,
            "exchange": holding.exchange,
            "currency": holding.currency,
            "quantity": float(holding.quantity),
            "current_price": float(current_price),
            "previous_close": float(previous_close) if previous_close else None,
            "day_change": float(change) if change else 0,
            "day_change_pct": float(change_pct) if change_pct else 0,
            "day_change_cad": float(day_change_value),
            "market_value_cad": float(market_value),
            "unrealized_gain_cad": float(unrealized_gain),
            "unrealized_gain_pct": float(unrealized_gain_pct)
        })
    
    # Sort by day change percentage
    holdings_with_change.sort(key=lambda x: x['day_change_pct'], reverse=True)
    
    # Get top gainers and losers
    gainers = [h for h in holdings_with_change if h['day_change_pct'] > 0]
    losers = [h for h in holdings_with_change if h['day_change_pct'] < 0]
    losers.reverse()  # Most negative first
    
    return {
        "all_holdings": holdings_with_change,
        "top_gainers": gainers[:limit],
        "top_losers": losers[:limit],
        "holdings_count": len(holdings_with_change),
        "last_updated": datetime.now()
    }


@router.get("/briefing")
async def get_portfolio_briefing(db: Session = Depends(get_db)) -> Dict:
    """
    Get a complete portfolio briefing suitable for daily summary.
    
    Combines portfolio summary, daily movers, and allocation data
    into a single response optimized for generating a text briefing.
    """
    # Get all the data we need
    summary = await calculate_portfolio_summary(db, fast=False)
    movers = await get_daily_movers(db, limit=4)
    
    # Get allocation for concentration analysis
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    symbols = [(h.symbol, h.exchange) for h in holdings]
    current_prices = PriceService.get_prices_bulk(symbols)
    
    total_value = Decimal(str(summary['total_value_cad']))
    
    # Build concentration alerts
    alerts = []
    for holding_data in movers['all_holdings']:
        pct = Decimal(str(holding_data['market_value_cad'])) / total_value * 100 if total_value > 0 else Decimal('0')
        
        # Alert if single position > 15%
        if pct > 15:
            alerts.append({
                "type": "concentration",
                "symbol": holding_data['symbol'],
                "message": f"{holding_data['symbol']} is {float(pct):.1f}% of portfolio",
                "severity": "warning"
            })
        
        # Alert if position down > 5% today
        if holding_data['day_change_pct'] < -5:
            alerts.append({
                "type": "big_loss",
                "symbol": holding_data['symbol'],
                "message": f"{holding_data['symbol']} down {abs(holding_data['day_change_pct']):.1f}% today",
                "severity": "alert"
            })
        
        # Alert if unrealized loss > 20%
        if holding_data['unrealized_gain_pct'] < -20:
            alerts.append({
                "type": "underwater",
                "symbol": holding_data['symbol'],
                "message": f"{holding_data['symbol']} down {abs(holding_data['unrealized_gain_pct']):.1f}% from cost",
                "severity": "info"
            })
    
    return {
        "summary": summary,
        "movers": {
            "top_gainers": movers['top_gainers'],
            "top_losers": movers['top_losers']
        },
        "alerts": alerts,
        "generated_at": datetime.now()
    }


@router.get("/realized-gains")
async def get_realized_gains(db: Session = Depends(get_db)) -> Dict:
    """
    Calculate realized gains/losses from completed (SELL) transactions.

    Uses FIFO (First In, First Out) accounting method:
    - When selling, the oldest purchased shares are sold first
    - Cost basis is calculated from the actual purchase price of those specific lots

    Same-day sell/buy transactions at identical price and quantity are detected
    as account transfers and excluded from realized gains calculations.
    """
    # Get all holdings (including inactive ones for historical sells)
    holdings = db.query(Holding).all()

    if not holdings:
        return {
            "total_realized_gain_cad": 0,
            "total_proceeds_cad": 0,
            "total_cost_basis_cad": 0,
            "transactions_count": 0,
            "by_holding": [],
            "by_year": {},
            "method": "FIFO"
        }

    # First, identify true round-trips (account transfers) to exclude
    # These are same-day sell/buy pairs with identical quantity and price
    round_trips = set()
    for holding in holdings:
        transactions = db.query(Transaction).filter(
            Transaction.holding_id == holding.id
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        # Group by date
        by_date = defaultdict(list)
        for txn in transactions:
            by_date[txn.transaction_date].append(txn)

        # Find matching sell/buy pairs on same day
        for date, day_txns in by_date.items():
            sells = [t for t in day_txns if t.transaction_type == "SELL"]
            buys = [t for t in day_txns if t.transaction_type == "BUY"]

            for sell in sells:
                for buy in buys:
                    # Check if same quantity and price (within small tolerance)
                    if (abs(float(sell.quantity) - float(buy.quantity)) < 0.0001 and
                        abs(float(sell.price_per_share) - float(buy.price_per_share)) < 0.01):
                        round_trips.add((holding.symbol, date, float(sell.quantity), float(sell.price_per_share)))

    total_realized_gain_cad = Decimal("0")
    total_proceeds_cad = Decimal("0")
    total_cost_basis_cad = Decimal("0")
    transactions_count = 0
    by_holding = []
    by_year = defaultdict(lambda: Decimal("0"))

    for holding in holdings:
        # Get all transactions for this holding, ordered by date and id
        transactions = db.query(Transaction).filter(
            Transaction.holding_id == holding.id
        ).order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()

        if not transactions:
            continue

        # FIFO: Track lots as a list of (quantity, price_per_share, fees)
        fifo_lots = []
        holding_realized_gain = Decimal("0")
        holding_proceeds = Decimal("0")
        holding_cost_basis = Decimal("0")
        sell_transactions = []

        for txn in transactions:
            txn_quantity = Decimal(str(txn.quantity))
            txn_price = Decimal(str(txn.price_per_share))
            txn_fees = Decimal(str(txn.fees)) if txn.fees else Decimal("0")

            # Check if this is part of a round-trip (account transfer)
            is_round_trip = (holding.symbol, txn.transaction_date,
                           float(txn_quantity), float(txn_price)) in round_trips

            if txn.transaction_type == "BUY":
                # Add new lot to FIFO queue (skip if round-trip)
                if not is_round_trip:
                    fifo_lots.append({
                        "quantity": txn_quantity,
                        "price": txn_price,
                        "fees": txn_fees
                    })

            elif txn.transaction_type == "SELL":
                # Skip round-trip sells
                if is_round_trip:
                    continue

                # Calculate proceeds from this sale
                proceeds = txn_quantity * txn_price - txn_fees

                # FIFO: Use oldest lots first to determine cost basis
                remaining_to_sell = txn_quantity
                cost_basis = Decimal("0")
                lots_used = []

                while remaining_to_sell > 0 and fifo_lots:
                    lot = fifo_lots[0]

                    if lot["quantity"] <= remaining_to_sell:
                        # Use entire lot
                        cost_basis += lot["quantity"] * lot["price"] + lot["fees"]
                        lots_used.append(f"{lot['quantity']}@${lot['price']:.2f}")
                        remaining_to_sell -= lot["quantity"]
                        fifo_lots.pop(0)
                    else:
                        # Use partial lot
                        cost_basis += remaining_to_sell * lot["price"]
                        # Proportional fees
                        cost_basis += lot["fees"] * (remaining_to_sell / lot["quantity"])
                        lots_used.append(f"{remaining_to_sell}@${lot['price']:.2f}")
                        # Update remaining lot
                        lot["fees"] = lot["fees"] * ((lot["quantity"] - remaining_to_sell) / lot["quantity"])
                        lot["quantity"] -= remaining_to_sell
                        remaining_to_sell = Decimal("0")

                # Calculate realized gain
                realized_gain = proceeds - cost_basis

                # Accumulate for this holding
                holding_realized_gain += realized_gain
                holding_proceeds += proceeds
                holding_cost_basis += cost_basis

                # Track by year
                year = txn.transaction_date.year

                # Convert to CAD if needed
                if holding.currency != "CAD":
                    rate = CurrencyService.get_exchange_rate_sync(holding.currency, "CAD", db)
                    if rate:
                        realized_gain_cad = realized_gain * rate
                        proceeds_cad = proceeds * rate
                        cost_basis_cad_val = cost_basis * rate
                    else:
                        realized_gain_cad = realized_gain
                        proceeds_cad = proceeds
                        cost_basis_cad_val = cost_basis
                else:
                    realized_gain_cad = realized_gain
                    proceeds_cad = proceeds
                    cost_basis_cad_val = cost_basis

                by_year[year] += realized_gain_cad
                total_realized_gain_cad += realized_gain_cad
                total_proceeds_cad += proceeds_cad
                total_cost_basis_cad += cost_basis_cad_val
                transactions_count += 1

                # Calculate average cost for display (cost basis / quantity)
                avg_cost_display = cost_basis / txn_quantity if txn_quantity > 0 else Decimal("0")

                sell_transactions.append({
                    "date": txn.transaction_date.isoformat(),
                    "quantity": float(txn_quantity),
                    "sell_price": float(txn_price),
                    "cost_basis": float(avg_cost_display),  # Per-share cost basis
                    "realized_gain": float(realized_gain),
                    "realized_gain_cad": float(realized_gain_cad),
                    "lots_used": ", ".join(lots_used) if lots_used else "N/A"
                })

        # Only add holdings with sell transactions
        if sell_transactions:
            # Convert holding totals to CAD
            if holding.currency != "CAD":
                rate = CurrencyService.get_exchange_rate_sync(holding.currency, "CAD", db)
                if rate:
                    holding_realized_gain_cad = holding_realized_gain * rate
                else:
                    holding_realized_gain_cad = holding_realized_gain
            else:
                holding_realized_gain_cad = holding_realized_gain

            by_holding.append({
                "symbol": holding.symbol,
                "company_name": holding.company_name,
                "exchange": holding.exchange,
                "currency": holding.currency,
                "realized_gain": float(holding_realized_gain),
                "realized_gain_cad": float(holding_realized_gain_cad),
                "transactions_count": len(sell_transactions),
                "transactions": sell_transactions
            })

    # Sort by holding with largest realized gains
    by_holding.sort(key=lambda x: abs(x['realized_gain_cad']), reverse=True)

    return {
        "total_realized_gain_cad": float(total_realized_gain_cad),
        "total_proceeds_cad": float(total_proceeds_cad),
        "total_cost_basis_cad": float(total_cost_basis_cad),
        "transactions_count": transactions_count,
        "by_holding": by_holding,
        "by_year": {str(k): float(v) for k, v in sorted(by_year.items())},
        "method": "FIFO"
    }


@router.get("/recommendations")
async def get_recommendations(
    db: Session = Depends(get_db),
    fast: bool = Query(True, description="Use cached prices for faster response")
) -> Dict:
    """
    Get actionable portfolio recommendations based on current holdings.
    
    Returns categorized recommendations:
    - take_profit: Holdings with significant gains (>40%)
    - review: Holdings with significant losses (>20%)
    - rebalance: Holdings that are overweight (>12% of portfolio)
    - watch: Holdings with big daily moves (>3%)
    
    Also returns a portfolio health score (0-100).
    """
    holdings = db.query(Holding).filter(Holding.is_active == True).all()
    
    if not holdings:
        return {
            "recommendations": [],
            "health_score": 100,
            "health_grade": "A",
            "summary": {
                "take_profit": 0,
                "review": 0,
                "rebalance": 0,
                "watch": 0
            },
            "generated_at": datetime.now()
        }
    
    # Get prices - prefer cache for speed
    if fast:
        current_prices = get_prices_from_cache(db, holdings)
        price_data = None
    else:
        symbols = [(h.symbol, h.exchange) for h in holdings]
        price_data = PriceService.get_prices_with_change_bulk(symbols)
        current_prices = {sym: data['price'] for sym, data in price_data.items()}
    
    # Calculate portfolio total and per-holding metrics
    total_value = Decimal("0")
    holdings_data = []
    
    for holding in holdings:
        price = current_prices.get(holding.symbol)
        if price is None:
            continue
        
        market_value = holding.quantity * price
        cost_basis = holding.quantity * holding.avg_purchase_price
        
        # Convert to CAD
        if holding.currency != "CAD":
            rate = CurrencyService.get_exchange_rate_sync(holding.currency, "CAD", db)
            if rate:
                market_value_cad = market_value * rate
                cost_basis_cad = cost_basis * rate
            else:
                market_value_cad = market_value
                cost_basis_cad = cost_basis
        else:
            market_value_cad = market_value
            cost_basis_cad = cost_basis
        
        gain_pct = ((market_value_cad - cost_basis_cad) / cost_basis_cad * 100) if cost_basis_cad > 0 else Decimal("0")
        
        # Get daily change if available
        day_change_pct = Decimal("0")
        if price_data and holding.symbol in price_data:
            change_pct = price_data[holding.symbol].get('change_pct')
            if change_pct:
                day_change_pct = change_pct
        
        total_value += market_value_cad
        
        holdings_data.append({
            "symbol": holding.symbol,
            "company_name": holding.company_name,
            "market_value_cad": market_value_cad,
            "cost_basis_cad": cost_basis_cad,
            "gain_pct": float(gain_pct),
            "day_change_pct": float(day_change_pct),
            "currency": holding.currency,
            "exchange": holding.exchange,
            "country": holding.country
        })
    
    # Calculate allocation percentages
    for h in holdings_data:
        h["allocation_pct"] = float(h["market_value_cad"] / total_value * 100) if total_value > 0 else 0
    
    # Generate recommendations
    recommendations = []
    health_deductions = 0
    
    for h in holdings_data:
        # Take profit: >40% gain
        if h["gain_pct"] > 40:
            severity = "high" if h["gain_pct"] > 80 else "medium"
            recommendations.append({
                "type": "take_profit",
                "symbol": h["symbol"],
                "company_name": h["company_name"],
                "title": f"Consider taking profits on {h['symbol']}",
                "description": f"Up {h['gain_pct']:.1f}% from cost basis. Consider trimming position.",
                "metric": h["gain_pct"],
                "metric_label": "Total Return",
                "severity": severity,
                "icon": "trending-up"
            })
            health_deductions += 2 if h["gain_pct"] > 80 else 1
        
        # Review: >20% loss
        if h["gain_pct"] < -20:
            severity = "high" if h["gain_pct"] < -40 else "medium"
            recommendations.append({
                "type": "review",
                "symbol": h["symbol"],
                "company_name": h["company_name"],
                "title": f"Review your {h['symbol']} position",
                "description": f"Down {abs(h['gain_pct']):.1f}% from cost. Review thesis or consider averaging down.",
                "metric": h["gain_pct"],
                "metric_label": "Total Return",
                "severity": severity,
                "icon": "alert-triangle"
            })
            health_deductions += 5 if h["gain_pct"] < -40 else 3
        
        # Rebalance: >12% of portfolio
        if h["allocation_pct"] > 12:
            severity = "high" if h["allocation_pct"] > 20 else "medium"
            recommendations.append({
                "type": "rebalance",
                "symbol": h["symbol"],
                "company_name": h["company_name"],
                "title": f"{h['symbol']} is overweight",
                "description": f"At {h['allocation_pct']:.1f}% of portfolio. Consider rebalancing for diversification.",
                "metric": h["allocation_pct"],
                "metric_label": "Portfolio Weight",
                "severity": severity,
                "icon": "pie-chart"
            })
            health_deductions += 3 if h["allocation_pct"] > 20 else 1
        
        # Watch: Big daily move (>3%)
        if abs(h["day_change_pct"]) > 3:
            direction = "up" if h["day_change_pct"] > 0 else "down"
            icon = "trending-up" if h["day_change_pct"] > 0 else "trending-down"
            recommendations.append({
                "type": "watch",
                "symbol": h["symbol"],
                "company_name": h["company_name"],
                "title": f"{h['symbol']} moved {direction} {abs(h['day_change_pct']):.1f}% today",
                "description": f"Check for news or earnings announcements.",
                "metric": h["day_change_pct"],
                "metric_label": "Day Change",
                "severity": "low",
                "icon": icon
            })
    
    # Check country concentration
    country_allocation = defaultdict(float)
    for h in holdings_data:
        country_allocation[h["country"]] += h["allocation_pct"]
    
    for country, pct in country_allocation.items():
        if pct > 70:
            recommendations.append({
                "type": "rebalance",
                "symbol": None,
                "company_name": None,
                "title": f"High {country} concentration ({pct:.0f}%)",
                "description": "Consider adding international diversification.",
                "metric": pct,
                "metric_label": "Country Weight",
                "severity": "medium",
                "icon": "globe"
            })
            health_deductions += 2
    
    # Calculate health score (start at 100, deduct for issues)
    health_score = max(0, min(100, 100 - health_deductions * 3))
    
    # Determine grade
    if health_score >= 90:
        health_grade = "A"
    elif health_score >= 80:
        health_grade = "B"
    elif health_score >= 70:
        health_grade = "C"
    elif health_score >= 60:
        health_grade = "D"
    else:
        health_grade = "F"
    
    # Sort recommendations by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda x: severity_order.get(x["severity"], 3))
    
    # Count by type
    summary = {
        "take_profit": len([r for r in recommendations if r["type"] == "take_profit"]),
        "review": len([r for r in recommendations if r["type"] == "review"]),
        "rebalance": len([r for r in recommendations if r["type"] == "rebalance"]),
        "watch": len([r for r in recommendations if r["type"] == "watch"])
    }
    
    return {
        "recommendations": recommendations,
        "health_score": health_score,
        "health_grade": health_grade,
        "summary": summary,
        "total_recommendations": len(recommendations),
        "generated_at": datetime.now()
    }


@router.get("/insights")
async def get_ai_insights(db: Session = Depends(get_db)) -> Dict:
    """
    Get AI-generated insights about the portfolio.
    
    Insights are generated by Nix (Claude) and cached in a file.
    This endpoint returns the cached insights.
    """
    import json
    import os
    
    insights_file = "/app/data/portfolio-insights.json"
    
    if os.path.exists(insights_file):
        try:
            with open(insights_file, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Failed to load insights: {e}")
    
    return {
        "insights": [],
        "generated_at": None,
        "message": "No insights available yet. Check back later."
    }


@router.get("/account-breakdown")
async def get_account_breakdown(
    db: Session = Depends(get_db),
    fast: bool = Query(True, description="Use cached prices for faster response")
) -> Dict:
    """
    Get portfolio breakdown by account type (TFSA, RRSP, FHSA, Non-Registered, etc.).

    Returns value and allocation for each account type, useful for:
    - Tax planning (registered vs non-registered)
    - Contribution room tracking
    - Account rebalancing decisions
    """
    from ..models.holding import ACCOUNT_TYPES

    holdings = db.query(Holding).filter(Holding.is_active == True).all()

    if not holdings:
        return {
            "by_account_type": {},
            "tax_advantaged_total": 0,
            "taxable_total": 0,
            "tax_advantaged_pct": 0,
            "total_value_cad": 0,
            "source": "cache" if fast else "live"
        }

    # Get prices
    if fast:
        current_prices = get_prices_from_cache(db, holdings)
    else:
        symbols = [(h.symbol, h.exchange) for h in holdings]
        current_prices = get_prices_with_dedup(symbols, with_change=False)
        save_prices_to_db_cache(db, holdings, current_prices)

    # Account types that are tax-advantaged
    TAX_ADVANTAGED = {"TFSA", "RRSP", "FHSA", "RESP", "LIRA", "RRIF"}

    # Calculate breakdown
    by_account = defaultdict(lambda: {
        "value_cad": Decimal("0"),
        "cost_cad": Decimal("0"),
        "holdings_count": 0,
        "holdings": []
    })

    total_value = Decimal("0")
    tax_advantaged_total = Decimal("0")
    taxable_total = Decimal("0")

    for holding in holdings:
        price = current_prices.get(holding.symbol)
        if price is None:
            continue

        market_value = holding.quantity * price
        cost_basis = holding.quantity * holding.avg_purchase_price

        # Convert to CAD
        if holding.currency != "CAD":
            rate = CurrencyService.get_exchange_rate_sync(holding.currency, "CAD", db)
            if rate:
                market_value = market_value * rate
                cost_basis = cost_basis * rate

        total_value += market_value

        # Use account_type or default to "UNASSIGNED"
        account_type = holding.account_type or "UNASSIGNED"
        account_name = ACCOUNT_TYPES.get(account_type, account_type)

        by_account[account_type]["value_cad"] += market_value
        by_account[account_type]["cost_cad"] += cost_basis
        by_account[account_type]["holdings_count"] += 1
        by_account[account_type]["name"] = account_name
        by_account[account_type]["holdings"].append({
            "symbol": holding.symbol,
            "company_name": holding.company_name,
            "value_cad": float(market_value),
            "quantity": float(holding.quantity)
        })

        # Track tax-advantaged vs taxable
        if account_type in TAX_ADVANTAGED:
            tax_advantaged_total += market_value
        else:
            taxable_total += market_value

    # Convert to response format with percentages
    result = {}
    for account_type, data in by_account.items():
        gain = data["value_cad"] - data["cost_cad"]
        gain_pct = (gain / data["cost_cad"] * 100) if data["cost_cad"] > 0 else Decimal("0")
        allocation_pct = (data["value_cad"] / total_value * 100) if total_value > 0 else Decimal("0")

        result[account_type] = {
            "name": data.get("name", account_type),
            "value_cad": float(data["value_cad"]),
            "cost_cad": float(data["cost_cad"]),
            "gain_cad": float(gain),
            "gain_pct": float(gain_pct),
            "allocation_pct": float(allocation_pct),
            "holdings_count": data["holdings_count"],
            "holdings": sorted(data["holdings"], key=lambda x: x["value_cad"], reverse=True),
            "is_tax_advantaged": account_type in TAX_ADVANTAGED
        }

    tax_advantaged_pct = (tax_advantaged_total / total_value * 100) if total_value > 0 else Decimal("0")

    return {
        "by_account_type": result,
        "tax_advantaged_total": float(tax_advantaged_total),
        "taxable_total": float(taxable_total),
        "tax_advantaged_pct": float(tax_advantaged_pct),
        "total_value_cad": float(total_value),
        "account_types_available": list(ACCOUNT_TYPES.keys()),
        "source": "cache" if fast else "live"
    }
