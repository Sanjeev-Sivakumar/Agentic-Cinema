#!/usr/bin/env bash
# ==============================================================================
# Chain of Title — Google Cloud Run Deployment Script
# Target Project: chain-of-title-cinema-2026
# Region: us-central1
# ==============================================================================
set -euo pipefail

PROJECT_ID="chain-of-title-cinema-2026"
REGION="us-central1"
SERVICE_NAME="chain-of-title-backend"
IMAGE_TAG="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "=============================================================================="
echo "          CHAIN OF TITLE — GOOGLE CLOUD RUN PRODUCTION DEPLOYMENT             "
echo "=============================================================================="
echo "Project ID    : ${PROJECT_ID}"
echo "Region        : ${REGION}"
echo "Service Name  : ${SERVICE_NAME}"
echo "Target Image  : ${IMAGE_TAG}"
echo "=============================================================================="

# 1. Set Active GCP Project
echo "1/4 Configuring Google Cloud project..."
gcloud config set project "${PROJECT_ID}"

# 2. Enable Required Google Cloud APIs (One-time setup)
echo "2/4 Ensuring required Cloud APIs are enabled..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    storage.googleapis.com \
    pubsub.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com

# 3. Build & Submit Container Image via Cloud Build
echo "3/4 Building container image with Google Cloud Build..."
gcloud builds submit --tag "${IMAGE_TAG}" .

# 4. Deploy to Google Cloud Run
echo "4/4 Deploying to Google Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_TAG}" \
    --platform managed \
    --region "${REGION}" \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 0 \
    --max-instances 5 \
    --timeout 300 \
    --set-env-vars "\
APP_ENV=production,\
DEBUG=false,\
GCP_PROJECT_ID=${PROJECT_ID},\
GCS_BUCKET=${PROJECT_ID},\
GCS_ENABLED=true,\
STORAGE_BACKEND=gcs,\
PUBSUB_TOPIC=chain-of-title-events,\
PUBSUB_ENABLED=true,\
ADK_MODE=live,\
AI_PROVIDER=gemini,\
RESEARCH_PROVIDER=parallel"

echo "=============================================================================="
echo " Deployment Complete! Retrieve service URL with:"
echo " gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)'"
echo "=============================================================================="
