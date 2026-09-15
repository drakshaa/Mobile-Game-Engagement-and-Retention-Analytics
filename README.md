# Mobile Game Product & Retention Analytics

**Stack:** SQL · Python (Pandas, scikit-learn, SciPy) · Regression Analysis · Cohort Analysis · A/B Testing · Power BI / DAX

An end-to-end product analytics project simulating a mid-size mobile game's
user/transaction data, built to answer the questions a Product/Growth
Analytics team is actually asked: *Who's churning, why, and what should we do
about it? Did the new onboarding experiment work? What drives revenue?*

The pipeline runs **CSV → SQL (SQLite) → Python statistics → Power BI**, and
every number in this README is reproduced directly from the code in this repo
— nothing here is hand-typed or hypothetical.

---

## 📁 Project structure

```
mobile-game-analytics/
├── data/                        # generated + derived CSVs, SQLite DB
├── sql/
│   ├── 01_schema.sql             # star-schema DDL (users, sessions, transactions, AB assignments)
│   ├── 02_cohort_retention.sql   # D1/D7/D30 cohort matrix, CTEs, CASE, window functions
│   └── 03_kpi_and_monetization.sql  # DAU, ARPU/ARPPU, conversion, revenue, AB summary
├── python/
│   ├── 01_data_generation.py     # synthetic but realistic data generator (retention decay curves, engineered treatment effect)
│   ├── 02_build_db_and_run_sql.py# loads CSVs into SQLite, executes & validates all SQL
│   ├── 03_kpi_automation.py      # recurring KPI automation (DAU, retention, ARPU, ARPPU, stickiness)
│   ├── 04_regression_analysis.py # logistic regression (retention drivers) + OLS (revenue drivers)
│   ├── 05_ab_testing.py          # two-proportion z-tests, Welch's t-test, CIs, power/sample-size check
│   └── 06_generate_charts.py     # chart generation for this README
├── powerbi/
│   ├── DAX_measures.md           # full DAX measure library + data model instructions
│   ├── dashboard_build_guide.md  # 4-page dashboard spec (Overview / Cohorts / Monetization / Experimentation)
│   └── data_for_powerbi/         # clean CSV extracts ready to import into Power BI
└── outputs/
    ├── figures/                  # PNG chart exports
    └── reports/                  # regression tables, AB test results, KPI summary
```

## ▶️ How to run it end-to-end

```bash
pip install numpy pandas scipy scikit-learn matplotlib
python python/01_data_generation.py        # 1. generate synthetic dataset
python python/02_build_db_and_run_sql.py   # 2. load into SQLite + run all SQL queries
python python/03_kpi_automation.py         # 3. automate recurring KPI calculations
python python/04_regression_analysis.py    # 4. regression: retention & revenue drivers
python python/05_ab_testing.py             # 5. A/B test significance testing
python python/06_generate_charts.py        # 6. generate chart images
```
Then open Power BI Desktop, import the CSVs from `powerbi/data_for_powerbi/`,
and follow `powerbi/DAX_measures.md` + `powerbi/dashboard_build_guide.md`.

---

## 1. Dataset

Simulated **6,000 users** over a 90-day install window, with:
- `dim_users` — install date, acquisition channel (Organic/Paid Social/Paid UA/Influencer/Cross-Promo), country, device, A/B group
- `fact_sessions` — 54,244 session-level engagement events (day-since-install, duration, level reached)
- `fact_transactions` — 4,493 in-app purchases across 8 SKUs
- `ab_test_assignments` — 50/50 split for a **"new guided onboarding tutorial"** experiment

Retention probabilities were generated from a realistic decay curve
(D1 ≈ 45%, D7 ≈ 20%, D30 ≈ 9% baseline) with an engineered treatment
uplift, so the regression and A/B testing modules have real, recoverable
signal — this mirrors how you'd validate a pipeline against known-truth data
before pointing it at production.

## 2. SQL — Cohort & KPI layer

`sql/02_cohort_retention.sql` builds the D1/D7/D30 cohort matrix using CTEs,
`CASE`-based day-bucketing, and window functions (`RANK()`, running totals
via `SUM() OVER`). Sample output (install-date cohort matrix):

| cohort_date | cohort_size | D1 % | D7 % | D30 % |
|---|---|---|---|---|
| 2025-10-02 | 65 | 50.8 | 16.9 | 15.4 |
| 2025-10-09 | 78 | 50.0 | 32.1 | 25.6 |
| 2025-10-14 | 84 | 57.1 | 22.6 | 9.5 |

`sql/03_kpi_and_monetization.sql` computes DAU, ARPU/ARPPU/conversion by
channel, SKU revenue with `CASE`-based product categorization, and an A/B
summary table (raw counts, joined downstream with Python for significance
testing).

