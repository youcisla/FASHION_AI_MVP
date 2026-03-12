# fashion_pipeline_dag.py
"""
DAG orchestrating the Fashion AI data pipeline with enhanced error handling,
monitoring, and professional features.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.common.sql.sensors.sql import SqlSensor
from airflow.operators.dummy import DummyOperator
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
import os
import json
import logging

# ─── Configuration ────────────────────────────────────────────────────────────
PIPELINE_CONFIG = {
    "catalog_dir": Variable.get("fashion_catalog_dir", default_var="/opt/airflow/Data/catalog"),
    "processed_dir": Variable.get("fashion_processed_dir", default_var="/opt/airflow/Data/processed"),
    "reports_dir": Variable.get("fashion_reports_dir", default_var="/opt/airflow/Data/reports"),
    "spark_master": Variable.get("spark_master", default_var="local[*]"),
    "spark_memory": Variable.get("spark_driver_memory", default_var="2g"),
    "qdrant_host": Variable.get("qdrant_host", default_var="qdrant"),
    "qdrant_port": int(Variable.get("qdrant_port", default_var="6333")),
    "collection_name": "fashion_images",
    "min_success_rate": 80.0,
}

# ─── Default arguments ────────────────────────────────────────────────────────
default_args = {
    "owner": "fashion-ai-team",
    "depends_on_past": False,
    "email": ["data-team@company.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

# ─── DAG definition ───────────────────────────────────────────────────────────
dag = DAG(
    dag_id="fashion_pipeline_v2",
    default_args=default_args,
    description="Production Fashion AI Pipeline with monitoring",
    schedule_interval="0 2 * * *",  # Daily at 2 AM
    # schedule_interval="0 2 * * 1",  # Weekly on Monday at 2 AM
    # schedule_interval="@daily",     # Alternative daily
    # schedule_interval="@weekly",    # Alternative weekly
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["fashion", "spark", "qdrant", "production"],
)

# ─── Helper Functions ─────────────────────────────────────────────────────────
def setup_directories():
    """Ensure all required directories exist."""
    for dir_path in [PIPELINE_CONFIG["catalog_dir"], 
                      PIPELINE_CONFIG["processed_dir"], 
                      PIPELINE_CONFIG["reports_dir"]]:
        os.makedirs(dir_path, exist_ok=True)
        logging.info(f"Directory ensured: {dir_path}")

def check_spark_installation():
    """Verify Spark is properly installed."""
    import subprocess
    try:
        result = subprocess.run(
            ["spark-submit", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(f"Spark not properly installed: {result.stderr}")
        logging.info("Spark installation verified")
        return True
    except Exception as e:
        logging.error(f"Spark check failed: {e}")
        raise

# ─── Tasks ────────────────────────────────────────────────────────────────────

with dag:
    
    # Start task
    start = DummyOperator(task_id="start")
    
    # Setup task
    task_setup = PythonOperator(
        task_id="setup_environment",
        python_callable=setup_directories,
    )
    
    # Spark check task
    task_check_spark = PythonOperator(
        task_id="check_spark",
        python_callable=check_spark_installation,
    )
    
    # ── TASK GROUP: Data Ingestion ───────────────────────────────────────────
    with TaskGroup("data_ingestion") as ingestion_group:
        
        def validate_catalog_structure(**context):
            """Validate catalog directory structure and permissions."""
            catalog_dir = PIPELINE_CONFIG["catalog_dir"]
            
            if not os.path.exists(catalog_dir):
                raise FileNotFoundError(f"Catalog directory not found: {catalog_dir}")
            
            if not os.access(catalog_dir, os.R_OK):
                raise PermissionError(f"Cannot read catalog directory: {catalog_dir}")
            
            logging.info(f"Catalog directory validated: {catalog_dir}")
            return True
        
        def ingest_catalog(**context):
            """Enhanced catalog ingestion with metadata extraction."""
            import hashlib
            from PIL import Image
            
            catalog_dir = PIPELINE_CONFIG["catalog_dir"]
            supported_exts = (".jpg", ".jpeg", ".png", ".webp")
            
            images_metadata = []
            
            for filename in os.listdir(catalog_dir):
                if filename.lower().endswith(supported_exts):
                    file_path = os.path.join(catalog_dir, filename)
                    
                    try:
                        # Get file metadata
                        file_stats = os.stat(file_path)
                        
                        # Calculate file hash for deduplication
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()
                        
                        # Get image dimensions
                        with Image.open(file_path) as img:
                            width, height = img.size
                            format_type = img.format
                        
                        metadata = {
                            "path": file_path,
                            "filename": filename,
                            "size_bytes": file_stats.st_size,
                            "modified_time": file_stats.st_mtime,
                            "hash": file_hash,
                            "width": width,
                            "height": height,
                            "format": format_type
                        }
                        
                        images_metadata.append(metadata)
                        
                    except Exception as e:
                        logging.warning(f"Failed to process {filename}: {e}")
                        continue
            
            if not images_metadata:
                raise ValueError(f"No valid images found in {catalog_dir}")
            
            logging.info(f"Ingested {len(images_metadata)} images with metadata")
            
            # Push to XCom
            context["ti"].xcom_push(key="images_metadata", value=images_metadata)
            context["ti"].xcom_push(key="image_count", value=len(images_metadata))
            
            # Save metadata to file for Spark
            metadata_file = os.path.join(
                PIPELINE_CONFIG["processed_dir"], 
                "ingestion_metadata.json"
            )
            with open(metadata_file, 'w') as f:
                json.dump(images_metadata, f, indent=2)
            
            context["ti"].xcom_push(key="metadata_file", value=metadata_file)
            
            return len(images_metadata)
        
        validate_task = PythonOperator(
            task_id="validate_catalog",
            python_callable=validate_catalog_structure,
        )
        
        ingest_task = PythonOperator(
            task_id="ingest_images",
            python_callable=ingest_catalog,
        )
        
        validate_task >> ingest_task
    
    # ── TASK: Spark Transformation (Fixed) ───────────────────────────────────
    def create_spark_job_script(**context):
        """Create Spark job script dynamically."""
        ti = context["ti"]
        metadata_file = ti.xcom_pull(task_ids="data_ingestion.ingest_images", key="metadata_file")
        
        spark_script = f"""
