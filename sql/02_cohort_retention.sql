/* ============================================================================
   02_cohort_retention.sql
   D1 / D7 / D30 cohort retention using CTEs, CASE statements, aggregations
   and window functions.
   ============================================================================ */

-- ----------------------------------------------------------------------------
-- QUERY 1: User-level retention flags (D1 / D7 / D30 "did they come back?")
-- ----------------------------------------------------------------------------
WITH user_active_days AS (
    -- distinct day_index values on which each user had >=1 session
    SELECT DISTINCT user_id, day_index
    FROM fact_sessions
),
user_retention_flags AS (
    SELECT
        u.user_id,
        u.install_date,
        u.acquisition_channel,
        u.ab_group,
        MAX(CASE WHEN a.day_index = 1  THEN 1 ELSE 0 END) AS retained_d1,
        MAX(CASE WHEN a.day_index = 7  THEN 1 ELSE 0 END) AS retained_d7,
        MAX(CASE WHEN a.day_index = 30 THEN 1 ELSE 0 END) AS retained_d30
    FROM dim_users u
    LEFT JOIN user_active_days a ON a.user_id = u.user_id
    GROUP BY u.user_id, u.install_date, u.acquisition_channel, u.ab_group
)
SELECT * FROM user_retention_flags
LIMIT 20;


-- ----------------------------------------------------------------------------
-- QUERY 2: Install-date cohort retention table (classic cohort matrix)
-- Only cohorts old enough to have reached each horizon are included,
-- computed with a window function comparing cohort age to today's max date.
-- ----------------------------------------------------------------------------
WITH install_cohorts AS (
    SELECT
        user_id,
        install_date,
        ab_group,
        acquisition_channel
    FROM dim_users
),
active_flags AS (
    SELECT DISTINCT user_id, day_index FROM fact_sessions
),
cohort_base AS (
    SELECT
        c.install_date AS cohort_date,
        c.user_id,
        c.ab_group,
        c.acquisition_channel,
        MAX(CASE WHEN a.day_index = 0  THEN 1 ELSE 0 END) AS d0,
        MAX(CASE WHEN a.day_index = 1  THEN 1 ELSE 0 END) AS d1,
        MAX(CASE WHEN a.day_index = 7  THEN 1 ELSE 0 END) AS d7,
        MAX(CASE WHEN a.day_index = 30 THEN 1 ELSE 0 END) AS d30
    FROM install_cohorts c
    LEFT JOIN active_flags a ON a.user_id = c.user_id
    GROUP BY c.install_date, c.user_id, c.ab_group, c.acquisition_channel
)
SELECT
    cohort_date,
    COUNT(DISTINCT user_id)                                   AS cohort_size,
    ROUND(100.0 * SUM(d1)  / COUNT(DISTINCT user_id), 2)       AS d1_retention_pct,
    ROUND(100.0 * SUM(d7)  / COUNT(DISTINCT user_id), 2)       AS d7_retention_pct,
    ROUND(100.0 * SUM(d30) / COUNT(DISTINCT user_id), 2)       AS d30_retention_pct
FROM cohort_base
GROUP BY cohort_date
ORDER BY cohort_date;


-- ----------------------------------------------------------------------------
-- QUERY 3: Retention by acquisition channel AND A/B group, with rank()
-- window function to surface the best/worst performing segments.
-- ----------------------------------------------------------------------------
WITH active_flags AS (
    SELECT DISTINCT user_id, day_index FROM fact_sessions
),
user_flags AS (
    SELECT
        u.user_id,
        u.acquisition_channel,
        u.ab_group,
        MAX(CASE WHEN a.day_index = 1  THEN 1 ELSE 0 END) AS d1,
        MAX(CASE WHEN a.day_index = 7  THEN 1 ELSE 0 END) AS d7,
        MAX(CASE WHEN a.day_index = 30 THEN 1 ELSE 0 END) AS d30
    FROM dim_users u
    LEFT JOIN active_flags a ON a.user_id = u.user_id
    GROUP BY u.user_id, u.acquisition_channel, u.ab_group
),
segment_summary AS (
    SELECT
        acquisition_channel,
        ab_group,
        COUNT(*) AS users,
        ROUND(100.0 * SUM(d1)  / COUNT(*), 2) AS d1_pct,
        ROUND(100.0 * SUM(d7)  / COUNT(*), 2) AS d7_pct,
        ROUND(100.0 * SUM(d30) / COUNT(*), 2) AS d30_pct
    FROM user_flags
    GROUP BY acquisition_channel, ab_group
)
SELECT
    *,
    RANK() OVER (ORDER BY d30_pct DESC) AS d30_rank_overall,
    ROUND(d30_pct - AVG(d30_pct) OVER (), 2) AS d30_vs_overall_avg
FROM segment_summary
ORDER BY d30_rank_overall;


-- ----------------------------------------------------------------------------
-- QUERY 4: Root-cause / drop-off analysis — where in the funnel do users
-- who churn before D7 stop showing up? Uses a CASE-based day bucket and a
-- running (window) cumulative share of drop-off.
-- ----------------------------------------------------------------------------
WITH last_active_day AS (
    SELECT
        user_id,
        MAX(day_index) AS last_day_index
    FROM fact_sessions
    GROUP BY user_id
),
churned_before_d7 AS (
    SELECT
        l.user_id,
        l.last_day_index,
        CASE
            WHEN l.last_day_index = 0 THEN 'Churned Day 0 (never returned)'
            WHEN l.last_day_index BETWEEN 1 AND 2 THEN 'Churned Day 1-2'
            WHEN l.last_day_index BETWEEN 3 AND 6 THEN 'Churned Day 3-6'
            ELSE 'Retained to D7+'
        END AS churn_bucket
    FROM last_active_day l
)
SELECT
    churn_bucket,
    COUNT(*) AS users,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_all_users,
    SUM(COUNT(*)) OVER (ORDER BY MIN(last_day_index)) AS running_total_users
FROM churned_before_d7
GROUP BY churn_bucket
ORDER BY MIN(last_day_index);
