"""
Optional fallback: export views/tables to CSV (use if Power BI can't connect to PostgreSQL directly).
Run:  python src/export_for_powerbi.py
"""
import pandas as pd

from config import OUTPUT_DIR, get_engine

OBJECTS = ["vw_sales_fact", "vw_monthly_revenue", "vw_category_performance", "vw_state_performance",
           "vw_top_categories_by_state", "rfm_segments", "rfm_segment_summary", "cohort_retention"]


def main():
    engine = get_engine()
    out = OUTPUT_DIR / "powerbi_export"
    out.mkdir(exist_ok=True)
    for name in OBJECTS:
        df = pd.read_sql(f"SELECT * FROM olist.{name}", engine)
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"{name:30s} {len(df):>8,} rows")


if __name__ == "__main__":
    main()
