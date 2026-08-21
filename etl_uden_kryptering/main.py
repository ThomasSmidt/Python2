"""ETL pipeline entry point: Extract -> Transform -> Load -> Visualise.

Run this after activating the venv and installing requirements.txt:
    python main.py
"""

import os

import mysql.connector
import pandas as pd

from config import DATA_URL, INPUT_DIR, OUTPUT_DIR, COLUMN_NAMES, MYSQL_CONFIG, MYSQL_DATABASE, MYSQL_TABLE
from extract import extract_with_requests, extract_with_wget, extract_with_curl
from transform import transform_data, get_spark_session
from load import save_to_csv, save_to_mysql
from visualisering import scatter_plot, histogram, boxplot


def run_extract() -> str:
    # SIKKERHEDSVURDERING - we use extract_with_requests().
    #
    # Security:   builds no command line and spawns nothing, so there is
    #             no injection surface and no PATH-hijackable binary,
    #             and TLS stays configurable from Python.
    # Robustness: streaming, connect+read timeouts, retry with backoff
    #             and typed exceptions - all in-process.
    #
    # Risks in the others: curl is injection-safe only by discipline
    # (one refactor to shell=True reopens it) and needs an external
    # binary; its edge - resume - is useless for a 4.5 KB file. The wget
    # module has no timeout, so a stalled connection hangs forever, and
    # it has been unmaintained since 2015.
    #
    return extract_with_requests(DATA_URL, INPUT_DIR)


def read_table_as_dataframe(table: str) -> pd.DataFrame:
    conn = mysql.connector.connect(database=MYSQL_DATABASE, **MYSQL_CONFIG)
    try:
        df = pd.read_sql(f"SELECT {', '.join(COLUMN_NAMES)} FROM `{table}`", conn)
    finally:
        conn.close()
    return df


def main():
    extracted_path = run_extract()
    original_filename = os.path.basename(extracted_path)
    print(f"Extracted: {extracted_path}")

    spark = get_spark_session()
    try:
        setosa_spark_df = transform_data(extracted_path, spark)
        setosa_df = setosa_spark_df.toPandas()
    finally:
        spark.stop()
    print(f"Transformed: {len(setosa_df)} Iris-setosa rows")

    csv_path = save_to_csv(setosa_df, original_filename, OUTPUT_DIR)
    print(f"Saved CSV: {csv_path}")

    save_to_mysql(setosa_df, MYSQL_CONFIG, MYSQL_DATABASE, MYSQL_TABLE)
    print(f"Loaded into MySQL: {MYSQL_DATABASE}.{MYSQL_TABLE}")

    viz_df = read_table_as_dataframe(MYSQL_TABLE)
    scatter_plot(viz_df)
    histogram(viz_df)
    boxplot(viz_df)


if __name__ == "__main__":
    main()
