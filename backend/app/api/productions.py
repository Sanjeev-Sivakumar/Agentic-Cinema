import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from app.core.logging import logger
from app.models.analysis import AnalysisJob, JobStatus
from app.models.production import Production, ProductionCreate, ProductionStatus, ProductionUpdate
from app.repositories import (
    get_production_repo,
    get_job_repo,
    get_entity_repo,
    get_evidence_repo,
    get_clearance_repo,
    get_verification_repo,
    get_resolution_repo,
)
from app.services.storage import storage_service
from app.agents.root_agent import root_agent

router = APIRouter(prefix="/productions", tags=["productions"])

@router.post("", response_model=Production, status_code=status.HTTP_201_CREATED)
async def create_production(payload: ProductionCreate) -> Production:
    """Create a new film, advertising, or media production."""
    prod_repo = get_production_repo()
    production = Production(
        title=payload.title,
        description=payload.description,
        director=payload.director,
        studio=payload.studio,
        budget_tier=payload.budget_tier or "Independent",
        metadata=payload.metadata,
    )
    saved = await prod_repo.create(production)
    logger.info(f"[API] Created production '{saved.title}' with ID: {saved.id}")
    return saved


@router.get("/available/videos")
@router.get("/available-videos")
async def list_available_videos() -> List[Dict[str, Any]]:
    """List available video files in the workspace project folder for selection."""
    from pathlib import Path
    from app.core.config import settings

    base_dir = Path(settings.BASE_DIR)
    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    videos = []

    for f in sorted(base_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in video_exts:
            size = f.stat().st_size
            name = f.name
            desc = "Clearance benchmark footage"
            is_rec = False
            if "video1" in name.lower():
                desc = "Cadbury Dairy Milk & Sony showcase footage (Recommended)"
                is_rec = True
            elif "video" in name.lower():
                desc = "Production B-roll sample reel"

            videos.append({
                "filename": name,
                "path": name,
                "url": f"/media/{name}",
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "is_recommended": is_rec,
                "description": desc,
            })

    return videos


@router.get("/{production_id}", response_model=Production)

async def get_production(production_id: str) -> Production:
    """Get production metadata by ID."""
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )
    return production


