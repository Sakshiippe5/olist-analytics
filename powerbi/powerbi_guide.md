# Power BI Dashboard Guide

## 1. Connect
Home > Get Data > PostgreSQL database
- Server: `localhost:5432`   Database: `olist`   Mode: **Import**
- Credentials > Database > user `postgres` + your password
- If the connector errors, install Npgsql (https://github.com/npgsql/npgsql/releases, choose "GAC installation"),
  OR run `python src/export_for_powerbi.py` and use Get Data > Text/CSV on `outputs/powerbi_export/*.csv`.

Select (schema `olist`): vw_sales_fact, vw_monthly_revenue, vw_category_performance,
vw_state_performance, vw_top_categories_by_state, rfm_segments, rfm_segment_summary, cohort_retention.

## 2. Model
- Create a Date table (Modeling > New table):
  `DimDate = CALENDAR(DATE(2016,9,1), DATE(2018,10,31))`
- Relationship: `DimDate[Date]` 1 -> * `vw_sales_fact[order_date]`. Mark DimDate as date table.
- Filter delivered-only on the page: add `order_status = delivered` as a page-level filter.
- Select `customer_state` column > Column tools > Data category = State or Province; `country` = Country.

## 3. DAX measures (put in vw_sales_fact)
```DAX
Total Revenue   = SUM(vw_sales_fact[price])
Freight         = SUM(vw_sales_fact[freight_value])
Orders          = DISTINCTCOUNT(vw_sales_fact[order_id])
Customers       = DISTINCTCOUNT(vw_sales_fact[customer_unique_id])
AOV             = DIVIDE([Total Revenue], [Orders])
Avg Review      = AVERAGE(vw_sales_fact[review_score])
Late Delivery % = DIVIDE(CALCULATE(DISTINCTCOUNT(vw_sales_fact[order_id]), vw_sales_fact[is_late] = TRUE()), [Orders])
Revenue LM      = CALCULATE([Total Revenue], DATEADD(DimDate[Date], -1, MONTH))
MoM Growth %    = DIVIDE([Total Revenue] - [Revenue LM], [Revenue LM])
Revenue Share % = DIVIDE([Total Revenue], CALCULATE([Total Revenue], ALL(vw_sales_fact[category])))
```

## 4. Pages
**Page 1 - Executive Overview**: KPI cards (Revenue, Orders, Customers, AOV, Avg Review, Late %);
line chart revenue by month (DimDate); slicers for year, category, state.
**Page 2 - Product Category**: bar chart top 10 categories by revenue; treemap of revenue share;
Pareto from vw_category_performance (cumulative_share_pct); table with units, avg price.
**Page 3 - Region**: filled map by customer_state (size/colour = revenue); bar of avg_delivery_days and
late_delivery_pct by state; matrix state x top categories (vw_top_categories_by_state).
**Page 4 - Customers**: donut/bar of customers vs revenue by RFM segment (rfm_segment_summary);
cohort heatmap = matrix visual (rows cohort_month, columns month_index, values retention_pct, conditional-format background colour).

## 5. Save
File > Save as `powerbi/olist_dashboard.pbix`. Take screenshots into `outputs/` or `docs/` and embed in README.
