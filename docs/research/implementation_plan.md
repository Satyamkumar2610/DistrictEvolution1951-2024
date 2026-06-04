# Validation & Evaluation Framework Implementation Plan

## Goal Description
The objective is to produce scientific evidence that the newly implemented Lineage-Aware Architecture mathematically preserves data integrity (area, production, and yield) across district boundaries over time. We will also implement advanced Spatial Data Science research metrics to quantify administrative volatility for publication readiness.

## User Review Required
> [!WARNING]
> **Schema Correction Required:** My investigation revealed that the database schema uses `cdk` (string) for joins, whereas some existing backend code (like `metric_repo.py` and the Lineage API I just added) attempted to use `lgd_code` (integer). I must patch these queries first to ensure the aggregation engines and validation scripts actually run.

## Proposed Changes

### 1. Schema Patches & Bug Fixes
- **`backend/app/repositories/metric_repo.py`**: Fix the Bottom-Up Aggregation query to join on `cdk` and `parent_district`/`child_district` names instead of `lgd_code`.
- **`backend/app/api/v1/districts.py`**: Fix the Lineage API to correctly query `district_splits` using district names rather than casting `cdk` to integer.

### 2. Validation Reports Generation (A, B, C, D)
- **NEW SCRIPT:** `backend/scripts/generate_validation_framework.py`
- This script will generate the requested evidence:
  - **A. Completeness Report:** Count total districts, orphans, and lineage link coverage.
  - **B. Aggregation Accuracy Report:** Perform a checksum on parent total vs sum of children for 2017 to verify zero data loss.
  - **C. Temporal Consistency Report:** Flag time-series that cross split-events without aggregation.
  - **D. Split Impact Quantification:** Extract exact Area, Production, and Yield differences before and after splits.
- The output of this script will be saved as an artifact for your review.

### 3. Research Metrics Engine (E)
- **NEW FILE:** `backend/app/analytics/lineage_metrics.py`
- Implement the following algorithms:
  - **District Stability Index:** `(Years without split) / (Total Years Active)`
  - **Boundary Volatility Index:** Frequency of splits per state per decade.
  - **Administrative Fragmentation Index:** `(Total modern children) / 1 (historical parent)`
  - **Lineage Depth Score:** Maximum depth of the DAG for a given root district.
- **MODIFY:** `backend/app/api/v1/analytics.py` to expose `GET /api/v1/analytics/lineage-metrics`.

## Verification Plan

### Automated Verification
- The `generate_validation_framework.py` script will mathematically assert that `Sum(Children_Area) == Parent_Area` (within float tolerance). If it fails, the script will panic and log the exact district causing the leak.

### Publication Readiness Assessment (F)
- After the metrics are implemented and the checksums pass, I will provide a dedicated section in the `walkthrough.md` detailing if the results meet the rigor required for your SRIP final report and journal publication.
