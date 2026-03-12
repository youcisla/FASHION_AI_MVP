FROM apache/airflow:2.9.2

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python deps needed by DAG tasks (index_to_qdrant, validate)
# Pin qdrant-client to 1.9.1 to avoid grpc EnumTypeWrapper | None TypeError on Python 3.11
RUN pip install --no-cache-dir \
    sentence-transformers>=2.7.0 \
    "qdrant-client==1.9.1" \
    Pillow>=10.0.0 \
    pyspark>=3.5.0
