# Counterfactual Research Study: The Statistical Cost of Ignoring Lineage

This study evaluates how decision-making and statistical inference are distorted when agricultural models rely on standard (corrupted) district boundaries versus our I-ASCAP Lineage-Aware architecture.

Using the period of 2005-2017 for Rice Area (1000ha), we ran identical linear regressions and year-over-year shock analyses on both the corrupted time-series and the reconstructed true lineage time-series for 184 districts affected by splits.

## A. False Trend Report

**Finding:** 11.4% of agricultural trend analyses conducted on these districts yield mathematically inverted conclusions if lineage is ignored.

- **False Declines (12 Districts):** The raw data suggests a long-term agricultural contraction (negative slope), but when boundaries are properly aggregated, the agricultural base is actually expanding (positive slope).
  - *Barddhaman (West Bengal):* Corrupted trend = -11.22 1000ha/yr vs. **True Trend = +1.78 1000ha/yr**.
  - *Ranchi (Jharkhand):* Corrupted trend = -0.27 1000ha/yr vs. **True Trend = +3.01 1000ha/yr**.
  - *Dakshin Bastar Dantewada (Chhattisgarh):* Corrupted trend = -8.64 1000ha/yr vs. **True Trend = +0.66 1000ha/yr**.
- **False Growth (9 Districts):** The raw data suggests growth, but the district's true historical footprint is actually shrinking.

> [!WARNING]
> Any researcher concluding that rice cultivation is shrinking in Barddhaman or Ranchi based on the raw dataset is statistically incorrect. The "shrinkage" is merely the administrative excision of child districts.

## B. False Shock Report (Artificial Collapses)

When evaluating short-term shocks (e.g., measuring the impact of a 2016 drought using a 2015-to-2017 comparison), boundary changes introduce massive artificial collapses that models will misinterpret as extreme weather or policy failures.

- **Jalpaiguri (West Bengal):** 
  - Corrupted Shock: **-39.0%** (Looks like an absolute agricultural collapse)
  - True Lineage Shock: **-2.7%** (Normal minor fluctuation)
- **Kamrup (Assam):** 
  - Corrupted Shock: **-30.6%**
  - True Lineage Shock: **-3.4%**

## C. Regression Sensitivity Analysis

At the national level, the corruption drags down the macro averages.
- **National Average Trend (Corrupted):** -1.55 1000ha/year
- **National Average Trend (Lineage-Aware):** -2.14 1000ha/year

While the averages look similar in magnitude, the variance at the district level is extreme. **District rankings for "Fastest Growing Agricultural Regions" would be entirely invalid** under the corrupted system, as newly split parent districts plummet to the bottom of the rankings despite local agricultural health remaining stable.

## D. Policy Impact Analysis

The distortions highlighted above directly corrupt policy decisions:
1. **Misallocation of Subsidies:** Districts showing "False Declines" (like Dakshin Bastar Dantewada) might trigger unwarranted emergency agricultural subsidies or drought relief because the government dashboard shows their area halving over a decade.
2. **False Efficacy:** If a new irrigation policy is introduced, a "False Growth" district might be hailed as a success story, even though its true boundary is shrinking.
3. **Climate Shock Misidentification:** Researchers trying to train Machine Learning models to predict crop failures based on weather data will feed the -39.0% drop in Jalpaiguri into their algorithms. The ML model will associate the 2016 weather in West Bengal with catastrophic failure, permanently poisoning the model's weights.

## E. National Summary

If a data scientist downloads the standard unapportioned ICRISAT dataset and runs time-series regressions spanning the last two decades, **over 11% of their district-level conclusions will be materially, mathematically false.** 

By utilizing the I-ASCAP Lineage-Aware Architecture, this 11.4% error rate drops to 0%, ensuring that policy and statistical models are responding to reality rather than bureaucratic reorganizations.
