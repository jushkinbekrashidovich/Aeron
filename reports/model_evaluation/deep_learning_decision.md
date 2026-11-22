# Deep learning: decision to skip (task 3.5.1)

**Decision: LSTM and GRU models are not trained.** Tasks 3.5.2 and 3.5.3 are skipped. This was an expected outcome (the scope cut agreed after Phase 1) and the model comparison in `comparison.md` supports it.

## Reasons

1. **Little data.** The daily table has 1,823 local days with a daily mean PM2.5 (of 2,282 calendar days from 2018-11-28 to 2025-02-25). Winter days, where most of the forecast error is, number about 690. Sequence networks need far more rows than this to beat well-tuned simpler models, and the walk-forward protocol leaves even fewer rows for training in the early blocks.
2. **Broken series.** The daily series splits into 119 unbroken runs (longest 158 days; notebook 04 part A). Windows of past days for a sequence model would either cross gaps or be dropped, which shrinks the training set further. Filling gaps is not allowed by the missing-data policy.
3. **Little to gain from long history.** The partial autocorrelation of winter daily PM2.5 is near zero after lag 1 (at most 0.13), and in the lag ablation (comparison report) one lag performs as well as seven lags with rolling statistics (differences of at most 0.6 ug/m3, all intervals including 0 or ending at it). The main strength of LSTM and GRU, learning from long histories, has little to work with here.
4. **No headroom shown by flexible models.** Ridge regression, random forest, XGBoost and LightGBM are within about 1 to 2 ug/m3 winter MAE of each other, and on real forecasts the trees are not reliably better than ridge. Gains came from weather inputs, not from model flexibility, so a more flexible model class is unlikely to change the picture.
5. **Cost.** Training a network with the same split, tuning and leakage rules, repeated for every block and lead, is a large effort for a result that cannot be separated from noise with about 140 real-forecast test days.

## What would change this decision

More data (a longer record, several stations, or hourly modelling with many more rows) or evidence that the tree models miss structure over longer horizons. Neither exists in this project. A sequence model is listed as future work.
