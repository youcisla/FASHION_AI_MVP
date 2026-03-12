"""
fashion_pipeline_dag.py
DAG orchestrating the full Fashion AI data pipeline:
  1. ingest_catalog     — scan and list new catalog images
  2. spark_transform    — PySpark preprocessing job
  3. index_to_qdrant    — CLIP encoding + Qdrant upsert
  4. validate_export    — integrity check + JSON report
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# ─── Default arguments ────────────────────────────────────────────────────────
default_args = {
    "owner": "fashion-ai",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# ─── DAG definition ───────────────────────────────────────────────────────────
with DAG(
    dag_id="fashion_pipeline",
    default_args=default_args,
    description="Pipeline complet Fashion AI : ingestion → Spark → Qdrant → validation",
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["fashion", "spark", "qdrant"],
) as dag:

    # ── TASK 1: Ingestion ──────────────────────────────────────────────────────
    def ingest_catalog(**context):
        """
        Scans Data/catalog/ for images.
        Pushes the list of image paths to XCom for downstream tasks.
        """
        import os

        CATALOG_DIR = "/opt/airflow/Data/catalog"
        SUPPORTED_EXTS = (".jpg", ".jpeg", ".png")

        images = [
            os.path.join(CATALOG_DIR, f)
            for f in os.listdir(CATALOG_DIR)
            if f.lower().endswith(SUPPORTED_EXTS)
        ]

        if not images:
            raise ValueError(f"Aucune image trouvée dans {CATALOG_DIR}")

        print(f"[ingest_catalog] {len(images)} images détectées.")

        context["ti"].xcom_push(key="image_paths", value=images)
        context["ti"].xcom_push(key="image_count", value=len(images))

        return images

    task_ingest = PythonOperator(
        task_id="ingest_catalog",
        python_callable=ingest_catalog,
        provide_context=True,
    )

    # ── TASK 2: Spark Transformation ───────────────────────────────────────────
    task_spark = BashOperator(
        task_id="spark_transform",
        bash_command=(
            "spark-submit "
            "--master local[*] "
            "--driver-memory 2g "
            "/opt/airflow/spark_jobs/transform_catalog.py "
            "--input /opt/airflow/Data/catalog "
            "--output /opt/airflow/Data/processed "
        ),
    )

    # ── TASK 3: Index to Qdrant ────────────────────────────────────────────────
    def index_to_qdrant(**context):
        """
        Retrieves image paths from XCom (set by ingest_catalog),
        encodes them with CLIP, and upserts vectors into Qdrant.
        """
        import uuid
        from PIL import Image
        from sentence_transformers import SentenceTransformer
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct, VectorParams, Distance

        ti = context["ti"]
        image_paths = ti.xcom_pull(task_ids="ingest_catalog", key="image_paths")

        model = SentenceTransformer("clip-ViT-B-32")
        client = QdrantClient(host="qdrant", port=6333, timeout=120)

        COLLECTION = "fashion_images"
        if COLLECTION not in [c.name for c in client.get_collections().collections]:
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=512, distance=Distance.COSINE),
            )

        points = []
        errors = []

        for path in image_paths:
            try:
                with Image.open(path) as img:
                    vector = model.encode(img).tolist()
                points.append(
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={"path": path, "filename": path.split("/")[-1]},
                    )
                )
            except Exception as e:
                errors.append({"path": path, "error": str(e)})
                print(f"[index_to_qdrant] Erreur sur {path}: {e}")

        if points:
            client.upsert(collection_name=COLLECTION, points=points)

        indexed_count = len(points)
        print(f"[index_to_qdrant] {indexed_count} images indexées, {len(errors)} erreurs.")

        ti.xcom_push(key="indexed_count", value=indexed_count)
        ti.xcom_push(key="errors", value=errors)

        return indexed_count

    task_index = PythonOperator(
        task_id="index_to_qdrant",
        python_callable=index_to_qdrant,
        provide_context=True,
    )

    # ── TASK 4: Validate & Export ──────────────────────────────────────────────
    def validate_export(**context):
        """
        Compares input image count vs indexed count.
        Writes a JSON validation report to Data/reports/.
        Raises if discrepancy is too large.
        """
        import json
        import os
        from datetime import datetime as dt

        ti = context["ti"]
        image_count = ti.xcom_pull(task_ids="ingest_catalog", key="image_count")
        indexed_count = ti.xcom_pull(task_ids="index_to_qdrant", key="indexed_count")
        errors = ti.xcom_pull(task_ids="index_to_qdrant", key="errors") or []

        success_rate = (indexed_count / image_count * 100) if image_count else 0

        report = {
            "run_date": dt.utcnow().isoformat(),
            "images_detected": image_count,
            "images_indexed": indexed_count,
            "errors": len(errors),
            "success_rate_pct": round(success_rate, 2),
            "error_details": errors,
        }

        os.makedirs("/opt/airflow/Data/reports", exist_ok=True)
        report_path = (
            f"/opt/airflow/Data/reports/report_{dt.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"[validate_export] Rapport écrit : {report_path}")
        print(f"[validate_export] Taux de succès : {success_rate:.1f}%")

        if success_rate < 80.0:
            raise ValueError(
                f"Taux d'indexation trop bas: {success_rate:.1f}% < 80%. "
                f"Voir le rapport: {report_path}"
            )

        return report

    task_validate = PythonOperator(
        task_id="validate_export",
        python_callable=validate_export,
        provide_context=True,
    )

    # ── Dependencies ───────────────────────────────────────────────────────────
    task_ingest >> task_spark >> task_index >> task_validate
