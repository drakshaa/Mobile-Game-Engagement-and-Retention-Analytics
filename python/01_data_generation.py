"""
01_data_generation.py
----------------------

Generates a realistic synthetic dataset for a mobile game analytics project:

- dim_users
- fact_sessions
- fact_transactions
- ab_test_assignments

The dataset includes:
- Install dates
- Acquisition channels
- Countries
- Devices
- A/B groups
- Session activity
- Retention behavior
- Session duration
- Levels reached
- In-app purchases
"""

import numpy as np
import pandas as pd

from datetime import datetime, timedelta
from pathlib import Path


# ----------------------------------------------------------------------------
# RANDOM SEED
# ----------------------------------------------------------------------------

np.random.seed(42)


# ----------------------------------------------------------------------------
# PROJECT PATHS
# ----------------------------------------------------------------------------

# Project folder:
# E:\Resume Project\Mobile-game-analytics

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Data folder:
# E:\Resume Project\Mobile-game-analytics\data

DATA_DIR = PROJECT_DIR / "data"

# Create the data folder if it does not exist
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------

N_USERS = 6000

INSTALL_WINDOW_DAYS = 90

OBSERVATION_END = datetime(2025, 12, 31)

INSTALL_START = (
    OBSERVATION_END - timedelta(days=INSTALL_WINDOW_DAYS)
)


CHANNELS = [
    "Organic",
    "Paid_Social",
    "Paid_UA_Network",
    "Influencer",
    "Cross_Promo"
]

CHANNEL_WEIGHTS = [
    0.30,
    0.25,
    0.20,
    0.15,
    0.10
]


COUNTRIES = [
    "US",
    "UK",
    "IN",
    "BR",
    "DE",
    "CA",
    "AU",
    "PH",
    "MX",
    "FR"
]

COUNTRY_WEIGHTS = [
    0.22,
    0.10,
    0.16,
    0.10,
    0.08,
    0.06,
    0.05,
    0.08,
    0.08,
    0.07
]


DEVICES = [
    "iOS",
    "Android"
]

DEVICE_WEIGHTS = [
    0.35,
    0.65
]


# ----------------------------------------------------------------------------
# 1. CREATE USERS AND A/B ASSIGNMENTS
# ----------------------------------------------------------------------------

user_ids = [
    f"U{100000 + i}"
    for i in range(N_USERS)
]


install_offsets = np.random.randint(
    0,
    INSTALL_WINDOW_DAYS,
    N_USERS
)


install_dates = [
    INSTALL_START + timedelta(days=int(offset))
    for offset in install_offsets
]


channels = np.random.choice(
    CHANNELS,
    N_USERS,
    p=CHANNEL_WEIGHTS
)


countries = np.random.choice(
    COUNTRIES,
    N_USERS,
    p=COUNTRY_WEIGHTS
)


devices = np.random.choice(
    DEVICES,
    N_USERS,
    p=DEVICE_WEIGHTS
)


# 50/50 experiment assignment
ab_group = np.random.choice(
    ["control", "treatment"],
    N_USERS,
    p=[0.5, 0.5]
)


# User quality affects retention and monetization
channel_quality = {
    "Organic": 0.15,
    "Influencer": 0.10,
    "Cross_Promo": 0.05,
    "Paid_Social": -0.05,
    "Paid_UA_Network": -0.10
}


quality_noise = np.random.normal(
    0,
    0.25,
    N_USERS
)


user_quality = np.array([
    channel_quality[channel]
    for channel in channels
]) + quality_noise


dim_users = pd.DataFrame({
    "user_id": user_ids,
    "install_date": install_dates,
    "acquisition_channel": channels,
    "country": countries,
    "device": devices,
    "ab_group": ab_group,
    "_quality": user_quality
})


# ----------------------------------------------------------------------------
# 2. SIMULATE RETENTION AND SESSIONS
# ----------------------------------------------------------------------------

def retention_prob(day, quality, group):
    """
    Returns the probability that a user is active on a particular day.
    """

    base_retention = {
        1: 0.42,
        2: 0.33,
        3: 0.28,
        7: 0.19,
        14: 0.13,
        21: 0.10,
        30: 0.085
    }

    if day in base_retention:
        probability = base_retention[day]

    else:
        probability = (
            0.45 * np.exp(-0.11 * day) + 0.06
        )

    # Adjust for user quality
    probability += quality

    # Treatment effect
    if group == "treatment":

        treatment_lift = {
            1: 0.055,
            2: 0.045,
            3: 0.035,
            7: 0.028,
            14: 0.015,
            21: 0.010,
            30: 0.006
        }

        probability += treatment_lift.get(
            day,
            0.012 * np.exp(-0.05 * day)
        )

    return float(
        np.clip(probability, 0.01, 0.97)
    )


CHECK_DAYS = [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    10,
    14,
    21,
    30,
    45,
    60
]


session_rows = []


for _, row in dim_users.iterrows():

    uid = row["user_id"]
    install_dt = row["install_date"]
    quality = row["_quality"]
    group = row["ab_group"]

    days_observed_cap = (
        OBSERVATION_END - install_dt
    ).days

    # Every user has an install-day session
    session_rows.append(
        (
            uid,
            install_dt,
            0,
            1
        )
    )

    for day in CHECK_DAYS:

        if day == 0:
            continue

        if day > days_observed_cap:
            continue

        probability = retention_prob(
            day,
            quality,
            group
        )

        if np.random.random() < probability:

            number_of_sessions = (
                np.random.poisson(1.4) + 1
            )

            session_rows.append(
                (
                    uid,
                    install_dt + timedelta(days=day),
                    day,
                    number_of_sessions
                )
            )


