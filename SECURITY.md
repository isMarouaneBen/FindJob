# Secrets & deployment

## ⚠️ Before pushing to GitHub for the first time

Your repository **already contains a tracked `.env`** (it was committed before
being added to `.gitignore`). You must untrack it and **rotate every secret
that was in it**, because git history is forever.

### 1. Remove `.env` from git tracking (keeps the local file)

```bash
git rm --cached .env
git rm --cached pass.txt 2>/dev/null || true
git commit -m "chore: stop tracking secrets, use .env.example template"
```

### 2. Rotate the previously committed credentials

Any secret that ever appeared in a git commit is **compromised** even if you
remove it from the latest version. Replace the following in their respective
providers, then update your local `.env`:

| Secret              | Where to rotate                                                |
|---------------------|----------------------------------------------------------------|
| `ADZUNA_API_KEY`    | https://developer.adzuna.com/admin                             |
| `GOOGLE_CLIENT_ID`  | https://console.cloud.google.com/apis/credentials — recreate the OAuth client and update both the backend `.env` and the frontend build |
| `JWT_SECRET`        | `openssl rand -hex 48`                                         |
| `ADMIN_TOKEN`       | `openssl rand -hex 24`                                         |
| Postgres password   | edit `POSTGRES_PASSWORD` then `docker compose down -v && up`   |
| Mongo / MinIO creds | same — `docker compose down -v` wipes the volumes              |

### 3. (Optional but recommended) Purge history

If you don't care about preserving git history, the cleanest is to start a
fresh repo. Otherwise, use [`git filter-repo`](https://github.com/newren/git-filter-repo)
to scrub `.env` from every past commit:

```bash
git filter-repo --invert-paths --path .env --path pass.txt
git push --force-with-lease origin main
```

## Local setup

```bash
cp .env.example .env                       # backend env
cp platform/frontend/.env.example platform/frontend/.env

# Edit both files with your secrets
docker compose up -d --build
```

## What's safe to commit

| File / pattern                            | Tracked? | Why |
|-------------------------------------------|----------|-----|
| `.env`, `.env.local`, `**/.env`           | **No**   | secrets |
| `.env.example`, `**/.env.example`         | Yes      | template only |
| `pass.txt`                                | **No**   | legacy file |
| `docker-compose.yml`                      | Yes      | uses `${VAR:-default}` references |
| `platform/frontend/.env`                  | **No**   | contains `VITE_GOOGLE_CLIENT_ID` |
| `node_modules/`, `dist/`, `venv/`, `data/`, `cv_test/` | **No** | reproducible / large |

The `${VAR:-default}` form in `docker-compose.yml` means the file works for a
new contributor even without a `.env` (with insecure defaults). Production
deployments should always provide a real `.env` or use Docker secrets.

## Public vs private env vars (frontend)

Vite bakes `VITE_*` variables into the JavaScript bundle at build time.
**They are visible to every browser** that loads the site.

| Variable                  | Treat as |
|---------------------------|----------|
| `VITE_API_URL`            | public   |
| `VITE_GOOGLE_CLIENT_ID`   | public (Google's OAuth client IDs are intentionally not secret) |

Backend-only secrets (`JWT_SECRET`, `ADMIN_TOKEN`, `POSTGRES_PASSWORD`, …)
must NEVER be exposed to the frontend.

## Production checklist

- [ ] `.env` filled with rotated production secrets
- [ ] `JWT_SECRET` ≥ 48 random bytes
- [ ] `ADMIN_TOKEN` ≥ 24 random bytes
- [ ] `AIRFLOW_FERNET_KEY` generated (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- [ ] All default `admin / admin123` credentials replaced
- [ ] `POSTGRES_PASSWORD`, `MONGO_INITDB_ROOT_PASSWORD`, `MINIO_ROOT_PASSWORD` rotated
- [ ] Google OAuth: `Authorised JavaScript origins` set to your prod domain
- [ ] Reverse-proxy in front of `frontend` and `platform-api` with HTTPS (Caddy / Traefik / Nginx + certbot)
- [ ] CORS in `platform/app/main.py` restricted from `*` to your prod domain
- [ ] Disable / firewall the pgAdmin and Mongo-Express UIs (or change passwords)
