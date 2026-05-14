-- =========================================================================
--  MIGRATION ENRICHISSEMENT : taxonomie métier, salaire mensuel normalisé,
--  géolocalisation, score qualité, content hash, FTS, vue de recommandation.
--
--  Idempotente : peut être ré-exécutée sans dommage.
--
--  Usage :
--      docker cp postgres-init/03-enrichment.sql job_postgres:/tmp/enr.sql
--      docker exec job_postgres psql -U datauser -d job_db -f /tmp/enr.sql
-- =========================================================================

\connect job_db
SET search_path TO analytics, public;
BEGIN;

-- -------------------------------------------------------------------------
-- 1. dim_metier
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_metier (
    metier_id      SMALLSERIAL PRIMARY KEY,
    metier_code    VARCHAR(16) NOT NULL UNIQUE,
    metier_libelle VARCHAR(64) NOT NULL,
    ordre          SMALLINT NOT NULL DEFAULT 0
);

INSERT INTO analytics.dim_metier (metier_id, metier_code, metier_libelle, ordre) OVERRIDING SYSTEM VALUE
VALUES
    (0,  'AUTRE',      'Autre',                   999),
    (1,  'DATA_SCI',   'Data Scientist / ML',      10),
    (2,  'DATA_ENG',   'Data Engineer',            20),
    (3,  'DATA_ANA',   'Data Analyst',             30),
    (4,  'BI',         'Business Intelligence',    40),
    (5,  'DATA_ARCH',  'Data Architect',           50),
    (6,  'DEVOPS',     'DevOps / SRE',             60),
    (7,  'CLOUD',      'Cloud Engineer',           70),
    (8,  'CYBER',      'Cybersécurité',            80),
    (9,  'DEV_BACK',   'Développeur Backend',      90),
    (10, 'DEV_FRONT',  'Développeur Frontend',    100),
    (11, 'DEV_FULL',   'Développeur Fullstack',   110),
    (12, 'DEV_MOBILE', 'Développeur Mobile',      120),
    (13, 'ADMIN_SYS',  'Admin Système / Réseau',  130),
    (14, 'MGT',        'Management / Direction',  140),
    (15, 'PRODUCT',    'Product / Projet',        150),
    (16, 'CONSULT',    'Consultant',              160)
ON CONFLICT (metier_code) DO UPDATE
    SET metier_libelle = EXCLUDED.metier_libelle,
        ordre          = EXCLUDED.ordre;

SELECT setval('analytics.dim_metier_metier_id_seq', 100, false);

-- -------------------------------------------------------------------------
-- 2. fact_offer : ajout des colonnes enrichies (idempotent)
-- -------------------------------------------------------------------------
ALTER TABLE analytics.fact_offer
    ADD COLUMN IF NOT EXISTS metier_id               SMALLINT NOT NULL DEFAULT 0
        REFERENCES analytics.dim_metier(metier_id),
    ADD COLUMN IF NOT EXISTS salaire_min_mensuel_eur INTEGER  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS salaire_max_mensuel_eur INTEGER  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS salaire_min_mensuel_mad INTEGER  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS salaire_max_mensuel_mad INTEGER  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS latitude                NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS longitude               NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS quality_score           SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS content_hash            CHAR(16) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS is_duplicate            BOOLEAN  NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS search_doc              TSVECTOR;

-- -------------------------------------------------------------------------
-- 3. Repopulation depuis l'existant
-- -------------------------------------------------------------------------

-- 3a. Salaire mensuel normalisé (EUR & MAD).
--     Adzuna (3) = EUR annuel → / 12. Rekrute & Emploi-public = MAD mensuel.
UPDATE analytics.fact_offer SET
    salaire_min_mensuel_eur = ROUND(salaire_min / 12.0)::int,
    salaire_max_mensuel_eur = ROUND(salaire_max / 12.0)::int,
    salaire_min_mensuel_mad = ROUND((salaire_min / 12.0) * 10.9)::int,
    salaire_max_mensuel_mad = ROUND((salaire_max / 12.0) * 10.9)::int
WHERE devise = 'EUR' AND salaire_connu;

UPDATE analytics.fact_offer SET
    salaire_min_mensuel_mad = ROUND(salaire_min)::int,
    salaire_max_mensuel_mad = ROUND(salaire_max)::int,
    salaire_min_mensuel_eur = ROUND(salaire_min / 10.9)::int,
    salaire_max_mensuel_eur = ROUND(salaire_max / 10.9)::int
