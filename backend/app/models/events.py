from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
import json
from pydantic import BaseModel, Field

class EventType(str, Enum):
    ANALYSIS_STARTED = "ANALYSIS_STARTED"
    STAGE_STARTED = "STAGE_STARTED"
    STAGE_COMPLETED = "STAGE_COMPLETED"
    SCREENPLAY_ANALYSIS_STARTED = "SCREENPLAY_ANALYSIS_STARTED"
    SCREENPLAY_SCENE_DETECTED = "SCREENPLAY_SCENE_DETECTED"
    SCREENPLAY_ENTITY_EXTRACTED = "SCREENPLAY_ENTITY_EXTRACTED"
    SCREENPLAY_ANALYSIS_COMPLETED = "SCREENPLAY_ANALYSIS_COMPLETED"
    SCREENPLAY_ANALYSIS_FAILED = "SCREENPLAY_ANALYSIS_FAILED"
    VIDEO_INGESTION_STARTED = "VIDEO_INGESTION_STARTED"
    VIDEO_METADATA_EXTRACTED = "VIDEO_METADATA_EXTRACTED"
    VIDEO_INGESTION_COMPLETED = "VIDEO_INGESTION_COMPLETED"
    SCENE_DETECTION_STARTED = "SCENE_DETECTION_STARTED"
    SCENE_DETECTED = "SCENE_DETECTED"
    SCENE_DETECTION_COMPLETED = "SCENE_DETECTION_COMPLETED"
    FRAME_EXTRACTION_STARTED = "FRAME_EXTRACTION_STARTED"
    FRAME_EXTRACTED = "FRAME_EXTRACTED"
    FRAME_EXTRACTION_COMPLETED = "FRAME_EXTRACTION_COMPLETED"
    OCR_STARTED = "OCR_STARTED"
    OCR_COMPLETED = "OCR_COMPLETED"
    OBJECT_DETECTION_STARTED = "OBJECT_DETECTION_STARTED"
    OBJECT_DETECTED = "OBJECT_DETECTED"
    OBJECT_DETECTION_COMPLETED = "OBJECT_DETECTION_COMPLETED"
    FRAME_RANKED = "FRAME_RANKED"
    FRAME_SELECTED_FOR_VISION = "FRAME_SELECTED_FOR_VISION"
    VISION_ANALYSIS_STARTED = "VISION_ANALYSIS_STARTED"
    VISION_ANALYSIS_COMPLETED = "VISION_ANALYSIS_COMPLETED"
    ENTITY_DETECTED = "ENTITY_DETECTED"
    ENTITY_ADDED = "ENTITY_ADDED"
    ENTITY_DEDUPLICATED = "ENTITY_DEDUPLICATED"
    VISUAL_ONLY_DISCOVERED = "VISUAL_ONLY_DISCOVERED"
    RESEARCH_STARTED = "RESEARCH_STARTED"
    RESEARCH_QUERY_BUILT = "RESEARCH_QUERY_BUILT"
    RESEARCH_RESULT_RECEIVED = "RESEARCH_RESULT_RECEIVED"
    RESEARCH_EVIDENCE_FOUND = "RESEARCH_EVIDENCE_FOUND"
    RESEARCH_COMPLETED = "RESEARCH_COMPLETED"
    RESEARCH_FAILED = "RESEARCH_FAILED"
    RISK_ASSESSMENT_STARTED = "RISK_ASSESSMENT_STARTED"
    RISK_SIGNAL_CALCULATED = "RISK_SIGNAL_CALCULATED"
    RISK_CALCULATED = "RISK_CALCULATED"
    RISK_ASSESSMENT_COMPLETED = "RISK_ASSESSMENT_COMPLETED"
    RISK_ASSESSMENT_FAILED = "RISK_ASSESSMENT_FAILED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_CHECK_COMPLETED = "VERIFICATION_CHECK_COMPLETED"
    VERIFICATION_CONTRADICTION_FOUND = "VERIFICATION_CONTRADICTION_FOUND"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    RESOLUTION_STARTED = "RESOLUTION_STARTED"
    RESOLUTION_ACTION_RECOMMENDED = "RESOLUTION_ACTION_RECOMMENDED"
    RESOLUTION_ESCALATED = "RESOLUTION_ESCALATED"
    RESOLUTION_COMPLETED = "RESOLUTION_COMPLETED"
    RESOLUTION_FAILED = "RESOLUTION_FAILED"
    REPORT_GENERATION_STARTED = "REPORT_GENERATION_STARTED"
    REPORT_SECTION_GENERATED = "REPORT_SECTION_GENERATED"
    REPORT_GENERATION_COMPLETED = "REPORT_GENERATION_COMPLETED"
    REPORT_GENERATION_FAILED = "REPORT_GENERATION_FAILED"
    REPORT_GENERATED = "REPORT_GENERATED"
    # Phase 10-12 Events
    FINANCIAL_EXPOSURE_CALCULATED = "FINANCIAL_EXPOSURE_CALCULATED"
    OUTREACH_DRAFTED = "OUTREACH_DRAFTED"
    OUTREACH_APPROVED = "OUTREACH_APPROVED"
    REMEDIATION_PROPOSED = "REMEDIATION_PROPOSED"
    REMEDIATION_COMPLETED = "REMEDIATION_COMPLETED"
    # Phase 9: Google ADK Orchestration Events
    ORCHESTRATION_STARTED = "ORCHESTRATION_STARTED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    ORCHESTRATION_COMPLETED = "ORCHESTRATION_COMPLETED"
    ORCHESTRATION_FAILED = "ORCHESTRATION_FAILED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    ANALYSIS_CANCELLED = "ANALYSIS_CANCELLED"

