# Project summary (for applications)

**AERON: forecasting PM2.5 air pollution in Tashkent, one to three days ahead**

I built an end-to-end forecasting study for Tashkent, Uzbekistan, where winter smog regularly pushes daily PM2.5 into unhealthy levels. The project covers data collection from OpenAQ and Open-Meteo, cleaning and validation, a leak-free evaluation framework, a comparison of baselines, ridge regression, random forest, XGBoost and LightGBM, conformal prediction ranges, model explanations, a FastAPI service and a Next.js web app.

What I found, with the limits stated: on real archived weather forecasts, LightGBM reduced the average winter error from 24 to 17 µg/m³ at one day ahead against "tomorrow equals today", and the gain came mostly from weather inputs, not from the choice of model. The prediction ranges held for about 85% of winter days instead of the nominal 90%, and the model underpredicts the most polluted days. The data come from one monitor and end in February 2025, so the web app replays past forecasts and does not claim to be current.

Skills shown: time-series evaluation without leakage, honest handling of small samples (block bootstrap, no multiple-comparison claims), uncertainty quantification, reproducible pipelines (tests, MLflow, CI), and writing results with their limits.

Links: repository (see README); demo: none hosted (see `docs/deployment.md`).
