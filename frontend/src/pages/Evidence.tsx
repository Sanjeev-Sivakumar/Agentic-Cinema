import React from 'react';
import { Image as ImageIcon, Eye } from 'lucide-react';
import type { Entity, Evidence as EvidenceModel } from '../types';

interface EvidenceProps {
  entities: Entity[];
  evidenceList?: EvidenceModel[];
}

export const Evidence: React.FC<EvidenceProps> = ({ entities }) => {
  const resolveMediaUrl = (path?: string) => {
    if (!path) return '';
    if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/storage') || path.startsWith('/media')) {
      return path;
    }
    const clean = path.replace(/\\/g, '/');
    if (clean.includes('data/storage/')) {
      return `/storage/${clean.split('data/storage/')[1]}`;
    }
    return `/storage/${clean.replace(/^\/+/, '')}`;
  };

  return (
    <div className="space-y-4">
      <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ImageIcon className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold font-mono uppercase text-slate-100">
              EVIDENCE GALLERY &amp; OCR FRAMES
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Captured keyframes, OCR bounding boxes, and timestamped footage excerpts.
          </p>
        </div>
        <span className="text-xs font-mono text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded border border-amber-500/30">
          {entities.length} CAPTURED ASSETS
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {entities.map((entity) => {
          const isVisual = entity.classification === 'VISUAL_ONLY' || entity.sources.includes('VISUAL') && !entity.sources.includes('SCRIPT');
          const frameImgUrl = resolveMediaUrl(entity.frame_path);

          return (
            <div key={entity.id} className="bg-[#0e1320] border border-[#1e293b] rounded overflow-hidden hover:border-slate-600 transition-all flex flex-col">
              {/* Evidence Frame Canvas */}
              <div className="aspect-video bg-[#06080e] relative flex items-center justify-center border-b border-[#1e293b] group overflow-hidden">
                {frameImgUrl && (
                  <img
                    src={frameImgUrl}
                    alt={entity.name}
                    className="w-full h-full object-cover z-0"
                    onError={(e) => { (e.target as HTMLElement).style.display = 'none'; }}
                  />
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent z-10" />

                <div className="absolute top-[25%] left-[35%] w-[30%] h-[40%] border-2 border-amber-400 bg-amber-500/10 rounded z-20 flex flex-col justify-between p-1">
                  <span className="text-[9px] font-mono bg-amber-500 text-black font-bold px-1 rounded w-fit">
                    {entity.name}
                  </span>
                  <span className="text-[8px] font-mono text-amber-300">CONF: {Math.round(entity.confidence * 100)}%</span>
                </div>


                <div className="absolute bottom-2 left-3 right-3 flex items-center justify-between z-20 text-[10px] font-mono text-slate-300">
                  <span>{entity.frame_path || 'frames/scene01_147.jpg'}</span>
                  <span className="text-amber-400 font-semibold">{entity.timestamp ? `${entity.timestamp.toFixed(1)}s` : '14.7s'}</span>
                </div>
              </div>

              {/* Card Meta */}
              <div className="p-3.5 space-y-2 flex-1 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs text-slate-200">{entity.name}</span>
                    {isVisual ? (
                      <span className="telemetry-badge badge-visual-only text-[9px]">
                        <Eye className="w-2.5 h-2.5" /> VISUAL ONLY
                      </span>
                    ) : (
                      <span className="telemetry-badge badge-both text-[9px]">BOTH</span>
                    )}
                  </div>

                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">
                    {entity.context || 'Captured in foreground frame during actor dialogue sequence.'}
                  </p>
                </div>

                <div className="pt-2 border-t border-[#1e293b] flex items-center justify-between text-[10px] font-mono text-slate-400">
                  <span>SCENE {entity.scene || 1}</span>
                  <span className={entity.risk_score >= 70 ? 'text-red-400 font-bold' : 'text-slate-300'}>
                    RISK: {entity.risk_score}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
