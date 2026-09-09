export type EventType =
  | 'ANALYSIS_STARTED'
  | 'STAGE_STARTED'
  | 'STAGE_COMPLETED'
  | 'VIDEO_INGESTION_STARTED'
  | 'VIDEO_METADATA_EXTRACTED'
  | 'VIDEO_INGESTION_COMPLETED'
  | 'SCENE_DETECTION_STARTED'
  | 'SCENE_DETECTED'
  | 'SCENE_DETECTION_COMPLETED'
  | 'FRAME_EXTRACTION_STARTED'
  | 'FRAME_EXTRACTED'
  | 'FRAME_EXTRACTION_COMPLETED'
  | 'OCR_STARTED'
  | 'OCR_COMPLETED'
  | 'OBJECT_DETECTION_STARTED'
  | 'OBJECT_DETECTED'
  | 'OBJECT_DETECTION_COMPLETED'
  | 'FRAME_RANKED'
  | 'FRAME_SELECTED_FOR_VISION'
  | 'VISION_ANALYSIS_STARTED'
  | 'VISION_ANALYSIS_COMPLETED'
  | 'ENTITY_DETECTED'
  | 'ENTITY_ADDED'
  | 'ENTITY_DEDUPLICATED'
  | 'VISUAL_ONLY_DISCOVERED'
  | 'RESEARCH_STARTED'
  | 'RESEARCH_COMPLETED'
  | 'RISK_ASSESSMENT_STARTED'
  | 'RISK_SIGNAL_CALCULATED'
  | 'RISK_CALCULATED'
  | 'RISK_ASSESSMENT_COMPLETED'
  | 'RISK_ASSESSMENT_FAILED'
  | 'VERIFICATION_STARTED'
  | 'VERIFICATION_CHECK_COMPLETED'
  | 'VERIFICATION_CONTRADICTION_FOUND'
  | 'VERIFICATION_COMPLETED'
  | 'VERIFICATION_FAILED'
  | 'RESOLUTION_STARTED'
  | 'RESOLUTION_ACTION_RECOMMENDED'
  | 'RESOLUTION_ESCALATED'
  | 'RESOLUTION_COMPLETED'
  | 'RESOLUTION_FAILED'
  | 'REPORT_GENERATION_STARTED'
  | 'REPORT_SECTION_GENERATED'
  | 'REPORT_GENERATION_COMPLETED'
  | 'REPORT_GENERATION_FAILED'
  | 'REPORT_GENERATED'
  | 'ORCHESTRATION_STARTED'
  | 'AGENT_STARTED'
  | 'AGENT_COMPLETED'
  | 'AGENT_FAILED'
  | 'TOOL_STARTED'
  | 'TOOL_COMPLETED'
  | 'ORCHESTRATION_COMPLETED'
  | 'ORCHESTRATION_FAILED'
  | 'ANALYSIS_COMPLETED'
  | 'ANALYSIS_FAILED'
  | 'ANALYSIS_CANCELLED';

export type PipelineStage =
  | 'Screenplay Extraction'
  | 'Video Ingestion'
  | 'Scene Detection'
  | 'OCR'
  | 'Object Detection'
  | 'Gemini Vision'
  | 'Entity Merge'
  | 'Parallel Research'
  | 'Risk Assessment'
  | 'Verification'
  | 'Resolution'
  | 'Report Generation';

export type JobStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
export type StageStatus = 'WAITING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface StageState {
  stage: string;
  status: StageStatus;
  started_at?: string;
  completed_at?: string;
  progress: number;
  latest_event?: string;
  duration_ms?: number;
}

export interface ProcessingEvent {
  event_id: string;
  sequence_number?: number;
  production_id: string;
  job_id: string;
  event_type: EventType;
  stage?: PipelineStage;
  timestamp: string;
  progress: number;
  message: string;
  scene_number?: number;
  video_timestamp?: number;
  entity_id?: string;
  entity_name?: string;
  entity_type?: string;
  confidence?: number;
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
  risk_score?: number;
  verification_decision?: string;
  verification_confidence?: number;
  resolution_id?: string;
  resolution_status?: string;
  resolution_action?: string;
  resolution_priority?: string;
  frame_path?: string;
  report_id?: string;
  report_section?: string;
  report_format?: string;
  workflow_id?: string;
  agent_name?: string;
  tool_name?: string;
  agent_status?: string;
  duration_seconds?: number;
  metadata?: Record<string, any>;
}

