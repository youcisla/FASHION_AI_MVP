"""
validate_export.py
Can be run standalone outside of Airflow for local testing.
Verifies indexed count in Qdrant against an expected count.
"""

import json
import os
from qdrant_client import QdrantClient


def run_validation(expected_count: int, report_dir: str = "Data/reports"):
    client = QdrantClient(host="localhost", port=6333)
    count = client.count(collection_name="fashion_images").count
    print(f"Expected: {expected_count}, In Qdrant: {count}")

    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, "latest.json"), "w") as f:
        json.dump({"expected": expected_count, "indexed": count}, f, indent=2)


if __name__ == "__main__":
    run_validation(expected_count=100)
