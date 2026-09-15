# Mobile Game Product & Retention Analytics

**Tech Stack:** SQL, Python, Pandas, SciPy, scikit-learn, Regression Analysis, Cohort Analysis, and A/B Testing

This project analyzes user behavior, retention, churn, and monetization for a simulated mobile game. It follows an end-to-end analytics workflow:

**CSV → SQLite/SQL → Python Analysis**

The project focuses on questions such as:

- Which users are more likely to churn?
- What factors influence retention?
- How do acquisition channels perform?
- Did the new onboarding experience improve retention?
- What drives in-app revenue?

## Project Structure

```text
mobile-game-analytics/
├── data/
├── sql/
│   ├── 01_schema.sql
│   ├── 02_cohort_retention.sql
│   └── 03_kpi_and_monetization.sql
├── python/
│   ├── 01_data_generation.py
│   ├── 02_build_db_and_run_sql.py
│   ├── 03_kpi_automation.py
│   ├── 04_regression_analysis.py
│   ├── 05_ab_testing.py
│   └── 06_generate_charts.py
└── outputs/
    ├── figures/
    └── reports/
