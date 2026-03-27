"""
Dependency Injection for API Routes.
Provides database connections, provenance generators, and common utilities.
"""
import hashlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import asyncpg
from fastapi import Request

from app.config import get_settings
from app.database import get_connection
from app.schemas.common import ProvenanceMetadata

settings = get_settings()


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """Database connection dependency."""
    async with get_connection() as conn:
        yield conn


def generate_provenance(
        request: Request,
        method: str = None) -> ProvenanceMetadata:
    """
    Generate reproducibility metadata for API responses.

    Args:
        request: The incoming HTTP request
        method: Optional harmonization method used

    Returns:
        ProvenanceMetadata with dataset version, query hash, and timestamp
    """
    # Normalize and hash query params
    query_string = str(sorted(request.query_params.items()))
    query_hash = f"sha256:{hashlib.sha256(query_string.encode()).hexdigest()[:16]}"

    return ProvenanceMetadata(
        dataset_version=settings.dataset_version,
        boundary_version=settings.boundary_version,
        query_hash=query_hash,
        generated_at=datetime.now(UTC),
        harmonization_method=method,
        warnings=[],
    )
