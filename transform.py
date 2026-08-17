"""Transform module.

Uses PySpark to read the extracted CSV and filter it down to only the
Iris-setosa observations, per the customer's requirement.
"""

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, DoubleType, StringType

from config import COLUMN_NAMES

_SCHEMA = StructType([
    StructField("sepal_length", DoubleType(), True),
    StructField("sepal_width", DoubleType(), True),
    StructField("petal_length", DoubleType(), True),
    StructField("petal_width", DoubleType(), True),
    StructField("species", StringType(), True),
])


def get_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("IrisETL")
        .master("local[*]")
        .getOrCreate()
    )


def transform_data(input_csv_path: str, spark: SparkSession = None):
    """Read the raw CSV and return a Spark DataFrame containing only
    rows where species == 'Iris-setosa'.

    The caller is responsible for turning the result into whatever
    shape the Load module needs (e.g. via .toPandas()).
    """
    owns_session = spark is None
    if spark is None:
        spark = get_spark_session()

    # The source file has no header row, so we apply our own schema
    # instead of relying on inferSchema/header (which would silently
    # mis-name columns if the source format ever changes).
    raw_df = (
        spark.read
        .schema(_SCHEMA)
        .csv(input_csv_path, header=False)
    )

    setosa_df = raw_df.filter(raw_df.species == "Iris-setosa")

    if owns_session:
        # Caller didn't hand us a session, so keep it alive on the
        # DataFrame's SparkSession reference; nothing further to do here.
        pass

    return setosa_df
