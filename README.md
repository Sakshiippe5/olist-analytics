# Sales & Customer Analytics Pipeline (Olist E-Commerce)

An end-to-end analytics project on the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce): a Python ETL loads ~100K orders into PostgreSQL, SQL views power the KPIs, Python handles RFM segmentation and cohort retention, and a Power BI dashboard presents the results.

**Tech stack:** Python (Pandas, SQLAlchemy) · PostgreSQL · SQL (CTEs, joins, window functions) · Power BI

---

## Key Results

| Metric | Value |
|---|---|
| Delivered orders | 96,478 |
| Revenue (BRL) | 13.22M |
| Unique customers | ~93K |
| Average order value | 137.04 |
| Average review score | 4.08 / 5 |
| Late deliveries | ~8% |
| Average delivery time | 12.5 days |
| Top states by revenue | SP, RJ, MG |
| Top categories by revenue | Health Beauty, Watches Gifts, Bed Bath Table |
| Top RFM segment | ___ (___% of revenue from ___% of customers) |
| At-risk customers | ___ (___% of revenue) |
| Month-1 retention | ___% |

*Revenue = item price on delivered orders, excluding freight.*

---

## Dashboard

**Overview**
![Overview](docs/page1_overview.png)

**Product Category**
![Category](docs/page2_category.png)

**Regional Performance**
![Region](docs/page3_region.png)

---

## Customer Analysis (Python)

**RFM segments:** customer share vs revenue share
![RFM](outputs/rfm_segments.png)

**Cohort retention:** monthly retention by acquisition cohort
![Cohort](outputs/cohort_retention_heatmap.png)

---

## Architecture

```
Kaggle CSVs
   │
   ▼
src/etl.py  ── clean, normalize, validate (Pandas)
   │
   ▼
PostgreSQL (schema: olist, 7 tables)
   │
   ▼
sql/02_views.sql  ── 10 analytical views
   │
   ├──► src/rfm.py      ── RFM scoring and segments
   ├──► src/cohort.py   ── cohort retention matrix
   │
   ▼
Power BI dashboard
```

## Repository Structure

```
olist-analytics/
├── data/raw/              # Kaggle CSVs (not tracked)
├── docs/                  # dashboard screenshots
├── outputs/               # charts and CSV results
├── powerbi/               # dashboard (.pbix) and build guide
├── sql/
│   ├── 01_schema.sql      # tables, keys, indexes
│   └── 02_views.sql       # analytical views
├── src/
│   ├── config.py
│   ├── etl.py
│   ├── rfm.py
│   ├── cohort.py
│   └── export_for_powerbi.py
├── .env.example
├── requirements.txt
└── README.md
```

## ETL Highlights

- Fixes misspelled source columns and translates product categories to English
- Parses timestamps and derives `delivery_days`, `delivery_delay_days` and `is_late`
- Drops duplicates and rows that break referential integrity, and logs every removal
- Keeps the latest review per order, since `review_id` is not unique in the source
- Rebuilds the schema on each run, so the pipeline can be re-run safely

## SQL Views

| View | Purpose | Techniques |
|---|---|---|
| `vw_order_summary` | One row per order with KPIs | CTEs, joins |
| `vw_sales_fact` | Item-level fact table for Power BI | Joins |
| `vw_monthly_revenue` | Revenue, AOV, month-over-month growth | `LAG`, running `SUM OVER` |
| `vw_category_performance` | Rank, revenue share, Pareto | `RANK`, windowed `SUM` |
| `vw_state_performance` | Regional revenue and delivery KPIs | Window share |
| `vw_top_categories_by_state` | Top 3 categories per state | `ROW_NUMBER` |
| `vw_customer_kpis` | Per-customer orders and revenue | Aggregation |
| `vw_customer_order_sequence` | Days between repeat orders | `ROW_NUMBER`, `LAG` |
| `vw_rfm_base` | Recency, frequency, monetary inputs | CTE |
| `vw_cohort_retention` | Retention by acquisition month | `FIRST_VALUE`, `AGE` |

---

## Getting Started

**Prerequisites:** Python 3.10+, PostgreSQL 16, Power BI Desktop (optional)

```bash
# 1. Install dependencies
python -m venv venv
venv\Scripts\activate            # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt

# 2. Configure the database connection
copy .env.example .env           # Mac/Linux: cp .env.example .env
# edit .env and set PG_PASSWORD

# 3. Create the database
psql -U postgres -c "CREATE DATABASE olist;"
```

Download the dataset from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and place the CSVs in `data/raw/` (the geolocation file is not used).

```bash
python src/etl.py       # create schema, load tables, create views
python src/rfm.py       # RFM segmentation -> outputs/ and DB tables
python src/cohort.py    # cohort heatmap -> outputs/
```

To build the dashboard, follow [`powerbi/powerbi_guide.md`](powerbi/powerbi_guide.md) and open `powerbi/olist_dashboard.pbix`.

## Notes

- About 97% of customers placed a single order, so retention is low by nature, and RFM frequency uses fixed bins instead of quantiles.
- The dataset covers 2016 to 2018. Early 2016 and late 2018 have very few orders.