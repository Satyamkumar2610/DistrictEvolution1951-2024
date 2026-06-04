# Unmapped Polygons Diagnostic Report

The frontend GeoJSON (`districts.json`) contains 641 district boundaries. The strict mapping engine successfully mapped 627 polygons (97.8% coverage). 

This report details the 14 unmapped geometries, the reasons for their mapping failure, and the exact patch required to reach 100% geometry utilization.

## 1. Unmapped Polygons Analysis

| Geometry (DISTRICT\|STATE) | Closest Database Match | Failure Reason | Recommended CDK |
| :--- | :--- | :--- | :--- |
| **Chikkaballapura\|Karnataka** | *None / Chikmagalur (0.69)* | **Split:** Chikkaballapura was carved out of Kolar in 2007. Since the map is 2011, it has the split geometry. The historical ICRISAT data tracks the parent (Kolar). | `KA_kolar_2001` (Parent) |
| **Chitradurga\|Karnataka** | Chitaldrug (0.67) | **Spelling Variation:** Traditional name 'Chitaldrug' vs modern 'Chitradurga'. | `KA_chitra_1951` |
| **Jalgaon\|Maharashtra** | East Khandesh (0.0) | **Renamed District:** Jalgaon was historically known as East Khandesh in older census records. | `MH_jalgao_1951` |
| **Kamrup Metropolitan\|Assam** | Kamrup (0.48) | **Split:** Kamrup Metropolitan was carved from Kamrup. | `AS_kamrup_1981` (Parent) |
| **Kanpur Dehat\|Uttar Pradesh** | Kanpur (0.67) | **Split:** Kanpur was split into Nagar and Dehat. | `UP_kanpur_1951` (Parent) |
| **Kolkata\|West Bengal** | Calcutta (0.40) | **Spelling Variation / Rename:** Classic Calcutta vs Kolkata. | `WB_kolkat_1951` |
| **Kollam\|Kerala** | Quilon (0.17) | **Renamed District:** Quilon was anglicized to Kollam. | `KL_kollam_1951` |
| **Mumbai Suburban\|Maharashtra** | Greater Bombay (0.41) | **Split / Rename:** Split from the historical Greater Bombay / Mumbai entity. | `MH_greate_1991` (Parent) |
| **Pune\|Maharashtra** | Poona (0.44) | **Spelling Variation / Rename:** Poona vs Pune. | `MH_pune_1951` |
| **Satara\|Maharashtra** | Satara North (0.67) | **Rename:** Historically recorded as Satara North. | `MH_satara_1951` |
| **Thanjavur\|Tamil Nadu** | Tanjore (0.62) | **Spelling Variation / Rename:** Tanjore vs Thanjavur. | `TN_thanja_1951` |
| **Thiruvananthapuram\|Kerala** | Trivandrum (0.50) | **Spelling Variation / Rename:** Trivandrum vs Thiruvananthapuram. | `KL_thiruv_1951` |
| **Thrissur\|Kerala** | Trichur (0.67) | **Spelling Variation / Rename:** Trichur vs Thrissur. | `KL_thriss_1951` |
| **Tiruvannamalai\|Tamil Nadu** | Tiruvannamalai Sambuvarayar (0.68) | **Rename:** Dropped the 'Sambuvarayar' suffix. | `TN_tiruva_1991` |

---

## 2. Map Bridge Patch Generation

To resolve the 14 missing polygons and achieve 641/641 coverage, the following JSON block should be merged into `map_bridge.json`.

```json
{
  "Chikkaballapura|Karnataka": "KA_kolar_2001",
  "Chitradurga|Karnataka": "KA_chitra_1951",
  "Jalgaon|Maharashtra": "MH_jalgao_1951",
  "Kamrup Metropolitan|Assam": "AS_kamrup_1981",
  "Kanpur Dehat|Uttar Pradesh": "UP_kanpur_1951",
  "Kolkata|West Bengal": "WB_kolkat_1951",
  "Kollam|Kerala": "KL_kollam_1951",
  "Mumbai Suburban|Maharashtra": "MH_greate_1991",
  "Pune|Maharashtra": "MH_pune_1951",
  "Satara|Maharashtra": "MH_satara_1951",
  "Thanjavur|Tamil Nadu": "TN_thanja_1951",
  "Thiruvananthapuram|Kerala": "KL_thiruv_1951",
  "Thrissur|Kerala": "KL_thriss_1951",
  "Tiruvannamalai|Tamil Nadu": "TN_tiruva_1991"
}
```

## 3. Migration Impact Note (663-Polygon Bhuvan Geometry)

> [!WARNING]
> You mentioned an "uploaded 663-polygon geometry" (likely from Bhuvan) to compare against. **This file does not appear to be present in the workspace.** 
> 
> Please ensure the file is uploaded to the `/data` or `/frontend/public/data` directory so I can generate the requested Migration Impact Report and determine the viability of replacing the 641-polygon layer.
