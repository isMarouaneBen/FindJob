-- Create airflow role with proper permissions
CREATE ROLE airflow WITH LOGIN PASSWORD 'airflow';

-- Create airflow database (will be owned by airflow user)
CREATE DATABASE airflow OWNER airflow;

-- Grant connection privileges to airflow user
GRANT CONNECT ON DATABASE airflow TO airflow;
GRANT ALL PRIVILEGES ON DATABASE job_db TO airflow;

-- Ensure airflow user can create objects in databases
ALTER ROLE airflow CREATEDB CREATEROLE;

-- Set default privileges for airflow
ALTER DEFAULT PRIVILEGES FOR ROLE airflow IN SCHEMA public GRANT ALL ON TABLES TO airflow;
ALTER DEFAULT PRIVILEGES FOR ROLE airflow IN SCHEMA public GRANT ALL ON SEQUENCES TO airflow;