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
    # Sikkerhedsvurdering / method choice:
    #
    # We use extract_with_requests() as the single method actually run
    # here. Reasoning:
    #   - requests never touches a shell (no subprocess involved at all),
    #     so it has zero command-line injection surface. extract_with_curl
    #     is the only one of the three that shells out to an external
    #     program; even though we call it safely (argument list,
    #     shell=False), it still depends on curl being present and
    #     correctly configured on the host, which is an extra risk
    #     requests doesn't have.
    #   - requests gives us the most direct control over TLS behaviour
    #     (certificate verification is on by default and easy to
    #     inspect/override in Python) and over timeouts/retries, without
    #     relying on how the `wget` module or the external curl binary
    #     happen to be built on a given system.
    #   - Risk with extract_with_wget: the `wget` package is a small,
    #     lightly-maintained third-party module; error handling around
    #     interrupted downloads is less robust than requests' exception
    #     model.
    #   - Risk with extract_with_curl: relies on an external binary being
    #     installed and on PATH (not guaranteed cross-platform), and any
    #     future change to how the command is built could reintroduce a
    #     command-injection risk if argument-list/shell=False discipline
    #     is dropped.
    # For the demo/grading, uncomment either of these to show that the
    # other two extract methods also work correctly end-to-end. Only one
    # method is used for the actual pipeline run (see reasoning above).
    # return extract_with_wget(DATA_URL, INPUT_DIR)
    # return extract_with_curl(DATA_URL, INPUT_DIR)
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
