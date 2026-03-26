# Deploy Mork to Google Cloud with GitHub Actions

This guide walks through running the bot on Google Cloud and adding a **Deploy Mork** job to GitHub Actions. It assumes you already have a Discord bot token and the usual Mork secrets (see the main README).

## What you are building

1. A container image that runs `Mork.py` (see the repo `Dockerfile`).
2. A GCP runtime that can run that container with secrets available as environment variables or mounted files.
3. A GitHub Actions workflow that builds the image, pushes it to Artifact Registry, and updates the service on each push to `main` (or on manual dispatch).

Cloud Run is the simplest option: it runs a container, scales to zero when idle, and integrates cleanly with IAM and Secret Manager.

## Prerequisites

- A **Google Cloud project** with billing enabled.
- **APIs enabled**: Artifact Registry, Cloud Run (or your chosen runtime), IAM Credentials, and Secret Manager (recommended for tokens).
- **GitHub repository** with Actions enabled.

## One-time GCP setup

### 1. Artifact Registry

Create a Docker repository (example names — adjust to taste):

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable artifactregistry.googleapis.com

gcloud artifacts repositories create mork \
  --repository-format=docker \
  --location=us-central1 \
  --description="Mork bot images"
```

Your image will look like:

`us-central1-docker.pkg.dev/YOUR_PROJECT_ID/mork/mork:latest`

### 2. Secret Manager (recommended)

Store sensitive values instead of putting them in the workflow YAML:

```bash
echo -n 'your-discord-bot-token' | gcloud secrets create discord-bot-token --data-file=-
# Repeat for other secrets (e.g. contents of client_secrets.json, reddit creds).
```

Grant the **Cloud Run service account** access to read these secrets when you create or update the service (Console: Cloud Run → service → Edit → Variables & secrets → Reference secret).

### 3. Workload Identity Federation (no JSON key in GitHub)

This lets GitHub Actions authenticate to GCP without storing a long-lived service account key in a GitHub secret.

Follow Google’s overview: [Workload Identity Federation for deployment pipelines](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines), and the setup steps in the [`google-github-actions/auth`](https://github.com/google-github-actions/auth#workload-identity-federation) README.

Summary of the pieces:

1. Create a **Workload Identity Pool** and **Provider** tied to your GitHub org/repo.
2. Create a **service account** for deployments (e.g. `github-deployer@PROJECT.iam.gserviceaccount.com`) with roles such as:
   - `roles/artifactregistry.writer` (push images)
   - `roles/run.admin` (deploy Cloud Run)
   - `roles/iam.serviceAccountUser` (on the Cloud Run **runtime** service account if different)
3. Bind `roles/iam.workloadIdentityUser` on that service account so the GitHub provider can impersonate it.

Note the outputs: `workload_identity_provider` (full resource name) and `service_account` email — you will store them as GitHub repo **Variables** or **Secrets**.

### 4. Cloud Run service (first deploy)

You can deploy once from your laptop to create the service, then let GitHub Actions take over updates:

```bash
gcloud run deploy mork \
  --region=us-central1 \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/mork/mork:latest \
  --service-account=YOUR_RUNTIME_SA@YOUR_PROJECT.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --set-secrets=DISCORD_SECRET=discord-bot-token:latest
```

Adapt secret names and env vars to match how `Mork.py` / `bot_secrets` load configuration. If the code expects files on disk, either:

- Change the bot to read from environment variables in production, or  
- Mount secrets as files via Cloud Run volume mounts (Secret Manager volume).

## GitHub repository configuration

Add these **GitHub Actions secrets** (names are suggestions):

| Secret | Purpose |
|--------|---------|
| `WORKLOAD_IDENTITY_PROVIDER` | Full WIF provider resource name |
| `SERVICE_ACCOUNT_EMAIL` | Deployer service account email |
| `GCP_PROJECT_ID` | Optional if hard-coded in workflow |

Optional: `GCP_REGION` as a variable.

## Example workflow: build, push, deploy

Create `.github/workflows/deploy-mork.yml` (adjust image path, region, and service name):

```yaml
name: Deploy Mork

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGION: us-central1
  PROJECT_ID: YOUR_PROJECT_ID
  REPO: mork
  IMAGE_NAME: mork
  SERVICE: mork

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write

    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.SERVICE_ACCOUNT_EMAIL }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker auth
        run: gcloud auth configure-docker ${{ env.REGION }}-docker.pkg.dev --quiet

      - name: Build image
        run: |
          IMAGE="${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.REPO }}/${{ env.IMAGE_NAME }}:${{ github.sha }}"
          docker build -t "$IMAGE" .
          docker push "$IMAGE"

      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: ${{ env.SERVICE }}
          region: ${{ env.REGION }}
          image: ${{ env.REGION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.REPO }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
```

After the first successful deploy, tighten the workflow: require CI to pass (the repo’s `CI` workflow) before deploy by using a `workflow_run` trigger or branch protection rules.

## Operational notes

- **Long-running bot**: Cloud Run is request-driven by default. A Discord bot is a long-lived process; use **minimum instances = 1** (or run on GKE / a VM) so the gateway does not shut the container down when there are no HTTP requests. Alternatively, use a small Compute Engine instance or GKE Deployment if you prefer a traditional always-on server.
- **Secrets**: Prefer Secret Manager + IAM over baking JSON into the image.
- **Database / Drive**: Ensure the **runtime** service account has the same spreadsheet and Drive access as your local `client_secrets.json` service account (or use that account as the Cloud Run service account).

## Related repo files

- [`Dockerfile`](../Dockerfile) — container entrypoint `python Mork.py`
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — lint / syntax checks on pull requests
- [`scripts/download_and_upload_images_gcs.py`](../scripts/download_and_upload_images_gcs.py) — optional GCS sync for token images (run from repo root; use a scheduled job with credentials if you automate it)
