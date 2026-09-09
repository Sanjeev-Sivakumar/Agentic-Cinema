import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Boxes,
  ShieldAlert,
  Search,
  Scale,
  FileText,
  Eye,
  Activity,
  ChevronRight,
  Terminal,
  Layers,
  Sparkles,
  Info,
  CheckCircle,
  XCircle,
  ExternalLink,
  Download,
  Film,
} from 'lucide-react';
import {
  Production,
  OrchestrationResult,
  WorkflowStatus,
  AgentStatus,
  ProcessingEvent,
  AvailableVideo,
  ExtractedFrameItem,
} from '../types';
import { api } from '../services/api';
import { FrameInspector } from '../components/video/FrameInspector';


interface OrchestrationProps {
  currentProduction: Production | null;
}

interface AgentNodeInfo {
  id: string;
  name: string;
  role: string;
  responsibility: string;
  toolName: string;
  icon: React.ReactNode;
}

const AGENT_NODES: AgentNodeInfo[] = [
  {
    id: 'screenplay',
    name: 'Screenplay Agent',
    role: 'Script Clearance',
    responsibility: 'Segments scenes and deterministically extracts candidate brands, trademarks, and copyright mentions from screenplay tokens.',
    toolName: 'analyze_screenplay_tool',
    icon: <FileText className="w-5 h-5 text-indigo-400" />,
  },
  {
    id: 'visual',
    name: 'Visual Agent',
    role: 'Footage Intelligence',
    responsibility: 'Coordinates real multi-modal video ingestion, scene detection, OCR, YOLOv8 object recognition, and Gemini Vision.',
    toolName: 'analyze_visual_tool',
    icon: <Eye className="w-5 h-5 text-cyan-400" />,
  },
  {
    id: 'merge',
    name: 'Entity Merge',
    role: 'Screenplay Comparison',
    responsibility: 'Synchronizes screenplay tokens with video discoveries to isolate high-exposure VISUAL_ONLY unscripted findings.',
    toolName: 'merge_entities_tool',
    icon: <Layers className="w-5 h-5 text-violet-400" />,
  },
  {
    id: 'research',
    name: 'Research Agent',
    role: 'Registry Corroboration',
    responsibility: 'Queries trademark and copyright registries to identify candidate rights holders without hallucinating legal ownership.',
    toolName: 'research_entities_tool',
    icon: <Search className="w-5 h-5 text-blue-400" />,
  },
  {
    id: 'risk',
    name: 'Risk Agent',
    role: 'Deterministic Triage',
    responsibility: 'Executes the multi-factor RiskEngine to assign objective clearance exposure scores (LOW / MEDIUM / HIGH / UNKNOWN).',
    toolName: 'assess_risk_tool',
    icon: <ShieldAlert className="w-5 h-5 text-amber-400" />,
  },
  {
    id: 'verification',
    name: 'Verification Agent',
    role: 'Adversarial Verification',
    responsibility: 'Challenges research and risk findings against real visual evidence, registry corroboration, and screenplay alignment.',
    toolName: 'verify_entities_tool',
    icon: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
  },
  {
    id: 'resolution',
    name: 'Resolution Agent',
    role: 'Action & Review Boundary',
    responsibility: 'Recommends operational workflows (License, Blur, Replace, Escalate) and enforces strict HUMAN_REVIEW terminal boundaries.',
    toolName: 'resolve_entities_tool',
    icon: <Scale className="w-5 h-5 text-amber-400" />,
  },
  {
    id: 'report',
    name: 'Report Agent',
    role: 'Audit Synthesis',
    responsibility: 'Compiles full upstream intelligence into evidence-traceable JSON, HTML, and ReportLab PDF clearance audit reports.',
    toolName: 'generate_report_tool',
    icon: <FileText className="w-5 h-5 text-rose-400" />,
  },
];

