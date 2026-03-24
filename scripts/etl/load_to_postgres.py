
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import os

import logging
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, 'backend', '.env')
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    logger.info(f"Loaded env from {ENV_PATH}")
else:
    logger.warning("No backend/.env file found.")

# Config
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    logger.error("DATABASE_URL not set. Set it in backend/.env or as an environment variable.")
    raise EnvironmentError("DATABASE_URL is required. Example: postgresql://user:pass@host:5432/i_ascap")


def setup_schema(engine):
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS agri_metrics CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS districts CASCADE;"))
        conn.commit()

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS districts (
                cdk TEXT PRIMARY KEY,
                state_name TEXT,
                district_name TEXT,
                start_year INTEGER,
                end_year INTEGER
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agri_metrics (
                id SERIAL PRIMARY KEY,
                cdk TEXT NOT NULL REFERENCES districts(cdk),
                year INTEGER,
                variable_name TEXT,
                value REAL,
                source TEXT DEFAULT 'ICRISAT'
            );
        """))

        # Create indexes for common query patterns
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agri_metrics_cdk ON agri_metrics(cdk);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agri_metrics_year ON agri_metrics(year);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agri_metrics_variable ON agri_metrics(variable_name);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agri_metrics_cdk_var ON agri_metrics(cdk, variable_name);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_agri_metrics_cdk_year ON agri_metrics(cdk, year);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_districts_state ON districts(state_name);"))
        
        conn.commit()
    logger.info("Schema setup complete with indexes.")


def load_data():
    try:
        engine = create_engine(DB_URL)
        setup_schema(engine)
    except Exception as e:
        logger.error(f"Failed to connect/setup DB: {e}")
        return

    # 1. Prepare Districts Table from district_master.csv
    try:
        MASTER_PATH = os.path.join(BASE_DIR, 'data', 'v1', 'district_master.csv')
        if os.path.exists(MASTER_PATH):
            logger.info("Loading District Master...")
            master = pd.read_csv(MASTER_PATH)
            
            # Ensure cdk column exists
            if 'cdk' not in master.columns:
                logger.error("district_master.csv has no 'cdk' column!")
                return
            
            # Map master columns to schema
            col_map = {'cdk': 'cdk', 'state_name': 'state_name', 'district_name': 'district_name'}
            
            # Prefer start_year/end_year if available, else map creation/abolition
            if 'start_year' in master.columns:
                col_map['start_year'] = 'start_year'
            elif 'creation_year' in master.columns:
                col_map['creation_year'] = 'start_year'
                
            if 'end_year' in master.columns:
                col_map['end_year'] = 'end_year'
            elif 'abolition_year' in master.columns:
                col_map['abolition_year'] = 'end_year'
            
            dists = master.rename(columns=col_map)
            required_cols = ['cdk', 'state_name', 'district_name', 'start_year', 'end_year']
            for col in required_cols:
                if col not in dists.columns:
                    dists[col] = None
            dists = dists[required_cols].copy()
            dists = dists.drop_duplicates(subset=['cdk'])
            
            with engine.begin() as conn:
                dists.to_sql('districts', conn, if_exists='append', index=False, method='multi', chunksize=1000)
            logger.info(f"Loaded {len(dists)} districts.")
    except Exception as e:
        logger.error(f"Failed loading districts: {e}")
        return

    # 2. Prepare Metrics from district_year_panel_v1_5.csv (wide → long)
    try:
        PANEL_PATH = os.path.join(BASE_DIR, 'data', 'v1_5', 'district_year_panel_v1_5.csv')
        logger.info(f"Loading Harmonized Panel from {PANEL_PATH}...")
        panel = pd.read_csv(PANEL_PATH)
        
        # Keep cdk as-is (TEXT) — do NOT rename to anything else
        if 'cdk' not in panel.columns:
            logger.error("Panel CSV has no 'cdk' column!")
            return
        
        # Columns to exclude from melt (metadata columns, not metric values)
        meta_cols = {'cdk', 'year', 'dist_code', 'state_code', 'state_name', 'dist_name', 'harmonization_method'}
        value_vars = [c for c in panel.columns if c not in meta_cols]
        
        long_df = panel.melt(
            id_vars=['cdk', 'year'], 
            value_vars=value_vars, 
            var_name='variable_name', 
            value_name='value'
        )
        
        # Replace -1 sentinel with NaN, drop nulls
        long_df['value'] = long_df['value'].replace(-1, np.nan)
        long_df = long_df.dropna(subset=['value'])
        # Remove zero-value rows to save space
        long_df = long_df[long_df['value'] != 0]
        
        logger.info(f"Transformed to {len(long_df)} rows.")
        long_df['source'] = 'V1.5_Harmonized'
        
        with engine.begin() as conn:
            long_df.to_sql('agri_metrics', conn, if_exists='append', index=False, method='multi', chunksize=5000)
        logger.info("Metrics Loaded.")
    except Exception as e:
        logger.error(f"Failed loading metrics: {e}")

if __name__ == "__main__":
    load_data()