@router.post("/{production_id}/script")
async def upload_script(
    production_id: str,
    file: Optional[UploadFile] = File(None),
    script_text: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Upload or provide screenplay text for a production."""
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    saved_path = ""
    if file:
        content = await file.read()
        filename = f"scripts/{production_id}_{file.filename}"
        saved_path = await storage_service.save_file(filename, content)
    elif script_text:
        content = script_text.encode("utf-8")
        filename = f"scripts/{production_id}_screenplay.txt"
        saved_path = await storage_service.save_file(filename, content)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a script file or script_text must be provided",
        )

    production.script_path = saved_path
    production.updated_at = datetime.now(timezone.utc)
    if production.footage_path:
        production.status = ProductionStatus.READY_FOR_ANALYSIS
    await prod_repo.update(production)

    return {
        "status": "SUCCESS",
        "production_id": production_id,
        "script_path": saved_path,
        "message": "Screenplay uploaded successfully",
    }


class ScreenplayAnalyzeRequest(BaseModel):
    text: str = Field(..., description="Screenplay text content to analyze")

@router.post("/{production_id}/screenplay/analyze")
async def analyze_screenplay_endpoint(
    production_id: str,
    payload: ScreenplayAnalyzeRequest,
) -> Dict[str, Any]:
    """
    Directly analyze screenplay text for clearance-relevant entities.
    Segments scenes, extracts entities using configured provider, and stores in repository.
    """
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    from app.agents.text_agent import text_agent
    from app.services.screenplay_parser import screenplay_scene_parser

    # Execute text agent analysis
    entities = await text_agent.analyze_screenplay(
        screenplay_text=payload.text,
        production_id=production_id,
    )

    # Persist extracted entities to entity repository
    entity_repo = get_entity_repo()
    for ent in entities:
        await entity_repo.create(ent)

    # Count scenes
    scenes = screenplay_scene_parser.parse_scenes(payload.text)
    scene_count = len(scenes)

    return {
        "production_id": production_id,
        "entities": [ent.model_dump() for ent in entities],
        "scene_count": scene_count,
        "entity_count": len(entities),
    }


class ResearchRequestPayload(BaseModel):
    entity_ids: Optional[List[str]] = Field(default=None, description="Optional subset of entity IDs to research")
    force_refresh: bool = Field(default=False, description="Bypass cache and force re-research")

@router.post("/{production_id}/research")
async def research_entities_endpoint(
    production_id: str,
    payload: Optional[ResearchRequestPayload] = None,
) -> Dict[str, Any]:
    """
    Execute factual rights-holder and trademark research for entities in a production.
    Prioritizes VISUAL_ONLY > BOTH > SCRIPT_ONLY entities.
    """
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    entity_repo = get_entity_repo()
    all_entities = await entity_repo.list_by_production(production_id)

    target_entities: List[Entity] = []
    requested_ids = payload.entity_ids if payload and payload.entity_ids else None

    if requested_ids:
        id_set = set(requested_ids)
        target_entities = [e for e in all_entities if e.id in id_set]
    else:
        target_entities = all_entities

    from app.agents.research_agent import research_agent

    force = payload.force_refresh if payload else False
    results = await research_agent.research_entities(
        entities=target_entities,
        production_id=production_id,
        force_refresh=force,
    )

    formatted_results = [
        {
            "entity_name": r.entity_name,
            "status": r.status.value,
            "candidate_rights_holder": r.candidate_rights_holder,
            "research_confidence": r.research_confidence,
            "evidence_count": len(r.evidence),
            "provider": r.provider,
            "entity_id": r.entity_id,
        }
        for r in results
    ]

    return {
        "production_id": production_id,
        "results": formatted_results,
    }


class RiskAssessmentRequestPayload(BaseModel):
    entity_ids: Optional[List[str]] = Field(default=None, description="Optional subset of entity IDs to assess")
    force_refresh: bool = Field(default=False, description="Bypass cache and force re-assessment")

@router.post("/{production_id}/risk-assessment")
async def risk_assessment_endpoint(
    production_id: str,
    payload: Optional[RiskAssessmentRequestPayload] = None,
) -> Dict[str, Any]:
    """
    Execute multi-factor triage risk assessment for entities in a production.
    Prioritizes VISUAL_ONLY > BOTH > SCRIPT_ONLY entities.
    """
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    entity_repo = get_entity_repo()
    all_entities = await entity_repo.list_by_production(production_id)

    requested_ids = payload.entity_ids if payload and payload.entity_ids else None
    if requested_ids:
        id_set = set(requested_ids)
        target_entities = [e for e in all_entities if e.id in id_set]
    else:
        target_entities = all_entities

    from app.agents.risk_agent import risk_agent

    force = payload.force_refresh if payload else False
    assessments = await risk_agent.assess_entities(
        entities=target_entities,
        production_id=production_id,
        force_refresh=force,
    )

    formatted = [
        {
            "entity_id": a.entity_id,
            "entity_name": a.entity_name,
            "risk_level": a.risk_level.value if hasattr(a.risk_level, "value") else str(a.risk_level),
            "risk_score": round(a.risk_score, 1),
            "confidence": a.confidence,
        }
        for a in assessments
    ]

    return {
        "production_id": production_id,
        "assessments": formatted,
    }


class VerificationRequestPayload(BaseModel):
    entity_ids: Optional[List[str]] = Field(default=None, description="Optional subset of entity IDs to verify")
    force_refresh: bool = Field(default=False, description="Bypass cache and force re-verification")

@router.post("/{production_id}/verification")
async def verification_endpoint(
    production_id: str,
    payload: Optional[VerificationRequestPayload] = None,
) -> Dict[str, Any]:
    """
    Execute adversarial verification for entities in a production.
    Prioritizes High Risk > Medium Risk > Low Risk, Visual-Only > Both > Script-Only.
    """
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    entity_repo = get_entity_repo()
    all_entities = await entity_repo.list_by_production(production_id)

    requested_ids = payload.entity_ids if payload and payload.entity_ids else None
    if requested_ids:
        id_set = set(requested_ids)
        target_entities = [e for e in all_entities if e.id in id_set]
    else:
        target_entities = all_entities

    from app.agents.verification_agent import verification_agent

    force = payload.force_refresh if payload else False
    results = await verification_agent.verify_entities(
        entities=target_entities,
        production_id=production_id,
        force_refresh=force,
    )

    formatted = [
        {
            "verification_id": r.verification_id,
            "entity_id": r.entity_id,
            "entity_name": r.entity_name,
            "decision": r.decision.value if hasattr(r.decision, "value") else str(r.decision),
            "confidence": round(r.confidence, 2),
            "claims_supported": r.claims_supported,
            "claims_disputed": r.claims_disputed,
            "contradictions": r.contradictions,
            "recommended_action": r.recommended_action,
            "registry_source": r.registry_source,
            "registration_number": r.registration_number,
            "checks_run": [c.model_dump() for c in r.checks_run],
        }
        for r in results
    ]

    return {
        "production_id": production_id,
        "results": formatted,
    }


@router.get("/{production_id}/verification")
async def get_verifications_endpoint(production_id: str) -> Dict[str, Any]:
    """Retrieve all verification records for a production."""
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    ver_repo = get_verification_repo()
    results = await ver_repo.list_for_production(production_id)

    formatted = [
        {
            "verification_id": r.verification_id,
            "entity_id": r.entity_id,
            "entity_name": r.entity_name,
            "decision": r.decision.value if hasattr(r.decision, "value") else str(r.decision),
            "confidence": round(r.confidence, 2),
            "claims_supported": r.claims_supported,
            "claims_disputed": r.claims_disputed,
            "contradictions": r.contradictions,
            "recommended_action": r.recommended_action,
            "registry_source": r.registry_source,
            "registration_number": r.registration_number,
            "checks_run": [c.model_dump() for c in r.checks_run],
        }
        for r in results
    ]

    return {
        "production_id": production_id,
        "results": formatted,
    }


class ResolutionRequestPayload(BaseModel):
    entity_ids: Optional[List[str]] = Field(default=None, description="Optional subset of entity IDs to resolve")
    force_refresh: bool = Field(default=False, description="Bypass cache and force re-resolution")

@router.post("/{production_id}/resolution")
async def resolution_endpoint(
    production_id: str,
    payload: Optional[ResolutionRequestPayload] = None,
) -> Dict[str, Any]:
    """
    Execute Phase 7 Operational Resolution formulation for entities in a production.
    Translates verified findings, risks, and evidence into prioritized operational next steps.
    """
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    entity_repo = get_entity_repo()
    all_entities = await entity_repo.list_by_production(production_id)

    requested_ids = payload.entity_ids if payload and payload.entity_ids else None
    if requested_ids:
        id_set = set(requested_ids)
        target_entities = [e for e in all_entities if e.id in id_set]
    else:
        target_entities = all_entities

    from app.agents.resolution_agent import resolution_agent

    force = payload.force_refresh if payload else False
    results = await resolution_agent.resolve_entities(
        entities=target_entities,
        production_id=production_id,
        force_refresh=force,
    )

    formatted = [r.model_dump() for r in results]
    summary = {
        "total": len(results),
        "critical": sum(1 for r in results if r.priority.value == "CRITICAL"),
        "high": sum(1 for r in results if r.priority.value == "HIGH"),
        "action_required": sum(1 for r in results if r.resolution_status.value == "ACTION_REQUIRED"),
        "human_review": sum(1 for r in results if r.resolution_status.value == "HUMAN_REVIEW"),
        "resolved": sum(1 for r in results if r.resolution_status.value == "RESOLVED"),
        "more_evidence_required": sum(1 for r in results if r.resolution_status.value == "MORE_EVIDENCE_REQUIRED"),
        "research_required": sum(1 for r in results if r.resolution_status.value == "RESEARCH_REQUIRED"),
        "escalated": sum(1 for r in results if r.recommended_action.value == "ESCALATE"),
    }

    return {
        "production_id": production_id,
        "results": formatted,
        "summary": summary,
    }


@router.get("/{production_id}/resolution")
async def get_resolutions_endpoint(production_id: str) -> Dict[str, Any]:
    """Retrieve all Phase 7 resolution records for a production."""
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    res_repo = get_resolution_repo()
    results = await res_repo.list_for_production(production_id)

    # Sort according to operational priority hierarchy
    from app.agents.resolution_agent import resolution_agent
    sorted_results = sorted(results, key=resolution_agent._sort_key)

    formatted = [r.model_dump() for r in sorted_results]
    summary = {
        "total": len(sorted_results),
        "critical": sum(1 for r in sorted_results if r.priority.value == "CRITICAL"),
        "high": sum(1 for r in sorted_results if r.priority.value == "HIGH"),
        "action_required": sum(1 for r in sorted_results if r.resolution_status.value == "ACTION_REQUIRED"),
        "human_review": sum(1 for r in sorted_results if r.resolution_status.value == "HUMAN_REVIEW"),
        "resolved": sum(1 for r in sorted_results if r.resolution_status.value == "RESOLVED"),
        "more_evidence_required": sum(1 for r in sorted_results if r.resolution_status.value == "MORE_EVIDENCE_REQUIRED"),
        "research_required": sum(1 for r in sorted_results if r.resolution_status.value == "RESEARCH_REQUIRED"),
        "escalated": sum(1 for r in sorted_results if r.recommended_action.value == "ESCALATE"),
    }

    return {
        "production_id": production_id,
        "results": formatted,
        "summary": summary,
    }


@router.post("/{production_id}/footage")
async def upload_footage(
    production_id: str,
    file: Optional[UploadFile] = File(None),
    footage_path_override: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Upload or register captured video footage for a production."""
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    saved_path = ""
    if file:
        content = await file.read()
        filename = f"footage/{production_id}_{file.filename}"
        saved_path = await storage_service.save_file(filename, content)
    elif footage_path_override:
        saved_path = footage_path_override
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a footage file or footage_path_override must be provided",
        )

    production.footage_path = saved_path
    production.updated_at = datetime.now(timezone.utc)
    if production.script_path:
        production.status = ProductionStatus.READY_FOR_ANALYSIS
    await prod_repo.update(production)

    return {
        "status": "SUCCESS",
        "production_id": production_id,
        "footage_path": saved_path,
        "message": "Footage registered successfully",
    }


