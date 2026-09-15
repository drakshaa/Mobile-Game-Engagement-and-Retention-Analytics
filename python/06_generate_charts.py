"""
06_generate_charts.py
---------------------
Generates static chart images for the README and project write-up.

The interactive version of these visuals can be built in Power BI.
These PNG files provide quick previews for GitHub.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# -----------------------------------------------------------------------------
# 1. PROJECT PATHS
# -----------------------------------------------------------------------------

# This file is located inside:
# E:/Resume Project/Mobile-game-analytics/python/

# parents[0] = python
# parents[1] = Mobile-game-analytics
ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"
FIG = ROOT / "outputs" / "figures"
REPORTS = ROOT / "outputs" / "reports"

# Create output folders if they do not exist
FIG.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# 2. MATPLOTLIB SETTINGS
# -----------------------------------------------------------------------------

plt.rcParams.update({
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.autolayout": True
})


# -----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def check_file(path):
    """Check that an input file exists before reading it."""
    if not path.exists():
        raise FileNotFoundError(f"Required file was not found: {path}")


def save_chart(filename):
    """Save the current chart to the figures directory."""
    output_path = FIG / filename
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Created: {output_path}")


# -----------------------------------------------------------------------------
# 4. LOAD DATA
# -----------------------------------------------------------------------------

daily_path = DATA / "daily_kpi_trend.csv"
retention_group_path = DATA / "python_retention_by_group.csv"
retention_channel_path = DATA / "python_retention_by_channel.csv"
churn_path = DATA / "churn_dropoff_buckets.csv"
sku_path = DATA / "revenue_by_sku.csv"
ab_path = REPORTS / "ab_test_results.csv"

required_files = [
    daily_path,
    retention_group_path,
    retention_channel_path,
    churn_path,
    sku_path,
    ab_path
]

for file_path in required_files:
    check_file(file_path)


daily = pd.read_csv(
    daily_path,
    parse_dates=["date"]
)

retention_group = pd.read_csv(
    retention_group_path,
    index_col=0
)

retention_channel = pd.read_csv(
    retention_channel_path,
    index_col=0
)

churn = pd.read_csv(churn_path)
sku_rev = pd.read_csv(sku_path)
ab = pd.read_csv(ab_path)


# -----------------------------------------------------------------------------
# 5. DAU / INSTALLS TREND
# -----------------------------------------------------------------------------

required_columns = [
    "date",
    "dau",
    "new_installs",
    "dau_7d_avg"
]

for column in required_columns:
    if column not in daily.columns:
        raise KeyError(
            f"Column '{column}' is missing from daily_kpi_trend.csv"
        )

fig, ax1 = plt.subplots(figsize=(9, 4.5))

ax1.plot(
    daily["date"],
    daily["dau"],
    linewidth=1,
    alpha=0.4,
    label="DAU"
)

ax1.plot(
    daily["date"],
    daily["dau_7d_avg"],
    linewidth=2.2,
    label="DAU 7-day average"
)

ax1.set_ylabel("Daily Active Users")
ax1.set_xlabel("Date")
ax1.set_title("Daily Active Users and New Installs Trend")

ax2 = ax1.twinx()

ax2.bar(
    daily["date"],
    daily["new_installs"],
    alpha=0.35,
    label="New Installs"
)

ax2.set_ylabel("New Installs")

lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()

ax1.legend(
    lines_1 + lines_2,
    labels_1 + labels_2,
    loc="upper left",
    fontsize=8
)

save_chart("01_dau_installs_trend.png")


# -----------------------------------------------------------------------------
# 6. D1 / D7 / D30 RETENTION: CONTROL VS TREATMENT
# -----------------------------------------------------------------------------

retention_columns = [
    "retained_d1",
    "retained_d7",
    "retained_d30"
]

retention_labels = [
    "D1",
    "D7",
    "D30"
]

required_groups = ["control", "treatment"]

for group in required_groups:
    if group not in retention_group.index:
        raise KeyError(
            f"'{group}' group is missing from python_retention_by_group.csv"
        )

for column in retention_columns:
    if column not in retention_group.columns:
        raise KeyError(
            f"Column '{column}' is missing from retention group data"
        )

fig, ax = plt.subplots(figsize=(7, 4.5))

x = np.arange(len(retention_columns))
width = 0.35

control_values = retention_group.loc["control", retention_columns].astype(float)
treatment_values = retention_group.loc[
    "treatment",
    retention_columns
].astype(float)

ax.bar(
    x - width / 2,
    control_values,
    width,
    label="Control"
)

ax.bar(
    x + width / 2,
    treatment_values,
    width,
    label="Treatment"
)

ax.set_xticks(x)
ax.set_xticklabels(retention_labels)
ax.set_ylabel("Retention Rate (%)")
ax.set_title("D1 / D7 / D30 Retention: Control vs Treatment")
ax.legend()

for i, value in enumerate(control_values):
    ax.text(
        i - width / 2,
        value + 0.5,
        f"{value:.1f}%",
        ha="center",
        fontsize=8
    )

for i, value in enumerate(treatment_values):
    ax.text(
        i + width / 2,
        value + 0.5,
        f"{value:.1f}%",
        ha="center",
        fontsize=8
    )

save_chart("02_retention_ab_comparison.png")


# -----------------------------------------------------------------------------
# 7. D30 RETENTION BY ACQUISITION CHANNEL
# -----------------------------------------------------------------------------

if "retained_d30" not in retention_channel.columns:
    raise KeyError(
        "Column 'retained_d30' is missing from python_retention_by_channel.csv"
    )

retention_channel = retention_channel.sort_values(
    "retained_d30",
    ascending=True
)

fig, ax = plt.subplots(figsize=(7, 4.5))

values = retention_channel["retained_d30"].astype(float)

ax.barh(
    retention_channel.index.astype(str),
    values
)

ax.set_xlabel("D30 Retention Rate (%)")
ax.set_title("D30 Retention by Acquisition Channel")

for i, value in enumerate(values):
    ax.text(
        value + 0.2,
        i,
        f"{value:.1f}%",
        va="center",
        fontsize=8
    )

save_chart("03_retention_by_channel.png")


# -----------------------------------------------------------------------------
# 8. CHURN DROP-OFF BUCKETS
# -----------------------------------------------------------------------------

required_churn_columns = [
    "churn_bucket",
    "users",
    "pct_of_all_users"
]

for column in required_churn_columns:
    if column not in churn.columns:
        raise KeyError(
            f"Column '{column}' is missing from churn_dropoff_buckets.csv"
        )

bucket_order = [
    "Churned Day 0 (never returned)",
    "Churned Day 1-2",
    "Churned Day 3-6",
    "Retained to D7+"
]

churn = churn.set_index("churn_bucket")

# Keep only buckets that exist in the CSV
available_buckets = [
    bucket for bucket in bucket_order
    if bucket in churn.index
]

churn = churn.loc[available_buckets].reset_index()

fig, ax = plt.subplots(figsize=(8, 4.5))

bars = ax.bar(
    churn["churn_bucket"],
    churn["users"]
)

ax.set_ylabel("Users")
ax.set_title("User Drop-Off by Retention Stage")

plt.xticks(
    rotation=20,
    ha="right",
    fontsize=8
)

for i, bar in enumerate(bars):
    users_count = churn.loc[i, "users"]
    percentage = churn.loc[i, "pct_of_all_users"]

    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height(),
        f"{int(users_count):,}\n({percentage:.1f}%)",
        ha="center",
        va="bottom",
        fontsize=8
    )

save_chart("04_churn_dropoff_funnel.png")


# -----------------------------------------------------------------------------
# 9. REVENUE BY SKU
# -----------------------------------------------------------------------------

required_sku_columns = [
    "sku",
    "total_revenue"
]

for column in required_sku_columns:
    if column not in sku_rev.columns:
        raise KeyError(
            f"Column '{column}' is missing from revenue_by_sku.csv"
        )

sku_rev = sku_rev.sort_values(
    "total_revenue",
    ascending=True
)

fig, ax = plt.subplots(figsize=(7, 4.5))

values = sku_rev["total_revenue"].astype(float)

ax.barh(
    sku_rev["sku"].astype(str),
    values
)

ax.set_xlabel("Total Revenue (USD)")
ax.set_title("Revenue by SKU")

for i, value in enumerate(values):
    ax.text(
        value,
        i,
        f"${value:,.0f}",
        va="center",
        fontsize=8
    )

save_chart("05_revenue_by_sku.png")


# -----------------------------------------------------------------------------
# 10. A/B TEST FOREST PLOT
# -----------------------------------------------------------------------------

required_ab_columns = [
    "metric",
    "test",
    "absolute_difference_pct_points",
    "ci_95_low_pct_points",
    "ci_95_high_pct_points",
    "p_value",
    "significant_at_05"
]

for column in required_ab_columns:
    if column not in ab.columns:
        raise KeyError(
            f"Column '{column}' is missing from ab_test_results.csv"
        )

prop_metrics = ab[
    ab["test"] == "two_proportion_z_test"
].copy()

if not prop_metrics.empty:

    prop_metrics = prop_metrics.reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(8, 4.5))

    y_positions = np.arange(len(prop_metrics))

    differences = prop_metrics["absolute_difference_pct_points"].astype(float)
    lower_ci = prop_metrics["ci_95_low_pct_points"].astype(float)
    upper_ci = prop_metrics["ci_95_high_pct_points"].astype(float)

    lower_errors = differences - lower_ci
    upper_errors = upper_ci - differences

    ax.errorbar(
        differences,
        y_positions,
        xerr=[
            lower_errors,
            upper_errors
        ],
        fmt="o",
        elinewidth=2,
        capsize=4,
        markersize=7
    )

    ax.axvline(
        0,
        linestyle="--",
        linewidth=1
    )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(prop_metrics["metric"])
    ax.set_xlabel(
        "Treatment − Control Difference (percentage points, 95% CI)"
    )
    ax.set_title(
        "A/B Test: Treatment Effect by Metric"
    )

    for i, row in prop_metrics.iterrows():

        significance = (
            "significant"
            if bool(row["significant_at_05"])
            else "not significant"
        )

        ax.text(
            row["absolute_difference_pct_points"],
            i + 0.15,
            f"p={row['p_value']:.4f} ({significance})",
            ha="center",
            fontsize=7.5
        )

    save_chart("06_ab_test_forest_plot.png")

else:
    print(
        "No two-proportion test results found. "
        "Skipping A/B forest plot."
    )


# -----------------------------------------------------------------------------
# 11. FINAL OUTPUT
# -----------------------------------------------------------------------------

print("\nCharts successfully generated.")
print(f"Figures directory: {FIG}")

for file_path in sorted(FIG.glob("*.png")):
    print(f" - {file_path.name}")