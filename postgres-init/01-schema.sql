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

-- CREATE USER airflow WITH PASSWORD 'airflow';
-- CREATE DATABASE airflow OWNER airflow;
-- GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;

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
    UNIQUE (ville_nom, pays_id),
    -- Empêche les pays / régions / départements français de se retrouver
    -- comme villes (cause principale de "France" dans dim_ville).
    CONSTRAINT chk_dim_ville_not_country_or_region CHECK (
        ville_id = 0 OR LOWER(unaccent(ville_nom)) NOT IN (
            'france','maroc','morocco','algerie','tunisie','espagne','spain',
            'belgique','suisse','luxembourg','allemagne','italie','portugal',
            -- 13 régions FR
            'auvergne-rhone-alpes','bourgogne-franche-comte','bretagne',
            'centre-val de loire','corse','grand est','hauts-de-france',
            'ile-de-france','normandie','nouvelle-aquitaine','occitanie',
            'pays de la loire','provence-alpes-cote d''azur','paca',
            -- Départements FR (sauf Paris qui est aussi une ville)
            'ain','aisne','allier','aube','aude','aveyron','calvados','cantal',
            'charente','cher','correze','creuse','dordogne','doubs','drome',
            'eure','finistere','gard','gironde','herault','indre','isere',
            'jura','landes','loire','loiret','lot','lozere','manche','marne',
            'mayenne','meuse','morbihan','moselle','nievre','nord','oise',
            'orne','puy-de-dome','rhone','sarthe','savoie','somme','tarn',
            'var','vaucluse','vendee','vienne','vosges','yonne','yvelines',
            'essonne','hauts-de-seine','seine-saint-denis','val-de-marne',
            'val-d''oise','seine-maritime','seine-et-marne','haute-garonne',
            'haute-loire','haute-marne','haute-saone','haute-savoie',
            'haute-vienne','hautes-alpes','hautes-pyrenees','alpes-maritimes',
            'alpes-de-haute-provence','ardennes','ardeche','ariege',
            'bouches-du-rhone','charente-maritime','cote-d''or','cotes-d''armor',
            'deux-sevres','eure-et-loir','ille-et-vilaine','indre-et-loire',
            'lot-et-garonne','loire-atlantique','loir-et-cher','maine-et-loire',
            'meurthe-et-moselle','pas-de-calais','pyrenees-atlantiques',
            'pyrenees-orientales','bas-rhin','haut-rhin','saone-et-loire',
            'tarn-et-garonne','territoire de belfort','corse-du-sud','haute-corse'
        )
    )
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
--  dim_metier : famille de poste (Data, Cloud, Dev, ...) pour groupement
--  analytique et système de recommandation.
-- -------------------------------------------------------------------------
CREATE TABLE analytics.dim_metier (
    metier_id      SMALLSERIAL PRIMARY KEY,
    metier_code    VARCHAR(16) NOT NULL UNIQUE,
    metier_libelle VARCHAR(64) NOT NULL,
    ordre          SMALLINT NOT NULL DEFAULT 0
);
INSERT INTO analytics.dim_metier (metier_id, metier_code, metier_libelle, ordre) OVERRIDING SYSTEM VALUE VALUES
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
    (16, 'CONSULT',    'Consultant',              160);
SELECT setval('analytics.dim_metier_metier_id_seq', 100, false);

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

    -- ---------------------------------------------------------------------
    --  Enrichissement : recommandation, recherche, scoring
    -- ---------------------------------------------------------------------
    metier_id                 SMALLINT      NOT NULL DEFAULT 0 REFERENCES analytics.dim_metier(metier_id),
    salaire_min_mensuel_eur   INTEGER       NOT NULL DEFAULT 0,
    salaire_max_mensuel_eur   INTEGER       NOT NULL DEFAULT 0,
    salaire_min_mensuel_mad   INTEGER       NOT NULL DEFAULT 0,
    salaire_max_mensuel_mad   INTEGER       NOT NULL DEFAULT 0,
    latitude                  NUMERIC(9,6),
    longitude                 NUMERIC(9,6),
    quality_score             SMALLINT      NOT NULL DEFAULT 0,
    content_hash              CHAR(16)      NOT NULL DEFAULT '',
    is_duplicate              BOOLEAN       NOT NULL DEFAULT FALSE,
    -- tsvector calculé par trigger : poste + titre + description + competences + technologies
    search_doc                TSVECTOR,

    inserted_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (source_id, source_ref),

    -- ---------------------------------------------------------------------
    -- Contraintes métier
    -- ---------------------------------------------------------------------
    CONSTRAINT chk_fact_offer_devise CHECK (devise IN ('','MAD','EUR','USD','GBP')),
    CONSTRAINT chk_fact_offer_devise_si_salaire CHECK (
        NOT salaire_connu OR devise <> ''
    ),
    CONSTRAINT chk_fact_offer_salaire_positif CHECK (
        salaire_min >= 0 AND salaire_max >= 0
    ),
    CONSTRAINT chk_fact_offer_salaire_borne CHECK (
        salaire_max >= salaire_min
    ),
    CONSTRAINT chk_fact_offer_experience CHECK (
        experience_min_annees >= 0
        AND experience_max_annees >= experience_min_annees
        AND experience_max_annees <= 50
    ),
    CONSTRAINT chk_fact_offer_age CHECK (
        age_max = 0 OR (age_max BETWEEN 16 AND 99)
    ),
    CONSTRAINT chk_fact_offer_nb_postes CHECK (nb_postes >= 1),
    CONSTRAINT chk_fact_offer_statut CHECK (statut IN ('actif','expire','retire','inconnu')),
    CONSTRAINT chk_fact_offer_quality_score CHECK (quality_score BETWEEN 0 AND 100),
    CONSTRAINT chk_fact_offer_lat CHECK (latitude  IS NULL OR latitude  BETWEEN -90 AND 90),
    CONSTRAINT chk_fact_offer_lon CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CONSTRAINT chk_fact_offer_salaire_eur_borne CHECK (salaire_max_mensuel_eur >= salaire_min_mensuel_eur),
    CONSTRAINT chk_fact_offer_salaire_mad_borne CHECK (salaire_max_mensuel_mad >= salaire_min_mensuel_mad)
);

