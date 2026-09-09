import React from 'react';
import { Shield, Film, Activity, Cpu, Search, Eye } from 'lucide-react';
import { Production, AvailableVideo } from '../../types';

interface HeaderProps {
  currentProduction: Production | null;
  activeJobId: string | null;
  isConnected: boolean;
  selectedVideo?: string;
  availableVideos?: AvailableVideo[];
  onSelectVideo?: (vid: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentProduction,
  activeJobId,
  isConnected,
  selectedVideo,
  availableVideos = [],
  onSelectVideo,
}) => {
  return (
    <header className="h-16 border-b border-[#1e293b] bg-[#090d16] px-6 flex items-center justify-between z-10 select-none">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm tracking-wider uppercase text-slate-100 font-mono">
                CHAIN OF TITLE
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                v0.1.0 PRE-CLEARANCE
              </span>
            </div>
            <p className="text-[11px] text-slate-400">Agentic Pre-Clearance Intelligence System</p>
          </div>
        </div>

        {/* Video Selector Dropdown */}
        {availableVideos.length > 0 && onSelectVideo && (
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#121826] border border-[#1e293b] text-xs font-mono">
            <Film className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
            <span className="text-slate-400 hidden lg:inline">VIDEO:</span>
            <select
              value={selectedVideo || 'test_video1.mp4'}
              onChange={(e) => onSelectVideo(e.target.value)}
              className="bg-transparent text-amber-300 font-semibold focus:outline-none cursor-pointer text-xs"
              title="Select video footage for clearance analysis"
            >
              {availableVideos.map((v) => (
                <option key={v.filename} value={v.filename} className="bg-[#0e1320] text-slate-200">
                  {v.filename} {v.is_recommended ? '★ (Cadbury Showcase)' : `(${v.size_mb} MB)`}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Active AI Stack Indicators */}
        <div className="hidden xl:flex items-center gap-2 text-[11px] font-mono">
          <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
            <Eye className="w-3 h-3 text-cyan-400" />
            <span>GEMINI VISION</span>
          </div>
          <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
            <Search className="w-3 h-3 text-amber-400" />
            <span>PARALLEL API</span>
          </div>
        </div>

        {activeJobId && (
          <div className="flex items-center gap-2 px-3 py-1 rounded bg-[#121826] border border-[#1e293b] font-mono text-xs text-slate-300">
            <Cpu className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
            <span>JOB: {activeJobId.substring(0, 10)}</span>
          </div>
        )}

        <div className="flex items-center gap-2 px-3 py-1 rounded bg-[#121826] border border-[#1e293b]">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]' : 'bg-slate-500'}`} />
          <span className="font-mono text-xs text-slate-300">
            {isConnected ? 'STREAM ACTIVE' : 'READY'}
          </span>
        </div>
      </div>
    </header>
  );
};
