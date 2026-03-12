# Airflow Integration Plan — Fashion AI Pipeline
### Orchestration d'un pipeline Big Data avec Apache Airflow

---

## Table of Contents

1. [Project Overview & Context](#1-project-overview--context)
2. [Recommended Architecture](#2-recommended-architecture)
3. [Project Folder Structure](#3-project-folder-structure)
4. [Airflow DAG Design](#4-airflow-dag-design)
5. [Streamlit ↔ Airflow Interaction](#5-streamlit--airflow-interaction)
6. [Full DAG Implementation](#6-full-dag-implementation)
7. [Supporting Scripts](#7-supporting-scripts)
8. [Deployment Considerations](#8-deployment-considerations)
9. [Monitoring & Logs](#9-monitoring--logs)
10. [Bonus Features](#10-bonus-features)
11. [Best Practices & Pitfalls](#11-best-practices--pitfalls)
12. [Dependencies & Installation](#12-dependencies--installation)

---

## 1. Project Overview & Context

The existing project is a **Fashion AI** application built with:

| Component | Role |
|---|---|
| **Streamlit** (`app.py`) | User-facing interface (login, search, look generator, analytics) |
| **Qdrant** | Vector database storing fashion image embeddings and user profiles |
| **Redis** | Message queue between `producer.py` and `worker_ia.py` |
| **CLIP (clip-ViT-B-32)** | Vision encoder for semantic image/text embedding |
| **`batch_indexer.py`** | Bulk-indexes all catalog images into Qdrant |
| **`producer.py`** | Watches catalog folder, pushes new image paths to Redis queue |
| **`worker_ia.py`** | Consumes Redis queue, encodes images, upserts vectors into Qdrant |

The goal of this integration is to **orchestrate** all of the above pipeline steps using **Apache Airflow**, so they are scheduled, monitored, retried automatically, and can also be triggered manually from the Streamlit interface.

---

## 2. Recommended Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        USER LAYER                            │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Streamlit App (app.py)                  │   │
│   │   - Login / Profile                                  │   │
│   │   - Semantic Search                                  │   │
│   │   - Look Generator                                   │   │
│   │   - Analytics Dashboard                              │   │
│   │   - 🆕 Pipeline Trigger Panel (via Airflow REST API) │   │
│   └────────────────────┬────────────────────────────────┘   │
└────────────────────────┼─────────────────────────────────────┘
                         │ HTTP (Airflow REST API)
                         │ POST /api/v1/dags/{dag_id}/dagRuns
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                       │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │             Apache Airflow                           │   │
│   │                                                      │   │
│   │   Scheduler ──► DAG: fashion_pipeline               │   │
│   │                        │                             │   │
│   │                  ┌─────▼──────┐                     │   │
│   │                  │  Task 1    │  ingest_catalog      │   │
│   │                  │ (Python)   │  (scan Data/catalog) │   │
│   │                  └─────┬──────┘                     │   │
│   │                        │                             │   │
│   │                  ┌─────▼──────┐                     │   │
│   │                  │  Task 2    │  spark_transform     │   │
│   │                  │  (Bash /   │  (PySpark job)       │   │
│   │                  │  Spark)    │                      │   │
│   │                  └─────┬──────┘                     │   │
│   │                        │                             │   │
│   │                  ┌─────▼──────┐                     │   │
│   │                  │  Task 3    │  index_to_qdrant     │   │
│   │                  │ (Python)   │  (batch_indexer)     │   │
│   │                  └─────┬──────┘                     │   │
│   │                        │                             │   │
│   │                  ┌─────▼──────┐                     │   │
│   │                  │  Task 4    │  validate_export     │   │
│   │                  │ (Python)   │  (verify + report)   │   │
│   │                  └────────────┘                     │   │
│   │                                                      │   │
│   │   Webserver ──► UI (localhost:8080)                  │   │
│   └─────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌─────────────┐ ┌──────────┐ ┌───────────────┐
   │   Qdrant    │ │  Redis   │ │  Data/catalog  │
   │ :6333       │ │ :6379    │ │  (images)      │
   └─────────────┘ └──────────┘ └───────────────┘
```

### Key Design Decisions

- **Streamlit does NOT execute pipeline logic directly.** It delegates to Airflow via the REST API.
- **Airflow orchestrates** all heavy work: ingestion, Spark transformation, Qdrant indexing, and validation.
- **Redis** is still used internally by the worker for streaming/real-time ingestion, but the *batch pipeline* is fully owned by Airflow.
- **Qdrant** remains the single source of truth for vectors.

---

## 3. Project Folder Structure

```
fashion-ai/
│
├── app.py                        # Streamlit main app
├── auth.py                       # Authentication logic
├── utile.py                      # Shared utilities (Qdrant, hashing, etc.)
├── search.py                     # Semantic search component
├── analytic.py                   # Analytics component
├── profile_ai.py                 # Profile sidebar
├── look_generator.py             # Look generator component
│
├── airflow/
│   ├── dags/
│   │   └── fashion_pipeline_dag.py   # ★ Main Airflow DAG
│   ├── plugins/                       # Custom Airflow operators (optional)
│   └── logs/                          # Auto-generated by Airflow
│
├── spark_jobs/
│   └── transform_catalog.py          # ★ PySpark transformation job
│
├── scripts/
│   ├── ingest_catalog.py             # Ingestion task (Task 1)
│   ├── index_to_qdrant.py            # Indexing task (Task 3)
│   └── validate_export.py            # Validation task (Task 4)
│
├── Data/
│   └── catalog/                      # Raw fashion images
│
├── profile_images/                   # User profile photos
│
├── producer.py                       # Real-time file watcher (standalone)
├── worker_ia.py                      # Redis queue consumer (standalone)
├── batch_indexer.py                  # Legacy batch indexer (now wrapped by Airflow)
│
├── docker-compose.yml                # All services (Airflow, Qdrant, Redis, Spark)
├── requirements.txt
└── README.md
```

---

## 4. Airflow DAG Design

### Pipeline Overview

The DAG `fashion_pipeline` implements the full lifecycle:

```
[ingest_catalog] → [spark_transform] → [index_to_qdrant] → [validate_export]
```

| Task ID | Operator | Description |
|---|---|---|
| `ingest_catalog` | `PythonOperator` | Scans `Data/catalog/`, lists new images, pushes paths to XCom |
| `spark_transform` | `BashOperator` | Executes PySpark job to preprocess and normalize image metadata |
| `index_to_qdrant` | `PythonOperator` | Reads output of Spark job, encodes images with CLIP, upserts into Qdrant |
| `validate_export` | `PythonOperator` | Verifies indexed count vs. input count, writes a JSON report |

### Schedule

- **Automatic:** `schedule_interval="0 2 * * *"` — runs daily at 2:00 AM
- **Manual:** Triggerable at any time from Airflow UI or Streamlit via REST API

---

## 5. Streamlit ↔ Airflow Interaction

### How Streamlit Triggers Airflow

Streamlit communicates with Airflow through its **stable REST API** (available since Airflow 2.0).

Add the following panel to `app.py` inside the logged-in dashboard section:

```python
# app.py — Pipeline Trigger Panel (add inside the logged-in block)
import requests
from datetime import datetime

AIRFLOW_BASE_URL = "http://localhost:8080"
AIRFLOW_USER = "admin"
AIRFLOW_PASSWORD = "admin"
DAG_ID = "fashion_pipeline"

if mode == "Pipeline Admin":
    st.header("⚙️ Gestion du Pipeline Airflow")

    col1, col2 = st.columns(2)

    # Trigger DAG manually
    with col1:
        if st.button("▶️ Lancer le pipeline maintenant"):
            run_id = f"manual__{datetime.utcnow().isoformat()}"
            response = requests.post(
                f"{AIRFLOW_BASE_URL}/api/v1/dags/{DAG_ID}/dagRuns",
                json={"dag_run_id": run_id},
                auth=(AIRFLOW_USER, AIRFLOW_PASSWORD)
            )
            if response.status_code == 200:
                st.success(f"Pipeline lancé ! Run ID: {run_id}")
            else:
                st.error(f"Erreur : {response.text}")

    # Get last DAG run status
    with col2:
        if st.button("🔄 Statut du dernier run"):
            response = requests.get(
                f"{AIRFLOW_BASE_URL}/api/v1/dags/{DAG_ID}/dagRuns?limit=1&order_by=-execution_date",
                auth=(AIRFLOW_USER, AIRFLOW_PASSWORD)
            )
            if response.status_code == 200:
                runs = response.json().get("dag_runs", [])
                if runs:
                    last = runs[0]
                    st.json({
                        "state": last["state"],
                        "run_id": last["dag_run_id"],
                        "start_date": last["start_date"],
                        "end_date": last["end_date"],
                    })
```

> **Security note:** In production, store `AIRFLOW_USER`/`AIRFLOW_PASSWORD` in environment variables or a secrets manager — never hardcode credentials.

---

## 6. Full DAG Implementation

### `airflow/dags/fashion_pipeline_dag.py`

```python
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
    "retries": 2,                          # BONUS: automatic retry
    "retry_delay": timedelta(minutes=5),
}

# ─── DAG definition ───────────────────────────────────────────────────────────
with DAG(
    dag_id="fashion_pipeline",
    default_args=default_args,
    description="Pipeline complet Fashion AI : ingestion → Spark → Qdrant → validation",
    schedule_interval="0 2 * * *",         # Daily at 02:00
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

        # Push to XCom — BONUS: XCom usage
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

        # Pull image list from XCom — BONUS: XCom usage
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

        # Push result count to XCom
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
        from datetime import datetime

        ti = context["ti"]
        image_count = ti.xcom_pull(task_ids="ingest_catalog", key="image_count")
        indexed_count = ti.xcom_pull(task_ids="index_to_qdrant", key="indexed_count")
        errors = ti.xcom_pull(task_ids="index_to_qdrant", key="errors") or []

        success_rate = (indexed_count / image_count * 100) if image_count else 0

        report = {
            "run_date": datetime.utcnow().isoformat(),
            "images_detected": image_count,
            "images_indexed": indexed_count,
            "errors": len(errors),
            "success_rate_pct": round(success_rate, 2),
            "error_details": errors,
        }

        os.makedirs("/opt/airflow/Data/reports", exist_ok=True)
        report_path = f"/opt/airflow/Data/reports/report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"[validate_export] Rapport écrit : {report_path}")
        print(f"[validate_export] Taux de succès : {success_rate:.1f}%")

        # Fail the task if success rate drops below 80%
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
```

---

## 7. Supporting Scripts

### `spark_jobs/transform_catalog.py` — PySpark Transformation Job

```python
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
```

### `scripts/validate_export.py` — Standalone Validation (for testing)

```python
"""
validate_export.py
Can be run standalone outside of Airflow for local testing.
"""
import json
import os
from qdrant_client import QdrantClient

def run_validation(expected_count: int, report_dir: str = "Data/reports"):
    client = QdrantClient(host="localhost", port=6333)
    count = client.count(collection_name="fashion_images").count
    print(f"Expected: {expected_count}, In Qdrant: {count}")

    os.makedirs(report_dir, exist_ok=True)
    with open(f"{report_dir}/latest.json", "w") as f:
        json.dump({"expected": expected_count, "indexed": count}, f)

if __name__ == "__main__":
    run_validation(expected_count=100)
```

---

## 8. Deployment Considerations

### 8.1 Local Development — Docker Compose

Create `docker-compose.yml` to orchestrate all services:

```yaml
version: "3.8"

x-airflow-common: &airflow-common
  image: apache/airflow:2.9.2
  environment:
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    AIRFLOW__CORE__FERNET_KEY: ""
    AIRFLOW__WEBSERVER__SECRET_KEY: "fashion-ai-secret"
    AIRFLOW__API__AUTH_BACKENDS: "airflow.api.auth.backend.basic_auth"
  volumes:
    - ./airflow/dags:/opt/airflow/dags
    - ./airflow/logs:/opt/airflow/logs
    - ./spark_jobs:/opt/airflow/spark_jobs
    - ./scripts:/opt/airflow/scripts
    - ./Data:/opt/airflow/Data
  depends_on:
    postgres:
      condition: service_healthy

services:

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 10s
      retries: 5

  airflow-webserver:
    <<: *airflow-common
    ports:
      - "8080:8080"
    command: webserver
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8080/health"]
      interval: 30s

  airflow-scheduler:
    <<: *airflow-common
    command: scheduler

  airflow-init:
    <<: *airflow-common
    command: >
      bash -c "airflow db init &&
               airflow users create --username admin --password admin
               --firstname Admin --lastname User --role Admin
               --email admin@fashion-ai.com"

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  streamlit:
    build: .
    ports:
      - "8501:8501"
    command: streamlit run app.py --server.port 8501
    depends_on:
      - qdrant
      - redis
    environment:
      AIRFLOW_BASE_URL: "http://airflow-webserver:8080"

volumes:
  qdrant_storage:
```

**Start everything:**
```bash
docker-compose up -d
docker-compose run airflow-init
```

### 8.2 Local Development — Without Docker

```bash
# 1. Create virtual environment
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize Airflow
export AIRFLOW_HOME=$(pwd)/airflow
airflow db init

# 4. Create admin user
airflow users create \
  --username admin --password admin \
  --firstname Admin --lastname User \
  --role Admin --email admin@local.dev

# 5. Copy DAG
cp airflow/dags/fashion_pipeline_dag.py $AIRFLOW_HOME/dags/

# 6. Start services (separate terminals)
airflow webserver --port 8080
airflow scheduler

# 7. Start Streamlit
streamlit run app.py
```

### 8.3 Production Considerations

| Concern | Recommendation |
|---|---|
| **Executor** | Switch from `LocalExecutor` to `CeleryExecutor` or `KubernetesExecutor` for scalability |
| **Database** | Use managed PostgreSQL (e.g., AWS RDS, Cloud SQL) instead of local Postgres |
| **Secrets** | Use Airflow Connections & Variables, or integrate with HashiCorp Vault |
| **Qdrant** | Use Qdrant Cloud or a dedicated VM with persistent volumes |
| **Spark** | Replace `local[*]` with a real Spark cluster (e.g., EMR, Dataproc) |
| **Reverse proxy** | Put Nginx in front of both Airflow (8080) and Streamlit (8501) |
| **Authentication** | Enable Airflow's OAuth2/LDAP integration; protect the REST API |
| **CI/CD** | Lint DAGs with `airflow dags test` in your CI pipeline before deploying |

---

## 9. Monitoring & Logs

### From the Airflow Webserver (localhost:8080)

- **DAGs view:** See all DAGs, their schedule, and last run status
- **Grid view:** Visual timeline of all task runs across DAG runs
- **Graph view:** Interactive task dependency graph
- **Task logs:** Click any task instance → "Logs" to read stdout/stderr
- **Task duration chart:** Track performance over time

### From Streamlit (optional monitoring panel)

```python
# Add to app.py for a live monitoring widget
if mode == "Pipeline Admin":
    st.subheader("📋 Historique des runs")
    response = requests.get(
        f"{AIRFLOW_BASE_URL}/api/v1/dags/{DAG_ID}/dagRuns?limit=5&order_by=-execution_date",
        auth=(AIRFLOW_USER, AIRFLOW_PASSWORD)
    )
    if response.status_code == 200:
        runs = response.json().get("dag_runs", [])
        for run in runs:
            color = "🟢" if run["state"] == "success" else "🔴" if run["state"] == "failed" else "🟡"
            st.write(f"{color} `{run['dag_run_id']}` — {run['state']} — {run['start_date']}")
```

---

## 10. Bonus Features

### B1 — Automatic Retry (already included)
```python
default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}
```

### B2 — XComs (already included)
All tasks pass data between each other via `ti.xcom_push` / `ti.xcom_pull`. The image list, count, and error details flow through the full pipeline without using shared files.

### B3 — Sensor (optional addition)
Add a sensor before `ingest_catalog` to wait until new images appear:

```python
from airflow.sensors.filesystem import FileSensor

task_wait_for_images = FileSensor(
    task_id="wait_for_catalog_images",
    filepath="/opt/airflow/Data/catalog/*.jpg",
    poke_interval=60,          # check every 60s
    timeout=3600,              # fail after 1 hour
    mode="reschedule",         # free worker slot while waiting
)

task_wait_for_images >> task_ingest >> task_spark >> task_index >> task_validate
```

### B4 — Dynamic Pipeline (optional addition)
Generate tasks dynamically based on catalog subdirectories:

```python
import os

categories = [d for d in os.listdir("/opt/airflow/Data/catalog")
              if os.path.isdir(os.path.join("/opt/airflow/Data/catalog", d))]

index_tasks = []
for category in categories:
    t = PythonOperator(
        task_id=f"index_{category}",
        python_callable=index_to_qdrant,
        op_kwargs={"category": category},
        provide_context=True,
    )
    task_spark >> t
    index_tasks.append(t)

index_tasks >> task_validate
```

---

## 11. Best Practices & Pitfalls

### ✅ Best Practices

| Practice | Why |
|---|---|
| Use `catchup=False` on all DAGs | Prevents Airflow from retroactively running all missed intervals on first deploy |
| Keep tasks **idempotent** | A task re-run should produce the same result (use `upsert` in Qdrant, not `insert`) |
| Use XComs for small data only | XComs are stored in the Airflow metadata DB — never push large payloads (use files/S3 instead) |
| Set `retries` and `retry_delay` | Makes pipelines resilient to transient network or service failures |
| Set `execution_timeout` per task | Prevents hung tasks from blocking the scheduler |
| Test DAGs locally with `airflow dags test fashion_pipeline 2024-01-01` | Validates the DAG before deploying |
| Keep Spark jobs in separate files | Easier to test, version, and debug independently from Airflow |
| Never import heavy libraries at the top of the DAG file | Slows down DAG parsing; import inside callable functions instead |

### ⚠️ Common Pitfalls

| Pitfall | Solution |
|---|---|
| Streamlit calling Qdrant/Redis directly for long jobs | Delegate all heavy work to Airflow; Streamlit only reads results |
| Hardcoding absolute paths | Use `AIRFLOW_HOME` env var or Airflow Variables for paths |
| Using `LocalExecutor` in production with parallel DAGs | Switch to `CeleryExecutor` for true parallelism |
| Not setting `start_date` in the past | Airflow won't schedule DAGs with a future `start_date` |
| Importing `SentenceTransformer` at DAG file top-level | This runs on every DAG parse cycle; always import inside task functions |
| Calling `client.recreate_collection` in the indexing task | This **deletes** existing data; use `get_or_create` pattern with `create_collection` conditionally |

---

## 12. Dependencies & Installation

### `requirements.txt`

```
# Core application
streamlit>=1.32.0
qdrant-client>=1.9.0
sentence-transformers>=2.7.0
Pillow>=10.0.0
redis>=5.0.0
watchdog>=4.0.0
plotly>=5.20.0
pandas>=2.0.0
scikit-learn>=1.4.0

# Airflow
apache-airflow==2.9.2
apache-airflow-providers-apache-spark>=4.7.0

# Spark
pyspark>=3.5.0

# HTTP client (for Streamlit → Airflow API calls)
requests>=2.31.0
```

### Quick Start Commands

```bash
# Initialize and start the full stack with Docker
docker-compose up -d

# Or locally:
pip install -r requirements.txt
export AIRFLOW_HOME=$(pwd)/airflow
airflow db init
airflow users create --username admin --password admin \
  --firstname Admin --lastname User --role Admin --email admin@local.dev
airflow webserver --port 8080 &
airflow scheduler &
streamlit run app.py
```

### Verify the setup

```bash
# Check Airflow is up
curl http://localhost:8080/health

# Trigger DAG manually via CLI
airflow dags trigger fashion_pipeline

# Trigger via REST API (as Streamlit would do)
curl -X POST http://localhost:8080/api/v1/dags/fashion_pipeline/dagRuns \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{"dag_run_id": "test_run_001"}'
```

---

*Document generated for the Fashion AI project — Apache Airflow integration plan.*
*Covers all requirements from the project brief: ≥3 Airflow tasks, functional DAG, Spark job via Airflow, multiple operators (PythonOperator, BashOperator), scheduling, manual triggering, monitoring, logs, and all bonus features (retry, XComs, Sensors, dynamic pipeline).*