SET search_path TO olist;

-- 1) ORDER GRAIN: one row per order (CTEs pre-aggregate items & payments to avoid join fan-out)
CREATE OR REPLACE VIEW vw_order_summary AS
WITH items AS (
    SELECT order_id,
           COUNT(*)           AS items_count,
           SUM(price)         AS items_revenue,
           SUM(freight_value) AS freight_value
    FROM order_items
    GROUP BY order_id
),
pay AS (
    SELECT order_id,
           SUM(payment_value)        AS payment_value,
           MAX(payment_installments) AS max_installments
    FROM order_payments
    GROUP BY order_id
)
SELECT o.order_id,
       o.customer_id,
       c.customer_unique_id,
       c.customer_state,
       c.customer_city,
       o.order_status,
       o.order_purchase_timestamp,
       DATE_TRUNC('month', o.order_purchase_timestamp)::date AS order_month,
       COALESCE(i.items_count, 0)                            AS items_count,
       COALESCE(i.items_revenue, 0)                          AS items_revenue,
       COALESCE(i.freight_value, 0)                          AS freight_value,
       COALESCE(i.items_revenue, 0) + COALESCE(i.freight_value, 0) AS order_value,
       COALESCE(p.payment_value, 0)                          AS payment_value,
       p.max_installments,
       o.delivery_days,
       o.delivery_delay_days,
       o.is_late,
       r.review_score
FROM orders o
JOIN customers c           ON c.customer_id = o.customer_id
LEFT JOIN items i          ON i.order_id = o.order_id
LEFT JOIN pay p            ON p.order_id = o.order_id
LEFT JOIN order_reviews r  ON r.order_id = o.order_id;

-- 2) ITEM GRAIN fact table for Power BI (category x region x time)
CREATE OR REPLACE VIEW vw_sales_fact AS
SELECT oi.order_id,
       oi.order_item_id,
       o.order_purchase_timestamp::date AS order_date,
       DATE_TRUNC('month', o.order_purchase_timestamp)::date AS order_month,
       o.order_status,
       COALESCE(p.category_english, 'Unknown') AS category,
       c.customer_unique_id,
       c.customer_state,
       c.customer_city,
       'Brazil'::text AS country,
       oi.seller_id,
       oi.price,
       oi.freight_value,
       oi.price + oi.freight_value AS gross_value,
       o.delivery_days,
       o.is_late,
       r.review_score
FROM order_items oi
JOIN orders o             ON o.order_id = oi.order_id
JOIN customers c          ON c.customer_id = o.customer_id
LEFT JOIN products p      ON p.product_id = oi.product_id
LEFT JOIN order_reviews r ON r.order_id = oi.order_id;

-- 3) MONTHLY REVENUE with MoM growth + running total (LAG, SUM OVER)
CREATE OR REPLACE VIEW vw_monthly_revenue AS
WITH monthly AS (
    SELECT order_month,
           COUNT(*)                            AS orders,
           COUNT(DISTINCT customer_unique_id)  AS customers,
           SUM(items_revenue)                  AS revenue
    FROM vw_order_summary
    WHERE order_status = 'delivered'
    GROUP BY order_month
)
SELECT order_month,
       orders,
       customers,
       revenue,
       ROUND(revenue / NULLIF(orders, 0), 2) AS avg_order_value,
       LAG(revenue) OVER (ORDER BY order_month) AS prev_month_revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month))
             / NULLIF(LAG(revenue) OVER (ORDER BY order_month), 0), 2) AS mom_growth_pct,
       SUM(revenue) OVER (ORDER BY order_month) AS cumulative_revenue
FROM monthly;

-- 4) CATEGORY PERFORMANCE: rank, share, cumulative share / Pareto (RANK, SUM OVER)
CREATE OR REPLACE VIEW vw_category_performance AS
WITH cat AS (
    SELECT COALESCE(p.category_english, 'Unknown') AS category,
           COUNT(DISTINCT oi.order_id) AS orders,
           COUNT(*)                    AS units_sold,
           SUM(oi.price)               AS revenue,
           AVG(oi.price)               AS avg_price
    FROM order_items oi
    JOIN orders o        ON o.order_id = oi.order_id AND o.order_status = 'delivered'
    LEFT JOIN products p ON p.product_id = oi.product_id
    GROUP BY 1
)
SELECT category,
       orders,
       units_sold,
       revenue,
       ROUND(avg_price, 2) AS avg_price,
       RANK() OVER (ORDER BY revenue DESC) AS revenue_rank,
       ROUND(100.0 * revenue / SUM(revenue) OVER (), 2) AS revenue_share_pct,
       ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC
                                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(revenue) OVER (), 2) AS cumulative_share_pct
