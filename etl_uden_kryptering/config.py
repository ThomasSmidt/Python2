"""Central configuration for the ETL pipeline."""

DATA_URL = "https://raw.githubusercontent.com/jbrownlee/Datasets/master/iris.csv"

INPUT_DIR = "Input_dir"
OUTPUT_DIR = "Output_dir"

# iris.csv has no header row in the source file, so we name the columns ourselves.
COLUMN_NAMES = ["sepal_length", "sepal_width", "petal_length", "petal_width", "species"]

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "Passw0rd",
}
MYSQL_DATABASE = "iris_pipeline"
MYSQL_TABLE = "iris_setosa"
