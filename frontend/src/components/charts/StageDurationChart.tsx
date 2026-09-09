import React from 'react';
import { StageState } from '../../types';

interface StageDurationChartProps {
  stages: Record<string, StageState>;
}

export const StageDurationChart: React.FC<StageDurationChartProps> = ({ stages }) => {
  const stageList = Object.values(stages);

  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col h-full">
      <div className="flex items-center justify-between pb-2 border-b border-[#1e293b] mb-3">
        <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
          STAGE DURATION &amp; EXECUTION METRICS
        </span>
        <span className="text-[10px] font-mono text-cyan-400">TELEMETRY</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {stageList.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs font-mono text-slate-400">
            Awaiting stage telemetry...
          </div>
        ) : (
          stageList.map((st) => (
            <div key={st.stage} className="text-xs font-mono">
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-300 truncate max-w-[200px]">{st.stage}</span>
                <span className="text-amber-400">
                  {st.duration_ms ? `${st.duration_ms}ms` : st.status}
                </span>
              </div>
              <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full ${
                    st.status === 'COMPLETED'
                      ? 'bg-emerald-400'
                      : st.status === 'RUNNING'
                      ? 'bg-amber-400'
                      : 'bg-transparent'
                  }`}
                  style={{ width: `${st.progress || (st.status === 'COMPLETED' ? 100 : 0)}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
