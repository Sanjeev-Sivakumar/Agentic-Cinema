import React, { useState } from 'react';
import { Play, Cpu, ArrowRight, Activity, CheckCircle, Sparkles } from 'lucide-react';
import { Entity } from '../types';
import { Resolution } from './Resolution';
import { api } from '../services/api';

interface ClearanceProps {
  entities: Entity[];
  productionId?: string;
}

export const Clearance: React.FC<ClearanceProps> = ({ entities, productionId }) => {
  const [running, setRunning] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRunAutonomous = async () => {
    if (!productionId) return;
    setRunning(true);
    setStatusMessage('Root Agent coordinating Screenplay, Visual, Research, Risk, Verification, and Resolution...');

    try {
      const res = await api.runOrchestration(productionId, { mode: 'offline', force_refresh: true });
      setStatusMessage(`Autonomous workflow completed (${res.status}) in ${res.duration.toFixed(1)}s! Report ID: ${res.report_id || 'generated'}`);
      setRefreshKey((prev) => prev + 1);
    } catch (e: any) {
      setStatusMessage(`Orchestration encountered an error: ${e.message}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Autonomous Orchestrator Banner */}
      <div className="bg-gradient-to-r from-[#0c1222] via-[#0f172a] to-[#0c1222] border border-cyan-500/30 rounded-lg p-5 shadow-xl shadow-cyan-950/20">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 font-bold">
                GOOGLE ADK RUNTIME
              </span>
              <span className="text-xs font-mono text-slate-400">AUTONOMOUS CLEARANCE PIPELINE</span>
            </div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2 font-mono">
              <Cpu className="w-5 h-5 text-cyan-400" />
              END-TO-END AUTONOMOUS CLEARANCE
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Trigger complete multi-agent clearance across all intelligence components without manual multi-step API execution.
            </p>
          </div>

          <button
            onClick={handleRunAutonomous}
            disabled={running}
            className="flex items-center justify-center gap-2 px-6 py-2.5 rounded font-mono text-xs font-bold uppercase transition-all bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 shadow-lg shadow-cyan-500/20 disabled:opacity-50"
          >
            {running ? (
              <>
                <Activity className="w-4 h-4 animate-spin" />
                ORCHESTRATING WORKFLOW...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                RUN AUTONOMOUS ANALYSIS
              </>
            )}
          </button>
        </div>

        {/* Visual Workflow Steps */}
        <div className="mt-4 pt-4 border-t border-slate-800/80">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono">
            <span className="px-2.5 py-1 rounded bg-cyan-950/40 text-cyan-300 border border-cyan-500/30 font-bold flex items-center gap-1">
              <Cpu className="w-3 h-3" /> ROOT AGENT
            </span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
            <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">DETECT</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
            <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">RESEARCH</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
            <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">ASSESS</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
            <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">VERIFY</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
            <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">RESOLVE</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
            <span className="px-2.5 py-1 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 font-bold flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> REPORT
            </span>
          </div>

          {statusMessage && (
            <div className="mt-3 p-2.5 rounded bg-slate-900/90 border border-cyan-500/30 text-xs font-mono text-cyan-300 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-cyan-400 flex-shrink-0" />
              <span>{statusMessage}</span>
            </div>
          )}
        </div>
      </div>

      {/* Embedded Operational Resolution Center (for detailed triage & testing) */}
      <Resolution key={refreshKey} entities={entities} productionId={productionId} />
    </div>
  );
};
