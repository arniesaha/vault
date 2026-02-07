# Portfolio Tracker - Project Documentation

**Last Updated:** February 6, 2026
**Version:** 1.2 (Development)
**Status:** Phase 3 Complete, Phase 4 In Progress

---

## Project Overview

Personal web application to track stock investments across Canadian (TSX, TSX-V), US (NASDAQ, NYSE), and Indian (NSE, BSE) markets with analytics, import capabilities, and AI-powered insights.

### Tech Stack
- **Backend:** FastAPI (Python 3.11+), SQLAlchemy, SQLite
- **Frontend:** React 18 + Vite, TailwindCSS, Recharts, TanStack Query
- **External APIs:** yfinance (prices), exchangerate-api.com (currency), Claude API (AI features)

---

## Current Implementation Status

### ✅ Complete (Phase 1, 2 & 3)

**Backend:**
- Holdings CRUD API (`/api/v1/holdings`)
- Transactions API with cost basis calculation (`/api/v1/transactions`)
- Real-time price fetching via yfinance with 15-min caching
- Portfolio analytics endpoints (summary, allocation, performance, realized gains, recommendations)
- Currency conversion service (CAD, USD, INR)
- Portfolio snapshot infrastructure with daily snapshots
- Portfolio history API with chart data
- Database models: holdings, transactions, price_history, exchange_rates, portfolio_snapshots, current_price_cache
- **Import system** - TD Direct Investing and Wealthsimple CSV parsers
- Price caching with request deduplication (prevents slow cold starts)

**Frontend:**
- Dashboard with summary cards, allocation charts, top holdings
- Portfolio value history chart
- Holdings management page (add/edit/delete)
- Transactions page with filtering and CSV import
- News page with AI-generated insights
- React Query hooks with progressive loading (cached → live)
- Responsive design (desktop/tablet/mobile)

### 🔄 In Progress (Phase 4)

- AI features expansion (news summarization improvements)
- Additional broker import formats

### ❌ Not Started (Phase 5)

- Dividend tracking and income reporting
- Export features (CSV/PDF)
- Test coverage
- Zerodha/ICICI Direct import support

---

## Requirements

### Core Features (MVP)

1. **Portfolio Management**
   - Add/edit/delete holdings with symbol, exchange, quantity, avg price
   - Record buy/sell transactions
   - Automatic cost basis calculation
   - Soft delete for holdings (preserve history)

2. **Price Updates**
   - Real-time prices from yfinance
   - 15-minute cache for efficiency
   - Manual refresh capability
   - Multi-exchange support (TSX, TSX-V, NASDAQ, NYSE, NSE, BSE)

3. **Analytics**
   - Portfolio summary (total value, gains, daily change)
   - Geographic allocation (by country)
   - Exchange allocation
   - Top performers/holdings
   - Portfolio value over time

4. **Currency Handling**
   - Support CAD, USD, INR
   - Auto-convert to CAD for display
   - Cache exchange rates

### Import Features (NEW)

#### Supported Platforms

| Platform | Country | Import Method | Status |
|----------|---------|---------------|--------|
| TD Direct Investing | Canada | CSV (Gain/Loss tab export) | Planned |
| Wealthsimple | Canada | CSV (via browser extension) | Planned |
| Zerodha Kite | India | API (free personal) + Console CSV | Planned |
| Smallcase | India | Via Zerodha (holdings in broker) | Planned |
| ICICI Direct | India | Excel/CSV (Tradebook export) | Planned |

#### Import Architecture

```
User uploads CSV/Excel
        ↓
Platform-specific parser (detects format)
        ↓
Unified internal format
        ↓
Validation & de-duplication
        ↓
Holdings/Transactions created
```

#### Unified Import Format (Internal)

```json
{
  "transactions": [
    {
      "date": "2024-01-15",
      "symbol": "SHOP.TO",
      "exchange": "TSX",
      "type": "BUY",
      "quantity": 10,
      "price": 65.50,
      "fees": 9.99,
      "currency": "CAD",
      "source": "td_direct"
    }
  ]
}
```

#### Platform-Specific Details

