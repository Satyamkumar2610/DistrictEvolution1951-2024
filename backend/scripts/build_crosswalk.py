"""
Build ICRISAT Crosswalk Table
Maps Dataset A (Apportioned, 311 districts) codes to Dataset B (Unapportioned, 602 districts) codes.
Detects split events, renames, and state changes.
"""

import csv
import pandas as pd

DATA_DIR = "/Users/satyamkumar/Desktop/DistrictEvolution/data/raw"

A = pd.read_csv(f"{DATA_DIR}/ICRISAT-District Level Data.csv")
B = pd.read_csv(f"{DATA_DIR}/ICRISAT-District Level Data Unapportioned.csv")

# Normalise names for matching
def norm(name: str) -> str:
    return name.strip().upper().replace("  ", " ")

# Build lookup tables
a_info = A.drop_duplicates("Dist Code")[["Dist Code", "Dist Name", "State Code", "State Name"]].copy()
b_info = B.drop_duplicates("Dist Code")[["Dist Code", "Dist Name", "State Code", "State Name"]].copy()

a_code_to_name = dict(zip(a_info["Dist Code"], a_info["Dist Name"]))
a_code_to_state = dict(zip(a_info["Dist Code"], a_info["State Name"]))

b_code_to_name = dict(zip(b_info["Dist Code"], b_info["Dist Name"]))
b_code_to_state = dict(zip(b_info["Dist Code"], b_info["State Name"]))

# Detect first year with real data for each B district
def first_real_year(dist_code: int) -> int | None:
    """Find the first year a district has non-sentinel data in Dataset B."""
    subset = B[B["Dist Code"] == dist_code].sort_values("Year")
    yield_cols = [c for c in B.columns if "YIELD" in c or "AREA" in c or "PRODUCTION" in c]
    for _, row in subset.iterrows():
        # A row has real data if at least one non-sentinel numeric value exists
        vals = [row[c] for c in yield_cols if row[c] != -1 and row[c] != 0]
        if vals:
            return int(row["Year"])
    return None

# Build B lookup by state
b_by_state: dict[str, list[dict]] = {}
for _, r in b_info.iterrows():
    state = r["State Name"]
    if state not in b_by_state:
        b_by_state[state] = []
    first_yr = first_real_year(r["Dist Code"])
    b_by_state[state].append({
        "code": r["Dist Code"],
        "name": r["Dist Name"],
        "first_year": first_yr,
    })

# Common codes (direct mapping)
common_codes = set(a_info["Dist Code"]) & set(b_info["Dist Code"])
a_only_codes = set(a_info["Dist Code"]) - set(b_info["Dist Code"])
b_only_codes = set(b_info["Dist Code"]) - set(a_info["Dist Code"])

crosswalk = []

# 1. Map common codes (IDENTITY or RENAME)
for code in sorted(common_codes):
    a_name = a_code_to_name[code]
    b_name = b_code_to_name[code]
    a_state = a_code_to_state[code]
    b_state = b_code_to_state[code]
    
    event = "IDENTITY"
    if norm(a_name) != norm(b_name):
        event = "RENAME"
    
    crosswalk.append({
        "icrisat_code_a": code,
        "icrisat_code_b": code,
        "parent_name": a_name,
        "child_name": b_name,
        "state": b_state,
        "split_year": None,
        "event_type": event,
        "confidence": 1.0,
    })

# 2. Map A-only codes (districts that exist in A but not B)
for code in sorted(a_only_codes):
    a_name = a_code_to_name[code]
    a_state = a_code_to_state[code]
    crosswalk.append({
        "icrisat_code_a": code,
        "icrisat_code_b": None,
        "parent_name": a_name,
        "child_name": None,
        "state": a_state,
        "split_year": None,
        "event_type": "A_ONLY",
        "confidence": 0.5,
    })

# 3. Map B-only codes as SPLIT children of A parents
# Use state + first_real_year heuristic + naming patterns
telangana_lineage = {
    63: [2101, 2102, 2103],          # Adilabad → Kumurambheem, Mancherial, Nirmal
    62: [2104, 2105, 2106],          # Karimnagar → Jagityal, Peddapally, Rajanna Siricilla
    61: [2107],                       # Khammam → Bhadradri
    58: [2108, 2109, 2110, 2122],    # Mahabubnagar → Jogulamba, Nagarkurnool, Wanaparthy, Narayanpet
    57: [2115, 2111, 2112],          # Medak → Kamareddy, Sangareddy, Siddipet
    59: [2113, 2114],                 # Nalgonda → Suryapet, Yadadri Bhuvanagiri
    60: [2119, 2118, 2121, 2120, 2123], # Warangal → Jangaon, Jayashankar, Mahabubabad, Warangal Urban, Mulugu
    55: [2116],                       # Hyderabad → Malkaigiri
    # Nizamabad (56) → no split detected
}

# Rangareddy (520 in B, not in A) → Vikarabad (2117)
# Rangareddy itself is a B-only code that was likely split from Hyderabad pre-1990

for parent_code, child_codes in telangana_lineage.items():
    for child_code in child_codes:
        child_name = b_code_to_name.get(child_code, "Unknown")
        first_yr = first_real_year(child_code)
        crosswalk.append({
            "icrisat_code_a": parent_code,
            "icrisat_code_b": child_code,
            "parent_name": a_code_to_name[parent_code],
            "child_name": child_name,
            "state": "Telangana",
            "split_year": first_yr,
            "event_type": "SPLIT",
            "confidence": 1.0,
        })

# For remaining B-only codes, mark them as NEW_DISTRICT (split child, parent unknown or needs manual mapping)
mapped_b_codes = {r["icrisat_code_b"] for r in crosswalk if r["icrisat_code_b"] is not None}
for code in sorted(b_only_codes):
    if code in mapped_b_codes:
        continue
    b_name = b_code_to_name[code]
    b_state = b_code_to_state[code]
    first_yr = first_real_year(code)
    crosswalk.append({
        "icrisat_code_a": None,
        "icrisat_code_b": code,
        "parent_name": None,
        "child_name": b_name,
        "state": b_state,
        "split_year": first_yr,
        "event_type": "NEW_DISTRICT",
        "confidence": 0.7,
    })

# Write crosswalk
output_path = "/Users/satyamkumar/Desktop/DistrictEvolution/data/processed/icrisat_crosswalk.csv"
df = pd.DataFrame(crosswalk)
df.to_csv(output_path, index=False)

# Summary
print(f"Crosswalk built: {len(df)} entries")
print(f"  IDENTITY:      {(df['event_type']=='IDENTITY').sum()}")
print(f"  RENAME:        {(df['event_type']=='RENAME').sum()}")
print(f"  SPLIT:         {(df['event_type']=='SPLIT').sum()}")
print(f"  A_ONLY:        {(df['event_type']=='A_ONLY').sum()}")
print(f"  NEW_DISTRICT:  {(df['event_type']=='NEW_DISTRICT').sum()}")
print(f"\nWritten to: {output_path}")

