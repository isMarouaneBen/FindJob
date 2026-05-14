-- =========================================================================
--  MIGRATION : nettoyage de l'existant + ajout des contraintes métier.
--  Idempotent : peut être ré-exécuté sans dommage.
--
--  À lancer sur une base déjà peuplée (le fichier init-schema.sql ne
--  s'exécute que sur une base vide via docker-entrypoint-initdb.d).
--
--  Usage :
--      docker exec -i job_postgres \
--          psql -U datauser -d job_db < postgres-init/02-cleanup-and-constraints.sql
-- =========================================================================

\connect job_db
SET search_path TO analytics, public;
BEGIN;

-- -------------------------------------------------------------------------
-- 1. Ré-affecter toutes les offres pointant vers des "fausses villes"
--    (pays / régions / départements français) au sentinel ville_id=0.
-- -------------------------------------------------------------------------
WITH bad_villes AS (
    SELECT ville_id
    FROM analytics.dim_ville
    WHERE ville_id <> 0
      AND LOWER(unaccent(ville_nom)) IN (
        'france','maroc','morocco','algerie','tunisie','espagne','spain',
        'belgique','suisse','luxembourg','allemagne','italie','portugal',
        'auvergne-rhone-alpes','bourgogne-franche-comte','bretagne',
        'centre-val de loire','corse','grand est','hauts-de-france',
        'ile-de-france','normandie','nouvelle-aquitaine','occitanie',
        'pays de la loire','provence-alpes-cote d''azur','paca',
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
UPDATE analytics.fact_offer
SET ville_id = 0
WHERE ville_id IN (SELECT ville_id FROM bad_villes);

-- 1b. Ré-affecter les arrondissements parisiens à "Paris".
--     Crée Paris s'il n'existe pas (rare : devrait déjà exister).
INSERT INTO analytics.dim_ville (ville_nom, pays_id)
SELECT 'Paris', 2
WHERE NOT EXISTS (
    SELECT 1 FROM analytics.dim_ville WHERE ville_nom = 'Paris' AND pays_id = 2
);

WITH paris AS (
    SELECT ville_id FROM analytics.dim_ville WHERE ville_nom = 'Paris' AND pays_id = 2 LIMIT 1
),
arrondissements AS (
    SELECT ville_id FROM analytics.dim_ville
    WHERE pays_id = 2
      AND ville_nom ~* '^\s*\d{1,2}\s*(er|e|eme|ème|nd|nde)?[\s\-]+arrondissement'
)
UPDATE analytics.fact_offer
SET ville_id = (SELECT ville_id FROM paris)
WHERE ville_id IN (SELECT ville_id FROM arrondissements);

-- 1c. Supprimer les lignes désormais orphelines de dim_ville.
DELETE FROM analytics.dim_ville
WHERE ville_id <> 0
  AND ville_id NOT IN (SELECT DISTINCT ville_id FROM analytics.fact_offer);

-- -------------------------------------------------------------------------
-- 2. Devise : forcer la devise par source pour toutes les lignes existantes.
--    - Adzuna (3) → EUR
--    - Rekrute (2) / Emploi-public (1) → MAD
--    Vide pour les offres sans salaire connu.
-- -------------------------------------------------------------------------
UPDATE analytics.fact_offer
SET devise = ''
WHERE NOT salaire_connu;

UPDATE analytics.fact_offer
SET devise = 'EUR'
WHERE source_id = 3
  AND salaire_connu
  AND (devise IS NULL OR devise NOT IN ('EUR','MAD','USD','GBP'));

UPDATE analytics.fact_offer
SET devise = 'MAD'
WHERE source_id IN (1, 2)
  AND salaire_connu
  AND (devise IS NULL OR devise NOT IN ('EUR','MAD','USD','GBP'));

-- 2b. Adzuna avait l'estimation MAD comme fallback : on convertit ces
--     valeurs (MAD mensuel) en EUR annuel pour cohérence pays.
--     mensuel_MAD * 12 / 10.9 ≈ annuel_EUR.
UPDATE analytics.fact_offer
SET salaire_min = ROUND(salaire_min * 12.0 / 10.9, 2),
    salaire_max = ROUND(salaire_max * 12.0 / 10.9, 2),
    devise      = 'EUR'
WHERE source_id = 3
  AND devise = 'MAD'
  AND salaire_connu;

-- -------------------------------------------------------------------------
-- 3. Salaires : swap min↔max si incohérence, plafonner expérience.
-- -------------------------------------------------------------------------
UPDATE analytics.fact_offer
SET salaire_min = LEAST(salaire_min, salaire_max),
    salaire_max = GREATEST(salaire_min, salaire_max)
WHERE salaire_max < salaire_min;

UPDATE analytics.fact_offer
SET experience_max_annees = experience_min_annees
WHERE experience_max_annees < experience_min_annees;

UPDATE analytics.fact_offer
SET experience_max_annees = LEAST(experience_max_annees, 50),
    experience_min_annees = LEAST(experience_min_annees, 50);

UPDATE analytics.fact_offer
SET age_max = 0
WHERE age_max <> 0 AND (age_max < 16 OR age_max > 99);

UPDATE analytics.fact_offer
SET nb_postes = 1
WHERE nb_postes < 1;

UPDATE analytics.fact_offer
SET statut = 'actif'
WHERE statut NOT IN ('actif','expire','retire','inconnu');

-- -------------------------------------------------------------------------
-- 4. Cohérence pays/ville : aligner pays_id sur la ville (sauf sentinel).
-- -------------------------------------------------------------------------
UPDATE analytics.fact_offer f
SET pays_id = v.pays_id
FROM analytics.dim_ville v
WHERE v.ville_id = f.ville_id
  AND v.ville_id <> 0
  AND f.pays_id <> v.pays_id;

-- -------------------------------------------------------------------------
-- 5. Ajout des CHECK CONSTRAINTS (idempotent : on droppe d'abord)
-- -------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_dim_ville_not_country_or_region') THEN
        ALTER TABLE analytics.dim_ville DROP CONSTRAINT chk_dim_ville_not_country_or_region;
    END IF;
END $$;

ALTER TABLE analytics.dim_ville ADD CONSTRAINT chk_dim_ville_not_country_or_region CHECK (
    ville_id = 0 OR LOWER(unaccent(ville_nom)) NOT IN (
        'france','maroc','morocco','algerie','tunisie','espagne','spain',
        'belgique','suisse','luxembourg','allemagne','italie','portugal',
        'auvergne-rhone-alpes','bourgogne-franche-comte','bretagne',
        'centre-val de loire','corse','grand est','hauts-de-france',
        'ile-de-france','normandie','nouvelle-aquitaine','occitanie',
        'pays de la loire','provence-alpes-cote d''azur','paca',
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
);

DO $$
DECLARE
    cname text;
    cnames text[] := ARRAY[
        'chk_fact_offer_devise',
        'chk_fact_offer_devise_si_salaire',
        'chk_fact_offer_salaire_positif',
        'chk_fact_offer_salaire_borne',
        'chk_fact_offer_experience',
        'chk_fact_offer_age',
        'chk_fact_offer_nb_postes',
        'chk_fact_offer_statut'
    ];
BEGIN
    FOREACH cname IN ARRAY cnames LOOP
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = cname) THEN
            EXECUTE format('ALTER TABLE analytics.fact_offer DROP CONSTRAINT %I', cname);
        END IF;
    END LOOP;
END $$;

ALTER TABLE analytics.fact_offer
    ADD CONSTRAINT chk_fact_offer_devise CHECK (devise IN ('','MAD','EUR','USD','GBP')),
    ADD CONSTRAINT chk_fact_offer_devise_si_salaire CHECK (NOT salaire_connu OR devise <> ''),
    ADD CONSTRAINT chk_fact_offer_salaire_positif CHECK (salaire_min >= 0 AND salaire_max >= 0),
    ADD CONSTRAINT chk_fact_offer_salaire_borne   CHECK (salaire_max >= salaire_min),
    ADD CONSTRAINT chk_fact_offer_experience      CHECK (
        experience_min_annees >= 0
        AND experience_max_annees >= experience_min_annees
        AND experience_max_annees <= 50
    ),
    ADD CONSTRAINT chk_fact_offer_age              CHECK (age_max = 0 OR (age_max BETWEEN 16 AND 99)),
    ADD CONSTRAINT chk_fact_offer_nb_postes        CHECK (nb_postes >= 1),
    ADD CONSTRAINT chk_fact_offer_statut           CHECK (statut IN ('actif','expire','retire','inconnu'));

-- -------------------------------------------------------------------------
-- 6. Triggers (idempotent)
-- -------------------------------------------------------------------------
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

DROP TRIGGER IF EXISTS trg_fact_offer_sync_pays ON analytics.fact_offer;
CREATE TRIGGER trg_fact_offer_sync_pays
BEFORE INSERT OR UPDATE OF ville_id ON analytics.fact_offer
FOR EACH ROW EXECUTE FUNCTION analytics.fact_offer_sync_pays();

CREATE OR REPLACE FUNCTION analytics.fact_offer_default_devise()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.salaire_connu AND (NEW.devise IS NULL OR NEW.devise = '') THEN
        NEW.devise := CASE NEW.source_id
            WHEN 1 THEN 'MAD'
            WHEN 2 THEN 'MAD'
            WHEN 3 THEN 'EUR'
            ELSE ''
        END;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_fact_offer_default_devise ON analytics.fact_offer;
CREATE TRIGGER trg_fact_offer_default_devise
BEFORE INSERT OR UPDATE OF devise, salaire_min, salaire_max ON analytics.fact_offer
FOR EACH ROW EXECUTE FUNCTION analytics.fact_offer_default_devise();

COMMIT;

-- -------------------------------------------------------------------------
-- 7. Vérifications post-migration
-- -------------------------------------------------------------------------
SELECT 'dim_ville rows'              AS metric, COUNT(*)::text AS value FROM analytics.dim_ville
UNION ALL SELECT 'dim_ville polluees',
       COUNT(*)::text FROM analytics.dim_ville
       WHERE ville_id <> 0 AND LOWER(unaccent(ville_nom)) IN ('france','ile-de-france','hauts-de-seine','nord','rhone')
UNION ALL SELECT 'fact_offer rows',     COUNT(*)::text FROM analytics.fact_offer
UNION ALL SELECT 'fact_offer FR/EUR',   COUNT(*)::text FROM analytics.fact_offer WHERE source_id = 3 AND devise = 'EUR'
UNION ALL SELECT 'fact_offer FR/MAD',   COUNT(*)::text FROM analytics.fact_offer WHERE source_id = 3 AND devise = 'MAD'
UNION ALL SELECT 'fact_offer devise vide avec salaire', COUNT(*)::text FROM analytics.fact_offer WHERE devise = '' AND salaire_connu;
