
"""
Name matching utilities for district resolution.
"""

# Normalized corrections map
NAME_CORRECTIONS = {
    # Spelling variants
    "anantapuramu": "anantapur", "srikakulum": "srikakulam",
    "visakhapatnam": "visakhapatanam", "kokrajihar": "kokrajhar",
    "nalbali": "nalbari", "sibsagar": "sivasagar",
    "purnea": "purnia", "monghyr": "munger",
    "chittaurgarh": "chittorgarh", "darjiling": "darjeeling",
    "giridh": "giridih", "hazaribag": "hazaribagh",
    "sahibganj": "sahebganj", "baramula": "baramulla",
    "dakshina kannad": "dakshina kannada",
    "jayashankar bhupalpally": "jayashankar bhupalapally",
    "tiruchchirappalli": "tiruchirappalli",
    "tiruchirapalli": "tiruchirappalli",
    "kancheepuram": "kanchipuram",
    "dakshin bastar dantewada": "dantewada",
    "raj nandgaon": "rajnandgaon",
    "purba champaran": "purbi champaran",
    "pashchim champaran": "west champaran",
    # Renamed districts
    "gurgaon": "gurugram", "bangalore": "bengaluru urban",
    "bangalore rural": "bengaluru rural", "bijapur": "vijayapura",
    "gulbarga": "kalaburagi", "mysore": "mysuru",
    "belgaum": "belagavi", "bellary": "ballari",
    "hoshangabad": "narmadapuram", "allahabad": "prayagraj",
    "faizabad": "ayodhya", "cannanore": "kannur",
    "quilon": "kollam", "trichur": "thrissur",
    "palghat": "palakkad",
    # Historical/composite names (map to first split child if existing)
    "champaran": "purbi champaran", "shahabad": "rohtas",
    "greater bombay": "mumbai", "west nimar": "khargone",
    "nimar": "khargone", "simla": "shimla",
    "lahaul and spiti": "lahul and spiti",
    "alleppey": "alappuzha",
    # Advanced mapped aliases
    "nicobar": "nicobars",
    "north & middle andaman": "north and middle andaman",
    "south andaman": "south andamans",
    "lepa - rada": "leparada",
    "pakke-kesang": "pakke kessang",
    "shi-yomi": "shi yomi",
    "subansiri": "upper subansiri",
    "dhuburi": "dhubri",
    "kamrup metropolitan": "kamrup metro",
    "south salmara-mankachar": "south salmara mancachar",
    "gaurela-pendra-marwahi": "gaurella pendra marwahi",
    "ahmedabad": "ahmadabad",
    "aravalli": "arvalli",
    "chhota udepur": "chhotaudepur",
    "mehsana": "mahesana",
    "charkhi dadri": "charki dadri",
    "kulu": "kullu",
    "badgam": "budgam",
    "bandipore": "bandipora",
    "rajauri": "rajouri",
    "shupiyan": "shopian",
    "kodarma": "koderma",
    "pakaur": "pakur",
    "saraikela-kharsawan": "saraikela kharsawan",
    "singhbhum": "west singhbhum",
    "bagalkot": "bagalkote",
    "chamarajanagar": "chamarajanagara",
    "davanagere": "davangere",
    "vijayanagara": "vijayanagar",
    "kasargod": "kasaragod",
    "agar-malwa": "agar malwa",
    "annupur": "anuppur",
    "narsimhapur": "narsinghpur",
    "gondiya": "gondia",
    "mumbai": "mumbai suburban",
    "garo hills": "west garo hills",
    "jaintia hills": "west jaintia hills",
    "hnathial": "hnahthial",
    "tseminyü": "tseminyu",
    "baudh": "boudh",
    "debagarh": "deogarh",
    "nabarangapur": "nabarangpur",
    "sonapur": "sonepur",
    "bhatinda": "bathinda",
    "firozpur": "ferozepur",
    "sahibzada ajit singh nagar": "shahid bhagat singh nagar",
    "dhaulpur": "dholpur",
    "chengalpattu mgr": "chengalpattu",
    "dindigul anna": "dindigul",
    "tirupattur": "tirupathur",
    "viluppuram": "villupuram",
    "jagtial": "jagitial",
    "jangaon": "jangoan",
    "mahbubnagar": "mahabubnagar",
    "medchal–malkajgiri": "medchal malkajgiri",
    "rangareddi": "ranga reddy",
    "rangareddy": "ranga reddy",
    "sipahijala": "sepahijala",
    "etawah'": "etawah",
    "kanpur": "jaunpur",
    "kanshiram nagar": "kushi nagar",
    "kushinagar": "kushi nagar",
    "sant kabir nagar": "sant kabeer nagar",
    "shrawasti": "shravasti",
    "siddharthnagar": "siddharth nagar",
    "rudraprayag": "rudra prayag",
    "udham singh nagar": "udam singh nagar",
    "medinipur": "medinipur west",
    "pashchim barddhaman": "paschim bardhaman",
    "purba barddhaman": "purba bardhaman",
    "dr. b. r. ambedkar konaseema": "konaseema",
    "nellore": "spsr nellore",
    "sri potti sriramulu nellore": "spsr nellore",
    "balipara frontier tract": "west kameng",
    "mikir hills": "karbi anglong",
    "north cachar hills": "dima hasao",
    "punch": "poonch",
    "pashchimi singhbhum": "west singhbhum",
    "purbi singhbhum": "east singhbhum",
    "phulabani": "kandhamal",
    "muktsar": "sri muktsar sahib",
    "nawanshahr": "shahid bhagat singh nagar",
    "ropar": "rupnagar",
    "kamarajar": "virudhunagar",
    "north arcot": "vellore",
    "periyar": "erode",
    "south arcot": "cuddalore",
    "tirunelveli kattabomman": "tirunelveli",
    "kumuram bheem": "komaram bheem asifabad",
    "warangal rural": "warangal",
    "jyotiba phule nagar": "amroha",
    "sant ravidas nagar": "bhadohi",
    "garhwal": "pauri garhwal",
    "barddhaman": "purba bardhaman",
    "twenty four parganas": "north twenty four parganas",
    "warangal urban (hanamkonda)": "hanamkonda",
    "hapur (panchsheel nagar)": "hapur",
    "sambhal (bhimnagar)": "sambhal",
    "shamli (prabuddhanagar)": "shamli",
}

