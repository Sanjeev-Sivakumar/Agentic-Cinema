import React from 'react';
import {
  AlertTriangle,
  ShieldCheck,
  AlertOctagon,
  HelpCircle,
  BarChart3,
  Eye,
  Layers,
  Flame,
  TrendingUp,
} from 'lucide-react';
import { Entity } from '../types';
import { RiskDistributionChart } from '../components/charts/RiskDistributionChart';

interface RiskProps {
  entities: Entity[];
}

export const Risk: React.FC<RiskProps> = ({ entities }) => {
  // Categorize entities strictly without collapsing UNKNOWN into LOW
  const unknownRiskList = entities.filter(
    (e) => e.risk_level === 'UNKNOWN' || (!e.risk_level && e.confidence < 0.35)
  );
  const highRiskList = entities.filter(
    (e) =>
      e.risk_level !== 'UNKNOWN' &&
      (e.risk_level === 'HIGH' || e.risk_score >= 70)
  );
  const medRiskList = entities.filter(
    (e) =>
      e.risk_level !== 'UNKNOWN' &&
      (e.risk_level === 'MEDIUM' || (e.risk_score >= 40 && e.risk_score < 70))
  );
  const lowRiskList = entities.filter(
    (e) =>
      e.risk_level !== 'UNKNOWN' &&
      (e.risk_level === 'LOW' || e.risk_score < 40)
  );

  // 1. Risk by Entity Type
  const entityTypes = Array.from(new Set(entities.map((e) => e.entity_type || 'OTHER')));
  const typeStats = entityTypes.map((t) => {
    const matching = entities.filter((e) => (e.entity_type || 'OTHER') === t);
    const high = matching.filter((e) => e.risk_level === 'HIGH' || (e.risk_score >= 70 && e.risk_level !== 'UNKNOWN')).length;
    const med = matching.filter((e) => e.risk_level === 'MEDIUM' || (e.risk_score >= 40 && e.risk_score < 70 && e.risk_level !== 'UNKNOWN')).length;
    const low = matching.filter((e) => e.risk_level === 'LOW' || (e.risk_score < 40 && e.risk_level !== 'UNKNOWN')).length;
    const unk = matching.filter((e) => e.risk_level === 'UNKNOWN').length;
    const avgScore = matching.length > 0 ? Math.round(matching.reduce((acc, curr) => acc + (curr.risk_score || 0), 0) / matching.length) : 0;
    return { type: t, total: matching.length, high, med, low, unk, avgScore };
  }).sort((a, b) => b.total - a.total);

  // 2. Risk Score Distribution Brackets: 0-19, 20-39, 40-59, 60-79, 80-100
  const brackets = [
    { label: '0-19', min: 0, max: 19, color: 'bg-emerald-500', count: 0 },
    { label: '20-39', min: 20, max: 39, color: 'bg-emerald-400', count: 0 },
    { label: '40-59', min: 40, max: 59, color: 'bg-amber-400', count: 0 },
    { label: '60-79', min: 60, max: 79, color: 'bg-amber-500', count: 0 },
    { label: '80-100', min: 80, max: 100, color: 'bg-red-500', count: 0 },
  ];
  entities.forEach((e) => {
    if (e.risk_level === 'UNKNOWN') return;
    const score = Math.max(0, Math.min(100, e.risk_score || 0));
    for (const b of brackets) {
      if (score >= b.min && score <= b.max) {
        b.count++;
        break;
      }
    }
  });
  const maxBracketCount = Math.max(...brackets.map((b) => b.count), 1);

  // 3. Visual-Only Risk Items
  const visualOnlyEntities = entities.filter(
    (e) =>
      e.classification === 'VISUAL_ONLY' ||
      (e.sources?.includes('VISUAL') && !e.sources?.includes('SCRIPT'))
  ).sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));

  // 4. Top High-Risk Entities Leaderboard
  const topHighRisk = [...entities]
    .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-bold font-mono uppercase text-slate-100">
              DETERMINISTIC PRODUCT TRIAGE & RISK ASSESSMENT
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Evaluates visual prominence, commercial impression, music rights, visual-only exposure, and research confidence.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px]">
          <span className="px-2.5 py-1 rounded bg-red-500/10 border border-red-500/30 text-red-400 font-bold">
            HIGH: {highRiskList.length}
          </span>
          <span className="px-2.5 py-1 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 font-bold">
            MED: {medRiskList.length}
          </span>
          <span className="px-2.5 py-1 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold">
            LOW: {lowRiskList.length}
          </span>
          <span className="px-2.5 py-1 rounded bg-slate-500/10 border border-slate-500/30 text-slate-400 font-bold">
            UNKNOWN: {unknownRiskList.length}
          </span>
        </div>
      </div>

      {/* 5 REQUIRED INTELLIGENCE CHARTS & VIEWS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* View 1: Overall Risk Distribution */}
        <div className="h-full">
          <RiskDistributionChart
            highRisk={highRiskList.length}
            medRisk={medRiskList.length}
            lowRisk={lowRiskList.length}
            unknownRisk={unknownRiskList.length}
          />
        </div>

        {/* View 2: Risk by Entity Type */}
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col">
          <div className="flex items-center justify-between pb-2 border-b border-[#1e293b] mb-3">
            <div className="flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
                RISK BY ENTITY TYPE
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">{typeStats.length} TYPES</span>
          </div>

          <div className="space-y-2.5 overflow-y-auto max-h-[160px] pr-1">
            {typeStats.length === 0 ? (
              <div className="text-xs text-slate-500 font-mono py-4 text-center">No entities registered</div>
            ) : (
              typeStats.map((st) => (
                <div key={st.type} className="text-[11px] font-mono bg-[#121826] p-2 rounded border border-[#1e293b]">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-slate-300">{st.type}</span>
                    <span className="text-slate-400">Avg Score: <strong className="text-amber-400">{st.avgScore}</strong> ({st.total})</span>
                  </div>
                  <div className="flex items-center gap-1 text-[10px]">
                    <span className="text-red-400">{st.high}H</span> •
                    <span className="text-amber-400">{st.med}M</span> •
                    <span className="text-emerald-400">{st.low}L</span>
                    {st.unk > 0 && <span className="text-slate-400"> • {st.unk}U</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* View 3: Risk Score Distribution (Histogram) */}
        <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col">
          <div className="flex items-center justify-between pb-2 border-b border-[#1e293b] mb-3">
            <div className="flex items-center gap-1.5">
              <BarChart3 className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
                SCORE DISTRIBUTION
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">[0 - 100] RANGE</span>
          </div>

          <div className="flex items-end justify-between gap-2 h-[120px] pt-4 pb-1">
            {brackets.map((b) => {
              const heightPct = Math.round((b.count / maxBracketCount) * 100);
              return (
                <div key={b.label} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[10px] font-mono text-slate-300 font-bold">{b.count}</span>
                  <div className="w-full bg-[#1e293b] rounded-t flex items-end h-[70px] overflow-hidden">
                    <div
                      style={{ height: `${Math.max(heightPct, 8)}%` }}
                      className={`w-full ${b.color} transition-all duration-300`}
                    />
                  </div>
                  <span className="text-[9px] font-mono text-slate-400">{b.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Row 2: Visual-Only Risk & Top High-Risk Entities */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* View 4: Visual-Only Risk */}
        <div className="bg-[#0e1320] border border-violet-500/30 rounded p-4 flex flex-col">
          <div className="flex items-center justify-between pb-2 border-b border-violet-500/20 mb-3">
            <div className="flex items-center gap-1.5">
              <Eye className="w-4 h-4 text-violet-400" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-violet-300">
                VISUAL-ONLY RISK EXPOSURE
              </span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-violet-500/20 text-violet-300 font-bold">
              {visualOnlyEntities.length} UNPLANNED ASSETS
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mb-3">
            Entities appearing in visual frames without script pre-clearance. High clearance exposure.
          </p>

          <div className="space-y-2 overflow-y-auto max-h-[200px] pr-1">
            {visualOnlyEntities.length === 0 ? (
              <div className="text-xs text-slate-500 font-mono py-4 text-center">
                No visual-only entities detected.
              </div>
            ) : (
              visualOnlyEntities.map((ent) => (
                <div
                  key={ent.id}
                  className="p-2.5 rounded bg-[#13111d] border border-violet-500/20 flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="font-semibold text-slate-200">{ent.name}</div>
                    <div className="text-[10px] font-mono text-violet-400 uppercase">
                      {ent.entity_type} • Scene {ent.scene || 1} • {ent.clearance_type || 'TRADEMARK'}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="font-mono font-bold text-amber-400">{ent.risk_score}/100</span>
                    <div className="text-[9px] font-mono text-red-400 uppercase font-bold">
                      {ent.risk_level}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* View 5: Top High-Risk Entities Leaderboard */}
        <div className="bg-[#0e1320] border border-red-500/30 rounded p-4 flex flex-col">
          <div className="flex items-center justify-between pb-2 border-b border-red-500/20 mb-3">
            <div className="flex items-center gap-1.5">
              <Flame className="w-4 h-4 text-red-400" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-red-300">
                TOP HIGH-RISK ENTITIES
              </span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-red-500/20 text-red-300 font-bold">
              PRIORITY TRIAGE
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mb-3">
            Highest clearance exposure items requiring immediate legal/production clearance review.
          </p>

          <div className="space-y-2 overflow-y-auto max-h-[200px] pr-1">
            {topHighRisk.length === 0 ? (
              <div className="text-xs text-slate-500 font-mono py-4 text-center">
                No entities evaluated yet.
              </div>
            ) : (
              topHighRisk.map((ent, idx) => (
                <div
                  key={ent.id}
                  className="p-2.5 rounded bg-[#161014] border border-red-500/20 flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs font-bold text-red-400/80">#{idx + 1}</span>
                    <div>
                      <div className="font-semibold text-slate-200">{ent.name}</div>
                      <div className="text-[10px] font-mono text-slate-400">
                        {ent.entity_type} • {ent.rights_holder || 'Unknown Holder'}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono font-bold text-red-400 text-sm">
                      {ent.risk_score}<span className="text-xs text-slate-500">/100</span>
                    </div>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-red-500/20 text-red-300 font-bold uppercase">
                      {ent.risk_level}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* 4-COLUMN RISK ASSESSMENT MATRIX */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Column 1: High Risk */}
        <div className="bg-[#0e1320] border border-red-500/30 rounded p-4 flex flex-col space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-red-500/20">
            <div className="flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-red-400" />
              <span className="text-xs font-mono font-bold text-red-300 uppercase">HIGH RISK [70-100]</span>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-red-500/20 text-red-300 font-bold">
              {highRiskList.length}
            </span>
          </div>

          <div className="space-y-2.5 overflow-y-auto max-h-[480px] pr-1">
            {highRiskList.length === 0 ? (
              <div className="text-xs text-slate-500 font-mono py-4 text-center">No high risk entities</div>
            ) : (
              highRiskList.map((ent) => (
                <div key={ent.id} className="p-3 rounded bg-[#141016] border border-red-500/20 space-y-1">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                    <span>{ent.name}</span>
                    <span className="font-mono text-red-400">{ent.risk_score}/100</span>
                  </div>
                  <div className="text-[10px] font-mono text-violet-300 uppercase">
                    {ent.classification || (ent.sources?.includes('VISUAL') ? 'VISUAL' : 'SCRIPT')} • {ent.entity_type}
                  </div>
                  <p className="text-[11px] text-slate-400 pt-1">
                    Significant clearance risk. Triage recommendation: blur or obtain commercial license.
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Column 2: Medium Risk */}
        <div className="bg-[#0e1320] border border-amber-500/30 rounded p-4 flex flex-col space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-amber-500/20">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-mono font-bold text-amber-300 uppercase">MEDIUM RISK [40-69]</span>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">
              {medRiskList.length}
            </span>
          </div>

          <div className="space-y-2.5 overflow-y-auto max-h-[480px] pr-1">
            {medRiskList.length === 0 ? (
              <div className="text-xs text-slate-500 font-mono py-4 text-center">No medium risk entities</div>
            ) : (
              medRiskList.map((ent) => (
                <div key={ent.id} className="p-3 rounded bg-[#161410] border border-amber-500/20 space-y-1">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                    <span>{ent.name}</span>
                    <span className="font-mono text-amber-400">{ent.risk_score}/100</span>
                  </div>
                  <div className="text-[10px] font-mono text-cyan-300 uppercase">
                    {ent.classification || (ent.sources?.includes('VISUAL') ? 'VISUAL' : 'SCRIPT')} • {ent.entity_type}
                  </div>
                  <p className="text-[11px] text-slate-400 pt-1">
                    Moderate exposure. Verification with rights holder or fair use assessment recommended.
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Column 3: Low Risk */}
        <div className="bg-[#0e1320] border border-emerald-500/30 rounded p-4 flex flex-col space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-emerald-500/20">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-mono font-bold text-emerald-300 uppercase">LOW / FAIR USE [0-39]</span>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
              {lowRiskList.length}
            </span>
          </div>

          <div className="space-y-2.5 overflow-y-auto max-h-[480px] pr-1">
            {lowRiskList.length === 0 ? (
              <div className="text-xs text-slate-500 font-mono py-4 text-center">No low risk entities</div>
            ) : (
              lowRiskList.map((ent) => (
                <div key={ent.id} className="p-3 rounded bg-[#0e1714] border border-emerald-500/20 space-y-1">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                    <span>{ent.name}</span>
                    <span className="font-mono text-emerald-400">{ent.risk_score}/100</span>
                  </div>
                  <div className="text-[10px] font-mono text-emerald-300 uppercase">
                    {ent.classification || (ent.sources?.includes('VISUAL') ? 'VISUAL' : 'SCRIPT')} • {ent.entity_type}
                  </div>
                  <p className="text-[11px] text-slate-400 pt-1">
                    Incidental / de minimis narrative use. Low clearance priority under standard doctrine.
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Column 4: Unknown Risk */}
        <div className="bg-[#0e1320] border border-slate-500/30 rounded p-4 flex flex-col space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-500/20">
            <div className="flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-mono font-bold text-slate-300 uppercase">UNKNOWN / REVIEW</span>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-500/20 text-slate-300 font-bold">
              {unknownRiskList.length}
            </span>
          </div>

          <div className="space-y-2.5 overflow-y-auto max-h-[480px] pr-1">
            {unknownRiskList.length === 0 ? (
              <div className="text-xs text-slate-500 font-mono py-4 text-center">No unclassified entities</div>
            ) : (
              unknownRiskList.map((ent) => (
                <div key={ent.id} className="p-3 rounded bg-[#12141c] border border-slate-500/20 space-y-1">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                    <span>{ent.name}</span>
                    <span className="font-mono text-slate-400">TBD</span>
                  </div>
                  <div className="text-[10px] font-mono text-slate-400 uppercase">
                    {ent.classification || 'UNCLASSIFIED'} • {ent.entity_type || 'UNKNOWN'}
                  </div>
                  <p className="text-[11px] text-slate-400 pt-1">
                    Insufficient evidence or low detection confidence (&lt;35%). Manual review recommended.
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

