from typing import Any

import geopandas as gpd
from shapely.geometry import shape


class GeometryService:
    def __init__(self):
        # EPSG:7755 is the standard India Equal Area projection suitable for
        # accurate sq km calculations
        self.TARGET_CRS = "EPSG:7755"
        self.SOURCE_CRS = "EPSG:4326"

    def _dict_to_gdf(self, geojson_dict: dict[str, Any]) -> gpd.GeoDataFrame:
        features = geojson_dict.get("features", [])
        if not features:
            if geojson_dict.get("type") in [
                    "Feature", "Polygon", "MultiPolygon"]:
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

        gdf = gpd.GeoDataFrame(geometry=geometries, crs=self.SOURCE_CRS)
        return gdf

    def calculate_split_areas(self,
                              parent_geojson: dict[str,
                                                   Any],
                              child_geojson: dict[str,
                                                  Any]) -> dict[str,
                                                                float]:
        """
        Calculates the transferred area and remaining parent area in square kilometers
        using high-precision Indian Equal Area projection.
        """
        # Convert to GeoDataFrames
        parent_gdf = self._dict_to_gdf(parent_geojson)
        child_gdf = self._dict_to_gdf(child_geojson)

        # Reproject to Equal Area (EPSG:7755)
        parent_proj = parent_gdf.to_crs(self.TARGET_CRS)
        child_proj = child_gdf.to_crs(self.TARGET_CRS)

        # Dissolve into single geometries if there are multiple parts
        parent_geom = parent_proj.geometry.unary_union
        child_geom = child_proj.geometry.unary_union

        # Clean topology with buffer(0)
        parent_geom = parent_geom.buffer(0)
        child_geom = child_geom.buffer(0)

        # Calculate Transferred Area (Intersection)
        intersection_geom = parent_geom.intersection(child_geom)

        # Determine valid slivers (buffer 0 to clean artifacts from
        # intersection)
        intersection_geom = intersection_geom.buffer(0)

        transferred_area_sqm = intersection_geom.area
        transferred_area_sqkm = transferred_area_sqm / 1_000_000.0

        # Calculate Remaining Parent Area (Difference)
        remaining_geom = parent_geom.difference(child_geom)
        remaining_geom = remaining_geom.buffer(0)

        remaining_area_sqm = remaining_geom.area
        remaining_area_sqkm = remaining_area_sqm / 1_000_000.0

        return {
            "transferred_area_sqkm": float(transferred_area_sqkm),
            "remaining_area_sqkm": float(remaining_area_sqkm)
        }
