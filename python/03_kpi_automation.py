"""
03_kpi_automation.py
--------------------

Calculates recurring mobile game KPIs using Python and Pandas.

KPIs:
- DAU
- New installs
- MAU proxy
- DAU/MAU stickiness
- D1, D7, D30 retention
- Conversion rate
- ARPU
- ARPPU
- Revenue trends
- KPI breakdown by channel and A/B group
"""

import pandas as pd
import numpy as np
from pathlib import Path


# -----------------------------------------------------------------------------
# 1. PROJECT PATHS
# -----------------------------------------------------------------------------

# Automatically identifies the main project folder:
# E:/Resume Project/Mobile-game-analytics
ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"
REPORTS = ROOT / "outputs" / "reports"

# Create output directory if it does not already exist
REPORTS.mkdir(parents=True, exist_ok=True)

print("Project folder:", ROOT)
print("Data folder:", DATA)
print("Reports folder:", REPORTS)


# -----------------------------------------------------------------------------
# 2. LOAD DATASETS
# -----------------------------------------------------------------------------

users_file = DATA / "dim_users.csv"
sessions_file = DATA / "fact_sessions.csv"
transactions_file = DATA / "fact_transactions.csv"

# Check that required files exist
required_files = [
    users_file,
    sessions_file,
    transactions_file
]

for file in required_files:
    if not file.exists():
        raise FileNotFoundError(f"Required file not found: {file}")

users = pd.read_csv(
    users_file,
    parse_dates=["install_date"]
)

sessions = pd.read_csv(
    sessions_file,
    parse_dates=["session_date"]
)

txns = pd.read_csv(
    transactions_file,
    parse_dates=["transaction_date"]
)

print("\nData loaded successfully:")
print("Users:", len(users))
print("Sessions:", len(sessions))
print("Transactions:", len(txns))


# -----------------------------------------------------------------------------
# 3. DAILY ACTIVE USERS, INSTALLS AND STICKINESS
# -----------------------------------------------------------------------------

# Number of unique active users per day
dau = (
    sessions
    .groupby("session_date")["user_id"]
    .nunique()
    .rename("dau")
)

# Number of new users installed per day
installs = (
    users
    .groupby("install_date")["user_id"]
    .nunique()
    .rename("new_installs")
)

# Combine DAU and installs
daily = pd.concat([dau, installs], axis=1).fillna(0)

# Create a continuous date range
all_dates = pd.date_range(
    start=daily.index.min(),
    end=daily.index.max(),
    freq="D"
)

daily = daily.reindex(all_dates, fill_value=0)
daily.index.name = "date"

# Calculate trailing 30-day active users
mau_values = []

sessions_sorted = sessions.sort_values("session_date")

for current_date in daily.index:

    window_start = current_date - pd.Timedelta(days=29)

    active_users = sessions_sorted.loc[
        (sessions_sorted["session_date"] > window_start)
        & (sessions_sorted["session_date"] <= current_date),
        "user_id"
    ].nunique()

    mau_values.append(active_users)

daily["mau_trailing_30d"] = mau_values

# DAU / MAU stickiness
daily["dau_mau_stickiness_pct"] = np.where(
    daily["mau_trailing_30d"] > 0,
    (daily["dau"] / daily["mau_trailing_30d"]) * 100,
    0
).round(2)


# -----------------------------------------------------------------------------
# 4. DAILY REVENUE AND ROLLING AVERAGES
# -----------------------------------------------------------------------------

daily_revenue = (
    txns
    .groupby("transaction_date")["revenue_usd"]
    .sum()
    .rename("revenue")
)

daily = daily.join(daily_revenue, how="left")

daily["revenue"] = daily["revenue"].fillna(0)

# Rolling 7-day averages
daily["revenue_7d_avg"] = (
    daily["revenue"]
    .rolling(window=7, min_periods=1)
    .mean()
    .round(2)
)

daily["dau_7d_avg"] = (
    daily["dau"]
    .rolling(window=7, min_periods=1)
    .mean()
    .round(2)
)

# Convert date index into a normal column
daily = daily.reset_index()

# Save daily KPI trend
daily.to_csv(
    DATA / "daily_kpi_trend.csv",
    index=False
)

print("\nDaily KPI trend saved.")


# -----------------------------------------------------------------------------
# 5. RETENTION CALCULATION
# -----------------------------------------------------------------------------

# Keep only unique user/day combinations
active_days = sessions[
    ["user_id", "day_index"]
].drop_duplicates()


def get_retained_users(data, day):
    """
    Returns users who were active on a particular day after installation.
    """
    return set(
        data.loc[
            data["day_index"] == day,
            "user_id"
        ]
    )


d1_users = get_retained_users(active_days, 1)
d7_users = get_retained_users(active_days, 7)
d30_users = get_retained_users(active_days, 30)

# Add retention flags to the users table
users["retained_d1"] = users["user_id"].isin(d1_users).astype(int)
users["retained_d7"] = users["user_id"].isin(d7_users).astype(int)
users["retained_d30"] = users["user_id"].isin(d30_users).astype(int)

retention_columns = [
    "retained_d1",
    "retained_d7",
    "retained_d30"
]

# Overall retention
overall_retention = (
    users[retention_columns]
    .mean()
    .mul(100)
    .round(2)
)

# Retention by A/B group
retention_by_group = (
    users
    .groupby("ab_group")[retention_columns]
    .mean()
    .mul(100)
    .round(2)
)

