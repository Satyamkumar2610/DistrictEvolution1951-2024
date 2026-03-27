#!/bin/bash
# Migration script to import data into Neon DB
# Usage: DATABASE_URL="postgresql://..." ./migrate_to_neon.sh

NEON_URL="${DATABASE_URL:?ERROR: DATABASE_URL environment variable is not set}"

EXPORT_DIR="$(dirname "$0")"

echo "=== Migrating data to Neon DB ==="

# Step 1: Create schema
echo "1. Creating schema..."
psql "$NEON_URL" -f "$EXPORT_DIR/schema.sql"

# Step 2: Import districts
echo "2. Importing districts (928 rows)..."
psql "$NEON_URL" -f "$EXPORT_DIR/districts.sql"

# Step 3: Import agri_metrics (this may take a few minutes)
echo "3. Importing agri_metrics (1M+ rows - this will take a few minutes)..."
psql "$NEON_URL" -f "$EXPORT_DIR/agri_metrics.sql"

# Verify
echo "4. Verifying import..."
psql "$NEON_URL" -c "SELECT 'districts' as table_name, COUNT(*) FROM districts UNION ALL SELECT 'agri_metrics', COUNT(*) FROM agri_metrics;"

echo "=== Migration complete! ==="
