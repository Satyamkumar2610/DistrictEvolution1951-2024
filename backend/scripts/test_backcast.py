import asyncio

from app.database import get_pool
from app.services.advanced_analytics_service import AdvancedAnalyticsFacade


async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Testing Backcast...")
        service = AdvancedAnalyticsFacade(conn)

        # We need a parent which split into kids.
        # Warangal -> Warangal Rural, Warangal Urban, Jayashankar Bhupalpally, Mahabubabad, Jangaon, Mulugu
        # Wait, let's use a simpler one.
        # Adilabad -> Adilabad, Kumuram Bheem, Mancherial, Nirmal (Split year 2016 for Telangana districts usually 2014, but districts split in 2016)
        # Let's use Adilabad split
        # Let's query split events first

        splits = await conn.fetch("SELECT * FROM split_events WHERE parent_cdk LIKE 'TG_%' LIMIT 1")
        if not splits:
            print("No splits found.")
            return

        parent_cdk = splits[0]['parent_cdk']
        split_year = splits[0]['split_year']

        # Get children array
        child_cdks = splits[0]['child_cdks']

        print(f"Parent: {parent_cdk}, Split: {split_year}")
        print(f"Children: {child_cdks}")

        try:
             res = await service.get_backcast_response(
                 parent_cdk=parent_cdk,
                 child_cdks=child_cdks,
                 split_year=split_year,
                 crop="rice",
                 start_year=2010
             )
             print("\n--- Success! ---")
             print(res.model_dump_json(indent=2))
        except Exception as e:
             print(f"Error during backcast: {e}")

if __name__ == '__main__':
    asyncio.run(main())
