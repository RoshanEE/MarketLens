# MarketLens — CI/CD and Cloud Deployment

## Overview

```
GitHub Repository
       │
       ├── PR to main ──────► Lint only (ruff / eslint) — no deploy
       │
       └── Manual dispatch ──► Lint + Build + Deploy
                               │
                               ├── Backend  → AWS Lightsail Container Service
                               └── Frontend → AWS S3 + CloudFront CDN
```

The two services are deployed independently. A backend change doesn't trigger a frontend redeploy and vice versa.

---

## Infrastructure (AWS CloudFormation)

All AWS resources are defined in `infrastructure/cloudformation.yml` and provisioned as a single stack.

### Resources Created

**Lightsail Container Service** — backend
- Power: `micro` (0.5 vCPU, 1 GB RAM)
- Estimated cost: ~$10/month
- Scale: 1 node (can be increased without code changes)

**S3 Bucket** — frontend static assets
- Public access blocked; served exclusively via CloudFront
- Versioned uploads (`--delete` flag removes stale files on each deploy)

**CloudFront Distribution** — frontend CDN
- Origin Access Control (OAC) ensures S3 objects are only accessible through CloudFront, not directly
- Global edge caching for fast load times
- Cache invalidation (`/*`) on every frontend deploy

**IAM User** (`marketlens-github-deployer`) with scoped permissions:
- Lightsail: push container images, create deployments
- S3: upload and delete objects in the frontend bucket
- CloudFront: create cache invalidations

---

## Why Lightsail for the Backend

**Lightweight + predictable cost**: Lightsail Container Services offer a flat monthly price (no per-request billing). For a backend that runs long-lived pipeline tasks (30–90 seconds per research run), a serverless option like Lambda would either time out or require complex async splitting.

**Simpler than ECS/EKS**: Lightsail Container Services support Docker image pushes directly via `lightsailctl` — no ECR registry to manage, no ECS task definitions, no VPC configuration. Enough control (health checks, env vars, port mapping) without the operational overhead.

**Built-in HTTPS**: Lightsail provides a public HTTPS endpoint automatically; no certificate management needed.

**Fast cold start**: The container is always-on (not cold-start serverless), which matters for SSE connections where the client opens a persistent stream.

---

## Why S3 + CloudFront for the Frontend

The frontend is a static SPA (React + Vite build output: HTML, JS, CSS). There's no server-side rendering needed.

**S3** is the cheapest possible static file store — essentially free at this traffic level.

**CloudFront** provides:
- Global CDN — assets served from edge locations close to the user
- HTTPS with no certificate management
- Cache invalidation on deploy so users always get the latest version
- Origin Access Control so the S3 bucket is not publicly accessible on its own

The nginx proxy pattern (used for local Docker Compose) is not needed in production: the frontend calls `VITE_API_BASE_URL` directly (the Lightsail endpoint). No reverse proxy required.

---

## GitHub Actions Workflows

### Backend — `.github/workflows/deploy-backend.yml`

**Triggers:**
- Pull request to `main` (backend files changed) → lint only
- Manual `workflow_dispatch` → lint + build + deploy

**Steps:**

1. **Lint** — `ruff check app/` (runs on every PR, fails fast)
2. **Build** — `docker build` the multi-stage backend image
3. **Push** — `aws lightsail push-container-image` uploads the image to the Lightsail service (no ECR involved)
4. **Deploy** — `aws lightsail create-container-service-deployment` with container config (image, env vars, port, health check path)

Environment variables (Supabase credentials, API keys, CORS origins) are injected at deploy time from GitHub Secrets — they are never baked into the image.

**Health check:** `GET /health` at 10-second intervals; 2 successful checks to go healthy, 3 failures to mark unhealthy.

**Required GitHub Secrets:**
```
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET
DATABASE_URL
ANTHROPIC_API_KEY, OPENAI_API_KEY
CORS_ORIGINS
```

---

### Frontend — `.github/workflows/deploy-frontend.yml`

**Triggers:**
- Pull request to `main` (frontend files changed) → lint only
- Manual `workflow_dispatch` → lint + build + deploy

**Steps:**

1. **Lint** — `npm run lint` (eslint on `.ts`/`.tsx` files)
2. **Build** — `npm run build` with `VITE_*` env vars baked in at build time (Vite replaces them at bundle time, not runtime)
3. **Sync to S3** — `aws s3 sync frontend/dist/ s3://<bucket> --delete` replaces all files
4. **Invalidate CloudFront** — `aws cloudfront create-invalidation --paths "/*"` forces edge nodes to re-fetch from S3

The S3 sync and CloudFront invalidation steps are **skipped gracefully** if `S3_BUCKET` or `CLOUDFRONT_DISTRIBUTION_ID` secrets are not set. This means the workflow can be committed before the CloudFormation stack is deployed without failing.

**Required GitHub Secrets:**
```
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
VITE_API_BASE_URL           (Lightsail public endpoint)
S3_BUCKET                   (from CloudFormation stack output)
CLOUDFRONT_DISTRIBUTION_ID  (from CloudFormation stack output)
```

---

## Deployment Sequence (First Time)

1. **Provision infrastructure** — deploy the CloudFormation stack (`infrastructure/cloudformation.yml`) to create the Lightsail service, S3 bucket, and CloudFront distribution
2. **Collect outputs** — note `FrontendBucketName`, `CloudFrontDistributionId`, `LightsailEndpoint` from the stack outputs
3. **Set GitHub Secrets** — add all required secrets listed above for both workflows
4. **Run database migrations** — apply `001_initial.sql` and `002_add_source_run_id.sql` in Supabase SQL editor
5. **Deploy backend** — trigger "Deploy Backend" workflow manually from GitHub Actions
6. **Deploy frontend** — trigger "Deploy Frontend" workflow manually, using the Lightsail endpoint as `VITE_API_BASE_URL`

---

## Docker Setup (Local)

Both services have multi-stage Dockerfiles to minimize image size.

**Backend (`backend/Dockerfile`):**
- Stage 1: Python 3.12-slim — installs dependencies
- Stage 2: Python 3.12-slim runtime — copies only installed packages + app code
- Runs as non-root `appuser`
- Exposes port 8000

**Frontend (`frontend/Dockerfile`):**
- Stage 1: Node 20-alpine — `npm ci && npm run build`
- Stage 2: Nginx 1.27-alpine — serves `/usr/share/nginx/html`
- `nginx.conf` handles SPA routing (all paths → `index.html`) and proxies `/api/*` to the backend

**`docker-compose.yml`:**
- Starts both services
- Backend health check before frontend starts
- Both read from `.env` files in their respective directories
