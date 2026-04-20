# Counterfactual Disaggregation Methodology

This dataset distinguishes three different confidence layers:

- Lineage certainty: confidence that the administrative event and parent-child relationship are correct.
- Weight certainty: confidence that parent totals can be distributed across children using the available transfer weights.
- Model certainty: confidence in harmonized panel values or backcast estimates used to fill missing child series.

Public point confidence is conservative by design. The API uses the minimum of those signals rather than averaging them away.

Metric policy:

- `area` and `production` are treated as extensive quantities and can be distributed using child weights.
- `yield` is never split directly. It is derived from estimated `production / area` whenever both are available.
- If one of those extensive components is unavailable, the API falls back to the existing yield backcast engine.
- If even that is unavailable, the API exposes a clearly labeled `parent_yield_passthrough` fallback with low confidence.

Tier semantics:

- `Tier A`: official lineage plus official or geometry-derived weights.
- `Tier B`: official lineage plus proxy or fallback weights.
- `Tier C`: metadata-only packet with no released child series.
