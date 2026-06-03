import asyncio
from app.database import get_connection
from app.services.analysis_service import AnalysisService

async def main():
    async with get_connection() as conn:
        service = AnalysisService(conn)
        print("Fetching split analysis for Khammam -> Mulugu (509 -> 720)...")
        # Khammam -> Mulugu split_year = 2019
        try:
            res = await service.analyze_split_impact(
                parent_cdk="509",
                children_cdks=["720"],
                split_year=2019,
                domain="agriculture",
                variable="rice_yield",
                mode="before_after",
                query_hash="test"
            )
            print(f"Data timeline length: {len(res.data)}")
            if len(res.data) > 0:
                print("First data point:", res.data[0])
                print("Last data point:", res.data[-1])
            else:
                print("No data points returned!")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(main())