**TD Direct Investing (Canada)**
- Export: Accounts > Gain/Loss > By Transaction > Export CSV
- Fields: Date, Symbol, Transaction Type, Quantity, Price, Amount, Fees
- Challenges: 60-day activity limit (use Gain/Loss for history back to 2017)
- Date format: YYYY-MM-DD

**Wealthsimple (Canada)**
- Export: Use Wealthsimple Trade Enhancer browser extension or Wealthica
- Fields: Date, Payee, Notes, Category, Amount, Transaction Type, Account Name
- Challenges: No official export; rely on third-party tools

**Zerodha Kite (India)**
- API: Kite Connect Personal (free) for current holdings
- CSV: Console > Reports > Tradebook (max 365 days per export)
- Fields: trade_date, tradingsymbol, exchange, segment, trade_type, quantity, price
- Date format: DD-MM-YYYY

**Smallcase (India)**
- Export via connected broker (typically Zerodha)
- Individual stocks appear in broker tradebook
- No direct Smallcase export

**ICICI Direct (India)**
- Export: Trade & Invest > Equity > Trade Book > Export to Excel
- Fields: Trade Date, Trading Symbol, Exchange, Trade Type, Quantity, Price
- Challenges: Only works after market close
- Date format: DD-MM-YYYY

### AI Features (Phase 4)

1. **News Summarization**
   - Fetch top 3 news per holding
   - Claude-generated 2-3 sentence summary
   - Cache for 24 hours

2. **Portfolio Health Check**
   - Concentration analysis
   - Sector diversification
   - Basic risk assessment

3. **Rebalancing Suggestions**
   - Identify over-concentrated positions
   - Suggest allocation changes

---

## Task Tracker

### Legend
- 🔴 Not Started
- 🟡 In Progress
- 🟢 Complete
- ⏸️ Blocked

### Phase 3: Analytics & History

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Verify database initialization | 🔴 | High | Run backend once to create portfolio.db |
| Test snapshot service | 🔴 | High | Verify create/retrieve functionality |
| Connect portfolio history chart to data | 🔴 | High | Chart component exists, needs data |
| Add snapshot creation on price refresh | 🔴 | Medium | Auto-capture daily values |
| Backfill historical snapshots | 🔴 | Low | Use price history to reconstruct |