@router.post("/{production_id}/analyze", response_model=AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    production_id: str,
    background_tasks: BackgroundTasks,
) -> AnalysisJob:
    """Start an agentic pre-clearance intelligence analysis job."""
    prod_repo = get_production_repo()
    job_repo = get_job_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    job = AnalysisJob.create_new(production_id=production_id)
    saved_job = await job_repo.create(job)

    production.status = ProductionStatus.ANALYZING
    await prod_repo.update(production)

    # Launch pipeline execution asynchronously
    background_tasks.add_task(root_agent.execute_pipeline, production_id, saved_job.job_id)

    logger.info(f"[API] Triggered analysis job '{saved_job.job_id}' for production '{production_id}'")
    return saved_job


@router.get("/{production_id}/status")
async def get_production_status(production_id: str) -> Dict[str, Any]:
    """Get live production status, active jobs, and clearance summary counts."""
    prod_repo = get_production_repo()
    job_repo = get_job_repo()
    entity_repo = get_entity_repo()

    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    jobs = await job_repo.get_by_production(production_id)
    entities = await entity_repo.list_by_production(production_id)

    visual_only = [e for e in entities if e.classification.value == "VISUAL_ONLY"]
    high_risk = [e for e in entities if e.risk_level.value == "HIGH"]

    return {
        "production_id": production.id,
        "title": production.title,
        "status": production.status.value,
        "total_jobs": len(jobs),
        "latest_job": jobs[-1] if jobs else None,
        "total_entities": len(entities),
        "visual_only_count": len(visual_only),
        "high_risk_count": len(high_risk),
        "has_script": bool(production.script_path),
        "has_footage": bool(production.footage_path),
    }


