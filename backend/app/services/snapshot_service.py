"""
Portfolio Snapshot Service

Service for creating and managing daily portfolio value snapshots.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List
import json
import logging

from ..models.portfolio_snapshot import PortfolioSnapshot
from ..models.holding import Holding
from ..models.transaction import Transaction
from .price_service import PriceService
from .currency_service import CurrencyService

logger = logging.getLogger(__name__)


class SnapshotService:
    """Service for managing portfolio snapshots"""

    @staticmethod
    def get_holding_state_at_date(db: Session, holding: Holding, target_date: date) -> tuple[Decimal, Decimal]:
        """
        Calculate quantity and cost basis for a holding at a specific date.

        This reconstructs the holding state by replaying all transactions
        up to and including the target date.

        Args:
            db: Database session
            holding: The holding to calculate state for
            target_date: The date to calculate state at

        Returns:
            Tuple of (quantity, total_cost) at that date
        """
        transactions = db.query(Transaction).filter(
            Transaction.holding_id == holding.id,
            Transaction.transaction_date <= target_date
        ).order_by(Transaction.transaction_date).all()

        quantity = Decimal('0')
        total_cost = Decimal('0')

        for txn in transactions:
            txn_quantity = Decimal(str(txn.quantity))
            txn_price = Decimal(str(txn.price_per_share))
            txn_fees = Decimal(str(txn.fees)) if txn.fees else Decimal('0')

            if txn.transaction_type == 'BUY':
                total_cost += txn_quantity * txn_price + txn_fees
                quantity += txn_quantity
            else:  # SELL
                if quantity > 0:
                    avg_cost = total_cost / quantity
                    quantity -= txn_quantity
                    total_cost -= txn_quantity * avg_cost

        return max(quantity, Decimal('0')), max(total_cost, Decimal('0'))

    @staticmethod
    def create_snapshot(db: Session, snapshot_date: Optional[date] = None) -> PortfolioSnapshot:
        """
        Create a portfolio snapshot for the given date (or today if not specified).

        Args:
            db: Database session
            snapshot_date: Date for the snapshot (defaults to today)

        Returns:
            PortfolioSnapshot object
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        logger.info(f"Creating portfolio snapshot for {snapshot_date}")

        # Check if snapshot already exists for this date
        existing = db.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.snapshot_date == snapshot_date
        ).first()

        if existing:
            logger.info(f"Snapshot for {snapshot_date} already exists, updating...")
            snapshot = existing
        else:
            snapshot = PortfolioSnapshot(snapshot_date=snapshot_date)

        # Get holdings that existed at the snapshot date
        # Filter by first_purchase_date to exclude holdings that didn't exist yet
        # Include holdings with NULL first_purchase_date (e.g., mutual funds without transaction history)
        from sqlalchemy import or_
        holdings = db.query(Holding).filter(
            Holding.is_active == True,
            or_(
                Holding.first_purchase_date <= snapshot_date,
                Holding.first_purchase_date == None
            )
        ).all()

        total_value_cad = Decimal('0')
        total_cost_cad = Decimal('0')
        value_by_country = {}
        holdings_with_value = 0

        # For today's date, use current holdings directly (more accurate)
        # For historical dates, replay transactions
        is_today = snapshot_date == date.today()

        for holding in holdings:
            if is_today:
                # Use current holdings data directly
                quantity = Decimal(str(holding.quantity))
                cost = quantity * Decimal(str(holding.avg_purchase_price))
            else:
                # Get historical quantity and cost at the snapshot date
                quantity, cost = SnapshotService.get_holding_state_at_date(db, holding, snapshot_date)

            # Skip if no quantity at this date (all shares were sold)
            if quantity <= 0:
                continue

            holdings_with_value += 1

            # Get price for the snapshot date (checks price_history first, then yfinance)
            price_for_date = PriceService.get_price_for_date(holding.symbol, holding.exchange, snapshot_date, db=db)

            if price_for_date is None:
                # Try to extract snapshot value from notes (for mutual funds without live prices)
                # Format: "... | Snapshot: ₹XXX,XXX | ..."
                snapshot_value = None
                if holding.notes and "Snapshot:" in holding.notes:
                    import re
                    match = re.search(r'Snapshot: ₹([\d,]+)', holding.notes)
                    if match:
                        try:
                            snapshot_value = Decimal(match.group(1).replace(',', ''))
                            logger.info(f"Using snapshot value from notes for {holding.symbol}: {snapshot_value}")
                        except:
                            pass
                
                if snapshot_value is None:
                    logger.warning(f"No price available for {holding.symbol} on {snapshot_date}, skipping")
                    continue
                
                # Use snapshot value directly as market value (already in holding's currency)
                market_value = snapshot_value
            else:
                # Calculate market value using historical quantity and price
                market_value = quantity * price_for_date

            # Convert to CAD
            if holding.currency != 'CAD':
                rate = CurrencyService.get_exchange_rate_sync(holding.currency, 'CAD', db)
                if rate:
                    market_value_cad = market_value * rate
                else:
                    market_value_cad = market_value
            else:
                market_value_cad = market_value

            # Use historical cost (already in holding's currency)
            if holding.currency != 'CAD':
                rate = CurrencyService.get_exchange_rate_sync(holding.currency, 'CAD', db)
                if rate:
                    cost_cad = cost * rate
                else:
                    cost_cad = cost
            else:
                cost_cad = cost

            total_value_cad += market_value_cad
            total_cost_cad += cost_cad

            # Track by country
            country = holding.country or 'Unknown'
            if country not in value_by_country:
                value_by_country[country] = Decimal('0')
            value_by_country[country] += market_value_cad

        # Calculate gains
        unrealized_gain_cad = total_value_cad - total_cost_cad
        unrealized_gain_pct = Decimal('0')
        if total_cost_cad > 0:
            unrealized_gain_pct = (unrealized_gain_cad / total_cost_cad) * Decimal('100')

        # Update snapshot
        snapshot.total_value_cad = total_value_cad
        snapshot.total_cost_cad = total_cost_cad
        snapshot.unrealized_gain_cad = unrealized_gain_cad
        snapshot.unrealized_gain_pct = unrealized_gain_pct
        snapshot.holdings_count = holdings_with_value

        # Store country breakdown as JSON
        value_by_country_serializable = {
            k: float(v) for k, v in value_by_country.items()
        }
        snapshot.value_by_country = json.dumps(value_by_country_serializable)

        if not existing:
            db.add(snapshot)

        try:
            db.commit()
            db.refresh(snapshot)
        except Exception as e:
            db.rollback()
            # Try to fetch existing snapshot if insert failed due to unique constraint
            existing = db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.snapshot_date == snapshot_date
            ).first()
            if existing:
                # Update existing snapshot
                existing.total_value_cad = total_value_cad
                existing.total_cost_cad = total_cost_cad
                existing.unrealized_gain_cad = unrealized_gain_cad
                existing.unrealized_gain_pct = unrealized_gain_pct
                existing.holdings_count = holdings_with_value
                existing.value_by_country = json.dumps(value_by_country_serializable)
                db.commit()
                db.refresh(existing)
                snapshot = existing
                logger.info(f"Updated existing snapshot for {snapshot_date}")
            else:
                raise e

        logger.info(f"Snapshot created: value={total_value_cad} CAD, gain={unrealized_gain_cad} CAD ({unrealized_gain_pct:.2f}%)")

        return snapshot

    @staticmethod
    def get_snapshot(db: Session, snapshot_date: date) -> Optional[PortfolioSnapshot]:
        """Get snapshot for a specific date"""
        return db.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.snapshot_date == snapshot_date
        ).first()

    @staticmethod
    def get_snapshots_range(
        db: Session,
        start_date: date,
        end_date: date
    ) -> List[PortfolioSnapshot]:
        """Get all snapshots within a date range"""
        return db.query(PortfolioSnapshot).filter(
            and_(
                PortfolioSnapshot.snapshot_date >= start_date,
                PortfolioSnapshot.snapshot_date <= end_date
            )
        ).order_by(PortfolioSnapshot.snapshot_date).all()

    @staticmethod
    def get_recent_snapshots(db: Session, days: int = 30) -> List[PortfolioSnapshot]:
        """Get snapshots for the last N days"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        return SnapshotService.get_snapshots_range(db, start_date, end_date)

    @staticmethod
    def get_previous_snapshot(db: Session, reference_date: Optional[date] = None) -> Optional[PortfolioSnapshot]:
        """
        Get the most recent snapshot before the reference date.

        Used for calculating "today's change".

        Args:
            db: Database session
            reference_date: Reference date (defaults to today)

        Returns:
            Most recent snapshot before reference_date, or None
        """
        if reference_date is None:
            reference_date = date.today()

        return db.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.snapshot_date < reference_date
        ).order_by(PortfolioSnapshot.snapshot_date.desc()).first()

    @staticmethod
    def calculate_change_from_previous(
        db: Session,
        current_value: Decimal,
        reference_date: Optional[date] = None
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate change in portfolio value from the previous snapshot.

        Returns:
            Tuple of (value_change, percent_change)
        """
        previous = SnapshotService.get_previous_snapshot(db, reference_date)

        if previous is None:
            return Decimal('0'), Decimal('0')

        value_change = current_value - previous.total_value_cad
        percent_change = Decimal('0')

        if previous.total_value_cad > 0:
            percent_change = (value_change / previous.total_value_cad) * Decimal('100')

        return value_change, percent_change

    @staticmethod
    def backfill_snapshots(
        db: Session,
        start_date: date,
        end_date: Optional[date] = None
    ) -> int:
        """
        Backfill portfolio snapshots for a date range.

        This creates snapshots for each day using historical transaction data.
        NOTE: This requires historical price data to be accurate.

        Args:
            db: Database session
            start_date: Start date for backfill
            end_date: End date for backfill (defaults to today)

        Returns:
            Number of snapshots created
        """
        if end_date is None:
            end_date = date.today()

        logger.info(f"Backfilling snapshots from {start_date} to {end_date}")

        count = 0
        current_date = start_date

        while current_date <= end_date:
            try:
                # Only create snapshot for business days (Mon-Fri)
                if current_date.weekday() < 5:  # 0=Monday, 4=Friday
                    existing = SnapshotService.get_snapshot(db, current_date)
                    if not existing:
                        SnapshotService.create_snapshot(db, current_date)
                        count += 1
                        logger.info(f"Created snapshot for {current_date}")
                    else:
                        logger.debug(f"Snapshot already exists for {current_date}")
            except Exception as e:
                logger.error(f"Error creating snapshot for {current_date}: {e}")

            current_date += timedelta(days=1)

        logger.info(f"Backfill complete: {count} snapshots created")
        return count
