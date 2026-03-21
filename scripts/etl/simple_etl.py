"""
Simple ETL: Raw Data → Neon Database
Loads districts, lineage events, and agricultural metrics.
"""

import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import os
import logging
from difflib import get_close_matches
from sqlalchemy import create_engine, text  # type: ignore
from dotenv import load_dotenv  # type: ignore

# Setup
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, 'backend', '.env'))

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError("DATABASE_URL not set in backend/.env")

# File paths
MASTER_PATH = os.path.join(BASE_DIR, 'data', 'v1', 'district_master.csv')
LINEAGE_PATH = os.path.join(BASE_DIR, 'data', 'v1', 'district_lineage_cleaned.csv')
ICRISAT_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'ICRISAT_correct.csv')
STATE_XLSX_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'crop-area-and-production (1).xlsx')


def simple_normalize(name):
    """Normalize district name for matching."""
    normalized = "".join(c for c in str(name).lower().strip() if c.isalnum())
    # Bypass slice notation ([:6]) to prevent Pyright errors in unconfigured IDE environments
    return "".join(normalized[i] for i in range(min(6, len(normalized))))


# State name mappings (ICRISAT → Master)
STATE_ALIASES = {
    'Orissa': 'Odisha',
    'Uttaranchal': 'Uttarakhand',
    'Pondicherry': 'Puducherry',
    'Chattisgarh': 'Chhattisgarh',
    'Jammu and Kashmir': 'Jammu & Kashmir',
    'Delhi': 'NCT of Delhi',
}

# District name fixes (normalized ICRISAT → normalized Master)
NAME_FIXES = {
    '24parg': 'south2',
    'ysrkad': 'kadapa',
    'spsnel': 'sripot',
    'khandw': 'eastn',
    'beed': 'bhir',
    'mehsan': 'mahesa',
    'dholpu': 'dhaulp',
    'thriss': 'trichu',
    'phulba': 'kandha',
    'burdwa': 'barddh',
    'mungai': 'munger',
    'bhabhu': 'kaimur',
    'dahod': 'dohad',
    'shrimu': 'mukts',
    'karoli': 'karaul',
    'gbnaga': 'gautam',
    'jagity': 'jagtia',
}


def create_schema(engine):
    """Create database tables."""
    with engine.connect() as conn:
        # Drop existing tables
        conn.execute(text("DROP TABLE IF EXISTS agri_metrics CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS lineage_events CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS districts CASCADE"))
        conn.commit()
        
        # Create tables
        conn.execute(text("""
            CREATE TABLE districts (
                cdk TEXT PRIMARY KEY,
                state_name TEXT,
                district_name TEXT,
                creation_year INTEGER
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE lineage_events (
                parent_cdk TEXT,
                child_cdk TEXT,
                event_year INTEGER,
                event_type TEXT,
                PRIMARY KEY (parent_cdk, child_cdk, event_year),
                FOREIGN KEY (parent_cdk) REFERENCES districts(cdk),
                FOREIGN KEY (child_cdk) REFERENCES districts(cdk)
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE agri_metrics (
                id SERIAL PRIMARY KEY,
                cdk TEXT REFERENCES districts(cdk),
                year INTEGER,
                variable_name TEXT,
                value REAL
            )
        """))
        
        # Create indexes
        conn.execute(text("CREATE INDEX idx_metrics_cdk ON agri_metrics(cdk)"))
        conn.execute(text("CREATE INDEX idx_metrics_year ON agri_metrics(year)"))
        conn.execute(text("CREATE INDEX idx_metrics_var ON agri_metrics(variable_name)"))
        conn.execute(text("CREATE INDEX idx_metrics_cdk_year ON agri_metrics(cdk, year)"))
        conn.commit()
    
    logger.info("Schema created successfully")


