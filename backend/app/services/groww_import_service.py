"""
Groww import service for Indian mutual funds.

Parses Groww portfolio export xlsx files to extract current MF holdings.
"""
import pandas as pd
import io
import base64
from decimal import Decimal
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class GrowwMFHolding:
    """Parsed mutual fund holding from Groww."""
    scheme_name: str
    amc: str
    category: str
    sub_category: str
    folio_no: str
    units: Decimal
    invested_value: Decimal
    current_value: Decimal
    returns: Decimal
    xirr: Optional[str]


class GrowwImportService:
    """Service for importing Groww mutual fund holdings."""
    
    # Short codes for common fund houses
    AMC_CODES = {
        "DSP Mutual Fund": "DSP",
        "Quant Mutual Fund": "QUANT",
        "Axis Mutual Fund": "AXIS",
        "PPFAS Mutual Fund": "PPFAS",
        "UTI Mutual Fund": "UTI",
        "Bandhan Mutual Fund": "BANDHAN",
        "HDFC Mutual Fund": "HDFC",
        "ICICI Prudential Mutual Fund": "ICICI",
        "SBI Mutual Fund": "SBI",
        "Nippon India Mutual Fund": "NIPPON",
        "Kotak Mutual Fund": "KOTAK",
        "Mirae Asset Mutual Fund": "MIRAE",
        "Aditya Birla Sun Life Mutual Fund": "ABSL",
        "Tata Mutual Fund": "TATA",
    }
    
    @staticmethod
    def generate_symbol(scheme_name: str, amc: str, folio_no: str = "") -> str:
        """Generate a short symbol from scheme name and folio."""
        # Get AMC code
        amc_code = GrowwImportService.AMC_CODES.get(amc, amc[:4].upper())
        
        # Extract key words from scheme name
        # Remove common suffixes
        name = scheme_name.replace("Direct Plan Growth", "").replace("Direct Growth", "")
        name = name.replace("Fund", "").replace("Scheme", "")
        name = name.strip()
        
        # Take first significant words
        words = [w for w in name.split() if len(w) > 2][:2]
        name_part = "".join(w[:4].upper() for w in words)
        
        # Add last 4 digits of folio if provided (to distinguish same fund in diff folios)
        folio_suffix = ""
        if folio_no:
            folio_clean = str(folio_no).replace(".0", "")[-4:]
            folio_suffix = f"_{folio_clean}"
        
        return f"{amc_code}_{name_part}{folio_suffix}"
    
    @staticmethod
    def parse_xlsx_content(content: bytes) -> Tuple[List[GrowwMFHolding], List[str]]:
        """Parse Groww portfolio xlsx file."""
        warnings = []
        
        try:
            df = pd.read_excel(io.BytesIO(content), header=None)
            
            # Find the header row with 'Scheme Name'
            header_row = None
            for i, row in df.iterrows():
                row_str = str(row.values)
                if 'Scheme Name' in row_str:
                    header_row = i
                    break
            
            if header_row is None:
                warnings.append("Could not find header row with 'Scheme Name'")
                return [], warnings
            
            # Re-read with proper header
            df = pd.read_excel(io.BytesIO(content), header=header_row)
            
            # Filter to rows with valid scheme names
            df = df[df['Scheme Name'].notna()]
            
            holdings = []
            for _, row in df.iterrows():
                try:
                    # Parse numeric values
                    units = Decimal(str(row.get('Units', 0)))
                    invested = Decimal(str(row.get('Invested Value', 0)))
                    current = Decimal(str(row.get('Current Value', 0)))
                    returns = Decimal(str(row.get('Returns', 0)))
                    
                    holdings.append(GrowwMFHolding(
                        scheme_name=str(row['Scheme Name']),
                        amc=str(row.get('AMC', '')),
                        category=str(row.get('Category', '')),
                        sub_category=str(row.get('Sub-category', '')),
                        folio_no=str(row.get('Folio No.', '')),
                        units=units,
                        invested_value=invested,
                        current_value=current,
                        returns=returns,
                        xirr=str(row.get('XIRR', '')),
                    ))
                except Exception as e:
                    warnings.append(f"Error parsing row: {e}")
                    continue
            
            return holdings, warnings
            
        except Exception as e:
            warnings.append(f"Error parsing xlsx: {str(e)}")
            return [], warnings
    
    @staticmethod
    def decode_base64(content: str) -> bytes:
        """Decode base64 content to bytes."""
        try:
            return base64.b64decode(content)
        except Exception:
            return content.encode('utf-8')
