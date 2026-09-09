import {
  Production,
  AnalysisJob,
  Entity,
  Evidence,
  ClearanceRequest,
  Report,
  ReportResult,
  GenerateReportPayload,
  VerificationResult,
  ResolutionResult,
  ResolutionSummary,
  OrchestrationResult,
  OrchestrationPayload,
  AvailableVideo,
  ExtractedFrameItem,
} from '../types';

const API_BASE = '';


export const api = {
  async getHealth(): Promise<{ status: string; service: string; version: string }> {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
  },

  async createProduction(payload: {
    title: string;
    description?: string;
    director?: string;
    studio?: string;
    budget_tier?: string;
  }): Promise<Production> {
    const res = await fetch(`${API_BASE}/productions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to create production');
    return res.json();
  },

  async getProduction(id: string): Promise<Production> {
    const res = await fetch(`${API_BASE}/productions/${id}`);
    if (!res.ok) throw new Error(`Failed to fetch production ${id}`);
    return res.json();
  },

  async uploadScriptText(productionId: string, scriptText: string): Promise<any> {
    const formData = new FormData();
    formData.append('script_text', scriptText);
    const res = await fetch(`${API_BASE}/productions/${productionId}/script`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to upload screenplay');
    return res.json();
  },

  async registerFootage(productionId: string, footagePath: string): Promise<any> {
    const formData = new FormData();
    formData.append('footage_path_override', footagePath);
    const res = await fetch(`${API_BASE}/productions/${productionId}/footage`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to register footage');
    return res.json();
  },

  async uploadFootageFile(productionId: string, file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/productions/${productionId}/footage`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to upload footage file');
    return res.json();
  },

  async startAnalysis(productionId: string): Promise<AnalysisJob> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/analyze`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to start analysis job');
    return res.json();
  },

  async cancelAnalysis(productionId: string, jobId: string): Promise<AnalysisJob> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/analysis/${jobId}/cancel`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to cancel analysis job');
    return res.json();
  },

  async getProductionStatus(productionId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/status`);
    if (!res.ok) throw new Error('Failed to fetch status');
    return res.json();
  },

  async getEntities(productionId: string, filters?: { classification?: string; risk_level?: string }): Promise<Entity[]> {
    const params = new URLSearchParams();
    if (filters?.classification) params.append('classification', filters.classification);
    if (filters?.risk_level) params.append('risk_level', filters.risk_level);

    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/productions/${productionId}/entities${query}`);
    if (!res.ok) throw new Error('Failed to fetch entities');
    return res.json();
  },

  async getEvidence(productionId: string, entityId?: string): Promise<Evidence[]> {
    const url = entityId
      ? `${API_BASE}/productions/${productionId}/evidence?entity_id=${entityId}`
      : `${API_BASE}/productions/${productionId}/evidence`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch evidence');
    return res.json();
  },

  async getRequests(productionId: string): Promise<ClearanceRequest[]> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/requests`);
    if (!res.ok) throw new Error('Failed to fetch clearance requests');
    return res.json();
  },

  async getReport(productionId: string): Promise<Report> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/report`);
    if (!res.ok) throw new Error('Failed to fetch audit report');
    return res.json();
  },

  async verifyEntities(productionId: string, payload?: { entity_ids?: string[]; force_refresh?: boolean }): Promise<{ production_id: string; results: VerificationResult[] }> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/verification`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) throw new Error('Failed to execute verification');
    return res.json();
  },

  async getVerifications(productionId: string): Promise<{ production_id: string; results: VerificationResult[] }> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/verification`);
    if (!res.ok) throw new Error('Failed to fetch verifications');
    return res.json();
  },

  async resolveEntities(productionId: string, payload?: { entity_ids?: string[]; force_refresh?: boolean }): Promise<{ production_id: string; results: ResolutionResult[]; summary: ResolutionSummary }> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/resolution`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) throw new Error('Failed to execute resolution formulation');
    return res.json();
  },

  async getResolutions(productionId: string): Promise<{ production_id: string; results: ResolutionResult[]; summary: ResolutionSummary }> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/resolution`);
    if (!res.ok) throw new Error('Failed to fetch resolutions');
    return res.json();
  },

  async generateProductionReport(productionId: string, payload?: GenerateReportPayload): Promise<ReportResult> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) throw new Error('Failed to generate clearance intelligence report');
    return res.json();
  },

  async getProductionReportResult(productionId: string): Promise<ReportResult> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/report/result`);
    if (!res.ok) throw new Error('Failed to fetch clearance report result');
    return res.json();
  },

  getReportHtmlUrl(productionId: string, reportId?: string): string {
    return reportId
      ? `${API_BASE}/productions/${productionId}/report/${reportId}/html`
      : `${API_BASE}/productions/${productionId}/report/html`;
  },

  getReportPdfUrl(productionId: string, reportId?: string): string {
    return reportId
      ? `${API_BASE}/productions/${productionId}/report/${reportId}/pdf`
      : `${API_BASE}/productions/${productionId}/report/pdf`;
  },

  async runOrchestration(productionId: string, payload?: OrchestrationPayload): Promise<OrchestrationResult> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/orchestrate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) throw new Error('Failed to run autonomous orchestration');
    return res.json();
  },

  async getLatestOrchestration(productionId: string): Promise<OrchestrationResult> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/orchestrate`);
    if (!res.ok) throw new Error('Failed to fetch latest orchestration result');
    return res.json();
  },

  async getOrchestration(productionId: string, workflowId: string): Promise<OrchestrationResult> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/orchestrate/${workflowId}`);
    if (!res.ok) throw new Error('Failed to fetch orchestration result');
    return res.json();
  },

  async getAvailableVideos(): Promise<AvailableVideo[]> {
    const res = await fetch(`${API_BASE}/productions/available-videos`);
    if (!res.ok) throw new Error('Failed to fetch available videos');
    return res.json();
  },

  async getExtractedFrames(productionId: string): Promise<{ production_id: string; total_frames: number; frames: ExtractedFrameItem[] }> {
    const res = await fetch(`${API_BASE}/productions/${productionId}/frames`);
    if (!res.ok) throw new Error('Failed to fetch extracted frames');
    return res.json();
  },
};