#!/usr/bin/env python
# Auto-generated Spark job for Fashion Pipeline

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf, lit
from pyspark.sql.types import StringType, FloatType
import json
import os

def main():
    spark = SparkSession.builder \\
        .appName("FashionCatalogTransform") \\
        .config("spark.sql.adaptive.enabled", "true") \\
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \\
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    # Read metadata
    with open("{metadata_file}", 'r') as f:
        metadata = json.load(f)
    
    # Create DataFrame
    df = spark.createDataFrame(metadata)
    
    # Add transformations
    df_transformed = df \\
        .filter(col("size_bytes") > 0) \\
        .filter(col("width") >= 224) \\
        .filter(col("height") >= 224) \\
        .withColumn("aspect_ratio", col("width") / col("height")) \\
        .withColumn("megapixels", (col("width") * col("height")) / 1000000)
    
    # Show stats
    print(f"Total images: {{df.count()}}")
    print(f"After filtering: {{df_transformed.count()}}")
    
    # Save results
    output_path = "{PIPELINE_CONFIG['processed_dir']}/spark_output"
    df_transformed.coalesce(1).write \\
        .mode("overwrite") \\
        .json(output_path)
    
    print(f"Results saved to: {{output_path}}")
    
    spark.stop()

if __name__ == "__main__":
    main()
