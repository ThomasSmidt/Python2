"""Load module.

Takes the transformed data (as a pandas DataFrame) and persists it in
two places: a CSV file in Output_dir, and a table in a MySQL database.
Both overwrite whatever was there from a previous run.
"""

import os

import mysql.connector

from config import COLUMN_NAMES


def save_to_csv(df, original_filename: str, output_dir: str) -> str:
    """Save the transformed DataFrame as CSV in output_dir.

    The filename reuses the original source filename (never hardcoded)
    with a "transform_" prefix, e.g. iris.csv -> transform_iris.csv.
    Writing with mode="w" naturally overwrites any file left over from
    a previous run.
    """
    os.makedirs(output_dir, exist_ok=True)
    new_filename = f"transform_{original_filename}"
    dest_path = os.path.join(output_dir, new_filename)

    df.to_csv(dest_path, index=False)  # header row -> proper column names when opened manually
    return dest_path


def _ensure_database(mysql_config: dict, database: str) -> None:
    """Create the target database if it doesn't already exist."""
    conn = mysql.connector.connect(**mysql_config)
    try:
        cursor = conn.cursor()
        # database name comes from our own config, not user input, but we
        # still validate it to keep this safe against copy/paste mistakes.
        if not database.isidentifier():
            raise ValueError(f"Unsafe database name: {database!r}")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def save_to_mysql(df, mysql_config: dict, database: str, table: str) -> None:
    """Save the transformed DataFrame as a table in MySQL.

    - Auto-creates the database if it doesn't exist.
    - Drops and recreates the table each run, so old data never lingers.
    - Uses a parameterized INSERT (executemany with %s placeholders) so
      row values are never interpolated directly into SQL text.
    """
    if not table.isidentifier():
        raise ValueError(f"Unsafe table name: {table!r}")

    _ensure_database(mysql_config, database)

    conn = mysql.connector.connect(database=database, **mysql_config)
    try:
        cursor = conn.cursor()

        cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        cursor.execute(
            f"""
            CREATE TABLE `{table}` (
                sepal_length DOUBLE,
                sepal_width DOUBLE,
                petal_length DOUBLE,
                petal_width DOUBLE,
                species VARCHAR(50)
            )
            """
        )

        rows = [tuple(row) for row in df[COLUMN_NAMES].itertuples(index=False)]
        insert_sql = (
            f"INSERT INTO `{table}` "
            "(sepal_length, sepal_width, petal_length, petal_width, species) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        cursor.executemany(insert_sql, rows)

        conn.commit()
        cursor.close()
    finally:
        conn.close()
