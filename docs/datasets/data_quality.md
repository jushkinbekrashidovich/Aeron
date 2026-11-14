# Data quality

Findings are recorded here as they are produced by `research/notebooks/02_data_quality_assessment.ipynb` and the validation code. Nothing has been assessed yet.

## Checks planned for each dataset

| Check | What it detects |
|---|---|
| Coverage per station | First/last timestamp, station lifetime |
| Missingness | Share missing by hour, month, station; length of gaps |
| Duplicates | Repeated timestamps or stations |
| Range validity | Negative or physically implausible values |
| Stuck or flat sensor | Long runs of identical values |
| Spikes | Sudden jumps inconsistent with neighbors |
| Cross-source consistency | Disagreement between stations or sources |
| Time-zone and resolution | Misaligned timestamps, irregular sampling |

## Results

_Not yet available._

## Decisions

Each cleaning decision (what was removed, flagged or imputed, and why) is logged here with the evidence that justified it.
