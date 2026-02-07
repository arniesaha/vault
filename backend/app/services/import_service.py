"""
Import service for parsing CSV files from various brokers.

Supported platforms:
- TD Direct Investing (Canada)
- Wealthsimple (Canada)
"""
import csv
import io
import re
import base64
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple
import logging

from sqlalchemy.orm import Session

from ..models.holding import Holding
from ..models.transaction import Transaction
from ..schemas.import_schema import (
    ImportPlatform,
    ParsedTransaction,
    ImportPreviewResponse,
    ImportResult,
    SupportedFormat,
)

logger = logging.getLogger(__name__)


# Symbol mappings for standardization
SYMBOL_MAPPINGS = {
    # TD Direct descriptions to standard symbols
    "ISHARES CORE EQUITY ETF": ("XEQT", "iShares Core Equity ETF Portfolio", "TSX", "CA", "CAD"),
    "VANGUARD FTSE CDN H/D ETF": ("VDY", "Vanguard FTSE Canadian High Dividend Yield Index ETF", "TSX", "CA", "CAD"),
    "VANGUARD FTSE CDN HI DIV": ("VDY", "Vanguard FTSE Canadian High Dividend Yield Index ETF", "TSX", "CA", "CAD"),
    "GLB X NSDQ-100 CRP CL ETF": ("HXQ", "Global X Nasdaq-100 Index Corporate Class ETF", "TSX", "CA", "CAD"),
    "VANGUARD 500 INDX ETF-NEW": ("VOO", "Vanguard S&P 500 ETF", "NYSE", "US", "USD"),
    "VANGUARD 500 INDX ETF": ("VOO", "Vanguard S&P 500 ETF", "NYSE", "US", "USD"),
    "VANGUARD TTL STK MRKT ETF": ("VTI", "Vanguard Total Stock Market ETF", "NYSE", "US", "USD"),
    "VANGUARD TOT INTL STK ETF": ("VXUS", "Vanguard Total International Stock ETF", "NASDAQ", "US", "USD"),
    "SCHWAB US DIV EQTY    ETF": ("SCHD", "Schwab US Dividend Equity ETF", "NYSE", "US", "USD"),
    "SCHWAB US DIV EQTY ETF": ("SCHD", "Schwab US Dividend Equity ETF", "NYSE", "US", "USD"),
    "FIDELITY MSCI HLTHCR ETF": ("FHLC", "Fidelity MSCI Health Care Index ETF", "NYSE", "US", "USD"),
    "NVIDIA CORP": ("NVDA", "NVIDIA Corporation", "NASDAQ", "US", "USD"),
    "BROADCOM INC": ("AVGO", "Broadcom Inc", "NASDAQ", "US", "USD"),
    "PALANTIR TECHS INC CL-A": ("PLTR", "Palantir Technologies Inc", "NYSE", "US", "USD"),
    "MEDTRONIC PLC": ("MDT", "Medtronic PLC", "NYSE", "US", "USD"),
}

# Canadian ETFs (for Wealthsimple)
CANADIAN_SYMBOLS = {
    "VDY": ("Vanguard FTSE Canadian High Dividend Yield Index ETF", "TSX", "CA", "CAD"),
    "XEF": ("iShares Core MSCI EAFE IMI Index ETF", "TSX", "CA", "CAD"),
    "HXQ": ("Global X Nasdaq-100 Index Corporate Class ETF", "TSX", "CA", "CAD"),
    "XEQT": ("iShares Core Equity ETF Portfolio", "TSX", "CA", "CAD"),
    "VBAL": ("Vanguard Balanced ETF Portfolio", "TSX", "CA", "CAD"),
    "KILO": ("Purpose Gold Bullion Fund", "TSX", "CA", "CAD"),
    "ZRE": ("BMO Equal Weight REITs Index ETF", "TSX", "CA", "CAD"),
}

