"""
Mapping Service: Provides robust district-to-GeoJSON mapping with fallback strategies.

Handles:
- Name normalization for district/state matching (via shared name_resolver)
- Reverse lookup (CDK -> GeoJSON key)
- Fuzzy matching when exact lookup fails
- Split district scenarios: child data mapped to parent polygon
"""

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

from app.services.name_resolver import _ALIASES as SHARED_ALIASES

logger = logging.getLogger(__name__)


class MappingService:
    """
    Service for resolving district mappings between database CDKs and GeoJSON keys.

    The bridge maps GeoJSON keys (DISTRICT|STATE) to CDK codes.
    This service provides reverse lookup and fallback matching.
    Uses the shared name_resolver for canonical alias resolution.
    """

    # Use aliases from the single shared source of truth
    NAME_ALIASES: dict[str, str] = SHARED_ALIASES

    # State code to full name mapping
    STATE_CODES: dict[str, str] = {
        "AN": "Andhra Pradesh",
        "AP": "Andhra Pradesh",
        "AR": "Arunachal Pradesh",
        "AS": "Assam",
        "BR": "Bihar",
        "CG": "Chhattisgarh",
        "CH": "Chandigarh",
        "GA": "Goa",
        "GJ": "Gujarat",
        "GU": "Gujarat",
        "HP": "Himachal Pradesh",
        "HI": "Himachal Pradesh",
        "HR": "Haryana",
        "JH": "Jharkhand",
        "JK": "Jammu & Kashmir",
        "KA": "Karnataka",
        "KE": "Kerala",
        "KL": "Kerala",
        "LA": "Lakshadweep",
        "MA": "Maharashtra",
        "MH": "Maharashtra",
        "ML": "Meghalaya",
        "MN": "Manipur",
        "MP": "Madhya Pradesh",
        "MZ": "Mizoram",
        "MI": "Mizoram",
        "NC": "NCT of Delhi",
        "NL": "Nagaland",
        "OD": "Odisha",
        "OR": "Odisha",
        "PB": "Punjab",
        "PU": "Punjab",
        "RA": "Rajasthan",
        "RJ": "Rajasthan",
        "SK": "Sikkim",
        "TA": "Tamil Nadu",
        "TN": "Tamil Nadu",
        "TG": "Telangana",
        "TS": "Telangana",
        "TR": "Tripura",
        "UK": "Uttarakhand",
        "UP": "Uttar Pradesh",
        "UT": "Uttar Pradesh",
        "WB": "West Bengal",
        "WE": "West Bengal",
        "BI": "Bihar",
        "DA": "Dadra & Nagar Haveli",
    }

    # Districts that were part of undivided AP but now belong to Telangana.
    # Used as a fallback when geo_key lookup with "Telangana" fails — retry
    # with "Andhra Pradesh" (and vice versa) for these districts.
    _TELANGANA_AP_DISTRICTS: set[str] = {
        "adilabad",
        "hyderabad",
        "karimnagar",
        "khammam",
        "mahbubnagar",
        "mahabubnagar",
        "medak",
        "nalgonda",
        "nizamabad",
        "rangareddy",
        "rangareddi",
        "warangal",
    }

    def __init__(self, bridge_path: str | None = None):
        """
        Initialize with bridge file path.

        Args:
            bridge_path: Path to map_bridge.json. If None, uses default location.
        """
        self._bridge_path = bridge_path
        self._bridge: dict[str, str] | None = None
        self._reverse_bridge: dict[str, str] | None = None
        self._geo_keys_normalized: dict[str, str] | None = None

    @staticmethod
    def _default_bridge_candidates() -> list[Path]:
        """Return candidate locations for the map bridge in local and deployed layouts."""
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parents[2]  # /app
        repo_root = current_file.parents[3]  # fallback to /

        candidates: list[Path] = []

        env_path = os.getenv("MAP_BRIDGE_PATH")
        if env_path:
            candidates.append(Path(env_path))

        candidates.extend(
            [
                Path("/app/data/map_bridge.json"),  # Docker standard layout
                backend_dir / "data" / "map_bridge.json",  # Relative to backend root
                repo_root / "frontend" / "public" / "data" / "map_bridge.json",  # Repo layout
                repo_root / "backend" / "data" / "map_bridge.json",  # Repo layout fallback
            ]
        )

        return candidates

    def _load_bridge(self) -> dict[str, str]:
        """Load bridge file lazily."""
        if self._bridge is not None:
            return self._bridge

        if self._bridge_path:
            path = Path(self._bridge_path)
        else:
            possible_paths = self._default_bridge_candidates()
            path = None
            for p in possible_paths:
                if p.exists():
                    path = p
                    break

            if path is None:
                logger.warning(
                    "Could not find map_bridge.json in any known location: %s",
                    [str(candidate) for candidate in possible_paths],
                )
                self._bridge = {}
                return self._bridge

        try:
            assert path is not None
            with open(path, encoding="utf-8") as f:
                self._bridge = json.load(f)
            logger.info(f"Loaded bridge with {len(self._bridge)} entries")
        except Exception as e:
            logger.error(f"Failed to load bridge: {e}")
            self._bridge = {}

        if self._bridge is None:
            self._bridge = {}
        return self._bridge

    @lru_cache(maxsize=1)
    def _build_reverse_bridge(self) -> dict[str, str]:
        """Build CDK -> GeoKey lookup from bridge."""
        bridge = self._load_bridge()
        reverse = {}

        for geo_key, cdk in bridge.items():
            # A CDK may map to multiple geo_keys (rare), keep first
            if cdk not in reverse:
                reverse[cdk] = geo_key

        return reverse

    @lru_cache(maxsize=1)
    def _build_normalized_geo_keys(self) -> dict[str, str]:
        """Build normalized name -> original geo_key lookup."""
        bridge = self._load_bridge()
        normalized = {}

        for geo_key in bridge:
            norm_key = self._normalize_geo_key(geo_key)
            if norm_key not in normalized:
                normalized[norm_key] = geo_key

        return normalized

    def normalize_name(self, name: str) -> str:
        """
        Normalize a district or state name for matching.

        - Lowercase
        - Remove special characters except spaces
        - Replace common aliases
        - Trim whitespace
        """
        if not name:
            return ""

        # Lowercase and strip
        normalized = name.lower().strip()

        # Replace common aliases
        for alias, standard in self.NAME_ALIASES.items():
            if normalized == alias:
                normalized = standard
                break

        # Remove special chars except spaces and alphanumeric
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)

        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _normalize_geo_key(self, geo_key: str) -> str:
        """Normalize a DISTRICT|STATE geo key."""
        if "|" not in geo_key:
            return self.normalize_name(geo_key)

        parts = geo_key.split("|", 1)
        district = self.normalize_name(parts[0])
        state = self.normalize_name(parts[1]) if len(parts) > 1 else ""

        return f"{district}|{state}"

    def get_state_from_cdk(self, cdk: str) -> str | None:
        """Extract state name from CDK code prefix."""
        if not cdk or "_" not in cdk:
            return None

        state_code = cdk.split("_")[0]
        return self.STATE_CODES.get(state_code)

    def _alternate_states(self, district: str | None, state: str | None) -> list[str]:
        """
        Return alternate state names to try when the primary state doesn't match.

        Handles Telangana ↔ Andhra Pradesh: the GeoJSON may label a polygon
        under one state while the database uses the other.
        """
        if not district or not state:
            return []

        norm_district = self.normalize_name(district)
        norm_state = self.normalize_name(state)

        if norm_district in self._TELANGANA_AP_DISTRICTS:
            if "telangana" in norm_state:
                return ["Andhra Pradesh"]
            if "andhra" in norm_state:
                return ["Telangana"]

        return []

    def resolve_geo_key(self, cdk: str, district: str | None = None, state: str | None = None) -> str | None:
        """
        Resolve the GeoJSON key for a CDK with multiple fallback strategies.

        Priority:
        1. Exact reverse bridge lookup (CDK -> GeoKey)
        2. Direct name construction (district|state)
        3. Normalized name matching
        4. Telangana ↔ AP state remapping
        5. State inference from CDK prefix
        6. Fuzzy matching (expensive, only if others fail)

        Args:
            cdk: The canonical district key from database
            district: Optional district name for fallback
            state: Optional state name for fallback

        Returns:
            GeoJSON key (DISTRICT|STATE) or None if no match found
        """
        bridge = self._load_bridge()

        # Strategy 1: Reverse bridge lookup
        reverse = self._build_reverse_bridge()
        if cdk in reverse:
            return reverse[cdk]

        # Strategy 2: Direct name construction
        if district and state:
            direct_key = f"{district}|{state}"
            if direct_key in bridge:
                return direct_key

        # Strategy 3: Normalized name matching
        if district and state:
            norm_key = f"{self.normalize_name(district)}|{self.normalize_name(state)}"
            normalized_lookup = self._build_normalized_geo_keys()
            if norm_key in normalized_lookup:
                return normalized_lookup[norm_key]

        # No match found - strict mapping enforces no aggressive fuzzing
        logger.debug(f"No geo_key mapping found for CDK={cdk}, district={district}, state={state}")
        return None

    def fuzzy_match_geo_key(self, district: str, state: str | None = None, threshold: float = 0.8) -> str | None:
        """
        Fuzzy match a district name against known GeoJSON keys.
        """
        best_match = None
        best_score = 0.0
        
        norm_dist = self.normalize_name(district)
        if not norm_dist:
            return None
            
        norm_state = self.normalize_name(state) if state else None
        
        bridge = self._bridge
        for geo_key in bridge.keys():
            parts = geo_key.split("|")
            if len(parts) != 2:
                continue
                
            b_dist, b_state = parts
            
            if norm_state and self.normalize_name(b_state) != norm_state:
                continue
                
            score = self._similarity_ratio(norm_dist, self.normalize_name(b_dist))
            if score > best_score and score >= threshold:
                best_score = score
                best_match = geo_key
                
        return best_match

    def _similarity_ratio(self, a: str, b: str) -> float:
        """
        Simple similarity ratio using longest common subsequence.
        Returns value between 0 and 1.
        """
        if not a or not b:
            return 0.0

        if a == b:
            return 1.0

        # Simple approach: ratio of common characters
        len_a, len_b = len(a), len(b)

        # Check if one is substring of other
        if a in b:
            return len_a / len_b
        if b in a:
            return len_b / len_a

        # Check prefix match
        common_prefix = 0
        for i in range(min(len_a, len_b)):
            if a[i] == b[i]:
                common_prefix += 1
            else:
                break

        # Combined score
        return (2 * common_prefix) / (len_a + len_b)

    def get_all_unmapped_cdks(self, cdks: list[str]) -> list[str]:
        """
        Get list of CDKs that don't have geo_key mappings.
        Useful for diagnostics.
        """
        reverse = self._build_reverse_bridge()
        return [cdk for cdk in cdks if cdk not in reverse]


# Singleton instance for reuse
_mapping_service: MappingService | None = None


def get_mapping_service() -> MappingService:
    """Get singleton mapping service instance."""
    global _mapping_service
    if _mapping_service is None:
        _mapping_service = MappingService()
    return _mapping_service
