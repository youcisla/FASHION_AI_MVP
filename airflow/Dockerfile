FROM apache/airflow:2.9.2

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python deps needed by DAG tasks (index_to_qdrant, validate)
RUN pip install --no-cache-dir \
    sentence-transformers>=2.7.0 \
    qdrant-client>=1.9.0 \
    Pillow>=10.0.0 \
    pyspark>=3.5.0