# US stocks/ETFs
US_SYMBOLS = {
    "NVDA": ("NVIDIA Corporation", "NASDAQ", "US", "USD"),
    "LLY": ("Eli Lilly & Co", "NYSE", "US", "USD"),
    "TSM": ("Taiwan Semiconductor Manufacturing", "NYSE", "US", "USD"),
    "PLTR": ("Palantir Technologies Inc", "NYSE", "US", "USD"),
    "VGT": ("Vanguard Information Technology ETF", "NYSE", "US", "USD"),
    "FXI": ("iShares China Large-Cap ETF", "NYSE", "US", "USD"),
    "KWEB": ("KraneShares CSI China Internet ETF", "NYSE", "US", "USD"),
    "ANET": ("Arista Networks Inc", "NYSE", "US", "USD"),
    "BOTZ": ("Global X Robotics & Artificial Intelligence ETF", "NASDAQ", "US", "USD"),
    "META": ("Meta Platforms Inc", "NASDAQ", "US", "USD"),
    "VOO": ("Vanguard S&P 500 ETF", "NYSE", "US", "USD"),
    "VTI": ("Vanguard Total Stock Market ETF", "NYSE", "US", "USD"),
    "VXUS": ("Vanguard Total International Stock ETF", "NASDAQ", "US", "USD"),
    "SCHD": ("Schwab US Dividend Equity ETF", "NYSE", "US", "USD"),
    "FHLC": ("Fidelity MSCI Health Care Index ETF", "NYSE", "US", "USD"),
    "AVGO": ("Broadcom Inc", "NASDAQ", "US", "USD"),
    "MDT": ("Medtronic PLC", "NYSE", "US", "USD"),
}


