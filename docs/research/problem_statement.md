# Problem statement

## Context

Air pollution is a recognized environmental concern in Tashkent, Uzbekistan. Current air-quality data is available from public platforms, but it does not tell a user how pollution will change in the next days, which conditions accompany high pollution, or how much a forecast can be trusted.

## Problem

Can PM2.5 concentrations in Tashkent be forecast 24 hours ahead (48 and 72 hours later, if the data supports it) from historical air-quality and weather data, and how accurate and reliable are those forecasts compared with simple baselines?

## Why this was not answerable at the start (resolved in Phase 1)

Phase 1 established what data exists; see the [feasibility report](feasibility_report.md). The text below is the original reasoning.

The answer depends on data whose availability for Tashkent is unknown: how many monitoring stations exist, how long they have reported, and how complete their records are. Phase 1 establishes this before any forecasting claim is made. If the data is too sparse for a horizon or a location, the project will report that.

## Scope

In scope:
- PM2.5 as the primary target; PM10 and other pollutants when available.
- Tashkent and its monitoring stations.
- Forecasting target: hourly PM2.5, 24 hour ahead and from one station start.
- Historical analysis, forecasting, model evaluation and explanation.

Out of scope for now:
- Health-risk modelling and medical advice.
- Source attribution (finding which source emitted the pollution).
- Claims about neighborhood-level pollution where station coverage cannot support them.

## Association and causation

Statistical and model-based findings describe associations in observed data. They do not establish causes, and documents in this repository must not present them as such.
