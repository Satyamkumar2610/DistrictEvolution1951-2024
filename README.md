# I-ASCAP: Indian Agri-Spatial Comparative Analytics Platform

[![CI](https://github.com/Satyamkumar2610/I-ASCAP/actions/workflows/ci.yml/badge.svg)](https://github.com/Satyamkumar2610/I-ASCAP/actions/workflows/ci.yml)
[![Deploy Status](https://img.shields.io/badge/Deployment-Live-success)](https://i-ascap.onrender.com)
[![API Docs](https://img.shields.io/badge/API-Docs-blue)](https://i-ascap.onrender.com/docs)

## Overview

I-ASCAP is a research-grade geospatial platform designed to visualize and analyze the evolution of Indian agriculture at the district level. It solves the "Modifiable Areal Unit Problem" (MAUP) through a lineage-aware harmonization engine that tracks district splits and merges over 60 years.

## Data Coverage

| Source         | Years         | Metrics                        |
|----------------|---------------|--------------------------------|
| ICRISAT VDSA   | 1966 – 2017   | Crop area, yield, production   |
| Census of India| 1971, 81, 91, 2001, 2011 | Population, land use |

Coverage is uneven before 1980. Districts created after 1966 have
historical values estimated via area-weighted apportionment from
parent units. All estimates are tagged with a confidence score
visible in the district panel and the AI analyst responses.

## Key Features

### 🔬 Research-Grade Analytics
- **Lineage Tracking**: Full ancestry visualization for split districts (e.g., Adilabad → Nirmal).
- **Statistical Analysis**: CAGR, YoY growth, linear trends, and inflection point detection.
- **Uncertainty Propagation**: Confidence intervals for all apportioned data.
- **Period Comparison**: Statistical t-tests comparing pre- and post-split performance.

### 🛡️ Robust Architecture
- **Reliability**: Custom error handling, rate limiting (100 req/min), and health checks.
- **Performance**: Redis + in-memory LRU caching, database connection pooling, and Gunicorn/Uvicorn workers.
- **Security**: OWASP security headers, input sanitization, and SQL injection protection.

### 📊 Data & Export
- **Formats**: Export to CSV, JSON, and GeoJSON.
- **Validation**: Strict schema validation for years, crops, and CDKs.
- **Coverage**: 928+ districts, 60+ years, 1M+ agricultural records.

## Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 15, React 19, Tailwind CSS 3, MapLibre GL JS |
| **Backend** | FastAPI, Python 3.13, AsyncPG, NumPy/SciPy, Statsmodels |
| **Database** | PostgreSQL 15 + PostGIS (Neon Serverless) |
| **Infrastructure** | Docker, Gunicorn, GitHub Actions CI, Redis |

## Setup & Development

### Prerequisites
- Docker & Docker Compose
- Python 3.13+
- Node.js 20+

### Environment Configuration
```bash
cp .env.example .env
# Edit .env with your DATABASE_URL, MAPBOX_TOKEN, etc.
```

### Quick Start (Docker)
```bash
docker compose up --build
```
- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend**: [http://localhost:8000](http://localhost:8000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Local Development

#### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Available Commands
Run `make help` to see all available pipeline commands:
```
  clean           Remove cached/compiled files
  dev             Start backend dev server
  dev-all         Start both backend and frontend
  dev-frontend    Start frontend dev server
  format          Auto-format backend code with Ruff
  lint            Run Ruff linter on backend
  test            Run all backend tests
  test-cov        Run tests with coverage report
  typecheck       Run mypy type checking on backend
```

### Testing
```bash
make test          # Run tests
make test-cov      # Run tests with coverage
make lint          # Lint backend with Ruff
make typecheck     # Type-check with mypy
```

## API Documentation

Interactive Swagger documentation is available at `/docs`. Key endpoint groups:

| Endpoint Group | Description |
|---|---|
| `GET /api/v1/metrics/*` | Agricultural data retrieval |
| `GET /api/v1/lineage/*` | District evolution tracing |
| `GET /api/v1/analytics/*` | Advanced analytics (diversification, trends, rankings) |
| `GET /api/v1/splits/*` | Split impact analysis |
| `GET /api/v1/climate/*` | Climate correlation data |
| `GET /health` | System health check |

## Deployment

- **Backend**: Deployed on Render using Gunicorn with Uvicorn workers.
- **Frontend**: Deployed on Vercel with edge caching.
- **Database**: Hosted on Neon with connection pooling.

## Project Structure

```
├── backend/           # FastAPI application
│   ├── app/           # Main application package
│   │   ├── api/v1/    # API route handlers
│   │   ├── core/      # Core business logic
│   │   ├── models/    # Database models
│   │   ├── schemas/   # Pydantic schemas
│   │   ├── services/  # Service layer
│   │   └── repositories/  # Data access layer
│   ├── tests/         # Backend test suite
│   └── scripts/       # Utility & debug scripts
├── frontend/          # Next.js application
│   └── src/app/       # App router pages & components
├── scripts/           # ETL & data pipeline scripts
├── data/              # Data files
└── docs/              # Documentation
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License. Data sources: ICRISAT, Directorate of Economics and Statistics.
