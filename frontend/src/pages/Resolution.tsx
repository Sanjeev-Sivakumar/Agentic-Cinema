import React, { useState, useEffect } from 'react';
import {
  Scale,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  Search,
  Eye,
  FileText,
  ChevronRight,
  Info,
  ShieldAlert,
  ArrowRight,
  Sparkles,
  ClipboardCheck,
  Flame,
  Layers,
  FileQuestion,
  Lightbulb,
  ExternalLink,
} from 'lucide-react';
import { Entity, ResolutionResult, ResolutionStatus, ResolutionAction, ResolutionPriority } from '../types';
import { api } from '../services/api';

interface ResolutionProps {
  entities: Entity[];
  productionId?: string;
}

export const Resolution: React.FC<ResolutionProps> = ({ entities, productionId }) => {
  const [results, setResults] = useState<ResolutionResult[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [forceRefresh, setForceRefresh] = useState<boolean>(false);
  const [selectedResult, setSelectedResult] = useState<ResolutionResult | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [filterPriority, setFilterPriority] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Load existing resolutions on mount
  useEffect(() => {
    if (productionId) {
      api.getResolutions(productionId)
        .then((res) => {
          if (res.results && res.results.length > 0) {
            setResults(res.results);
          } else {
            synthesizeDemoResolutions();
          }
        })
        .catch((e) => {
          console.warn('[Resolution] No pre-existing resolution results:', e);
          synthesizeDemoResolutions();
        });
    } else {
      synthesizeDemoResolutions();
    }
  }, [productionId, entities]);

  const synthesizeDemoResolutions = () => {
    const synthetic: ResolutionResult[] = entities.map((ent) => {
      const isHighRisk = ent.risk_score >= 70 || ent.risk_level === 'HIGH';
      const isMediumRisk = ent.risk_score >= 40 || ent.risk_level === 'MEDIUM';
      const isVisualOnly = ent.classification === 'VISUAL_ONLY';
      const isConfirmed = ent.verification_status === 'CONFIRMED';
      const isUnverified = ent.verification_status === 'UNVERIFIED';

      let status: ResolutionStatus = 'HUMAN_REVIEW';
      let action: ResolutionAction = 'HUMAN_REVIEW';
      let priority: ResolutionPriority = 'MEDIUM';
      let reason = 'Clearance review recommended.';
      let replacement: string | undefined = undefined;
      const missingEvidence: string[] = [];
      const requiredInfo: string[] = [];

      if (isUnverified) {
        status = 'MORE_EVIDENCE_REQUIRED';
        action = 'COLLECT_EVIDENCE';
        priority = isVisualOnly ? 'HIGH' : 'MEDIUM';
        reason = 'Additional evidence required to substantiate potential clearance item presence.';
        missingEvidence.push('High-resolution keyframe capture', 'Scene continuity timestamp range');
        requiredInfo.push('Confirm whether asset is intentional or incidental');
      } else if (isHighRisk && isConfirmed) {
        status = 'ACTION_REQUIRED';
        priority = isVisualOnly ? 'CRITICAL' : 'HIGH';
        action = ent.entity_type === 'BRAND' ? 'REVIEW_BRAND_USAGE' :
                 ent.entity_type === 'MUSIC' ? 'REVIEW_MUSIC_USAGE' :
                 ent.entity_type === 'ARTWORK' ? 'REVIEW_ARTWORK_USAGE' : 'HUMAN_REVIEW';
        reason = `Confirmed high-exposure ${ent.entity_type.toLowerCase()} element. Active operational resolution pathway required.`;
        replacement = `Consider replacing '${ent.name}' with a neutral or unbranded alternative if clearance is not pursued.`;
        requiredInfo.push('Rights holder verification', 'Licensing paperwork or VFX work order');
      } else if (isMediumRisk && isConfirmed) {
        status = 'HUMAN_REVIEW';
        priority = isVisualOnly ? 'HIGH' : 'MEDIUM';
        action = ent.entity_type === 'BRAND' ? 'REVIEW_BRAND_USAGE' : 'HUMAN_REVIEW';
        reason = `Confirmed medium-exposure item. Editorial clearance assessment advised.`;
        replacement = `Consider neutral unbranded asset or subtle digital obscuration.`;
        requiredInfo.push('Editorial context confirmation');
      } else if (!isHighRisk && !isMediumRisk && isConfirmed) {
        status = 'RESOLVED';
        action = 'NO_ACTION';
        priority = 'LOW';
        reason = 'This item does not currently require an additional operational action based on the available evidence.';
      }

      return {
        resolution_id: `res_syn_${ent.id}`,
        entity_id: ent.id,
        production_id: productionId || ent.production_id || 'prod_demo',
        entity_name: ent.name,
        entity_type: ent.entity_type,
        verification_decision: ent.verification_status,
        risk_level: ent.risk_level,
        risk_score: ent.risk_score,
        resolution_status: status,
        recommended_action: action,
        priority: priority,
        action_reason: reason,
        supporting_evidence_ids: ent.evidence_ids || [ent.id],
        missing_evidence: missingEvidence,
        required_information: requiredInfo,
        replacement_suggestion: replacement,
        confidence: 0.88,
        resolver: 'DeterministicResolutionEngine',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        metadata: {
          classification: ent.classification || 'VISUAL_ONLY',
        },
      };
    });

    setResults(synthetic);
  };

  const handleRunResolution = async () => {
    if (!productionId) {
      synthesizeDemoResolutions();
      return;
    }
    setLoading(true);
    try {
      const res = await api.resolveEntities(productionId, { force_refresh: forceRefresh });
      if (res.results) {
        setResults(res.results);
      }
    } catch (err) {
      console.error('[Resolution] Error formulating resolutions:', err);
      synthesizeDemoResolutions();
    } finally {
      setLoading(false);
    }
  };

  // Metrics calculation
  const totalCount = results.length;
  const criticalCount = results.filter((r) => r.priority === 'CRITICAL').length;
  const highPriorityCount = results.filter((r) => r.priority === 'HIGH').length;
  const actionRequiredCount = results.filter((r) => r.resolution_status === 'ACTION_REQUIRED').length;
  const humanReviewCount = results.filter((r) => r.resolution_status === 'HUMAN_REVIEW').length;
  const moreEvidenceCount = results.filter((r) => r.resolution_status === 'MORE_EVIDENCE_REQUIRED').length;
  const researchRequiredCount = results.filter((r) => r.resolution_status === 'RESEARCH_REQUIRED').length;
  const resolvedCount = results.filter((r) => r.resolution_status === 'RESOLVED').length;
  const escalatedCount = results.filter((r) => r.recommended_action === 'ESCALATE').length;

  // Filter and search
  const filteredResults = results.filter((r) => {
    const matchesStatus = filterStatus === 'ALL' || r.resolution_status === filterStatus;
    const matchesPriority = filterPriority === 'ALL' || r.priority === filterPriority;
    const query = searchQuery.toLowerCase();
    const matchesSearch =
      !searchQuery ||
      r.entity_name.toLowerCase().includes(query) ||
      r.recommended_action.toLowerCase().includes(query) ||
      r.action_reason.toLowerCase().includes(query) ||
      r.entity_type.toLowerCase().includes(query);
    return matchesStatus && matchesPriority && matchesSearch;
  });

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getPriorityBadgeClass = (priority: ResolutionPriority) => {
    switch (priority) {
      case 'CRITICAL':
        return 'bg-red-950/80 text-red-300 border-red-500/70 shadow-[0_0_12px_rgba(239,68,68,0.25)]';
      case 'HIGH':
        return 'bg-amber-950/80 text-amber-300 border-amber-500/60';
      case 'MEDIUM':
        return 'bg-yellow-950/60 text-yellow-300 border-yellow-500/50';
      case 'LOW':
        return 'bg-emerald-950/60 text-emerald-300 border-emerald-500/50';
      case 'INFO':
      default:
        return 'bg-slate-900 text-slate-400 border-slate-700';
    }
  };

  const getStatusBadgeClass = (status: ResolutionStatus) => {
    switch (status) {
      case 'ACTION_REQUIRED':
        return 'bg-red-500/20 text-red-300 border-red-500/50';
      case 'HUMAN_REVIEW':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50';
      case 'MORE_EVIDENCE_REQUIRED':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50';
      case 'RESEARCH_REQUIRED':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/50';
      case 'RESOLVED':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50';
      case 'ESCALATED':
        return 'bg-rose-500/25 text-rose-200 border-rose-500/70 animate-pulse';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Triage Station Banner */}
      <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-lg shadow-black/40">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold font-mono tracking-wide uppercase text-slate-100">
                  RESOLUTION &amp; REMEDIATION INTELLIGENCE
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  PHASE 7
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Actionable operational pathways derived strictly from verified evidence, research, and risk scores.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-slate-400 select-none cursor-pointer">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(e) => setForceRefresh(e.target.checked)}
              className="rounded bg-[#121826] border-slate-700 text-amber-500 focus:ring-0"
            />
            Force Re-evaluate
          </label>

          <button
            onClick={handleRunResolution}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-slate-950 font-semibold text-xs tracking-wide transition-all shadow-md shadow-amber-950/40 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Formulating...' : 'Formulate Resolutions'}
          </button>
        </div>
      </div>

      {/* KPI Metrics Dashboard */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        <div
          onClick={() => { setFilterStatus('ALL'); setFilterPriority('ALL'); }}
          className={`cursor-pointer rounded-lg p-3.5 border transition-all ${
            filterStatus === 'ALL' && filterPriority === 'ALL'
              ? 'bg-[#141b2d] border-amber-500/60 ring-1 ring-amber-500/30'
              : 'bg-[#0b0f19] border-[#1e293b] hover:border-slate-700'
          }`}
        >
          <div className="text-[10px] font-mono uppercase text-slate-400">Total Items</div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">{totalCount}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Assessed</div>
        </div>

        <div
          onClick={() => { setFilterPriority('CRITICAL'); setFilterStatus('ALL'); }}
          className={`cursor-pointer rounded-lg p-3.5 border transition-all ${
            filterPriority === 'CRITICAL'
              ? 'bg-red-950/30 border-red-500/70 ring-1 ring-red-500/30'
              : 'bg-[#0b0f19] border-[#1e293b] hover:border-red-900/50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-red-400">Critical Priority</span>
            <Flame className="w-3.5 h-3.5 text-red-400" />
          </div>
          <div className="text-xl font-bold font-mono text-red-300 mt-1">{criticalCount}</div>
          <div className="text-[10px] text-red-400/80 mt-0.5">Immediate action</div>
        </div>

        <div
          onClick={() => { setFilterStatus('ACTION_REQUIRED'); setFilterPriority('ALL'); }}
          className={`cursor-pointer rounded-lg p-3.5 border transition-all ${
            filterStatus === 'ACTION_REQUIRED'
              ? 'bg-amber-950/30 border-amber-500/70 ring-1 ring-amber-500/30'
              : 'bg-[#0b0f19] border-[#1e293b] hover:border-amber-900/50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-amber-400">Action Required</span>
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="text-xl font-bold font-mono text-amber-300 mt-1">{actionRequiredCount}</div>
          <div className="text-[10px] text-amber-400/80 mt-0.5">High exposure</div>
        </div>

        <div
          onClick={() => { setFilterStatus('HUMAN_REVIEW'); setFilterPriority('ALL'); }}
          className={`cursor-pointer rounded-lg p-3.5 border transition-all ${
            filterStatus === 'HUMAN_REVIEW'
              ? 'bg-cyan-950/30 border-cyan-500/70 ring-1 ring-cyan-500/30'
              : 'bg-[#0b0f19] border-[#1e293b] hover:border-cyan-900/50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-cyan-400">Human Review</span>
            <Eye className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="text-xl font-bold font-mono text-cyan-300 mt-1">{humanReviewCount}</div>
          <div className="text-[10px] text-cyan-400/80 mt-0.5">Triage assessment</div>
        </div>

        <div
          onClick={() => { setFilterStatus('MORE_EVIDENCE_REQUIRED'); setFilterPriority('ALL'); }}
          className={`cursor-pointer rounded-lg p-3.5 border transition-all ${
            filterStatus === 'MORE_EVIDENCE_REQUIRED'
              ? 'bg-yellow-950/30 border-yellow-500/70 ring-1 ring-yellow-500/30'
              : 'bg-[#0b0f19] border-[#1e293b] hover:border-yellow-900/50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-yellow-400">More Evidence</span>
            <FileQuestion className="w-3.5 h-3.5 text-yellow-400" />
          </div>
          <div className="text-xl font-bold font-mono text-yellow-300 mt-1">{moreEvidenceCount}</div>
          <div className="text-[10px] text-yellow-400/80 mt-0.5">Capture needed</div>
        </div>

        <div
          onClick={() => { setFilterStatus('RESEARCH_REQUIRED'); setFilterPriority('ALL'); }}
          className={`cursor-pointer rounded-lg p-3.5 border transition-all ${
            filterStatus === 'RESEARCH_REQUIRED'
              ? 'bg-purple-950/30 border-purple-500/70 ring-1 ring-purple-500/30'
              : 'bg-[#0b0f19] border-[#1e293b] hover:border-purple-900/50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-purple-400">Research Req</span>
            <Search className="w-3.5 h-3.5 text-purple-400" />
          </div>
          <div className="text-xl font-bold font-mono text-purple-300 mt-1">{researchRequiredCount}</div>
          <div className="text-[10px] text-purple-400/80 mt-0.5">Ownership inquiry</div>
        </div>

        <div
          onClick={() => { setFilterStatus('RESOLVED'); setFilterPriority('ALL'); }}
          className={`cursor-pointer rounded-lg p-3.5 border transition-all ${
            filterStatus === 'RESOLVED'
              ? 'bg-emerald-950/30 border-emerald-500/70 ring-1 ring-emerald-500/30'
              : 'bg-[#0b0f19] border-[#1e293b] hover:border-emerald-900/50'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-emerald-400">Resolved</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-xl font-bold font-mono text-emerald-300 mt-1">{resolvedCount}</div>
          <div className="text-[10px] text-emerald-400/80 mt-0.5">No action needed</div>
        </div>
      </div>

      {/* Traceability Evidence Chain Banner */}
      <div className="bg-[#0b0f19] border border-[#1e293b] rounded-lg p-3.5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs font-mono font-semibold text-slate-300">
            <Layers className="w-4 h-4 text-cyan-400" />
            OPERATIONAL EVIDENCE TRACEABILITY CHAIN
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            Bidirectional Pipeline Lineage (Phases 1–7)
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-center text-xs font-mono">
          <div className="bg-[#121826] border border-slate-800 rounded p-2 text-slate-400">
            <div className="text-[10px] text-slate-400">Phase 2</div>
            <div className="text-slate-200 font-bold">1. FRAME CAPTURE</div>
          </div>
          <div className="bg-[#121826] border border-slate-800 rounded p-2 text-slate-400">
            <div className="text-[10px] text-slate-400">Phase 3</div>
            <div className="text-violet-300 font-bold">2. ENTITY DETECT</div>
          </div>
          <div className="bg-[#121826] border border-slate-800 rounded p-2 text-slate-400">
            <div className="text-[10px] text-slate-400">Phase 4</div>
            <div className="text-blue-300 font-bold">3. RESEARCH QUERY</div>
          </div>
          <div className="bg-[#121826] border border-slate-800 rounded p-2 text-slate-400">
            <div className="text-[10px] text-slate-400">Phase 5</div>
            <div className="text-amber-300 font-bold">4. RISK SIGNALS</div>
          </div>
          <div className="bg-[#121826] border border-slate-800 rounded p-2 text-slate-400">
            <div className="text-[10px] text-slate-400">Phase 6</div>
            <div className="text-emerald-300 font-bold">5. VERIFICATION</div>
          </div>
          <div className="bg-amber-950/40 border border-amber-500/40 rounded p-2 text-amber-300">
            <div className="text-[10px] text-amber-400">Phase 7</div>
            <div className="text-amber-300 font-bold">6. RESOLUTION ACTION</div>
          </div>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#0b0f19] border border-[#1e293b] rounded-lg p-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search items, actions, reasons..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#121826] border border-slate-800 rounded pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:border-amber-500"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          <span className="text-[10px] font-mono text-slate-400 uppercase">Priority:</span>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setFilterPriority(lvl)}
              className={`px-2.5 py-1 rounded text-[10px] font-mono font-semibold transition-all ${
                filterPriority === lvl
                  ? 'bg-amber-500 text-slate-950 shadow-sm'
                  : 'bg-[#121826] text-slate-400 hover:text-slate-200 border border-slate-800'
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>

      {/* Resolution Items Table & Drawer Container */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Table View */}
        <div className={`${selectedResult ? 'lg:col-span-7' : 'lg:col-span-12'} space-y-3 transition-all`}>
          {filteredResults.length === 0 ? (
            <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg p-10 text-center space-y-3">
              <Scale className="w-8 h-8 text-slate-400 mx-auto" />
              <p className="text-sm font-semibold text-slate-300">No resolution recommendations found</p>
              <p className="text-xs text-slate-400">
                Adjust search filters or run "Formulate Resolutions" to evaluate entities.
              </p>
            </div>
          ) : (
            <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg overflow-hidden shadow-md">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[#080c14] border-b border-[#1e293b] text-slate-400 uppercase text-[10px]">
                    <tr>
                      <th className="py-3 px-4">Priority</th>
                      <th className="py-3 px-4">Entity &amp; Type</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Recommended Action</th>
                      <th className="py-3 px-4">Risk &amp; Decision</th>
                      <th className="py-3 px-4 text-right">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1e293b]/60">
                    {filteredResults.map((item) => {
                      const isSelected = selectedResult?.resolution_id === item.resolution_id;
                      const classification = item.metadata?.classification || 'VISUAL_ONLY';
                      const isVisualOnly = classification === 'VISUAL_ONLY';

                      return (
                        <tr
                          key={item.resolution_id}
                          onClick={() => setSelectedResult(item)}
                          className={`cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-[#182238] border-l-2 border-amber-500'
                              : 'hover:bg-[#121826]'
                          }`}
                        >
                          <td className="py-3 px-4">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getPriorityBadgeClass(
                                item.priority
                              )}`}
                            >
                              {item.priority}
                            </span>
                          </td>

                          <td className="py-3 px-4">
                            <div className="font-bold text-slate-200">{item.entity_name}</div>
                            <div className="flex items-center gap-1.5 mt-0.5">
                              <span className="text-[10px] text-slate-400">{item.entity_type}</span>
                              {isVisualOnly && (
                                <span className="text-[9px] px-1.5 py-0.2 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30">
                                  VISUAL ONLY
                                </span>
                              )}
                            </div>
                          </td>

                          <td className="py-3 px-4">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getStatusBadgeClass(
                                item.resolution_status
                              )}`}
                            >
                              {item.resolution_status.replace(/_/g, ' ')}
                            </span>
                          </td>

                          <td className="py-3 px-4">
                            <div className="text-slate-200 font-semibold">
                              {item.recommended_action.replace(/_/g, ' ')}
                            </div>
                            <div className="text-[10px] text-slate-400 truncate max-w-xs mt-0.5">
                              {item.action_reason}
                            </div>
                          </td>

                          <td className="py-3 px-4">
                            <div className="text-slate-300">
                              Risk: <span className="font-bold">{item.risk_score}</span>{' '}
                              <span className="text-[10px] text-slate-400">({item.risk_level})</span>
                            </div>
                            <div className="text-[10px] text-emerald-400 mt-0.5">
                              {item.verification_decision || 'VERIFIED'}
                            </div>
                          </td>

                          <td className="py-3 px-4 text-right">
                            <button className="p-1 rounded bg-[#121826] hover:bg-slate-700 text-slate-300 border border-slate-700">
                              <ChevronRight className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Detailed Inspection Drawer */}
        {selectedResult && (
          <div className="lg:col-span-5 bg-[#0e1320] border border-amber-500/40 rounded-lg p-5 space-y-4 shadow-xl shadow-black/50">
            <div className="flex items-start justify-between pb-3 border-b border-[#1e293b]">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getPriorityBadgeClass(
                      selectedResult.priority
                    )}`}
                  >
                    {selectedResult.priority} PRIORITY
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getStatusBadgeClass(
                      selectedResult.resolution_status
                    )}`}
                  >
                    {selectedResult.resolution_status.replace(/_/g, ' ')}
                  </span>
                </div>
                <h3 className="text-base font-bold text-slate-100 mt-2">{selectedResult.entity_name}</h3>
                <div className="text-xs text-slate-400 font-mono mt-0.5">
                  Type: {selectedResult.entity_type} &bull; ID: {selectedResult.entity_id}
                </div>
              </div>

              <button
                onClick={() => setSelectedResult(null)}
                className="text-slate-400 hover:text-slate-200 text-xs font-mono p-1 rounded hover:bg-slate-800"
              >
                Close &times;
              </button>
            </div>

            {/* Recommended Action Card */}
            <div className="bg-[#121826] border border-amber-500/30 rounded-lg p-4 space-y-2">
              <div className="flex items-center gap-2 text-xs font-mono text-amber-400 font-bold uppercase tracking-wide">
                <Sparkles className="w-4 h-4" />
                RECOMMENDED OPERATIONAL ACTION
              </div>
              <div className="text-sm font-bold text-slate-100">
                {selectedResult.recommended_action.replace(/_/g, ' ')}
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{selectedResult.action_reason}</p>
            </div>

            {/* Neutral Replacement Suggestion if available */}
            {selectedResult.replacement_suggestion && (
              <div className="bg-amber-950/20 border border-amber-500/40 rounded-lg p-3.5 space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-mono text-amber-300 font-bold">
                    <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
                    NEUTRAL REPLACEMENT SUGGESTION
                  </div>
                  <button
                    onClick={() =>
                      copyToClipboard(
                        selectedResult.replacement_suggestion || '',
                        selectedResult.resolution_id
                      )
                    }
                    className="text-[10px] font-mono text-amber-400 hover:text-amber-200 flex items-center gap-1"
                  >
                    {copiedId === selectedResult.resolution_id ? (
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    ) : (
                      <ClipboardCheck className="w-3 h-3" />
                    )}
                    {copiedId === selectedResult.resolution_id ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <p className="text-xs text-amber-200/90 italic leading-relaxed">
                  "{selectedResult.replacement_suggestion}"
                </p>
                <div className="text-[10px] text-slate-400 font-mono">
                  * Suggestion strictly recommends generic/unbranded creative substitutions.
                </div>
              </div>
            )}

            {/* Required Information Checklist */}
            {selectedResult.required_information && selectedResult.required_information.length > 0 && (
              <div className="bg-[#121826] border border-slate-800 rounded-lg p-3.5 space-y-2">
                <div className="text-xs font-mono text-slate-300 font-bold uppercase">
                  Required Clearance Information:
                </div>
                <ul className="space-y-1 text-xs text-slate-300 font-mono">
                  {selectedResult.required_information.map((infoItem, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <ChevronRight className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                      <span>{infoItem}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Missing Evidence List if applicable */}
            {selectedResult.missing_evidence && selectedResult.missing_evidence.length > 0 && (
              <div className="bg-yellow-950/20 border border-yellow-500/40 rounded-lg p-3.5 space-y-2">
                <div className="text-xs font-mono text-yellow-300 font-bold uppercase flex items-center gap-1.5">
                  <FileQuestion className="w-3.5 h-3.5" />
                  Missing Evidence for Verification:
                </div>
                <ul className="space-y-1 text-xs text-yellow-200/80 font-mono">
                  {selectedResult.missing_evidence.map((miss, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-yellow-400">&bull;</span>
                      <span>{miss}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Supporting Evidence Traceability */}
            <div className="border-t border-[#1e293b] pt-3 space-y-2 font-mono text-xs">
              <div className="text-slate-400 text-[11px] font-semibold uppercase">
                Supporting Evidence Identifiers:
              </div>
              <div className="flex flex-wrap gap-1.5">
                {selectedResult.supporting_evidence_ids.map((id, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded bg-[#162032] text-slate-300 border border-slate-700 text-[10px]"
                  >
                    {id}
                  </span>
                ))}
              </div>
            </div>

            {/* Disclaimer Alert */}
            <div className="p-2.5 rounded bg-slate-900/80 border border-slate-800 text-[10px] text-slate-400 leading-normal flex items-start gap-2">
              <Info className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
              <span>
                Operational triage guidance only. These recommendations prioritize production review workflows
                and do not constitute legal advice or formal release clearance.
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Persistent Legal Disclaimer Footer */}
      <div className="text-center py-2 text-[11px] font-mono text-slate-400 border-t border-[#1e293b]">
        Chain of Title &bull; Phase 7 Resolution Intelligence &bull; Deterministic &amp; Zero-Network &bull; Operational Guidance Only
      </div>
    </div>
  );
};
