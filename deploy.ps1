Write-Host "=============================================================================="
Write-Host "       CHAIN OF TITLE -- DEPLOYING CURRENT VERSION TO GOOGLE CLOUD RUN"
Write-Host "=============================================================================="

$ErrorActionPreference = "Stop"

Write-Host "Step 1/3: Submitting container build to Google Cloud Build..."
& gcloud builds submit --tag gcr.io/chain-of-title-cinema-2026/chain-of-title-backend:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Step 2/3: Deploying new image revision to Google Cloud Run..."
& gcloud run deploy chain-of-title-backend `
    --image gcr.io/chain-of-title-cinema-2026/chain-of-title-backend:latest `
    --platform managed `
    --region us-central1 `
    --allow-unauthenticated `
    --port 8080 `
    --memory 2Gi `
    --cpu 2 `
    --min-instances 0 `
    --max-instances 5 `
    --timeout 300 `
    --update-env-vars "APP_ENV=production,DEBUG=false,GCP_PROJECT_ID=chain-of-title-cinema-2026,GCS_BUCKET=chain-of-title-cinema-2026,GCS_ENABLED=true,STORAGE_BACKEND=gcs,PUBSUB_TOPIC=chain-of-title-events,PUBSUB_ENABLED=true,ADK_MODE=live,AI_PROVIDER=gemini,RESEARCH_PROVIDER=parallel"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Run deploy failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Step 3/3: Verifying deployment endpoint..."
$url = (& gcloud run services describe chain-of-title-backend --region us-central1 --format "value(status.url)").Trim()
Write-Host "=============================================================================="
Write-Host "DEPLOYED_URL: $url"
Write-Host "=============================================================================="
