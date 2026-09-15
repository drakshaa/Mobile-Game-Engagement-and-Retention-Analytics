/* ============================================================================
   03_kpi_and_monetization.sql
   Core recurring KPIs: DAU, conversion rate, ARPU, ARPPU, revenue by channel,
   and an A/B test summary table (feeds Python stats + Power BI dashboard).
   ============================================================================ */

-- ----------------------------------------------------------------------------
-- QUERY 1: Daily Active Users (DAU) and New Installs by day
-- ----------------------------------------------------------------------------
WITH daily_active AS (
    SELECT session_date AS activity_date, COUNT(DISTINCT user_id) AS dau
    FROM fact_sessions
    GROUP BY session_date
),
daily_installs AS (
    SELECT install_date AS activity_date, COUNT(DISTINCT user_id) AS new_installs
    FROM dim_users
    GROUP BY install_date
)
SELECT
    COALESCE(a.activity_date, i.activity_date) AS activity_date,
    COALESCE(a.dau, 0)            AS dau,
    COALESCE(i.new_installs, 0)   AS new_installs
FROM daily_active a
FULL OUTER JOIN daily_installs i ON a.activity_date = i.activity_date
ORDER BY activity_date;
-- NOTE: SQLite has no native FULL OUTER JOIN support. The Python KPI script
-- (02_kpi_automation.py) implements the equivalent logic with a LEFT JOIN /
-- UNION pattern (pandas merge how='outer') for portability across engines.


-- ----------------------------------------------------------------------------
-- QUERY 2: Conversion rate (installs -> payers) and ARPU / ARPPU by channel
-- ----------------------------------------------------------------------------
WITH revenue_per_user AS (
    SELECT user_id, SUM(revenue_usd) AS user_revenue, COUNT(*) AS n_purchases
    FROM fact_transactions
    GROUP BY user_id
)
SELECT
    u.acquisition_channel,
    COUNT(DISTINCT u.user_id)                                        AS installs,
    COUNT(DISTINCT r.user_id)                                        AS payers,
    ROUND(100.0 * COUNT(DISTINCT r.user_id) / COUNT(DISTINCT u.user_id), 2) AS conversion_rate_pct,
    ROUND(SUM(COALESCE(r.user_revenue, 0)) / COUNT(DISTINCT u.user_id), 2)   AS arpu,
    ROUND(SUM(COALESCE(r.user_revenue, 0)) / NULLIF(COUNT(DISTINCT r.user_id), 0), 2) AS arppu,
    ROUND(SUM(COALESCE(r.user_revenue, 0)), 2)                        AS total_revenue
FROM dim_users u
LEFT JOIN revenue_per_user r ON r.user_id = u.user_id
GROUP BY u.acquisition_channel
ORDER BY total_revenue DESC;


-- ----------------------------------------------------------------------------
-- QUERY 3: Revenue by SKU with CASE-based product category tagging
-- ----------------------------------------------------------------------------
SELECT
    sku,
    CASE
        WHEN sku LIKE 'Gem%'      THEN 'Currency'
        WHEN sku = 'Battle_Pass'  THEN 'Season Content'
        WHEN sku = 'No_Ads'       THEN 'QoL / Ads Removal'
        WHEN sku = 'VIP_Subscription' THEN 'Subscription'
        ELSE 'Starter / Bundle'
    END AS product_category,
    COUNT(*) AS n_purchases,
    ROUND(SUM(revenue_usd), 2) AS total_revenue,
    ROUND(AVG(revenue_usd), 2) AS avg_price
FROM fact_transactions
GROUP BY sku
ORDER BY total_revenue DESC;


-- ----------------------------------------------------------------------------
-- QUERY 4: A/B TEST SUMMARY — conversion & retention by experiment group
-- (raw counts feed the statistical significance test done in Python,
--  02_ab_testing.py, since SQL alone can compute rates but not p-values.)
-- ----------------------------------------------------------------------------
WITH active_flags AS (
    SELECT DISTINCT user_id, day_index FROM fact_sessions
),
user_level AS (
    SELECT
        u.user_id,
        u.ab_group,
        MAX(CASE WHEN a.day_index = 1  THEN 1 ELSE 0 END) AS retained_d1,
        MAX(CASE WHEN a.day_index = 7  THEN 1 ELSE 0 END) AS retained_d7,
        MAX(CASE WHEN a.day_index = 30 THEN 1 ELSE 0 END) AS retained_d30,
        CASE WHEN t.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_payer,
        COALESCE(t.total_revenue, 0) AS total_revenue
    FROM dim_users u
    LEFT JOIN active_flags a ON a.user_id = u.user_id
    LEFT JOIN (
        SELECT user_id, SUM(revenue_usd) AS total_revenue
        FROM fact_transactions
        GROUP BY user_id
    ) t ON t.user_id = u.user_id
    GROUP BY u.user_id, u.ab_group, t.user_id, t.total_revenue
)
SELECT
    ab_group,
    COUNT(*)                                            AS n_users,
    SUM(retained_d1)                                    AS retained_d1_count,
    ROUND(100.0 * SUM(retained_d1) / COUNT(*), 2)        AS d1_retention_pct,
    SUM(retained_d7)                                     AS retained_d7_count,
    ROUND(100.0 * SUM(retained_d7) / COUNT(*), 2)        AS d7_retention_pct,
    SUM(retained_d30)                                    AS retained_d30_count,
    ROUND(100.0 * SUM(retained_d30) / COUNT(*), 2)       AS d30_retention_pct,
    SUM(is_payer)                                        AS payer_count,
    ROUND(100.0 * SUM(is_payer) / COUNT(*), 2)           AS conversion_rate_pct,
    ROUND(SUM(total_revenue) / COUNT(*), 2)              AS arpu
FROM user_level
GROUP BY ab_group;