class ImportService:
    """Service for importing transactions from various platforms."""

    @staticmethod
    def get_supported_formats() -> List[SupportedFormat]:
        """Return list of supported import formats."""
        return [
            SupportedFormat(
                platform=ImportPlatform.TD_DIRECT.value,
                name="TD Direct Investing",
                description="Import from TD Direct Investing activity CSV export",
                file_types=["csv"],
                date_format="DD MMM YYYY (e.g., 05 Jan 2026)",
                example_fields=["Trade Date", "Settle Date", "Description", "Action", "Quantity", "Price", "Commission", "Net Amount", "(Security Type)", "(Currency)"],
                notes="Export from Accounts > Activity. Only BUY and SELL transactions are imported. Dividends (DIV, TXPDDV) and other actions are skipped.",
            ),
            SupportedFormat(
                platform=ImportPlatform.WEALTHSIMPLE.value,
                name="Wealthsimple",
                description="Import from Wealthsimple monthly statement CSV",
                file_types=["csv"],
                date_format="YYYY-MM-DD",
                example_fields=["date", "transaction", "description", "amount", "(balance)", "(currency)"],
                notes="Export using Wealthsimple Trade Enhancer extension or Wealthica. Only BUY and SELL transactions are imported. Dividends (DIV), deposits, and withdrawals are skipped.",
            ),
        ]

    @staticmethod
    def decode_file_content(content: str) -> str:
        """Decode base64 content if needed, otherwise return as-is."""
        try:
            # Try to decode as base64
            decoded = base64.b64decode(content).decode('utf-8')
            return decoded
        except Exception:
            # Already plain text
            return content

    @staticmethod
    def parse_td_direct_csv(content: str, account_type: Optional[str] = None) -> Tuple[List[ParsedTransaction], List[str]]:
        """
        Parse TD Direct Investing CSV export.

        Format (may vary):
        Line 1: As of Date,2026-01-24 21:59:31
        Line 2: Account,TD Direct Investing - 71XW74J
        Line 3: (empty or just comma)
        Line 4: Trade Date,Settle Date,Description,Action,Quantity,Price,Commission,Net Amount[,Security Type,Currency]
        Line 5+: Data rows

        Actions to import: BUY, SELL
        Note: Other actions like TXPDDV (dividends), DIV, WHTX02 are skipped.
        """
        transactions = []
        warnings = []

        lines = content.strip().split('\n')

        # Skip header lines and find the actual CSV data
        # Handle both "Trade Date," and potential whitespace
        data_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("Trade Date,") or stripped.startswith("Trade Date\t"):
                data_start = i
                break

        if data_start == 0:
            warnings.append("Could not find CSV header row. Expected header starting with 'Trade Date,'")
            return transactions, warnings

        # Parse CSV starting from header row
        csv_content = '\n'.join(lines[data_start:])
        reader = csv.DictReader(io.StringIO(csv_content))

        # Track skipped actions for better user feedback
        skipped_actions = {}

        for row in reader:
            action = row.get('Action', '').strip()

            # Only process BUY and SELL transactions
            if action not in ('BUY', 'SELL'):
                # Track what we're skipping
                skipped_actions[action] = skipped_actions.get(action, 0) + 1
                continue

            try:
                # Parse date (format: "05 Jan 2026")
                trade_date_str = row.get('Trade Date', '').strip()
                trade_date = datetime.strptime(trade_date_str, "%d %b %Y").date()

                # Parse description to extract symbol
                description = row.get('Description', '').strip()
                # Remove trailing codes like "GW-777156"
                clean_description = re.sub(r'\s+[A-Z]{2}-\d+$', '', description)

                # Look up symbol mapping
                symbol_info = None
                for desc_key, info in SYMBOL_MAPPINGS.items():
                    if desc_key in clean_description.upper():
                        symbol_info = info
                        break

                if not symbol_info:
                    warnings.append(f"Unknown security: {clean_description}")
                    continue

                symbol, company_name, exchange, country, currency = symbol_info

                # Parse quantity (handle scientific notation like "2E+1" = 20)
                qty_str = row.get('Quantity', '0').strip()
                if not qty_str:
                    continue
                # Handle negative quantities for SELL and round to 4 decimal places
                quantity = abs(Decimal(qty_str)).quantize(Decimal("0.0001"))

                # Parse price
                price_str = row.get('Price', '0').strip()
                if not price_str:
                    warnings.append(f"Missing price for {symbol} on {trade_date}")
                    continue
                price = Decimal(price_str)

                # Parse commission (fees)
                commission_str = row.get('Commission', '0').strip() or '0'
                commission = abs(Decimal(commission_str))

                # Override currency if present in row
                row_currency = row.get('Currency', '').strip()
                if row_currency:
                    currency = row_currency

                transactions.append(ParsedTransaction(
                    date=trade_date,
                    symbol=symbol,
                    company_name=company_name,
                    exchange=exchange,
                    country=country,
                    transaction_type=action,
                    quantity=quantity,
                    price_per_share=price,
                    fees=commission,
                    currency=currency,
                    source=ImportPlatform.TD_DIRECT.value,
                    account_type=account_type,
                    raw_description=description,
                ))

            except (ValueError, InvalidOperation) as e:
                warnings.append(f"Error parsing row: {e}")
                continue

        # Add helpful warning if no BUY/SELL transactions found but other actions exist
        if not transactions and skipped_actions:
            action_summary = ", ".join([f"{action}: {count}" for action, count in skipped_actions.items()])
            warnings.append(f"No BUY/SELL transactions found. Skipped actions: {action_summary}")
            warnings.append("Only BUY and SELL transactions can be imported. Dividends (DIV, TXPDDV) and other actions are not supported.")

        return transactions, warnings

    @staticmethod
    def parse_wealthsimple_csv(content: str, account_type: Optional[str] = None) -> Tuple[List[ParsedTransaction], List[str]]:
        """
        Parse Wealthsimple monthly statement CSV.

        Format:
        date,transaction,description,amount[,balance,currency]
        2025-03-12,BUY,"NVDA - NVIDIA Corp.: Bought 5.0000 shares (executed at 2025-03-12), FX Rate: 1.4644",-1500.00
        """
        transactions = []
        warnings = []

        reader = csv.DictReader(io.StringIO(content))

        # Track skipped transaction types for better user feedback
        skipped_types = {}

        for row in reader:
            trans_type = row.get('transaction', '').strip()
            if trans_type not in ('BUY', 'SELL'):
                # Track what we're skipping
                skipped_types[trans_type] = skipped_types.get(trans_type, 0) + 1
                continue

            try:
                description = row.get('description', '')
                parsed = ImportService._parse_wealthsimple_description(description)

                if not parsed['symbol'] or not parsed['quantity']:
                    warnings.append(f"Could not parse: {description}")
                    continue

                symbol = parsed['symbol']
                is_canadian = symbol in CANADIAN_SYMBOLS

                # Calculate price per share
                amount_cad = Decimal(row.get('amount', '0'))
                price, currency = ImportService._calculate_wealthsimple_price(
                    amount_cad,
                    parsed['quantity'],
                    parsed['fx_rate'],
                    is_canadian
                )

                # Determine exchange and country
                if is_canadian:
                    company_name, exchange, country, _ = CANADIAN_SYMBOLS[symbol]
                elif symbol in US_SYMBOLS:
                    company_name, exchange, country, _ = US_SYMBOLS[symbol]
                else:
                    company_name = parsed['company_name'] or symbol
                    exchange = "NYSE"
                    country = "US"
                    currency = "USD"
                    warnings.append(f"Unknown symbol {symbol}, defaulting to NYSE")

                # Parse date
                date_str = row.get('date', '')
                if parsed['executed_date']:
                    trade_date = parsed['executed_date']
                else:
                    trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                transactions.append(ParsedTransaction(
                    date=trade_date,
                    symbol=symbol,
                    company_name=company_name,
                    exchange=exchange,
                    country=country,
                    transaction_type=trans_type,
                    quantity=parsed['quantity'],
                    price_per_share=price,
                    fees=Decimal("0"),  # Wealthsimple has no explicit fees
                    currency=currency,
                    source=ImportPlatform.WEALTHSIMPLE.value,
                    account_type=account_type,
                    raw_description=description,
                ))

            except Exception as e:
                warnings.append(f"Error parsing row: {e}")
                continue

        # Add helpful warning if no BUY/SELL transactions found but other types exist
        if not transactions and skipped_types:
            type_summary = ", ".join([f"{t}: {count}" for t, count in skipped_types.items()])
            warnings.append(f"No BUY/SELL transactions found. Skipped transaction types: {type_summary}")
            warnings.append("Only BUY and SELL transactions can be imported. Dividends (DIV), deposits, and withdrawals are not supported.")

        return transactions, warnings

    @staticmethod
    def _parse_wealthsimple_description(description: str) -> dict:
        """Parse Wealthsimple transaction description."""
        result = {
            "symbol": None,
            "company_name": None,
            "quantity": None,
            "action": None,
            "executed_date": None,
            "fx_rate": None,
        }

        # Extract symbol and company name
        match = re.match(r"^([A-Z]+)\s*-\s*(.+?):\s*(Bought|Sold)", description)
        if match:
            result["symbol"] = match.group(1)
            result["company_name"] = match.group(2).strip()
            result["action"] = "BUY" if match.group(3) == "Bought" else "SELL"

        # Extract quantity
        qty_match = re.search(r"(Bought|Sold)\s+([\d.]+)\s+shares", description)
        if qty_match:
            result["quantity"] = Decimal(qty_match.group(2))

        # Extract executed date
        date_match = re.search(r"executed at (\d{4}-\d{2}-\d{2})", description)
        if date_match:
            result["executed_date"] = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()

        # Extract FX rate
        fx_match = re.search(r"FX Rate:\s*([\d.]+)", description)
        if fx_match:
            result["fx_rate"] = Decimal(fx_match.group(1))

        return result

    @staticmethod
    def _calculate_wealthsimple_price(
        amount_cad: Decimal,
        quantity: Decimal,
        fx_rate: Optional[Decimal],
        is_canadian: bool
    ) -> Tuple[Decimal, str]:
        """Calculate price per share for Wealthsimple transactions."""
        amount_abs = abs(amount_cad)

        if is_canadian or fx_rate is None:
            price = amount_abs / quantity
            return price.quantize(Decimal("0.0001")), "CAD"
        else:
            price = amount_abs / quantity / fx_rate
            return price.quantize(Decimal("0.0001")), "USD"

    @staticmethod
    def parse_file(
        content: str,
        platform: ImportPlatform,
        account_type: Optional[str] = None
    ) -> Tuple[List[ParsedTransaction], List[str]]:
        """Parse file content based on platform."""
        decoded_content = ImportService.decode_file_content(content)

        if platform == ImportPlatform.TD_DIRECT:
            return ImportService.parse_td_direct_csv(decoded_content, account_type)
        elif platform == ImportPlatform.WEALTHSIMPLE:
            return ImportService.parse_wealthsimple_csv(decoded_content, account_type)
        else:
            return [], [f"Unsupported platform: {platform}"]

    @staticmethod
    def preview_import(
        db: Session,
        content: str,
        platform: ImportPlatform,
        account_type: Optional[str] = None
    ) -> ImportPreviewResponse:
        """Preview import without saving to database."""
        transactions, warnings = ImportService.parse_file(content, platform, account_type)

        # Get existing holdings
        existing_holdings = db.query(Holding).filter(Holding.is_active == True).all()
        existing_symbols = {h.symbol for h in existing_holdings}

        # Get existing transactions for deduplication
        # Normalize decimals to remove trailing zeros for consistent comparison
        existing_transactions = db.query(Transaction).all()
        existing_dedup_keys = {
            f"{t.transaction_date}|{t.symbol}|{t.transaction_type}|{t.quantity.normalize()}|{t.price_per_share.normalize()}"
            for t in existing_transactions
        }

        # Categorize symbols and count duplicates
        new_symbols = set()
        import_existing_symbols = set()
        potential_duplicates = 0

        for t in transactions:
            if t.symbol in existing_symbols:
                import_existing_symbols.add(t.symbol)
            else:
                new_symbols.add(t.symbol)

            if t.dedup_key in existing_dedup_keys:
                potential_duplicates += 1

        return ImportPreviewResponse(
            platform=platform.value,
            total_transactions=len(transactions),
            buy_transactions=len([t for t in transactions if t.transaction_type == "BUY"]),
            sell_transactions=len([t for t in transactions if t.transaction_type == "SELL"]),
            transactions=transactions,
            new_symbols=sorted(list(new_symbols)),
            existing_symbols=sorted(list(import_existing_symbols)),
            potential_duplicates=potential_duplicates,
            warnings=warnings,
        )

    @staticmethod
    def import_transactions(
        db: Session,
        content: str,
        platform: ImportPlatform,
        account_type: Optional[str] = None,
        skip_duplicates: bool = True
    ) -> ImportResult:
        """Import transactions into the database."""
        transactions, warnings = ImportService.parse_file(content, platform, account_type)

        if not transactions:
            return ImportResult(
                success=False,
                transactions_imported=0,
                holdings_created=0,
                holdings_updated=0,
                duplicates_skipped=0,
                errors=["No valid transactions found in file"],
                warnings=warnings,
            )

        # Get existing transactions for deduplication
        # Normalize decimals to remove trailing zeros for consistent comparison
        existing_transactions = db.query(Transaction).all()
        existing_dedup_keys = {
            f"{t.transaction_date}|{t.symbol}|{t.transaction_type}|{t.quantity.normalize()}|{t.price_per_share.normalize()}"
            for t in existing_transactions
        }

        # Track results
        imported_count = 0
        duplicates_skipped = 0
        holdings_created = 0
        holdings_updated = 0
        errors = []

        # Sort transactions by date (oldest first) for proper cost basis calculation
        transactions.sort(key=lambda t: t.date)

        # Group transactions by (symbol, account_type) to create/update holdings
        # This allows same symbol in multiple accounts (e.g., XEQT in both TFSA and FHSA)
        holdings_map = {}  # (symbol, account_type) -> holding

        # Get existing holdings keyed by (symbol, account_type)
        existing_holdings = {(h.symbol, h.account_type): h for h in db.query(Holding).all()}

        for t in transactions:
            holding_key = (t.symbol, t.account_type)

            # Check for duplicates
            if skip_duplicates and t.dedup_key in existing_dedup_keys:
                duplicates_skipped += 1
                continue

            try:
                # Get or create holding for this (symbol, account_type) pair
                if holding_key not in holdings_map:
                    if holding_key in existing_holdings:
                        holding = existing_holdings[holding_key]
                        # Reactivate if needed
                        if not holding.is_active:
                            holding.is_active = True
                            holdings_updated += 1

                        holdings_map[holding_key] = holding
                    else:
                        # Create new holding with zero quantity (will be updated by transaction)
                        holding = Holding(
                            symbol=t.symbol,
                            company_name=t.company_name,
                            exchange=t.exchange,
                            country=t.country,
                            quantity=Decimal("0"),
                            avg_purchase_price=Decimal("0"),
                            currency=t.currency,
                            account_type=t.account_type,
                            first_purchase_date=t.date,
                            is_active=True,
                        )
                        db.add(holding)
                        db.flush()  # Get ID
                        holdings_map[holding_key] = holding
                        existing_holdings[holding_key] = holding
                        holdings_created += 1

                holding = holdings_map[holding_key]

                # Update holding quantities and avg cost
                if t.transaction_type == "BUY":
                    total_cost = (holding.quantity * holding.avg_purchase_price) + \
                                 (t.quantity * t.price_per_share) + t.fees
                    holding.quantity += t.quantity
                    if holding.quantity > 0:
                        holding.avg_purchase_price = total_cost / holding.quantity

                    # Update first purchase date if earlier
                    if holding.first_purchase_date is None or t.date < holding.first_purchase_date:
                        holding.first_purchase_date = t.date
                else:  # SELL
                    if holding.quantity >= t.quantity:
                        holding.quantity -= t.quantity
                    else:
                        warnings.append(f"Sell quantity ({t.quantity}) exceeds holding quantity ({holding.quantity}) for {t.symbol}")
                        holding.quantity = Decimal("0")

                # Create transaction record
                db_transaction = Transaction(
                    holding_id=holding.id,
                    symbol=t.symbol,
                    transaction_type=t.transaction_type,
                    quantity=t.quantity,
                    price_per_share=t.price_per_share,
                    fees=t.fees,
                    transaction_date=t.date,
                    notes=f"Imported from {platform.value}" + (f" ({account_type})" if account_type else ""),
                )
                db.add(db_transaction)
                imported_count += 1

                # Add to existing dedup keys to prevent duplicates within same import
                existing_dedup_keys.add(t.dedup_key)

            except Exception as e:
                errors.append(f"Error importing {t.symbol} on {t.date}: {str(e)}")
                continue

        # Mark holdings with zero quantity as inactive
        for holding in holdings_map.values():
            if holding.quantity <= Decimal("0.0001"):
                holding.is_active = False

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            return ImportResult(
                success=False,
                transactions_imported=0,
                holdings_created=0,
                holdings_updated=0,
                duplicates_skipped=duplicates_skipped,
                account_types_updated=0,
                errors=[f"Database error: {str(e)}"],
                warnings=warnings,
            )

        return ImportResult(
            success=True,
            transactions_imported=imported_count,
            holdings_created=holdings_created,
            holdings_updated=holdings_updated,
            duplicates_skipped=duplicates_skipped,
            account_types_updated=0,  # No longer needed with per-account holdings
            errors=errors,
            warnings=warnings,
        )