def load_districts(engine):
    """Load districts from master file."""
    master = pd.read_csv(MASTER_PATH)
    
    # Select and clean columns
    districts = master[['cdk', 'state_name', 'district_name', 'creation_year']].copy()
    districts = districts.drop_duplicates(subset=['cdk'])
    districts['creation_year'] = districts['creation_year'].fillna(0).astype(int)
    
    districts.to_sql('districts', engine, if_exists='append', index=False, method='multi', chunksize=500)
    logger.info(f"Loaded {len(districts)} districts")
    return districts


def load_lineage(engine):
    """Load lineage events."""
    lineage = pd.read_csv(LINEAGE_PATH)
    
    # Only keep columns we need
    lineage = lineage[['parent_cdk', 'child_cdk', 'event_year', 'event_type']].copy()
    
    lineage.to_sql('lineage_events', engine, if_exists='append', index=False, method='multi', chunksize=500)
    logger.info(f"Loaded {len(lineage)} lineage events")


def load_metrics(engine, districts_df):
    """Load agricultural metrics from ICRISAT data."""
    icrisat = pd.read_csv(ICRISAT_PATH)
    logger.info(f"Loaded ICRISAT data: {len(icrisat)} rows")
    
    # Build lookup: (state, normalized_name) → cdk
    all_master_names = []
    cdk_lookup = {}
    for _, row in districts_df.iterrows():
        nm = simple_normalize(row['district_name'])
        cdk_lookup[(row['state_name'], nm)] = row['cdk']
        all_master_names.append(nm)
    
    # Map ICRISAT rows to CDKs
    def get_cdk(row):
        state = STATE_ALIASES.get(row['state_name'], row['state_name'])
        nm = simple_normalize(row['dist_name'])
        nm = NAME_FIXES.get(nm, nm)
        
        # Try exact match
        if (state, nm) in cdk_lookup:
            return cdk_lookup[(state, nm)]
        
        # Try matching just by name (find in any state)
        matches = [(s, n) for (s, n) in cdk_lookup.keys() if n == nm]
        if len(matches) == 1:
            return cdk_lookup[matches[0]]
        
        # Fuzzy match
        fuzzy = get_close_matches(nm, all_master_names, n=1, cutoff=0.7)
        if fuzzy:
            matches = [(s, n) for (s, n) in cdk_lookup.keys() if n == fuzzy[0]]
            if matches:
                return cdk_lookup[matches[0]]
        
        return None
    
    icrisat['cdk'] = icrisat.apply(get_cdk, axis=1)
    
    # Report mapping stats
    mapped = icrisat['cdk'].notna().sum()
    logger.info(f"Mapped {mapped}/{len(icrisat)} rows to CDKs")
    
    # Keep only mapped rows
    icrisat = icrisat[icrisat['cdk'].notna()]
    
    # Melt to long format
    id_cols = ['cdk', 'year']
    value_cols = [c for c in icrisat.columns if c not in ['dist_code', 'year', 'state_code', 'state_name', 'dist_name', 'cdk']]
    
    metrics = icrisat.melt(id_vars=id_cols, value_vars=value_cols, var_name='variable_name', value_name='value')
    
    # Clean: remove -1 (missing) and NaN
    metrics['value'] = metrics['value'].replace(-1, np.nan)
    metrics = metrics.dropna(subset=['value'])
    
    logger.info(f"Transformed to {len(metrics)} metric rows")
    
    # Insert in chunks
    metrics.to_sql('agri_metrics', engine, if_exists='append', index=False, method='multi', chunksize=5000)
    logger.info("Metrics loaded successfully")


