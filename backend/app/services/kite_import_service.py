"""
Kite (Zerodha) import service for Indian stocks.

Parses Annual Global Transaction Statement (AGTS) xlsx files and
calculates current holdings by aggregating buy/sell across years.
"""
import pandas as pd
import io
import base64
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class KiteHolding:
    """Parsed holding from Kite AGTS."""
    symbol: str
    exchange: str
    quantity: Decimal
    avg_cost: Decimal
    total_buy_value: Decimal
    total_sell_value: Decimal
    total_buy_qty: Decimal
    total_sell_qty: Decimal


class KiteImportService:
    """Service for importing Kite (Zerodha) holdings."""
    
    @staticmethod
    def parse_xlsx_content(content: bytes) -> Tuple[pd.DataFrame, List[str]]:
        """Parse a single Kite AGTS xlsx file."""
        warnings = []
        
        try:
            # Read excel file
            df = pd.read_excel(io.BytesIO(content), header=None)
            
            # Find the header row containing 'Symbol'
            header_row = None
            for i, row in df.iterrows():
                if 'Symbol' in str(row.values):
                    header_row = i
                    break
            
            if header_row is None:
                warnings.append("Could not find header row with 'Symbol'")
                return pd.DataFrame(), warnings
            
            # Re-read with proper header
            df = pd.read_excel(io.BytesIO(content), header=header_row)
            
            # Filter to rows with valid symbols
            df = df[df['Symbol'].notna()]
            
            # Ensure required columns exist
            required_cols = ['Symbol', 'Exchange', 'Buy Quantity', 'Buy Value', 'Sell Quantity', 'Sell Value']
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                warnings.append(f"Missing columns: {missing}")
                return pd.DataFrame(), warnings
            
            return df, warnings
            
        except Exception as e:
            warnings.append(f"Error parsing xlsx: {str(e)}")
            return pd.DataFrame(), warnings
    
    @staticmethod
    def aggregate_holdings(dataframes: List[pd.DataFrame]) -> List[KiteHolding]:
        """Aggregate holdings across multiple AGTS files."""
        # Combine all dataframes
        if not dataframes:
            return []
        
        combined = pd.concat(dataframes, ignore_index=True)
        
        # Group by symbol and exchange, sum quantities and values
        grouped = combined.groupby(['Symbol', 'Exchange']).agg({
            'Buy Quantity': 'sum',
            'Buy Value': 'sum',
            'Sell Quantity': 'sum',
            'Sell Value': 'sum'
        }).reset_index()
        
        holdings = []
        for _, row in grouped.iterrows():
            buy_qty = Decimal(str(row['Buy Quantity']))
            sell_qty = Decimal(str(row['Sell Quantity']))
            buy_value = Decimal(str(row['Buy Value']))
            sell_value = Decimal(str(row['Sell Value']))
            
            net_qty = buy_qty - sell_qty
            
            # Only include positive holdings
            if net_qty > 0:
                # Calculate average cost from total buy value / total buy qty
                # This is simplified - doesn't account for FIFO properly
                avg_cost = buy_value / buy_qty if buy_qty > 0 else Decimal("0")
                
                holdings.append(KiteHolding(
                    symbol=row['Symbol'],
                    exchange=row['Exchange'],
                    quantity=net_qty,
                    avg_cost=avg_cost.quantize(Decimal("0.01")),
                    total_buy_value=buy_value,
                    total_sell_value=sell_value,
                    total_buy_qty=buy_qty,
                    total_sell_qty=sell_qty,
                ))
        
        return holdings
    
    @staticmethod
    def parse_multiple_files(file_contents: List[bytes]) -> Tuple[List[KiteHolding], List[str]]:
        """Parse multiple AGTS files and return aggregated holdings."""
        all_warnings = []
        dataframes = []
        
        for content in file_contents:
            df, warnings = KiteImportService.parse_xlsx_content(content)
            all_warnings.extend(warnings)
            if not df.empty:
                dataframes.append(df)
        
        holdings = KiteImportService.aggregate_holdings(dataframes)
        return holdings, all_warnings
    
    @staticmethod
    def decode_base64(content: str) -> bytes:
        """Decode base64 content to bytes."""
        try:
            return base64.b64decode(content)
        except Exception:
            return content.encode('utf-8')
