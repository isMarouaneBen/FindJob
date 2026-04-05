-- Créer le user airflow
CREATE USER airflow WITH PASSWORD 'airflow';

-- Créer la base airflow et en donner la propriété
CREATE DATABASE airflow OWNER airflow;

-- Donner tous les droits à airflow sur sa base
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;

-- Créer les schémas dans job_db
\connect job_db

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

GRANT ALL PRIVILEGES ON SCHEMA staging   TO datauser;
GRANT ALL PRIVILEGES ON SCHEMA analytics TO datauser;