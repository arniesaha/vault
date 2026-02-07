import httpx
from typing import Dict, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy.orm import Session
import logging
from ..models.price import ExchangeRate

logger = logging.getLogger(__name__)


class CurrencyService:
    """Service for handling currency conversions"""

    # Exchange rate API (free tier)
    API_URL = "https://api.exchangerate-api.com/v4/latest/{}"

    # Cache for rates
    _rate_cache: Dict[str, Dict] = {}
    _cache_duration = timedelta(hours=24)

    # Fallback rates for common currencies (used to avoid slow API calls)
    FALLBACK_RATES = {
        'USD:CAD': Decimal('1.37'),
        'CAD:USD': Decimal('0.73'),
        'INR:CAD': Decimal('0.0151'),
        'CAD:INR': Decimal('66.2'),
        'USD:INR': Decimal('86.0'),
        'INR:USD': Decimal('0.012'),
    }

    @classmethod
    async def get_exchange_rate(cls, from_currency: str, to_currency: str, db: Session) -> Optional[Decimal]:
        """
        Get exchange rate from one currency to another.
        Returns None if rate cannot be fetched.
        """
        if from_currency == to_currency:
            return Decimal("1.0")

        # Check database cache first
        today = date.today()
        cached_rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.date == today
        ).first()

        if cached_rate:
            logger.info(f"Using cached exchange rate {from_currency} -> {to_currency}: {cached_rate.rate}")
            return cached_rate.rate

        # Check memory cache
        cache_key = f"{from_currency}:{to_currency}"
        if cache_key in cls._rate_cache:
            cached = cls._rate_cache[cache_key]
            if datetime.now() - cached['timestamp'] < cls._cache_duration:
                return cached['rate']

        # Fetch from API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(cls.API_URL.format(from_currency), timeout=10.0)
                response.raise_for_status()
                data = response.json()

                if 'rates' in data and to_currency in data['rates']:
                    rate = Decimal(str(data['rates'][to_currency]))

                    # Cache in memory
                    cls._rate_cache[cache_key] = {
                        'rate': rate,
                        'timestamp': datetime.now()
                    }

                    # Cache in database
                    db_rate = ExchangeRate(
                        from_currency=from_currency,
                        to_currency=to_currency,
                        rate=rate,
                        date=today
                    )
                    db.add(db_rate)
                    db.commit()

                    logger.info(f"Fetched exchange rate {from_currency} -> {to_currency}: {rate}")
                    return rate
                else:
                    logger.warning(f"Currency {to_currency} not found in rates")
                    return None

        except Exception as e:
            logger.error(f"Error fetching exchange rate {from_currency} -> {to_currency}: {str(e)}")
            return None

    @classmethod
    def get_exchange_rate_sync(cls, from_currency: str, to_currency: str, db: Session) -> Optional[Decimal]:
        """
        Synchronous version of get_exchange_rate.
        Uses in-memory cache first, then database, then API, then fallback rates.
        """
        if from_currency == to_currency:
            return Decimal("1.0")

        # Check in-memory cache FIRST (fastest, no DB query)
        cache_key = f"{from_currency}:{to_currency}"
        if cache_key in cls._rate_cache:
            cached = cls._rate_cache[cache_key]
            if datetime.now() - cached['timestamp'] < cls._cache_duration:
                logger.info(f"Using cached exchange rate {from_currency} -> {to_currency}: {cached['rate']}")
                return cached['rate']

        # For INR, use fallback rates to avoid slow API calls during requests
        # This is acceptable because INR rates don't change dramatically intraday
        fallback_key = f"{from_currency}:{to_currency}"
        if fallback_key in cls.FALLBACK_RATES:
            rate = cls.FALLBACK_RATES[fallback_key]
            cls._rate_cache[cache_key] = {'rate': rate, 'timestamp': datetime.now()}
            logger.info(f"Using fallback exchange rate {from_currency} -> {to_currency}: {rate}")
            return rate

        # Check database cache
        today = date.today()
        cached_rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.date == today
        ).first()

        if cached_rate:
            # Populate in-memory cache
            cls._rate_cache[cache_key] = {'rate': cached_rate.rate, 'timestamp': datetime.now()}
            logger.info(f"Using DB cached exchange rate {from_currency} -> {to_currency}: {cached_rate.rate}")
            return cached_rate.rate

        # Fetch from API synchronously (only for non-INR currencies now)
        try:
            response = httpx.get(cls.API_URL.format(from_currency), timeout=10.0)
            response.raise_for_status()
            data = response.json()

            if 'rates' in data and to_currency in data['rates']:
                rate = Decimal(str(data['rates'][to_currency]))

                # Cache in memory
                cache_key = f"{from_currency}:{to_currency}"
                cls._rate_cache[cache_key] = {
                    'rate': rate,
                    'timestamp': datetime.now()
                }

                # Cache in database (flush only, let caller commit)
                db_rate = ExchangeRate(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=rate,
                    date=today
                )
                db.add(db_rate)
                try:
                    db.flush()
                except Exception:
                    db.rollback()  # Rate might already exist, that's OK

                logger.info(f"Fetched exchange rate {from_currency} -> {to_currency}: {rate}")
                return rate
            else:
                logger.warning(f"Currency {to_currency} not found in API response")

        except Exception as e:
            logger.warning(f"API call failed for {from_currency} -> {to_currency}: {e}")

        # Fallback to approximate rates if API fails
        approximate_rates = {
            'USD:CAD': Decimal('1.37'),
            'CAD:USD': Decimal('0.73'),
            'INR:CAD': Decimal('0.016'),
            'CAD:INR': Decimal('62.5'),
            'USD:INR': Decimal('86.0'),
            'INR:USD': Decimal('0.012'),
        }

        key = f"{from_currency}:{to_currency}"
        if key in approximate_rates:
            rate = approximate_rates[key]
            logger.warning(f"Using fallback rate for {key}: {rate}")
            return rate

        logger.error(f"No exchange rate available for {key}")
        return None

    @classmethod
    def convert_amount(cls, amount: Decimal, from_currency: str, to_currency: str, db: Session) -> Optional[Decimal]:
        """Convert an amount from one currency to another"""
        rate = cls.get_exchange_rate_sync(from_currency, to_currency, db)
        if rate:
            return amount * rate
        return None
