import asyncio
from app.database import get_connection
from app.services.analysis_service import AnalysisService

async def main():
    async with get_connection() as conn:
        service = AnalysisService(conn)
        print("Fetching split analysis for Khammam -> Mulugu (TG_khamma_1961 -> TG_mulugu_2024)...")
        try:
            res = await service.analyze_split_impact(
                parent_cdk="TG_khamma_1961",
                children_cdks=["TG_mulugu_2024"],
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
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(main())