WHERE devise = 'MAD' AND salaire_connu;

UPDATE analytics.fact_offer
SET salaire_min_mensuel_eur = LEAST(salaire_min_mensuel_eur, salaire_max_mensuel_eur),
    salaire_max_mensuel_eur = GREATEST(salaire_min_mensuel_eur, salaire_max_mensuel_eur)
WHERE salaire_max_mensuel_eur < salaire_min_mensuel_eur;

UPDATE analytics.fact_offer
SET salaire_min_mensuel_mad = LEAST(salaire_min_mensuel_mad, salaire_max_mensuel_mad),
    salaire_max_mensuel_mad = GREATEST(salaire_min_mensuel_mad, salaire_max_mensuel_mad)
WHERE salaire_max_mensuel_mad < salaire_min_mensuel_mad;

-- 3b. Métier : classification SQL simple (le full pipeline ETL fait mieux,
--     mais on a déjà ~1100 offres en place — on les classifie en attendant
--     une re-run complète).
UPDATE analytics.fact_offer f SET metier_id = (
    SELECT m.metier_id FROM analytics.dim_metier m
    WHERE m.metier_code = CASE
        WHEN f.poste ~* '\m(architecte\s+(de\s+)?(donn|data)|data\s+architect)\M' THEN 'DATA_ARCH'
        WHEN f.poste ~* '\m(data\s+scientist|ml\s+engineer|machine\s+learning\s+engineer)\M' THEN 'DATA_SCI'
        WHEN f.poste ~* '\m(big\s+data\s+engineer|data\s+engineer|ingenieur\s+(de\s+)?donn[ée]es)\M' THEN 'DATA_ENG'
        WHEN f.poste ~* '\m(data\s+analyst|analyste?\s+(de\s+)?donn[ée]es|business\s+analyst)\M' THEN 'DATA_ANA'
        WHEN f.poste ~* '\m(business\s+intelligence|bi\s+(developer|developpeur|consultant|analyst))\M' THEN 'BI'
        WHEN f.poste ~* '\m(devops|sre|site\s+reliability|platform\s+engineer)\M' THEN 'DEVOPS'
        WHEN f.poste ~* '\m(cloud\s+(engineer|architect|consultant)|(aws|azure|gcp)\s+(engineer|architect))\M' THEN 'CLOUD'
        WHEN f.poste ~* '\m(cybers[eé]curit|security\s+engineer|pentester|soc\s+analyst|ingenieur\s+s[eé]curit)\M' THEN 'CYBER'
        WHEN f.poste ~* '\m(full[\s-]?stack)\M' THEN 'DEV_FULL'
        WHEN f.poste ~* '\m(back[\s-]?end|backend).*?(developer|developpeur|engineer|ingenieur)\M' THEN 'DEV_BACK'
        WHEN f.poste ~* '\m(front[\s-]?end|frontend).*?(developer|developpeur|engineer|ingenieur)\M' THEN 'DEV_FRONT'
        WHEN f.poste ~* '\m(mobile|android|ios)\s+(developer|developpeur)|react\s*native|flutter\M' THEN 'DEV_MOBILE'
        WHEN f.poste ~* '\m(administrateur|admin)\s+(syst[eè]me|r[eé]seau|infrastructure)|system\s+administrator\M' THEN 'ADMIN_SYS'
        WHEN f.poste ~* '\m(product\s+(owner|manager)|scrum\s+master|chef\s+de\s+projet|project\s+manager)\M' THEN 'PRODUCT'
        WHEN f.poste ~* '\m(directeur|director|head\s+of|cto|cio|chief)\M' THEN 'MGT'
        WHEN f.poste ~* '\mconsultant\M' THEN 'CONSULT'
        WHEN f.poste ~* '\m(developpeur|developer|software\s+engineer)\M' THEN 'DEV_BACK'
        ELSE 'AUTRE'
    END
);

