
import asyncio
from typing import Any

from arq.connections import RedisSettings

from app.config import get_settings
from app.database import close_db_pool, init_db_pool
from app.logging_config import get_logger

# Import tasks here (to be implemented)
# from app.analytics.tasks import recalculate_lineage_task

settings = get_settings()
logger = get_logger("worker")


async def startup(ctx: dict[str, Any]):
    """Initialize resources for the worker."""
    logger.info("Worker starting up...")
    ctx["db_pool"] = await init_db_pool()
    logger.info("Worker DB pool initialized.")


async def shutdown(ctx: dict[str, Any]):
    """Cleanup resources."""
    logger.info("Worker shutting down...")
    await close_db_pool()
    logger.info("Worker DB pool closed.")


async def test_task(ctx: dict[str, Any], word: str) -> str:
    """Simple test task."""
    logger.info(f"Test task received: {word}")
    await asyncio.sleep(1)
    return f"processed {word}"


class WorkerSettings:
    """
    ARQ Worker Settings.
    """
    functions = [test_task]

    # Parse Redis URL
    # arq expects RedisSettings object or kwargs
    # We need to parse "redis://host:port/db" manually or use from_dsn if supported
    # RedisSettings.from_dsn(settings.redis_url) is the way.
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    poll_delay = 0.5