FROM cat;

-- 5) REGION (STATE) PERFORMANCE
CREATE OR REPLACE VIEW vw_state_performance AS
SELECT customer_state,
       COUNT(*)                           AS orders,
       COUNT(DISTINCT customer_unique_id) AS customers,
       SUM(items_revenue)                 AS revenue,
       ROUND(AVG(items_revenue), 2)       AS avg_order_value,
       ROUND(AVG(delivery_days), 1)       AS avg_delivery_days,
       ROUND(100.0 * AVG(CASE WHEN is_late THEN 1 ELSE 0 END), 2) AS late_delivery_pct,
       ROUND(AVG(review_score), 2)        AS avg_review_score,
       ROUND(100.0 * SUM(items_revenue) / SUM(SUM(items_revenue)) OVER (), 2) AS revenue_share_pct
FROM vw_order_summary
WHERE order_status = 'delivered'
GROUP BY customer_state;

-- 6) TOP 3 CATEGORIES PER STATE (ROW_NUMBER with PARTITION BY)
CREATE OR REPLACE VIEW vw_top_categories_by_state AS
WITH ranked AS (
    SELECT customer_state,
           category,
           SUM(price) AS revenue,
           ROW_NUMBER() OVER (PARTITION BY customer_state ORDER BY SUM(price) DESC) AS rn
    FROM vw_sales_fact
    WHERE order_status = 'delivered'
    GROUP BY customer_state, category
)
SELECT customer_state, category, revenue, rn AS rank_in_state
FROM ranked
WHERE rn <= 3;

-- 7) CUSTOMER KPIs (one row per real customer)
CREATE OR REPLACE VIEW vw_customer_kpis AS
SELECT customer_unique_id,
       MIN(order_purchase_timestamp)  AS first_order_ts,
       MAX(order_purchase_timestamp)  AS last_order_ts,
       COUNT(*)                       AS total_orders,
       SUM(items_revenue)             AS total_revenue,
       ROUND(AVG(items_revenue), 2)   AS avg_order_value,
       CASE WHEN COUNT(*) > 1 THEN 1 ELSE 0 END AS is_repeat_customer
FROM vw_order_summary
WHERE order_status = 'delivered'
GROUP BY customer_unique_id;

-- 8) Days between consecutive orders per customer (ROW_NUMBER + LAG)
CREATE OR REPLACE VIEW vw_customer_order_sequence AS
SELECT customer_unique_id,
       order_id,
       order_purchase_timestamp,
       ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY order_purchase_timestamp) AS order_number,
       (order_purchase_timestamp::date
        - LAG(order_purchase_timestamp::date) OVER (PARTITION BY customer_unique_id
                                                    ORDER BY order_purchase_timestamp)) AS days_since_prev_order
FROM vw_order_summary
WHERE order_status = 'delivered';

-- 9) RFM base (scoring is done in Python)
CREATE OR REPLACE VIEW vw_rfm_base AS
WITH ref AS (
    SELECT MAX(order_purchase_timestamp)::date + 1 AS ref_date FROM orders
)
SELECT k.customer_unique_id,
       (ref.ref_date - k.last_order_ts::date) AS recency_days,
       k.total_orders   AS frequency,
       k.total_revenue  AS monetary
FROM vw_customer_kpis k
CROSS JOIN ref;

-- 10) COHORT RETENTION (first-purchase month vs months since)
CREATE OR REPLACE VIEW vw_cohort_retention AS
WITH cust_months AS (
    SELECT customer_unique_id,
           DATE_TRUNC('month', order_purchase_timestamp)::date AS order_month
    FROM vw_order_summary
    WHERE order_status = 'delivered'
    GROUP BY 1, 2
),
first_month AS (
    SELECT customer_unique_id, MIN(order_month) AS cohort_month
    FROM cust_months
    GROUP BY 1
),
activity AS (
    SELECT f.cohort_month,
           (EXTRACT(YEAR FROM AGE(c.order_month, f.cohort_month)) * 12
            + EXTRACT(MONTH FROM AGE(c.order_month, f.cohort_month)))::int AS month_index,
           COUNT(DISTINCT c.customer_unique_id) AS active_customers
    FROM cust_months c
    JOIN first_month f ON f.customer_unique_id = c.customer_unique_id
    GROUP BY 1, 2
)
SELECT cohort_month,
       month_index,
       active_customers,
       FIRST_VALUE(active_customers) OVER (PARTITION BY cohort_month ORDER BY month_index) AS cohort_size,
       ROUND(100.0 * active_customers
             / FIRST_VALUE(active_customers) OVER (PARTITION BY cohort_month ORDER BY month_index), 2) AS retention_pct
FROM activity;
