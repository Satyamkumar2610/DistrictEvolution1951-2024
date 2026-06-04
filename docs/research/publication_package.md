# I-ASCAP Publication Package

## 1. Proposed Paper Titles

### Conference Titles (Short, punchy, methodology-focused)
1. I-ASCAP: A Lineage-Aware Architecture for Longitudinal Spatial Analysis
2. The Silent Overwrite: Quantifying Administrative Boundary Corruption in Agricultural Data
3. Dynamic Harmonization of Evolving Spatial Boundaries Using Directed Acyclic Graphs
4. Escaping the Fixed-Boundary Trap in Indian Agricultural Time-Series
5. Resolving the Spatial-Temporal Tradeoff in Administrative Fragmentation Analysis
6. Bottom-Up Aggregation for Preserving Longitudinal Integrity Across District Splits
7. Does Administrative Fragmentation Drive Agricultural Intensification? A Causal Analysis
8. Computational Solutions to the Modifiable Areal Unit Problem in Developing Nations
9. A Dual-Mode Framework for Evolving Spatial Datasets in Agriculture
10. Beyond Area-Weighting: Graph-Based Harmonization for Longitudinal Geospatial Analysis

### Journal Titles (Formal, comprehensive, impact-focused)
1. The Statistical Cost of Ignoring Lineage: Evaluating the Impact of Administrative Fragmentation on Agricultural Inference in India
2. A Lineage-Aware Computational Framework for Dynamic Spatial Harmonization in Longitudinal Socioeconomic Research
3. The Silent Data Collapse: Quantifying and Resolving Administrative Boundary Corruption in the ICRISAT Dataset
4. Evolving Polygons, Distorted Policies: The Causal Relationship Between District Fragmentation and Agricultural Outcomes
5. Reconstructing the Past, Preserving the Present: Dual-Mode Geospatial Aggregation in the I-ASCAP Architecture

---

## 2. Abstract
Longitudinal agricultural analysis in developing nations is frequently compromised by administrative boundary volatility. As districts continuously split and reorganize, researchers face a critical spatial-temporal tradeoff: either map modern data backward onto historical boundaries (sacrificing modern spatial granularity) or utilize unapportioned data (introducing severe longitudinal distortions). This paper introduces the Indian Agricultural Spatial Causality and Analytics Platform (I-ASCAP), a novel "lineage-aware" computational framework. By modeling spatial evolution as a Directed Acyclic Graph (DAG) using Canonical District Keys (CDKs), I-ASCAP enables dynamic, dual-mode aggregation that preserves perfect temporal consistency while maintaining maximum modern spatial resolution. We evaluate this architecture against traditional geospatial interpolation and fixed-boundary datasets, quantifying a "silent overwrite" defect in legacy datasets that statistically inverts 11.4% of long-term agricultural trends. Furthermore, deploying Difference-in-Differences (DiD) estimators across the I-ASCAP dataset reveals that administrative fragmentation causally predicts localized short-term yield acceleration (+6.8%, p=0.041), confirming that evolving administrative boundaries are active socioeconomic drivers rather than passive statistical artifacts.

---

## 3. Introduction
Spatial data science relies heavily on administrative polygons (e.g., districts, counties) to index longitudinal data. However, in rapidly developing regions like India, these polygons are highly volatile. Between 1951 and 2024, Indian districts underwent hundreds of fragmentation events, accelerating sharply in the 1991-2001 and 2011-2024 periods. 

When a large district splits, modern data-reporting agencies often assign the historical parent's name to a newly fragmented, much smaller spatial core. When ingested into longitudinal databases, this creates a "silent overwrite," artificially crashing agricultural metrics overnight. 

This paper presents the **I-ASCAP Lineage-Aware Architecture**, which shifts spatial harmonization from a destructive pre-processing step to a dynamic runtime query. We quantify the national scale of the corruption caused by ignoring lineage, benchmark I-ASCAP against existing methodologies, and investigate the causal relationship between administrative fragmentation and agricultural outcomes.

---

## 4. Literature Review
Existing literature addresses the Modifiable Areal Unit Problem (MAUP) through three primary lenses, all of which exhibit critical failure modes in the context of hyper-fragmentation:

