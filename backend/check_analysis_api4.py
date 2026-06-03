import asyncio
from app.database import get_connection
from app.repositories.metric_repo import MetricRepository

async def main():
    async with get_connection() as conn:
        repo = MetricRepository(conn)
        variables = ["rice_area_kharif", "rice_production_kharif", "rice_yield_kharif"]
        cdks = ["TG_khamma_1961", "TG_mulugu_2024"]
        data_map = await repo.build_data_map(cdks, variables)
        print(f"Data map keys: {list(data_map.keys())}")
        if len(data_map) > 0:
            print("Sample year:", next(iter(data_map.values())))

asyncio.run(main())
