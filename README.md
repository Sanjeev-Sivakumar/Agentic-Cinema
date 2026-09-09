# Chain of Title (Foundational Architecture)

> **Agentic Pre-Clearance Intelligence System for Film, Advertising, and Media Productions**

Chain of Title compares screenplay intention against captured video footage, detects potential clearance-relevant entities, performs parallel intelligence research, computes multi-factor liability risk, verifies rights holders, and formulates remediation pathways.

The signature product differentiator is **VISUAL-ONLY FINDINGS** — rights-relevant brands, logos, artwork, or music appearing in raw footage that were unscripted.

---

## 🏛️ Architecture Overview

```
React Frontend (Vite + TypeScript)
        ↓ (HTTP REST + Server-Sent Events SSE)
FastAPI Modular Backend
        ↓
Google ADK Root Agent Orchestrator
        ↓
Specialized Agent Submodules (Text, Visual, Research, Risk, Verification, Resolution, Report)
        ↓
Repository & Storage Abstractions (Local InMemory/Filesystem ↔ Google Cloud Firestore/GCS)
        ↓
Async InMemoryEventBus (Local Pub/Sub with History Replay)
```

---

## 🚀 Quickstart & Local Execution

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Node.js 18+ (tested on Node v24)
- npm

### 2. Backend Setup
```bash
# Navigate to workspace root
pip install -r backend/requirements.txt

# Run backend API server
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```
API Health: `http://localhost:8000/health`  
Interactive OpenAPI Docs: `http://localhost:8000/docs`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Dashboard URL: `http://localhost:5173`

### 4. Running Automated Tests
```bash
python -m pytest backend/tests -v
```

---

## 📡 API Specification

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health, version, and active backends |
| `/productions` | POST | Create media production record |
| `/productions/{id}` | GET | Retrieve production details |
| `/productions/{id}/script` | POST | Upload screenplay (text/file) |
| `/productions/{id}/footage` | POST | Register raw footage path/file |
| `/productions/{id}/analyze` | POST | Trigger 12-stage analysis job |
| `/productions/{id}/status` | GET | Active job and entity counts |
| `/productions/{id}/entities` | GET | Filterable entity directory |
| `/productions/{id}/evidence` | GET | Captured frames & OCR records |
| `/productions/{id}/requests` | GET | Clearance action items |
| `/productions/{id}/report` | GET | Audit report & checklist |
| `/productions/{id}/analysis/{job_id}/events` | GET | Real-time SSE streaming endpoint |

---

## 🛡️ Cloud Deployment Roadmap (Demo Mode)

The architecture is cloud-compatible from day one without rewriting:
- **Storage**: Set `STORAGE_BACKEND=gcs` and `GCS_BUCKET=...` to use `GoogleCloudStorageService`.
- **Database**: Set `DATABASE_BACKEND=firestore` and `ENABLE_FIRESTORE=true` to use `FirestoreRepository`.
- **Compute**: Ready for single-container deployment on Google Cloud Run.
- **AI / Research**: Plug `GEMINI_API_KEY` (Gemini 3.5 Flash Lite) and `PARALLEL_API_KEY` (Parallel Web Intelligence).

---

## 📄 Open Source License

This project is open source and licensed under the **[Apache License 2.0](LICENSE)** (an [OSI-Approved License](https://opensource.org/licenses/Apache-2.0)).

* **Repository URL**: [https://github.com/Sanjeev-Sivakumar/Agentic-Cinema](https://github.com/Sanjeev-Sivakumar/Agentic-Cinema)

