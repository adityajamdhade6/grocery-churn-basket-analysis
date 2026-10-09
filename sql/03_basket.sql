-- ============================================================================
-- LAYER 2 SUPPORT: aggregates that feed the Excel workbook and the dashboard
-- ============================================================================

-- QUESTION: How big is a typical basket, and does it change as a customer matures?
-- WHY IT MATTERS: Basket size drives revenue per delivery, and delivery cost is mostly fixed. A basket that grows
-- with tenure means the relationship deepens, while a shrinking one is an early sign of drift to another store.
CREATE OR REPLACE TABLE order_facts AS
SELECT o.order_id, o.user_id, o.order_number, o.order_dow, o.order_hour_of_day,
       o.days_since_prior_order, COUNT(*) AS basket_size, SUM(oi.reordered) AS reordered_items
FROM orders o JOIN order_items oi USING (order_id)
GROUP BY ALL;

-- @export basket_by_order_number
SELECT LEAST(order_number, 30) AS order_number, COUNT(*) AS orders, ROUND(AVG(basket_size), 2) AS avg_basket_size,
       ROUND(100.0 * SUM(reordered_items) / SUM(basket_size), 1) AS reorder_rate_pct
FROM order_facts GROUP BY 1 ORDER BY 1;

-- @export volume_by_week_since_first_order
-- QUESTION: How does order volume evolve over a customer's life with us?
-- WHY IT MATTERS: The dataset has no calendar, so "over time" is measured from each customer's own first order.
-- A cumulative SUM() of the gaps turns "days since previous order" into "days since first order".
WITH t AS (
    SELECT user_id, SUM(COALESCE(days_since_prior_order, 0)) OVER (PARTITION BY user_id ORDER BY order_number) AS days_since_first
    FROM orders
)
SELECT CAST(days_since_first / 7 AS INT) AS week_since_first_order, COUNT(*) AS orders, COUNT(DISTINCT user_id) AS active_customers
FROM t WHERE days_since_first < 7 * 52 GROUP BY 1 ORDER BY 1;

-- QUESTION: Which departments do customers keep buying again?
-- WHY IT MATTERS: A high repeat rate means the department is a habit (stock it reliably, protect quality).
-- A low repeat rate means customers explore there (good for discovery and promotions, weak for retention).
-- @export dept_repeat
SELECT d.department, COUNT(*) AS items_ordered, SUM(oi.reordered) AS items_reordered,
       ROUND(100.0 * AVG(oi.reordered), 1) AS reorder_rate_pct
FROM order_items oi JOIN products p USING (product_id) JOIN departments d USING (department_id)
GROUP BY 1 ORDER BY reorder_rate_pct DESC;

-- QUESTION: Which pairs of products land in the same basket most often?
-- WHY IT MATTERS: Pairs tell us what to place next to each other in the app, what to bundle, and what to suggest at checkout.
-- To keep the self-join fast we use a fixed random 400,000-order sample and the 300 most-bought products.
-- Lift above 1 means the pair appears together more than chance would predict (a real affinity, not just two popular items).
CREATE OR REPLACE TABLE sample_orders AS SELECT order_id FROM order_facts USING SAMPLE reservoir(400000 ROWS) REPEATABLE (42);
CREATE OR REPLACE TABLE top_products AS
    SELECT product_id FROM order_items GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 300;
CREATE OR REPLACE TABLE sample_items AS
    SELECT oi.order_id, oi.product_id FROM order_items oi
    JOIN sample_orders USING (order_id) JOIN top_products USING (product_id);
-- @export product_pairs
CREATE OR REPLACE TABLE product_pairs AS
WITH pc AS (SELECT product_id, COUNT(*) AS n FROM sample_items GROUP BY 1),
     total AS (SELECT COUNT(*)::DOUBLE AS n FROM sample_orders),
     pairs AS (
        SELECT a.product_id AS p1, b.product_id AS p2, COUNT(*) AS together
        FROM sample_items a JOIN sample_items b ON a.order_id = b.order_id AND a.product_id < b.product_id
        GROUP BY 1, 2 HAVING COUNT(*) >= 200)
SELECT p1n.product_name AS product_a, p2n.product_name AS product_b, together AS orders_together,
       ROUND(100.0 * together / total.n, 2) AS pct_of_orders,
       ROUND((together / total.n) / ((pa.n / total.n) * (pb.n / total.n)), 2) AS lift
FROM pairs JOIN pc pa ON pa.product_id = p1 JOIN pc pb ON pb.product_id = p2 CROSS JOIN total
JOIN products p1n ON p1n.product_id = p1 JOIN products p2n ON p2n.product_id = p2
ORDER BY together DESC;
