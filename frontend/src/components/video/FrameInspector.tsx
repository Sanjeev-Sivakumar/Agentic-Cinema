import React, { useState, useEffect } from 'react';
import {
  Film,
  ChevronLeft,
  ChevronRight,
  Eye,
  AlertTriangle,
  CheckCircle2,
  ScanText,
  Clock,
  Layers,
  Sparkles,
} from 'lucide-react';
import { ExtractedFrameItem, Entity } from '../../types';

interface FrameInspectorProps {
  frames: ExtractedFrameItem[];
  selectedFrameIndex?: number;
  onSelectFrame?: (frame: ExtractedFrameItem, index: number) => void;
  activeEntity?: Entity | null;
}

export const FrameInspector: React.FC<FrameInspectorProps> = ({
  frames = [],
  selectedFrameIndex = 0,
  onSelectFrame,
  activeEntity,
}) => {
  const [currentIndex, setCurrentIndex] = useState<number>(selectedFrameIndex);

  useEffect(() => {
    if (selectedFrameIndex >= 0 && selectedFrameIndex < frames.length) {
      setCurrentIndex(selectedFrameIndex);
    }
  }, [selectedFrameIndex, frames.length]);

  if (!frames || frames.length === 0) {
    return (
      <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 text-center">
        <div className="flex items-center justify-center gap-2 text-slate-400 text-xs font-mono">
          <Film className="w-4 h-4 text-amber-400 animate-pulse" />
          <span>Awaiting candidate frame extraction from backend pipeline...</span>
        </div>
      </div>
    );
  }

  const currentFrame = frames[currentIndex] || frames[0];

  const handlePrev = () => {
    if (currentIndex > 0) {
      const nextIdx = currentIndex - 1;
      setCurrentIndex(nextIdx);
      if (onSelectFrame) onSelectFrame(frames[nextIdx], nextIdx);
    }
  };

  const handleNext = () => {
    if (currentIndex < frames.length - 1) {
      const nextIdx = currentIndex + 1;
      setCurrentIndex(nextIdx);
      if (onSelectFrame) onSelectFrame(frames[nextIdx], nextIdx);
    }
  };

  const handleThumbClick = (idx: number) => {
    setCurrentIndex(idx);
    if (onSelectFrame) onSelectFrame(frames[idx], idx);
  };

  const formatTimecode = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(1);
    return `${String(mins).padStart(2, '0')}:${String(s).padStart(4, '0')}s`;
  };

  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded flex flex-col overflow-hidden shadow-lg">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#090d16] border-b border-[#1e293b]">
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            FRAME-BY-FRAME VISUAL INSPECTOR
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
            FRAME {currentIndex + 1} / {frames.length}
          </span>
        </div>

        {/* Frame Stepper Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrev}
            disabled={currentIndex === 0}
            className={`p-1.5 rounded text-xs font-mono flex items-center gap-1 border transition-all ${
              currentIndex === 0
                ? 'border-slate-800 text-slate-600 cursor-not-allowed'
                : 'border-slate-700 bg-slate-800/60 hover:bg-slate-700 text-slate-200'
            }`}
            title="Previous Frame"
          >
            <ChevronLeft className="w-4 h-4" />
            <span>PREV</span>
          </button>

          <span className="text-xs font-mono text-amber-400 font-semibold px-2">
            {formatTimecode(currentFrame.timestamp)}
          </span>

          <button
            onClick={handleNext}
            disabled={currentIndex === frames.length - 1}
            className={`p-1.5 rounded text-xs font-mono flex items-center gap-1 border transition-all ${
              currentIndex === frames.length - 1
                ? 'border-slate-800 text-slate-600 cursor-not-allowed'
                : 'border-slate-700 bg-slate-800/60 hover:bg-slate-700 text-slate-200'
            }`}
            title="Next Frame"
          >
            <span>NEXT</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Inspection Viewport & Findings Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-0">
        {/* Large Frame Preview Viewport */}
        <div className="lg:col-span-2 bg-[#05070c] relative aspect-video flex items-center justify-center overflow-hidden border-b lg:border-b-0 lg:border-r border-[#1e293b]">
          <img
            src={currentFrame.url}
            alt={`Frame at ${currentFrame.timestamp}s`}
            className="w-full h-full object-contain select-none"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />

          {/* Timecode and Scene Stamp Overlay */}
          <div className="absolute top-3 left-3 bg-black/80 backdrop-blur-sm border border-slate-700/60 px-2.5 py-1 rounded text-[11px] font-mono text-slate-200 flex items-center gap-2">
            <span className="text-cyan-400 font-bold">SCENE {String(currentFrame.scene_number).padStart(2, '0')}</span>
            <span className="text-slate-500">|</span>
            <span className="text-amber-400 font-semibold">{formatTimecode(currentFrame.timestamp)}</span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-400">{currentFrame.filename}</span>
          </div>

          {/* Detected Entity Bounding Box Overlay if present */}
          {currentFrame.detected_entities && currentFrame.detected_entities.length > 0 && (
            <div className="absolute top-3 right-3 bg-violet-950/80 backdrop-blur-sm border border-violet-500/60 px-2.5 py-1 rounded text-[11px] font-mono text-violet-200 flex items-center gap-1.5 shadow-[0_0_15px_rgba(139,92,246,0.4)]">
              <Eye className="w-3.5 h-3.5 text-violet-400" />
              <span>{currentFrame.detected_entities.length} DETECTED ENTITY</span>
            </div>
          )}
        </div>

        {/* Frame Inspection Telemetry Sidebar */}
        <div className="p-4 flex flex-col justify-between bg-[#0b0f1a] text-xs space-y-4">
          <div>
            <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
              <span className="font-bold text-slate-200 uppercase tracking-wider text-[11px]">
                FRAME TELEMETRY DETAILS
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                REC.709
              </span>
            </div>

            <div className="space-y-2 font-mono text-[11px]">
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Scene Identifier</span>
                <span className="text-slate-200 font-semibold">Scene {currentFrame.scene_number}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Exact Timestamp</span>
                <span className="text-amber-400 font-semibold">{currentFrame.timestamp.toFixed(2)}s</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Storage Relative</span>
                <span className="text-slate-300 truncate max-w-[150px]">{currentFrame.filename}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Inspection Engine</span>
                <span className="text-cyan-400">Gemini Vision + OCR</span>
              </div>
            </div>

            {/* Detections on this frame */}
            <div className="mt-4">
              <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block mb-2">
                CLEARANCE SIGNALS IN FRAME
              </span>

              {currentFrame.detected_entities && currentFrame.detected_entities.length > 0 ? (
                <div className="space-y-2">
                  {currentFrame.detected_entities.map((det) => (
                    <div
                      key={det.entity_id}
                      className="p-2.5 rounded bg-violet-950/30 border border-violet-500/40 flex flex-col gap-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-violet-200">{det.name}</span>
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30">
                          {det.classification}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                        <span>Risk Score: {det.risk_score}/100</span>
                        <span className={det.risk_score >= 70 ? 'text-red-400 font-bold' : 'text-amber-400'}>
                          {det.risk_level}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 rounded bg-slate-900/60 border border-slate-800 text-center text-slate-500 text-[11px] font-mono">
                  No direct clearance trademark violations detected on this keyframe.
                </div>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800 text-[10px] font-mono text-slate-500 flex items-center justify-between">
            <span>KEYFRAME SAMPLING</span>
            <span>24 FPS SYNCED</span>
          </div>
        </div>
      </div>

      {/* Horizontal Thumbnail Filmstrip Scrubber */}
      <div className="bg-[#070a12] border-t border-[#1e293b] p-2.5">
        <div className="flex items-center gap-1 mb-1.5 px-1">
          <Layers className="w-3 h-3 text-slate-400" />
          <span className="text-[10px] font-mono uppercase text-slate-400">
            EXTRACTED CANDIDATE FILMSTRIP (CLICK ANY FRAME TO INSPECT)
          </span>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
          {frames.map((f, idx) => {
            const isSelected = idx === currentIndex;
            const hasEntities = f.detected_entities && f.detected_entities.length > 0;

            return (
              <button
                key={f.frame_id || idx}
                onClick={() => handleThumbClick(idx)}
                className={`relative flex-shrink-0 rounded overflow-hidden border-2 transition-all group ${
                  isSelected
                    ? 'border-amber-400 scale-105 shadow-[0_0_12px_rgba(245,158,11,0.5)] z-10'
                    : hasEntities
                    ? 'border-violet-500/60 hover:border-violet-400'
                    : 'border-slate-800 hover:border-slate-600 opacity-75 hover:opacity-100'
                }`}
                style={{ width: '88px', height: '52px' }}
                title={`Scene ${f.scene_number} @ ${f.timestamp}s`}
              >
                <img
                  src={f.url}
                  alt={`Thumbnail ${idx + 1}`}
                  className="w-full h-full object-cover"
                />

                <div className="absolute inset-x-0 bottom-0 bg-black/80 px-1 py-0.5 text-[8px] font-mono text-slate-300 flex items-center justify-between">
                  <span>Sc.{f.scene_number}</span>
                  <span className={isSelected ? 'text-amber-400 font-bold' : 'text-slate-400'}>
                    {f.timestamp.toFixed(1)}s
                  </span>
                </div>

                {hasEntities && (
                  <div className="absolute top-1 right-1 w-2 h-2 rounded-full bg-violet-400 shadow-[0_0_6px_#a78bfa]" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
