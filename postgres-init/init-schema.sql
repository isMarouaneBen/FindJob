-- =========================================================================
--  Postgres init — POSTGRES_DB=job_db
--  Schéma star SIMPLE (Kimball) dans `analytics`.
--    - 1 fact_offer (mesures + arrays TEXT[] pour langues/missions/compétences)
--    - 9 dimensions (dim_source, dim_pays, dim_ville, dim_societe,
--                    dim_contrat, dim_teletravail, dim_seniorite,
--                    dim_niveau_diplome, dim_technologie, dim_date)
--    - 1 bridge unique : bridge_offer_technologie  (compter les offres / techno)
--  Centralisation FR (Adzuna) + MA (Rekrute, Emploi-Public) dans la même base.
-- =========================================================================

CREATE USER airflow WITH PASSWORD 'airflow';
CREATE DATABASE airflow OWNER airflow;
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;

\connect job_db

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "unaccent";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

CREATE SCHEMA IF NOT EXISTS analytics;
GRANT ALL PRIVILEGES ON SCHEMA analytics TO datauser;

SET search_path TO analytics, public;

-- =========================================================================
--  DIMENSIONS  (toutes ont une ligne sentinel id=0 "Non spécifié")
-- =========================================================================

CREATE TABLE analytics.dim_source (
    source_id   SMALLINT PRIMARY KEY,
    source_code VARCHAR(32)  NOT NULL UNIQUE,
    source_nom  VARCHAR(128) NOT NULL,
    source_pays VARCHAR(32)  NOT NULL DEFAULT 'Non spécifié'
);
INSERT INTO analytics.dim_source VALUES
    (0, 'unknown',       'Non spécifié',     'Non spécifié'),
    (1, 'emploi_public', 'Emploi-Public.ma', 'Maroc'),
    (2, 'rekrute',       'ReKrute.com',      'Maroc'),
    (3, 'adzuna',        'Adzuna',           'France');

CREATE TABLE analytics.dim_pays (
    pays_id  SMALLSERIAL PRIMARY KEY,
    pays_nom VARCHAR(64) NOT NULL UNIQUE
);
INSERT INTO analytics.dim_pays (pays_id, pays_nom) OVERRIDING SYSTEM VALUE VALUES
    (0, 'Non spécifié'),
    (1, 'Maroc'),
    (2, 'France');
SELECT setval('analytics.dim_pays_pays_id_seq', 100, false);

CREATE TABLE analytics.dim_ville (
    ville_id  SERIAL PRIMARY KEY,
    ville_nom VARCHAR(160) NOT NULL,
    pays_id   SMALLINT NOT NULL DEFAULT 0 REFERENCES analytics.dim_pays(pays_id),
    UNIQUE (ville_nom, pays_id)
);
INSERT INTO analytics.dim_ville (ville_id, ville_nom, pays_id) OVERRIDING SYSTEM VALUE VALUES
    (0, 'Non spécifié', 0);
SELECT setval('analytics.dim_ville_ville_id_seq', 100, false);

CREATE TABLE analytics.dim_societe (
    societe_id   SERIAL PRIMARY KEY,
    societe_nom  VARCHAR(300) NOT NULL UNIQUE
);
INSERT INTO analytics.dim_societe (societe_id, societe_nom) OVERRIDING SYSTEM VALUE VALUES
    (0, 'Non spécifié');
SELECT setval('analytics.dim_societe_societe_id_seq', 100, false);
CREATE INDEX idx_dim_societe_trgm ON analytics.dim_societe USING gin (societe_nom gin_trgm_ops);

CREATE TABLE analytics.dim_contrat (
    contrat_id      SMALLSERIAL PRIMARY KEY,
    contrat_code    VARCHAR(32) NOT NULL UNIQUE,
    contrat_libelle VARCHAR(64) NOT NULL
);
INSERT INTO analytics.dim_contrat (contrat_id, contrat_code, contrat_libelle) OVERRIDING SYSTEM VALUE VALUES
    (0, 'unknown',    'Non spécifié'),
    (1, 'CDI',        'CDI'),
    (2, 'CDD',        'CDD'),
    (3, 'Stage',      'Stage'),
    (4, 'Alternance', 'Alternance'),
    (5, 'Freelance',  'Freelance'),
    (6, 'Interim',    'Intérim');
SELECT setval('analytics.dim_contrat_contrat_id_seq', 100, false);

