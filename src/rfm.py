"""
RFM segmentation. Reads olist.vw_rfm_base, scores R/F/M 1-5, assigns segments,
saves CSV + chart, and writes olist.rfm_segments / olist.rfm_segment_summary for Power BI.
Run:  python src/rfm.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import OUTPUT_DIR, get_engine


def score_rfm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["monetary"] = df["monetary"].astype(float)
    # rank(method="first") breaks ties so qcut always produces 5 equal-sized buckets
    # Recency: fewer days = better = higher score
    df["r_score"] = pd.qcut(df["recency_days"].rank(method="first", ascending=False),
                            5, labels=[1, 2, 3, 4, 5]).astype(int)
    # Frequency: ~97% of Olist customers ordered once, so quantiles don't work -> fixed bins
    df["f_score"] = pd.cut(df["frequency"], bins=[0, 1, 2, 3, 4, np.inf],
                           labels=[1, 2, 3, 4, 5]).astype(int)
    df["m_score"] = pd.qcut(df["monetary"].rank(method="first"),
                            5, labels=[1, 2, 3, 4, 5]).astype(int)
    df["rfm_score"] = df["r_score"].astype(str) + df["f_score"].astype(str) + df["m_score"].astype(str)
    return df


def assign_segment(df: pd.DataFrame) -> pd.DataFrame:
    r, f, m = df["r_score"], df["f_score"], df["m_score"]
    conditions = [
        (r >= 4) & (f >= 2) & (m >= 4),   # recent, repeat, big spenders
        (f >= 2) & (r >= 3),              # repeat buyers, fairly recent
        (r >= 4) & (m >= 4),              # recent first-timers with big baskets
        (r >= 4),                         # recent first-timers
        (r <= 2) & ((f >= 2) | (m >= 4)), # valuable but gone quiet
        (r <= 2),                         # low value and inactive
    ]
    labels = ["Champions", "Loyal Customers", "High-Value New", "New Customers",
              "At Risk", "Hibernating"]
    df["segment"] = np.select(conditions, labels, default="Need Attention")
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    s = (df.groupby("segment")
           .agg(customers=("customer_unique_id", "count"),
                revenue=("monetary", "sum"),
                avg_recency_days=("recency_days", "mean"),
                avg_frequency=("frequency", "mean"),
                avg_monetary=("monetary", "mean"))
           .reset_index())
    s["pct_customers"] = (100 * s["customers"] / s["customers"].sum()).round(2)
    s["pct_revenue"] = (100 * s["revenue"] / s["revenue"].sum()).round(2)
    return s.sort_values("revenue", ascending=False).round(2)


def plot(summary: pd.DataFrame, path):
    s = summary.sort_values("pct_revenue")
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(y - 0.2, s["pct_customers"], height=0.4, label="% of customers")
    ax.barh(y + 0.2, s["pct_revenue"], height=0.4, label="% of revenue")
    ax.set_yticks(y)
    ax.set_yticklabels(s["segment"])
    ax.set_xlabel("%")
    ax.set_title("RFM segments: customer share vs revenue share")
    ax.legend()
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    engine = get_engine()
    df = pd.read_sql("SELECT * FROM olist.vw_rfm_base", engine)
    print(f"Customers scored: {len(df):,}")

    df = assign_segment(score_rfm(df))
    summary = summarize(df)

    print("\n=== RFM SEGMENT SUMMARY ===")
    print(summary.to_string(index=False))
    top = summary.iloc[0]
    print(f"\nTOP SEGMENT BY REVENUE: {top['segment']} -> {top['pct_revenue']}% of revenue "
          f"from {top['pct_customers']}% of customers")
    at_risk = summary[summary["segment"] == "At Risk"]
    if not at_risk.empty:
        print(f"AT RISK: {int(at_risk['customers'].iloc[0]):,} customers, "
              f"{at_risk['pct_revenue'].iloc[0]}% of revenue")

    df.to_csv(OUTPUT_DIR / "rfm_segments.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "rfm_segment_summary.csv", index=False)
    plot(summary, OUTPUT_DIR / "rfm_segments.png")

    df.to_sql("rfm_segments", engine, schema="olist", if_exists="replace", index=False, chunksize=5000)
    summary.to_sql("rfm_segment_summary", engine, schema="olist", if_exists="replace", index=False)
    print("\nSaved CSVs + chart to outputs/ and tables olist.rfm_segments, olist.rfm_segment_summary")


if __name__ == "__main__":
    main()
