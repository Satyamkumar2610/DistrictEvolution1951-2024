import asyncio
from app.repositories.metric_repo import MetricRepository
from app.database import get_connection

async def main():
    async with get_connection() as conn:
        repo = MetricRepository(conn)
        res = await repo.get_by_year_and_variable(2013, "rice_yield")
        print(f"Got {len(res)} results")

asyncio.run(main())
