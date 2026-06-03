import asyncio
from app.database import get_connection
from app.services.analysis_service import AnalysisService

async def main():
    async with get_connection() as conn:
        service = AnalysisService(conn)
        print("Fetching split events for Telangana...")
        events = await service.get_resolved_split_events_for_state("Telangana")
        for event in events:
            print(f"{event.parent_name} ({event.parent_cdk}) -> {list(zip(event.children_names, event.children_cdks))}")

asyncio.run(main())
