# GCP Deployment

This app is best deployed on GCP as Cloud Run Jobs triggered by Cloud Scheduler.
That avoids keeping a 24/7 worker alive just to wait for market times.

## 1. Create GCP Project

Create a project and enable billing/free trial.

Recommended region close to India:

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-south1"
export REPOSITORY="stockbot"
export IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/stockbot:latest"
gcloud config set project "$PROJECT_ID"
```

Enable APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com
```

## 2. Build And Push Image

```bash
gcloud artifacts repositories create "$REPOSITORY" \
  --repository-format=docker \
  --location="$REGION"

gcloud builds submit --tag "$IMAGE"
```

## 3. Create Cloud Run Jobs

Create the main trading scan:

```bash
gcloud run jobs create stockbot-morning-scan \
  --image "$IMAGE" \
  --region "$REGION" \
  --command python \
  --args -m,project.trading.scheduler,run,morning-scan \
  --memory 2Gi \
  --cpu 2 \
  --task-timeout 21600 \
  --set-env-vars TRADING_MODE=paper,TRADING_CAPITAL=10000
```

Create the end-of-day report:

```bash
gcloud run jobs create stockbot-evening-report \
  --image "$IMAGE" \
  --region "$REGION" \
  --command python \
  --args -m,project.trading.scheduler,run,evening-report \
  --memory 1Gi \
  --cpu 1 \
  --task-timeout 1800 \
  --set-env-vars TRADING_MODE=paper,TRADING_CAPITAL=10000
```

Create the nightly retrain:

```bash
gcloud run jobs create stockbot-nightly-retrain \
  --image "$IMAGE" \
  --region "$REGION" \
  --command python \
  --args -m,project.trading.scheduler,run,nightly-retrain \
  --memory 4Gi \
  --cpu 2 \
  --task-timeout 21600 \
  --set-env-vars TRADING_MODE=paper,TRADING_CAPITAL=10000
```

Optional pre-market preview:

```bash
gcloud run jobs create stockbot-pre-market \
  --image "$IMAGE" \
  --region "$REGION" \
  --command python \
  --args -m,project.trading.scheduler,run,pre-market \
  --memory 1Gi \
  --cpu 1 \
  --task-timeout 1800 \
  --set-env-vars TRADING_MODE=paper,TRADING_CAPITAL=10000
```

## 4. Add Secrets / Env Vars

Do not commit `.env`. Add secrets in Cloud Run job configuration.

Common variables:

```text
TRADING_MODE=paper
TRADING_CAPITAL=10000
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
ANGEL_API_KEY=...
ANGEL_CLIENT_ID=...
ANGEL_PASSWORD=...
ANGEL_TOTP_SECRET=...
```

For live trading, update each job from `TRADING_MODE=paper` to `TRADING_MODE=live`
only after paper mode has been verified.

## 5. Schedule Jobs

Use IST time zone directly:

```bash
gcloud scheduler jobs create http stockbot-morning-scan \
  --location "$REGION" \
  --schedule "30 9 * * 1-5" \
  --time-zone "Asia/Kolkata" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/stockbot-morning-scan:run" \
  --http-method POST \
  --oauth-service-account-email "$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

gcloud scheduler jobs create http stockbot-evening-report \
  --location "$REGION" \
  --schedule "0 16 * * 1-5" \
  --time-zone "Asia/Kolkata" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/stockbot-evening-report:run" \
  --http-method POST \
  --oauth-service-account-email "$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

gcloud scheduler jobs create http stockbot-nightly-retrain \
  --location "$REGION" \
  --schedule "0 18 * * 1-5" \
  --time-zone "Asia/Kolkata" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/stockbot-nightly-retrain:run" \
  --http-method POST \
  --oauth-service-account-email "$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
```

Cloud Scheduler includes 3 free jobs per billing account. The optional
pre-market job would be a fourth scheduled job.

## 6. Test Manually

```bash
gcloud run jobs execute stockbot-morning-scan --region "$REGION" --wait
gcloud run jobs executions list --job stockbot-morning-scan --region "$REGION"
```