export interface Production {
  id: string;
  title: string;
  description?: string;
  director?: string;
  studio?: string;
  budget_tier?: string;
  script_path?: string;
  footage_path?: string;
  status: 'DRAFT' | 'READY_FOR_ANALYSIS' | 'ANALYZING' | 'COMPLETED' | 'FAILED';
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface AnalysisJob {
  job_id: string;
  production_id: string;
  status: JobStatus;
  current_stage?: string;
  progress: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
  frames_processed: number;
  scenes_detected: number;
  entities_detected: number;
  visual_only_count: number;
  research_completed: number;
  verification_completed: number;
  stages: Record<string, StageState>;
}

export type EntityClassification = 'BOTH' | 'SCRIPT_ONLY' | 'VISUAL_ONLY' | 'AUDIO_ONLY';

export interface Entity {
  id: string;
  production_id: string;
  job_id?: string;
  name: string;
  entity_type: string;
  sources: ('SCRIPT' | 'VISUAL' | 'AUDIO')[];
  classification?: EntityClassification;
  confidence: number;
  scene?: number;
  timestamp?: number;
  context?: string;
  frame_path?: string;
  bounding_box?: [number, number, number, number];
  appearances?: number;
  clearance_type: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
  risk_score: number;
  rights_holder?: string;
  evidence_ids: string[];
  verification_status: 'PENDING' | 'UNVERIFIED' | 'CONFIRMED' | 'DISPUTED' | 'INCONCLUSIVE';
  verification_id?: string;
  verification_decision?: VerificationDecision;
  verification_confidence?: number;
  resolution_id?: string;
  resolution_status?: string;
  resolution_action?: string;
  resolution_priority?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  created_at: string;
  metadata?: Record<string, any>;
}

export interface Evidence {
  id: string;
  production_id: string;
  entity_id?: string;
  job_id?: string;
  evidence_type: string;
  timestamp?: number;
  scene_number?: number;
  frame_path?: string;
  ocr_text?: string;
  bounding_box?: [number, number, number, number];
  confidence: number;
  created_at: string;
  metadata?: Record<string, any>;
}

export interface RiskFactor {
  category: string;
  description: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
  weight: number;
  mitigating_factors: string[];
}

export interface RiskAssessment {
  id: string;
  entity_id: string;
  production_id: string;
  overall_risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
  risk_score: number;
  factors: RiskFactor[];
  legal_analysis: string;
  recommended_action: string;
  evaluated_at: string;
}

export type VerificationDecision = 'CONFIRMED' | 'REVIEW' | 'REJECTED' | 'INSUFFICIENT_EVIDENCE';

export interface VerificationCheck {
  check_id: string;
  name: string;
  passed: boolean;
  evidence_evaluated: string[];
  explanation: string;
  severity_if_failed: 'HIGH' | 'MEDIUM' | 'LOW';
  timestamp: string;
}

export interface VerificationResult {
  id?: string;
  verification_id?: string;
  entity_id: string;
  production_id: string;
  entity_name?: string;
  decision: VerificationDecision;
  confidence: number;
  checks_run: VerificationCheck[];
  claims_supported: string[];
  claims_disputed: string[];
  contradictions: string[];
  recommended_action: string;
  verified_at: string;
  registry_source?: string;
  registration_number?: string;
  notes?: string;
  rights_holder?: string;
  match_confidence?: number;
  license_required?: boolean;
  status?: 'PENDING' | 'UNVERIFIED' | 'CONFIRMED' | 'DISPUTED' | 'INCONCLUSIVE';
  metadata?: Record<string, any>;
}

export interface ClearanceRequest {
  id: string;
  production_id: string;
  entity_id: string;
  action_type: string;
  status: 'PENDING_REVIEW' | 'IN_PROGRESS' | 'APPROVED' | 'REJECTED' | 'RESOLVED';
  assigned_to?: string;
  rights_holder_contact?: string;
  estimated_license_fee?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface Report {
  id: string;
  production_id: string;
  job_id: string;
  title: string;
  executive_summary: string;
  total_entities: number;
  visual_only_count: number;
  script_only_count: number;
  both_count: number;
  audio_only_count: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  unresolved_count: number;
  entity_breakdown: any[];
  clearance_checklist: any[];
  generated_at: string;
}

export type ResolutionStatus =
  | 'RESOLVED'
  | 'ACTION_REQUIRED'
  | 'HUMAN_REVIEW'
  | 'MORE_EVIDENCE_REQUIRED'
  | 'RESEARCH_REQUIRED'
  | 'REPLACEMENT_RECOMMENDED'
  | 'ESCALATED'
  | 'UNRESOLVED'
  | 'PENDING';

export type ResolutionAction =
  | 'NO_ACTION'
  | 'HUMAN_REVIEW'
  | 'COLLECT_EVIDENCE'
  | 'CONDUCT_RESEARCH'
  | 'REQUEST_RIGHTS_INFORMATION'
  | 'REQUEST_LICENSE_INFORMATION'
  | 'REVIEW_MUSIC_USAGE'
  | 'REVIEW_BRAND_USAGE'
  | 'REVIEW_LOCATION_USAGE'
  | 'REVIEW_ARTWORK_USAGE'
  | 'REVIEW_PUBLIC_FIGURE_USAGE'
  | 'CONSIDER_REPLACEMENT'
  | 'ESCALATE';

export type ResolutionPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export interface ResolutionResult {
  id?: string;
  resolution_id: string;
  entity_id: string;
  production_id: string;
  job_id?: string;
  entity_name: string;
  entity_type: string;
  verification_decision?: string;
  risk_level: string;
  risk_score: number;
  resolution_status: ResolutionStatus;
  recommended_action: ResolutionAction;
  priority: ResolutionPriority;
  action_reason: string;
  supporting_evidence_ids: string[];
  missing_evidence: string[];
  required_information: string[];
  research_action?: string;
  replacement_suggestion?: string;
  confidence: number;
  resolver: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface ResolutionSummary {
  total: number;
  critical: number;
  high: number;
  action_required: number;
  human_review: number;
  resolved: number;
  more_evidence_required: number;
  research_required: number;
  escalated: number;
}

export type ReportStatus = 'GENERATING' | 'COMPLETED' | 'PARTIAL' | 'FAILED';
export type ReportFormat = 'JSON' | 'HTML' | 'PDF';

export interface ReportFinding {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  classification: string;
  risk_level: string;
  risk_score: number;
  risk_factors: string[];
  scene_number?: number;
  timestamp_start?: number;
  timestamp_end?: number;
  rights_holder?: string;
  verification_decision?: string;
  verification_confidence?: number;
  verification_rationale?: string;
  resolution_status?: string;
  resolution_action?: string;
  resolution_priority?: string;
  resolution_owner?: string;
  resolution_cost_estimate?: string;
  resolution_time_estimate?: string;
  resolution_details?: string;
  evidence_count: number;
  evidence_snippets: Array<{
    evidence_id: string;
    evidence_type: string;
    confidence: number;
    text_content?: string;
    bounding_box?: any;
    timestamp?: number;
    frame_path?: string;
  }>;
  evidence_chain: {
    stage_1_detection?: any;
    stage_2_visual_evidence?: any;
    stage_3_screenplay_evidence?: any;
    stage_4_research?: any;
    stage_5_risk?: any;
    stage_6_verification?: any;
    stage_7_resolution?: any;
  };
  metadata?: Record<string, any>;
}

export interface ReportResult {
  report_id: string;
  production_id: string;
  job_id: string;
  production_title: string;
  version: string;
  status: ReportStatus;
  generated_at: string;
  generation_duration_ms: number;
  total_entities: number;
  researched_count: number;
  verified_count: number;
  resolved_count: number;
  research_coverage: number;
  verification_coverage: number;
  resolution_coverage: number;
  classification_counts: Record<string, number>;
  risk_distribution: Record<string, number>;
  verification_distribution: Record<string, number>;
  resolution_distribution: Record<string, number>;
  priority_findings: ReportFinding[];
  visual_only_findings: ReportFinding[];
  all_findings: ReportFinding[];
  formats: ReportFormat[];
  format_paths: Record<string, string>;
  format_urls: Record<string, string>;
  format_errors: Record<string, string>;
  executive_summary: string;
  disclaimer: string;
  metadata?: Record<string, any>;
}

export interface GenerateReportPayload {
  formats?: ReportFormat[];
  force_refresh?: boolean;
  version?: string;
}

// =============================================================================
// Phase 9: Google ADK Orchestration Types
// =============================================================================

export type WorkflowStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'PARTIAL'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type AgentStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'SKIPPED'
  | 'BLOCKED';

export interface WorkflowSummary {
  detection: Record<string, any>;
  research: Record<string, any>;
  risk: Record<string, any>;
  verification: Record<string, any>;
  resolution: Record<string, any>;
  reporting: Record<string, any>;
}

export interface OrchestrationResult {
  workflow_id: string;
  production_id: string;
  job_id: string;
  status: WorkflowStatus;
  current_agent?: string;
  completed_agents: string[];
  failed_agents: string[];
  blocked_agents: string[];
  skipped_agents: string[];
  entity_ids: string[];
  evidence_ids: string[];
  report_id?: string;
  warnings: string[];
  errors: string[];
  started_at: string;
  completed_at?: string;
  duration: number;
  workflow_summary?: WorkflowSummary;
  agent_durations: Record<string, number>;
  agent_outputs: Record<string, any>;
}

export interface OrchestrationPayload {
  job_id?: string;
  force_refresh?: boolean;
  mode?: 'offline' | 'live';
  video_path?: string;
  research_provider?: string;
}

export interface AvailableVideo {
  filename: string;
  path: string;
  url: string;
  size_bytes: number;
  size_mb: number;
  is_recommended: boolean;
  description: string;
}

export interface ExtractedFrameItem {
  frame_id: string;
  filename: string;
  scene_number: number;
  timestamp: number;
  url: string;
  relative_path: string;
  detected_entities: {
    entity_id: string;
    name: string;
    classification: string;
    risk_level: string;
    risk_score: number;
    bounding_box?: number[];
  }[];
  entity_count: number;
}