class PipelineStage(str, Enum):
    SCREENPLAY_EXTRACTION = "Screenplay Extraction"
    VIDEO_INGESTION = "Video Ingestion"
    SCENE_DETECTION = "Scene Detection"
    OCR = "OCR"
    OBJECT_DETECTION = "Object Detection"
    GEMINI_VISION = "Gemini Vision"
    ENTITY_MERGE = "Entity Merge"
    PARALLEL_RESEARCH = "Parallel Research"
    RISK_ASSESSMENT = "Risk Assessment"
    VERIFICATION = "Verification"
    RESOLUTION = "Resolution"
    FINANCIAL_EXPOSURE = "Financial Exposure"
    CLEARANCE_OUTREACH = "Clearance Outreach"
    VISUAL_REMEDIATION = "Visual Remediation"
    REPORT_GENERATION = "Report Generation"

class ProcessingEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    sequence_number: int = 0
    production_id: str
    job_id: str
    event_type: EventType
    stage: Optional[PipelineStage] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    progress: float = 0.0
    message: str
    scene_number: Optional[int] = None
    video_timestamp: Optional[float] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None
    confidence: Optional[float] = None
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    verification_decision: Optional[str] = None
    verification_confidence: Optional[float] = None
    resolution_id: Optional[str] = None
    resolution_status: Optional[str] = None
    resolution_action: Optional[str] = None
    resolution_priority: Optional[str] = None
    frame_path: Optional[str] = None
    report_id: Optional[str] = None
    report_section: Optional[str] = None
    report_format: Optional[str] = None
    workflow_id: Optional[str] = None
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    agent_status: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump()
        data["timestamp"] = self.timestamp.isoformat()
        if self.event_type:
            data["event_type"] = self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type)
        if self.stage:
            data["stage"] = self.stage.value if hasattr(self.stage, "value") else str(self.stage)
        return data

    def to_sse_message(self) -> str:
        """Serialize event to standard SSE wire format"""
        payload = json.dumps(self.to_dict(), default=str)
        event_name = self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type)
        return f"event: {event_name}\ndata: {payload}\nid: {self.event_id}\n\n"
