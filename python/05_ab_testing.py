"""
05_ab_testing.py
----------------
Evaluates the onboarding_flow_v2 experiment.

Tests:
- D1 retention
- D7 retention
- D30 retention
- Conversion rate
- ARPU

Outputs:
- data/ab_test_results.csv
- outputs/reports/ab_test_results.csv
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats


# -----------------------------------------------------------------------------
# 1. WINDOWS-SAFE PROJECT PATHS
# -----------------------------------------------------------------------------

# Project root = parent of the python folder
ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
REPORTS = ROOT / "outputs" / "reports"

# Create output folder if it does not exist
DATA.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# 2. LOAD DATA
# -----------------------------------------------------------------------------

users_path = DATA / "dim_users.csv"
sessions_path = DATA / "fact_sessions.csv"
transactions_path = DATA / "fact_transactions.csv"

if not users_path.exists():
    raise FileNotFoundError(f"Missing file: {users_path}")

if not sessions_path.exists():
    raise FileNotFoundError(f"Missing file: {sessions_path}")

if not transactions_path.exists():
    raise FileNotFoundError(f"Missing file: {transactions_path}")


users = pd.read_csv(
    users_path,
    parse_dates=["install_date"]
)

sessions = pd.read_csv(
    sessions_path,
    parse_dates=["session_date"]
)

txns = pd.read_csv(
    transactions_path,
    parse_dates=["transaction_date"]
)


# -----------------------------------------------------------------------------
# 3. CREATE RETENTION FLAGS
# -----------------------------------------------------------------------------

active_days = sessions[
    ["user_id", "day_index"]
].drop_duplicates()


for day in [1, 7, 30]:
    retained_users = set(
        active_days.loc[
            active_days["day_index"] == day,
            "user_id"
        ]
    )

    users[f"retained_d{day}"] = (
        users["user_id"].isin(retained_users).astype(int)
    )


# -----------------------------------------------------------------------------
# 4. CREATE USER-LEVEL REVENUE AND CONVERSION DATA
# -----------------------------------------------------------------------------

revenue_per_user = (
    txns.groupby("user_id")["revenue_usd"]
    .sum()
    .rename("total_revenue")
)

users = users.merge(
    revenue_per_user,
    on="user_id",
    how="left"
)

users["total_revenue"] = users["total_revenue"].fillna(0)

users["is_payer"] = (
    users["total_revenue"] > 0
).astype(int)


# -----------------------------------------------------------------------------
# 5. SPLIT CONTROL AND TREATMENT GROUPS
# -----------------------------------------------------------------------------

if "ab_group" not in users.columns:
    raise ValueError(
        "The column 'ab_group' does not exist in dim_users.csv"
    )

control = users[
    users["ab_group"].str.lower() == "control"
].copy()

treatment = users[
    users["ab_group"].str.lower() == "treatment"
].copy()

if len(control) == 0 or len(treatment) == 0:
    raise ValueError(
        "Control or treatment group is empty. Check the ab_group column."
    )

print(f"Control users: {len(control):,}")
print(f"Treatment users: {len(treatment):,}")


# -----------------------------------------------------------------------------
# 6. TWO-PROPORTION Z-TEST
# -----------------------------------------------------------------------------

def two_proportion_z_test(
    control_successes,
    control_total,
    treatment_successes,
    treatment_total,
    alpha=0.05
):
    """
    Compares two proportions.

    Control proportion:
        control_successes / control_total

    Treatment proportion:
        treatment_successes / treatment_total
    """

    p_control = control_successes / control_total
    p_treatment = treatment_successes / treatment_total

    difference = p_treatment - p_control

    # Pooled proportion for hypothesis testing
    pooled_probability = (
        control_successes + treatment_successes
    ) / (
        control_total + treatment_total
    )

    pooled_se = np.sqrt(
        pooled_probability
        * (1 - pooled_probability)
        * (
            1 / control_total
            + 1 / treatment_total
        )
    )

    if pooled_se == 0:
        z_stat = np.nan
        p_value = np.nan
    else:
        z_stat = difference / pooled_se
        p_value = 2 * stats.norm.sf(abs(z_stat))

    # Unpooled standard error for confidence interval
    unpooled_se = np.sqrt(
        p_control * (1 - p_control) / control_total
        + p_treatment * (1 - p_treatment) / treatment_total
    )

    z_critical = stats.norm.ppf(1 - alpha / 2)

    ci_low = difference - z_critical * unpooled_se
    ci_high = difference + z_critical * unpooled_se

    if p_control > 0:
        relative_lift = difference / p_control * 100
    else:
        relative_lift = np.nan

    return {
        "control_rate_pct": round(p_control * 100, 3),
        "treatment_rate_pct": round(p_treatment * 100, 3),
        "absolute_difference_pct_points": round(
            difference * 100, 3
        ),
        "relative_lift_pct": round(relative_lift, 2),
        "z_stat": round(z_stat, 4)
        if not np.isnan(z_stat) else np.nan,
        "p_value": round(p_value, 5)
        if not np.isnan(p_value) else np.nan,
        "significant_at_05": (
            bool(p_value < alpha)
            if not np.isnan(p_value)
            else False
        ),
        "ci_95_low_pct_points": round(ci_low * 100, 3),
        "ci_95_high_pct_points": round(ci_high * 100, 3),
    }


# -----------------------------------------------------------------------------
# 7. WELCH'S T-TEST FOR ARPU
# -----------------------------------------------------------------------------

def welch_t_test(control_values, treatment_values, alpha=0.05):
    """
    Compares average revenue per user between the two groups.
    """

    control_values = np.asarray(control_values, dtype=float)
    treatment_values = np.asarray(treatment_values, dtype=float)

    control_mean = np.mean(control_values)
    treatment_mean = np.mean(treatment_values)

    difference = treatment_mean - control_mean

    control_variance = np.var(control_values, ddof=1)
    treatment_variance = np.var(treatment_values, ddof=1)

    control_n = len(control_values)
    treatment_n = len(treatment_values)

    standard_error = np.sqrt(
        control_variance / control_n
        + treatment_variance / treatment_n
    )

    if standard_error == 0:
        t_stat = np.nan
        p_value = np.nan
        ci_low = np.nan
        ci_high = np.nan
    else:
        t_stat, p_value = stats.ttest_ind(
            treatment_values,
            control_values,
            equal_var=False
        )

        variance_term_control = control_variance / control_n
        variance_term_treatment = treatment_variance / treatment_n

        numerator = (
            variance_term_control
            + variance_term_treatment
        ) ** 2

        denominator = (
            variance_term_control ** 2 / (control_n - 1)
            + variance_term_treatment ** 2 / (treatment_n - 1)
        )

        degrees_of_freedom = numerator / denominator

        t_critical = stats.t.ppf(
            1 - alpha / 2,
            degrees_of_freedom
        )

        ci_low = difference - t_critical * standard_error
        ci_high = difference + t_critical * standard_error

    if control_mean > 0:
        relative_lift = difference / control_mean * 100
    else:
        relative_lift = np.nan

    return {
        "control_mean": round(control_mean, 4),
        "treatment_mean": round(treatment_mean, 4),
        "absolute_difference": round(difference, 4),
        "relative_lift_pct": round(relative_lift, 2),
        "t_stat": round(t_stat, 4)
        if not np.isnan(t_stat) else np.nan,
        "p_value": round(p_value, 5)
        if not np.isnan(p_value) else np.nan,
        "significant_at_05": (
            bool(p_value < alpha)
            if not np.isnan(p_value)
            else False
        ),
        "ci_95_low": round(ci_low, 4)
        if not np.isnan(ci_low) else np.nan,
        "ci_95_high": round(ci_high, 4)
        if not np.isnan(ci_high) else np.nan,
    }


# -----------------------------------------------------------------------------
# 8. RUN A/B TESTS FOR RETENTION AND CONVERSION
# -----------------------------------------------------------------------------

results = []

metrics = [
    ("D1 Retention", "retained_d1"),
    ("D7 Retention", "retained_d7"),
    ("D30 Retention", "retained_d30"),
    ("Conversion Rate", "is_payer"),
]

control_size = len(control)
treatment_size = len(treatment)

for metric_name, column_name in metrics:

    control_successes = int(control[column_name].sum())
    treatment_successes = int(treatment[column_name].sum())

    result = two_proportion_z_test(
        control_successes=control_successes,
        control_total=control_size,
        treatment_successes=treatment_successes,
        treatment_total=treatment_size
    )

    result.update({
        "metric": metric_name,
        "test": "Two-Proportion Z-Test",
        "n_control": control_size,
        "n_treatment": treatment_size,
    })

    results.append(result)


# -----------------------------------------------------------------------------
# 9. RUN ARPU TEST
# -----------------------------------------------------------------------------

arpu_result = welch_t_test(
    control["total_revenue"].values,
    treatment["total_revenue"].values
)

arpu_result.update({
    "metric": "ARPU",
    "test": "Welch's T-Test",
    "n_control": control_size,
    "n_treatment": treatment_size,
})

results.append(arpu_result)


# -----------------------------------------------------------------------------
# 10. FORMAT AND SAVE RESULTS
# -----------------------------------------------------------------------------

results_df = pd.DataFrame(results)

column_order = [
    "metric",
    "test",
    "n_control",
    "n_treatment",
    "control_rate_pct",
    "treatment_rate_pct",
    "control_mean",
    "treatment_mean",
    "absolute_difference_pct_points",
    "absolute_difference",
    "relative_lift_pct",
    "z_stat",
    "t_stat",
    "p_value",
    "significant_at_05",
    "ci_95_low_pct_points",
    "ci_95_high_pct_points",
    "ci_95_low",
    "ci_95_high",
]

existing_columns = [
    column for column in column_order
    if column in results_df.columns
]

results_df = results_df[existing_columns]

# Save in both locations
results_df.to_csv(
    DATA / "ab_test_results.csv",
    index=False
)

results_df.to_csv(
    REPORTS / "ab_test_results.csv",
    index=False
)


# -----------------------------------------------------------------------------
# 11. PRINT RESULTS
# -----------------------------------------------------------------------------

print("\n" + "=" * 100)
print("A/B TEST RESULTS — onboarding_flow_v2")
print("=" * 100)

print(
    results_df.to_string(index=False)
)


# -----------------------------------------------------------------------------
# 12. SAMPLE SIZE / POWER CHECK FOR D7 RETENTION
# -----------------------------------------------------------------------------

baseline_d7 = control["retained_d7"].mean()

mde = 0.02
alpha = 0.05
power = 0.80

z_alpha = stats.norm.ppf(1 - alpha / 2)
z_beta = stats.norm.ppf(power)

target_d7 = baseline_d7 + mde

if target_d7 < 1:

    average_probability = (
        baseline_d7 + target_d7
    ) / 2

    required_sample_size = (
        (
            z_alpha
            * np.sqrt(
                2
                * average_probability
                * (1 - average_probability)
            )
            + z_beta
            * np.sqrt(
                baseline_d7 * (1 - baseline_d7)
                + target_d7 * (1 - target_d7)
            )
        ) ** 2
    ) / (mde ** 2)

    required_sample_size = int(
        np.ceil(required_sample_size)
    )

    print("\n" + "=" * 100)
    print("POWER / SAMPLE SIZE CHECK")
    print("=" * 100)

    print(
        f"Baseline D7 retention: {baseline_d7 * 100:.2f}%"
    )

    print(
        f"Minimum detectable effect: {mde * 100:.1f} percentage points"
    )

    print(
        f"Required sample size per group: "
        f"{required_sample_size:,}"
    )

    print(
        f"Actual control sample size: {control_size:,}"
    )

    print(
        f"Actual treatment sample size: {treatment_size:,}"
    )

else:
    print(
        "\nPower calculation skipped because the target "
        "retention rate would exceed 100%."
    )


print("\nFiles written successfully:")
print(f"- {DATA / 'ab_test_results.csv'}")
print(f"- {REPORTS / 'ab_test_results.csv'}")