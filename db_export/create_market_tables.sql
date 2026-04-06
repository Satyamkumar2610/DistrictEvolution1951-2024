-- I-ASCAP: Mandi Prices & MSP Tables
-- Run this on Neon PostgreSQL to create market data tables

-- =============================================================================
-- MANDI PRICES TABLE — Daily commodity prices from mandis across India
-- Source: data.gov.in (Ministry of Agriculture)
-- =============================================================================

CREATE TABLE IF NOT EXISTS mandi_prices (
    id SERIAL PRIMARY KEY,
    state VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    market VARCHAR(200),
    commodity VARCHAR(200) NOT NULL,
    commodity_normalized VARCHAR(100),
    variety VARCHAR(200),
    grade VARCHAR(100),
    arrival_date DATE NOT NULL,
    min_price DECIMAL(12,2),
    max_price DECIMAL(12,2),
    modal_price DECIMAL(12,2) NOT NULL,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state, district, market, commodity, variety, arrival_date)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_mandi_state ON mandi_prices(state);
CREATE INDEX IF NOT EXISTS idx_mandi_district ON mandi_prices(district);
CREATE INDEX IF NOT EXISTS idx_mandi_commodity ON mandi_prices(commodity_normalized);
CREATE INDEX IF NOT EXISTS idx_mandi_date ON mandi_prices(arrival_date);
CREATE INDEX IF NOT EXISTS idx_mandi_state_commodity ON mandi_prices(state, commodity_normalized);
CREATE INDEX IF NOT EXISTS idx_mandi_state_district ON mandi_prices(state, district);

-- =============================================================================
-- MSP RATES TABLE — Official Minimum Support Prices from CACP
-- =============================================================================

CREATE TABLE IF NOT EXISTS msp_rates (
    id SERIAL PRIMARY KEY,
    crop VARCHAR(50) NOT NULL,
    season VARCHAR(20) NOT NULL,
    year INTEGER NOT NULL,
    msp_price DECIMAL(10,2) NOT NULL,
    grade VARCHAR(50),
    unit VARCHAR(20) DEFAULT 'INR/quintal',
    source VARCHAR(100) DEFAULT 'CACP (Commission for Agricultural Costs & Prices)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(crop, season, year)
);

CREATE INDEX IF NOT EXISTS idx_msp_crop ON msp_rates(crop);
CREATE INDEX IF NOT EXISTS idx_msp_year ON msp_rates(year);
CREATE INDEX IF NOT EXISTS idx_msp_crop_year ON msp_rates(crop, year);

-- =============================================================================
-- ANALYZE
-- =============================================================================

ANALYZE mandi_prices;
ANALYZE msp_rates;

-- =============================================================================
-- VERIFY
-- =============================================================================

SELECT 'mandi_prices' as table_name, COUNT(*) as row_count FROM mandi_prices
UNION ALL
SELECT 'msp_rates', COUNT(*) FROM msp_rates;
