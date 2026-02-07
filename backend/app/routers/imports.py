"""
Import router for handling CSV file imports from various brokers.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

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
