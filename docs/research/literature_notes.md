# Literature notes

## Papers

## Prediction of PM2.5 and PM10 Concentrations Using Machine and Deep Learning Techniques: Evidence from Tashkent, Uzbekistan
- **Citation:**
https://opendata.uni-halle.de/bitstream/1981185920/127395/1/ICAIIT_2026_14%284%29-7-20.pdf
- **Peer reviewed?** 
no, it is conference papaer
- **City and data:** stations, period, resolution, source
  - Stations: Tashkent, 16 stations from opendata.tashkent.uz
  - Period: 7 Nov 2023 to 5 Jan 2025
  - Variables: PM2.5, PM10, temperature, humidity, wind speed, pressure
- **Methods and models compared:**
  - Linear Regression, SVR, Random Forest and GRU and persistence baseline.
  - Features: lags of 1, 2, 3, 6, 12 and 24 hours, plus hour, weekday and month.
- **Forecast horizon:**
- One hour ahead. Add a short note that the abstract speaks about "hours and days" but the models forecast 1 hour.
- **Validation (chronological or random split?):**
- Chronological. Train 7 Nov 2023 to 31 Oct 2024, test 1 Nov 2024 to 5 Jan 2025. Five-fold expanding-window CV for
  tuning. Scalers and imputation fitted on training data only.
- **Baselines used:**
- Persistence, PM(t) = PM(t-1). For PM2.5: MAE 9.63, RMSE 12.14, R² 0.81.
- **Reported results:** (metric, value, page/table)
1-hour-ahead, winter test set only
- **Limitations (theirs and mine):**
- Missing emission source: The dataset doesn include traffic volume, industrial emission and construction activties.
- Forecast horizon: only one hour ahead is evaluated. We need 24 hour or 48 hour prediction to evaluate how precise the dataset is
- Real time deployment: they haven't completed real time deployment
- **What I take from it for AERON:**
- A 16-station hourly source may exist for Tashkent. Verify access and license in 1.2.2.
- Their horizon one hour ahead forecasting, we will investigate 24-hour, 48-hour and 72-hour forecasts
- More environmental features
  

## Prediction of atmospheric PM2.5 level by machine learning techniques in Isfahan, Iran
- **Citation:**
Mohammadi F., Teiri H., Hajizadeh Y., Abdolahnejad A., Ebrahimi A. (2024). Scientific Reports 14:2109. https://doi.org/10.1038/s41598-024-52617-z
- **Peer reviewed?**
Yes, journal article (Scientific Reports, Nature Portfolio).
- **City and data:** stations, period, resolution, source
  - City: Isfahan, Iran (semi-arid, about 2 million residents, heavy industry).
  - Stations: 7 PM2.5 monitors operated by the Isfahan Department of Environment (beta attenuation monitors). Meteorology from the Isfahan Meteorological Administration.
  - Period: Jan 2011 to Dec 2019 (3285 days) for model building. Year 2020 for external validation.
  - Resolution: daily. PM2.5 is hourly at source (Table 1) but used as a 24-hour average.
  - Variables: average temperature, relative humidity, rainfall/snowmelt, average wind speed, wind direction, plus day, month, year and station ID. Tmax, Tmin and max wind speed were removed because of collinearity (VIF > 10).
  - Availability: data only "upon reasonable request".
- **Methods and models compared:**
  - ANN (MLP, 9:25:1, tansig hidden layer, Levenberg-Marquardt), SVM (quadratic kernel), KNN (cosine distance), Random Forest (boosted ensemble). Implemented in MATLAB R2020b.
  - ANN predicts the PM2.5 concentration (regression), and the value is then converted to a grade. SVM, KNN and RF directly classify four EPA-based grades (Good, Moderate, Unhealthy for sensitive groups, Unhealthy).
  - Spatial step: ANN output for 2020 interpolated with IDW in ArcGIS to make monthly pollution maps.
  - No baseline model such as persistence or climatology.
- **Forecast horizon:**
  - None in the forecasting sense. Models map same-day meteorology to same-day PM2.5 (nowcasting or estimation). There are no lagged PM2.5 inputs and no next-day target, although the paper says "prediction" and "forecast".
- **Validation (chronological or random split?):**
  - Random. ANN: 70% train (2299), 15% validation (493), 15% test (493). SVM, KNN and RF: 15% holdout test, 15% holdout validation, rest training.
  - External check: 2020 data (monthly station averages), which is the only time-ordered test.
- **Baselines used:**
  - None. The four models are compared only with each other.
- **Reported results:** (metric, value, page/table)
  - Table 2 (test data, grade classification): accuracy ANN 0.911, RF 0.861, SVM 0.848, KNN 0.823. ANN specificity 0.720, F1 0.882.
  - AUC (Fig. 6): ANN 0.95, RF 0.94, KNN 0.93, SVM 0.92.
  - External validation 2020 (ANN, p. 10): R = 0.895, MSE = 14.382.
  - Inconsistency: the abstract says ANN accuracy is 90.1%, while Table 2 and the conclusion say 91.1%.
  - Not reported: RMSE, MAE or R² on the test set, and per-grade results. Specificity is low for SVM (0.529) and KNN (0.424), so the classes are probably imbalanced.
- **Limitations (theirs and mine):**
  - Theirs: none stated explicitly. The paper lists as its advantage that it compares four models and combines them with GIS.
  - Mine: random split of a time series mixes neighbouring days between train and test. This leaks information, and accuracy is likely overstated.
  - Mine: `year` and `day of month` are used as inputs, which lets the models memorise time patterns. Year cannot generalise to the future.
  - Mine: it is not a forecast, because same-day weather is needed as input. Real forecasts would depend on forecast weather, which is less accurate.
  - Mine: coarse four-grade classification, and the range of PM2.5 is only 11 to 98 µg/m³, so extreme events are not covered.
  - Mine: no baseline and no regression error for the classifiers. The 2020 check uses monthly averages, so daily skill is not shown.
  - Mine: no emissions data (traffic, industry), although the discussion attributes pollution to them. Data not openly available, so results can't be reproduced.
- **What I take from it for AERON:**
  - Supports using meteorology (temperature, humidity, wind, rain) and calendar features for PM2.5 models, and checking collinearity with VIF.
  - Shows a spatial mapping idea (IDW from station predictions) that we could use for Tashkent maps.
  - Do not copy the random split or the year feature. Use chronological splits, as in the Tashkent paper.
  - Always include persistence and seasonal-naive baselines, and report MAE and RMSE in µg/m³ so models are comparable with other papers.
  - Compare with the Tashkent paper: daily and 7 stations here against hourly and 16 stations there. Neither covers 24 to 72 hour horizons, which is the gap AERON targets.