-- 3c. Score qualité initial (pondération basique sur l'existant).
UPDATE analytics.fact_offer SET quality_score = LEAST(100,
      (CASE WHEN poste IS NOT NULL AND poste <> '' AND poste <> 'Non spécifié' THEN 10 ELSE 0 END)
    + (CASE WHEN societe_id <> 0 THEN 10 ELSE 0 END)
    + (CASE WHEN ville_id <> 0 THEN 10 ELSE 0 END)
    + (CASE WHEN contrat_id <> 0 THEN 8 ELSE 0 END)
    + (CASE WHEN seniorite_id <> 0 THEN 5 ELSE 0 END)
    + (CASE WHEN niveau_diplome_id <> 0 THEN 5 ELSE 0 END)
    + (CASE WHEN experience_connue THEN 5 ELSE 0 END)
    + (CASE WHEN salaire_connu AND devise <> '' THEN 12 ELSE 0 END)
    + (CASE WHEN nb_technologies >= 1 THEN 10 ELSE 0 END)
    + (CASE WHEN nb_missions     >= 1 THEN 8  ELSE 0 END)
    + (CASE WHEN nb_competences  >= 1 THEN 7  ELSE 0 END)
    + (CASE WHEN length(description_brute) >= 400 THEN 5 ELSE 0 END)
    + (CASE WHEN date_publication_id <> 19000101 THEN 5 ELSE 0 END)
);

-- 3d. content_hash : poste + société + ville (lower / sans bruit) → sha1 16hex
UPDATE analytics.fact_offer f SET content_hash = LEFT(
    md5(
        regexp_replace(LOWER(unaccent(COALESCE(f.poste, ''))), '\W+', '', 'g') || '|' ||
        regexp_replace(LOWER(unaccent(COALESCE(soc.societe_nom, ''))), '\W+', '', 'g') || '|' ||
        regexp_replace(LOWER(unaccent(COALESCE(v.ville_nom, ''))), '\W+', '', 'g')
    ), 16
)
FROM analytics.dim_societe soc, analytics.dim_ville v
WHERE soc.societe_id = f.societe_id
  AND v.ville_id     = f.ville_id;

-- -------------------------------------------------------------------------
-- 4. dim_technologie : populate categorie pour les techs déjà présentes
-- -------------------------------------------------------------------------
UPDATE analytics.dim_technologie SET categorie = CASE
    WHEN tech_nom IN ('Python','Java','Scala','R','C','C++','C#','.NET','JavaScript','TypeScript','Go','Kotlin','Swift','PHP','Ruby','Rust','PowerShell','Bash','Shell','PL/SQL','VBA','MATLAB') THEN 'Programmation'
    WHEN tech_nom IN ('Hadoop','Spark','Kafka','Hive','HBase','Flink','Storm','Databricks','Snowflake','Redshift','BigQuery','Teradata','Synapse','Delta Lake') THEN 'Big Data'
    WHEN tech_nom IN ('MySQL','PostgreSQL','Oracle','MongoDB','Cassandra','Redis','Elasticsearch','SQL Server','MariaDB','Neo4j','DynamoDB','SQLite','Couchbase') THEN 'Bases de données'
    WHEN tech_nom IN ('AWS','Azure','GCP','OpenStack','Heroku','Cloudflare','Vercel','DigitalOcean') THEN 'Cloud'
    WHEN tech_nom IN ('Docker','Kubernetes','Terraform','Ansible','Jenkins','GitLab','GitHub Actions','CircleCI','Helm','ArgoCD','Prometheus','Grafana','ELK','CI/CD','Nginx','Apache','VMware','Hyper-V') THEN 'DevOps/Infra'
    WHEN tech_nom IN ('TensorFlow','PyTorch','Scikit-Learn','Keras','Pandas','NumPy','XGBoost','LightGBM','Hugging Face','MLflow','MLOps','Machine Learning','Deep Learning','Computer Vision','NLP','GPT','LLM','Rasa','Dialogflow') THEN 'Data Science / ML'
    WHEN tech_nom IN ('Power BI','Tableau','QlikView','Qlik Sense','Looker','SAP BO','Cognos','Matplotlib','Seaborn','Plotly','Superset') THEN 'BI / Visualisation'
    WHEN tech_nom IN ('Airflow','Talend','Informatica','Collibra','ETL','ELT','DBT','NiFi','Data Vault','MDM','Fivetran') THEN 'Data Engineering'
    WHEN tech_nom IN ('SIEM','SOC','Splunk','Qualys','Nessus','Wireshark','Burp Suite','OWASP','ISO 27001','Pentesting','PKI','IAM','Active Directory','Azure AD') THEN 'Sécurité'
    WHEN tech_nom IN ('Linux','Unix','Windows','TCP/IP','DNS','SAN','NAS','VPN','Cisco','Juniper','Fortinet','Palo Alto') THEN 'Réseau / Système'
    WHEN tech_nom IN ('React','Angular','Vue','Vue.js','Next.js','Nuxt','Svelte','HTML','CSS','Tailwind','Bootstrap','jQuery','Redux') THEN 'Web / Frontend'
    WHEN tech_nom IN ('Django','Flask','FastAPI','Spring','Spring Boot','Express','NestJS','Node.js','Laravel','Symfony','Rails','.NET Core') THEN 'Backend / Frameworks'
    WHEN tech_nom IN ('Android','iOS','Flutter','React Native','Xamarin','Ionic') THEN 'Mobile'
    WHEN tech_nom IN ('Git','Jira','Confluence','SAP','Salesforce','ServiceNow','Notion','Postman','Figma') THEN 'Outils'
    WHEN tech_nom IN ('Agile','Scrum','Kanban','TDD','BDD','DevSecOps') THEN 'Méthodologies'
    WHEN tech_nom IN ('SQL','NoSQL') THEN 'SQL & autres'
    ELSE 'Autre'
END
WHERE categorie = 'Autre' OR categorie IS NULL;

-- -------------------------------------------------------------------------
-- 5. CHECK constraints additionnels (idempotent)
-- -------------------------------------------------------------------------
DO $$
DECLARE c text;
BEGIN
    FOREACH c IN ARRAY ARRAY[
        'chk_fact_offer_quality_score','chk_fact_offer_lat','chk_fact_offer_lon',
        'chk_fact_offer_salaire_eur_borne','chk_fact_offer_salaire_mad_borne'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = c) THEN
            EXECUTE format('ALTER TABLE analytics.fact_offer DROP CONSTRAINT %I', c);
        END IF;
    END LOOP;
END $$;

ALTER TABLE analytics.fact_offer
    ADD CONSTRAINT chk_fact_offer_quality_score CHECK (quality_score BETWEEN 0 AND 100),
    ADD CONSTRAINT chk_fact_offer_lat CHECK (latitude  IS NULL OR latitude  BETWEEN -90 AND 90),
    ADD CONSTRAINT chk_fact_offer_lon CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    ADD CONSTRAINT chk_fact_offer_salaire_eur_borne CHECK (salaire_max_mensuel_eur >= salaire_min_mensuel_eur),
    ADD CONSTRAINT chk_fact_offer_salaire_mad_borne CHECK (salaire_max_mensuel_mad >= salaire_min_mensuel_mad);

-- -------------------------------------------------------------------------
-- 6. Index pour recommandation / recherche
-- -------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fact_offer_metier  ON analytics.fact_offer(metier_id);
CREATE INDEX IF NOT EXISTS idx_fact_offer_hash    ON analytics.fact_offer(content_hash) WHERE content_hash <> '';
CREATE INDEX IF NOT EXISTS idx_fact_offer_quality ON analytics.fact_offer(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_fact_offer_search  ON analytics.fact_offer USING gin(search_doc);
CREATE INDEX IF NOT EXISTS idx_fact_offer_geo     ON analytics.fact_offer(latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- -------------------------------------------------------------------------
-- 7. Triggers FTS + duplicate refresh + vue recommandation
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION analytics.fact_offer_build_tsv()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_doc :=
        setweight(to_tsvector('french', COALESCE(NEW.poste, '')), 'A') ||
        setweight(to_tsvector('french', COALESCE(NEW.titre_original, '')), 'A') ||
        setweight(to_tsvector('simple', array_to_string(NEW.competences, ' ')), 'B') ||
        setweight(to_tsvector('simple', array_to_string(NEW.missions, ' ')), 'C') ||
        setweight(to_tsvector('french', COALESCE(LEFT(NEW.description_brute, 8000), '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_fact_offer_build_tsv ON analytics.fact_offer;
CREATE TRIGGER trg_fact_offer_build_tsv
BEFORE INSERT OR UPDATE OF poste, titre_original, competences, missions, description_brute
ON analytics.fact_offer
FOR EACH ROW EXECUTE FUNCTION analytics.fact_offer_build_tsv();

-- Recompute search_doc pour les lignes existantes (touche poste -> trigger).
UPDATE analytics.fact_offer SET poste = poste;

CREATE OR REPLACE FUNCTION analytics.refresh_duplicates() RETURNS void AS $$
BEGIN
    UPDATE analytics.fact_offer SET is_duplicate = FALSE WHERE is_duplicate;
    WITH dups AS (
        SELECT offer_id,
               ROW_NUMBER() OVER (PARTITION BY content_hash ORDER BY quality_score DESC, offer_id) AS rn
        FROM analytics.fact_offer
        WHERE content_hash <> ''
    )
    UPDATE analytics.fact_offer f
    SET is_duplicate = TRUE
    FROM dups
    WHERE f.offer_id = dups.offer_id AND dups.rn > 1;
END;
$$ LANGUAGE plpgsql;

SELECT analytics.refresh_duplicates();

-- -------------------------------------------------------------------------
-- 8. Vue de recommandation
-- -------------------------------------------------------------------------
DROP VIEW IF EXISTS analytics.v_offer_recommandation;
CREATE VIEW analytics.v_offer_recommandation AS
SELECT
    f.offer_id,
    f.content_hash,
    f.is_duplicate,
    f.quality_score,
    s.source_code,
    p.pays_nom,
    v.ville_nom,
    soc.societe_nom,
    f.poste,
    m.metier_code,
    m.metier_libelle,
    c.contrat_libelle,
    sen.seniorite_libelle,
    nd.niveau_libelle              AS niveau_diplome,
    t.teletravail_libelle,
    f.experience_min_annees, f.experience_max_annees,
    f.salaire_min, f.salaire_max, f.devise,
    f.salaire_min_mensuel_eur, f.salaire_max_mensuel_eur,
    f.salaire_min_mensuel_mad, f.salaire_max_mensuel_mad,
    f.latitude, f.longitude,
    f.competences,
    f.langues,
    dp.date_jour                   AS date_publication,
    f.url
FROM analytics.fact_offer f
JOIN analytics.dim_source         s   ON s.source_id      = f.source_id
JOIN analytics.dim_pays           p   ON p.pays_id        = f.pays_id
JOIN analytics.dim_ville          v   ON v.ville_id       = f.ville_id
JOIN analytics.dim_societe        soc ON soc.societe_id   = f.societe_id
JOIN analytics.dim_metier         m   ON m.metier_id      = f.metier_id
JOIN analytics.dim_contrat        c   ON c.contrat_id     = f.contrat_id
JOIN analytics.dim_seniorite      sen ON sen.seniorite_id = f.seniorite_id
JOIN analytics.dim_niveau_diplome nd  ON nd.niveau_id     = f.niveau_diplome_id
JOIN analytics.dim_teletravail    t   ON t.teletravail_id = f.teletravail_id
JOIN analytics.dim_date           dp  ON dp.date_id       = f.date_publication_id
WHERE NOT f.is_duplicate;

GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO datauser;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA analytics TO datauser;

COMMIT;

-- -------------------------------------------------------------------------
-- Vérifications post-migration
-- -------------------------------------------------------------------------
SELECT 'metiers'           AS metric, COUNT(*)::text   FROM analytics.dim_metier
UNION ALL SELECT 'fact_offer rows',     COUNT(*)::text FROM analytics.fact_offer
UNION ALL SELECT 'fact_offer doublons', COUNT(*)::text FROM analytics.fact_offer WHERE is_duplicate
UNION ALL SELECT 'fact_offer FTS ok',   COUNT(*)::text FROM analytics.fact_offer WHERE search_doc IS NOT NULL
UNION ALL SELECT 'fact_offer geo ok',   COUNT(*)::text FROM analytics.fact_offer WHERE latitude IS NOT NULL
UNION ALL SELECT 'tech catégorisées',   COUNT(*)::text FROM analytics.dim_technologie WHERE categorie <> 'Autre';

SELECT m.metier_code, m.metier_libelle, COUNT(*) AS nb
FROM analytics.fact_offer f
JOIN analytics.dim_metier m ON m.metier_id = f.metier_id
GROUP BY m.metier_code, m.metier_libelle, m.ordre
ORDER BY m.ordre;
