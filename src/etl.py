"""
ETL pipeline: Extract Olist CSVs -> Clean/Normalize (Pandas) -> Load into PostgreSQL -> Create SQL views.
Run:  python src/etl.py
"""
import logging

import pandas as pd

from config import RAW_DIR, SQL_DIR, get_engine, run_sql_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("etl")

SCHEMA = "olist"
FILES = {
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "translation": "product_category_name_translation.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
}
# parents before children (foreign keys)
LOAD_ORDER = ["customers", "sellers", "products", "orders",
              "order_items", "order_payments", "order_reviews"]


# ----------------------------------------------------------------- EXTRACT
def extract() -> dict:
    data = {}
    for key, fname in FILES.items():
        path = RAW_DIR / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Download the Olist dataset into data/raw/")
        data[key] = pd.read_csv(
            path, encoding="utf-8-sig",
            dtype={"customer_zip_code_prefix": str, "seller_zip_code_prefix": str},
        )
        log.info("Extracted %-15s %8d rows", key, len(data[key]))
    return data


# --------------------------------------------------------------- TRANSFORM
def _drop(df: pd.DataFrame, mask, label: str) -> pd.DataFrame:
    """Keep rows where mask is True, and log how many were removed."""
    removed = int((~mask).sum())
    if removed:
        log.warning("%s: removed %d rows", label, removed)
    return df[mask].copy()


def clean_customers(df):
    df = df.drop_duplicates("customer_id").copy()
    df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].astype(str).str.zfill(5)
    df["customer_city"] = df["customer_city"].str.strip().str.lower()
    df["customer_state"] = df["customer_state"].str.strip().str.upper()
    return df


def clean_sellers(df):
    df = df.drop_duplicates("seller_id").copy()
    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str).str.zfill(5)
    df["seller_city"] = df["seller_city"].str.strip().str.lower()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()
    return df


def clean_products(df, translation):
    df = df.drop_duplicates("product_id").copy()
    # the source file has typos in two column names
    df = df.rename(columns={"product_name_lenght": "product_name_length",
                            "product_description_lenght": "product_description_length"})
    translation = translation.rename(columns={"product_category_name_english": "category_english"})
    df = df.merge(translation, on="product_category_name", how="left")
    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    # fall back to the Portuguese name if no translation exists, then make it dashboard-friendly
    df["category_english"] = df["category_english"].fillna(df["product_category_name"])
    df["category_english"] = df["category_english"].str.replace("_", " ").str.title()

    for col in ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]:
        df[col] = df[col].fillna(df[col].median())
    for col in ["product_name_length", "product_description_length", "product_photos_qty"]:
        df[col] = df[col].fillna(df[col].median()).round().astype(int)

    return df[["product_id", "product_category_name", "category_english",
               "product_name_length", "product_description_length", "product_photos_qty",
               "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]]


def clean_orders(df, valid_customers):
    df = df.drop_duplicates("order_id").copy()
    ts_cols = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
               "order_delivered_customer_date", "order_estimated_delivery_date"]
    for c in ts_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["order_status"] = df["order_status"].str.strip().str.lower()
    df = _drop(df, df["order_purchase_timestamp"].notna(), "orders w/o purchase timestamp")
    df = _drop(df, df["customer_id"].isin(valid_customers), "orders w/ unknown customer")

    # derived delivery metrics
    secs_per_day = 86400
    df["delivery_days"] = ((df["order_delivered_customer_date"] - df["order_purchase_timestamp"])
                           .dt.total_seconds() / secs_per_day).round(2)
    df["delivery_delay_days"] = ((df["order_delivered_customer_date"] - df["order_estimated_delivery_date"])
                                 .dt.total_seconds() / secs_per_day).round(2)
    df["is_late"] = (df["order_delivered_customer_date"] > df["order_estimated_delivery_date"]) \
        .where(df["order_delivered_customer_date"].notna()).astype("boolean")
    return df


def clean_items(df, valid_orders, valid_products, valid_sellers):
    df = df.drop_duplicates(["order_id", "order_item_id"]).copy()
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")
    df = _drop(df, (df["price"] >= 0) & (df["freight_value"] >= 0), "items w/ negative price/freight")
    df = _drop(df, df["order_id"].isin(valid_orders), "items w/ unknown order")
    df = _drop(df, df["product_id"].isin(valid_products), "items w/ unknown product")
    df = _drop(df, df["seller_id"].isin(valid_sellers), "items w/ unknown seller")
    return df


def clean_payments(df, valid_orders):
    df = df.drop_duplicates(["order_id", "payment_sequential"]).copy()
    df["payment_type"] = df["payment_type"].str.strip().str.lower()
    df = _drop(df, df["payment_type"] != "not_defined", "payments w/ type not_defined")
    df = _drop(df, df["payment_value"] >= 0, "payments w/ negative value")
    df = _drop(df, df["order_id"].isin(valid_orders), "payments w/ unknown order")
    return df


def clean_reviews(df, valid_orders):
    df = df.copy()
    for c in ["review_creation_date", "review_answer_timestamp"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    # review_id is NOT unique in the source; keep the latest review per order
    df = df.sort_values("review_answer_timestamp").drop_duplicates("order_id", keep="last")
    df = _drop(df, df["review_score"].between(1, 5), "reviews w/ invalid score")
    df = _drop(df, df["order_id"].isin(valid_orders), "reviews w/ unknown order")
    return df


def transform(raw: dict) -> dict:
    t = {}
    t["customers"] = clean_customers(raw["customers"])
    t["sellers"] = clean_sellers(raw["sellers"])
    t["products"] = clean_products(raw["products"], raw["translation"])
    t["orders"] = clean_orders(raw["orders"], set(t["customers"]["customer_id"]))
    oids = set(t["orders"]["order_id"])
    t["order_items"] = clean_items(raw["order_items"], oids,
                                   set(t["products"]["product_id"]), set(t["sellers"]["seller_id"]))
    t["order_payments"] = clean_payments(raw["order_payments"], oids)
    t["order_reviews"] = clean_reviews(raw["order_reviews"], oids)
    for k in LOAD_ORDER:
        log.info("Transformed %-15s %8d rows", k, len(t[k]))
    return t


# -------------------------------------------------------------------- LOAD
def load(tables: dict, engine):
    for name in LOAD_ORDER:
        tables[name].to_sql(name, engine, schema=SCHEMA, if_exists="append",
                            index=False, method="multi", chunksize=1000)
        log.info("Loaded %-15s -> %s.%s", name, SCHEMA, name)


def verify(engine):
    with engine.connect() as conn:
        for name in LOAD_ORDER:
            n = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {SCHEMA}.{name}").scalar()
            log.info("DB check %-15s %8d rows", name, n)


def main():
    engine = get_engine()
    raw = extract()
    tables = transform(raw)
    run_sql_file(engine, SQL_DIR / "01_schema.sql")
    log.info("Schema created")
    load(tables, engine)
    run_sql_file(engine, SQL_DIR / "02_views.sql")
    log.info("Views created")
    verify(engine)
    log.info("ETL complete")


if __name__ == "__main__":
    main()
