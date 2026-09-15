"""
04_regression_analysis.py
-------------------------

Performs:

1. Logistic regression:
   Predicts D7 retention using early engagement, A/B group,
   device, and acquisition channel.

2. Linear regression:
   Predicts total revenue using engagement and retention metrics.

Outputs:
    data/logistic_regression_d7_retention.csv
    data/ols_regression_revenue.csv
    outputs/reports/logistic_regression_d7_retention.csv
    outputs/reports/ols_regression_revenue.csv
"""

import numpy as np
import pandas as pd

from pathlib import Path
from scipy import stats

from sklearn.linear_model import LogisticRegression


# ---------------------------------------------------------------------
# 1. PROJECT PATHS
# ---------------------------------------------------------------------

# Automatically detects:
# E:\Resume Project\Mobile-game-analytics
ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
REPORTS = ROOT / "outputs" / "reports"

# Create output directory if it does not exist
REPORTS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------
# 2. LOAD DATA
# ---------------------------------------------------------------------

users = pd.read_csv(
    DATA / "dim_users.csv",
    parse_dates=["install_date"]
)

sessions = pd.read_csv(
    DATA / "fact_sessions.csv",
    parse_dates=["session_date"]
)

txns = pd.read_csv(
    DATA / "fact_transactions.csv",
    parse_dates=["transaction_date"]
)

print("Data loaded successfully.")
print("Users:", len(users))
print("Sessions:", len(sessions))
print("Transactions:", len(txns))


# ---------------------------------------------------------------------
# 3. FEATURE ENGINEERING
# ---------------------------------------------------------------------

# Day 0 engagement
d0 = (
    sessions[sessions["day_index"] == 0]
    .groupby("user_id")
    .agg(
        d0_sessions=("session_id", "count"),
        d0_duration=("session_duration_min", "sum"),
        d0_max_level=("level_reached", "max")
    )
)

# Engagement during the first 4 days
early = (
    sessions[sessions["day_index"].between(0, 3)]
    .groupby("user_id")
    .agg(
        early_sessions=("session_id", "count"),
        early_duration=("session_duration_min", "sum"),
        early_max_level=("level_reached", "max")
    )
)

# Users retained on D7 and D30
active_days = sessions[["user_id", "day_index"]].drop_duplicates()

d7_ids = set(
    active_days.loc[
        active_days["day_index"] == 7,
        "user_id"
    ]
)

d30_ids = set(
    active_days.loc[
        active_days["day_index"] == 30,
        "user_id"
    ]
)

# Total revenue per user
revenue_per_user = (
    txns.groupby("user_id")["revenue_usd"]
    .sum()
    .rename("total_revenue")
)

# Total sessions per user
total_sessions = (
    sessions.groupby("user_id")["session_id"]
    .count()
    .rename("total_sessions")
)

# Maximum level reached by each user
max_level_overall = (
    sessions.groupby("user_id")["level_reached"]
    .max()
    .rename("max_level_overall")
)


# ---------------------------------------------------------------------
# 4. CREATE USER-LEVEL ANALYTICS TABLE
# ---------------------------------------------------------------------

df = (
    users.set_index("user_id")
    .join(d0, how="left")
    .join(early, how="left")
    .join(revenue_per_user, how="left")
    .join(total_sessions, how="left")
    .join(max_level_overall, how="left")
)

# Replace missing engagement and revenue values with zero
fill_values = {
    "d0_sessions": 0,
    "d0_duration": 0,
    "d0_max_level": 0,
    "early_sessions": 0,
    "early_duration": 0,
    "early_max_level": 0,
    "total_revenue": 0,
    "total_sessions": 0,
    "max_level_overall": 0
}

df = df.fillna(fill_values).reset_index()

# Retention flags
df["retained_d7"] = df["user_id"].isin(d7_ids).astype(int)
df["retained_d30"] = df["user_id"].isin(d30_ids).astype(int)

# A/B group flag
df["is_treatment"] = (
    df["ab_group"] == "treatment"
).astype(int)

# Device flag
df["is_ios"] = (
    df["device"] == "iOS"
).astype(int)

# Convert acquisition channel into dummy variables
df = pd.get_dummies(
    df,
    columns=["acquisition_channel"],
    prefix="ch",
    drop_first=True
)

# Identify all channel dummy columns
channel_cols = [
    column
    for column in df.columns
    if column.startswith("ch_")
]


# ---------------------------------------------------------------------
# 5. LOGISTIC REGRESSION
# ---------------------------------------------------------------------

feature_cols = [
    "early_sessions",
    "early_duration",
    "early_max_level",
    "is_treatment",
    "is_ios"
] + channel_cols

X_raw = df[feature_cols].astype(float).values
y = df["retained_d7"].astype(int).values

# Standardize numerical and binary features
feature_means = X_raw.mean(axis=0)
feature_stds = X_raw.std(axis=0)

# Prevent division by zero for constant columns
feature_stds[feature_stds == 0] = 1

X = (X_raw - feature_means) / feature_stds

# Fit logistic regression
logit = LogisticRegression(
    max_iter=2000,
    solver="lbfgs"
)

logit.fit(X, y)

# Predicted probabilities
probs = logit.predict_proba(X)[:, 1]

# Add intercept column
X_design = np.column_stack(
    [
        np.ones(len(X)),
        X
    ]
)

# ---------------------------------------------------------------------
# 6. LOGISTIC REGRESSION STANDARD ERRORS
# ---------------------------------------------------------------------

# Avoid creating a huge 6000 x 6000 diagonal matrix.
# Instead, multiply each row by its corresponding weight.

weights = probs * (1 - probs)

weighted_X = X_design * weights[:, np.newaxis]

information_matrix = X_design.T @ weighted_X