CREATE INDEX idx_fact_offer_societe     ON analytics.fact_offer(societe_id);
CREATE INDEX idx_fact_offer_ville       ON analytics.fact_offer(ville_id);
CREATE INDEX idx_fact_offer_pays        ON analytics.fact_offer(pays_id);
CREATE INDEX idx_fact_offer_date_pub    ON analytics.fact_offer(date_publication_id);
CREATE INDEX idx_fact_offer_contrat     ON analytics.fact_offer(contrat_id);
CREATE INDEX idx_fact_offer_seniorite   ON analytics.fact_offer(seniorite_id);
CREATE INDEX idx_fact_offer_metier      ON analytics.fact_offer(metier_id);
CREATE INDEX idx_fact_offer_hash        ON analytics.fact_offer(content_hash) WHERE content_hash <> '';
CREATE INDEX idx_fact_offer_quality     ON analytics.fact_offer(quality_score DESC);
CREATE INDEX idx_fact_offer_search      ON analytics.fact_offer USING gin(search_doc);
CREATE INDEX idx_fact_offer_geo         ON analytics.fact_offer(latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

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

-- =========================================================================
--  Cohérence inter-dimensions : ville ↔ pays
--  Si une ville est rattachée à un pays X, toute offre référençant cette
--  ville doit avoir pays_id = X. On le garantit via un trigger BEFORE INSERT
--  / UPDATE qui aligne fact_offer.pays_id sur dim_ville.pays_id (sauf
--  sentinel ville_id=0 où on garde le pays demandé).
-- =========================================================================
CREATE OR REPLACE FUNCTION analytics.fact_offer_sync_pays()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ville_id <> 0 THEN
        SELECT pays_id INTO NEW.pays_id
        FROM analytics.dim_ville
        WHERE ville_id = NEW.ville_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_fact_offer_sync_pays
BEFORE INSERT OR UPDATE OF ville_id ON analytics.fact_offer
FOR EACH ROW EXECUTE FUNCTION analytics.fact_offer_sync_pays();

-- Devise par défaut imposée par source (au cas où l'ETL aurait laissé
-- passer une valeur vide ou hors liste).
CREATE OR REPLACE FUNCTION analytics.fact_offer_default_devise()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.salaire_connu AND (NEW.devise IS NULL OR NEW.devise = '') THEN
        NEW.devise := CASE NEW.source_id
            WHEN 1 THEN 'MAD'  -- emploi_public
            WHEN 2 THEN 'MAD'  -- rekrute
            WHEN 3 THEN 'EUR'  -- adzuna
            ELSE ''
        END;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_fact_offer_default_devise
BEFORE INSERT OR UPDATE OF devise, salaire_min, salaire_max ON analytics.fact_offer
FOR EACH ROW EXECUTE FUNCTION analytics.fact_offer_default_devise();

-- =========================================================================
--  Full-Text Search : indexe poste + titre + description + arrays multi-val
--  Sert à la recherche d'emploi par mots-clés ET au calcul de similarité
--  pour la recommandation (ts_rank + cosine via pg_trgm).
-- =========================================================================
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

CREATE TRIGGER trg_fact_offer_build_tsv
BEFORE INSERT OR UPDATE OF poste, titre_original, competences, missions, description_brute
ON analytics.fact_offer
FOR EACH ROW EXECUTE FUNCTION analytics.fact_offer_build_tsv();

-- =========================================================================
--  Marquage des doublons cross-source via content_hash.
--  La 1ère occurrence (id min) est gardée, les autres sont marquées.
-- =========================================================================
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

-- =========================================================================
--  Vue enrichie pour Power BI / API recommandation
-- =========================================================================
CREATE OR REPLACE VIEW analytics.v_offer_recommandation AS
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
    f.nb_technologies AS technologies_canoniques, --changed
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
