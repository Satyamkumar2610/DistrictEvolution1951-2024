# Migration Impact Report: 641-Polygon vs 663-Polygon (Bhuvan)

This report evaluates the potential migration from the current `districts.json` (641 polygons) to the newly uploaded `bhuvan_districts.geojsonl` (663 polygons).

## 1. Top-Level Geometry Changes
- **Current Geometry:** 641 polygons
- **Proposed Geometry:** 663 polygons
- **Net Addition:** 22 geometries
- **Naming Volatility:** 162 district/state keys underwent spelling or state-alignment changes (e.g., "Odisha" → "Orissa", or mapping Kashmir districts to "Union Territory of Jammu and Kashmir").

## 2. Which 22 additional districts exist?
The 22 net-new geometries are primarily a result of state-specific administrative updates outside of the core ICRISAT focus states. Key additions include:
- **Jammu & Kashmir / Ladakh Restructuring:** E.g., *Gilgit, Kargil, Leh, Jammu, Srinagar*.
- **North-Eastern Additions:** E.g., *East Kameng, Dibang Valley (Arunachal Pradesh); North, South, West (Tripura)*.
- **Scattered Splits:** E.g., *Palghar (Maharashtra), Shamli, Hapur (UP), Balod, Bemetara, Sukma (Chhattisgarh)*.

## 3. Which Telangana districts become newly available?
**None.** 
The 663-polygon Bhuvan dataset **still utilizes the historical 10-district macro boundaries** for Telangana. It does NOT contain geometries for the 33 modern Telangana districts (e.g., *Nirmal, Kamareddy, Bhadradri* are completely missing). 
The only changes in Telangana/AP were spelling variations (e.g., *Visakhapatnam* → *Visakhapatanam*, *S.P.S. Nellore* → *Spsr nellore*).

## 4. Does it improve modern-mode coverage?
**Marginally for minor states, but it fails for the primary analytical targets (Telangana/AP).**
While it successfully maps a few post-2011 splits in Chhattisgarh and Maharashtra, it entirely lacks the critical 2016 Telangana reorganization boundaries. Switching to this map will **not** allow Modern Mode to render the 33 Telangana districts natively. We would still have to rely on Bottom-Up Aggregation to project them onto the 10 macro polygons.

## 5. Lineage Mapping Impact
If we migrate to the 663-polygon file:
1. We would have to rebuild `map_bridge.json` from scratch to accommodate the 162 naming variations (e.g., tracking down `Spsr nellore` instead of `S.P.S. Nellore`).
2. We would need to remap the new Chhattisgarh splits (Sukma, Balod, Bemetara) to their respective CDKs to prevent them from becoming unmapped gaps.

## Recommendation
**Hold off on immediate replacement.**
The 663-polygon Bhuvan geometry introduces massive naming volatility (162 key changes) for a net gain of 22 districts, while fundamentally failing to solve the primary Modern-Mode problem: it lacks the 33 Telangana district geometries. 

The current 641-polygon map, with our newly applied 100% mapping patch and Bottom-Up Aggregation engine, is mathematically superior and far more stable for the ICRISAT dataset. I recommend waiting until a definitive 2024 GeoJSON (containing all 700+ modern districts) is acquired before performing a geometry migration.
