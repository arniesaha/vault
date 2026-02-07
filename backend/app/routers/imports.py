"""
Import router for handling CSV file imports from various brokers.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal

from ..database import get_db
from ..schemas.import_schema import (
    ImportPlatform,
    ImportPreviewRequest,
    ImportRequest,
    ImportPreviewResponse,
    ImportResult,
    SupportedFormat,
)
from ..services.import_service import ImportService
from ..services.kite_import_service import KiteImportService
from ..models.holding import Holding


class KiteImportRequest(BaseModel):
    """Request for Kite (Zerodha) import."""
    file_contents: List[str]  # Base64 encoded xlsx files
    account_type: str = "DEMAT"


class KiteImportResult(BaseModel):
    """Result of Kite import."""
    success: bool
    holdings_created: int
    holdings_updated: int
    total_holdings: int
    warnings: List[str]
    holdings: List[dict]

router = APIRouter(prefix="/import", tags=["import"])


@router.get("/formats", response_model=List[SupportedFormat])
def get_supported_formats():
    """Get list of supported import formats."""
    return ImportService.get_supported_formats()


@router.post("/preview", response_model=ImportPreviewResponse)
def preview_import(
    request: ImportPreviewRequest,
    db: Session = Depends(get_db)
):
    """
    Preview import without saving to database.

    Returns a summary of what will be imported, including:
    - Number of transactions
    - New symbols that will create holdings
    - Existing symbols that will update holdings
    - Potential duplicate transactions
    """
    try:
        return ImportService.preview_import(
            db=db,
            content=request.file_content,
            platform=request.platform,
            account_type=request.account_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error parsing file: {str(e)}"
        )


@router.post("/transactions", response_model=ImportResult)
def import_transactions(
    request: ImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import transactions from CSV file.

    Creates holdings for new symbols and updates existing holdings.
    Skips duplicate transactions if skip_duplicates is True.
    """
    try:
        result = ImportService.import_transactions(
            db=db,
            content=request.file_content,
            platform=request.platform,
            account_type=request.account_type,
            skip_duplicates=request.skip_duplicates,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.errors[0] if result.errors else "Import failed"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import error: {str(e)}"
        )


@router.post("/upload", response_model=ImportResult)
async def upload_and_import(
    file: UploadFile = File(...),
    platform: ImportPlatform = Form(...),
    account_type: Optional[str] = Form(None),
    skip_duplicates: bool = Form(True),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV file and import transactions.

    Alternative endpoint that accepts file upload directly instead of base64-encoded content.
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )

    try:
        content = await file.read()
        content_str = content.decode('utf-8')

        result = ImportService.import_transactions(
            db=db,
            content=content_str,
            platform=platform,
            account_type=account_type,
            skip_duplicates=skip_duplicates,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.errors[0] if result.errors else "Import failed"
            )

        return result

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding not supported. Please use UTF-8 encoded CSV files."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import error: {str(e)}"
        )


@router.post("/upload/preview", response_model=ImportPreviewResponse)
async def upload_and_preview(
    file: UploadFile = File(...),
    platform: ImportPlatform = Form(...),
    account_type: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV file and preview transactions without importing.

    Alternative endpoint that accepts file upload directly instead of base64-encoded content.
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported"
        )

    try:
        content = await file.read()
        content_str = content.decode('utf-8')

        return ImportService.preview_import(
            db=db,
            content=content_str,
            platform=platform,
            account_type=account_type,
        )

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File encoding not supported. Please use UTF-8 encoded CSV files."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error parsing file: {str(e)}"
        )


@router.post("/upload/bulk", response_model=ImportResult)
async def upload_bulk_import(
    files: List[UploadFile] = File(...),
    platform: ImportPlatform = Form(...),
    account_type: Optional[str] = Form(None),
    skip_duplicates: bool = Form(True),
    db: Session = Depends(get_db)
):
    """
    Upload multiple CSV files and import all transactions.

    Processes all files in order and combines results.
    """
    # Validate all files are CSV
    for file in files:
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only CSV files are supported. Got: {file.filename}"
            )

    total_result = ImportResult(
        success=True,
        transactions_imported=0,
        holdings_created=0,
        holdings_updated=0,
        duplicates_skipped=0,
        account_types_updated=0,
        errors=[],
        warnings=[],
    )

    for file in files:
        try:
            content = await file.read()
            content_str = content.decode('utf-8')

            result = ImportService.import_transactions(
                db=db,
                content=content_str,
                platform=platform,
                account_type=account_type,
                skip_duplicates=skip_duplicates,
            )

            # Aggregate results
            total_result.transactions_imported += result.transactions_imported
            total_result.holdings_created += result.holdings_created
            total_result.holdings_updated += result.holdings_updated
            total_result.duplicates_skipped += result.duplicates_skipped
            total_result.account_types_updated += result.account_types_updated
            total_result.errors.extend([f"{file.filename}: {e}" for e in result.errors])
            total_result.warnings.extend([f"{file.filename}: {w}" for w in result.warnings])

            if not result.success:
                total_result.success = False

        except UnicodeDecodeError:
            total_result.errors.append(f"{file.filename}: File encoding not supported")
            total_result.success = False
        except Exception as e:
            total_result.errors.append(f"{file.filename}: {str(e)}")
            total_result.success = False

    return total_result


