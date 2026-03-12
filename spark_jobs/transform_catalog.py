"""
transform_catalog.py
PySpark job: reads catalog image metadata, normalizes filenames,
filters corrupt entries, outputs a clean parquet manifest.

Usage:
  spark-submit transform_catalog.py --input /path/to/catalog --output /path/to/processed
"""

import argparse
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, regexp_extract, lit
from pyspark.sql.types import StructType, StructField, StringType, LongType


def main(input_dir: str, output_dir: str):
    spark = SparkSession.builder \
        .appName("FashionCatalogTransform") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    # ── Step 1: Ingest — build image manifest from filesystem ─────────────────
    SUPPORTED_EXTS = [".jpg", ".jpeg", ".png"]

    records = []
    for fname in os.listdir(input_dir):
        fpath = os.path.join(input_dir, fname)
        if any(fname.lower().endswith(ext) for ext in SUPPORTED_EXTS):
            size = os.path.getsize(fpath)
            records.append((fname, fpath, size))

    schema = StructType([
        StructField("filename", StringType(), False),
        StructField("path", StringType(), False),
        StructField("size_bytes", LongType(), False),
    ])

    df = spark.createDataFrame(records, schema=schema)
    print(f"[Spark] Images détectées: {df.count()}")

    # ── Step 2: Transform — normalize, filter, enrich ─────────────────────────
    df_clean = df \
        .filter(col("size_bytes") > 1024) \
        .withColumn("extension", lower(regexp_extract(col("filename"), r"\.(\w+)$", 1))) \
        .withColumn("source", lit("catalog")) \
        .dropDuplicates(["filename"])

    print(f"[Spark] Images après nettoyage: {df_clean.count()}")

    # ── Step 3: Output — save as Parquet ──────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "catalog_manifest.parquet")

    df_clean.coalesce(1).write.mode("overwrite").parquet(output_path)
    print(f"[Spark] Manifest Parquet écrit : {output_path}")

    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Dossier des images sources")
    parser.add_argument("--output", required=True, help="Dossier de sortie Parquet")
    args = parser.parse_args()
    main(args.input, args.output)
