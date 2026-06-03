import asyncio
from app.database import get_connection
from app.services.analysis_service import AnalysisService

async def main():
    async with get_connection() as conn:
        service = AnalysisService(conn)
        print("Fetching split events for Telangana...")
        events = await service.get_resolved_split_events_for_state("Telangana")
        print(f"Got {len(events)} events")
        for event in events:
            print(event.parent_name, "->", event.children_names)
        
        print("\nFetching split events for Andhra Pradesh...")
        events = await service.get_resolved_split_events_for_state("Andhra Pradesh")
        print(f"Got {len(events)} events")

asyncio.run(main())
