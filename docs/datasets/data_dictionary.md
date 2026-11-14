# Data dictionary

Template for every dataset used. A table is added when the dataset is first ingested. No dataset exists yet.

## Template

| Variable | Type | Unit | Source | Description | Missing-value handling |
|---|---|---|---|---|---|
| `example_variable` | float | µg/m³ | Source name | What it measures and how | Rule |

## Conventions (planned)

- Timestamps are timezone-aware, stored in UTC, and converted to local time (Asia/Tashkent) only for presentation or calendar features.
- Column names are `snake_case` with the unit where ambiguity is possible.
- Each row-level record keeps a `source` and a `value_type` (measured, estimated, predicted).

## Datasets

_None documented yet._
