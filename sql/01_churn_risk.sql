-- ============================================================================
-- LAYER 1a: CHURN RISK  (DuckDB; every query also works in SQLite with minor tweaks)
-- Note: the dataset has no calendar dates, only "days since the customer's previous order"
-- (capped at 30, so 30 means "30 or more"). Everything below is measured against
-- each customer's OWN rhythm, which is how a retention team would think about it anyway.
-- ============================================================================

-- QUESTION: How long does each customer normally wait between orders, and how long did they wait this time?
-- WHY IT MATTERS: A customer who orders every 3 days and then goes quiet for 12 is a very different
-- problem from a customer who orders monthly. We need a personal baseline before we can call anyone "late".
-- HOW: LAG() pulls the previous gap, a running AVG() over all earlier gaps is the personal baseline,
-- and a running COUNT() tells us how many orders of history we had at that point.
CREATE OR REPLACE TABLE order_gaps AS
SELECT
    user_id,
    order_number,
    days_since_prior_order                                   AS gap_days,
    LAG(days_since_prior_order) OVER w                       AS previous_gap,
    AVG(days_since_prior_order) OVER (
        PARTITION BY user_id ORDER BY order_number
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)    AS own_typical_gap,
    COUNT(*)   OVER (PARTITION BY user_id ORDER BY order_number) AS orders_so_far,
    MAX(order_number) OVER (PARTITION BY user_id)            AS total_orders
FROM orders
WINDOW w AS (PARTITION BY user_id ORDER BY order_number);

-- QUESTION: Who has gone quiet, or is ordering noticeably later than their own normal pattern?
-- WHY IT MATTERS: This is the early-warning list. "High risk" = the latest gap was 30+ days (a full month of silence,
-- the longest gap the data records). "Watch" = a regular shopper (usual gap under 12 days) whose latest gap is at least 1.5x their own
-- usual gap and at least 7 days, but under a month. The 7-day floor stops a daily shopper who skipped a few days being
-- flagged, and occasional shoppers are not flagged on this rule because the back-test below showed it carries no signal for them.
-- Each customer also gets a lifetime segment (Light = 4-5 orders, Core = 6-19, Loyal = 20+) reused by later queries.
-- @export customer_risk
CREATE OR REPLACE TABLE customer_risk AS
SELECT
    user_id,
    total_orders,
    CASE WHEN total_orders <= 5  THEN 'Light (4-5 orders)'
         WHEN total_orders <= 19 THEN 'Core (6-19 orders)'
         ELSE                         'Loyal (20+ orders)' END AS segment,
    ROUND(own_typical_gap, 1)                      AS typical_gap_days,
    gap_days                                       AS latest_gap_days,
    ROUND(gap_days / NULLIF(own_typical_gap, 0), 2) AS gap_vs_normal,
    CASE WHEN gap_days >= 30                                      THEN 'High risk'
         WHEN own_typical_gap < 12 AND gap_days >= 1.5 * own_typical_gap AND gap_days >= 7 THEN 'Watch'
         ELSE 'Healthy' END                        AS risk_tier
FROM order_gaps
WHERE order_number = total_orders;

-- @export risk_summary
SELECT risk_tier,
       COUNT(*)                                             AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct_of_customers,
       ROUND(AVG(typical_gap_days), 1)                      AS avg_typical_gap,
       ROUND(AVG(latest_gap_days), 1)                       AS avg_latest_gap
FROM customer_risk GROUP BY risk_tier ORDER BY customers DESC;

-- QUESTION: Is this risk flag actually predictive, or just a plausible-sounding rule?
-- WHY IT MATTERS: A churn flag nobody has tested is a guess. We rewind to each customer's 6th order, apply the same rule
-- using only what was known at that point, and count how many orders they went on to place. "Faded" = 2 or fewer further
-- orders. Results are split by how often the customer normally shops (typical gap under or over 12 days), because
-- infrequent shoppers naturally place fewer orders and would otherwise make the flag look better than it is.
-- @export risk_backtest
WITH at_order_6 AS (
    SELECT user_id, total_orders - 6 AS orders_after,
           CASE WHEN own_typical_gap < 12 THEN 'Regular shopper (gap < 12d)' ELSE 'Occasional shopper (gap 12d+)' END AS cadence,
           CASE WHEN gap_days >= 30                                      THEN 'High risk'
                WHEN own_typical_gap < 12 AND gap_days >= 1.5 * own_typical_gap AND gap_days >= 7 THEN 'Watch'
                ELSE 'Healthy' END AS tier_at_order_6
    FROM order_gaps WHERE order_number = 6
)
SELECT cadence, tier_at_order_6,
       COUNT(*)                                              AS customers,
       ROUND(100.0 * AVG((orders_after <= 2)::INT), 1)       AS pct_who_faded,
       ROUND(AVG(orders_after), 1)                           AS avg_orders_placed_afterwards
FROM at_order_6 GROUP BY ALL ORDER BY cadence, pct_who_faded;

-- QUESTION: Of the customers we'd contact first, which are worth the most?
-- WHY IT MATTERS: Retention budget is limited. RANK() inside each tier puts the customers with the most order history
-- (10+ orders) first, since losing a 40-order customer costs far more than losing a 5-order one.
-- @export top_save_list
SELECT * FROM (
    SELECT user_id, total_orders, typical_gap_days, latest_gap_days, gap_vs_normal, risk_tier,
           RANK() OVER (PARTITION BY risk_tier ORDER BY total_orders DESC, gap_vs_normal DESC) AS rank_in_tier
    FROM customer_risk WHERE total_orders >= 10 AND risk_tier <> 'Healthy'
) WHERE rank_in_tier <= 25 ORDER BY risk_tier, rank_in_tier;
