import React from 'react';

interface RiskDistributionChartProps {
  highRisk: number;
  medRisk: number;
  lowRisk: number;
  unknownRisk: number;
}

export const RiskDistributionChart: React.FC<RiskDistributionChartProps> = ({
  highRisk,
  medRisk,
  lowRisk,
  unknownRisk,
}) => {
  const total = highRisk + medRisk + lowRisk + unknownRisk || 1;
  const highPct = Math.round((highRisk / total) * 100);
  const medPct = Math.round((medRisk / total) * 100);
  const lowPct = Math.round((lowRisk / total) * 100);
  const unkPct = Math.round((unknownRisk / total) * 100);

  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col h-full">
      <div className="flex items-center justify-between pb-2 border-b border-[#1e293b] mb-3">
        <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
          RISK DISTRIBUTION
        </span>
        <span className="text-[10px] font-mono text-slate-400">TOTAL: {total === 1 && highRisk === 0 ? 0 : total}</span>
      </div>

      {/* Multi-segment progress bar */}
      <div className="w-full h-3 bg-slate-800 rounded-full flex overflow-hidden my-auto">
        <div style={{ width: `${highPct}%` }} className="bg-red-500 transition-all duration-500" title={`High: ${highRisk}`} />
        <div style={{ width: `${medPct}%` }} className="bg-amber-500 transition-all duration-500" title={`Medium: ${medRisk}`} />
        <div style={{ width: `${lowPct}%` }} className="bg-emerald-500 transition-all duration-500" title={`Low: ${lowRisk}`} />
        <div style={{ width: `${unkPct}%` }} className="bg-slate-600 transition-all duration-500" title={`Unknown: ${unknownRisk}`} />
      </div>

      {/* Legend & stats */}
      <div className="grid grid-cols-2 gap-2 mt-4 text-[11px] font-mono">
        <div className="flex items-center justify-between p-1.5 rounded bg-[#121826] border border-red-500/20">
          <span className="flex items-center gap-1.5 text-red-400">
            <span className="w-2 h-2 rounded-full bg-red-400" /> HIGH
          </span>
          <span className="font-bold text-slate-200">{highRisk}</span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded bg-[#121826] border border-amber-500/20">
          <span className="flex items-center gap-1.5 text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-400" /> MEDIUM
          </span>
          <span className="font-bold text-slate-200">{medRisk}</span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded bg-[#121826] border border-emerald-500/20">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400" /> LOW
          </span>
          <span className="font-bold text-slate-200">{lowRisk}</span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded bg-[#121826] border border-slate-700/50">
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="w-2 h-2 rounded-full bg-slate-500" /> UNKNOWN
          </span>
          <span className="font-bold text-slate-200">{unknownRisk}</span>
        </div>
      </div>
    </div>
  );
};