## 3. Root-cause / drop-off analysis

Where do non-retained users actually stop coming back?

![Churn drop-off funnel](outputs/figures/04_churn_dropoff_funnel.png)

**~19% of users never return after install day**, and another ~23% churn
within the first week — squarely the window the onboarding experiment (below)
targets.

## 4. Retention by acquisition channel

![Retention by channel](outputs/figures/03_retention_by_channel.png)

Organic and Influencer traffic retain 2–3x better at D30 than Paid UA
Network traffic — a direct input into budget reallocation decisions.

## 5. Regression analysis

**Logistic regression** — `P(D7 retained) ~ early engagement + A/B group + device + channel`
(scikit-learn, with Wald-test standard errors/p-values computed analytically):

| feature | coef | odds ratio | p-value | significant |
|---|---|---|---|---|
| early_sessions | 0.548 | 1.73 | <0.001 | ✅ |
| early_max_level | 0.126 | 1.13 | 0.005 | ✅ |
| is_treatment | 0.075 | 1.08 | 0.021 | ✅ |
| ch_Paid_UA_Network | -0.220 | 0.80 | <0.001 | ✅ |

*Read:* every additional early session raises the odds of D7 retention by
~73%; being in the treatment (new onboarding) group is a statistically
significant positive predictor even after controlling for channel/device.

**OLS regression** — `total_revenue ~ engagement depth + retention + A/B group`:
`total_sessions` (p<0.001) and `max_level_overall` (p<0.001) are the
strongest, statistically significant predictors of revenue — engagement
depth matters more for monetization than retention status alone in this
dataset (R² = 0.049; full table in `outputs/reports/ols_regression_revenue.csv`).

## 6. A/B Testing — "New Guided Onboarding" experiment

![A/B test forest plot](outputs/figures/06_ab_test_forest_plot.png)

| Metric | Control | Treatment | Lift | p-value | Significant? |
|---|---|---|---|---|---|
| D1 Retention | 45.16% | 51.31% | +13.6% relative | 0.0000 | ✅ Yes |
| D7 Retention | 22.17% | 25.42% | +14.7% relative | 0.0031 | ✅ Yes |
| D30 Retention | 12.09% | 13.61% | +12.6% relative | 0.0791 | ❌ Not yet |
| Conversion Rate | 27.11% | 29.44% | +8.6% relative | 0.0455 | ✅ Yes |
| ARPU | $6.47 | $6.92 | +6.9% relative | 0.2316 | ❌ No |

**Takeaway:** the new onboarding flow drives a statistically significant,
practically meaningful lift in early retention (D1/D7) and conversion. The
D30 and ARPU effects are directionally positive but not yet significant — a
power check shows we'd need **~7,000 users/arm** to reliably detect a 2pt D30
lift at 80% power, vs. the ~3,000/arm actually collected. **Recommendation:**
ship the onboarding change (early-funnel wins are real and immediate), and
keep the long-horizon metrics in a holdout to confirm the D30/revenue read
with more data.

## 7. Recurring KPI summary (auto-generated)

| Metric | Value |
|---|---|
| Total Users | 6,000 |
| Total Sessions | 54,244 |
| Total Revenue | $40,188.07 |
| D1 / D7 / D30 Retention | 48.3% / 23.8% / 12.9% |
| Conversion Rate | 28.3% |
| ARPU / ARPPU | $6.70 / $23.67 |
| Avg. DAU (peak) | 287 (365) |
| DAU/MAU Stickiness | 18.4% |

## 8. Power BI Dashboard

A 4-page dashboard (Executive Overview, Cohort & Retention, Monetization,
Experimentation) is specified in `powerbi/dashboard_build_guide.md` with the
full DAX measure library in `powerbi/DAX_measures.md` — DAU/MAU stickiness,
D1/D7/D30 retention with time-intelligence, ARPU/ARPPU, and live-sliceable
A/B test readouts, built on top of the clean CSV extracts in
`powerbi/data_for_powerbi/`.

---

## Key skills demonstrated
- **SQL:** CTEs, window functions (`RANK`, `SUM() OVER`), `CASE`-based
  segmentation, multi-table joins, cohort matrix construction
- **Python/Pandas:** ETL, KPI automation, feature engineering for modeling
- **Statistics:** logistic & OLS regression with full inferential output
  (coefficients, SEs, p-values, odds ratios, R²), two-proportion z-tests,
  Welch's t-test, confidence intervals, power/sample-size analysis
- **Experimentation:** hypothesis formulation, significance testing,
  interpreting mixed/partial results and making a ship/no-ship recommendation
- **BI/Reporting:** dimensional modeling and DAX measure design for
  self-serve dashboards
