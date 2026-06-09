"""
Extend I-ASCAP dataset with 1966-1989 historical data from ICRISAT Dataset A.

Strategy:
  - Dataset A (Apportioned) has 311 harmonized parent districts from 1966-2017
  - The existing v1.5 panel uses Dataset B (Unapportioned) from 1990-2017
  - For 1966-1989, we use Dataset A directly since all districts existed as parents
  - We map Dataset A district codes to existing CDK identifiers via the crosswalk
  - Output: Extended panel rows to be appended to the database

This script does NOT modify any existing data — it only creates NEW rows for 1966-1989.
"""

import os
import sys

import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
V1_5_DIR = os.path.join(DATA_DIR, "v1_5")

DATASET_A = os.path.join(RAW_DIR, "ICRISAT-District Level Data Unapportioned.csv")
EXISTING_PANEL = os.path.join(V1_5_DIR, "district_year_panel_v1_5.csv")
CROSSWALK = os.path.join(PROCESSED_DIR, "icrisat_crosswalk.csv")
OUTPUT = os.path.join(V1_5_DIR, "historical_extension_1966_1989.csv")


def load_data():
    """Load all required datasets."""
    a = pd.read_csv(DATASET_A)
    panel = pd.read_csv(EXISTING_PANEL, nrows=5)  # Just for column names
    crosswalk = pd.read_csv(CROSSWALK)
    return a, panel, crosswalk


def build_code_to_cdk_map(crosswalk: pd.DataFrame, panel_path: str) -> dict:
    """
    Build mapping from ICRISAT Dataset A codes to CDK identifiers.

    For each Dataset A code, find its CDK in the existing panel by matching
    the Dataset B code (which the panel was built from).
    """
    panel = pd.read_csv(panel_path)

    # Get unique (dist_code, cdk) pairs from existing panel
    panel_code_cdk = panel.drop_duplicates("dist_code")[["dist_code", "cdk"]].dropna()
    code_to_cdk = dict(zip(panel_code_cdk["dist_code"], panel_code_cdk["cdk"]))

    # For Dataset A codes that map via IDENTITY or RENAME to a B code
    a_to_cdk: dict[int, str] = {}
    for _, row in crosswalk.iterrows():
        a_code = row["icrisat_code_a"]
        b_code = row["icrisat_code_b"]
        event = row["event_type"]

        if pd.isna(a_code):
            continue

        a_code = int(a_code)

        # For IDENTITY/RENAME, the A code IS the B code
        if event in ("IDENTITY", "RENAME"):
            b_code_int = int(b_code) if pd.notna(b_code) else None
            if b_code_int and b_code_int in code_to_cdk:
                a_to_cdk[a_code] = code_to_cdk[b_code_int]

    return a_to_cdk


def normalise_columns(a: pd.DataFrame) -> pd.DataFrame:
    """
    Rename Dataset A columns to match the v1.5 panel column names.
    """
    # Build column mapping: "RICE AREA (1000 ha)" -> "rice_area"
    col_map = {
        "Dist Code": "dist_code",
        "Year": "year",
        "State Code": "state_code",
        "State Name": "state_name",
        "Dist Name": "dist_name",
    }

    for col in a.columns:
        if col in col_map:
            continue
        # Convert "RICE AREA (1000 ha)" -> "rice_area"
        lower = col.lower()
        # Remove units
        for unit in ["(1000 ha)", "(1000 tons)", "(kg per ha)"]:
            lower = lower.replace(unit, "")
        lower = lower.strip().replace(" ", "_").replace("__", "_")
        col_map[col] = lower

    return a.rename(columns=col_map)


def main():
    """Main execution."""
    print("Loading datasets...")
    a, panel_sample, crosswalk = load_data()

    # Only keep 1966-1989 from Dataset A
    historical = a[a["Year"] < 1990].copy()
    print(f"Historical records (1966-1989): {len(historical):,}")
    print(f"Year range: {historical['Year'].min()}-{historical['Year'].max()}")
    print(f"Unique districts: {historical['Dist Code'].nunique()}")

    # Build CDK mapping
    print("\nBuilding code-to-CDK mapping...")
    code_to_cdk = build_code_to_cdk_map(crosswalk, EXISTING_PANEL)
    print(f"Mapped {len(code_to_cdk)} Dataset A codes to CDK identifiers")

    # Check unmapped
    all_a_codes = set(historical["Dist Code"].unique())
    mapped_codes = set(code_to_cdk.keys())
    unmapped = all_a_codes - mapped_codes
    if unmapped:
        print(f"\n⚠️  {len(unmapped)} Dataset A codes could not be mapped to CDKs:")
        for code in sorted(unmapped):
            name = a[a["Dist Code"] == code]["Dist Name"].iloc[0]
            state = a[a["Dist Code"] == code]["State Name"].iloc[0]
            print(f"    Code {code}: {name} ({state})")

    # Normalise columns
    print("\nNormalising column names...")
    historical = normalise_columns(historical)

    # Add CDK column
    historical["cdk"] = historical["dist_code"].map(code_to_cdk)
    historical["harmonization_method"] = "Historical_DatasetA"

    # Drop rows without CDK mapping
    before = len(historical)
    historical = historical.dropna(subset=["cdk"])
    after = len(historical)
    if before != after:
        print(f"Dropped {before - after} rows without CDK mapping")

    # Ensure column order matches existing panel
    panel_cols = pd.read_csv(EXISTING_PANEL, nrows=0).columns.tolist()

    # Add any missing columns as NaN
    for col in panel_cols:
        if col not in historical.columns:
            historical[col] = None

    # Reorder to match
    historical = historical[panel_cols]

    # Replace -1 sentinels with -1 (keep consistent with existing panel)
    print(f"\nFinal historical extension: {len(historical):,} rows")
    print(f"CDKs covered: {historical['cdk'].nunique()}")
    print(f"Year range: {historical['year'].min()}-{historical['year'].max()}")

    # Save
    historical.to_csv(OUTPUT, index=False)
    print(f"\n✅ Written to: {OUTPUT}")

    # Summary stats
    print("\n── Coverage Summary ──")
    for state in sorted(historical["state_name"].unique()):
        n = historical[historical["state_name"] == state]["cdk"].nunique()
        print(f"  {state:<25} {n} districts")


if __name__ == "__main__":
    main()
