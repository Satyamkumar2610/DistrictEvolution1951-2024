# ============================================================================
# I-ASCAP Project Makefile
# Single entry point for all pipeline operations
# ============================================================================

.PHONY: help etl ingest verify maint test lint format typecheck dev clean

# Default target
help: ## Show this help message
	@echo "I-ASCAP Pipeline Commands"
	@echo "========================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Data Pipeline
# ---------------------------------------------------------------------------
etl: ## Run the core ETL pipeline (extract, transform, load)
	python -m scripts etl

ingest: ## Run the multi-stage data ingestion pipeline
	python -m scripts ingest

etl-full: ## Run ETL + ingestion sequentially
	python -m scripts etl
	python -m scripts ingest

# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------
verify: ## Run all data verification checks
	python -m scripts verify

maint: ## Run maintenance scripts (bridge rebuild, sync splits)
	python -m scripts maint

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
dev: ## Start backend dev server
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

dev-all: ## Start both backend and frontend (requires tmux or two terminals)
	@echo "Starting backend..."
	cd backend && uvicorn app.main:app --reload --port 8000 &
	@echo "Starting frontend..."
	cd frontend && npm run dev

# ---------------------------------------------------------------------------
# Testing & Quality
# ---------------------------------------------------------------------------
test: ## Run all backend tests
	cd backend && python -m pytest tests/ -v

test-cov: ## Run tests with coverage report
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

lint: ## Run Ruff linter on backend
	cd backend && ruff check app/

format: ## Auto-format backend code with Ruff
	cd backend && ruff format app/

typecheck: ## Run mypy type checking on backend
	cd backend && mypy app/ --ignore-missing-imports

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
docker-up: ## Start all services via Docker Compose
	docker compose up -d

docker-down: ## Stop all Docker services
	docker compose down

docker-logs: ## Tail Docker logs
	docker compose logs -f

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: ## Remove cached/compiled files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
