"""
Tests for MappingService: District-to-GeoJSON mapping with fallback strategies.
"""
from pathlib import Path

import pytest

from app.services.mapping_service import MappingService, get_mapping_service

# Sample bridge data for testing
MOCK_BRIDGE = {
    "Alappuzha|Kerala": "KE_alappu_1951",
    "Thiruvananthapuram|Kerala": "KE_thiruv_1951",
    "Agra|Uttar Pradesh": "UP_agra_1981",
    "Mumbai|Maharashtra": "MH_mumbai_1951",
    "Chennai|Tamil Nadu": "TN_chenna_1951",
    "Bastar|Chhattisgarh": "CG_bastar_1991",
    "Bangalore|Karnataka": "KA_bangal_1981",
}


@pytest.fixture
def mapping_service():
    """Create MappingService with mock bridge data."""
    service = MappingService()
    service._bridge = MOCK_BRIDGE.copy()
    return service


class TestNameNormalization:
    """Tests for name normalization logic."""

    def test_normalize_basic(self, mapping_service):
        """Basic normalization - lowercase and strip."""
        assert mapping_service.normalize_name("  AGRA  ") == "agra"
        assert mapping_service.normalize_name("Mumbai") == "mumbai"

    def test_normalize_special_chars(self, mapping_service):
        """Remove special characters."""
        assert mapping_service.normalize_name("North 24-Parganas") == "north 24parganas"
        assert mapping_service.normalize_name("Daman & Diu") == "daman diu"  # Spaces collapsed

    def test_normalize_aliases(self, mapping_service):
        """Replace common name aliases."""
        assert mapping_service.normalize_name("Bombay") == "mumbai"
        assert mapping_service.normalize_name("Madras") == "chennai"
        assert mapping_service.normalize_name("Calcutta") == "kolkata"
        assert mapping_service.normalize_name("Trivandrum") == "thiruvananthapuram"

    def test_normalize_empty(self, mapping_service):
        """Handle empty/None inputs."""
        assert mapping_service.normalize_name("") == ""
        assert mapping_service.normalize_name(None) == ""


class TestReverseBridge:
    """Tests for reverse bridge lookup (CDK -> GeoKey)."""

    def test_build_reverse_bridge(self, mapping_service):
        """Build reverse lookup from bridge."""
        reverse = mapping_service._build_reverse_bridge()

        assert reverse["KE_alappu_1951"] == "Alappuzha|Kerala"
        assert reverse["UP_agra_1981"] == "Agra|Uttar Pradesh"
        assert reverse["MH_mumbai_1951"] == "Mumbai|Maharashtra"

    def test_reverse_bridge_cached(self, mapping_service):
        """Reverse bridge should be cached."""
        r1 = mapping_service._build_reverse_bridge()
        r2 = mapping_service._build_reverse_bridge()
        # LRU cache means same object is returned
        assert r1 is r2


class TestStateFromCDK:
    """Tests for extracting state from CDK prefix."""

    def test_get_state_from_cdk(self, mapping_service):
        """Extract state name from CDK code prefix."""
        assert mapping_service.get_state_from_cdk("UP_agra_1981") == "Uttar Pradesh"
        assert mapping_service.get_state_from_cdk("KE_alappu_1951") == "Kerala"
        assert mapping_service.get_state_from_cdk("MH_mumbai_1951") == "Maharashtra"
        assert mapping_service.get_state_from_cdk("CG_bastar_1991") == "Chhattisgarh"

    def test_get_state_unknown_code(self, mapping_service):
        """Handle unknown state codes."""
        assert mapping_service.get_state_from_cdk("XX_unknown_2000") is None

    def test_get_state_invalid_cdk(self, mapping_service):
        """Handle invalid CDK formats."""
        assert mapping_service.get_state_from_cdk("invalid") is None
        assert mapping_service.get_state_from_cdk("") is None
        assert mapping_service.get_state_from_cdk(None) is None