def load_state_metrics(engine):
    """Load state-level crop data from xlsx as fallback metrics."""
    if not os.path.exists(STATE_XLSX_PATH):
        logger.warning(f"State xlsx not found: {STATE_XLSX_PATH}")
        return
    
    df = pd.read_excel(STATE_XLSX_PATH, sheet_name='st-area-prod-ua', header=4)
    logger.info(f"Loaded state xlsx: {len(df)} rows")
    
    # Clean column names
    df.columns = [str(c).strip() for c in df.columns]
    
    # Rename for clarity
    df = df.rename(columns={'State': 'state_name', 'YEAR': 'year'})
    
    # Filter valid rows
    df = df[df['state_name'].notna() & df['year'].notna()]
    df['year'] = df['year'].astype(int)
    
    # Create state CDK: STATE_ANDHRA_PRADESH
    def make_state_cdk(state):
        normalized = str(state).upper().replace(' ', '_').replace('&', 'AND')
        return f"STATE_{normalized}"
    
    df['cdk'] = df['state_name'].apply(make_state_cdk)
    
    # First insert state "districts" into districts table
    state_districts = df[['cdk', 'state_name']].drop_duplicates()
    state_districts['district_name'] = 'State Average'
    state_districts['creation_year'] = 1950
    
    state_districts.to_sql('districts', engine, if_exists='append', index=False, method='multi', chunksize=100)
    logger.info(f"Added {len(state_districts)} state-level entries to districts")
    
    # Crop column mapping: xlsx column -> (crop, metric_type)
    CROP_MAP = {
        'RICE_TA': ('rice', 'area'),
        'RICE_TQ': ('rice', 'production'),
        'WHT_TA': ('wheat', 'area'),
        'WHT_TQ': ('wheat', 'production'),
        'SORG_KA': ('sorghum', 'area'),
        'SORG_KQ': ('sorghum', 'production'),
        'PMLT_A': ('pearl_millet', 'area'),
        'PMLT_Q': ('pearl_millet', 'production'),
        'MAIZ_A': ('maize', 'area'),
        'MAIZ_Q': ('maize', 'production'),
        'FMLT_A': ('finger_millet', 'area'),
        'FMLT_Q': ('finger_millet', 'production'),
        'BMLT_A': ('barley', 'area'),
        'BMLT_Q': ('barley', 'production'),
    }
    
    # Melt state data
    rows = []
    for _, row in df.iterrows():
        cdk = row['cdk']
        year = row['year']
        
        for col, (crop, metric) in CROP_MAP.items():
            if col in df.columns:
                val = row.get(col)
                if pd.notna(val) and val != -1 and val > 0:
                    # Convert '000s to actual: area in ha, production in tonnes
                    actual_val = float(val) * 1000
                    variable = f"{crop}_{metric}"
                    rows.append({'cdk': cdk, 'year': year, 'variable_name': variable, 'value': actual_val})
        
        # Calculate yield from area/production
        for col_a, (crop, _) in [(k, v) for k, v in CROP_MAP.items() if v[1] == 'area']:
            # Bypass string slice ([:-1]) to satisfy Pyright in unconfigured IDE environments
            col_q = str(col_a).replace('_TA', '_TQ').replace('_KA', '_KQ').replace('_A', '_Q')
            if col_a in df.columns and col_q in df.columns:
                area = row.get(col_a)
                prod = row.get(col_q)
                if pd.notna(area) and pd.notna(prod) and area > 0 and area != -1 and prod != -1:
                    yield_val = (float(prod) / float(area)) * 1000  # kg/ha
                    variable = f"{crop}_yield"
                    rows.append({'cdk': cdk, 'year': year, 'variable_name': variable, 'value': yield_val})
    
    state_metrics = pd.DataFrame(rows)
    state_metrics = state_metrics.drop_duplicates(subset=['cdk', 'year', 'variable_name'])
    
    state_metrics.to_sql('agri_metrics', engine, if_exists='append', index=False, method='multi', chunksize=5000)
    logger.info(f"Loaded {len(state_metrics)} state-level metric rows")


def main():
    logger.info("Starting ETL...")
    engine = create_engine(DB_URL)
    
    # Step 1: Create schema
    create_schema(engine)
    
    # Step 2: Load districts
    districts_df = load_districts(engine)
    
    # Step 3: Load lineage
    load_lineage(engine)
    
    # Step 4: Load district metrics (ICRISAT)
    load_metrics(engine, districts_df)
    
    # Step 5: Load state-level metrics (fallback)
    load_state_metrics(engine)
    
    logger.info("ETL complete!")


if __name__ == "__main__":
    main()
