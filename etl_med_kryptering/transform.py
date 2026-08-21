"""Transform module.

Uses PySpark to read the extracted CSV and filter it down to only the
Iris-setosa observations, per the customer's requirement.
"""

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, DoubleType, StringType

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
    """Return a Spark DataFrame of only the Iris-setosa rows.

    The caller converts it to whatever Load needs (e.g. .toPandas()).
    """
    if spark is None:
        spark = get_spark_session()

    # Extract wrote the header row, so skip it. We still pin our own
    # schema rather than inferSchema, so types cannot drift.
    raw_df = (
        spark.read
        .schema(_SCHEMA)
        .csv(input_csv_path, header=True)
    )

    return raw_df.filter(raw_df.species == "Iris-setosa")