# ----------------------------------------------------------------------------
# 3. EXPAND DAILY ACTIVITY INTO SESSION-LEVEL DATA
# ----------------------------------------------------------------------------

sessions_expanded = []


for uid, session_date, day_index, number_of_sessions in session_rows:

    for _ in range(number_of_sessions):

        # Session duration in minutes
        duration = max(
            1,
            np.random.gamma(
                shape=2.2,
                scale=4.5
            )
        )

        # Simulated level reached
        level_reached = min(
            200,
            max(
                1,
                int(
                    np.random.normal(
                        5 + day_index * 1.8,
                        4
                    )
                )
            )
        )

        sessions_expanded.append({
            "user_id": uid,
            "session_date": session_date,
            "day_index": day_index,
            "session_duration_min": round(
                duration,
                2
            ),
            "level_reached": level_reached
        })


fact_sessions = pd.DataFrame(
    sessions_expanded
)


# Add unique session IDs
fact_sessions["session_id"] = [
    f"S{i:07d}"
    for i in range(len(fact_sessions))
]


# Arrange columns
fact_sessions = fact_sessions[
    [
        "session_id",
        "user_id",
        "session_date",
        "day_index",
        "session_duration_min",
        "level_reached"
    ]
]


# ----------------------------------------------------------------------------
# 4. GENERATE IN-APP PURCHASE TRANSACTIONS
# ----------------------------------------------------------------------------

IAP_SKUS = [
    ("Starter_Pack", 2.99),
    ("Gem_Bundle_S", 4.99),
    ("Gem_Bundle_M", 9.99),
    ("Gem_Bundle_L", 19.99),
    ("Battle_Pass", 7.99),
    ("No_Ads", 3.99),
    ("Mega_Bundle", 49.99),
    ("VIP_Subscription", 12.99)
]


sku_names = [
    sku[0]
    for sku in IAP_SKUS
]


sku_prices = {
    sku[0]: sku[1]
    for sku in IAP_SKUS
}


sku_weights = [
    0.22,
    0.20,
    0.16,
    0.08,
    0.14,
    0.10,
    0.03,
    0.07
]


# Calculate user engagement
user_engagement = (
    fact_sessions
    .groupby("user_id")
    .agg(
        total_sessions=("session_id", "count"),
        max_level=("level_reached", "max")
    )
    .reset_index()
)


# Add engagement information to users
dim_users_e = dim_users.merge(
    user_engagement,
    on="user_id",
    how="left"
)


dim_users_e = dim_users_e.fillna({
    "total_sessions": 1,
    "max_level": 1
})


transaction_rows = []

transaction_id = 0


for _, row in dim_users_e.iterrows():

    engagement_score = (
        np.log1p(row["total_sessions"]) * 0.10
        + row["max_level"] * 0.001
    )

    pay_probability = np.clip(
        0.03
        + engagement_score
        + row["_quality"] * 0.15
        + (
            0.015
            if row["ab_group"] == "treatment"
            else 0
        ),
        0.005,
        0.6
    )

    is_payer = (
        np.random.random()
        < pay_probability
    )

    if is_payer:

        number_of_transactions = (
            np.random.poisson(1.6) + 1
        )

        for _ in range(number_of_transactions):

            available_days = (
                OBSERVATION_END - row["install_date"]
            ).days

            days_after_install = np.random.randint(
                0,
                max(1, available_days)
            )

            transaction_date = (
                row["install_date"]
                + timedelta(days=int(days_after_install))
            )

            if transaction_date > OBSERVATION_END:
                continue

            sku = np.random.choice(
                sku_names,
                p=sku_weights
            )

            transaction_rows.append({
                "transaction_id": f"T{transaction_id:07d}",
                "user_id": row["user_id"],
                "transaction_date": transaction_date,
                "sku": sku,
                "revenue_usd": sku_prices[sku]
            })

            transaction_id += 1


fact_transactions = pd.DataFrame(
    transaction_rows
)


# ----------------------------------------------------------------------------
# 5. CREATE A/B TEST ASSIGNMENT TABLE
# ----------------------------------------------------------------------------

ab_test_assignments = dim_users[
    [
        "user_id",
        "ab_group",
        "install_date"
    ]
].copy()


ab_test_assignments["experiment_name"] = (
    "onboarding_flow_v2"
)


ab_test_assignments["assignment_date"] = (
    ab_test_assignments["install_date"]
)


ab_test_assignments = ab_test_assignments.drop(
    columns=["install_date"]
)


# ----------------------------------------------------------------------------
# 6. EXPORT CSV FILES
# ----------------------------------------------------------------------------

# Remove the hidden quality variable before exporting users
dim_users_out = dim_users.drop(
    columns=["_quality"]
)


# Save all datasets inside the project's data folder
dim_users_out.to_csv(
    DATA_DIR / "dim_users.csv",
    index=False
)


fact_sessions.to_csv(
    DATA_DIR / "fact_sessions.csv",
    index=False
)


fact_transactions.to_csv(
    DATA_DIR / "fact_transactions.csv",
    index=False
)


ab_test_assignments.to_csv(
    DATA_DIR / "ab_test_assignments.csv",
    index=False
)


# ----------------------------------------------------------------------------
# 7. PRINT SUMMARY
# ----------------------------------------------------------------------------

print("\nDataset generation completed successfully.")

print("Data saved to:")
print(DATA_DIR)

print("\nUsers:", len(dim_users_out))

print("Sessions:", len(fact_sessions))

print("Transactions:", len(fact_transactions))

print(
    "Payers:",
    fact_transactions["user_id"].nunique(),
    "/",
    len(dim_users_out)
)

print(
    "Total revenue: $",
    round(
        fact_transactions["revenue_usd"].sum(),
        2
    )
)