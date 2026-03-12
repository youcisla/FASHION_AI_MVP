# Fashion AI MVP

Application de mode intelligente : recherche sémantique, génération de looks et analytics, orchestrée par Apache Airflow.

## Architecture

```
Streamlit (UI) → Airflow (orchestration) → Spark (transformation) → Qdrant (vecteurs)
                                          → Redis (file d'attente temps réel)
```

## Prérequis

- **Docker** & **Docker Compose** (méthode recommandée)
- **Python 3.11 ou 3.12** (pas 3.13/3.14 — Airflow ne les supporte pas encore)
- **Important :** Apache Airflow ne tourne **pas** sur Windows natif. Utiliser **Docker** ou **WSL2**.

## Lancement avec Docker (recommandé)

```bash
# 1. Démarrer tous les services
docker-compose up -d

# 2. Initialiser Airflow (première fois uniquement)
docker-compose run airflow-init

# 3. Accéder aux interfaces
#    - Streamlit : http://localhost:8501
#    - Airflow   : http://localhost:8080  (admin / admin)
#    - Qdrant    : http://localhost:6333
```

## Lancement local (Windows + Docker hybride)

L'app Streamlit tourne sur Windows, Airflow dans Docker ou WSL2.

### Étape 1 — Streamlit (Windows PowerShell)

```powershell
# Créer et activer l'environnement (Python 3.11 ou 3.12 recommandé)
py -3.12 -m venv venv
venv\Scripts\Activate.ps1

# Installer les dépendances applicatives
pip install -r requirements.txt

# Démarrer Redis + Qdrant via Docker
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -p 6333:6333 qdrant/qdrant

# Lancer Streamlit
cd src
streamlit run app.py
```

### Étape 2 — Airflow (Docker ou WSL2)

**Option A — Docker (recommandé) :**
```bash
docker-compose up -d airflow-webserver airflow-scheduler postgres
docker-compose run airflow-init
# Airflow UI : http://localhost:8080  (admin / admin)
```

**Option B — WSL2 :**
```bash
# Dans un terminal WSL2
python3.12 -m venv venv-airflow
source venv-airflow/bin/activate
pip install -r requirements-airflow.txt

export AIRFLOW_HOME=$(pwd)/airflow
airflow db init
airflow users create --username admin --password admin \
  --firstname Admin --lastname User --role Admin --email admin@local.dev

# Deux terminaux WSL2 séparés :
airflow webserver --port 8080
airflow scheduler
```

Streamlit communique avec Airflow via l'API REST — les deux n'ont pas besoin d'être dans le même environnement.

## Indexer le catalogue

Placer les images dans `Data/catalog/`, puis au choix :

- **Via Airflow** : déclencher le DAG `fashion_pipeline` depuis l'UI Airflow ou le panneau "Pipeline Admin" dans Streamlit
- **Manuellement** : `python src/batch_indexer.py`
- **Temps réel** : lancer `python src/producer.py` + `python src/worker_ia.py` pour indexer automatiquement les nouvelles images

## Structure du projet

```
├── airflow/dags/          # DAG Airflow (fashion_pipeline)
├── spark_jobs/            # Job PySpark (transform_catalog)
├── scripts/               # Scripts utilitaires (validate_export)
├── src/                   # Code applicatif (Streamlit, auth, search, etc.)
├── Data/catalog/          # Images du catalogue
├── docker-compose.yml     # Stack complète
└── requirements.txt       # Dépendances Python
```