from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models.holding import Holding, ACCOUNT_TYPES
from ..schemas.holding import HoldingCreate, HoldingUpdate, HoldingResponse
from datetime import datetime

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("/account-types")
def get_account_types():
    """Get list of available account types"""
    return {
        "account_types": [
            {"code": code, "name": name}
            for code, name in ACCOUNT_TYPES.items()
        ]
    }


@router.get("/", response_model=List[HoldingResponse])
def get_holdings(
    skip: int = 0,
    limit: int = 100,
    country: Optional[str] = Query(None, description="Filter by country code (CA, US, IN)"),
    exchange: Optional[str] = Query(None, description="Filter by exchange (TSX, NYSE, etc.)"),
    account_type: Optional[str] = Query(None, description="Filter by account type (TFSA, RRSP, FHSA, NON_REG)"),
    db: Session = Depends(get_db)
):
    """Get all active holdings with optional filters"""
    query = db.query(Holding).filter(Holding.is_active == True)

    if country:
        query = query.filter(Holding.country == country)
    if exchange:
        query = query.filter(Holding.exchange == exchange)
    if account_type:
        query = query.filter(Holding.account_type == account_type)

    holdings = query.offset(skip).limit(limit).all()
    return holdings


@router.get("/{holding_id}", response_model=HoldingResponse)
def get_holding(holding_id: int, db: Session = Depends(get_db)):
    """Get a single holding by ID"""
    holding = db.query(Holding).filter(
        Holding.id == holding_id,
        Holding.is_active == True
    ).first()

    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding with id {holding_id} not found"
        )

    return holding


@router.post("/", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
def create_holding(holding: HoldingCreate, db: Session = Depends(get_db)):
    """Create a new holding"""
    # Check if holding with same symbol already exists
    existing = db.query(Holding).filter(
        Holding.symbol == holding.symbol,
        Holding.exchange == holding.exchange,
        Holding.is_active == True
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Holding for {holding.symbol} on {holding.exchange} already exists"
        )

    db_holding = Holding(**holding.model_dump())
    db.add(db_holding)
    db.commit()
    db.refresh(db_holding)

    return db_holding


@router.put("/{holding_id}", response_model=HoldingResponse)
def update_holding(
    holding_id: int,
    holding_update: HoldingUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing holding"""
    db_holding = db.query(Holding).filter(
        Holding.id == holding_id,
        Holding.is_active == True
    ).first()

    if not db_holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding with id {holding_id} not found"
        )

    # Update only provided fields
    update_data = holding_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_holding, field, value)

    db_holding.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_holding)

    return db_holding


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    """Soft delete a holding"""
    db_holding = db.query(Holding).filter(
        Holding.id == holding_id,
        Holding.is_active == True
    ).first()

    if not db_holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holding with id {holding_id} not found"
        )

    # Soft delete
    db_holding.is_active = False
    db_holding.updated_at = datetime.utcnow()
    db.commit()

    return None