STATE_ALIASES = {
    "andhra pradesh-telangana": ["TELANGANA", "ANDHRA PRADESH"],
    "daman and diu": ["THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU"],
}

TELANGANA_DISTRICTS = {
    "adilabad", "karimnagar", "warangal", "khammam", "nalgonda",
    "medak", "nizamabad", "rangareddy", "rangareddi", "mahabubnagar",
    "hyderabad",
}


def resolve_district_name(district_name: str,
                          state_name: str | None = None) -> str:
    """
    Resolve a district name to its canonical form used in the database.
    """
    dn = district_name.lower().strip()

    # Exact map check
    if dn in NAME_CORRECTIONS:
        return NAME_CORRECTIONS[dn]

    # Heuristic stripping for colonial names / complex split aliases
    # Remove suffixes like "Rural", "MGR", "Anna", "District"
    dn_clean = dn.replace(" mgr", "").replace(" anna", "").replace(" rural", "")
    dn_clean = dn_clean.replace(" district", "").replace(" frontier tract", "").strip()

    # Re-check the map after heuristic stripping
    if dn_clean in NAME_CORRECTIONS:
        return NAME_CORRECTIONS[dn_clean]

    return dn_clean


DISTRICT_RESOLUTION = {

    # ----------------------------------------------------------
    # ANDAMAN & NICOBAR
    # ----------------------------------------------------------
    ("Andaman and Nicobar Islands", "Andaman"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "North and Middle Andaman", "lgd": 637},
            {"name": "South Andaman", "lgd": 638}
        ]},

    ("Andaman and Nicobar Islands", "Andaman and Nicobar Islands"): {
        "type": "state_parent",
        "maps_to": [
            {"name": "Nicobar", "lgd": 639},
            {"name": "North and Middle Andaman", "lgd": 637},
            {"name": "South Andaman", "lgd": 638}
        ]},

    # ----------------------------------------------------------
    # ANDHRA PRADESH
    # ----------------------------------------------------------
    ("Andhra Pradesh", "Vishakhapatnam"): {
        "type": "alias",
        "maps_to": [{"name": "Visakhapatnam", "lgd": 544}]
    },

    # ----------------------------------------------------------
    # ARUNACHAL PRADESH
    # ----------------------------------------------------------
    ("Arunachal Pradesh", "Kameng"): {
        "type": "colonial_parent",
        "maps_to": [
            {"name": "West Kameng", "lgd": 229},
            {"name": "East Kameng", "lgd": 230}
        ]},

    ("Arunachal Pradesh", "Subansiri Frontier"): {
        "type": "colonial_parent",
        "maps_to": [
            {"name": "Upper Subansiri", "lgd": 236},
            {"name": "Lower Subansiri", "lgd": 235}
        ]},

    # ----------------------------------------------------------
    # ASSAM
    # ----------------------------------------------------------
    ("Assam", "United Mikir and North Cachar Hills"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "Karbi Anglong", "lgd": 302},
            {"name": "Dima Hasao", "lgd": 288}
        ]},

    # ----------------------------------------------------------
    # BIHAR
    # ----------------------------------------------------------
    ("Bihar", "Pashchim Champaran"): {
        "type": "alias",
        "maps_to": [{"name": "West Champaran", "lgd": 218}]
    },

    # ----------------------------------------------------------
    # CHHATTISGARH
    # ----------------------------------------------------------
    ("Chhattisgarh", "Kawardha"): {
        "type": "renamed",
        "maps_to": [{"name": "Kabirdham", "lgd": 377}]
    },

    ("Chhattisgarh", "Koriya"): {
        "type": "alias",
        "maps_to": [{"name": "Korea", "lgd": 379}]
    },

    # ----------------------------------------------------------
    # DELHI
    # ----------------------------------------------------------
    ("Delhi", "Delhi"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "Central Delhi", "lgd": 95},
            {"name": "East Delhi", "lgd": 96},
            {"name": "New Delhi", "lgd": 97},
            {"name": "North Delhi", "lgd": 98},
            {"name": "North East Delhi", "lgd": 99},
            {"name": "North West Delhi", "lgd": 100},
            {"name": "South Delhi", "lgd": 101},
            {"name": "South West Delhi", "lgd": 102},
            {"name": "West Delhi", "lgd": 103}
        ]},

    # ----------------------------------------------------------
    # GOA
    # ----------------------------------------------------------
    ("Goa", "Goa"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "North Goa", "lgd": 551},
            {"name": "South Goa", "lgd": 552}
        ]},

    # ----------------------------------------------------------
    # HARYANA
    # ----------------------------------------------------------
    ("Haryana", "Mewat"): {
        "type": "renamed",
        "maps_to": [{"name": "Nuh", "lgd": 84}]
    },

    # ----------------------------------------------------------
    # HIMACHAL
    # ----------------------------------------------------------
    ("Himachal Pradesh", "Mahasu"): {
        "type": "dissolved_parent",
        "maps_to": [
            {"name": "Shimla", "lgd": 31},
            {"name": "Solan", "lgd": 32},
            {"name": "Sirmaur", "lgd": 33}
        ]},

    # ----------------------------------------------------------
    # JAMMU & KASHMIR
    # ----------------------------------------------------------
    ("Jammu & Kashmir", "Punch"): {
        "type": "alias",
        "maps_to": [{"name": "Poonch", "lgd": 2}]
    },

    ("Jammu & Kashmir", "Baramula"): {
        "type": "alias",
        "maps_to": [{"name": "Baramulla", "lgd": 9}]
    },

    ("Jammu & Kashmir", "Ladakh"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "Leh", "lgd": 1},
            {"name": "Kargil", "lgd": 10}
        ]},

    ("Jammu & Kashmir", "Doda"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "Doda", "lgd": 4},
            {"name": "Kishtwar", "lgd": 12},
            {"name": "Ramban", "lgd": 13}
        ]},

    # ----------------------------------------------------------
    # JHARKHAND
    # ----------------------------------------------------------
    ("Jharkhand", "Purbi Singhbhum"): {
        "type": "alias",
        "maps_to": [{"name": "East Singhbhum", "lgd": 343}]
    },

    ("Jharkhand", "Santhal Pargana"): {
        "type": "historical_division",
        "maps_to": [
            {"name": "Dumka", "lgd": 344},
            {"name": "Deoghar", "lgd": 345},
            {"name": "Godda", "lgd": 346},
            {"name": "Sahibganj", "lgd": 347},
            {"name": "Pakur", "lgd": 348}
        ]},

    # ----------------------------------------------------------
    # KERALA
    # ----------------------------------------------------------
    ("Kerala", "Malabar"): {
        "type": "colonial_parent",
        "maps_to": [
            {"name": "Kozhikode", "lgd": 561},
            {"name": "Kannur", "lgd": 559},
            {"name": "Malappuram", "lgd": 560},
            {"name": "Wayanad", "lgd": 562}
        ]},

    # ----------------------------------------------------------
    # MADHYA PRADESH
    # ----------------------------------------------------------
    ("Madhya Pradesh", "Khandwa (East Nimar)"): {
        "type": "renamed",
        "maps_to": [{"name": "Khandwa", "lgd": 439}]
    },

    # ----------------------------------------------------------
    # MANIPUR
    # ----------------------------------------------------------
    ("Manipur", "Manipur Central"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "Imphal East", "lgd": 253},
            {"name": "Imphal West", "lgd": 254}
        ]},

    # ----------------------------------------------------------
    # MIZORAM
    # ----------------------------------------------------------
    ("Mizoram", "Chhimtuipui"): {
        "type": "renamed",
        "maps_to": [{"name": "Lawngtlai", "lgd": 266}]
    },

    # ----------------------------------------------------------
    # NAGALAND
    # ----------------------------------------------------------
    ("Nagaland", "Niuland"): {
        "type": "valid",
        "maps_to": [{"name": "Niuland", "lgd": 613}]
    },

    # ----------------------------------------------------------
    # SIKKIM
    # ----------------------------------------------------------
    ("Sikkim", "East District"): {
        "type": "alias",
        "maps_to": [{"name": "East Sikkim", "lgd": 239}]
    },

    ("Sikkim", "West District"): {
        "type": "alias",
        "maps_to": [{"name": "West Sikkim", "lgd": 242}]
    },

    # ----------------------------------------------------------
    # TAMIL NADU
    # ----------------------------------------------------------
    ("Tamil Nadu", "Chidambaranar"): {
        "type": "renamed",
        "maps_to": [{"name": "Thoothukudi", "lgd": 587}]
    },

    ("Tamil Nadu", "North Arcot Ambedkar"): {
        "type": "renamed",
        "maps_to": [{"name": "Vellore", "lgd": 593}]
    },

    # ----------------------------------------------------------
    # TELANGANA
    # ----------------------------------------------------------
    ("Telangana", "Kumuram Bheem"): {
        "type": "alias",
        "maps_to": [{"name": "Komaram Bheem Asifabad", "lgd": 699}]
    },

    # ----------------------------------------------------------
    # TRIPURA
    # ----------------------------------------------------------
    ("Tripura", "Tripura"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "West Tripura", "lgd": 281},
            {"name": "North Tripura", "lgd": 282},
            {"name": "Dhalai", "lgd": 283},
            {"name": "South Tripura", "lgd": 284}
        ]},

    # ----------------------------------------------------------
    # WEST BENGAL
    # ----------------------------------------------------------
    ("West Bengal", "West Dinajpur"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "Uttar Dinajpur", "lgd": 317},
            {"name": "Dakshin Dinajpur", "lgd": 318}
        ]},

    ("West Bengal", "Twenty Four Parganas"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "North 24 Parganas", "lgd": 304},
            {"name": "South 24 Parganas", "lgd": 305}
        ]
    },

    # ---------------- ANDAMAN ----------------
    ("Andaman and Nicobar Islands", "Andamans"): {
        "type": "alias",
        "maps_to": [
            {"name": "North and Middle Andaman", "lgd": 637},
            {"name": "South Andaman", "lgd": 638}
        ]
    },

    # ---------------- ARUNACHAL ----------------
    ("Arunachal Pradesh", "Kameng Frontier"): {
        "type": "colonial_parent",
        "maps_to": [
            {"name": "West Kameng", "lgd": 229},
            {"name": "East Kameng", "lgd": 230}
        ]
    },

    # ---------------- CHHATTISGARH ----------------
    ("Chhattisgarh", "Bijapur"): {
        "type": "valid",
        "maps_to": [{"name": "Bijapur", "lgd": 374}]
    },

    # ---------------- J&K CORE ----------------
    ("Jammu & Kashmir", "Anantnag"): {
        "type": "valid",
        "maps_to": [{"name": "Anantnag", "lgd": 14}]
    },

    ("Jammu & Kashmir", "Badgam"): {
        "type": "alias",
        "maps_to": [{"name": "Budgam", "lgd": 8}]
    },

    ("Jammu & Kashmir", "Bandipore"): {
        "type": "alias",
        "maps_to": [{"name": "Bandipora", "lgd": 6}]
    },

    ("Jammu & Kashmir", "Baramulla"): {
        "type": "valid",
        "maps_to": [{"name": "Baramulla", "lgd": 9}]
    },

    ("Jammu & Kashmir", "Ganderbal"): {
        "type": "valid",
        "maps_to": [{"name": "Ganderbal", "lgd": 7}]
    },

    ("Jammu & Kashmir", "Jammu"): {
        "type": "valid",
        "maps_to": [{"name": "Jammu", "lgd": 3}]
    },

    ("Jammu & Kashmir", "Kargil"): {
        "type": "valid",
        "maps_to": [{"name": "Kargil", "lgd": 10}]
    },

    ("Jammu & Kashmir", "Kathua"): {
        "type": "valid",
        "maps_to": [{"name": "Kathua", "lgd": 5}]
    },

    ("Jammu & Kashmir", "Kishtwar"): {
        "type": "valid",
        "maps_to": [{"name": "Kishtwar", "lgd": 12}]
    },

    ("Jammu & Kashmir", "Kulgam"): {
        "type": "valid",
        "maps_to": [{"name": "Kulgam", "lgd": 15}]
    },

    ("Jammu & Kashmir", "Kupwara"): {
        "type": "valid",
        "maps_to": [{"name": "Kupwara", "lgd": 11}]
    },

    ("Jammu & Kashmir", "Poonch"): {
        "type": "valid",
        "maps_to": [{"name": "Poonch", "lgd": 2}]
    },

    ("Jammu & Kashmir", "Pulwama"): {
        "type": "valid",
        "maps_to": [{"name": "Pulwama", "lgd": 16}]
    },

    ("Jammu & Kashmir", "Rajauri"): {
        "type": "alias",
        "maps_to": [{"name": "Rajouri", "lgd": 1}]
    },

    ("Jammu & Kashmir", "Ramban"): {
        "type": "valid",
        "maps_to": [{"name": "Ramban", "lgd": 13}]
    },

    ("Jammu & Kashmir", "Reasi"): {
        "type": "valid",
        "maps_to": [{"name": "Reasi", "lgd": 17}]
    },

    ("Jammu & Kashmir", "Samba"): {
        "type": "valid",
        "maps_to": [{"name": "Samba", "lgd": 18}]
    },

    ("Jammu & Kashmir", "Shupiyan"): {
        "type": "alias",
        "maps_to": [{"name": "Shopian", "lgd": 19}]
    },

    ("Jammu & Kashmir", "Srinagar"): {
        "type": "valid",
        "maps_to": [{"name": "Srinagar", "lgd": 20}]
    },

    ("Jammu & Kashmir", "Udhampur"): {
        "type": "valid",
        "maps_to": [{"name": "Udhampur", "lgd": 21}]
    },

    # ---------------- MAHARASHTRA ----------------
    ("Maharashtra", "Mumbai (Suburban)"): {
        "type": "alias",
        "maps_to": [{"name": "Mumbai Suburban", "lgd": 399}]
    },

    # ---------------- MANIPUR ----------------
    ("Manipur", "Imphal"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "Imphal East", "lgd": 253},
            {"name": "Imphal West", "lgd": 254}
        ]
    },

    ("Manipur", "Manipur East"): {
        "type": "alias",
        "maps_to": [{"name": "Imphal East", "lgd": 253}]
    },

    ("Manipur", "Manipur North"): {
        "type": "alias",
        "maps_to": [{"name": "Senapati", "lgd": 257}]
    },

    ("Manipur", "Manipur South"): {
        "type": "alias",
        "maps_to": [{"name": "Churachandpur", "lgd": 252}]
    },

    ("Manipur", "Manipur West"): {
        "type": "alias",
        "maps_to": [{"name": "Imphal West", "lgd": 254}]
    },

    # ---------------- MEGHALAYA ----------------
    ("Meghalaya", "United Khasi and Jaintia Hills"): {
        "type": "parent_split",
        "maps_to": [
            {"name": "East Khasi Hills", "lgd": 282},
            {"name": "West Khasi Hills", "lgd": 284},
            {"name": "West Jaintia Hills", "lgd": 286}
        ]
    },

    # ---------------- MIZORAM ----------------
    ("Mizoram", "Mizoram"): {
        "type": "virtual_parent",
        "maps_to": [
            {"name": "Aizawl", "lgd": 261},
            {"name": "Lunglei", "lgd": 264},
            {"name": "Champhai", "lgd": 262},
            {"name": "Serchhip", "lgd": 267}
        ]
    },

    # ---------------- DELHI ----------------
    ("NCT of Delhi", "Central"): {"type": "valid", "maps_to": [{"name": "Central Delhi", "lgd": 95}]},
    ("NCT of Delhi", "East"): {"type": "valid", "maps_to": [{"name": "East Delhi", "lgd": 96}]},
    ("NCT of Delhi", "New Delhi"): {"type": "valid", "maps_to": [{"name": "New Delhi", "lgd": 97}]},
    ("NCT of Delhi", "North"): {"type": "valid", "maps_to": [{"name": "North Delhi", "lgd": 98}]},
    ("NCT of Delhi", "North East"): {"type": "valid", "maps_to": [{"name": "North East Delhi", "lgd": 99}]},
    ("NCT of Delhi", "North West"): {"type": "valid", "maps_to": [{"name": "North West Delhi", "lgd": 100}]},
    ("NCT of Delhi", "South"): {"type": "valid", "maps_to": [{"name": "South Delhi", "lgd": 101}]},
    ("NCT of Delhi", "South West"): {"type": "valid", "maps_to": [{"name": "South West Delhi", "lgd": 102}]},
    ("NCT of Delhi", "West"): {"type": "valid", "maps_to": [{"name": "West Delhi", "lgd": 103}]},

    # ---------------- SIKKIM ----------------
    ("Sikkim", "East"): {"type": "valid", "maps_to": [{"name": "East Sikkim", "lgd": 239}]},
    ("Sikkim", "West"): {"type": "valid", "maps_to": [{"name": "West Sikkim", "lgd": 242}]},
    ("Sikkim", "North District"): {"type": "alias", "maps_to": [{"name": "North Sikkim", "lgd": 240}]},
    ("Sikkim", "South District"): {"type": "alias", "maps_to": [{"name": "South Sikkim", "lgd": 241}]},

    # ---------------- TAMIL NADU ----------------
    ("Tamil Nadu", "Pasumpon Muthuramalinga Thevar"): {
        "type": "renamed",
        "maps_to": [{"name": "Ramanathapuram", "lgd": 585}]
    },

    ("Tamil Nadu", "Tiruvannamalai Sambuvarayar"): {
        "type": "renamed",
        "maps_to": [{"name": "Tiruvannamalai", "lgd": 590}]
    },

    # ---------------- TELANGANA ----------------
    ("Telangana", "Warangal Urban (Hanamkonda)"): {
        "type": "renamed",
        "maps_to": [{"name": "Hanamkonda", "lgd": 711}]
    },

    # ---------------- WEST BENGAL ----------------
    ("West Bengal", "Dakshin Dinajpur"): {"type": "valid", "maps_to": [{"name": "Dakshin Dinajpur", "lgd": 318}]},
    ("West Bengal", "Uttar Dinajpur"): {"type": "valid", "maps_to": [{"name": "Uttar Dinajpur", "lgd": 317}]},
    ("West Bengal", "North Twenty Four Parganas"): {"type": "alias", "maps_to": [{"name": "North 24 Parganas", "lgd": 304}]},
    ("West Bengal", "South Twenty Four Parganas"): {"type": "alias", "maps_to": [{"name": "South 24 Parganas", "lgd": 305}]},
    ("West Bengal", "Paschim Medinipur"): {"type": "valid", "maps_to": [{"name": "Paschim Medinipur", "lgd": 312}]},
    ("West Bengal", "Purba Medinipur"): {"type": "valid", "maps_to": [{"name": "Purba Medinipur", "lgd": 311}]},
}


def check_historical_resolution(state_name: str, district_name: str) -> bool:
    """
    Checks if a given state and historical district name exists in the
    known resolution dictionary. Case insensitive matching.
    """
    s_lower = state_name.strip().lower()
    d_lower = district_name.strip().lower()
    return any(st.lower() == s_lower and dist.lower() == d_lower for (st, dist), data in DISTRICT_RESOLUTION.items())
