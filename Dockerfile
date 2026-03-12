# Utiliser l'image officielle Airflow comme base
FROM apache/airflow:2.7.1-python3.11

# Passer en root pour installer des packages
USER root

# Installer Java (Spark en a besoin) et utilitaires
RUN apt-get update && apt-get install -y \
    default-jdk \
    build-essential \
    curl \
    git \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Télécharger et installer Spark
RUN wget https://archive.apache.org/dist/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz \
    && tar -xzf spark-3.5.0-bin-hadoop3.tgz -C /opt/ \
    && ln -s /opt/spark-3.5.0-bin-hadoop3 /opt/spark \
    && rm spark-3.5.0-bin-hadoop3.tgz

# Ajouter Spark au PATH
ENV PATH="/opt/spark/bin:${PATH}"

# Passer à l'utilisateur airflow
USER airflow

# Définir le répertoire de travail (optionnel pour ton projet)
WORKDIR /app

# Copier requirements si besoin (pour Streamlit ou autre)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application
COPY . .

# Exposer le port Streamlit si tu l'utilises
EXPOSE 8501

# Commande par défaut (ici Streamlit, tu peux l'adapter si tu veux lancer Airflow)
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]