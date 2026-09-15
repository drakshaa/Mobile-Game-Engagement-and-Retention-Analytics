# Mobile Game Product & Retention Analytics

A product analytics project built around a mobile game's user data — engagement, retention, monetization, and one A/B test, worked through the way an actual product analyst would.

Since I didn't have a real game's data to use, I generated a synthetic dataset (6,000 users, 90 days, realistic retention curves) so the pipeline could be built and tested end to end. Everything downstream — the SQL, the regressions, the A/B test — runs on that data and is fully reproducible.

## What's in here

- **SQL** — cohort retention (D1/D7/D30) using CTEs, window functions, CASE statements
- **Python** — KPI automation, logistic + OLS regression, A/B testing with significance tests and confidence intervals
- **Power BI** — DAX measures and a dashboard build guide 

## Structure
data/ generated CSVs + SQLite db
sql/ schema + cohort/KPI queries
python/ data gen, KPI automation, regression, A/B testing
powerbi/ DAX measures, interactive dashboard
outputs/ charts, regression tables, A/B results


## Running it

```bash
pip install numpy pandas scipy scikit-learn matplotlib
python python/01_data_generation.py
python python/02_build_db_and_run_sql.py
python python/03_kpi_automation.py
python python/04_regression_analysis.py
python python/05_ab_testing.py
python python/06_generate_charts.py
```

## The experiment

The dataset includes a simulated A/B test — a new guided onboarding tutorial vs. the old flow, 50/50 split.

| Metric | Control | Treatment | Lift | p-value | Significant |
|---|---|---|---|---|---|
| D1 retention | 45.2% | 51.3% | +13.6% | <0.001 | yes |
| D7 retention | 22.2% | 25.4% | +14.7% | 0.003 | yes |
| D30 retention | 12.1% | 13.6% | +12.6% | 0.079 | not yet |
| Conversion | 27.1% | 29.4% | +8.6% | 0.045 | yes |
| ARPU | $6.47 | $6.92 | +6.9% | 0.232 | no |

The new onboarding clearly helps early retention. D30 and revenue trend the right way but aren't significant yet — a power check shows the test would need roughly 7,000 users per arm to reliably catch a 2-point D30 lift, and it only had ~3,000. Recommendation: ship it, keep watching the long-horizon numbers.

## Regression findings

Logistic regression on D7 retention: early session count is the strongest predictor (each extra session in the first few days raises the odds of D7 retention by ~73%), followed by early max level reached. Being in the treatment group is also a significant, positive predictor on its own, controlling for channel and device.

OLS on total revenue: session count and max level reached are the two significant drivers — engagement depth predicts spend better than retention status alone.

## Notes

- Built without `statsmodels` (not available in the environment) — the regression inference (standard errors, p-values) is computed directly from the model math instead of a stats library, so the numbers are the same, just derived by hand.
- The Power BI dashboard spec is fully written (DAX + build guide), but I don't have Power BI Desktop to export an actual `.pbix`. There's an interactive HTML version in `powerbi/interactive_dashboard.html` that mirrors the same four pages if you want something to open immediately.
