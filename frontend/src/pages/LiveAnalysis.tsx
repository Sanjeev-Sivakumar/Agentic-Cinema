import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Activity, ShieldCheck, Eye, Cpu, XCircle, Film, Sparkles, Binary, ScanText, Search, FileText } from 'lucide-react';
import { VideoPlayer } from '../components/video/VideoPlayer';
import { FrameInspector } from '../components/video/FrameInspector';
import { LivePipeline } from '../components/live-analysis/LivePipeline';
import { LiveEventFeed } from '../components/live-analysis/LiveEventFeed';
import { SignatureInspector } from '../components/live-analysis/SignatureInspector';
import { DetectionTimelineChart } from '../components/charts/DetectionTimelineChart';
import { Entity, ProcessingEvent, Production, StageState, ExtractedFrameItem, AvailableVideo } from '../types';
import { LiveMetricsData } from '../hooks/useLiveMetrics';
import { api } from '../services/api';

interface LiveAnalysisProps {
  currentProduction: Production | null;
  activeJobId: string | null;
  isConnected: boolean;
  events: ProcessingEvent[];
  stages: Record<string, StageState>;
  currentStage: string;
  currentProgress: number;
  metrics: LiveMetricsData;
  entities: Entity[];
  onStartAnalysis: () => void;
  onCancelAnalysis?: () => void;
  onClearEvents: () => void;
  selectedVideo?: string;
  availableVideos?: AvailableVideo[];
  onSelectVideo?: (vid: string) => void;
}

