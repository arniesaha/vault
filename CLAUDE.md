# Portfolio Tracker

Personal web application to track stock investments across Canadian (TSX, TSX-V), US (NASDAQ, NYSE), and Indian (NSE, BSE) markets with analytics and multi-currency support.

## Tech Stack

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy, SQLite
- **Frontend:** React 18 + Vite, TailwindCSS, Recharts, TanStack Query
- **External APIs:** yfinance (prices), exchangerate-api.com (currency)

## Quick Start

### Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Or use: `./start-backend.sh`

### Frontend
```bash
cd frontend
npm run dev
```
Or use: `./start-frontend.sh`

### URLs
- Frontend: http://localhost:5173
- API: http://localhost:8000/api/v1
- API Docs: http://localhost:8000/docs

## Project Structure

```
portfolio-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Settings
│   │   ├── database.py       # SQLAlchemy setup
│   │   ├── models/           # ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── routers/          # API routes
│   │   └── services/         # Business logic
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/            # Page components
│   │   ├── hooks/            # Custom hooks (React Query)
│   │   ├── services/         # API client
│   │   └── utils/            # Formatters, constants
│   └── package.json
├── data/
│   └── portfolio.db          # SQLite database
└── docs/                     # Full documentation
```

## Key API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /holdings` | List all active holdings |
| `POST /holdings` | Create holding |
| `GET /transactions` | List all transactions |
| `POST /transactions` | Create transaction |
| `GET /prices/current` | Current prices for all holdings |
| `GET /prices/cached` | Cached prices (instant, no API call) |
| `POST /prices/refresh` | Force refresh all prices |
| `GET /analytics/portfolio/summary` | Portfolio overview |
| `GET /analytics/allocation` | Geographic & exchange breakdown |
| `GET /analytics/realized-gains` | Realized gains with FIFO calculation |
| `GET /analytics/recommendations` | Portfolio health recommendations |
| `GET /analytics/account-breakdown` | Breakdown by account type (TFSA, RRSP, etc.) |
| `GET /holdings/account-types` | List available account types |
| `POST /import/preview` | Preview CSV import |
| `POST /import/transactions` | Import transactions from CSV |
| `GET /import/formats` | List supported import formats |
| `GET /portfolio/history` | Portfolio value history for charts |

## Database Tables

- `holdings` - Stock positions (symbol, exchange, quantity, avg_price)
- `transactions` - Buy/sell history
- `price_history` - Historical price data
- `current_price_cache` - Fast-access price cache for instant page loads
- `exchange_rates` - Currency conversion rates
- `portfolio_snapshots` - Daily portfolio value snapshots

## Development Guidelines

### Backend
- Use async/await for I/O operations
- Validate inputs with Pydantic
- Use Decimal for financial calculations (never float)
- Return appropriate HTTP status codes

### Frontend
- Use React Query (TanStack Query) for server state
- Use `formatters.js` for display formatting
- Handle loading and error states in components

### Symbol Formats
- TSX: `SHOP.TO`, `TD.TO`
- NSE: `RELIANCE.NS`, `TCS.NS`
- BSE: `RELIANCE.BO`
- US: `AAPL`, `MSFT` (no suffix)

## Current Status

**Complete:**
- Holdings CRUD with soft delete
- Transaction history with FIFO cost basis calculation
- Real-time prices via yfinance (15-min cache + DB cache)
- Portfolio analytics (summary, allocation, performance, realized gains, recommendations)
- Multi-currency support (CAD, USD, INR)
- Responsive dashboard UI
- Portfolio value history chart with snapshots
- Import from TD Direct Investing (CSV)
- Import from Wealthsimple (CSV)
- Request deduplication for faster cold starts
- News page with AI insights
- **Account type tracking** (TFSA, RRSP, FHSA, Non-Registered, etc.)

**In Progress:**
- AI features expansion

**Planned (Upcoming):**
- Dividend tracking and income reporting
- DRIP (Dividend Reinvestment) support
- Tax reporting (capital gains, dividend summaries by year)
- Zerodha/ICICI Direct import support
- Export to CSV/PDF

## Known Issues

1. Yahoo Finance rate limits - 15-min cache helps, wait if 429 errors occur
2. Import only supports BUY/SELL transactions - dividends (DIV, TXPDDV) are skipped (planned feature)

## Import Support

| Platform | Supported | Transaction Types |
|----------|-----------|-------------------|
| TD Direct Investing | ✅ | BUY, SELL |
| Wealthsimple | ✅ | BUY, SELL |
| Zerodha | ❌ Planned | - |
| ICICI Direct | ❌ Planned | - |

**Note:** Dividend transactions (DIV, TXPDDV, etc.) are currently skipped. Dividend tracking is a planned feature.

## Documentation

See `/docs` folder for detailed documentation:
- `QUICKSTART.md` - Get running quickly
- `PROJECT.md` - Full specifications and task tracker
- `DEPLOYMENT.md` - Docker and NAS deployment
- `TROUBLESHOOTING.md` - Common issues and solutions