### Phase 4: Import System

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Design import API endpoint | 🟢 | High | POST /api/v1/import/* |
| Create unified import schema | 🟢 | High | Pydantic models for validation |
| Build TD Direct CSV parser | 🟢 | High | Supports BUY/SELL, handles format variations |
| Build Wealthsimple parser | 🟢 | High | Supports BUY/SELL transactions |
| Frontend import UI | 🟢 | High | File upload + preview in Transactions page |
| De-duplication logic | 🟢 | Medium | Prevents duplicate transactions on re-import |
| Build Zerodha CSV parser | 🔴 | Medium | Indian broker support |
| Build ICICI Direct parser | 🔴 | Low | Excel/CSV handling |
| Zerodha API integration | 🔴 | Low | Optional real-time sync |

### Phase 4: AI Features

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Implement news service | 🔴 | Medium | NewsAPI or Alpha Vantage |
| Add Claude API integration | 🔴 | Medium | News summarization |
| Build health check endpoint | 🔴 | Medium | Concentration analysis |
| Build rebalancing endpoint | 🔴 | Low | Suggestion generation |
| Complete News page UI | 🔴 | Medium | Currently placeholder |

### Phase 5: Polish

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Add unit tests (backend) | 🔴 | High | pytest framework |
| Add integration tests | 🔴 | Medium | API endpoint testing |
| Add frontend tests | 🔴 | Low | React Testing Library |
| Performance optimization | 🔴 | Low | Caching, query optimization |
| Sample data generator | 🔴 | Low | For testing/demo |
| Export to CSV | 🔴 | Low | Post-MVP feature |

### Bug Fixes / Technical Debt

| Task | Status | Priority | Notes |
|------|--------|----------|-------|
| Verify transaction history working | 🟢 | High | Fixed - FIFO calculation working |
| Test multi-currency calculations | 🟢 | Medium | CAD/USD/INR conversions working |
| Fix slow cold start loading | 🟢 | High | Added price cache + request deduplication |
| Add request logging middleware | 🔴 | Low | Debugging aid |

---

## Upcoming Features (Roadmap)

### ✅ Account Type Tracking (Implemented)

Track holdings by registered account type for tax planning.

**Supported Account Types:**
- TFSA - Tax-Free Savings Account
- RRSP - Registered Retirement Savings Plan
- FHSA - First Home Savings Account
- RESP - Registered Education Savings Plan
- LIRA - Locked-In Retirement Account
- RRIF - Registered Retirement Income Fund
- NON_REG - Non-Registered (Taxable)
- MARGIN - Margin Account

**Features:**
- Filter holdings by account type
- Account breakdown analytics endpoint
- Tax-advantaged vs taxable split
- Import with account type assignment
- Per-account performance tracking

**API Endpoints:**
- `GET /holdings/account-types` - List available account types
- `GET /holdings?account_type=TFSA` - Filter holdings by account
- `GET /analytics/account-breakdown` - Portfolio breakdown by account type

---

### 🔜 Dividend Tracking (Phase 5)

Track dividend income separately from buy/sell transactions.

**Backend:**
- New `dividends` table: id, holding_id, symbol, amount, currency, ex_date, pay_date, source
- Import dividend transactions from TD Direct (DIV, TXPDDV) and Wealthsimple (DIV)
- API endpoints: GET/POST /api/v1/dividends
- Dividend yield calculations per holding
- Annual dividend income summary

**Frontend:**
- Dividend history page
- Dividend income by month/year chart
- Dividend yield display on holdings
- Import dividends from CSV (same parsers, new transaction type)

**Data Model:**
```sql
dividends (
  id, holding_id, symbol, exchange,
  amount, currency,
  ex_date, pay_date, record_date,
  dividend_type (CASH, DRIP, SPECIAL),
  withholding_tax,
  source (manual, td_direct, wealthsimple),
  notes, created_at
)
```

### 🔜 DRIP (Dividend Reinvestment) Support

- Track reinvested dividends as both dividend income AND buy transactions
- Properly calculate cost basis for DRIP shares
- Link dividend to resulting buy transaction

### 🔜 Tax Reporting

- Capital gains summary by tax year
- Dividend income summary by tax year
- T5 slip data preparation (Canadian taxes)
- ACB (Adjusted Cost Base) tracking for Canadian tax rules

### 🔜 Performance Improvements

- Background price refresh scheduler (every 15 min during market hours)
- WebSocket for real-time price updates
- Database query optimization for large portfolios

### 🔜 Additional Import Sources

| Platform | Country | Priority | Notes |
|----------|---------|----------|-------|
| Zerodha Kite | India | Medium | Console CSV export |
| ICICI Direct | India | Low | Excel tradebook export |
| Questrade | Canada | Low | CSV export |
| Interactive Brokers | Multi | Low | Flex Query export |

---

## API Reference

### Base URL
`http://localhost:8000/api/v1`

### Endpoints

**Holdings**
```
GET    /holdings              List all active holdings
GET    /holdings/{id}         Get single holding
POST   /holdings              Create holding
PUT    /holdings/{id}         Update holding
DELETE /holdings/{id}         Soft delete holding
```

**Transactions**
```
GET    /transactions          List all transactions
GET    /transactions/holding/{id}  Transactions for holding
POST   /transactions          Create transaction
DELETE /transactions/{id}     Delete transaction
```

**Prices**
```
GET    /prices/current        Current prices for all holdings
GET    /prices/{symbol}       Price for single symbol
POST   /prices/refresh        Force refresh all prices
GET    /prices/history/{symbol}  Historical prices (30 days)
```

**Analytics**
```
GET    /portfolio/summary     Portfolio overview
GET    /analytics/allocation  Geographic & exchange breakdown
GET    /analytics/performance Performance metrics
```

**Snapshots**
```
POST   /snapshots/create      Create daily snapshot
GET    /snapshots/latest      Latest snapshot
GET    /snapshots/portfolio/history  Historical values
POST   /snapshots/backfill    Backfill historical data
```

**Import (Planned)**
```
POST   /import/transactions   Import from CSV/Excel
GET    /import/formats        List supported formats
POST   /import/preview        Preview import without saving
```

---

## Database Schema

### Tables

```sql
holdings (
  id, symbol, company_name, exchange, country,
  quantity, avg_purchase_price, currency,
  first_purchase_date, notes, is_active,
  created_at, updated_at
)

transactions (
  id, holding_id, symbol, transaction_type,
  quantity, price_per_share, fees,
  transaction_date, notes, created_at
)

price_history (
  id, symbol, exchange, date,
  open, high, low, close, volume, created_at
  UNIQUE(symbol, exchange, date)
)

exchange_rates (
  id, from_currency, to_currency, rate, date, created_at
  UNIQUE(from_currency, to_currency, date)
)

portfolio_snapshots (
  id, date, total_value_cad, total_cost_cad,
  unrealized_gain_cad, value_by_country, holdings_count,
  previous_snapshot_id, change_from_previous, created_at
  UNIQUE(date)
)

ai_insights (
  id, insight_type, symbol, content,
  created_at, expires_at
)
```

---

## Development Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with API keys
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Environment Variables

**Backend (.env)**
```
DATABASE_URL=sqlite:///./data/portfolio.db
ANTHROPIC_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
ALLOWED_ORIGINS=http://localhost:5173
DEBUG=True
```

**Frontend (.env)**
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## File Structure

```
portfolio-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app entry
│   │   ├── config.py         # Settings
│   │   ├── database.py       # SQLAlchemy setup
│   │   ├── models/           # ORM models (6 files)
│   │   ├── schemas/          # Pydantic schemas (4 files)
│   │   ├── routers/          # API routes (5 files)
│   │   ├── services/         # Business logic (4 files)
│   │   └── utils/            # Helpers
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/       # React components (16 files)
│   │   ├── pages/            # Page components (4 files)
│   │   ├── hooks/            # Custom hooks (4 files)
│   │   ├── services/         # API client
│   │   └── utils/            # Formatters, constants
│   ├── package.json
│   └── .env
├── data/
│   └── portfolio.db          # SQLite database
├── CLAUDE.md                 # This file
└── README.md
```

---

## Coding Guidelines

1. **Backend**
   - Use async/await for I/O operations
   - Validate all inputs with Pydantic
   - Use Decimal for financial calculations (never float)
   - Log errors with context
   - Return appropriate HTTP status codes

2. **Frontend**
   - Use React Query for server state
   - Keep components focused and reusable
   - Handle loading and error states
   - Use formatters.js for display formatting

3. **General**
   - Keep functions small and focused
   - Write descriptive variable names
   - Add comments for complex logic
   - Test edge cases (empty portfolio, single holding, etc.)

---

## Known Issues

1. ~~**Transaction history may not be working**~~ - Fixed, FIFO calculation implemented
2. ~~**Database not initialized**~~ - Auto-initializes on startup
3. ~~**Portfolio history chart**~~ - Complete with snapshot data
4. ~~**Slow cold start loading**~~ - Fixed with price cache + request deduplication
5. **No tests** - Zero test coverage currently
6. **Import limitations** - Only BUY/SELL transactions supported; dividends skipped (planned feature)

---

## Next Actions (Priority Order)

1. ~~Initialize database and verify all tables created~~ ✅
2. ~~Test existing API endpoints work correctly~~ ✅
3. ~~Investigate and fix transaction history issues~~ ✅
4. ~~Complete portfolio value history chart~~ ✅
5. ~~Build import system (TD Direct, Wealthsimple)~~ ✅
6. **Add dividend tracking** - Import DIV transactions, dividend income reporting
7. **Add Zerodha CSV parser** - Indian broker support
8. **Tax reporting features** - Capital gains and dividend summaries by tax year
9. Add unit/integration tests

---

## References

- [yfinance documentation](https://github.com/ranaroussi/yfinance)
- [Kite Connect API](https://kite.trade/docs/connect/v3/)
- [FastAPI docs](https://fastapi.tiangolo.com/)
- [TanStack Query](https://tanstack.com/query/latest)