CREATE TABLE analytics.dim_teletravail (
    teletravail_id      SMALLSERIAL PRIMARY KEY,
    teletravail_code    VARCHAR(32) NOT NULL UNIQUE,
    teletravail_libelle VARCHAR(64) NOT NULL
);
INSERT INTO analytics.dim_teletravail (teletravail_id, teletravail_code, teletravail_libelle) OVERRIDING SYSTEM VALUE VALUES
    (0, 'unknown',  'Non spécifié'),
    (1, 'Non',      'Non'),
    (2, 'Hybride',  'Hybride'),
    (3, 'Total',    '100% remote'),
    (4, 'Possible', 'Possible / Occasionnel');
SELECT setval('analytics.dim_teletravail_teletravail_id_seq', 100, false);

CREATE TABLE analytics.dim_seniorite (
    seniorite_id      SMALLSERIAL PRIMARY KEY,
    seniorite_code    VARCHAR(32) NOT NULL UNIQUE,
    seniorite_libelle VARCHAR(64) NOT NULL,
    ordre             SMALLINT NOT NULL DEFAULT 0
);
INSERT INTO analytics.dim_seniorite (seniorite_id, seniorite_code, seniorite_libelle, ordre) OVERRIDING SYSTEM VALUE VALUES
    (0, 'unknown',       'Non spécifié',  0),
    (1, 'Stage',         'Stage',         10),
    (2, 'Alternance',    'Alternance',    20),
    (3, 'Junior',        'Junior',        30),
    (4, 'Intermediaire', 'Intermédiaire', 40),
    (5, 'Confirme',      'Confirmé',      50),
    (6, 'Senior',        'Senior',        60),
    (7, 'Expert',        'Expert / Lead', 70);
SELECT setval('analytics.dim_seniorite_seniorite_id_seq', 100, false);

CREATE TABLE analytics.dim_niveau_diplome (
    niveau_id      SMALLSERIAL PRIMARY KEY,
    niveau_code    VARCHAR(32) NOT NULL UNIQUE,
    niveau_libelle VARCHAR(64) NOT NULL,
    niveau_ordre   SMALLINT NOT NULL DEFAULT 0
);
INSERT INTO analytics.dim_niveau_diplome (niveau_id, niveau_code, niveau_libelle, niveau_ordre) OVERRIDING SYSTEM VALUE VALUES
    (0, 'unknown',  'Non spécifié',              0),
    (1, 'Bac',      'Baccalauréat',             10),
    (2, 'Bac+2',    'Bac+2 (BTS/DUT)',          20),
    (3, 'Bac+3',    'Bac+3 (Licence)',          30),
    (4, 'Bac+4',    'Bac+4',                    40),
    (5, 'Bac+5',    'Bac+5 (Master/Ingénieur)', 50),
    (6, 'Doctorat', 'Doctorat',                 60);
SELECT setval('analytics.dim_niveau_diplome_niveau_id_seq', 100, false);

CREATE TABLE analytics.dim_technologie (
    tech_id   SERIAL PRIMARY KEY,
    tech_nom  VARCHAR(64) NOT NULL UNIQUE,
    categorie VARCHAR(32) NOT NULL DEFAULT 'Autre'
);
INSERT INTO analytics.dim_technologie (tech_id, tech_nom, categorie) OVERRIDING SYSTEM VALUE VALUES
    (0, 'Non spécifié', 'Autre');
SELECT setval('analytics.dim_technologie_tech_id_seq', 100, false);

-- -------------------------------------------------------------------------
--  dim_date : 2020-01-01 .. 2030-12-31 + sentinels 1900-01-01 / 9999-12-31
-- -------------------------------------------------------------------------
CREATE TABLE analytics.dim_date (
    date_id      INTEGER PRIMARY KEY,        -- YYYYMMDD
    date_jour    DATE     NOT NULL UNIQUE,
    annee        SMALLINT NOT NULL,
    trimestre    SMALLINT NOT NULL,
    mois         SMALLINT NOT NULL,
    mois_nom     VARCHAR(16) NOT NULL,
    jour         SMALLINT NOT NULL,
    jour_semaine SMALLINT NOT NULL,
    jour_nom     VARCHAR(16) NOT NULL,
    semaine_iso  SMALLINT NOT NULL,
    est_weekend  BOOLEAN  NOT NULL,
    est_sentinel BOOLEAN  NOT NULL DEFAULT FALSE
);