class TestResolveGeoKey:
    """Tests for geo_key resolution with fallback strategies."""

    def test_resolve_exact_reverse_lookup(self, mapping_service):
        """Strategy 1: Exact reverse bridge lookup."""
        result = mapping_service.resolve_geo_key("KE_alappu_1951")
        assert result == "Alappuzha|Kerala"

    def test_resolve_direct_name_construction(self, mapping_service):
        """Strategy 2: Direct name construction."""
        # CDK not in reverse bridge, but name matches
        mapping_service._bridge["NewDistrict|TestState"] = "XX_new_2020"
        result = mapping_service.resolve_geo_key(
            "YY_other_2020",  # Different CDK
            district="NewDistrict",
            state="TestState"
        )
        assert result == "NewDistrict|TestState"

    def test_resolve_with_state_inference(self, mapping_service):
        """Strategy 4: State inference from CDK when not provided."""
        # Mumbai is in bridge, state inferred from MH prefix
        result = mapping_service.resolve_geo_key(
            "MH_mumbai_1951",
            district="Mumbai"
            # state not provided - should be inferred
        )
        assert result == "Mumbai|Maharashtra"

    def test_resolve_no_match(self, mapping_service):
        """Return None when no match found."""
        result = mapping_service.resolve_geo_key(
            "XX_unknown_2000",
            district="NonExistent",
            state="FakeState"
        )
        assert result is None


class TestFuzzyMatching:
    """Tests for fuzzy name matching."""

    def test_fuzzy_match_exact(self, mapping_service):
        """Fuzzy matching finds exact matches."""
        result = mapping_service.fuzzy_match_geo_key("Alappuzha", "Kerala")
        assert result == "Alappuzha|Kerala"

    def test_fuzzy_match_case_insensitive(self, mapping_service):
        """Fuzzy matching is case insensitive."""
        result = mapping_service.fuzzy_match_geo_key("ALAPPUZHA", "KERALA")
        assert result == "Alappuzha|Kerala"

    def test_fuzzy_match_partial(self, mapping_service):
        """Fuzzy matching finds partial/similar matches."""
        # "Thiruvanant..." prefix should match
        result = mapping_service.fuzzy_match_geo_key("Thiruvanant", "Kerala", threshold=0.5)
        assert result == "Thiruvananthapuram|Kerala"

    def test_fuzzy_match_no_match(self, mapping_service):
        """Return None when similarity is below threshold."""
        result = mapping_service.fuzzy_match_geo_key("XYZ123", "UnknownState", threshold=0.8)
        assert result is None


class TestSimilarityRatio:
    """Tests for string similarity calculation."""

    def test_similarity_exact(self, mapping_service):
        """Exact match returns 1.0."""
        assert mapping_service._similarity_ratio("agra", "agra") == 1.0

    def test_similarity_substring(self, mapping_service):
        """Substring match returns proportional score."""
        ratio = mapping_service._similarity_ratio("agra", "agrawal")
        assert 0.5 < ratio < 1.0

    def test_similarity_prefix(self, mapping_service):
        """Prefix match scores higher than no match."""
        prefix_ratio = mapping_service._similarity_ratio("mumbai", "mumbais")
        no_match_ratio = mapping_service._similarity_ratio("mumbai", "delhi")
        assert prefix_ratio > no_match_ratio

    def test_similarity_empty(self, mapping_service):
        """Empty strings return 0."""
        assert mapping_service._similarity_ratio("", "test") == 0.0
        assert mapping_service._similarity_ratio("test", "") == 0.0


class TestUnmappedCDKs:
    """Tests for diagnostic functions."""

    def test_get_unmapped_cdks(self, mapping_service):
        """Identify CDKs without geo_key mappings."""
        cdks = ["KE_alappu_1951", "XX_unknown_2000", "UP_agra_1981", "YY_fake_1999"]
        unmapped = mapping_service.get_all_unmapped_cdks(cdks)

        assert "XX_unknown_2000" in unmapped
        assert "YY_fake_1999" in unmapped
        assert "KE_alappu_1951" not in unmapped
        assert "UP_agra_1981" not in unmapped


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_mapping_service_singleton(self):
        """get_mapping_service returns same instance."""
        # Reset singleton for test
        import app.services.mapping_service as ms
        ms._mapping_service = None

        s1 = get_mapping_service()
        s2 = get_mapping_service()

        assert s1 is s2


class TestBridgeDiscovery:
    """Tests for deploy-safe bridge path discovery."""

    def test_default_bridge_candidates_include_repo_public_data(self, monkeypatch):
        service = MappingService()
        monkeypatch.delenv("MAP_BRIDGE_PATH", raising=False)

        candidates = service._default_bridge_candidates()

        repo_root = Path(__file__).resolve().parents[2]
        expected_path = repo_root / "frontend" / "public" / "data" / "map_bridge.json"
        assert expected_path in candidates

    def test_default_bridge_candidates_prioritize_env_override(self, monkeypatch, tmp_path):
        service = MappingService()
        custom_bridge = tmp_path / "map_bridge.json"
        monkeypatch.setenv("MAP_BRIDGE_PATH", str(custom_bridge))

        candidates = service._default_bridge_candidates()

        assert candidates[0] == custom_bridge
