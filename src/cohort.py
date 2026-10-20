"""
Cohort retention analysis. Reads olist.vw_cohort_retention, builds the retention matrix + heatmap.
Run:  python src/cohort.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config import OUTPUT_DIR, get_engine

MAX_MONTHS = 12


def main():
    engine = get_engine()
    df = pd.read_sql("SELECT * FROM olist.vw_cohort_retention", engine)
    df["cohort_month"] = pd.to_datetime(df["cohort_month"])
    df["retention_pct"] = df["retention_pct"].astype(float)

    # first/last months of the dataset have very few customers -> noisy; keep the stable window
    df = df[(df["cohort_month"] >= "2017-01-01") & (df["cohort_month"] <= "2018-08-01")]
    df = df[df["month_index"] <= MAX_MONTHS]

    matrix = df.pivot(index="cohort_month", columns="month_index", values="retention_pct")
    sizes = df[df["month_index"] == 0].set_index("cohort_month")["cohort_size"]
    matrix.index = [f"{d:%Y-%m} (n={int(sizes[d]):,})" for d in matrix.index]

    matrix.to_csv(OUTPUT_DIR / "cohort_retention_matrix.csv")

    # month 0 is always 100% -> hide it so the colour scale shows the real signal
    plot_df = matrix.drop(columns=[0])
    plt.figure(figsize=(13, 8))
    sns.heatmap(plot_df, annot=True, fmt=".1f", cmap="YlGnBu", cbar_kws={"label": "Retention %"})
    plt.title("Monthly customer retention by acquisition cohort (%)")
    plt.xlabel("Months since first purchase")
    plt.ylabel("Cohort")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "cohort_retention_heatmap.png", dpi=150)
    plt.close()

    print("Average retention % by months since first purchase:")
    print(plot_df.mean().round(2).to_string())
    print("\nSaved matrix CSV + heatmap to outputs/")

    df.to_sql("cohort_retention", engine, schema="olist", if_exists="replace", index=False)


if __name__ == "__main__":
    main()
