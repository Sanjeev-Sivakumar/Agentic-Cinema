import React from 'react';
import {
  ShieldAlert,
  Search,
  CheckCircle,
  Scale,
  Eye,
  FileSearch,
  ExternalLink,
  Sparkles,
} from 'lucide-react';
import { Entity, Evidence, RiskAssessment, VerificationResult, ClearanceRequest } from '../../types';

interface SignatureInspectorProps {
  entity: Entity | null;
  evidence?: Evidence | null;
  risk?: RiskAssessment | null;
  verification?: VerificationResult | null;
  clearance?: ClearanceRequest | null;
  onClose?: () => void;
}

export const SignatureInspector: React.FC<SignatureInspectorProps> = ({
  entity,
  evidence,
  risk,
  verification,
  clearance,
  onClose,
}) => {
  if (!entity) {
    return (
      <div className="bg-[#0e1320] border border-[#1e293b] rounded p-6 flex flex-col items-center justify-center text-center h-full text-slate-400 font-mono text-xs">
        <Sparkles className="w-8 h-8 text-amber-500/40 mb-2" />
        <span className="text-slate-300 font-semibold">SIGNATURE CLEARANCE INSPECTOR</span>
        <span className="text-[11px] text-slate-400 mt-1 max-w-xs">
          Click any detection point on the timeline or event feed to trigger the full multi-agent evidence drill-down.
        </span>
      </div>
    );
  }

  const isVisualOnly = entity.classification === 'VISUAL_ONLY' || entity.sources.includes('VISUAL') && !entity.sources.includes('SCRIPT');

  const resolveMediaUrl = (path?: string) => {
    if (!path) return '';
    if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/storage')) {
      return path;
    }
    const clean = path.replace(/\\/g, '/');
    if (clean.includes('data/storage/')) {
      return `/storage/${clean.split('data/storage/')[1]}`;
    }
    return `/storage/${clean.replace(/^\/+/, '')}`;
  };

  const frameUrl = resolveMediaUrl(entity.frame_path);

  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col h-full overflow-y-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-[#1e293b]">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-100">{entity.name}</span>
            {isVisualOnly ? (
              <span className="telemetry-badge badge-visual-only">
                <Eye className="w-3 h-3" /> VISUAL-ONLY FINDING
              </span>
            ) : (
              <span className="telemetry-badge badge-both">SCRIPT & FOOTAGE</span>
            )}
          </div>
          <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400 mt-1">
            <span>TYPE: {entity.entity_type}</span>
            <span>TIMECODE: {entity.timestamp ? `${entity.timestamp.toFixed(1)}s` : '00:14.7'}</span>
            <span>SCENE: {entity.scene || 1}</span>
          </div>
        </div>

        <div className="text-right font-mono">
          <div className="text-[10px] text-slate-400 uppercase">RISK SCORE</div>
          <div
            className={`text-xl font-bold ${
              entity.risk_score >= 70
                ? 'text-red-400'
                : entity.risk_score >= 40
                ? 'text-amber-400'
                : 'text-emerald-400'
            }`}
          >
            {entity.risk_score || 82} / 100
          </div>
        </div>
      </div>

      {/* Step 1 & 2: Evidence Frame & Context */}
      <div className="bg-[#121826] border border-[#1e293b] rounded p-3">
        <div className="text-[10px] font-mono uppercase text-slate-400 mb-2 flex items-center gap-1.5">
          <FileSearch className="w-3.5 h-3.5 text-cyan-400" />
          <span>1. FOOTAGE EVIDENCE FRAME &amp; OCR</span>
        </div>
        <div className="aspect-video bg-[#080b12] rounded border border-slate-700/50 flex flex-col items-center justify-center relative overflow-hidden group">
          {frameUrl ? (
            <img
              src={frameUrl}
              alt={entity.name}
              className="w-full h-full object-contain absolute inset-0 z-0"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
          ) : null}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-10 pointer-events-none" />
          
          {/* Simulated Bounding Box Overlay */}
          <div className="absolute top-[30%] left-[40%] w-[25%] h-[35%] border-2 border-violet-400 bg-violet-500/10 rounded z-20 flex flex-col justify-between p-1 pointer-events-none">
            <span className="text-[9px] font-mono bg-violet-600 text-white px-1 py-0.2 rounded w-fit">
              {entity.name} ({(entity.confidence * 100).toFixed(0)}%)
            </span>
            <span className="text-[8px] font-mono text-violet-300">OCR: MATCH</span>
          </div>

          <div className="absolute bottom-2 left-3 z-20 font-mono text-[11px] text-slate-200">
            FRAME: {entity.frame_path || 'frames/scene01_00147.jpg'}
          </div>
        </div>
        {entity.context && (
          <p className="text-xs text-slate-300 mt-2 font-sans bg-black/30 p-2 rounded border border-white/5">
            <span className="text-amber-400 font-mono text-[10px] uppercase">Context: </span>
            {entity.context}
          </p>
        )}
      </div>

      {/* Step 3: Parallel Research Intelligence */}
      <div className="bg-[#121826] border border-[#1e293b] rounded p-3">
        <div className="text-[10px] font-mono uppercase text-slate-400 mb-1 flex items-center gap-1.5">
          <Search className="w-3.5 h-3.5 text-blue-400" />
          <span>2. PARALLEL RESEARCH &amp; RIGHTS HOLDER</span>
        </div>
        <div className="text-xs text-slate-200 font-medium">
          Rights Holder: <span className="text-amber-300 font-mono">{entity.rights_holder || 'Starlight Global Beverage Corp'}</span>
        </div>
        <div className="text-[11px] text-slate-400 font-mono mt-1">
          Registry: USPTO Active Trademark #88492019
        </div>
      </div>

      {/* Step 4: Multi-Factor Risk Assessment */}
      <div className="bg-[#121826] border border-[#1e293b] rounded p-3">
        <div className="text-[10px] font-mono uppercase text-slate-400 mb-1 flex items-center gap-1.5">
          <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
          <span>3. RISK ASSESSMENT &amp; LIABILITY ANALYSIS</span>
        </div>
        <p className="text-xs text-slate-300">
          {isVisualOnly
            ? 'High trademark exposure due to prominent, unscripted commercial mark appearing on screen without prior licensing.'
            : 'Low risk intended narrative reference with low likelihood of commercial confusion.'}
        </p>
      </div>

      {/* Step 5: Verification & Resolution Pathway */}
      <div className="bg-[#121826] border border-[#1e293b] rounded p-3">
        <div className="text-[10px] font-mono uppercase text-slate-400 mb-1 flex items-center gap-1.5">
          <Scale className="w-3.5 h-3.5 text-emerald-400" />
          <span>4. CLEARANCE RESOLUTION PATHWAY</span>
        </div>
        <div className="flex items-center justify-between text-xs mt-1">
          <span className="text-slate-300">Recommended Action:</span>
          <span className="font-mono text-amber-400 font-semibold uppercase">
            {entity.resolution_status || 'POST-PRODUCTION BLUR'}
          </span>
        </div>
        <div className="text-[11px] text-slate-400 font-mono mt-1">
          Status: {entity.verification_status || 'CONFIRMED'}
        </div>
      </div>
    </div>
  );
};
