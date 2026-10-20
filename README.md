# Sales & Customer Analytics Pipeline (Olist E-Commerce)

End-to-end analytics project: Python ETL -> PostgreSQL -> SQL views -> RFM + cohort analysis -> Power BI dashboard.

**Stack:** Python, Pandas, SQLAlchemy, PostgreSQL, SQL (CTEs, joins, window functions), Power BI

## Architecture
```
Kaggle CSVs -> src/etl.py (clean, normalize, validate) -> PostgreSQL (schema olist, 7 tables)
            -> sql/02_views.sql (10 analytical views)
            -> src/rfm.py + src/cohort.py (segmentation, retention)
            -> Power BI dashboard (category, region, customers)
```

## Setup
```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env   then edit the password
```
1. Create DB: in pgAdmin or `psql -U postgres -c "CREATE DATABASE olist;"`
2. Download dataset from https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce and put the CSVs in `data/raw/`
   (the geolocation CSV is not used).

## Run
```bash
python src/etl.py       # creates schema, loads tables, creates views
python src/rfm.py       # RFM segments -> outputs/ + DB tables
python src/cohort.py    # cohort heatmap -> outputs/
python src/export_for_powerbi.py   # optional CSV fallback
```

## Key Views
| View | Purpose | SQL features |
|---|---|---|
| vw_order_summary | order-level KPIs | CTEs, joins |
| vw_sales_fact | item-level fact for Power BI | joins |
| vw_monthly_revenue | revenue, AOV, MoM growth | LAG, running SUM OVER |
| vw_category_performance | rank, share, Pareto | RANK, SUM OVER frame |
| vw_state_performance | regional KPIs | window share |
| vw_top_categories_by_state | top 3 per state | ROW_NUMBER PARTITION BY |
| vw_customer_kpis / vw_customer_order_sequence | customer metrics, repeat gaps | ROW_NUMBER, LAG |
| vw_rfm_base | RFM input | CTE |
| vw_cohort_retention | cohort matrix | FIRST_VALUE, AGE |

## Results
_Fill in from your own run output (rfm.py prints these):_
- Orders loaded: ___
- Top RFM segment: ___ drives ___% of revenue from ___% of customers
- At-risk customers: ___ (___% of revenue)
- Month-1 retention: ___%

## Dashboard
See `powerbi/powerbi_guide.md`. Add screenshots here.
