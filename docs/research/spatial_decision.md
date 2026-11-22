# Spatial analysis: decision (task 4.4)

**Decision: no spatial interpolation or multi-station modelling is done. Results are station-level only (US Diplomatic Post, OpenAQ location 8881).** Task 4.4.2 is skipped.

## Evidence

- Only one station has a multi-year series (2018-11 to 2025-02). The other series are the TIIAME station in the Mendeley dataset (about 5.4 km from the US station, 2024-02-27 to 2024-09-11 in the overlap, warm season only, 185 overlapping days) and Sputnik-4 on OpenAQ (about 3,277 hours from 2025-09, a different period from the US series).
- The city portal download returns HTTP 500 (checked 2026-11-17), so the 10 to 16 station network is not available.
- In the overlap, TIIAME correlates with the US station (Pearson 0.82, Spearman 0.77) but reads about 40% as high (mean 7.3 against 18.2 ug/m3). The data cannot separate a difference between two places from a difference between a reference-grade monitor and a light-scattering sensor (notebook 03, section 4).
- Interpolation needs enough stations to validate with leave-one-station-out. Two stations in the same season, with different instruments, cannot support that.

## Consequences

- Every forecast, interval and explanation in this project is for one point in the city. Nothing here says how PM2.5 varies across Tashkent.
- RQ6 (variation across stations) is not answered.
- The frontend map shows the station location and value only, with no interpolated surface.

## What would reopen this

Access to the city network data (several stations, several winters). Then station-level evaluation and leave-one-station-out interpolation would become possible.