INSERT INTO analytics.dim_date
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT,
    d::DATE,
    EXTRACT(YEAR FROM d)::SMALLINT,
    EXTRACT(QUARTER FROM d)::SMALLINT,
    EXTRACT(MONTH FROM d)::SMALLINT,
    TRIM(TO_CHAR(d, 'TMMonth')),
    EXTRACT(DAY FROM d)::SMALLINT,
    EXTRACT(ISODOW FROM d)::SMALLINT,
    TRIM(TO_CHAR(d, 'TMDay')),
    EXTRACT(WEEK FROM d)::SMALLINT,
    EXTRACT(ISODOW FROM d) IN (6,7),
    FALSE
FROM generate_series('2020-01-01'::DATE, '2030-12-31'::DATE, '1 day') d;

INSERT INTO analytics.dim_date VALUES
    (19000101, '1900-01-01'::DATE, 1900, 1,  1, 'Inconnu',  1, 1, 'Inconnu',  1, FALSE, TRUE),
    (99991231, '9999-12-31'::DATE, 9999, 4, 12, 'Inconnu', 31, 5, 'Inconnu', 52, FALSE, TRUE);

-- =========================================================================
--  FACT TABLE — grain = une annonce unique (source_id, source_ref)
-- =========================================================================
CREATE TABLE analytics.fact_offer (
    offer_id              BIGSERIAL PRIMARY KEY,

    -- Clés métier
    source_id             SMALLINT     NOT NULL REFERENCES analytics.dim_source(source_id),
    source_ref            VARCHAR(64)  NOT NULL,
    external_id           VARCHAR(64)  NOT NULL DEFAULT '',

    -- Dimensions (NOT NULL, sentinels id=0 / dates 19000101 / 99991231)
    societe_id            INTEGER  NOT NULL DEFAULT 0 REFERENCES analytics.dim_societe(societe_id),
    ville_id              INTEGER  NOT NULL DEFAULT 0 REFERENCES analytics.dim_ville(ville_id),
    pays_id               SMALLINT NOT NULL DEFAULT 0 REFERENCES analytics.dim_pays(pays_id),
    contrat_id            SMALLINT NOT NULL DEFAULT 0 REFERENCES analytics.dim_contrat(contrat_id),
    teletravail_id        SMALLINT NOT NULL DEFAULT 0 REFERENCES analytics.dim_teletravail(teletravail_id),
    seniorite_id          SMALLINT NOT NULL DEFAULT 0 REFERENCES analytics.dim_seniorite(seniorite_id),
    niveau_diplome_id     SMALLINT NOT NULL DEFAULT 0 REFERENCES analytics.dim_niveau_diplome(niveau_id),

    date_publication_id   INTEGER  NOT NULL DEFAULT 19000101 REFERENCES analytics.dim_date(date_id),
    date_limite_id        INTEGER  NOT NULL DEFAULT 99991231 REFERENCES analytics.dim_date(date_id),
    date_scraping_id      INTEGER  NOT NULL DEFAULT 19000101 REFERENCES analytics.dim_date(date_id),

    -- Attributs descriptifs
    poste                 VARCHAR(300)  NOT NULL,
    titre_original        VARCHAR(600)  NOT NULL DEFAULT '',
    url                   VARCHAR(1000) NOT NULL,
    statut                VARCHAR(20)   NOT NULL DEFAULT 'actif',

    -- Mesures
    nb_postes             SMALLINT      NOT NULL DEFAULT 1,
    experience_min_annees SMALLINT      NOT NULL DEFAULT 0,
    experience_max_annees SMALLINT      NOT NULL DEFAULT 0,
    experience_connue     BOOLEAN       NOT NULL DEFAULT FALSE,
    age_max               SMALLINT      NOT NULL DEFAULT 0,
    age_max_connu         BOOLEAN       NOT NULL DEFAULT FALSE,
    salaire_min           NUMERIC(12,2) NOT NULL DEFAULT 0,
    salaire_max           NUMERIC(12,2) NOT NULL DEFAULT 0,
    salaire_connu         BOOLEAN       NOT NULL DEFAULT FALSE,
    devise                CHAR(3)       NOT NULL DEFAULT '',

    -- Multi-valeurs (arrays Postgres natifs)
    langues               TEXT[]        NOT NULL DEFAULT '{}',
    missions              TEXT[]        NOT NULL DEFAULT '{}',
    competences           TEXT[]        NOT NULL DEFAULT '{}',
    diplome_types         TEXT[]        NOT NULL DEFAULT '{}',
    emails_contact        TEXT[]        NOT NULL DEFAULT '{}',
    urls_postulation      TEXT[]        NOT NULL DEFAULT '{}',

    -- Compteurs pré-agrégés (pour Power BI)
    nb_technologies       SMALLINT NOT NULL DEFAULT 0,
    nb_missions           SMALLINT NOT NULL DEFAULT 0,
    nb_competences        SMALLINT NOT NULL DEFAULT 0,
    nb_langues            SMALLINT NOT NULL DEFAULT 0,

    description_brute     TEXT     NOT NULL DEFAULT '',

    inserted_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source_id, source_ref)
);