export const LiveAnalysis: React.FC<LiveAnalysisProps> = ({
  currentProduction,
  activeJobId,
  isConnected,
  events,
  stages,
  currentStage,
  currentProgress,
  metrics,
  entities,
  onStartAnalysis,
  onCancelAnalysis,
  onClearEvents,
  selectedVideo = 'test_video1.mp4',
  availableVideos = [],
  onSelectVideo,
}) => {
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(entities[0] || null);
  const [currentVideoTimestamp, setCurrentVideoTimestamp] = useState<number>(14.7);
  const [currentEvidenceFrame, setCurrentEvidenceFrame] = useState<string>('');
  const [currentSceneNumber, setCurrentSceneNumber] = useState<number>(1);
  const [extractedFrames, setExtractedFrames] = useState<ExtractedFrameItem[]>([]);
  const [viewMode, setViewMode] = useState<'video' | 'inspector'>('video');

  // Load extracted frames for visual frame-by-frame inspector
  useEffect(() => {
    if (currentProduction?.id) {
      api.getExtractedFrames(currentProduction.id)
        .then((res) => {
          if (res?.frames && res.frames.length > 0) {
            setExtractedFrames(res.frames);
          }
        })
        .catch(() => {});
    }
  }, [currentProduction?.id, activeJobId, selectedVideo]);


  // Sync state to incoming backend events as processing unfolds in real-time
  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[events.length - 1];

    if (latest.video_timestamp !== undefined) {
      setCurrentVideoTimestamp(latest.video_timestamp);
    }
    if (latest.scene_number !== undefined) {
      setCurrentSceneNumber(latest.scene_number);
    }
    if (latest.frame_path) {
      setCurrentEvidenceFrame(latest.frame_path);
    }

    // Dynamic frame extraction real-time synchronization
    if (latest.event_type === 'FRAME_EXTRACTED' && latest.frame_path) {
      const frameName = latest.frame_path.split('/').pop() || 'frame.jpg';
      const newFrame: ExtractedFrameItem = {
        frame_id: `frm_${latest.video_timestamp}_${Date.now()}`,
        filename: frameName,
        url: latest.frame_path,
        relative_path: latest.frame_path,
        timestamp: latest.video_timestamp || 0,
        scene_number: latest.scene_number || 1,
        detected_entities: [],
        entity_count: 0,
      };
      setExtractedFrames((prev) => {
        if (prev.some((f) => Math.abs(f.timestamp - newFrame.timestamp) < 0.2)) return prev;
        return [...prev, newFrame].sort((a, b) => a.timestamp - b.timestamp);
      });
    } else if (latest.event_type === 'FRAME_EXTRACTION_COMPLETED' && currentProduction?.id) {
      api.getExtractedFrames(currentProduction.id)
        .then((res) => {
          if (res?.frames && res.frames.length > 0) setExtractedFrames(res.frames);
        })
        .catch(() => {});
    }

    // Automatically highlight newly detected or visual-only findings
    if (latest.event_type === 'VISUAL_ONLY_DISCOVERED' || latest.event_type === 'ENTITY_DETECTED') {
      const match = entities.find((e) => e.name.toLowerCase() === latest.entity_name?.toLowerCase());
      if (match) {
        setSelectedEntity(match);
      } else if (latest.entity_name) {
        setSelectedEntity({
          id: latest.entity_id || `ent_${Date.now()}`,
          production_id: latest.production_id,
          name: latest.entity_name,
          entity_type: latest.entity_type || 'BRAND',
          sources: [latest.event_type === 'VISUAL_ONLY_DISCOVERED' ? 'VISUAL' : 'SCRIPT'],
          confidence: latest.confidence || 0.94,
          timestamp: latest.video_timestamp,
          scene: latest.scene_number || 1,
          frame_path: latest.frame_path,
          clearance_type: 'TRADEMARK',
          risk_level: (latest.risk_level as any) || 'HIGH',
          risk_score: latest.risk_score || 85,
          rights_holder: 'Pending Verification',
          evidence_ids: [],
          verification_status: 'UNVERIFIED',
          resolution_status: 'BLUR_REQUIRED',
          created_at: new Date().toISOString(),
        });
      }
    }
  }, [events, entities]);

  const handleSelectEntity = (entity: Entity) => {
    setSelectedEntity(entity);
    if (entity.timestamp !== undefined) {
      setCurrentVideoTimestamp(entity.timestamp);
    }
    if (entity.scene !== undefined) {
      setCurrentSceneNumber(entity.scene);
    }
    if (entity.frame_path) {
      setCurrentEvidenceFrame(entity.frame_path);
    }
  };

  const handleSelectEvent = (event: ProcessingEvent) => {
    if (event.video_timestamp !== undefined) {
      setCurrentVideoTimestamp(event.video_timestamp);
    }
    if (event.scene_number !== undefined) {
      setCurrentSceneNumber(event.scene_number);
    }
    if (event.frame_path) {
      setCurrentEvidenceFrame(event.frame_path);
    }

    if (event.entity_name) {
      const match = entities.find((e) => e.name.toLowerCase() === event.entity_name?.toLowerCase());
      if (match) setSelectedEntity(match);
      else if (event.entity_id) {
        setSelectedEntity({
          id: event.entity_id,
          production_id: event.production_id,
          name: event.entity_name,
          entity_type: event.entity_type || 'BRAND',
          sources: [event.event_type === 'VISUAL_ONLY_DISCOVERED' ? 'VISUAL' : 'SCRIPT'],
          confidence: event.confidence || 0.92,
          timestamp: event.video_timestamp || 14.7,
          scene: event.scene_number || 1,
          frame_path: event.frame_path,
          clearance_type: 'TRADEMARK',
          risk_level: (event.risk_level as any) || 'HIGH',
          risk_score: event.risk_score || 82,
          rights_holder: 'Pending Verification',
          evidence_ids: [],
          verification_status: 'UNVERIFIED',
          resolution_status: 'BLUR_REQUIRED',
          created_at: new Date().toISOString(),
        });
      }
    }
  };

  return (
    <div className="space-y-3 h-full flex flex-col">
      {/* Action & Status Header */}
      <div className="flex items-center justify-between bg-[#0e1320] border border-[#1e293b] rounded px-4 py-2.5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
              LIVE PRE-CLEARANCE TELEMETRY
            </span>
          </div>

          <div className="hidden md:flex items-center gap-2 font-mono text-xs text-slate-400">
            <span>PROGRESS: {Math.round(currentProgress)}%</span>
            <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-400 transition-all duration-300"
                style={{ width: `${currentProgress}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Footage selector directly in Live Analysis */}
          {availableVideos.length > 0 && onSelectVideo && (
            <div className="flex items-center gap-1.5 bg-[#090d16] border border-[#1e293b] rounded px-2.5 py-1 text-xs font-mono">
              <Film className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
              <span className="text-slate-400 hidden sm:inline">FOOTAGE:</span>
              <select
                value={selectedVideo}
                onChange={(e) => onSelectVideo(e.target.value)}
                disabled={isConnected}
                className="bg-transparent text-amber-300 font-semibold focus:outline-none cursor-pointer text-xs"
                title="Select video footage to analyze"
              >
                {availableVideos.map((v) => (
                  <option key={v.filename} value={v.filename} className="bg-[#0e1320] text-slate-200">
                    {v.filename} {v.is_recommended ? '★ (Cadbury)' : `(${v.size_mb} MB)`}
                  </option>
                ))}
              </select>
            </div>
          )}

          {isConnected && onCancelAnalysis ? (
            <button
              onClick={onCancelAnalysis}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-semibold bg-red-600 hover:bg-red-500 text-white transition-all shadow-[0_0_10px_rgba(239,68,68,0.3)]"
            >
              <XCircle className="w-3.5 h-3.5" />
              CANCEL JOB
            </button>
          ) : (
            <button
              onClick={onStartAnalysis}
              disabled={!currentProduction || isConnected}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-semibold transition-all ${
                isConnected
                  ? 'bg-slate-800 text-slate-400 cursor-not-allowed'
                  : 'bg-amber-500 hover:bg-amber-400 text-black shadow-[0_0_10px_rgba(245,158,11,0.3)]'
              }`}
            >
              <Play className="w-3.5 h-3.5" />
              {isConnected ? 'ANALYZING...' : 'RUN PIPELINE'}
            </button>
          )}

          <button
            onClick={onClearEvents}
            className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-mono"
            title="Reset telemetry"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Real-time Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-2 flex flex-col">
          <span className="text-[10px] font-mono text-slate-400 uppercase">Frames Processed</span>
          <span className="text-base font-mono font-bold text-slate-100 mt-0.5">{metrics.framesProcessed}</span>
        </div>
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-2 flex flex-col">
          <span className="text-[10px] font-mono text-slate-400 uppercase">Scenes Detected</span>
          <span className="text-base font-mono font-bold text-cyan-400 mt-0.5">{metrics.scenesDetected}</span>
        </div>
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-2 flex flex-col">
          <span className="text-[10px] font-mono text-slate-400 uppercase">Entities Detected</span>
          <span className="text-base font-mono font-bold text-amber-400 mt-0.5">{metrics.totalEntities}</span>
        </div>
        <div className={`border rounded p-2 flex flex-col transition-all ${metrics.visualOnlyCount > 0 ? 'bg-violet-950/30 border-violet-500/60 shadow-[0_0_12px_rgba(139,92,246,0.2)]' : 'bg-[#0e1320] border-[#1e293b]'}`}>
          <span className="text-[10px] font-mono text-violet-300 uppercase flex items-center justify-between">
            Visual-Only
            {metrics.visualOnlyCount > 0 && <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse" />}
          </span>
          <span className="text-base font-mono font-bold text-violet-200 mt-0.5">{metrics.visualOnlyCount}</span>
        </div>
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-2 flex flex-col">
          <span className="text-[10px] font-mono text-slate-400 uppercase">Current Timecode</span>
          <span className="text-base font-mono font-bold text-emerald-400 mt-0.5">{metrics.currentVideoTimestamp.toFixed(1)}s</span>
        </div>
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-2 flex flex-col">
          <span className="text-[10px] font-mono text-slate-400 uppercase">Gemini Frames</span>
          <span className="text-base font-mono font-bold text-blue-400 mt-0.5">{metrics.geminiFramesCount}</span>
        </div>
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-2 flex flex-col">
          <span className="text-[10px] font-mono text-slate-400 uppercase">OCR Results</span>
          <span className="text-base font-mono font-bold text-pink-400 mt-0.5">{metrics.ocrResultsCount}</span>
        </div>
      </div>

      {/* Active AI Models Configuration & View Mode Toggle */}
      <div className="bg-[#0e1320] border border-[#1e293b] rounded p-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-mono text-[11px]" title="Google Gemini multimodal vision analyzes video keyframes">
            <Eye className="w-3.5 h-3.5 text-cyan-400" />
            <span>VISION: Gemini Multimodal</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono text-[11px]" title="Parallel Search API queries corporate rights holders and USPTO filings">
            <Search className="w-3.5 h-3.5 text-amber-400" />
            <span>RESEARCH: Parallel Search API (Live)</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 font-mono text-[11px]" title="Ultralytics YOLOv8 local spatial detector">
            <Cpu className="w-3.5 h-3.5 text-emerald-400" />
            <span>OBJECTS: YOLOv8</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-pink-500/10 text-pink-300 border border-pink-500/30 font-mono text-[11px]" title="Tesseract OCR extracts on-screen text">
            <ScanText className="w-3.5 h-3.5 text-pink-400" />
            <span>OCR: Tesseract</span>
          </div>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center bg-slate-900 border border-slate-700 rounded p-0.5 font-mono text-xs">
          <button
            onClick={() => setViewMode('video')}
            className={`px-3 py-1 rounded transition-all flex items-center gap-1.5 ${
              viewMode === 'video'
                ? 'bg-cyan-500 text-slate-950 font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>REAL-TIME STREAM</span>
          </button>
          <button
            onClick={() => setViewMode('inspector')}
            className={`px-3 py-1 rounded transition-all flex items-center gap-1.5 ${
              viewMode === 'inspector'
                ? 'bg-amber-500 text-slate-950 font-bold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>FRAME INSPECTOR ({extractedFrames.length})</span>
          </button>
        </div>
      </div>

      {/* Viewport: Either Frame-by-Frame Inspector or 4-Quadrant Pipeline Grid */}
      {viewMode === 'inspector' ? (
        <div className="flex-1 min-h-[440px]">
          <FrameInspector
            frames={extractedFrames}
            activeEntity={selectedEntity}
            onSelectFrame={(frame) => {
              setCurrentVideoTimestamp(frame.timestamp);
              setCurrentSceneNumber(frame.scene_number);
              setCurrentEvidenceFrame(frame.url);
            }}
          />
        </div>
      ) : (
        /* Main 4-Quadrant Grid (Left: Video, Center: Pipeline, Right: Event Feed) */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 flex-1 min-h-[440px]">
          {/* Left: Video Viewer & Synchronizer (4 Cols) */}
          <div className="lg:col-span-4 h-full">
            <VideoPlayer
              currentTimestamp={currentVideoTimestamp}
              currentScene={currentSceneNumber}
              activeEntity={selectedEntity}
              evidenceFrameUrl={currentEvidenceFrame}
              videoUrl={currentProduction?.footage_path || selectedVideo}
              onSeek={(ts) => setCurrentVideoTimestamp(ts)}
            />
          </div>


        {/* Center: Live 12-Stage Pipeline (4 Cols) */}
        <div className="lg:col-span-4 h-full">
          <LivePipeline stages={stages} currentStage={currentStage} />
        </div>

        {/* Right: Live Event Feed / Signature Inspector (4 Cols) */}
        <div className="lg:col-span-4 h-full flex flex-col gap-3">
          <div className="h-1/2">
            <LiveEventFeed events={events} onSelectEvent={handleSelectEvent} />
          </div>
          <div className="h-1/2">
            <SignatureInspector entity={selectedEntity} />
          </div>
        </div>
      </div>
      )}


      {/* Bottom Timeline & Detection Points */}
      <div className="h-40">
        <DetectionTimelineChart
          entities={entities}
          onSelectEntity={handleSelectEntity}
          selectedEntityId={selectedEntity?.id}
          videoDuration={metrics.currentVideoTimestamp + 10}
        />
      </div>
    </div>
  );
};
