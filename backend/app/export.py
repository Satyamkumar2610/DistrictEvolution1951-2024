"""
Data export utilities for I-ASCAP.
Provides functions to export data in various formats.
"""

import csv
import io
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from fastapi import Response
from fastapi.responses import StreamingResponse


@dataclass
class ExportMetadata:
    """Metadata for exported data."""
    exported_at: str
    source: str = "I-ASCAP API"
    version: str = "1.0"
    record_count: int = 0
    filters: dict[str, Any] | None = None


class DataExporter:
    """
    Export data in various formats.
    """

    def __init__(self, source: str = "I-ASCAP API"):
        self.source = source

    def _create_metadata(
        self,
        record_count: int,
        filters: dict[str, Any] | None = None
    ) -> ExportMetadata:
        """Create export metadata."""
        return ExportMetadata(
            exported_at=datetime.utcnow().isoformat() + "Z",
            source=self.source,
            record_count=record_count,
            filters=filters,
        )

    # -------------------------------------------------------------------------
    # JSON Export
    # -------------------------------------------------------------------------

    def to_json(
        self,
        data: list[dict[str, Any]],
        include_metadata: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Export data as JSON string."""
        output: Any
        if include_metadata:
            metadata = self._create_metadata(len(data), filters)
            output = {
                "metadata": asdict(metadata),  # type: ignore
                "data": data,
            }
        else:
            output = data

        return json.dumps(output, indent=2, default=str)

    def to_json_response(
        self,
        data: list[dict[str, Any]],
        filename: str = "export.json",
        filters: dict[str, Any] | None = None,
    ) -> Response:
        """Export data as JSON download response."""
        content = self.to_json(data, include_metadata=True, filters=filters)

        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            }
        )

    # -------------------------------------------------------------------------
    # CSV Export
    # -------------------------------------------------------------------------

    def to_csv(
        self,
        data: list[dict[str, Any]],
        columns: list[str] | None = None,
    ) -> str:
        """Export data as CSV string."""
        if not data:
            return ""

        # Determine columns
        if columns is None:
            columns = list(data[0].keys())

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=columns,
            extrasaction='ignore')
        writer.writeheader()

        for row in data:
            # Convert any complex types to strings
            cleaned_row: dict[str, Any] = {}
            for key, value in row.items():
                if key in columns:
                    if isinstance(value, (dict, list)):
                        cleaned_row[key] = json.dumps(value)
                    else:
                        cleaned_row[key] = value
            writer.writerow(cleaned_row)

        return output.getvalue()

    def to_csv_response(
        self,
        data: list[dict[str, Any]],
        filename: str = "export.csv",
        columns: list[str] | None = None,
    ) -> Response:
        """Export data as CSV download response."""
        content = self.to_csv(data, columns)

        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            }
        )

    # -------------------------------------------------------------------------
    # GeoJSON Export
    # -------------------------------------------------------------------------

    def to_geojson(
        self,
        features: list[dict[str, Any]],
        properties_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Export data as GeoJSON FeatureCollection.

        Args:
            features: List of feature dicts with geometry and properties
            properties_map: Optional mapping of property names
        """
        geojson: dict[str, Any] = {
            "type": "FeatureCollection",
            "features": [],
            "metadata": asdict(self._create_metadata(len(features))),  # type: ignore
        }

        for f in features:
            feature = {
                "type": "Feature",
                "geometry": f.get("geometry"),
                "properties": f.get("properties", {}),
            }
            if "id" in f:
                feature["id"] = f["id"]

            geojson["features"].append(feature)

        return geojson

    def to_geojson_response(
        self,
        features: list[dict[str, Any]],
        filename: str = "export.geojson",
    ) -> Response:
        """Export data as GeoJSON download response."""
        content = json.dumps(self.to_geojson(features), indent=2)

        return Response(
            content=content,
            media_type="application/geo+json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            }
        )

    # -------------------------------------------------------------------------
    # Streaming Export (for large datasets)
    # -------------------------------------------------------------------------

    def stream_csv(
        self,
        data_generator,
        columns: list[str],
        filename: str = "export.csv",
    ) -> StreamingResponse:
        """
        Stream CSV data for large exports.

        Args:
            data_generator: Async generator yielding row dicts
            columns: Column names for header
            filename: Download filename
        """
        async def generate():
            # Write header
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            yield output.getvalue()

            # Stream rows
            async for row in data_generator:
                output = io.StringIO()
                writer = csv.DictWriter(
                    output, fieldnames=columns, extrasaction='ignore')
                cleaned_row: dict[str, Any] = {}
                for key, value in row.items():
                    if key in columns:
                        if isinstance(value, (dict, list)):
                            cleaned_row[key] = json.dumps(value)  # type: ignore
                        else:
                            cleaned_row[key] = value  # type: ignore
                writer.writerow(cleaned_row)
                yield output.getvalue()

        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            }
        )


# Convenience function
def get_exporter(source: str = "I-ASCAP API") -> DataExporter:
    """Get a data exporter instance."""
    return DataExporter(source)


# Pre-defined column sets for common exports
class ExportColumns:
    """Standard column sets for exports."""

    DISTRICT_BASIC = ["cdk", "name", "state", "valid_from", "valid_to"]

    DISTRICT_FULL = [
        "cdk", "name", "state", "valid_from", "valid_to",
        "parent_cdk", "is_current", "area_km2",
    ]

    METRICS = [
        "year", "cdk", "district_name", "state",
        "crop", "area", "production", "yield",
    ]

    ANALYSIS = [
        "year", "parent_value", "child_combined_value",
        "difference", "percent_change",
    ]

    SUMMARY = [
        "state", "total_districts", "boundary_changes",
        "first_year", "last_year",
    ]
