"""Shared config: paths, DB engine, SQL-file runner."""
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")


def get_engine():
    user = os.getenv("PG_USER", "postgres")
    pwd = quote_plus(os.getenv("PG_PASSWORD", ""))
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    db = os.getenv("PG_DB", "olist")
    return create_engine(f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}")


def run_sql_file(engine, path):
    """Execute a whole .sql file (multiple statements) in one transaction."""
    sql = Path(path).read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