# Retention by acquisition channel
retention_by_channel = (
    users
    .groupby("acquisition_channel")[retention_columns]
    .mean()
    .mul(100)
    .round(2)
)

# Save retention outputs
retention_by_group.to_csv(
    DATA / "python_retention_by_group.csv"
)

retention_by_channel.to_csv(
    DATA / "python_retention_by_channel.csv"
)

print("Retention calculations completed.")


# -----------------------------------------------------------------------------
# 6. REVENUE PER USER AND PAYER IDENTIFICATION
# -----------------------------------------------------------------------------

# Total revenue generated by each user
revenue_per_user = (
    txns
    .groupby("user_id")["revenue_usd"]
    .sum()
    .rename("user_revenue")
)

# Merge revenue data into users
users_with_revenue = users.merge(
    revenue_per_user,
    on="user_id",
    how="left"
)

# Users without purchases have zero revenue
users_with_revenue["user_revenue"] = (
    users_with_revenue["user_revenue"]
    .fillna(0)
)

# Identify paying users
users_with_revenue["is_payer"] = (
    users_with_revenue["user_revenue"] > 0
).astype(int)


# -----------------------------------------------------------------------------
# 7. KPI CALCULATION FUNCTION
# -----------------------------------------------------------------------------

def calculate_kpis(data):
    """
    Calculates monetization KPIs for a given group of users.
    """

    total_users = len(data)
    total_payers = int(data["is_payer"].sum())
    total_revenue = data["user_revenue"].sum()

    if total_users > 0:
        conversion_rate = (total_payers / total_users) * 100
        arpu = total_revenue / total_users
    else:
        conversion_rate = 0
        arpu = 0

    if total_payers > 0:
        arppu = total_revenue / total_payers
    else:
        arppu = 0

    return pd.Series({
        "installs": total_users,
        "payers": total_payers,
        "conversion_rate_pct": round(conversion_rate, 2),
        "arpu": round(arpu, 2),
        "arppu": round(arppu, 2),
        "total_revenue": round(total_revenue, 2)
    })


# Overall KPIs
overall_kpi = calculate_kpis(users_with_revenue)

# KPIs by acquisition channel
channel_kpi_rows = []

for channel, group_data in users_with_revenue.groupby(
    "acquisition_channel"
):
    result = calculate_kpis(group_data)
    result["acquisition_channel"] = channel
    channel_kpi_rows.append(result)

kpi_by_channel = pd.DataFrame(channel_kpi_rows)

if not kpi_by_channel.empty:
    kpi_by_channel = kpi_by_channel.set_index(
        "acquisition_channel"
    )

# KPIs by A/B group
ab_kpi_rows = []

for group_name, group_data in users_with_revenue.groupby(
    "ab_group"
):
    result = calculate_kpis(group_data)
    result["ab_group"] = group_name
    ab_kpi_rows.append(result)

kpi_by_ab = pd.DataFrame(ab_kpi_rows)

if not kpi_by_ab.empty:
    kpi_by_ab = kpi_by_ab.set_index("ab_group")


# Save KPI breakdowns
kpi_by_channel.to_csv(
    DATA / "python_kpi_by_channel.csv"
)

kpi_by_ab.to_csv(
    DATA / "python_kpi_by_ab_group.csv"
)

print("Monetization KPIs calculated.")


# -----------------------------------------------------------------------------
# 8. CONSOLIDATED KPI SUMMARY
# -----------------------------------------------------------------------------

summary = {
    "total_users": len(users),
    "total_sessions": len(sessions),
    "total_revenue_usd": round(
        txns["revenue_usd"].sum(),
        2
    ),
    "d1_retention_pct": overall_retention["retained_d1"],
    "d7_retention_pct": overall_retention["retained_d7"],
    "d30_retention_pct": overall_retention["retained_d30"],
    "conversion_rate_pct": overall_kpi["conversion_rate_pct"],
    "arpu": overall_kpi["arpu"],
    "arppu": overall_kpi["arppu"],
    "avg_dau": round(daily["dau"].mean(), 1),
    "peak_dau": int(daily["dau"].max()),
    "avg_stickiness_pct": round(
        daily["dau_mau_stickiness_pct"].mean(),
        2
    )
}

summary_df = pd.DataFrame([summary])

summary_df.to_csv(
    REPORTS / "kpi_summary.csv",
    index=False
)


# -----------------------------------------------------------------------------
# 9. PRINT RESULTS
# -----------------------------------------------------------------------------

print("\n" + "=" * 70)
print("OVERALL KPI SUMMARY")
print("=" * 70)

print(
    summary_df
    .T
    .rename(columns={0: "value"})
)

print("\n" + "=" * 70)
print("RETENTION BY A/B GROUP")
print("=" * 70)

print(retention_by_group)

print("\n" + "=" * 70)
print("KPI BY A/B GROUP")
print("=" * 70)

print(kpi_by_ab)

print("\n" + "=" * 70)
print("KPI BY ACQUISITION CHANNEL")
print("=" * 70)

print(kpi_by_channel)

print("\nDaily KPI rows:", len(daily))

print("\nFiles successfully generated:")
print("- data/daily_kpi_trend.csv")
print("- data/python_retention_by_group.csv")
print("- data/python_retention_by_channel.csv")
print("- data/python_kpi_by_channel.csv")
print("- data/python_kpi_by_ab_group.csv")
print("- outputs/reports/kpi_summary.csv")