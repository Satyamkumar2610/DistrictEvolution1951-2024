#!/bin/bash
set -e

# =============================================================================
# I-ASCAP Data Seed Script
# Runs migrations, loads boundaries, transitions, and metrics.
# =============================================================================

# Source data locations — nothing in git, everything pulled/referenced here
ICRISAT_CSV="${ICRISAT_CSV:-./raw_data/icrisat_district_data.csv}"
BOUNDARY_GEOJSON="${BOUNDARY_GEOJSON:-./raw_data/india_districts.geojson}"

echo "=== I-ASCAP Seed Pipeline ==="
echo ""

echo "[1/4] Running migrations..."
alembic upgrade head
echo "  ✓ Migrations applied"

echo "[2/4] Loading boundaries..."
python pipeline/load_boundaries.py --source "$BOUNDARY_GEOJSON"
echo "  ✓ Boundaries loaded"

echo "[3/4] Loading admin transitions..."
python pipeline/load_transitions.py
echo "  ✓ Transitions loaded"

echo "[4/4] Loading metrics (with harmonization)..."
python pipeline/ingest.py --source "$ICRISAT_CSV"
echo "  ✓ Metrics ingested"

echo ""
echo "=== Done. Database is ready. ==="
