"""
Portfolio Snapshots Router

API endpoints for portfolio value snapshots and historical data.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
import logging

from ..database import get_db
from ..models.portfolio_snapshot import PortfolioSnapshot
from ..schemas.snapshot import (
    PortfolioSnapshotResponse,
    PortfolioHistoryResponse
)
from ..services.snapshot_service import SnapshotService
from ..routers.analytics import calculate_portfolio_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["snapshots"])


@router.post("/snapshots/create", response_model=PortfolioSnapshotResponse)
def create_snapshot(
    snapshot_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Create a portfolio snapshot for the specified date (or today).

    This endpoint:
    - Calculates current portfolio value
    - Stores snapshot in database
    - Returns the snapshot data

    Use this to manually create snapshots or for scheduled daily snapshots.
    """
    try:
        snapshot = SnapshotService.create_snapshot(db, snapshot_date)
        return snapshot
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots/latest", response_model=PortfolioSnapshotResponse)
def get_latest_snapshot(db: Session = Depends(get_db)):
    """Get the most recent portfolio snapshot"""
    snapshot = db.query(SnapshotService).order_by(
        SnapshotService.snapshot_date.desc()
    ).first()

    if not snapshot:
        raise HTTPException(status_code=404, detail="No snapshots found")

    return snapshot


@router.get("/snapshots/{snapshot_date}", response_model=PortfolioSnapshotResponse)
def get_snapshot_by_date(
    snapshot_date: date,
    db: Session = Depends(get_db)
):
    """Get portfolio snapshot for a specific date"""
    snapshot = SnapshotService.get_snapshot(db, snapshot_date)

    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"No snapshot found for {snapshot_date}"
        )

    return snapshot


@router.get("/portfolio/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    days: int = Query(default=30, ge=1, le=3650, description="Number of days of history"),
    db: Session = Depends(get_db)
):
    """
    Get portfolio value history for the specified number of days.

    Returns:
    - List of snapshots
    - Date range
    - Current value and change from start
    """
    try:
        # Get snapshots for the requested period
        snapshots = SnapshotService.get_recent_snapshots(db, days)

        if not snapshots:
            # No snapshots exist yet, return empty history
            summary = await calculate_portfolio_summary(db)
            return PortfolioHistoryResponse(
                snapshots=[],
                start_date=date.today() - timedelta(days=days),
                end_date=date.today(),
                total_days=0,
                current_value=summary['total_value_cad'],
                value_change=Decimal('0'),
                value_change_pct=Decimal('0')
            )

        # Get current portfolio value
        summary = await calculate_portfolio_summary(db)
        current_value = Decimal(str(summary['total_value_cad']))

        # Calculate change from first snapshot
        first_snapshot = snapshots[0]
        value_change = current_value - first_snapshot.total_value_cad
        value_change_pct = Decimal('0')

        if first_snapshot.total_value_cad > 0:
            value_change_pct = (value_change / first_snapshot.total_value_cad) * Decimal('100')

        return PortfolioHistoryResponse(
            snapshots=snapshots,
            start_date=first_snapshot.snapshot_date,
            end_date=snapshots[-1].snapshot_date,
            total_days=len(snapshots),
            current_value=current_value,
            value_change=value_change,
            value_change_pct=value_change_pct
        )

    except Exception as e:
        logger.error(f"Error getting portfolio history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots/backfill")
def backfill_snapshots(
    start_date: date = Query(..., description="Start date for backfill"),
    end_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    db: Session = Depends(get_db)
):
    """
    Backfill portfolio snapshots for a date range.

    WARNING: This may take a while for large date ranges as it fetches
    historical prices for each holding on each date.

    Returns:
        Number of snapshots created
    """
    try:
        count = SnapshotService.backfill_snapshots(db, start_date, end_date)
        return {
            "status": "success",
            "snapshots_created": count,
            "start_date": start_date,
            "end_date": end_date or date.today()
        }
    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/snapshots/clear-all")
def clear_all_snapshots(db: Session = Depends(get_db)):
    """
    Delete all portfolio snapshots.

    WARNING: This is a destructive operation and cannot be undone.
    Use with caution, typically only for development/testing.

    Returns:
        Number of snapshots deleted
    """
    try:
        count = db.query(PortfolioSnapshot).delete()
        db.commit()
        logger.info(f"Deleted {count} snapshots")
        return {
            "status": "success",
            "snapshots_deleted": count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting snapshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))
