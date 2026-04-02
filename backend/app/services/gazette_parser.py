"""
Gazette Text Parser — Extract district split events from gazette/notification text.

Uses regex and NLP pattern matching (not LLM) to parse gazette text like:
  "The district of Adilabad shall be divided into Adilabad, Nirmal, Mancherial,
   and Kumuram Bheem Asifabad districts with effect from October 11, 2016."

Returns structured SplitEvent records for insertion into split_events table.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("app.services.gazette_parser")


@dataclass
class ParsedSplitEvent:
    """A single split event extracted from gazette text."""

    parent_district: str
    child_districts: list[str]
    year: int
    state: str | None = None
    confidence: float = 0.5
    raw_text: str = ""
    source: str = "gazette_text"


# ── Pattern Library ────────────────────────────────────────────────────────

# "X shall be divided/bifurcated/split into A, B, C"
SPLIT_PATTERN = re.compile(
    r"(?:district|tehsil)?\s*(?:of\s+)?([A-Z][a-zA-Z\s\-']+?)\s+"
    r"(?:shall be|was|is|has been|to be)\s+"
    r"(?:divided|bifurcated|split|carved|reorgani[sz]ed|trifurcated)\s+"
    r"(?:in)?to\s+"
    r"(.+?)(?:\s+(?:district|districts))?(?:\s*\.|\s*$)",
    re.IGNORECASE | re.MULTILINE,
)

# "Y was carved out of X"  /  "Y has been separated from X"
CARVED_PATTERN = re.compile(
    r"([A-Z][a-zA-Z\s\-']+?)\s+"
    r"(?:was|has been|is)\s+"
    r"(?:carved\s+out\s+(?:of|from)|separated\s+from|detached\s+from)\s+"
    r"([A-Z][a-zA-Z\s\-']+)",
    re.IGNORECASE | re.MULTILINE,
)

# "With effect from October 11, 2016"  /  "w.e.f. 01.10.2016"  /  "in the year 2016"
YEAR_PATTERN = re.compile(
    r"(?:(?:w\.?e\.?f\.?|with\s+effect\s+from|effective\s+from|from|on)\s+"
    r"(?:\d{1,2}[\s\-\.\/]\w+[\s\-\.\/])?"
    r"(\d{4}))"
    r"|(?:(?:in|during|year)\s+(\d{4}))"
    r"|(?:(\d{4})[\s\-](?:\d{2})?)",
    re.IGNORECASE,
)

# "State of Telangana"  /  "in Maharashtra"
STATE_PATTERN = re.compile(
    r"(?:state\s+of|in|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
    r"(?:\s+(?:state|province))?",
    re.IGNORECASE,
)

# Indian states for validation
INDIAN_STATES = {
    "andhra pradesh",
    "arunachal pradesh",
    "assam",
    "bihar",
    "chhattisgarh",
    "goa",
    "gujarat",
    "haryana",
    "himachal pradesh",
    "jharkhand",
    "karnataka",
    "kerala",
    "madhya pradesh",
    "maharashtra",
    "manipur",
    "meghalaya",
    "mizoram",
    "nagaland",
    "odisha",
    "punjab",
    "rajasthan",
    "sikkim",
    "tamil nadu",
    "telangana",
    "tripura",
    "uttar pradesh",
    "uttarakhand",
    "west bengal",
    "jammu and kashmir",
    "jammu & kashmir",
    "ladakh",
    "delhi",
    "puducherry",
    "chandigarh",
    "lakshadweep",
    "andaman and nicobar",
    "dadra and nagar haveli",
}


def _clean_name(name: str) -> str:
    """Clean a district name."""
    name = name.strip().strip(",").strip(".")
    # Remove common prefixes
    name = re.sub(r"^(?:the|new|old)\s+", "", name, flags=re.IGNORECASE)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _split_list(text: str) -> list[str]:
    """Parse a comma/and separated list of district names."""
    # Handle "A, B, C and D"  or  "A, B, C & D"
    # First split by "and" or "&"
    parts = re.split(r"\s+and\s+|\s*&\s*", text, flags=re.IGNORECASE)
    result = []
    for part in parts:
        # Then split by commas
        sub_parts = part.split(",")
        for sp in sub_parts:
            cleaned = _clean_name(sp)
            if cleaned and len(cleaned) > 1 and cleaned.lower() not in INDIAN_STATES:
                result.append(cleaned)
    return result


def _extract_year(text: str) -> int | None:
    """Extract the most likely year from gazette text."""
    matches = YEAR_PATTERN.findall(text)
    years = []
    for groups in matches:
        for g in groups:
            if g:
                try:
                    y = int(g)
                    if 1947 <= y <= 2030:
                        years.append(y)
                except ValueError:
                    pass
    return max(years) if years else None


def _extract_state(text: str) -> str | None:
    """Extract state name from gazette text."""
    match = STATE_PATTERN.search(text)
    if match:
        candidate = match.group(1).strip().lower()
        if candidate in INDIAN_STATES:
            return match.group(1).strip().title()
    return None


# ── Main Parser ────────────────────────────────────────────────────────────


def parse_gazette_text(text: str) -> list[ParsedSplitEvent]:
    """
    Parse gazette/notification text and extract split events.

    Returns a list of ParsedSplitEvent objects.
    """
    events: list[ParsedSplitEvent] = []

    year = _extract_year(text)
    state = _extract_state(text)

    # Try pattern 1: "X divided into A, B, C"
    for match in SPLIT_PATTERN.finditer(text):
        parent = _clean_name(match.group(1))
        children_text = match.group(2)
        children = _split_list(children_text)

        if parent and len(children) >= 1:
            events.append(
                ParsedSplitEvent(
                    parent_district=parent,
                    child_districts=children,
                    year=year or 2000,
                    state=state,
                    confidence=0.7 if year else 0.4,
                    raw_text=match.group(0).strip(),
                )
            )

    # Try pattern 2: "Y carved out of X"
    for match in CARVED_PATTERN.finditer(text):
        child = _clean_name(match.group(1))
        parent = _clean_name(match.group(2))

        if parent and child:
            # Check if we already have this parent
            existing = [e for e in events if e.parent_district.lower() == parent.lower()]
            if existing:
                if child not in existing[0].child_districts:
                    existing[0].child_districts.append(child)
            else:
                events.append(
                    ParsedSplitEvent(
                        parent_district=parent,
                        child_districts=[child],
                        year=year or 2000,
                        state=state,
                        confidence=0.6 if year else 0.3,
                        raw_text=match.group(0).strip(),
                    )
                )

    # Deduplicate
    seen = set()
    unique = []
    for e in events:
        key = (e.parent_district.lower(), tuple(sorted(c.lower() for c in e.child_districts)))
        if key not in seen:
            seen.add(key)
            unique.append(e)

    if not unique:
        logger.info("No split events found in gazette text")
    else:
        logger.info(f"Extracted {len(unique)} split event(s) from gazette text")

    return unique