try:
    covariance_matrix = np.linalg.inv(information_matrix)
except np.linalg.LinAlgError:
    covariance_matrix = np.linalg.pinv(information_matrix)

standard_errors = np.sqrt(
    np.maximum(
        np.diag(covariance_matrix),
        0
    )
)

coefficients = np.concatenate(
    [
        logit.intercept_,
        logit.coef_[0]
    ]
)

# Avoid division by zero
safe_standard_errors = np.where(
    standard_errors == 0,
    np.nan,
    standard_errors
)

z_scores = coefficients / safe_standard_errors

p_values = 2 * (
    1 - stats.norm.cdf(np.abs(z_scores))
)

odds_ratios = np.exp(coefficients)

logit_summary = pd.DataFrame(
    {
        "feature": ["intercept"] + feature_cols,
        "coef": np.round(coefficients, 4),
        "std_err": np.round(standard_errors, 4),
        "z": np.round(z_scores, 3),
        "p_value": np.round(p_values, 4),
        "odds_ratio": np.round(odds_ratios, 3),
        "significant_at_05": p_values < 0.05
    }
)

logit_output = (
    REPORTS / "logistic_regression_d7_retention.csv"
)

logit_summary.to_csv(
    logit_output,
    index=False
)


# ---------------------------------------------------------------------
# 7. LOGISTIC REGRESSION MODEL METRICS
# ---------------------------------------------------------------------

from sklearn.metrics import log_loss

model_log_likelihood = -log_loss(
    y,
    probs,
    normalize=False
)

base_rate = y.mean()

null_probabilities = np.full(
    shape=len(y),
    fill_value=base_rate,
    dtype=float
)

null_log_likelihood = -log_loss(
    y,
    null_probabilities,
    normalize=False
)

mcfadden_r2 = 1 - (
    model_log_likelihood / null_log_likelihood
)

accuracy = (
    logit.predict(X) == y
).mean()

print("\n" + "=" * 80)
print("LOGISTIC REGRESSION: D7 RETENTION")
print("=" * 80)

print(logit_summary.to_string(index=False))

print(f"\nMcFadden's Pseudo R²: {mcfadden_r2:.4f}")
print(f"Model Accuracy: {accuracy:.4f}")
print(f"Base D7 Retention Rate: {base_rate:.4f}")

print(
    "\nLogistic regression saved to:",
    logit_output
)


# ---------------------------------------------------------------------
# 8. LINEAR REGRESSION USING ORDINARY LEAST SQUARES
# ---------------------------------------------------------------------

linear_features = [
    "total_sessions",
    "max_level_overall",
    "retained_d7",
    "retained_d30",
    "is_treatment"
]

X_linear = df[linear_features].astype(float).values
y_linear = df["total_revenue"].astype(float).values

# Add intercept column
X_linear_design = np.column_stack(
    [
        np.ones(len(X_linear)),
        X_linear
    ]
)

# Estimate coefficients using least squares
beta, residuals, rank, singular_values = np.linalg.lstsq(
    X_linear_design,
    y_linear,
    rcond=None
)

n, k = X_linear_design.shape

# Predicted revenue
y_predicted = X_linear_design @ beta

# Residuals
residual_errors = y_linear - y_predicted

# Residual variance
degrees_of_freedom = n - k

if degrees_of_freedom > 0:
    sigma_squared = (
        residual_errors @ residual_errors
    ) / degrees_of_freedom
else:
    sigma_squared = np.nan

# Calculate variance-covariance matrix
try:
    xtx_inverse = np.linalg.inv(
        X_linear_design.T @ X_linear_design
    )
except np.linalg.LinAlgError:
    xtx_inverse = np.linalg.pinv(
        X_linear_design.T @ X_linear_design
    )

standard_errors_ols = np.sqrt(
    np.maximum(
        np.diag(
            sigma_squared * xtx_inverse
        ),
        0
    )
)

safe_ols_se = np.where(
    standard_errors_ols == 0,
    np.nan,
    standard_errors_ols
)

t_statistics = beta / safe_ols_se

p_values_ols = 2 * (
    1 - stats.t.cdf(
        np.abs(t_statistics),
        df=degrees_of_freedom
    )
)

# R-squared
ss_residual = np.sum(
    residual_errors ** 2
)

ss_total = np.sum(
    (y_linear - y_linear.mean()) ** 2
)

if ss_total == 0:
    r_squared = np.nan
else:
    r_squared = 1 - (
        ss_residual / ss_total
    )

# Adjusted R-squared
if n - k > 0:
    adjusted_r_squared = 1 - (
        (1 - r_squared)
        * (n - 1)
        / (n - k)
    )
else:
    adjusted_r_squared = np.nan

ols_summary = pd.DataFrame(
    {
        "feature": ["intercept"] + linear_features,
        "coef": np.round(beta, 4),
        "std_err": np.round(standard_errors_ols, 4),
        "t": np.round(t_statistics, 3),
        "p_value": np.round(p_values_ols, 4),
        "significant_at_05": p_values_ols < 0.05
    }
)

ols_output = (
    REPORTS / "ols_regression_revenue.csv"
)

ols_summary.to_csv(
    ols_output,
    index=False
)


# ---------------------------------------------------------------------
# 9. PRINT OLS RESULTS
# ---------------------------------------------------------------------

print("\n" + "=" * 80)
print("OLS REGRESSION: TOTAL REVENUE")
print("=" * 80)

print(ols_summary.to_string(index=False))

print(f"\nR²: {r_squared:.4f}")
print(f"Adjusted R²: {adjusted_r_squared:.4f}")
print(f"Number of observations: {n}")

print(
    "\nOLS regression saved to:",
    ols_output
)

print("\nRegression analysis completed successfully.")