#!/usr/bin/env python3
"""
Script to clear and re-backfill portfolio snapshots.

This script:
1. Backfills historical prices for all holdings (from yfinance to price_history table)
2. Deletes all existing snapshots
3. Re-runs backfill from earliest transaction date to today

The price backfill ensures that snapshot creation can use cached prices
instead of making many individual yfinance API calls.
"""
import sys
import os

# Add the backend app to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from sqlalchemy import func
from app.database import SessionLocal, engine
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.transaction import Transaction
from app.models.price import PriceHistory
from app.services.snapshot_service import SnapshotService
from app.services.price_service import PriceService


def main():
    db = SessionLocal()

    try:
        # Find earliest transaction date first
        earliest_txn = db.query(func.min(Transaction.transaction_date)).scalar()

        if earliest_txn is None:
            print("No transactions found. Nothing to backfill.")
            return

        end_date = date.today()
        print(f"Earliest transaction date: {earliest_txn}")
        print(f"Will backfill from {earliest_txn} to {end_date}")

        # Step 1: Backfill price history
        print("\n" + "=" * 60)
        print("STEP 1: Backfilling historical prices...")
        print("=" * 60)

        price_count_before = db.query(func.count(PriceHistory.id)).scalar()
        print(f"Current price history records: {price_count_before}")

        prices_created = PriceService.backfill_historical_prices(db, earliest_txn, end_date)
        print(f"Created {prices_created} new price history records")

        price_count_after = db.query(func.count(PriceHistory.id)).scalar()
        print(f"Total price history records: {price_count_after}")

        # Step 2: Delete existing snapshots
        print("\n" + "=" * 60)
        print("STEP 2: Deleting existing snapshots...")
        print("=" * 60)

        snapshot_count = db.query(func.count(PortfolioSnapshot.id)).scalar()
        print(f"Found {snapshot_count} existing snapshots")

        db.query(PortfolioSnapshot).delete()
        db.commit()
        print("All snapshots deleted")

        # Step 3: Run snapshot backfill
        print("\n" + "=" * 60)
        print("STEP 3: Creating portfolio snapshots...")
        print("=" * 60)
        print("This may take a while...")

        count = SnapshotService.backfill_snapshots(db, earliest_txn, end_date)

        print(f"\nBackfill complete! Created {count} snapshots")

        # Ensure clean session state before verification queries
        try:
            db.commit()
        except Exception:
            db.rollback()

        # Show first few and last few snapshots for verification
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        print("\nFirst 5 snapshots:")
        first_snapshots = db.query(PortfolioSnapshot).order_by(
            PortfolioSnapshot.snapshot_date
        ).limit(5).all()
        for s in first_snapshots:
            print(f"  {s.snapshot_date}: ${s.total_value_cad:.2f} CAD, {s.holdings_count} holdings")

        print("\nLast 5 snapshots:")
        last_snapshots = db.query(PortfolioSnapshot).order_by(
            PortfolioSnapshot.snapshot_date.desc()
        ).limit(5).all()
        for s in reversed(last_snapshots):
            print(f"  {s.snapshot_date}: ${s.total_value_cad:.2f} CAD, {s.holdings_count} holdings")

        # Check for gaps in snapshots (more than 3 consecutive missing weekdays)
        print("\nChecking for gaps in snapshot coverage...")
        all_snapshots = db.query(PortfolioSnapshot).order_by(
            PortfolioSnapshot.snapshot_date
        ).all()

        if len(all_snapshots) >= 2:
            gaps = []
            for i in range(1, len(all_snapshots)):
                prev_date = all_snapshots[i-1].snapshot_date
                curr_date = all_snapshots[i].snapshot_date
                day_diff = (curr_date - prev_date).days
                # More than 5 days gap (accounting for weekends) indicates missing data
                if day_diff > 5:
                    gaps.append((prev_date, curr_date, day_diff))

            if gaps:
                print(f"WARNING: Found {len(gaps)} gap(s) in snapshot data:")
                for gap in gaps[:5]:  # Show first 5 gaps
                    print(f"  Gap from {gap[0]} to {gap[1]} ({gap[2]} days)")
            else:
                print("No significant gaps found in snapshot coverage.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