"""
        
        # Save script
        script_path = "/tmp/spark_fashion_job.py"
        with open(script_path, 'w') as f:
            f.write(spark_script)
        
        os.chmod(script_path, 0o755)
        logging.info(f"Spark script created: {script_path}")
        
        return script_path
    
    create_spark_script = PythonOperator(
        task_id="create_spark_script",
        python_callable=create_spark_job_script,
    )
    
    # Fixed Spark submit command
    spark_transform = BashOperator(
        task_id="spark_transform",
        bash_command="""
        if command -v spark-submit &> /dev/null; then
            spark-submit \
                --master {{ params.spark_master }} \
                --driver-memory {{ params.spark_memory }} \
                --conf spark.executor.memory=1g \
                --conf spark.executor.cores=2 \
                /tmp/spark_fashion_job.py
        else
            echo "Warning: spark-submit not found, using Python fallback"
            python /tmp/spark_fashion_job.py
        fi
        """,
        params={
            'spark_master': PIPELINE_CONFIG['spark_master'],
            'spark_memory': PIPELINE_CONFIG['spark_memory']
        },
    )
    
    # ── TASK GROUP: Vector Indexing ──────────────────────────────────────────
    with TaskGroup("vector_indexing") as indexing_group:
        
        def check_qdrant_health(**context):
            """Check Qdrant service health."""
            from qdrant_client import QdrantClient
            from qdrant_client.http.exceptions import UnexpectedResponse
            
            try:
                client = QdrantClient(
                    host=PIPELINE_CONFIG["qdrant_host"],
                    port=PIPELINE_CONFIG["qdrant_port"],
                    timeout=30
                )
                
                # Check collections
                collections = client.get_collections()
                logging.info(f"Qdrant healthy. Collections: {[c.name for c in collections.collections]}")
                return True
                
            except Exception as e:
                logging.error(f"Qdrant health check failed: {e}")
                raise
        
        def index_to_qdrant(**context):
            """Enhanced indexing with batch processing and error recovery."""
            import uuid
            from PIL import Image
            from sentence_transformers import SentenceTransformer
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct, VectorParams, Distance
            import numpy as np
            
            ti = context["ti"]
            images_metadata = ti.xcom_pull(
                task_ids="data_ingestion.ingest_images", 
                key="images_metadata"
            )
            
            # Initialize model and client
            model = SentenceTransformer("clip-ViT-B-32")
            client = QdrantClient(
                host=PIPELINE_CONFIG["qdrant_host"],
                port=PIPELINE_CONFIG["qdrant_port"],
                timeout=120
            )
            
            collection_name = PIPELINE_CONFIG["collection_name"]
            
            # Create or recreate collection
            try:
                client.delete_collection(collection_name)
            except:
                pass
            
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=512, distance=Distance.COSINE),
            )
            
            # Batch processing
            batch_size = 10
            points = []
            errors = []
            processed = 0
            
            for i in range(0, len(images_metadata), batch_size):
                batch = images_metadata[i:i+batch_size]
                batch_points = []
                
                for img_meta in batch:
                    try:
                        with Image.open(img_meta["path"]) as img:
                            # Resize if too large
                            if img.width > 1024 or img.height > 1024:
                                img.thumbnail((1024, 1024), Image.LANCZOS)
                            
                            vector = model.encode(img).tolist()
                            
                            batch_points.append(
                                PointStruct(
                                    id=str(uuid.uuid4()),
                                    vector=vector,
                                    payload={
                                        "path": img_meta["path"],
                                        "filename": img_meta["filename"],
                                        "size_bytes": img_meta["size_bytes"],
                                        "width": img_meta["width"],
                                        "height": img_meta["height"],
                                        "hash": img_meta["hash"]
                                    }
                                )
                            )
                            
                    except Exception as e:
                        errors.append({
                            "path": img_meta["path"],
                            "error": str(e)
                        })
                        logging.error(f"Failed to encode {img_meta['filename']}: {e}")
                
                # Upsert batch
                if batch_points:
                    client.upsert(collection_name=collection_name, points=batch_points)
                    points.extend(batch_points)
                    processed += len(batch_points)
                    logging.info(f"Indexed batch: {processed}/{len(images_metadata)}")
            
            # Push results
            indexed_count = len(points)
            ti.xcom_push(key="indexed_count", value=indexed_count)
            ti.xcom_push(key="indexing_errors", value=errors)
            
            logging.info(f"Indexing complete: {indexed_count} vectors, {len(errors)} errors")
            
            return indexed_count
        
        health_check = PythonOperator(
            task_id="check_qdrant",
            python_callable=check_qdrant_health,
        )
        
        index_task = PythonOperator(
            task_id="index_vectors",
            python_callable=index_to_qdrant,
        )
        
        health_check >> index_task
    
    # ── TASK: Validation and Reporting ───────────────────────────────────────
    def validate_and_report(**context):
        """Enhanced validation with detailed reporting."""
        from datetime import datetime as dt
        
        ti = context["ti"]
        
        # Gather metrics
        image_count = ti.xcom_pull(
            task_ids="data_ingestion.ingest_images", 
            key="image_count"
        ) or 0
        
        indexed_count = ti.xcom_pull(
            task_ids="vector_indexing.index_vectors", 
            key="indexed_count"
        ) or 0
        
        errors = ti.xcom_pull(
            task_ids="vector_indexing.index_vectors", 
            key="indexing_errors"
        ) or []
        
        success_rate = (indexed_count / image_count * 100) if image_count > 0 else 0
        
        # Create detailed report
        report = {
            "pipeline_run": {
                "dag_id": context["dag"].dag_id,
                "run_id": context["run_id"],
                "execution_date": context["execution_date"].isoformat(),
                "completion_time": dt.utcnow().isoformat(),
            },
            "metrics": {
                "images_detected": image_count,
                "images_indexed": indexed_count,
                "errors_count": len(errors),
                "success_rate_pct": round(success_rate, 2),
            },
            "quality_checks": {
                "min_success_rate_met": success_rate >= PIPELINE_CONFIG["min_success_rate"],
                "has_indexed_data": indexed_count > 0,
            },
            "error_summary": errors[:10] if errors else [],  # First 10 errors
        }
        
        # Save report
        os.makedirs(PIPELINE_CONFIG["reports_dir"], exist_ok=True)
        report_filename = f"pipeline_report_{context['execution_date'].strftime('%Y%m%d_%H%M%S')}.json"
        report_path = os.path.join(PIPELINE_CONFIG["reports_dir"], report_filename)
        
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        logging.info(f"Report saved: {report_path}")
        logging.info(f"Pipeline metrics - Success rate: {success_rate:.1f}%")
        
        # Quality gate
        if success_rate < PIPELINE_CONFIG["min_success_rate"]:
            raise ValueError(
                f"Pipeline quality gate failed: {success_rate:.1f}% < {PIPELINE_CONFIG['min_success_rate']}%"
            )
        
        # Push report path for potential downstream tasks
        ti.xcom_push(key="report_path", value=report_path)
        
        return report
    
    validation_task = PythonOperator(
        task_id="validate_and_report",
        python_callable=validate_and_report,
        trigger_rule="all_done",  # Run even if upstream tasks fail
    )
    
    # End task
    end = DummyOperator(
        task_id="end",
        trigger_rule="all_done"
    )
    
    # ─── Task Dependencies ────────────────────────────────────────────────────
    start >> [task_setup, task_check_spark]
    [task_setup, task_check_spark] >> ingestion_group
    ingestion_group >> create_spark_script >> spark_transform
    spark_transform >> indexing_group
    indexing_group >> validation_task >> end
