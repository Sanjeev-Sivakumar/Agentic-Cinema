import React, { useState } from 'react';
import { Boxes, Search, Filter, Eye, ShieldAlert, Sparkles, CheckCircle2 } from 'lucide-react';
import { Entity } from '../types';

interface EntitiesProps {
  entities: Entity[];
  onSelectEntity?: (entity: Entity) => void;
}

export const Entities: React.FC<EntitiesProps> = ({ entities, onSelectEntity }) => {
  const [filter, setFilter] = useState<'ALL' | 'VISUAL_ONLY' | 'SCRIPT_ONLY' | 'BOTH' | 'HIGH_RISK'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEntities = entities.filter((e) => {
    const matchesSearch =
      e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (e.rights_holder && e.rights_holder.toLowerCase().includes(searchQuery.toLowerCase()));

    const isVisual = e.classification === 'VISUAL_ONLY' || e.sources.includes('VISUAL') && !e.sources.includes('SCRIPT');
    const isScript = e.classification === 'SCRIPT_ONLY' || e.sources.includes('SCRIPT') && !e.sources.includes('VISUAL');
    const isBoth = e.classification === 'BOTH' || (e.sources.includes('SCRIPT') && e.sources.includes('VISUAL'));
    const isHighRisk = e.risk_level === 'HIGH' || e.risk_score >= 70;

    if (!matchesSearch) return false;
    if (filter === 'VISUAL_ONLY') return isVisual;
    if (filter === 'SCRIPT_ONLY') return isScript;
    if (filter === 'BOTH') return isBoth;
    if (filter === 'HIGH_RISK') return isHighRisk;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 bg-[#0e1320] border border-[#1e293b] rounded p-4">
        <div>
          <div className="flex items-center gap-2">
            <Boxes className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold font-mono uppercase text-slate-100">
              RIGHTS-RELEVANT ENTITIES DIRECTORY
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Detected brands, trademarks, artwork, public figures, and product assets.
          </p>
        </div>

        {/* Filter Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          {(['ALL', 'VISUAL_ONLY', 'BOTH', 'SCRIPT_ONLY', 'HIGH_RISK'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all ${
                filter === tab
                  ? 'bg-amber-500 text-black font-bold'
                  : 'bg-[#121826] text-slate-400 hover:text-slate-200 border border-[#1e293b]'
              }`}
            >
              {tab.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
        <input
          type="text"
          placeholder="Filter by entity name, trademark, or rights holder..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-9 pr-4 py-2 bg-[#0e1320] border border-[#1e293b] rounded text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-amber-500 font-mono"
        />
      </div>

      {/* Entities Table */}
      <div className="bg-[#0e1320] border border-[#1e293b] rounded overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-[#1e293b] bg-[#090d16] text-[10px] font-mono uppercase text-slate-400">
              <th className="py-2.5 px-4">Entity</th>
              <th className="py-2.5 px-3">Type</th>
              <th className="py-2.5 px-3">Source</th>
              <th className="py-2.5 px-3">Research</th>
              <th className="py-2.5 px-3">Risk</th>
              <th className="py-2.5 px-3">Risk Score</th>
              <th className="py-2.5 px-3">Verification</th>
              <th className="py-2.5 px-3">Confidence</th>
              <th className="py-2.5 px-3">Scene / Time</th>
              <th className="py-2.5 px-3">Resolution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e293b] text-xs">
            {filteredEntities.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center py-8 text-slate-400 font-mono text-xs">
                  No entities found matching active filter.
                </td>
              </tr>
            ) : (
              filteredEntities.map((ent) => {
                const isVisual = ent.classification === 'VISUAL_ONLY' || (ent.sources?.includes('VISUAL') && !ent.sources?.includes('SCRIPT'));
                return (
                  <tr
                    key={ent.id}
                    onClick={() => onSelectEntity && onSelectEntity(ent)}
                    className="hover:bg-[#121826] cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-200">{ent.name}</div>
                      <div className="text-[10px] font-mono text-slate-400">{ent.id}</div>
                    </td>

                    <td className="py-3 px-3 font-mono text-[11px] text-slate-300">
                      {ent.entity_type}
                    </td>

                    <td className="py-3 px-3">
                      {isVisual ? (
                        <span className="telemetry-badge badge-visual-only">
                          <Eye className="w-3 h-3" /> VISUAL ONLY
                        </span>
                      ) : ent.sources?.includes('SCRIPT') && ent.sources?.includes('VISUAL') ? (
                        <span className="telemetry-badge badge-both">BOTH</span>
                      ) : (
                        <span className="telemetry-badge badge-script-only">SCRIPT ONLY</span>
                      )}
                    </td>

                    <td className="py-3 px-3 text-slate-300 font-mono text-[11px] truncate max-w-[160px]">
                      {ent.rights_holder || 'Pending Research'}
                    </td>

                    <td className="py-3 px-3">
                      <span
                        className={`telemetry-badge ${
                          ent.risk_level === 'HIGH' || ent.risk_score >= 70
                            ? 'badge-high-risk'
                            : ent.risk_level === 'MEDIUM' || ent.risk_score >= 40
                            ? 'badge-med-risk'
                            : ent.risk_level === 'UNKNOWN'
                            ? 'badge-unverified'
                            : 'badge-low-risk'
                        }`}
                      >
                        {ent.risk_level || 'UNKNOWN'}
                      </span>
                    </td>

                    <td className="py-3 px-3 font-mono text-[12px] font-bold">
                      <span
                        className={
                          ent.risk_level === 'HIGH' || ent.risk_score >= 70
                            ? 'text-red-400'
                            : ent.risk_level === 'MEDIUM' || ent.risk_score >= 40
                            ? 'text-amber-400'
                            : ent.risk_level === 'UNKNOWN'
                            ? 'text-slate-400'
                            : 'text-emerald-400'
                        }
                      >
                        {ent.risk_level === 'UNKNOWN' ? 'TBD' : `${Math.round(ent.risk_score ?? 0)}/100`}
                      </span>
                    </td>

                    <td className="py-3 px-3">
                      <span
                        className={`telemetry-badge ${
                          ent.verification_decision === 'CONFIRMED' || ent.verification_status === 'CONFIRMED'
                            ? 'badge-confirmed'
                            : ent.verification_decision === 'REJECTED'
                            ? 'badge-rejected'
                            : ent.verification_decision === 'INSUFFICIENT_EVIDENCE'
                            ? 'badge-insufficient'
                            : 'badge-unverified'
                        }`}
                      >
                        {ent.verification_decision || ent.verification_status || 'PENDING'}
                      </span>
                    </td>

                    <td className="py-3 px-3 font-mono text-[11px] text-emerald-400">
                      {Math.round(ent.confidence * 100)}%
                    </td>

                    <td className="py-3 px-3 font-mono text-[11px] text-slate-300">
                      Scene {ent.scene || 1} • {ent.timestamp ? `${ent.timestamp.toFixed(1)}s` : '00:14.7'}
                    </td>

                    <td className="py-3 px-3 font-mono text-[11px]">
                      {ent.resolution_action ? (
                        <div>
                          <span className="text-amber-400 font-bold">{ent.resolution_action}</span>
                          <span className="text-[10px] text-slate-400 ml-1">[{ent.resolution_priority || 'MED'}]</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">{ent.resolution_status || 'PENDING'}</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
