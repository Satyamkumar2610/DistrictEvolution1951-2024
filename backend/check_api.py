import asyncio
from app.repositories.metric_repo import MetricRepository

async def main():
    repo = MetricRepository()
    # Try calling get_by_year_and_variable which is used for the map
    print("Fetching 2013 rice_yield...")
    res = await repo.get_by_year_and_variable(2013, "rice_yield")
    print(f"Got {len(res)} results")
    if len(res) > 0:
        print(res[0])

asyncio.run(main())