@router.get("/{production_id}/frames")
async def get_production_frames(production_id: str) -> Dict[str, Any]:
    """
    Retrieve all candidate frames extracted for a production during visual ingestion.
    Allows real-time frame-by-frame visual inspection from the frontend interface.
    """
    prod_repo = get_production_repo()
    production = await prod_repo.get(production_id)
    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production '{production_id}' not found",
        )

    entity_repo = get_entity_repo()
    entities = await entity_repo.list_by_production(production_id)
    
    # Map entities to timestamps/frames for quick lookup
    entity_frame_map: Dict[str, List[Dict[str, Any]]] = {}
    for ent in entities:
        if ent.frame_path:
            norm_key = Path(ent.frame_path).name
            entity_frame_map.setdefault(norm_key, []).append({
                "entity_id": ent.id,
                "name": ent.name,
                "classification": ent.classification.value if hasattr(ent.classification, "value") else str(ent.classification),
                "risk_level": ent.risk_level.value if hasattr(ent.risk_level, "value") else str(ent.risk_level),
                "risk_score": ent.risk_score,
                "bounding_box": ent.bounding_box,
            })

    from pathlib import Path
    from app.core.config import settings
    import re

    base_storage = Path(settings.LOCAL_STORAGE_DIR)
    frames_dir = base_storage / "frames" / production_id

    found_frames: List[Dict[str, Any]] = []

    if frames_dir.exists():
        # Search all image files under production frames
        for img_path in sorted(frames_dir.rglob("*.jpg")):
            fname = img_path.name
            rel_to_storage = str(img_path.relative_to(base_storage)).replace("\\", "/")
            url = f"/storage/{rel_to_storage}"

            # Parse scene and timestamp from standard naming: scene03_00027.jpg
            scene_num = 1
            ts = 0.0
            scene_match = re.search(r"scene(\d+)", fname, re.IGNORECASE)
            if scene_match:
                scene_num = int(scene_match.group(1))

            ts_match = re.search(r"_(\d+)\.jpg", fname, re.IGNORECASE)
            if ts_match:
                ts = round(int(ts_match.group(1)) / 10.0, 2)

            detected_entities = entity_frame_map.get(fname, [])

            found_frames.append({
                "frame_id": fname.replace(".jpg", ""),
                "filename": fname,
                "scene_number": scene_num,
                "timestamp": ts,
                "url": url,
                "relative_path": rel_to_storage,
                "detected_entities": detected_entities,
                "entity_count": len(detected_entities),
            })

    # Sort frames chronologically by timestamp
    found_frames.sort(key=lambda x: (x["scene_number"], x["timestamp"]))

    return {
        "production_id": production_id,
        "total_frames": len(found_frames),
        "frames": found_frames,
    }


