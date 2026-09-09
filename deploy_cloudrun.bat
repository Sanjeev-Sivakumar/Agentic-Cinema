@echo off
REM ==============================================================================
REM Chain of Title — Google Cloud Run Deployment Script (Windows)
REM Target Project: chain-of-title-cinema-2026
REM Region: us-central1
REM ==============================================================================

set PROJECT_ID=chain-of-title-cinema-2026
set REGION=us-central1
set SERVICE_NAME=chain-of-title-backend
set IMAGE_TAG=gcr.io/%PROJECT_ID%/%SERVICE_NAME%:latest

echo ==============================================================================
echo           CHAIN OF TITLE — GOOGLE CLOUD RUN PRODUCTION DEPLOYMENT             
echo ==============================================================================
echo Project ID    : %PROJECT_ID%
echo Region        : %REGION%
echo Service Name  : %SERVICE_NAME%
echo Target Image  : %IMAGE_TAG%
echo ==============================================================================

echo 1/4 Setting GCP project...
call gcloud config set project %PROJECT_ID%

echo 2/4 Enabling Google Cloud APIs...
call gcloud services enable run.googleapis.com cloudbuild.googleapis.com storage.googleapis.com pubsub.googleapis.com firestore.googleapis.com secretmanager.googleapis.com

echo 3/4 Building container image with Google Cloud Build...
call gcloud builds submit --tag %IMAGE_TAG% .

echo 4/4 Deploying to Google Cloud Run...
call gcloud run deploy %SERVICE_NAME% ^
    --image %IMAGE_TAG% ^
    --platform managed ^
    --region %REGION% ^
    --allow-unauthenticated ^
    --port 8080 ^
    --memory 2Gi ^
    --cpu 2 ^
    --min-instances 0 ^
    --max-instances 5 ^
    --timeout 300 ^
    --set-env-vars "APP_ENV=production,DEBUG=false,GCP_PROJECT_ID=%PROJECT_ID%,GCS_BUCKET=%PROJECT_ID%,GCS_ENABLED=true,STORAGE_BACKEND=gcs,PUBSUB_TOPIC=chain-of-title-events,PUBSUB_ENABLED=true,ADK_MODE=live,AI_PROVIDER=gemini,RESEARCH_PROVIDER=parallel"

echo ==============================================================================
echo Deployment completed!
echo ==============================================================================
