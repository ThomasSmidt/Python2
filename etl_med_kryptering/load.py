"""Load module (encrypted variant).

Persists the transformed DataFrame as a CSV in Output_dir and as a table
in MySQL, overwriting both on every run.

values are AES-encrypted before they leave the
process, so what hits disk and database is ciphertext. See security.py
for why AES-GCM was chosen.
"""

import os

import mysql.connector

from config import COLUMN_NAMES
from security import encrypt_dataframe


def save_to_csv(df, original_filename: str, output_dir: str, key: bytes) -> str:
    """Save the DataFrame as an ENCRYPTED CSV in output_dir.

    Filename reuses the source name (never hardcoded) with a "transform_"
    prefix: iris.csv -> transform_iris.csv. Writing overwrites the
    previous run. Opening the file shows the columns but no real data.
    """
    os.makedirs(output_dir, exist_ok=True)
    new_filename = f"transform_{original_filename}"
    dest_path = os.path.join(output_dir, new_filename)

    encrypted_df = encrypt_dataframe(df, key)
    encrypted_df.to_csv(dest_path, index=False)  # header row -> readable column names
    return dest_path


def _ensure_database(mysql_config: dict, database: str) -> None:
    """Create the target database if it doesn't already exist."""
    conn = mysql.connector.connect(**mysql_config)
    try:
        cursor = conn.cursor()
        # name comes from our own config, but validate anyway
        if not database.isidentifier():
            raise ValueError(f"Unsafe database name: {database!r}")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def save_to_mysql(df, mysql_config: dict, database: str, table: str, key: bytes) -> None:
    """Save the DataFrame as an ENCRYPTED table in MySQL.

    Auto-creates the database, drops and recreates the table each run,
    and inserts through parameterized SQL (%s placeholders).
    """
    if not table.isidentifier():
        raise ValueError(f"Unsafe table name: {table!r}")

    _ensure_database(mysql_config, database)

    encrypted_df = encrypt_dataframe(df, key)

    conn = mysql.connector.connect(database=database, **mysql_config)
    try:
        cursor = conn.cursor()

        cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        cursor.execute(
            f"""
            CREATE TABLE `{table}` (
                sepal_length VARCHAR(255),
                sepal_width VARCHAR(255),
                petal_length VARCHAR(255),
                petal_width VARCHAR(255),
                species VARCHAR(255)
            )
            """
        )

        rows = [tuple(row) for row in encrypted_df[COLUMN_NAMES].itertuples(index=False)]
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
