"""
Unified Name Resolver for district name matching.

Single source of truth for district name normalization and alias resolution.
Used by both the ETL pipeline and the backend API — no inline exceptions.
"""

# ──────────────────────────────────────────────────────────────
# Canonical alias map (old / variant → normalized modern name)
# ──────────────────────────────────────────────────────────────
_ALIASES: dict[str, str] = {
    # Karnataka
    "bangalore": "bengaluru urban",
    "bangalore rural": "bengaluru rural",
    "belgaum": "belagavi",
    "bellary": "ballari",
    "bijapur": "vijayapura",
    "chikmagalur": "chikkamagaluru",
    "gulbarga": "kalaburagi",
    "mysore": "mysuru",
    "shimoga": "shivamogga",
    "tumkur": "tumakuru",
    # Uttar Pradesh
    "allahabad": "prayagraj",
    "faizabad": "ayodhya",
    # Madhya Pradesh
    "hoshangabad": "narmadapuram",
    "west nimar": "khargone",
    "nimar": "khargone",
    # Chhattisgarh
    "koriya": "korea",
    "dakshin bastar dantewada": "dantewada",
    # Rajasthan
    "chittaurgarh": "chittorgarh",
    # Bihar / Jharkhand
    "purnea": "purnia",
    "monghyr": "munger",
    "giridh": "giridih",
    "hazaribag": "hazaribagh",
    "sahibganj": "sahebganj",
    "champaran": "purbi champaran",
    "shahabad": "rohtas",
    "purba champaran": "purbi champaran",
    "pashchim champaran": "west champaran",
    # Jammu & Kashmir / Ladakh
    "baramula": "baramulla",
    "punch": "poonch",
    # Andhra Pradesh / Telangana
    "anantapuramu": "anantapur",
    "srikakulum": "srikakulam",
    "visakhapatnam": "visakhapatanam",
    "drbrambedkarkonaseema": "konaseema",
    "ypsr": "ysr",
    # Assam
    "kokrajihar": "kokrajhar",
    "nalbali": "nalbari",
    "sibsagar": "sivasagar",
    # Tamil Nadu
    "tiruchchirappalli": "tiruchirappalli",
    "tiruchirapalli": "tiruchirappalli",
    "kancheepuram": "kanchipuram",
    # Haryana
    "gurgaon": "gurugram",
    # Kerala
    "cannanore": "kannur",
    "quilon": "kollam",
    "trichur": "thrissur",
    "palghat": "palakkad",
    "alleppey": "alappuzha",
    # Maharashtra
    "greater bombay": "mumbai",
    # Himachal
    "simla": "shimla",
    "lahaul and spiti": "lahul and spiti",
    # Telangana special
    "rangareddi": "rangareddy",
    "jayashankar bhupalpally": "jayashankar bhupalapally",
    "raj nandgaon": "rajnandgaon",
    "dakshina kannad": "dakshina kannada",
    "darjiling": "darjeeling",
    # Common Historical / City Aliases (moved from MappingService)
    "bombay": "mumbai",
    "madras": "chennai",
    "calcutta": "kolkata",
    "trivandrum": "thiruvananthapuram",
    "calicut": "kozhikode",
    "cochin": "kochi",
    "baroda": "vadodara",
    "poona": "pune",
    "pondicherry": "puducherry",
    "ooty": "nilgiris",
    "vizag": "visakhapatnam",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    # ICRISAT Aliases
    "ahmedabad": "ahmadabad",
    "amarawati": "amravati",
    "balasore": "baleshwar",
    "bhatinda": "bathinda",
    "bijapur / vijayapura": "vijayapura",
    "bolangir": "balangir",
    "burdwan": "purba bardhaman",
    "chickmagalur": "chikkamagaluru",
    "dangs": "dang",
    "eranakulam": "ernakulam",
    "garhwal": "pauri garhwal",
    "gulbarga / kalaburagi": "kalaburagi",
    "hissar": "hisar",
    "kadapa ysr": "y.s.r.",
    "kanyakumari": "kanniyakumari",
    "keonjhar": "kendujhar",
    "khandwa / east nimar": "east nimar",
    "kutch": "kachchh",
    "mayurbhanja": "mayurbhanj",
    "mehsana": "mahesana",
    "midnapur": "medinipur west",
    "mirzpur": "mirzapur",
    "mungair": "munger",
    "nasik": "nashik",
    "north arcot / vellore": "vellore",
    "north cachar hil / dima hasao": "dima hasao",
    "phulbani ( kandhamal )": "kandhamal",
    "rae-bareily": "rae bareli",
    "roopnagar / ropar": "rupnagar",
    "s.p.s. nellore": "spsr nellore",
    "santhal paragana / dumka": "dumka",
    "shahabad (now part of bhojpur district)": "bhojpur",
    "shimoge": "shivamogga",
    "singhbhum": "west singhbhum",
    "south arcot / cuddalore": "cuddalore",
    "swami madhopur": "sawai madhopur",
    "west dinajpur": "dinajpur uttar",
    "yeotmal": "yavatmal",

}

# States that changed names or were reorganised
_STATE_ALIASES: dict[str, list] = {
    "andhra pradesh-telangana": ["telangana", "andhra pradesh"],
    "daman and diu": ["the dadra and nagar haveli and daman and diu"],
    "orissa": ["odisha"],
    "uttaranchal": ["uttarakhand"],
}

_TELANGANA_DISTRICTS = {
    "adilabad", "karimnagar", "warangal", "khammam", "nalgonda",
    "medak", "nizamabad", "rangareddy", "rangareddi", "mahabubnagar",
    "hyderabad",
}


def normalize(name: str) -> str:
    """Normalize a district / state name to lowercase stripped form."""
    if not isinstance(name, str):
        return ""
    return name.lower().strip()


def resolve_alias(name: str) -> str:
    """Resolve a name through the canonical alias map."""
    n = normalize(name)
    return _ALIASES.get(n, n)


def resolve_lgd(
    district_name: str,
    state_name: str,
    lgd_lookup: dict[tuple, int],
) -> int | None:
    """
    Multi-strategy LGD resolution.

    Strategies tried in order:
      1. Direct match  (district, state)
      2. Alias-corrected match
      3. State alias expansion  (e.g. "Andhra Pradesh-Telangana")
      4. Telangana cross-lookup (AP parent → Telangana child)
      5. Prefix match  (first 5 chars)

    ``lgd_lookup`` must be  {(district_lower, state_lower): lgd_code}
    """
    dn = normalize(district_name)
    sn = normalize(state_name)

    # 1. Direct
    lgd = lgd_lookup.get((dn, sn))
    if lgd:
        return lgd

    # 2. Alias
    corrected = resolve_alias(district_name)
    lgd = lgd_lookup.get((corrected, sn))
    if lgd:
        return lgd

    # 3. State alias
    for alias_key, alt_states in _STATE_ALIASES.items():
        if alias_key in sn:
            for alt in alt_states:
                lgd = lgd_lookup.get(
                    (dn, alt)) or lgd_lookup.get(
                    (corrected, alt))
                if lgd:
                    return lgd

    # 4. Telangana
    if dn in _TELANGANA_DISTRICTS and "andhra" in sn:
        lgd = lgd_lookup.get(
            (dn, "telangana")) or lgd_lookup.get(
            (corrected, "telangana"))
        if lgd:
            return lgd

    # 5. Prefix
    if len(dn) >= 5:
        for (d, s), code in lgd_lookup.items():
            if s == sn and d[:5] == dn[:5]:
                return code

    return None
