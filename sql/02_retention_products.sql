-- ============================================================================
-- LAYER 1b: WHAT KEEPS PEOPLE COMING BACK
-- Depends on customer_risk (segments) from 01_churn_risk.sql
-- ============================================================================

-- QUESTION: What did customers put in their VERY FIRST basket, and how does that relate to whether they became loyal?
-- WHY IT MATTERS: The first order is the only moment we can influence before we know who will stay. If some first-basket
-- items are strongly linked to loyalty (20+ orders) we can feature, sample or discount them for new customers.
-- We only judge products at least 1,500 new customers bought, and compare against the overall loyal rate (the baseline).
-- Lift = loyal rate of buyers of this product / baseline loyal rate. This shows association, not proof of cause.
-- @export first_basket_lift
WITH first_basket AS (
    SELECT DISTINCT o.user_id, oi.product_id
    FROM orders o JOIN order_items oi USING (order_id)
    WHERE o.order_number = 1
), base AS (
    SELECT AVG((segment LIKE 'Loyal%')::INT) AS base_loyal, AVG((segment LIKE 'Light%')::INT) AS base_light
    FROM customer_risk
)
SELECT p.product_name, d.department,
       COUNT(*)                                                      AS first_basket_buyers,
       ROUND(100.0 * AVG((c.segment LIKE 'Loyal%')::INT), 1)         AS pct_became_loyal,
       ROUND(100.0 * AVG((c.segment LIKE 'Light%')::INT), 1)         AS pct_faded_light,
       ROUND(AVG((c.segment LIKE 'Loyal%')::INT) / MAX(b.base_loyal), 2) AS loyalty_lift,
       ROUND(100.0 * MAX(b.base_loyal), 1)                           AS baseline_pct_loyal
FROM first_basket fb
JOIN customer_risk c USING (user_id)
JOIN products p USING (product_id)
JOIN departments d USING (department_id)
CROSS JOIN base b
GROUP BY p.product_name, d.department
HAVING COUNT(*) >= 1500
ORDER BY loyalty_lift DESC;

-- QUESTION: Which departments do loyal customers lean on more than customers who fade?
-- WHY IT MATTERS: It tells merchandising where "habit" categories live. A department that is a bigger part of loyal
-- customers' baskets than of light customers' baskets is part of the weekly routine, not a one-off treat.
-- @export dept_mix_by_segment
WITH seg_items AS (
    SELECT c.segment, p.department_id, COUNT(*) AS items
    FROM order_items oi
    JOIN orders o USING (order_id) JOIN customer_risk c ON c.user_id = o.user_id
    JOIN products p USING (product_id)
    GROUP BY 1, 2
), shares AS (
    SELECT segment, department_id,
           100.0 * items / SUM(items) OVER (PARTITION BY segment) AS pct_of_basket
    FROM seg_items
)
SELECT d.department,
       ROUND(MAX(CASE WHEN segment LIKE 'Loyal%' THEN pct_of_basket END), 1) AS loyal_pct_of_basket,
       ROUND(MAX(CASE WHEN segment LIKE 'Light%' THEN pct_of_basket END), 1) AS light_pct_of_basket,
       ROUND(MAX(CASE WHEN segment LIKE 'Loyal%' THEN pct_of_basket END)
           - MAX(CASE WHEN segment LIKE 'Light%' THEN pct_of_basket END), 1) AS gap_pts
FROM shares JOIN departments d USING (department_id)
GROUP BY d.department ORDER BY gap_pts DESC;

-- QUESTION: Which individual products do customers buy again and again?
-- WHY IT MATTERS: These are the "anchor" products. If they are out of stock or overpriced, repeat orders suffer first.
-- RANK() orders products inside each department by reorder rate (share of purchases that were a repeat),
-- using products with at least 5,000 purchases so a niche item cannot top the list by luck.
-- @export top_repeat_products
WITH prod AS (
    SELECT p.product_id, p.product_name, p.department_id,
           COUNT(*) AS times_bought, SUM(oi.reordered) AS times_reordered,
           ROUND(100.0 * AVG(oi.reordered), 1) AS reorder_rate_pct
    FROM order_items oi JOIN products p USING (product_id)
    GROUP BY 1, 2, 3 HAVING COUNT(*) >= 5000
)
SELECT * FROM (
    SELECT d.department, prod.product_name, times_bought, times_reordered, reorder_rate_pct,
           RANK() OVER (PARTITION BY d.department ORDER BY reorder_rate_pct DESC) AS rank_in_dept,
           RANK() OVER (ORDER BY times_reordered DESC)                             AS rank_overall_by_repeat_volume
    FROM prod JOIN departments d USING (department_id)
) ORDER BY rank_overall_by_repeat_volume;
