# I-ASCAP: Indian Agri-Spatial Comparative Analytics Platform

[![Deploy Status](https://img.shields.io/badge/Deployment-Live-success)](https://i-ascap.onrender.com)
[![Documentation](https://img.shields.io/badge/API-Docs-blue)](https://i-ascap.onrender.com/docs)

## Overview
I-ASCAP is a research-grade geospatial platform designed to visualize and analyze the evolution of Indian agriculture at the district level from 1966 to 2024. It solves the "Modifiable Areal Unit Problem" (MAUP) through a lineage-aware harmonization engine that tracks district splits and merges over 60 years.

## Key Features

### 🔬 Research-Grade Analytics
- **Lineage Tracking**: Full ancestry visualization for split districts (e.g., Adilabad → Nirmal).
- **Statistical Analysis**: CAGR, YoY growth, linear trends, and inflection point detection.
- **Uncertainty Propagation**: Confidence intervals for all apportioned data.
- **Period Comparison**: Statistical t-tests comparing pre- and post-split performance.

### 🛡️ Robust Architecture
- **Reliability**: Custom error handling, rate limiting (60 req/min), and health checks.
- **Performance**: In-memory LRU caching, database connection pooling, and Gunicorn/Uvicorn workers.
- **Security**: OWASP security headers, input sanitization, and SQL injection protection.

### 📊 Data & Export
- **Formats**: Export to CSV, JSON, and GeoJSON.
- **Validation**: Strict schema validation for years, crops, and CDKs.
- **Coverage**: 928+ districts, 60+ years, 1M+ agricultural records.

## Technology Stack

- **Frontend**: Next.js 14, React 18, Tailwind CSS, Mapbox GL JS (Optimized for Vercel).
- **Backend**: FastAPI, Python 3.11, AsyncPG, NumPy/SciPy (Optimized for Render).
- **Database**: PostgreSQL 15 + PostGIS (Neon Serverless).
- **Infrastructure**: Docker, Gunicorn, GitHub Actions.

## Setup & Development

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### Quick Start (Docker - Local Dev)
```bash
docker-compose up --build
```
- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
*(Requires `.env` file with `DATABASE_URL`)*

### Live Production
- **Frontend**: [https://i-ascap.onrender.com](https://i-ascap.onrender.com) (or Vercel URL)
- **API Docs**: [https://i-ascap.onrender.com/docs](https://i-ascap.onrender.com/docs)

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

### Testing
Run the comprehensive test suite:
```bash
cd backend
pytest tests/ -v
```

## API Documentation
Interactive Swagger documentation is available at `/docs`.
Key endpoints:
- `GET /metrics`: Retrieve agricultural data
- `GET /lineage`: Trace district evolution
- `GET /analysis`: Perform split impact analysis
- `GET /export`: Download datasets
- `GET /stats`: System health and metrics

## Deployment
- **Backend**: Deployed on Render using `gunicorn` with Uvicorn workers.
- **Frontend**: Deployed on Vercel with edge caching.
- **Database**: Hosted on Neon with connection pooling.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
MIT License. Data sources: ICRISAT, Directorate of Economics and Statistics.

