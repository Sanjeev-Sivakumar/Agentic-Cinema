import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  ExternalLink,
  RefreshCw,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Eye,
  Layers,
  Search,
  CheckSquare,
  ChevronRight,
  Info,
  Clock,
  DollarSign,
  User,
  X,
} from 'lucide-react';
import { Entity, Production, ReportFinding, ReportResult } from '../types';
import { api } from '../services/api';

interface ReportsProps {
  currentProduction: Production | null;
  entities: Entity[];
}

export const Reports: React.FC<ReportsProps> = ({ currentProduction, entities }) => {
  const [report, setReport] = useState<ReportResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'EXECUTIVE' | 'PRIORITY' | 'VISUAL_ONLY' | 'ALL_FINDINGS'>('EXECUTIVE');
  const [selectedFinding, setSelectedFinding] = useState<ReportFinding | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const productionId = currentProduction?.id;

  const fetchReport = async () => {
    if (!productionId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getProductionReportResult(productionId);
      setReport(data);
    } catch (err: any) {
      console.warn('[Reports] Could not load pre-generated report result, will allow generation:', err);
      // Not a fatal error if report has not been created yet
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async (forceRefresh: boolean = false) => {
    if (!productionId) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await api.generateProductionReport(productionId, { force_refresh: forceRefresh });
      setReport(res);
    } catch (err: any) {
      setError(err.message || 'Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    if (productionId) {
      fetchReport();
    }
  }, [productionId]);

  // Fallback calculations if report is not yet generated
  const visualOnlyEntities = entities.filter(
    (e) => e.classification === 'VISUAL_ONLY' || (e.sources?.includes('VISUAL') && !e.sources?.includes('SCRIPT'))
  );
  const highRiskEntities = entities.filter((e) => (e.risk_score || 0) >= 0.7 || e.risk_level === 'HIGH');

  const totalCount = report?.total_entities ?? entities.length;
  const visualOnlyCount = report?.classification_counts?.VISUAL_ONLY ?? visualOnlyEntities.length;
  const highRiskCount = report?.risk_distribution?.HIGH ?? highRiskEntities.length;
  const researchCoveragePct = report ? (report.research_coverage * 100).toFixed(1) : '—';
  const verifCoveragePct = report ? (report.verification_coverage * 100).toFixed(1) : '—';
  const resolCoveragePct = report ? (report.resolution_coverage * 100).toFixed(1) : '—';

  // Filter findings
  const getFilteredFindings = (list: ReportFinding[]) => {
    if (!searchQuery.trim()) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (f) =>
        f.entity_name.toLowerCase().includes(q) ||
        f.entity_type.toLowerCase().includes(q) ||
        f.classification.toLowerCase().includes(q) ||
        (f.resolution_action || '').toLowerCase().includes(q)
    );
  };

  const priorityFindings = getFilteredFindings(report?.priority_findings || []);
  const visualFindings = getFilteredFindings(report?.visual_only_findings || []);
  const allFindings = getFilteredFindings(report?.all_findings || []);

  const badgeColor = (val: string = '', type: 'risk' | 'cls' | 'verif' | 'prio') => {
    const v = val.toUpperCase();
    if (type === 'risk') {
      if (v === 'HIGH') return 'bg-red-500/20 text-red-400 border-red-500/30';
      if (v === 'MEDIUM') return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    }
    if (type === 'cls') {
      if (v === 'VISUAL_ONLY') return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
      if (v === 'BOTH') return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
    if (type === 'verif') {
      if (v === 'VERIFIED') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      if (v === 'CONTRADICTED') return 'bg-red-500/20 text-red-400 border-red-500/30';
      return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
    if (type === 'prio') {
      if (v === 'CRITICAL') return 'bg-red-600/30 text-red-300 border-red-500/50';
      if (v === 'HIGH') return 'bg-amber-600/30 text-amber-300 border-amber-500/50';
      return 'bg-slate-700/30 text-slate-300 border-slate-600/40';
    }
    return 'bg-slate-800 text-slate-300 border-slate-700';
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Top Header Card */}
      <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <FileText className="w-4 h-4 text-amber-400" />
              <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">
                PHASE 8 &bull; CLEARANCE INTELLIGENCE REPORT
              </span>
              {report?.version && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  v{report.version}
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold font-mono text-slate-100 uppercase tracking-tight">
              {currentProduction?.title ? `${currentProduction.title} Pre-Clearance Audit` : 'Production Clearance Audit'}
            </h1>
            <div className="text-xs text-slate-400 mt-1 font-mono flex items-center gap-3">
              <span>ID: <strong className="text-slate-300">{productionId || 'Unknown'}</strong></span>
              {report?.generated_at && (
                <span>Generated: <strong className="text-slate-300">{new Date(report.generated_at).toLocaleString()}</strong></span>
              )}
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleGenerateReport(true)}
              disabled={generating}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-mono font-semibold transition disabled:opacity-50"
              title="Re-aggregate and regenerate report from latest repository artifacts"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin text-amber-400' : ''}`} />
              {generating ? 'GENERATING...' : report ? 'REFRESH REPORT' : 'GENERATE REPORT'}
            </button>

            {productionId && (
              <>
                <a
                  href={api.getReportHtmlUrl(productionId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 text-xs font-mono font-semibold transition"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  VIEW HTML
                </a>

                <a
                  href={api.getReportPdfUrl(productionId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded bg-amber-500 hover:bg-amber-400 text-black font-semibold font-mono text-xs shadow-[0_0_12px_rgba(245,158,11,0.25)] transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  EXPORT PDF
                </a>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Error Banner if any */}
      {error && (
        <div className="bg-red-950/40 border border-red-500/50 rounded-lg p-4 flex items-start gap-3 text-red-200 text-xs font-mono">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <strong className="font-bold">Error Generating Report:</strong> {error}
          </div>
        </div>
      )}

      {/* Mandatory Legal Disclaimer Banner */}
      <div className="bg-amber-950/30 border border-amber-600/50 border-l-4 border-l-amber-500 rounded-lg p-4 text-xs text-amber-200/90 leading-relaxed font-sans">
        <div className="flex items-center gap-2 font-mono font-bold uppercase tracking-wider text-amber-400 mb-1 text-[11px]">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          Mandatory Non-Legal Advice Notice
        </div>
        {report?.disclaimer ||
          'LEGAL DISCLAIMER: This Pre-Clearance Intelligence Report is generated by automated multi-agent analysis for operational clearance-workflow and preliminary risk evaluation purposes only. This report DOES NOT constitute legal advice, a formal legal opinion, or an errors & omissions (E&O) insurance binder. Clearance determinations and fair use evaluations must be reviewed by qualified legal counsel.'}
      </div>

      {/* Executive KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3.5 rounded-lg bg-[#0e1320] border border-[#1e293b]">
          <div className="text-slate-400 text-[10px] font-mono uppercase tracking-wider">TOTAL ENTITIES</div>
          <div className="text-2xl font-bold font-mono text-slate-100 mt-1">{totalCount}</div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">Screenplay + Video</div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#0e1320] border border-purple-500/30 border-l-2 border-l-purple-400">
          <div className="text-purple-400 text-[10px] font-mono uppercase tracking-wider">VISUAL-ONLY SPOTLIGHT</div>
          <div className="text-2xl font-bold font-mono text-purple-300 mt-1">{visualOnlyCount}</div>
          <div className="text-[10px] text-purple-400/70 font-mono mt-0.5">Unscripted exposure</div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#0e1320] border border-red-500/30 border-l-2 border-l-red-400">
          <div className="text-red-400 text-[10px] font-mono uppercase tracking-wider">HIGH RISK ITEMS</div>
          <div className="text-2xl font-bold font-mono text-red-300 mt-1">{highRiskCount}</div>
          <div className="text-[10px] text-red-400/70 font-mono mt-0.5">Action required</div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#0e1320] border border-[#1e293b]">
          <div className="text-slate-400 text-[10px] font-mono uppercase tracking-wider">RESEARCH COVERAGE</div>
          <div className="text-2xl font-bold font-mono text-slate-100 mt-1">{researchCoveragePct}%</div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">{report?.researched_count ?? 0} queried</div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#0e1320] border border-[#1e293b]">
          <div className="text-slate-400 text-[10px] font-mono uppercase tracking-wider">VERIFIED COVERAGE</div>
          <div className="text-2xl font-bold font-mono text-slate-100 mt-1">{verifCoveragePct}%</div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">{report?.verified_count ?? 0} checked</div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#0e1320] border border-[#1e293b]">
          <div className="text-slate-400 text-[10px] font-mono uppercase tracking-wider">RESOLVED COVERAGE</div>
          <div className="text-2xl font-bold font-mono text-slate-100 mt-1">{resolCoveragePct}%</div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">{report?.resolved_count ?? 0} formulated</div>
        </div>
      </div>

      {/* Navigation Tabs & Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#1e293b] pb-2">
        <div className="flex items-center gap-1 font-mono text-xs">
          <button
            onClick={() => setActiveTab('EXECUTIVE')}
            className={`px-3.5 py-2 rounded-t transition border-b-2 font-semibold ${
              activeTab === 'EXECUTIVE'
                ? 'bg-[#1e293b]/60 text-amber-400 border-amber-400'
                : 'text-slate-400 hover:text-slate-200 border-transparent'
            }`}
          >
            EXECUTIVE OVERVIEW
          </button>
          <button
            onClick={() => setActiveTab('PRIORITY')}
            className={`px-3.5 py-2 rounded-t transition border-b-2 font-semibold flex items-center gap-1.5 ${
              activeTab === 'PRIORITY'
                ? 'bg-[#1e293b]/60 text-amber-400 border-amber-400'
                : 'text-slate-400 hover:text-slate-200 border-transparent'
            }`}
          >
            <span>PRIORITY ITEMS</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-red-500/20 text-red-300 font-bold">
              {report?.priority_findings?.length ?? highRiskCount}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('VISUAL_ONLY')}
            className={`px-3.5 py-2 rounded-t transition border-b-2 font-semibold flex items-center gap-1.5 ${
              activeTab === 'VISUAL_ONLY'
                ? 'bg-[#1e293b]/60 text-purple-300 border-purple-400'
                : 'text-slate-400 hover:text-slate-200 border-transparent'
            }`}
          >
            <span>VISUAL-ONLY SPOTLIGHT</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-purple-500/20 text-purple-300 font-bold">
              {visualOnlyCount}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('ALL_FINDINGS')}
            className={`px-3.5 py-2 rounded-t transition border-b-2 font-semibold flex items-center gap-1.5 ${
              activeTab === 'ALL_FINDINGS'
                ? 'bg-[#1e293b]/60 text-amber-400 border-amber-400'
                : 'text-slate-400 hover:text-slate-200 border-transparent'
            }`}
          >
            <span>ALL FINDINGS</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-700 text-slate-300">
              {report?.all_findings?.length ?? entities.length}
            </span>
          </button>
        </div>

        {/* Search Filter */}
        {activeTab !== 'EXECUTIVE' && (
          <div className="relative w-full sm:w-64">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search findings, actions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-[#0e1320] border border-[#1e293b] rounded text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-500/50"
            />
          </div>
        )}
      </div>

      {/* Tab 1: Executive Overview */}
      {activeTab === 'EXECUTIVE' && (
        <div className="space-y-5">
          {/* Executive Narrative */}
          <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg p-5">
            <h3 className="text-xs font-mono font-bold uppercase text-slate-200 mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-amber-400" />
              Operational Clearance Intelligence Narrative
            </h3>
            <p className="text-xs font-sans text-slate-300 leading-relaxed">
              {report?.executive_summary || (
                <>
                  Pre-clearance evaluation completed for &apos;{currentProduction?.title || 'Production'}&apos;. A total of{' '}
                  <strong className="text-slate-100">{entities.length} rights-relevant assets</strong> were detected across
                  screenplay tokens and footage frames, including{' '}
                  <strong className="text-purple-300">{visualOnlyCount} Visual-Only findings</strong> requiring review.
                </>
              )}
            </p>
          </div>

          {/* Distribution Matrices */}
          {report && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              {/* Risk & Verification Distributions */}
              <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg p-4">
                <h4 className="text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-3">
                  Risk &amp; Verification Breakdown
                </h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center py-1 border-b border-[#1e293b]">
                    <span className="text-red-400">HIGH RISK</span>
                    <span className="font-bold text-slate-100">{report.risk_distribution?.HIGH ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-[#1e293b]">
                    <span className="text-amber-400">MEDIUM RISK</span>
                    <span className="font-bold text-slate-100">{report.risk_distribution?.MEDIUM ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-[#1e293b]">
                    <span className="text-emerald-400">LOW RISK</span>
                    <span className="font-bold text-slate-100">{report.risk_distribution?.LOW ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 pt-2">
                    <span className="text-red-400 font-semibold">VERIFICATION CONTRADICTIONS</span>
                    <span className="font-bold text-red-400">{report.verification_distribution?.CONTRADICTED ?? 0}</span>
                  </div>
                </div>
              </div>

              {/* Resolution Action Distributions */}
              <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg p-4">
                <h4 className="text-[11px] font-bold text-slate-300 uppercase tracking-wider mb-3">
                  Actionable Resolution Distribution
                </h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center py-1 border-b border-[#1e293b]">
                    <span className="text-amber-300">LICENSE REQUIRED</span>
                    <span className="font-bold text-slate-100">{report.resolution_distribution?.LICENSE_REQUIRED ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-[#1e293b]">
                    <span className="text-red-400">REMOVE OR REPLACE</span>
                    <span className="font-bold text-slate-100">{report.resolution_distribution?.REMOVE_OR_REPLACE ?? 0}</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-[#1e293b]">
                    <span className="text-blue-300">FAIR USE / PUBLIC DOMAIN</span>
                    <span className="font-bold text-slate-100">
                      {(report.resolution_distribution?.FAIR_USE_ARGUMENT ?? 0) +
                        (report.resolution_distribution?.PUBLIC_DOMAIN ?? 0)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-1 pt-2">
                    <span className="text-slate-400">CLEARED / NO ACTION</span>
                    <span className="font-bold text-emerald-400">{report.resolution_distribution?.CLEARED ?? 0}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Priority Items */}
      {activeTab === 'PRIORITY' && (
        <div className="space-y-4">
          <div className="bg-red-950/20 border border-red-500/30 rounded-lg p-3 text-xs text-red-300 font-mono flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span>
              Priority items include High Risk ratings, Critical/High clearance actions, contradicted research findings, or surprise Visual-Only liabilities.
            </span>
          </div>

          <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-[#121826] text-slate-400 uppercase tracking-wider border-b border-[#1e293b] text-[11px]">
                  <tr>
                    <th className="p-3">Entity</th>
                    <th className="p-3">Classification</th>
                    <th className="p-3">Risk Assessment</th>
                    <th className="p-3">Verification</th>
                    <th className="p-3">Recommended Action</th>
                    <th className="p-3 text-right">Traceability</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e293b]">
                  {priorityFindings.length > 0 ? (
                    priorityFindings.map((f) => (
                      <tr
                        key={f.entity_id}
                        onClick={() => setSelectedFinding(f)}
                        className="hover:bg-slate-800/40 cursor-pointer transition"
                      >
                        <td className="p-3">
                          <div className="font-bold text-slate-100">{f.entity_name}</div>
                          <div className="text-[10px] text-slate-500">{f.entity_id} &bull; {f.entity_type}</div>
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(f.classification, 'cls')}`}>
                            {f.classification}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(f.risk_level, 'risk')}`}>
                            {f.risk_level} ({(f.risk_score || 0).toFixed(2)})
                          </span>
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(f.verification_decision, 'verif')}`}>
                            {f.verification_decision || 'UNVERIFIED'}
                          </span>
                        </td>
                        <td className="p-3">
                          <div className="text-slate-200 font-semibold">{f.resolution_action || 'UNRESOLVED'}</div>
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            Priority: <strong className="text-amber-300">{f.resolution_priority || 'MEDIUM'}</strong> &bull; Owner: {f.resolution_owner || 'Legal'}
                          </div>
                        </td>
                        <td className="p-3 text-right">
                          <button className="text-xs text-amber-400 hover:text-amber-300 font-mono inline-flex items-center gap-1">
                            Inspect <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-slate-500">
                        No priority clearance findings match criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Visual-Only Spotlight */}
      {activeTab === 'VISUAL_ONLY' && (
        <div className="space-y-4">
          <div className="bg-purple-950/20 border border-purple-500/30 rounded-lg p-4 text-xs text-purple-200 font-mono leading-relaxed">
            <strong className="text-purple-300 uppercase tracking-wider block mb-1 flex items-center gap-1.5">
              <Eye className="w-4 h-4 text-purple-400" />
              Optical Exposure Advisory &bull; {visualFindings.length} Items
            </strong>
            These rights-bearing entities were discovered strictly on camera (wardrobe, set decoration, signage, props) with zero screenplay reference. They represent unscripted trademark and copyright liabilities.
          </div>

          <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-[#121826] text-slate-400 uppercase tracking-wider border-b border-[#1e293b] text-[11px]">
                  <tr>
                    <th className="p-3">Visual Entity</th>
                    <th className="p-3">Type &amp; Scene</th>
                    <th className="p-3">Risk Assessment</th>
                    <th className="p-3">Verification</th>
                    <th className="p-3">Recommended Clearance Action</th>
                    <th className="p-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e293b]">
                  {visualFindings.length > 0 ? (
                    visualFindings.map((f) => (
                      <tr
                        key={f.entity_id}
                        onClick={() => setSelectedFinding(f)}
                        className="hover:bg-slate-800/40 cursor-pointer transition"
                      >
                        <td className="p-3">
                          <div className="font-bold text-purple-200">{f.entity_name}</div>
                          <div className="text-[10px] text-slate-500">{f.entity_id}</div>
                        </td>
                        <td className="p-3">
                          <div className="text-slate-300">{f.entity_type}</div>
                          <div className="text-[10px] text-slate-500">
                            Scene {f.scene_number ?? 'N/A'} {f.timestamp_start ? `• ${f.timestamp_start.toFixed(1)}s` : ''}
                          </div>
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(f.risk_level, 'risk')}`}>
                            {f.risk_level} ({(f.risk_score || 0).toFixed(2)})
                          </span>
                        </td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(f.verification_decision, 'verif')}`}>
                            {f.verification_decision || 'UNVERIFIED'}
                          </span>
                        </td>
                        <td className="p-3">
                          <div className="text-slate-200 font-semibold">{f.resolution_action || 'UNRESOLVED'}</div>
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            Priority: <strong className="text-purple-300">{f.resolution_priority || 'HIGH'}</strong>
                          </div>
                        </td>
                        <td className="p-3 text-right">
                          <button className="text-xs text-purple-400 hover:text-purple-300 font-mono inline-flex items-center gap-1">
                            Inspect <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-slate-500">
                        No visual-only entities discovered.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: All Findings Matrix */}
      {activeTab === 'ALL_FINDINGS' && (
        <div className="bg-[#0e1320] border border-[#1e293b] rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[#121826] text-slate-400 uppercase tracking-wider border-b border-[#1e293b] text-[11px]">
                <tr>
                  <th className="p-3">Entity</th>
                  <th className="p-3">Classification</th>
                  <th className="p-3">Risk Assessment</th>
                  <th className="p-3">Verification</th>
                  <th className="p-3">Recommended Action</th>
                  <th className="p-3 text-right">Chain of Title</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e293b]">
                {allFindings.length > 0 ? (
                  allFindings.map((f) => (
                    <tr
                      key={f.entity_id}
                      onClick={() => setSelectedFinding(f)}
                      className="hover:bg-slate-800/40 cursor-pointer transition"
                    >
                      <td className="p-3">
                        <div className="font-bold text-slate-100">{f.entity_name}</div>
                        <div className="text-[10px] text-slate-500">{f.entity_id} &bull; {f.entity_type}</div>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(f.classification, 'cls')}`}>
                          {f.classification}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(f.risk_level, 'risk')}`}>
                          {f.risk_level} ({(f.risk_score || 0).toFixed(2)})
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(f.verification_decision, 'verif')}`}>
                          {f.verification_decision || 'UNVERIFIED'}
                        </span>
                      </td>
                      <td className="p-3">
                        <div className="text-slate-200 font-semibold">{f.resolution_action || 'UNRESOLVED'}</div>
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          Owner: {f.resolution_owner || 'Legal'}
                        </div>
                      </td>
                      <td className="p-3 text-right">
                        <button className="text-xs text-amber-400 hover:text-amber-300 font-mono inline-flex items-center gap-1">
                          Inspect <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-500">
                      No findings found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 7-Stage Traceability Drawer Modal */}
      {selectedFinding && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0e1320] border border-[#1e293b] rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
            {/* Modal Header */}
            <div className="p-5 border-b border-[#1e293b] flex items-start justify-between sticky top-0 bg-[#0e1320] z-10">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${badgeColor(selectedFinding.classification, 'cls')}`}>
                    {selectedFinding.classification}
                  </span>
                  <span className="text-xs font-mono text-slate-400">{selectedFinding.entity_id}</span>
                </div>
                <h2 className="text-xl font-bold font-mono text-slate-100">{selectedFinding.entity_name}</h2>
                <div className="text-xs font-mono text-slate-400 mt-0.5">
                  Type: {selectedFinding.entity_type} &bull; Rights Holder: {selectedFinding.rights_holder || 'Unknown / Under Investigation'}
                </div>
              </div>
              <button
                onClick={() => setSelectedFinding(null)}
                className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body: 7-Stage Pipeline */}
            <div className="p-5 space-y-4 font-mono text-xs">
              <div className="text-[11px] font-bold text-amber-400 uppercase tracking-widest flex items-center gap-1.5">
                <Layers className="w-4 h-4" />
                7-Stage Evidence &amp; Intelligence Traceability Chain
              </div>

              {/* Stage 1: Detection */}
              <div className="p-3.5 rounded-lg bg-[#121826] border border-[#1e293b]">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Stage 1 &bull; Detection &amp; Extraction</div>
                <div className="mt-1 text-slate-200">
                  Detected in Scene {selectedFinding.scene_number ?? 1}
                  {selectedFinding.timestamp_start ? ` at video timestamp ${selectedFinding.timestamp_start.toFixed(1)}s` : ''}.
                  Classification: <strong className="text-amber-300">{selectedFinding.classification}</strong>.
                </div>
              </div>

              {/* Stage 2 & 3: Evidence */}
              <div className="p-3.5 rounded-lg bg-[#121826] border border-[#1e293b]">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Stage 2 &amp; 3 &bull; Multi-Modal Evidence</div>
                <div className="mt-1 text-slate-200">
                  Captured <strong className="text-slate-100">{selectedFinding.evidence_count}</strong> distinct evidence record(s).
                </div>
                {selectedFinding.evidence_snippets?.length > 0 && (
                  <div className="mt-2 space-y-1.5">
                    {selectedFinding.evidence_snippets.map((ev, idx) => (
                      <div key={idx} className="p-2 rounded bg-[#0b0f19] text-[11px] text-slate-300">
                        <span className="text-amber-400 font-semibold">[{ev.evidence_type}]</span>{' '}
                        {ev.text_content || `Confidence: ${ev.confidence?.toFixed(2) || '0.90'}`}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Stage 4: Research */}
              <div className="p-3.5 rounded-lg bg-[#121826] border border-[#1e293b]">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Stage 4 &bull; Research Intelligence</div>
                <div className="mt-1 text-slate-200">
                  Rights Holder:{' '}
                  <strong className="text-slate-100">{selectedFinding.rights_holder || 'Not documented'}</strong>
                </div>
                {selectedFinding.evidence_chain?.stage_4_research?.summary && (
                  <div className="mt-1 text-slate-400 text-[11px]">
                    {selectedFinding.evidence_chain.stage_4_research.summary}
                  </div>
                )}
              </div>

              {/* Stage 5: Risk Assessment */}
              <div className="p-3.5 rounded-lg bg-[#121826] border border-[#1e293b]">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Stage 5 &bull; Risk Assessment</div>
                <div className="mt-1 flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(selectedFinding.risk_level, 'risk')}`}>
                    {selectedFinding.risk_level}
                  </span>
                  <span className="text-slate-300">Risk Score: <strong>{(selectedFinding.risk_score || 0).toFixed(2)}</strong></span>
                </div>
                {selectedFinding.risk_factors?.length > 0 && (
                  <div className="mt-1.5 text-slate-400 text-[11px]">
                    Factors: {selectedFinding.risk_factors.join(', ')}
                  </div>
                )}
              </div>

              {/* Stage 6: Adversarial Verification */}
              <div className="p-3.5 rounded-lg bg-[#121826] border border-[#1e293b]">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Stage 6 &bull; Verification Intelligence</div>
                <div className="mt-1 flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badgeColor(selectedFinding.verification_decision, 'verif')}`}>
                    {selectedFinding.verification_decision || 'UNVERIFIED'}
                  </span>
                  {selectedFinding.verification_confidence && (
                    <span className="text-slate-300">
                      Confidence: {(selectedFinding.verification_confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {selectedFinding.verification_rationale && (
                  <div className="mt-1.5 text-slate-400 text-[11px] leading-relaxed">
                    {selectedFinding.verification_rationale}
                  </div>
                )}
              </div>

              {/* Stage 7: Operational Resolution */}
              <div className="p-3.5 rounded-lg bg-[#121826] border border-amber-500/30">
                <div className="text-[10px] font-bold text-amber-400 uppercase">Stage 7 &bull; Actionable Clearance Plan</div>
                <div className="mt-1 text-slate-100 font-bold text-sm">
                  {selectedFinding.resolution_action || 'UNRESOLVED'}
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-slate-300">
                  <div>
                    <span className="text-slate-500 block">PRIORITY</span>
                    <strong className="text-amber-300">{selectedFinding.resolution_priority || 'MEDIUM'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">OWNER</span>
                    <span>{selectedFinding.resolution_owner || 'Clearance Team'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">EST. TIME</span>
                    <span>{selectedFinding.resolution_time_estimate || '2-3 Business Days'}</span>
                  </div>
                </div>
                {selectedFinding.resolution_details && (
                  <div className="mt-2 text-slate-400 text-[11px]">
                    {selectedFinding.resolution_details}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-[#1e293b] flex justify-end">
              <button
                onClick={() => setSelectedFinding(null)}
                className="px-4 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-mono text-xs font-semibold transition"
              >
                Close Traceability View
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
