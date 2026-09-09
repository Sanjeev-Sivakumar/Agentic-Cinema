# Chain of Title

> **Autonomous Agentic Pre-Clearance Intelligence System for Film, Advertising, and Media Productions**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![Google ADK: 2.8.0](https://img.shields.io/badge/Google%20ADK-2.8.0-blue.svg)](https://github.com/google/agent-development-kit)
[![Google Gemini: 3.5 Flash Lite](https://img.shields.io/badge/Google%20Gemini-3.5%20Flash%20Lite-orange.svg)](https://deepmind.google/technologies/gemini/)
[![Parallel Search: Live API](https://img.shields.io/badge/Parallel%20Search-Live%20Intelligence-purple.svg)](https://parallel.ai/)
[![Google Cloud Run: Ready](https://img.shields.io/badge/Google%20Cloud%20Run-Containerized-blue.svg)](https://cloud.google.com/run)

**Chain of Title** is an agentic AI system designed to turn raw media and screenplays into comprehensive, legally-auditable clearance decisions. Built on Google's Agent Development Kit (ADK 2.8.0), Google Gemini 3.5 Flash Lite, and the Parallel Search API, it automatically identifies rights-bearing entities, analyzes risk, estimates financial exposure, generates outreach permission drafts, and synthesizes remediation pathways before distribution.

---

## 🌟 The Signature Breakthrough: Visual-Only Clearance

In film and commercial production, the most catastrophic legal liabilities arise from **unscripted visual findings** — incidental logos, artwork, products, or music captured on set that never appeared in the original screenplay.

```
                  ┌───────────────────────────┐
                  │    Screenplay Intention   │
                  └─────────────┬─────────────┘
                                │
                    (Cross-Correlation Engine)
                                │
                  ┌─────────────▼─────────────┐
                  │    Captured Raw Footage   │
                  └─────────────┬─────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
     [SCRIPT_ONLY]            [BOTH]            [VISUAL_ONLY] 🚨
   Intentional text       Scripted & Filmed    UNSCRIPTED FINDING
   (Pre-cleared item)    (Verified on-set)   (High-risk incident)
```

Chain of Title computes full 8-stage evidence lineage for every entity:
$$\text{FRAME} \longrightarrow \text{ENTITY} \longrightarrow \text{RESEARCH QUERY} \longrightarrow \text{PARALLEL RESULTS} \longrightarrow \text{EVIDENCE} \longrightarrow \text{RISK} \longrightarrow \text{VERIFICATION} \longrightarrow \text{RESOLUTION}$$

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    React Dashboard (Vite + TypeScript)                  │
│       Command Center • Frame Inspector • Live SSE Pipeline Stream       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ (HTTP REST + Server-Sent Events SSE)
┌────────────────────────────────────▼────────────────────────────────────┐
│                       FastAPI Modular Backend                           │
│  Job Queue • Static Asset Streaming • Multi-Format Report Engine        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│            Google ADK 2.8.0 Multi-Agent Orchestrator (Root)             │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Screenplay Agent    │  5. Risk Agent        │  9. Financial Exposure│
│  2. Visual Agent        │  6. Verification Agent│ 10. Clearance Outreach│
│  3. Entity Merge Agent  │  7. Resolution Agent  │ 11. Visual Remediation│
│  4. Research Agent      │  8. Report Agent      │                       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  Parallel Search │       │  Google Gemini   │       │  Google Cloud    │
│  Live Trademarks │       │  3.5 Flash Lite  │       │  Storage & Pub/Sub│
└──────────────────┘       └──────────────────┘       └──────────────────┘
```

---

## ⚡ The 11-Stage Clearance Intelligence Pipeline

1. **Screenplay Parsing (`ScreenplayAgent`)**: Extracts scripted brand names, locations, music, and prop mentions directly from screenplay text or PDF documents.
2. **Video Ingestion & Adaptive Sampling (`VisualAgent`)**: Detects scene boundaries, extracts keyframes at optimal timestamps, and budgets vision API quota.
3. **Multimodal Visual Perception (`VisionProvider`)**: Runs YOLOv8 object detection, EasyOCR text recognition, and Google Gemini 3.5 Flash Lite visual analysis on extracted frames.
4. **Entity Normalization & Discrepancy Merge (`EntityMergeAgent`)**: Compares screenplay intentions against raw footage, flagging `BOTH`, `SCRIPT_ONLY`, and high-priority `VISUAL_ONLY` discrepancies.
5. **Live Intelligence Research (`ResearchAgent`)**: Queries the **Parallel Search API** live for candidate rights holders, corporate parent structures, and official USPTO trademark registrations.
6. **Multi-Factor Risk Assessment (`RiskAssessmentAgent`)**: Evaluates exposure on a 0–100 risk score based on visual prominence, duration, context, and fair use defensibility.
7. **Dual-Agent Verification (`VerificationAgent`)**: Validates candidate rights-holder relationships against retrieved web citations and corroborating evidence records.
8. **Automated Resolution Engine (`ResolutionAgent`)**: Assigns deterministic clearance actions (`NO_ACTION`, `REVIEW_BRAND_USAGE`, `BLUR_REMEDIATION`, `REPLACEMENT_REQUIRED`, `ACQUIRE_LICENSE`).
9. **Financial Exposure Intelligence (`FinancialExposureEngine`)**: Estimates evidence-backed operational liability and licensing ranges backed by statutory frameworks (e.g., 15 U.S.C. § 1117).
10. **Clearance Outreach Agent (`ClearanceOutreachAgent`)**: Drafts professional rights holder permission letters and packages Gmail drafts with timecode stamps and usage descriptions.
11. **Visual Remediation & Multi-Format Reporting (`VisualRemediationService` & `ReportEngine`)**: Generates visual blur/replacement proposals and compiles auditable JSON, standalone interactive HTML, and print-ready PDF clearance reports.

---

## 🛠️ Enterprise Tech Stack

| Layer | Technology |
|---|---|
| **Multi-Agent Orchestration** | Google Agent Development Kit (ADK 2.8.0) |
| **Multimodal AI Reasoning** | Google Gemini 3.5 Flash Lite (`google-genai`) |
| **Web & Trademark Intelligence** | Parallel Search API (Live USPTO / Corporate Registry Search) |
| **Computer Vision & OCR** | OpenCV, Ultralytics YOLOv8, PySceneDetect, EasyOCR, PyTorch |
| **Backend API Framework** | FastAPI, Uvicorn, Pydantic v2, Python 3.11+ |
| **Event Architecture** | InMemoryEventBus (Local Pub/Sub) ↔ Google Cloud Pub/Sub (`chain-of-title-events`) |
| **Storage Architecture** | Local Filesystem Cache ↔ Google Cloud Storage (`chain-of-title-cinema-2026`) |
| **Report Generation** | ReportLab (PDF), Jinja2 (HTML), JSON Schema |
| **Frontend UI** | React 18, Vite, TypeScript, TailwindCSS, Lucide Icons, SSE Client |
| **Cloud Deployment** | Google Cloud Run (Containerized single-port deployment) |

---

## 🚀 Quickstart & Local Execution

### 1. Prerequisites
- **Python 3.10+** (tested on Python 3.11, 3.12, 3.14)
- **Node.js 18+** & **npm**

### 2. Clone & Install Dependencies
```bash
# Clone the repository
git clone https://github.com/Sanjeev-Sivakumar/Agentic-Cinema.git
cd Agentic-Cinema

# Install Python backend dependencies
pip install -r backend/requirements.txt

# Install Frontend dependencies
cd frontend && npm install && cd ..
```

### 3. Configure Environment Variables
Copy the development environment template:
```bash
cp .env.example .env
```
Edit `.env` to set your API keys:
```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
PARALLEL_API_KEY=your_parallel_api_key_here
ADK_MODE=live
```

---

### 4. Running the Application

#### Option A: Full Solution (Frontend + Backend Concurrently)
```bash
python run_solution.py
```
* **Frontend Command Center**: [http://localhost:5173](http://localhost:5173)
* **Backend REST API & Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Health Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

#### Option B: Standalone CLI Pipeline Run
To analyze a video file directly from the command line:
```bash
python run_cli.py test_video1.mp4
```

---

## 🧪 Automated Testing

Chain of Title includes **349 comprehensive automated tests** covering unit, integration, edge-case, and mock scenarios:

```bash
# Run complete test suite
python -m pytest backend/tests -v
```

---

## ☁️ Google Cloud Run Deployment

The application is containerized and pre-configured for deployment on Google Cloud Run:

```bash
# 1. Configure GCP Project
gcloud config set project chain-of-title-cinema-2026

# 2. Enable Required APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com storage.googleapis.com pubsub.googleapis.com

# 3. Build Container via Cloud Build
gcloud builds submit --tag gcr.io/chain-of-title-cinema-2026/chain-of-title-backend:latest .

# 4. Deploy to Cloud Run
gcloud run deploy chain-of-title-backend \
    --image gcr.io/chain-of-title-cinema-2026/chain-of-title-backend:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --set-env-vars "\
APP_ENV=production,\
GCP_PROJECT_ID=chain-of-title-cinema-2026,\
GCS_BUCKET=chain-of-title-cinema-2026,\
GCS_ENABLED=true,\
STORAGE_BACKEND=gcs,\
PUBSUB_TOPIC=chain-of-title-events,\
PUBSUB_ENABLED=true,\
ADK_MODE=live,\
AI_PROVIDER=gemini,\
RESEARCH_PROVIDER=parallel"
```

---

## 📡 REST API & Streaming Specification

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Service health status, environment mode, and active storage/database backends |
| `/productions` | `POST` | Create a new media production project |
| `/productions/{id}` | `GET` | Retrieve production metadata and status |
| `/productions/{id}/script` | `POST` | Upload and parse screenplay text/PDF |
| `/productions/{id}/footage` | `POST` | Ingest and register raw video footage |
| `/productions/{id}/analyze` | `POST` | Trigger the 11-stage autonomous ADK clearance workflow |
| `/productions/{id}/status` | `GET` | Retrieve live entity counts and processing progress |
| `/productions/{id}/entities` | `GET` | Retrieve filterable clearance entity directory |
| `/productions/{id}/evidence` | `GET` | Retrieve extracted frames, OCR text, and bounding boxes |
| `/productions/{id}/report` | `GET` | Download synthesized audit reports (JSON / HTML / PDF) |
| `/productions/{id}/analysis/{job_id}/events` | `GET` | **Server-Sent Events (SSE)** real-time pipeline event stream |

---

## 📄 Open Source License

This project is licensed under the **[Apache License 2.0](LICENSE)** (an [OSI-Approved License](https://opensource.org/licenses/Apache-2.0)).

* **Repository URL**: [https://github.com/Sanjeev-Sivakumar/Agentic-Cinema](https://github.com/Sanjeev-Sivakumar/Agentic-Cinema)
* **Author**: Sanjeev Sivakumar
