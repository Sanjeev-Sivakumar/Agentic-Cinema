import React, { useState } from 'react';
import { Play, Pause, SkipBack, SkipForward, Maximize2, Shield, Eye } from 'lucide-react';
import { Entity } from '../../types';

interface VideoPlayerProps {
  currentTimestamp?: number;
  currentScene?: number;
  activeEntity?: Entity | null;
  evidenceFrameUrl?: string;
  videoUrl?: string;
  onSeek?: (timestamp: number) => void;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  currentTimestamp = 14.7,
  currentScene = 1,
  activeEntity,
  evidenceFrameUrl,
  videoUrl,
  onSeek,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const videoRef = React.useRef<HTMLVideoElement | null>(null);

  React.useEffect(() => {
    if (videoRef.current && Math.abs(videoRef.current.currentTime - currentTimestamp) > 0.5) {
      videoRef.current.currentTime = currentTimestamp;
    }
  }, [currentTimestamp]);

  React.useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play().catch(() => {});
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);

  const resolveMediaUrl = (path?: string) => {
    if (!path) return '';
    if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/storage') || path.startsWith('/media')) {
      return path;
    }
    const clean = path.replace(/\\/g, '/');
    if (clean.includes('data/storage/')) {
      return `/storage/${clean.split('data/storage/')[1]}`;
    }
    if (clean.endsWith('.mp4') || clean.endsWith('.mov') || clean.endsWith('.webm') || clean.endsWith('.avi')) {
      return `/media/${clean.replace(/^\/+/, '')}`;
    }
    return `/storage/${clean.replace(/^\/+/, '')}`;
  };


  const currentFrameSource = resolveMediaUrl(evidenceFrameUrl || activeEntity?.frame_path);

  const formatTimecode = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const remainingSec = (sec % 60).toFixed(1);
    const frames = Math.floor((sec % 1) * 24);
    return `${String(mins).padStart(2, '0')}:${String(remainingSec).padStart(4, '0')}:${String(frames).padStart(2, '0')}`;
  };

  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between pb-3 border-b border-[#1e293b] mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
            FOOTAGE &amp; EVIDENCE VIEWER
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            SYNCED
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-xs text-slate-400">
          <span>SCENE {String(currentScene).padStart(2, '0')}</span>
          <span className="text-amber-400 font-semibold">{formatTimecode(currentTimestamp)}</span>
        </div>
      </div>

      {/* Video Viewport / Canvas */}
      <div className="flex-1 bg-[#05070c] rounded border border-slate-800 relative flex items-center justify-center overflow-hidden">
        {videoUrl ? (
          <video
            ref={videoRef}
            src={resolveMediaUrl(videoUrl)}
            className="w-full h-full object-contain z-10"
            onTimeUpdate={(e) => {
              if (isPlaying && onSeek) {
                onSeek((e.target as HTMLVideoElement).currentTime);
              }
            }}
          />
        ) : currentFrameSource ? (
          <img
            src={currentFrameSource}
            alt="Current Footage Frame"
            className="w-full h-full object-contain z-10 transition-opacity duration-200"
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
        ) : null}

        {/* Fallback footage representation if no image */}
        <div className={`absolute inset-0 bg-gradient-to-br from-[#0c101c] via-[#080b14] to-[#04060a] flex items-center justify-center ${currentFrameSource || videoUrl ? 'opacity-20' : 'opacity-100'}`}>
          <div className="text-center p-6">
            <div className="w-16 h-16 rounded-full bg-slate-800/40 border border-slate-700/50 mx-auto flex items-center justify-center text-slate-500 mb-3">
              <Play className="w-8 h-8 ml-1 opacity-50" />
            </div>
            <p className="text-xs font-mono text-slate-400">FOOTAGE STREAM TELEMETRY</p>
            <p className="text-[10px] font-mono text-slate-400 mt-1">1080p 24fps • Rec.709 Color Space</p>
          </div>
        </div>

        {/* Dynamic Detected Entity Bounding Box Overlay */}
        {activeEntity && (() => {
          const bb = activeEntity.bounding_box;
          const style: React.CSSProperties = bb && bb.length >= 4 ? {
            left: `${Math.max(2, Math.min(95, bb[0] * 100))}%`,
            top: `${Math.max(2, Math.min(95, bb[1] * 100))}%`,
            width: `${Math.max(5, Math.min(95, bb[2] * 100))}%`,
            height: `${Math.max(5, Math.min(95, bb[3] * 100))}%`,
          } : {
            left: '38%',
            top: '28%',
            width: '24%',
            height: '32%',
          };

          const isVisualOnly = activeEntity.classification === 'VISUAL_ONLY' || 
            (activeEntity.sources?.includes('VISUAL') && !activeEntity.sources?.includes('SCRIPT'));
          const borderClass = isVisualOnly
            ? 'border-red-500 bg-red-500/15 shadow-[0_0_18px_rgba(239,68,68,0.4)]'
            : activeEntity.risk_score >= 70
            ? 'border-amber-500 bg-amber-500/15 shadow-[0_0_15px_rgba(245,158,11,0.3)]'
            : 'border-emerald-500 bg-emerald-500/15 shadow-[0_0_15px_rgba(16,185,129,0.3)]';

          return (
            <div
              style={style}
              className={`absolute border-2 rounded z-20 flex flex-col justify-between p-1.5 transition-all ${borderClass}`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className={`text-[10px] font-mono text-white px-1.5 py-0.5 rounded font-semibold tracking-wider truncate ${isVisualOnly ? 'bg-red-600' : 'bg-emerald-600'}`}>
                  {activeEntity.name}
                </span>
                <span className="text-[9px] font-mono text-white/90 bg-black/60 px-1 rounded">
                  {(activeEntity.confidence * 100).toFixed(0)}% CONF
                </span>
              </div>

              {/* Explicit AI Engine Attribution Badges (No Visual & Model Confusion) */}
              <div className="flex flex-wrap gap-1 my-1">
                <span className="text-[8px] font-mono px-1 py-0.5 rounded bg-cyan-950/90 text-cyan-300 border border-cyan-500/40">
                  VISION: GEMINI
                </span>
                {activeEntity.rights_holder && activeEntity.rights_holder !== 'Pending Verification' && (
                  <span className="text-[8px] font-mono px-1 py-0.5 rounded bg-amber-950/90 text-amber-300 border border-amber-500/40 truncate max-w-[130px]" title={activeEntity.rights_holder}>
                    PARALLEL: {activeEntity.rights_holder}
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between text-[9px] font-mono mt-auto">
                <span className={`uppercase px-1 rounded font-bold ${isVisualOnly ? 'bg-red-950 text-red-300 border border-red-500/40' : 'bg-emerald-950 text-emerald-300 border border-emerald-500/40'}`}>
                  {isVisualOnly ? 'VISUAL-ONLY' : activeEntity.classification}
                </span>
                <span className="text-amber-300 font-bold bg-black/70 px-1 rounded">
                  RISK: {activeEntity.risk_score}/100
                </span>
              </div>
            </div>
          );
        })()}

        {/* Bottom Timecode & Scene Overlay */}
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-[11px] font-mono text-slate-300 bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded border border-white/10 z-20">
          <div className="flex items-center gap-2">
            <span className="text-amber-400 font-bold">TC: {formatTimecode(currentTimestamp)}</span>
            <span className="text-slate-400">•</span>
            <span>FRAME: {Math.floor(currentTimestamp * 24)}</span>
          </div>

          {activeEntity && (
            <div className="flex items-center gap-2">
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${activeEntity.classification === 'VISUAL_ONLY' ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
                {activeEntity.classification === 'VISUAL_ONLY' ? 'VISUAL-ONLY EXPOSURE' : 'SCRIPT-MATCHED'}
              </span>
              <span className="text-amber-300 font-semibold">{activeEntity.name}</span>
            </div>
          )}
        </div>
      </div>

      {/* Transport Controls */}
      <div className="mt-3 flex items-center justify-between pt-2 border-t border-[#1e293b]">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
          <button className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">
            <SkipBack className="w-4 h-4" />
          </button>
          <button className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">
            <SkipForward className="w-4 h-4" />
          </button>
        </div>

        {/* Timeline seek slider */}
        <div className="flex-1 mx-4 flex items-center">
          <input
            type="range"
            min="0"
            max="60"
            step="0.1"
            value={currentTimestamp}
            onChange={(e) => onSeek && onSeek(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
          />
        </div>

        <button className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
