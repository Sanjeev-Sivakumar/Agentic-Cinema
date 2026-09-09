import React from 'react';
import { CheckCircle2, Clock, Loader2, AlertCircle } from 'lucide-react';
import { PipelineStage, StageState, StageStatus } from '../../types';

interface LivePipelineProps {
  stages: Record<string, StageState>;
  currentStage: string;
}

const ALL_STAGES: PipelineStage[] = [
  'Screenplay Extraction',
  'Video Ingestion',
  'Scene Detection',
  'OCR',
  'Object Detection',
  'Gemini Vision',
  'Entity Merge',
  'Parallel Research',
  'Risk Assessment',
  'Verification',
  'Resolution',
  'Report Generation',
];

export const LivePipeline: React.FC<LivePipelineProps> = ({ stages, currentStage }) => {
  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between pb-3 border-b border-[#1e293b] mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
            12-STAGE AGENTIC PIPELINE
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
            ADK ORCHESTRATION
          </span>
        </div>
        <span className="text-[11px] font-mono text-slate-400">ACTIVE: {currentStage}</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {ALL_STAGES.map((stageName, idx) => {
          const state = stages[stageName] || {
            stage: stageName,
            status: 'WAITING' as StageStatus,
            progress: 0,
          };

          const isCurrent = currentStage === stageName && state.status === 'RUNNING';

          let statusIcon = <Clock className="w-3.5 h-3.5 text-slate-500" />;
          let statusBadge = (
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
              WAITING
            </span>
          );

          if (state.status === 'RUNNING') {
            statusIcon = <Loader2 className="w-3.5 h-3.5 text-amber-400 animate-spin" />;
            statusBadge = (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40 animate-pulse">
                RUNNING
              </span>
            );
          } else if (state.status === 'COMPLETED') {
            statusIcon = <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />;
            statusBadge = (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                DONE
              </span>
            );
          } else if (state.status === 'FAILED') {
            statusIcon = <AlertCircle className="w-3.5 h-3.5 text-red-400" />;
            statusBadge = (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-red-500/20 text-red-400 border border-red-500/40">
                FAILED
              </span>
            );
          }

          return (
            <div
              key={stageName}
              className={`p-2.5 rounded border transition-all ${
                isCurrent
                  ? 'bg-[#172033] border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.15)]'
                  : 'bg-[#121826] border-[#1e293b]'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-slate-400 w-4">
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                  {statusIcon}
                  <span
                    className={`text-xs font-semibold ${
                      isCurrent ? 'text-amber-300' : 'text-slate-200'
                    }`}
                  >
                    {stageName}
                  </span>
                </div>
                {statusBadge}
              </div>

              {state.latest_event && (
                <div className="text-[11px] text-slate-400 font-mono truncate pl-6 mb-1">
                  &gt; {state.latest_event}
                </div>
              )}

              {/* Progress bar */}
              <div className="w-full h-1 bg-[#1a2333] rounded-full overflow-hidden mt-1.5">
                <div
                  className={`h-full transition-all duration-300 ${
                    state.status === 'COMPLETED'
                      ? 'bg-emerald-400'
                      : state.status === 'RUNNING'
                      ? 'bg-amber-400'
                      : 'bg-transparent'
                  }`}
                  style={{
                    width: `${state.status === 'COMPLETED' ? 100 : state.progress || (state.status === 'RUNNING' ? 50 : 0)}%`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