export const Orchestration: React.FC<OrchestrationProps> = ({ currentProduction }) => {
  const [orchestration, setOrchestration] = useState<OrchestrationResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [mode, setMode] = useState<'offline' | 'live'>('live');
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('screenplay');
  const [logs, setLogs] = useState<string[]>([]);
  const [availableVideos, setAvailableVideos] = useState<AvailableVideo[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<string>('test_video1.mp4');
  const [extractedFrames, setExtractedFrames] = useState<ExtractedFrameItem[]>([]);
  const [showFrameInspector, setShowFrameInspector] = useState<boolean>(true);

  const productionId = currentProduction?.id || 'prod_demo';

  // Load available videos and frames on mount
  useEffect(() => {
    api.getAvailableVideos()
      .then((vids) => {
        setAvailableVideos(vids);
        if (vids.length > 0) {
          const rec = vids.find((v) => v.is_recommended);
          if (rec) setSelectedVideo(rec.filename);
          else setSelectedVideo(vids[0].filename);
        }
      })
      .catch(() => {});

    if (productionId) {
      api.getLatestOrchestration(productionId)
        .then((res) => setOrchestration(res))
        .catch(() => {});

      api.getExtractedFrames(productionId)
        .then((res) => {
          if (res?.frames) setExtractedFrames(res.frames);
        })
        .catch(() => {});
    }
  }, [productionId]);

  const handleRunOrchestration = async () => {
    setLoading(true);
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [
      `[${timestamp}] ROOT AGENT: Autonomous clearance orchestration triggered (Video: ${selectedVideo} | Mode: ${mode.toUpperCase()} | Research: PARALLEL)`,
      ...prev,
    ]);

    try {
      const res = await api.runOrchestration(productionId, {
        force_refresh: forceRefresh,
        mode: mode,
        video_path: selectedVideo,
        research_provider: 'parallel',
      });
      setOrchestration(res);
      setLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] ROOT AGENT: Completed workflow ${res.workflow_id} (${res.status}) in ${res.duration}s`,
        ...prev,
      ]);

      // Refresh extracted frames for visual frame-by-frame inspector
      api.getExtractedFrames(productionId)
        .then((f) => {
          if (f?.frames) setExtractedFrames(f.frames);
        })
        .catch(() => {});
    } catch (err: any) {
      setLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] ROOT AGENT ERROR: ${err.message || 'Execution failed'}`,
        ...prev,
      ]);
    } finally {
      setLoading(false);
    }
  };


  const getNodeStatus = (nodeId: string): AgentStatus => {
    if (!orchestration) return 'PENDING';
    if (orchestration.status === 'RUNNING') {
      if (orchestration.current_agent?.toLowerCase().includes(nodeId)) return 'RUNNING';
    }
    if (orchestration.failed_agents?.includes(nodeId)) return 'FAILED';
    if (orchestration.blocked_agents?.includes(nodeId)) return 'BLOCKED';
    if (orchestration.skipped_agents?.includes(nodeId)) return 'SKIPPED';
    if (orchestration.completed_agents?.includes(nodeId)) return 'COMPLETED';
    if (nodeId === 'merge' && (orchestration.completed_agents.includes('screenplay') || orchestration.completed_agents.includes('visual'))) {
      return 'COMPLETED';
    }
    return 'PENDING';
  };

  const getStatusBadge = (status: AgentStatus) => {
    switch (status) {
      case 'COMPLETED':
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle className="w-3 h-3" /> COMPLETED
          </span>
        );
      case 'RUNNING':
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 animate-pulse">
            <Activity className="w-3 h-3 animate-spin" /> RUNNING
          </span>
        );
      case 'FAILED':
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
            <XCircle className="w-3 h-3" /> FAILED
          </span>
        );
      case 'BLOCKED':
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-3 h-3" /> BLOCKED
          </span>
        );
      case 'SKIPPED':
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            SKIPPED
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-500 border border-slate-800">
            PENDING
          </span>
        );
    }
  };

  const selectedNode = AGENT_NODES.find((n) => n.id === selectedAgentId) || AGENT_NODES[0];
  const summary = orchestration?.workflow_summary;

  return (
    <div className="p-6 space-y-6 text-slate-200 min-h-screen bg-[#070a12]">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-[#1e293b]">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              PHASE 9
            </span>
            <span className="text-xs font-mono text-slate-400">GOOGLE AGENT DEVELOPMENT KIT</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2 mt-1">
            <Cpu className="w-6 h-6 text-cyan-400" />
            AUTONOMOUS CLEARANCE ORCHESTRATOR
          </h1>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Google ADK Agent Runtime • Root Orchestrator & Multi-Agent Clearance DAG
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Video Selector */}
          <div className="flex items-center gap-2 bg-[#0e1320] border border-[#1e293b] rounded px-3 py-1.5 text-xs font-mono">
            <Film className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span className="text-slate-400 hidden sm:inline">INPUT VIDEO:</span>
            <select
              value={selectedVideo}
              onChange={(e) => setSelectedVideo(e.target.value)}
              className="bg-transparent text-amber-300 font-semibold focus:outline-none cursor-pointer"
            >
              {availableVideos.length > 0 ? (
                availableVideos.map((v) => (
                  <option key={v.filename} value={v.filename} className="bg-[#0e1320] text-slate-200">
                    {v.filename} {v.is_recommended ? '(Recommended - Cadbury)' : `(${v.size_mb} MB)`}
                  </option>
                ))
              ) : (
                <>
                  <option value="test_video1.mp4" className="bg-[#0e1320] text-slate-200">test_video1.mp4 (Cadbury Showcase)</option>
                  <option value="test_video.mp4" className="bg-[#0e1320] text-slate-200">test_video.mp4 (Sample Reel)</option>
                </>
              )}
            </select>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center bg-[#0e1320] border border-[#1e293b] rounded p-1 text-xs font-mono">
            <button
              onClick={() => setMode('offline')}
              className={`px-3 py-1 rounded transition-colors ${
                mode === 'offline' ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
              }`}
            >
              OFFLINE (0-QUOTA)
            </button>
            <button
              onClick={() => setMode('live')}
              className={`px-3 py-1 rounded transition-colors ${
                mode === 'live' ? 'bg-amber-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
              }`}
            >
              LIVE ADK
            </button>
          </div>

          {/* Force refresh checkbox */}
          <label className="flex items-center gap-1.5 text-xs font-mono text-slate-400 cursor-pointer bg-[#0e1320] border border-[#1e293b] px-3 py-1.5 rounded select-none">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(e) => setForceRefresh(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0 w-3.5 h-3.5"
            />
            <span>FORCE REFRESH</span>
          </label>

          {/* Main Action Button */}
          <button
            onClick={handleRunOrchestration}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 rounded font-mono text-xs font-bold uppercase transition-all bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 shadow-lg shadow-cyan-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Activity className="w-4 h-4 animate-spin" />
                ORCHESTRATING...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                RUN AUTONOMOUS ANALYSIS
              </>
            )}
          </button>
        </div>
      </div>

      {/* Active AI Models Transparency Bar */}
      <div className="bg-gradient-to-r from-[#0c1220] via-[#10182b] to-[#0c1220] border border-cyan-500/25 rounded-lg p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-mono text-[11px]">
            <Eye className="w-3.5 h-3.5 text-cyan-400" />
            <span>VISION: Gemini 3.5 Flash Lite</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono text-[11px]">
            <Search className="w-3.5 h-3.5 text-amber-400" />
            <span>RESEARCH: Parallel Search API (Trademarks &amp; Rights Holders)</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 font-mono text-[11px]">
            <FileText className="w-3.5 h-3.5 text-indigo-400" />
            <span>SCRIPT: Gemini Flash</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFrameInspector(!showFrameInspector)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 font-mono text-[11px] transition-all"
          >
            <Film className="w-3.5 h-3.5 text-amber-400" />
            <span>{showFrameInspector ? 'HIDE FRAME INSPECTOR' : `INSPECT EXTRACTED FRAMES (${extractedFrames.length})`}</span>
          </button>
        </div>
      </div>

      {/* Frame-by-Frame Inspector Viewport */}
      {showFrameInspector && extractedFrames.length > 0 && (
        <FrameInspector frames={extractedFrames} />
      )}


      {/* KPI Workflow Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-3 text-center">
          <div className="text-[10px] font-mono text-slate-400 uppercase">ENTITIES</div>
          <div className="text-xl font-bold font-mono text-white mt-1">
            {summary?.detection?.total_entities ?? orchestration?.entity_ids?.length ?? 0}
          </div>
        </div>

        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-3 text-center">
          <div className="text-[10px] font-mono text-slate-400 uppercase">VISUAL ONLY</div>
          <div className="text-xl font-bold font-mono text-violet-400 mt-1">
            {summary?.detection?.visual_only ?? 0}
          </div>
        </div>

        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-3 text-center">
          <div className="text-[10px] font-mono text-slate-400 uppercase">EVIDENCE</div>
          <div className="text-xl font-bold font-mono text-cyan-400 mt-1">
            {summary?.detection?.evidence_count ?? orchestration?.evidence_ids?.length ?? 0}
          </div>
        </div>

        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-3 text-center">
          <div className="text-[10px] font-mono text-slate-400 uppercase">RESEARCHED</div>
          <div className="text-xl font-bold font-mono text-blue-400 mt-1">
            {summary?.research?.completed ?? 0}
          </div>
        </div>

        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-3 text-center">
          <div className="text-[10px] font-mono text-slate-400 uppercase">HIGH RISK</div>
          <div className="text-xl font-bold font-mono text-rose-400 mt-1">
            {summary?.risk?.high ?? 0}
          </div>
        </div>

        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-3 text-center">
          <div className="text-[10px] font-mono text-slate-400 uppercase">VERIFIED</div>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
            {summary?.verification?.confirmed ?? 0}
          </div>
        </div>

        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-3 text-center">
          <div className="text-[10px] font-mono text-slate-400 uppercase">ACTION REQ</div>
          <div className="text-xl font-bold font-mono text-amber-400 mt-1">
            {summary?.resolution?.action_required ?? 0}
          </div>
        </div>

        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-3 text-center">
          <div className="text-[10px] font-mono text-slate-400 uppercase">HUMAN REVIEW</div>
          <div className="text-xl font-bold font-mono text-amber-300 mt-1">
            {summary?.resolution?.human_review ?? 0}
          </div>
        </div>
      </div>

      {/* Main Grid: DAG Visualization (Left) + Agent Inspection & Feed (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: DAG Visualizer (7 cols) */}
        <div className="lg:col-span-7 bg-[#0e1320] border border-[#1e293b] rounded p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#1e293b]">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
                GOOGLE ADK AGENT DEPENDENCY GRAPH
              </h2>
            </div>
            {orchestration && (
              <span className="text-[11px] font-mono text-slate-400">
                Total Duration: <strong className="text-cyan-400">{orchestration.duration.toFixed(1)}s</strong>
              </span>
            )}
          </div>

          {/* Root Agent Box */}
          <div className="p-3.5 rounded bg-gradient-to-r from-slate-900 to-[#12192b] border border-cyan-500/40 text-center relative shadow-lg shadow-cyan-950/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="w-5 h-5 text-cyan-400" />
                <span className="font-mono text-xs font-bold text-white tracking-wide">ROOT AGENT (ORCHESTRATOR)</span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                {orchestration?.status || 'READY'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 text-left mt-1.5">
              Autonomously plans agent branches, respects dependency barriers, enables parallel execution, isolates failures, and guarantees terminal human review boundaries.
            </p>
          </div>

          {/* Parallel Branches: Screenplay & Visual */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            {/* Screenplay Agent Node */}
            <div
              onClick={() => setSelectedAgentId('screenplay')}
              className={`p-3 rounded border cursor-pointer transition-all ${
                selectedAgentId === 'screenplay'
                  ? 'border-indigo-400 bg-indigo-950/20 shadow-lg shadow-indigo-950/30'
                  : 'border-[#1e293b] bg-slate-900/60 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-indigo-400" />
                  <span className="text-xs font-mono font-bold text-white">SCREENPLAY AGENT</span>
                </div>
                {getStatusBadge(getNodeStatus('screenplay'))}
              </div>
              <div className="text-[10px] text-slate-400 mt-1 font-mono">Parallel Execution Branch</div>
            </div>

            {/* Visual Agent Node */}
            <div
              onClick={() => setSelectedAgentId('visual')}
              className={`p-3 rounded border cursor-pointer transition-all ${
                selectedAgentId === 'visual'
                  ? 'border-cyan-400 bg-cyan-950/20 shadow-lg shadow-cyan-950/30'
                  : 'border-[#1e293b] bg-slate-900/60 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-cyan-400" />
                  <span className="text-xs font-mono font-bold text-white">VISUAL AGENT</span>
                </div>
                {getStatusBadge(getNodeStatus('visual'))}
              </div>
              <div className="text-[10px] text-slate-400 mt-1 font-mono">Parallel Execution Branch</div>
            </div>
          </div>

          {/* Synchronization Connector */}
          <div className="flex items-center justify-center text-slate-500 font-mono text-[10px] py-0.5">
            ▼ SYNCHRONIZATION POINT ▼
          </div>

          {/* Sequential Downstream Nodes */}
          <div className="space-y-2">
            {[
              AGENT_NODES[2], // Entity Merge
              AGENT_NODES[3], // Research
              AGENT_NODES[4], // Risk
              AGENT_NODES[5], // Verification
              AGENT_NODES[6], // Resolution
              AGENT_NODES[7], // Report
            ].map((node) => {
              const status = getNodeStatus(node.id);
              const isSelected = selectedAgentId === node.id;
              return (
                <div
                  key={node.id}
                  onClick={() => setSelectedAgentId(node.id)}
                  className={`p-2.5 rounded border flex items-center justify-between cursor-pointer transition-all ${
                    isSelected
                      ? 'border-cyan-400 bg-cyan-950/20 shadow-md shadow-cyan-950/20'
                      : 'border-[#1e293b] bg-slate-900/50 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded bg-slate-800/80">{node.icon}</div>
                    <div>
                      <div className="text-xs font-mono font-bold text-white">{node.name.toUpperCase()}</div>
                      <div className="text-[10px] text-slate-400">{node.role}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {orchestration?.agent_durations?.[node.name] !== undefined && (
                      <span className="text-[10px] font-mono text-slate-400">
                        {orchestration.agent_durations[node.name].toFixed(2)}s
                      </span>
                    )}
                    {getStatusBadge(status)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Agent Inspector & Live Telemetry Feed (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Agent Inspector Card */}
          <div className="bg-[#0e1320] border border-[#1e293b] rounded p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#1e293b]">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
                  AGENT INSPECTOR
                </h3>
              </div>
              {getStatusBadge(getNodeStatus(selectedNode.id))}
            </div>

            <div>
              <div className="text-sm font-bold text-white font-mono">{selectedNode.name}</div>
              <div className="text-xs text-slate-400 font-mono mt-0.5">{selectedNode.role}</div>
            </div>

            <div className="p-3 rounded bg-slate-900/80 border border-[#1e293b] text-xs text-slate-300">
              <div className="text-[10px] font-mono text-slate-400 uppercase font-semibold mb-1">Responsibility:</div>
              {selectedNode.responsibility}
            </div>

            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Primary Tool:</span>
                <span className="text-cyan-400 font-semibold">{selectedNode.toolName}()</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Execution Duration:</span>
                <span className="text-white">
                  {orchestration?.agent_durations?.[selectedNode.name]
                    ? `${orchestration.agent_durations[selectedNode.name].toFixed(2)}s`
                    : '--'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Output Handoff:</span>
                <span className="text-emerald-400 font-semibold">Structured AgentHandoff</span>
              </div>
            </div>

            {/* Generated Report Quick Actions if Report node selected */}
            {selectedNode.id === 'report' && orchestration?.report_id && (
              <div className="pt-2">
                <div className="text-[10px] font-mono text-slate-400 uppercase mb-2">Audit Report Artifacts:</div>
                <div className="flex gap-2">
                  <a
                    href={`/productions/${productionId}/report/${orchestration.report_id}/html`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 text-center py-1.5 rounded text-xs font-mono bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 transition-colors flex items-center justify-center gap-1"
                  >
                    <ExternalLink className="w-3 h-3" /> View HTML
                  </a>
                  <a
                    href={`/productions/${productionId}/report/${orchestration.report_id}/pdf`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 text-center py-1.5 rounded text-xs font-mono bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-colors flex items-center justify-center gap-1"
                  >
                    <Download className="w-3 h-3" /> PDF
                  </a>
                </div>
              </div>
            )}
          </div>

          {/* Live Orchestration Feed */}
          <div className="bg-[#0e1320] border border-[#1e293b] rounded p-5 space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-[#1e293b]">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
                  ORCHESTRATOR LIVE FEED
                </h3>
              </div>
              <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                ADK RUNTIME
              </span>
            </div>

            <div className="h-56 overflow-y-auto font-mono text-[11px] space-y-1.5 text-slate-400 bg-slate-950 p-3 rounded border border-slate-800">
              {logs.length === 0 ? (
                <div className="text-center text-slate-600 py-8">
                  Ready to orchestrate. Click &ldquo;RUN AUTONOMOUS ANALYSIS&rdquo; to launch Google ADK Root Agent.
                </div>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} className="leading-relaxed">
                    <span className="text-cyan-400 font-bold">&gt;</span> {log}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
