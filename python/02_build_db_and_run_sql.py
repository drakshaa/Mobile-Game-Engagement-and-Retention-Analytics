"""
02_build_db_and_run_sql.py
--------------------------
Loads generated CSV files into a SQLite database, executes SQL queries,
and exports results for Power BI and Python analysis.
"""

import sqlite3
import pandas as pd
import re
from pathlib import Path


# ---------------------------------------------------------
# 1. PROJECT PATHS
# ---------------------------------------------------------

# Automatically detects the project root:
# E:\Resume Project\Mobile-game-analytics
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
REPORT_DIR = ROOT / "outputs" / "reports"

DB_PATH = DATA_DIR / "game_analytics.db"

# Create required folders if they do not exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
SQL_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

print("Project root:", ROOT)
print("Data directory:", DATA_DIR)
print("SQL directory:", SQL_DIR)
print("Database path:", DB_PATH)


# ---------------------------------------------------------
# 2. CREATE SQLITE DATABASE
# ---------------------------------------------------------

# Delete the previous database if it exists
DB_PATH.unlink(missing_ok=True)

# Connect to SQLite
conn = sqlite3.connect(str(DB_PATH))

print("\nSQLite database connected successfully.")


# ---------------------------------------------------------
# 3. BUILD DATABASE SCHEMA
# ---------------------------------------------------------

schema_path = SQL_DIR / "01_schema.sql"

if not schema_path.exists():
    raise FileNotFoundError(
        f"Schema file not found: {schema_path}"
    )

schema_sql = schema_path.read_text(encoding="utf-8")

conn.executescript(schema_sql)

print("Database schema created successfully.")


# ---------------------------------------------------------
# 4. LOAD CSV FILES INTO SQLITE TABLES
# ---------------------------------------------------------

tables = {
    "dim_users": "dim_users.csv",
    "fact_sessions": "fact_sessions.csv",
    "fact_transactions": "fact_transactions.csv",
    "ab_test_assignments": "ab_test_assignments.csv",
}

for table_name, file_name in tables.items():

    csv_path = DATA_DIR / file_name

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV file not found: {csv_path}"
        )

    df = pd.read_csv(csv_path)

    df.to_sql(
        table_name,
        conn,
        if_exists="append",
        index=False
    )

    print(
        f"Loaded {len(df):>6} rows into table: {table_name}"
    )

conn.commit()


# ---------------------------------------------------------
# 5. SPLIT SQL FILE INTO STATEMENTS
# ---------------------------------------------------------

def split_statements(sql_text):
    """
    Splits a SQL file into individual SQL statements.

    It removes block comments and ignores comment-only statements.
    """

    # Correctly remove /* ... */ block comments
    sql_text = re.sub(
        r"/\*.*?\*/",
        "",
        sql_text,
        flags=re.DOTALL
    )

    statements = []

    for statement in sql_text.split(";"):

        statement = statement.strip()

        # Remove single-line comments
        clean_statement = "\n".join(
            line
            for line in statement.splitlines()
            if not line.strip().startswith("--")
        ).strip()

        if clean_statement:
            statements.append(clean_statement)

    return statements


# ---------------------------------------------------------
# 6. RUN SQL FILE
# ---------------------------------------------------------

def run_sql_file(path, label, max_rows=15):

    print("\n" + "=" * 90)
    print(f"RUNNING {label}")
    print("=" * 90)

    if not path.exists():
        print(f"SQL file not found: {path}")
        return []

    sql_text = path.read_text(encoding="utf-8")

    statements = split_statements(sql_text)

    results = []

    for i, statement in enumerate(statements, start=1):

        try:

            df = pd.read_sql_query(statement, conn)

            print(
                f"\n--- Statement {i}: {len(df)} rows ---"
            )

            print(
                df.head(max_rows).to_string(index=False)
            )

            results.append(df)

        except Exception as error:

            print(
                f"\n--- Statement {i} skipped ---"
            )

            print("Reason:", error)

    return results


# ---------------------------------------------------------
# 7. RUN COHORT RETENTION QUERIES
# ---------------------------------------------------------

cohort_sql_path = SQL_DIR / "02_cohort_retention.sql"