@router.post("/kite", response_model=KiteImportResult)
def import_kite_holdings(
    request: KiteImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import holdings from Kite (Zerodha) AGTS xlsx files.
    
    Aggregates buy/sell across multiple annual statement files
    to calculate current holdings with average cost basis.
    """
    try:
        # Decode all files
        file_bytes = [KiteImportService.decode_base64(f) for f in request.file_contents]
        
        # Parse and aggregate holdings
        holdings, warnings = KiteImportService.parse_multiple_files(file_bytes)
        
        if not holdings:
            return KiteImportResult(
                success=False,
                holdings_created=0,
                holdings_updated=0,
                total_holdings=0,
                warnings=warnings or ["No holdings found in files"],
                holdings=[],
            )
        
        created = 0
        updated = 0
        result_holdings = []
        
        for h in holdings:
            # Check if holding exists
            existing = db.query(Holding).filter(
                Holding.symbol == h.symbol,
                Holding.account_type == request.account_type
            ).first()
            
            if existing:
                # Update existing
                existing.quantity = h.quantity
                existing.avg_purchase_price = h.avg_cost
                existing.exchange = h.exchange
                existing.is_active = True
                updated += 1
            else:
                # Create new holding
                new_holding = Holding(
                    symbol=h.symbol,
                    company_name=h.symbol,  # Will be enriched later
                    exchange=h.exchange,
                    country="IN",
                    quantity=h.quantity,
                    avg_purchase_price=h.avg_cost,
                    currency="INR",
                    account_type=request.account_type,
                    is_active=True,
                )
                db.add(new_holding)
                created += 1
            
            result_holdings.append({
                "symbol": h.symbol,
                "exchange": h.exchange,
                "quantity": float(h.quantity),
                "avg_cost": float(h.avg_cost),
                "total_invested": float(h.total_buy_value - h.total_sell_value + (h.quantity * h.avg_cost) - h.total_buy_value + (h.total_sell_qty * h.avg_cost)),
            })
        
        db.commit()
        
        return KiteImportResult(
            success=True,
            holdings_created=created,
            holdings_updated=updated,
            total_holdings=len(holdings),
            warnings=warnings,
            holdings=result_holdings,
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kite import error: {str(e)}"
        )


@router.post("/kite/upload", response_model=KiteImportResult)
async def upload_kite_files(
    files: List[UploadFile] = File(...),
    account_type: str = Form("DEMAT"),
    db: Session = Depends(get_db)
):
    """
    Upload Kite AGTS xlsx files and import holdings.
    
    Accepts multiple xlsx files, aggregates them, and creates holdings.
    """
    # Validate file types
    for file in files:
        if not file.filename.endswith('.xlsx'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only xlsx files are supported. Got: {file.filename}"
            )
    
    try:
        # Read all files
        file_bytes = []
        for file in files:
            content = await file.read()
            file_bytes.append(content)
        
        # Parse and aggregate holdings
        holdings, warnings = KiteImportService.parse_multiple_files(file_bytes)
        
        if not holdings:
            return KiteImportResult(
                success=False,
                holdings_created=0,
                holdings_updated=0,
                total_holdings=0,
                warnings=warnings or ["No holdings found in files"],
                holdings=[],
            )
        
        created = 0
        updated = 0
        result_holdings = []
        
        for h in holdings:
            # Check if holding exists
            existing = db.query(Holding).filter(
                Holding.symbol == h.symbol,
                Holding.account_type == account_type
            ).first()
            
            if existing:
                existing.quantity = h.quantity
                existing.avg_purchase_price = h.avg_cost
                existing.exchange = h.exchange
                existing.is_active = True
                updated += 1
            else:
                new_holding = Holding(
                    symbol=h.symbol,
                    company_name=h.symbol,
                    exchange=h.exchange,
                    country="IN",
                    quantity=h.quantity,
                    avg_purchase_price=h.avg_cost,
                    currency="INR",
                    account_type=account_type,
                    is_active=True,
                )
                db.add(new_holding)
                created += 1
            
            # Calculate invested value (remaining cost basis)
            invested = float(h.quantity * h.avg_cost)
            result_holdings.append({
                "symbol": h.symbol,
                "exchange": h.exchange,
                "quantity": float(h.quantity),
                "avg_cost": float(h.avg_cost),
                "invested_value": invested,
            })
        
        db.commit()
        
        return KiteImportResult(
            success=True,
            holdings_created=created,
            holdings_updated=updated,
            total_holdings=len(holdings),
            warnings=warnings,
            holdings=result_holdings,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kite import error: {str(e)}"
        )


# Groww Mutual Funds Import

class GrowwImportRequest(BaseModel):
    """Request for Groww mutual fund import."""
    file_content: str  # Base64 encoded xlsx file
    account_type: str = "MF_INDIA"


class GrowwImportResult(BaseModel):
    """Result of Groww import."""
    success: bool
    holdings_created: int
    holdings_updated: int
    total_holdings: int
    total_invested: float
    total_current: float
    total_returns: float
    total_returns_pct: float
    warnings: List[str]
    holdings: List[dict]


@router.post("/groww", response_model=GrowwImportResult)
def import_groww_holdings(
    request: GrowwImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import mutual fund holdings from Groww portfolio export.
    
    Parses the xlsx file and creates holdings for each fund.
    Uses generated symbols based on AMC and fund name.
    """
    from ..services.groww_import_service import GrowwImportService
    
    try:
        # Decode file
        file_bytes = GrowwImportService.decode_base64(request.file_content)
        
        # Parse holdings
        holdings, warnings = GrowwImportService.parse_xlsx_content(file_bytes)
        
        if not holdings:
            return GrowwImportResult(
                success=False,
                holdings_created=0,
                holdings_updated=0,
                total_holdings=0,
                total_invested=0,
                total_current=0,
                total_returns=0,
                total_returns_pct=0,
                warnings=warnings or ["No holdings found in file"],
                holdings=[],
            )
        
        created = 0
        updated = 0
        result_holdings = []
        total_invested = Decimal("0")
        total_current = Decimal("0")
        total_returns = Decimal("0")
        
        for h in holdings:
            # Generate symbol (include folio to distinguish same fund in different accounts)
            symbol = GrowwImportService.generate_symbol(h.scheme_name, h.amc, h.folio_no)
            
            # Calculate avg price (NAV at purchase)
            avg_nav = h.invested_value / h.units if h.units > 0 else Decimal("0")
            
            # Check if holding exists
            existing = db.query(Holding).filter(
                Holding.symbol == symbol,
                Holding.account_type == request.account_type
            ).first()
            
            # Calculate P&L percentage
            pnl_pct = (h.returns / h.invested_value * 100) if h.invested_value > 0 else Decimal("0")
            
            # Store snapshot values in notes for reference
            notes = (
                f"Folio: {h.folio_no} | {h.category}/{h.sub_category} | "
                f"Snapshot: ₹{float(h.current_value):,.0f} | XIRR: {h.xirr}"
            )
            
            if existing:
                existing.quantity = h.units
                existing.avg_purchase_price = avg_nav.quantize(Decimal("0.0001"))
                existing.company_name = h.scheme_name
                existing.is_active = True
                existing.notes = notes
                updated += 1
            else:
                new_holding = Holding(
                    symbol=symbol,
                    company_name=h.scheme_name,
                    exchange="MF",  # Mutual Fund
                    country="IN",
                    quantity=h.units,
                    avg_purchase_price=avg_nav.quantize(Decimal("0.0001")),
                    currency="INR",
                    account_type=request.account_type,
                    is_active=True,
                    notes=notes,
                )
                db.add(new_holding)
                created += 1
            
            total_invested += h.invested_value
            total_current += h.current_value
            total_returns += h.returns
            
            result_holdings.append({
                "symbol": symbol,
                "scheme_name": h.scheme_name,
                "amc": h.amc,
                "category": h.category,
                "units": float(h.units),
                "invested_value": float(h.invested_value),
                "current_value": float(h.current_value),
                "returns": float(h.returns),
                "returns_pct": float(pnl_pct),
                "xirr": h.xirr,
            })
        
        db.commit()
        
        # Calculate total returns percentage
        total_returns_pct = (total_returns / total_invested * 100) if total_invested > 0 else 0
        
        return GrowwImportResult(
            success=True,
            holdings_created=created,
            holdings_updated=updated,
            total_holdings=len(holdings),
            total_invested=float(total_invested),
            total_current=float(total_current),
            total_returns=float(total_returns),
            total_returns_pct=float(total_returns_pct),
            warnings=warnings,
            holdings=result_holdings,
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groww import error: {str(e)}"
        )