CREATE INDEX idx_fact_offer_societe     ON analytics.fact_offer(societe_id);
CREATE INDEX idx_fact_offer_ville       ON analytics.fact_offer(ville_id);
CREATE INDEX idx_fact_offer_pays        ON analytics.fact_offer(pays_id);
CREATE INDEX idx_fact_offer_date_pub    ON analytics.fact_offer(date_publication_id);
CREATE INDEX idx_fact_offer_contrat     ON analytics.fact_offer(contrat_id);
CREATE INDEX idx_fact_offer_seniorite   ON analytics.fact_offer(seniorite_id);

-- =========================================================================
--  BRIDGE — seul lien many-to-many conservé : offre <-> technologie
--  But : SELECT tech_nom, COUNT(*) ... GROUP BY tech_nom ORDER BY 2 DESC
-- =========================================================================
CREATE TABLE analytics.bridge_offer_technologie (
    offer_id BIGINT  NOT NULL REFERENCES analytics.fact_offer(offer_id) ON DELETE CASCADE,
    tech_id  INTEGER NOT NULL REFERENCES analytics.dim_technologie(tech_id),
    PRIMARY KEY (offer_id, tech_id)
);
CREATE INDEX idx_bridge_tech_tech ON analytics.bridge_offer_technologie(tech_id);

-- =========================================================================
--  VUES ANALYTIQUES
-- =========================================================================
CREATE OR REPLACE VIEW analytics.v_offer_flat AS
SELECT
    f.offer_id,
    s.source_code,
    s.source_pays,
    f.poste,
    f.titre_original,
    soc.societe_nom,
    v.ville_nom,
    p.pays_nom,
    c.contrat_libelle,
    t.teletravail_libelle,
    sen.seniorite_libelle,
    nd.niveau_libelle              AS niveau_diplome,
    dp.date_jour                   AS date_publication,
    dl.date_jour                   AS date_limite,
    ds.date_jour                   AS date_scraping,
    f.nb_postes,
    f.experience_min_annees, f.experience_max_annees,
    f.salaire_min, f.salaire_max, f.devise, f.salaire_connu,
    f.nb_technologies, f.nb_missions, f.nb_competences, f.nb_langues,
    f.url, f.statut
FROM analytics.fact_offer f
JOIN analytics.dim_source         s   ON s.source_id      = f.source_id
JOIN analytics.dim_societe        soc ON soc.societe_id   = f.societe_id
JOIN analytics.dim_ville          v   ON v.ville_id       = f.ville_id
JOIN analytics.dim_pays           p   ON p.pays_id        = f.pays_id
JOIN analytics.dim_contrat        c   ON c.contrat_id     = f.contrat_id
JOIN analytics.dim_teletravail    t   ON t.teletravail_id = f.teletravail_id
JOIN analytics.dim_seniorite      sen ON sen.seniorite_id = f.seniorite_id
JOIN analytics.dim_niveau_diplome nd  ON nd.niveau_id     = f.niveau_diplome_id
JOIN analytics.dim_date           dp  ON dp.date_id       = f.date_publication_id
JOIN analytics.dim_date           dl  ON dl.date_id       = f.date_limite_id
JOIN analytics.dim_date           ds  ON ds.date_id       = f.date_scraping_id;

-- Top technologies (pour Power BI)
CREATE OR REPLACE VIEW analytics.v_tech_demand AS
SELECT
    dt.tech_nom,
    dt.categorie,
    COUNT(*) AS nb_offres,
    s.source_pays
FROM analytics.bridge_offer_technologie b
JOIN analytics.dim_technologie dt ON dt.tech_id   = b.tech_id
JOIN analytics.fact_offer       f ON f.offer_id   = b.offer_id
JOIN analytics.dim_source       s ON s.source_id  = f.source_id
GROUP BY dt.tech_nom, dt.categorie, s.source_pays
ORDER BY nb_offres DESC;

GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO datauser;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA analytics TO datauser;
