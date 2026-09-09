import React from 'react';

interface EntitySourceChartProps {
  visualOnly: number;
  scriptOnly: number;
  both: number;
  audioOnly: number;
}

export const EntitySourceChart: React.FC<EntitySourceChartProps> = ({
  visualOnly,
  scriptOnly,
  both,
  audioOnly,
}) => {
  const total = visualOnly + scriptOnly + both + audioOnly || 1;
  const vPct = Math.round((visualOnly / total) * 100);
  const sPct = Math.round((scriptOnly / total) * 100);
  const bPct = Math.round((both / total) * 100);
  const aPct = Math.round((audioOnly / total) * 100);

  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col h-full">
      <div className="flex items-center justify-between pb-2 border-b border-[#1e293b] mb-3">
        <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
          ENTITY SOURCE DISTRIBUTION
        </span>
        <span className="text-[10px] font-mono text-violet-400 font-semibold">
          {vPct}% VISUAL-ONLY
        </span>
      </div>

      <div className="w-full h-3 bg-slate-800 rounded-full flex overflow-hidden my-auto">
        <div style={{ width: `${vPct}%` }} className="bg-violet-500 transition-all duration-500" title={`Visual Only: ${visualOnly}`} />
        <div style={{ width: `${bPct}%` }} className="bg-emerald-500 transition-all duration-500" title={`Both: ${both}`} />
        <div style={{ width: `${sPct}%` }} className="bg-cyan-500 transition-all duration-500" title={`Script Only: ${scriptOnly}`} />
        <div style={{ width: `${aPct}%` }} className="bg-amber-500 transition-all duration-500" title={`Audio Only: ${audioOnly}`} />
      </div>

      <div className="grid grid-cols-2 gap-2 mt-4 text-[11px] font-mono">
        <div className="flex items-center justify-between p-1.5 rounded bg-[#121826] border border-violet-500/20">
          <span className="flex items-center gap-1.5 text-violet-400 font-medium">
            <span className="w-2 h-2 rounded-full bg-violet-400" /> VISUAL ONLY
          </span>
          <span className="font-bold text-slate-200">{visualOnly}</span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded bg-[#121826] border border-emerald-500/20">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400" /> SCRIPT &amp; VISUAL
          </span>
          <span className="font-bold text-slate-200">{both}</span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded bg-[#121826] border border-cyan-500/20">
          <span className="flex items-center gap-1.5 text-cyan-400">
            <span className="w-2 h-2 rounded-full bg-cyan-400" /> SCRIPT ONLY
          </span>
          <span className="font-bold text-slate-200">{scriptOnly}</span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded bg-[#121826] border border-amber-500/20">
          <span className="flex items-center gap-1.5 text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-400" /> AUDIO ONLY
          </span>
          <span className="font-bold text-slate-200">{audioOnly}</span>
        </div>
      </div>
    </div>
  );
};