cohort_results = run_sql_file(
    cohort_sql_path,
    "02_cohort_retention.sql"
)


# ---------------------------------------------------------
# 8. RUN KPI AND MONETIZATION QUERIES
# ---------------------------------------------------------

kpi_sql_path = SQL_DIR / "03_kpi_and_monetization.sql"

if not kpi_sql_path.exists():
    raise FileNotFoundError(
        f"KPI SQL file not found: {kpi_sql_path}"
    )

kpi_sql_text = kpi_sql_path.read_text(encoding="utf-8")

kpi_statements = split_statements(kpi_sql_text)

print("\n" + "=" * 90)
print("RUNNING 03_kpi_and_monetization.sql")
print("=" * 90)


# ---------------------------------------------------------
# 9. DAILY ACTIVE USERS AND DAILY INSTALLS
# ---------------------------------------------------------

# This query avoids FULL OUTER JOIN because SQLite compatibility
# can vary between versions.

dau_query = """
WITH daily_active AS (
    SELECT
        session_date AS activity_date,
        COUNT(DISTINCT user_id) AS dau
    FROM fact_sessions
    GROUP BY session_date
),

daily_installs AS (
    SELECT
        install_date AS activity_date,
        COUNT(DISTINCT user_id) AS new_installs
    FROM dim_users
    GROUP BY install_date
),

all_dates AS (
    SELECT activity_date FROM daily_active

    UNION

    SELECT activity_date FROM daily_installs
)

SELECT
    d.activity_date,
    COALESCE(a.dau, 0) AS dau,
    COALESCE(i.new_installs, 0) AS new_installs

FROM all_dates d

LEFT JOIN daily_active a
    ON a.activity_date = d.activity_date

LEFT JOIN daily_installs i
    ON i.activity_date = d.activity_date

ORDER BY d.activity_date;
"""

df_dau = pd.read_sql_query(dau_query, conn)

print(
    f"\n--- DAU / Installs by day: {len(df_dau)} rows ---"
)

print(
    df_dau.head(10).to_string(index=False)
)

df_dau.to_csv(
    DATA_DIR / "kpi_daily_dau_installs.csv",
    index=False
)


# ---------------------------------------------------------
# 10. RUN REMAINING KPI QUERIES
# ---------------------------------------------------------

kpi_results = []

# Statement 1 is handled separately above
for i, statement in enumerate(kpi_statements[1:], start=2):

    try:

        df = pd.read_sql_query(statement, conn)

        print(
            f"\n--- Statement {i}: {len(df)} rows ---"
        )

        print(
            df.head(15).to_string(index=False)
        )

        kpi_results.append((i, df))

    except Exception as error:

        print(
            f"\n--- Statement {i} skipped ---"
        )

        print("Reason:", error)


# ---------------------------------------------------------
# 11. EXPORT COHORT RESULTS
# ---------------------------------------------------------

if len(cohort_results) >= 2:

    cohort_results[1].to_csv(
        DATA_DIR / "cohort_retention_by_install_date.csv",
        index=False
    )

if len(cohort_results) >= 3:

    cohort_results[2].to_csv(
        DATA_DIR / "retention_by_channel_and_group.csv",
        index=False
    )

if len(cohort_results) >= 4:

    cohort_results[3].to_csv(
        DATA_DIR / "churn_dropoff_buckets.csv",
        index=False
    )


# ---------------------------------------------------------
# 12. EXPORT KPI RESULTS
# ---------------------------------------------------------

for statement_number, df in kpi_results:

    if statement_number == 2:

        df.to_csv(
            DATA_DIR / "kpi_by_channel.csv",
            index=False
        )

    elif statement_number == 3:

        df.to_csv(
            DATA_DIR / "revenue_by_sku.csv",
            index=False
        )

    elif statement_number == 4:

        df.to_csv(
            DATA_DIR / "ab_test_sql_summary.csv",
            index=False
        )


# ---------------------------------------------------------
# 13. CLOSE DATABASE
# ---------------------------------------------------------

conn.close()

print("\n" + "=" * 90)
print("PROCESS COMPLETED SUCCESSFULLY")
print("=" * 90)

print("SQLite database created at:")
print(DB_PATH)

print("\nOutput CSV files saved in:")
print(DATA_DIR)