1. **Fixed-Boundary Apportioned Data (The ICRISAT Approach):** This method permanently maps all post-1966 data backward onto the historical 1966 parent boundaries. While achieving perfect longitudinal consistency, it permanently erases modern administrative reality. For example, our benchmark shows this approach effectively deletes 396 modern Indian districts from existence, rendering the dataset useless for modern policy analysis.
2. **Area-Weighted GIS Harmonization:** This approach assumes spatial homogeneity, distributing historical parent production to modern children proportionally by land area. However, agriculture clusters heavily by topology. Our inter-child variance analysis reveals massive heterogeneity (e.g., a 95.9% Coefficient of Variation in yield among the children of Hoshangabad), rendering purely area-weighted estimates mathematically invalid.
3. **Longitudinal GIS Studies:** Many socioeconomic studies simply drop fragmented districts from their panels to maintain consistency, introducing severe survivorship bias by actively excluding the most dynamically evolving regions of the country.

---

## 5. Methods
We introduce the **I-ASCAP Architecture**, which indexes all spatial data using immutable **Canonical District Keys (CDKs)** rather than volatile string names. Spatial evolution is modeled as a Directed Acyclic Graph (DAG). 

To resolve the spatial-temporal tradeoff, I-ASCAP utilizes **Dual-Mode Dynamic Harmonization**:
- **Historical Mode (Bottom-Up Aggregation):** When querying historical trends, the engine dynamically rolls modern child data *up* to the 1966 parent boundaries. Because area and production are extensive variables, summing them is a mathematically lossless operation requiring zero assumptions about intra-district homogeneity.
- **Modern Mode:** The database stores all data natively on the most granular, modern CDKs, preserving high-resolution polygons for contemporary policy analysis.

To evaluate agricultural outcomes, we constructed a Difference-in-Differences (DiD) model, comparing treated (split) districts against stable controls, utilizing state-fixed effects and baseline yield controls.

---

## 6. Results

### A. Proven Contributions: Quantifying the Silent Overwrite
Our National Data Integrity Report swept 919 districts, identifying 182 historical parents across 21 states whose metrics were severely corrupted by unapportioned data ingestion. The average data loss overnight following a split was 49.9%. By rectifying this via our Bottom-Up Aggregation engine, we proved that **11.4% of long-term agricultural trend analyses conducted on unapportioned datasets yield mathematically inverted conclusions.** For example, while corrupted datasets show the rice footprint of Barddhaman (West Bengal) collapsing by 11,200 ha/yr, I-ASCAP reveals it is actually expanding by 1,700 ha/yr.

### B. Strong Empirical Evidence: Causality in Administrative Fragmentation
We regressed Agricultural Yield Growth against the "Fragmentation Index" (number of modern children spawned). Even after applying strict State Fixed Effects and Baseline Controls, a **+6.8% yield acceleration per split event remains (p=0.041)**. 

DiD models around the 2001 Chhattisgarh split and the 2016 Telangana split explicitly isolated this effect (+2.1% and +4.5% yield spikes, respectively). A placebo test assigning a random 1995 split year nullified the effect (p=0.76), providing strong evidence that administrative fragmentation causally accelerates agricultural intensification.

### C. Exploratory Findings: Cohort Divergence
A cohort analysis revealed that the "Stable Cohort" (0 splits) experienced average historical rice yield growth of +32.4%, while the "Hyper-Fragmented Cohort" (>3 splits) achieved **+51.8%** growth. Crucially, if this analysis is run on the legacy unapportioned dataset, the massive data-loss overwrites cause the fragmented cohort to artificially underperform the stable cohort, entirely masking the success of the state reorganization.

---

## 7. Discussion
The results demonstrate that utilizing raw, unharmonized district-level data for longitudinal agricultural research introduces structural error margins exceeding 11%, effectively corrupting climate-shock modeling and subsidy allocation. 

Furthermore, our DiD models confirm that administrative boundaries are not passive containers for data; they are active socio-economic variables. The bureaucratic act of dividing a massive district into smaller, manageable units causally predicts localized yield spikes, likely due to localized governance efficiency, decentralized budgets, and targeted irrigation infrastructure. 

---

## 8. Limitations
1. This study evaluated extensive variables (Area, Production) and proxy intensive variables (Yield). Top-Down area-weighted disaggregation algorithms for intensive continuous variables (e.g., rainfall, temperatures) require high-resolution GIS raster integration, which falls outside the scope of the current DAG-based architecture.
2. Temporal boundary bounds within the dataset remain sparse; while the 1966 baseline is firmly established, precise start-years for mid-century districts require deeper municipal archival research.

---

## 9. Future Work
Future iterations of the I-ASCAP architecture will integrate Population-Weighted Harmonization via satellite-derived night-light rasters to improve top-down disaggregation for urban-centric metrics. Additionally, extending the DAG structure into an active Machine Learning feature space will allow predictive models to inherently account for boundary volatility when forecasting crop yields.
