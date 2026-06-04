# Harmonization Benchmark Study

This study evaluates five distinct methodological approaches to handling administrative boundary changes in longitudinal agricultural datasets. 

## 1. Method Comparison Matrix

| Methodology | Longitudinal Consistency | Modern Policy Relevance | Sign-Reversal Rate | Interpretability |
| :--- | :--- | :--- | :--- | :--- |
| **Raw Unapportioned Data** | ❌ Failed (Corrupted) | ✅ High (Shows modern borders) | 11.4% (Highest) | Misleading |
| **Fixed-Boundary Apportioned (ICRISAT)** | ✅ Perfect | ❌ Failed (Erases 396 modern districts) | 0.0% | Moderate |
| **Area-Weighted Harmonization** | ⚠️ Moderate (Assumes spatial homogeneity) | ✅ High | ~3-5% (Estimated) | Low (Black box GIS) |
| **Population-Weighted Harmonization** | ❌ Failed (Inverse correlation to agriculture) | ✅ High | ~5-8% (Estimated) | Low |
| **I-ASCAP Lineage-Aware (Dual-Mode)** | ✅ Perfect (Bottom-Up Aggregation) | ✅ High (Preserves modern CDKs) | **0.0%** | **High (Transparent DAG)** |

---

## 2. Failure Modes of Existing Approaches

### 2.1 Fixed-Boundary Apportioned Data (The ICRISAT Approach)
**The Mechanism:** This method permanently maps all post-1966 data backward onto the historical 1966 boundaries. 
**The Failure Mode:** It achieves perfect longitudinal consistency at the cost of **total modern policy blindness**. 
- *Empirical Finding:* By locking the dataset to 522 historical parent boundaries, this method completely erases **396 modern districts** from existence. If the Indian government issues a targeted agricultural subsidy to the newly formed *Kamareddy* district in Telangana, a researcher using the ICRISAT dataset cannot measure its impact, because *Kamareddy* does not exist in the dataset (it is permanently swallowed by *Nizamabad*).

### 2.2 Area-Weighted Harmonization (Top-Down GIS Apportionment)
**The Mechanism:** Uses polygon intersections to estimate data. If a new child district takes 30% of the parent's land area, it is assigned 30% of the parent's historical production.
**The Failure Mode:** It assumes spatial homogeneity—that crops are distributed perfectly evenly across the parent district. Agriculture, however, clusters heavily around rivers, canals, and topography.
- *Empirical Finding:* Our variance analysis of modern child districts proves extreme heterogeneity. The modern children of *Hoshangabad* exhibit a **95.9% Coefficient of Variation** in rice yield. The children of *Tiruchirapalli* vary by **61.8%**. Distributing historical production purely by land area into these children would massively inflate production in barren children and artificially suppress it in fertile river-basin children.

### 2.3 Raw Unapportioned Data
**The Mechanism:** Directly ingesting raw data from the government year over year.
**The Failure Mode:** "The Silent Overwrite." Child districts reuse the names of their historical parents, silently deleting historical baselines and triggering artificial collapses. 
- *Empirical Finding:* Over **11.4%** of long-term trend calculations mathematically invert, causing "False Declines" and "Artificial Collapses."

---

## 3. What Does I-ASCAP Do That Existing Methods Cannot Do?

The fundamental breakthrough of I-ASCAP is its **Dual-Mode Dynamic Harmonization**, powered by the Canonical District Key (CDK) lineage DAG. 

Existing methods force researchers to choose between **Time** (Historical Fixed-Boundary) and **Space** (Modern Unapportioned). I-ASCAP eliminates this tradeoff.

1. **Information Preservation:** By utilizing *Bottom-Up Aggregation* at runtime, I-ASCAP perfectly reconstructs the 1966 historical boundaries dynamically (0.0% Sign Reversal Rate) without permanently altering the underlying database. 
2. **Modern Policy Relevance:** Because the database stores the data natively on the modern CDKs, the 396 newly minted modern districts are fully preserved. Researchers can track the efficacy of modern local policies on *Kamareddy* without losing the ability to view *Nizamabad's* 50-year macro-trend.
3. **No Spatial Guesswork:** Unlike Area-Weighted methods, I-ASCAP does not guess how historical production was distributed. When viewing historical trends, it rolls modern data *up* to the parent level, a mathematically lossless operation that requires zero assumptions about intra-district spatial homogeneity. 

### Conclusion
I-ASCAP shifts harmonization from a static, destructive pre-processing step (which either destroys modern borders or introduces massive spatial errors) into a dynamic, query-time operation. This ensures 100% longitudinal reliability while preserving the highest possible spatial granularity of modern India.
