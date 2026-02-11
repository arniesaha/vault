# 🔒 Vault

**Your Investment Portfolio, Unified.**

A modern, multi-market investment portfolio tracker with real-time prices, currency conversion, and comprehensive analytics. Track stocks from Canadian (TSX), US (NYSE/NASDAQ), and Indian (NSE/BSE) markets, plus mutual funds and fixed deposits — all in one place.

## ✨ Features

- **🌍 Multi-Market Support** — Track stocks from TSX, NYSE, NASDAQ, NSE, and BSE
- **📈 Real-Time Prices** — Live price updates via Yahoo Finance with smart caching
- **💱 Currency Conversion** — Automatic CAD/USD/INR conversion with live exchange rates
- **🏦 Account Types** — TFSA, RRSP, FHSA, DEMAT, NRO, and more with tax-advantaged tracking
- **📊 Portfolio Analytics** — Geographic allocation, exchange breakdown, unrealized/realized gains
- **📥 Import Support** — Import from Kite (Zerodha), Groww, and TD Direct CSV exports
- **📅 Daily Snapshots** — Track portfolio value history over time
- **🌙 Dark Mode** — Full dark mode support with Navy/Gold fintech theme
- **🔐 Privacy Mode** — Hide sensitive numbers with one click

## 🎨 Design

Vault uses a professional fintech design language:
- **Navy Blue** (#1e3a8a) — Trust & security
- **Warm Gold** (amber) — Premium accents
- **IBM Plex Sans** — Industry-standard fintech typography

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      React Frontend                             │
│              (Vite + TailwindCSS + Recharts)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│                    (Python + SQLAlchemy)                        │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│    SQLite     │    │ Yahoo Finance │    │ Exchange Rate │
│  (holdings)   │    │   (prices)    │    │     API       │
└───────────────┘    └───────────────┘    └───────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional, for containerized deployment)

### Local Development

1. Clone and set up backend:

```bash
git clone https://github.com/arniesaha/vault.git
cd vault/backend

python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

uvicorn app.main:app --reload
```

2. Set up frontend:

```bash
cd ../frontend
npm install
npm run dev
```

3. Open http://localhost:5173

### Docker Deployment

```bash
# Build images
docker build -t vault-backend:latest -f backend/Dockerfile backend/
docker build -t vault-frontend:latest -f frontend/Dockerfile frontend/

# Run with compose
docker compose up -d
```

## 📡 API Endpoints

### Holdings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/holdings/` | List all holdings |
| POST | `/api/v1/holdings/` | Create a holding |
| PUT | `/api/v1/holdings/{id}` | Update a holding |
| DELETE | `/api/v1/holdings/{id}` | Delete a holding |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/portfolio/summary` | Portfolio summary with gains |
| GET | `/api/v1/analytics/allocation` | Geographic and exchange allocation |
| GET | `/api/v1/analytics/account-breakdown` | Breakdown by account type |
| GET | `/api/v1/analytics/realized-gains` | Realized gains from sales |
| GET | `/api/v1/analytics/exchange-rates` | Current exchange rates |

### Imports

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/import/kite` | Import Kite (Zerodha) xlsx |
| POST | `/api/v1/import/groww` | Import Groww mutual fund xlsx |
| POST | `/api/v1/import/upload/preview` | Preview CSV import |

## 🏦 Supported Account Types

| Type | Tax Status | Description |
|------|------------|-------------|
| TFSA | Tax-Free | Tax-Free Savings Account (Canada) |
| RRSP | Tax-Deferred | Registered Retirement Savings Plan |
| FHSA | Tax-Free | First Home Savings Account |
| DEMAT | Taxable | Indian stock demat account |
| MF_INDIA | Taxable | Indian mutual funds |
| FD_INDIA | Taxable | Indian fixed deposits |
| PPF_INDIA | Tax-Free | Public Provident Fund |
| NON_REG | Taxable | Non-registered/taxable account |

## ⚙️ Configuration

### Environment Variables

```bash
# Backend
DATABASE_URL=sqlite:///./data/portfolio.db
ALLOWED_ORIGINS=http://localhost:5173,http://your-domain.com

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 🛠️ Tech Stack

**Backend:**
- FastAPI
- SQLAlchemy
- yfinance (Yahoo Finance API)
- pandas (data processing)

**Frontend:**
- React 18
- Vite
- TailwindCSS
- Recharts (charts)
- React Query (data fetching)

## 📄 License

MIT

## 👤 Author

[Arnab Saha](https://github.com/arniesaha)
