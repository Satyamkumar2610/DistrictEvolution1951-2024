from typing import Any

import pyproj
from shapely.geometry import shape
from shapely.ops import transform, unary_union


class GeometryService:
    def __init__(self):
        # EPSG:7755 is the standard India Equal Area projection suitable for
        # accurate sq km calculations
        self.TARGET_CRS = "EPSG:7755"
        self.SOURCE_CRS = "EPSG:4326"

        # Set up the coordinate transformer
        self._transformer = pyproj.Transformer.from_crs(self.SOURCE_CRS, self.TARGET_CRS, always_xy=True)

    def _geojson_to_geom(self, geojson_dict: dict[str, Any]):
        """Convert a GeoJSON dict (Feature, FeatureCollection, or bare geometry) to a shapely geometry."""
        features = geojson_dict.get("features", [])
        if not features:
            if geojson_dict.get("type") in ["Feature", "Polygon", "MultiPolygon"]:
                features = [geojson_dict]
            else:
                raise ValueError("Invalid GeoJSON provided.")

        geometries = []
        for feat in features:
            geom = shape(feat["geometry"]) if "geometry" in feat else shape(feat)

            # Apply a micro-buffer to fix invalid geometries
            if not geom.is_valid:
                geom = geom.buffer(0)
            geometries.append(geom)

        return unary_union(geometries)

    def _project(self, geom):
        """Reproject a geometry from WGS84 to India Equal Area."""
        return transform(self._transformer.transform, geom)

    def calculate_split_areas(self, parent_geojson: dict[str, Any], child_geojson: dict[str, Any]) -> dict[str, float]:
        """
        Calculates the transferred area and remaining parent area in square kilometers
        using high-precision Indian Equal Area projection.
        """
        parent_geom = self._geojson_to_geom(parent_geojson)
        child_geom = self._geojson_to_geom(child_geojson)

        # Reproject to Equal Area (EPSG:7755)
        parent_proj = self._project(parent_geom)
        child_proj = self._project(child_geom)

        # Clean topology with buffer(0)
        parent_proj = parent_proj.buffer(0)
        child_proj = child_proj.buffer(0)

        # Calculate Transferred Area (Intersection)
        intersection_geom = parent_proj.intersection(child_proj).buffer(0)
        transferred_area_sqkm = intersection_geom.area / 1_000_000.0

        # Calculate Remaining Parent Area (Difference)
        remaining_geom = parent_proj.difference(child_proj).buffer(0)
        remaining_area_sqkm = remaining_geom.area / 1_000_000.0

        return {
            "transferred_area_sqkm": float(transferred_area_sqkm),
            "remaining_area_sqkm": float(remaining_area_sqkm),
        }
