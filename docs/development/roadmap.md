# Roadmap

Status values: Not started, In progress, Done. Updated only when work is merged.

| Phase | Goal | Deliverables | Status |
|---|---|---|---|
| 1. Research and feasibility | Find out what data exists and what can be forecast | Dataset inventory, feasibility report, refined methodology | In progress |
| 2. Data collection and EDA | Reproducible dataset and understanding of its patterns | Ingestion scripts, clean dataset, EDA and statistics notebooks | Not started |
| 3. ML experiments | Compare baselines and models fairly | Training pipeline, experiment records, comparison report | Not started |
| 4. Explainability | Understand and stress-test the models | SHAP analysis, error analysis, uncertainty evaluation | Not started |
| 5. Backend | Serve predictions | FastAPI service, database integration, containers | Not started |
| 6. Frontend | Present results | Dashboard, forecast, map, insights, research pages | Not started |
| 7. Documentation | Complete, reproducible write-up | Methodology, results, limitations, final report | Not started |

## Phase 1 tasks

- [ ] Inventory air-quality sources and stations for Tashkent
- [ ] Inventory weather sources
- [ ] Check licensing and API access for each
- [ ] Measure coverage and missingness on a real pull
- [ ] Decide viable target, horizons and stations
- [ ] Update methodology and data documentation with findings

Phases may be revised after Phase 1. If the data cannot support a feature, it will be dropped or reduced, and the reason documented.
