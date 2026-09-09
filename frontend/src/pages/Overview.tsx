import React, { useState, useEffect } from 'react';
import {
  Play,
  Film,
  Plus,
  Shield,
  Eye,
  AlertTriangle,
  CheckCircle,
  FileText,
  Search,
  Sparkles,
  Layers,
  Cpu,
} from 'lucide-react';
import { MetricCard } from '../components/dashboard/MetricCard';
import { RiskDistributionChart } from '../components/charts/RiskDistributionChart';
import { EntitySourceChart } from '../components/charts/EntitySourceChart';
import { Production, Entity, AvailableVideo } from '../types';
import { LiveMetricsData } from '../hooks/useLiveMetrics';
import { api } from '../services/api';

interface OverviewProps {
  currentProduction: Production | null;
  metrics: LiveMetricsData;
  entities: Entity[];
  onStartAnalysis: () => void;
  onCreateSampleProduction: () => void;
  isAnalyzing: boolean;
  selectedVideo?: string;
  availableVideos?: AvailableVideo[];
  onSelectVideo?: (vid: string) => void;
}

export const Overview: React.FC<OverviewProps> = ({
  currentProduction,
  metrics,
  entities,
  onStartAnalysis,
  onCreateSampleProduction,
  isAnalyzing,
  selectedVideo = 'test_video1.mp4',
  availableVideos = [],
  onSelectVideo,
}) => {
  const handleVideoChange = async (vidName: string) => {
    if (onSelectVideo) onSelectVideo(vidName);
    if (currentProduction?.id) {
      try {
        await api.registerFootage(currentProduction.id, vidName);
      } catch (err) {
        console.warn('Could not update footage path on backend:', err);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="bg-gradient-to-r from-[#121826] via-[#161f33] to-[#0f1523] border border-[#1e293b] rounded-lg p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
              COMMAND OVERVIEW
            </span>
            <span className="text-xs font-mono text-slate-400">PRODUCTION TELEMETRY</span>
          </div>
          <h1 className="text-xl font-bold text-slate-100">
            {currentProduction ? currentProduction.title : 'No Production Loaded'}
          </h1>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Real-time agentic pre-clearance intelligence. Compares intended screenplay elements against captured footage to isolate Visual-Only trademark and copyright exposures.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Video Selector */}
          <div className="flex items-center gap-2 bg-[#090d16] border border-[#1e293b] rounded px-3 py-2 text-xs font-mono">
            <Film className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span className="text-slate-400 hidden sm:inline">VIDEO:</span>
            <select
              value={selectedVideo}
              onChange={(e) => handleVideoChange(e.target.value)}
              className="bg-transparent text-amber-300 font-semibold focus:outline-none cursor-pointer"
            >
              {availableVideos.length > 0 ? (
                availableVideos.map((v) => (
                  <option key={v.filename} value={v.filename} className="bg-[#0e1320] text-slate-200">
                    {v.filename} {v.is_recommended ? '(Recommended - Cadbury)' : `(${v.size_mb} MB)`}
                  </option>
                ))
              ) : (
                <>
                  <option value="test_video1.mp4" className="bg-[#0e1320] text-slate-200">test_video1.mp4 (Cadbury Showcase)</option>
                  <option value="test_video.mp4" className="bg-[#0e1320] text-slate-200">test_video.mp4 (Sample Reel)</option>
                </>
              )}
            </select>
          </div>

          {!currentProduction ? (
            <button
              onClick={onCreateSampleProduction}
              className="flex items-center gap-2 px-4 py-2.5 rounded bg-amber-500 hover:bg-amber-400 text-black font-semibold text-xs font-mono transition-all shadow-[0_0_15px_rgba(245,158,11,0.3)]"
            >
              <Plus className="w-4 h-4" />
              LOAD DEMO PRODUCTION
            </button>
          ) : (
            <button
              onClick={onStartAnalysis}
              disabled={isAnalyzing}
              className={`flex items-center gap-2 px-5 py-2.5 rounded font-semibold text-xs font-mono transition-all ${
                isAnalyzing
                  ? 'bg-slate-800 text-slate-400 cursor-not-allowed'
                  : 'bg-amber-500 hover:bg-amber-400 text-black shadow-[0_0_20px_rgba(245,158,11,0.4)]'
              }`}
            >
              <Play className="w-4 h-4" />
              {isAnalyzing ? 'PIPELINE RUNNING...' : 'LAUNCH ANALYSIS JOB'}
            </button>
          )}
        </div>
      </div>

      {/* Active AI Models Configuration Bar */}
      <div className="bg-[#0e1320] border border-cyan-500/20 rounded p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-slate-400 font-mono text-[10px] uppercase tracking-wider mr-1">ACTIVE AI ENGINES:</span>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-mono text-[11px]">
            <Eye className="w-3 h-3 text-cyan-400" />
            <span>VISION: Gemini 3.5 Flash Lite</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono text-[11px]">
            <Search className="w-3 h-3 text-amber-400" />
            <span>RESEARCH: Parallel Search API (Trademarks &amp; USPTO)</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 font-mono text-[11px]">
            <FileText className="w-3 h-3 text-indigo-400" />
            <span>SCREENPLAY: Gemini Flash</span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 font-mono text-[10px] text-slate-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-emerald-400 font-semibold">LIVE CONNECTIVITY ACTIVE</span>
        </div>
      </div>


      {/* Visual-Only Highlight Banner */}
      <div className="bg-violet-950/20 border border-violet-500/30 rounded p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded bg-violet-500/20 text-violet-400 border border-violet-500/40">
            <Eye className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-violet-300">
                CORE DIFFERENTIATOR: VISUAL-ONLY FINDINGS
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-violet-500/30 text-violet-200">
                {metrics.visualOnlyCount} ISOLATED
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Entities detected by camera vision but absent from the screenplay script. Evaluated with high-priority risk assessment.
            </p>
          </div>
        </div>
      </div>

      {/* 10 Real-Time Telemetry Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard
          title="Total Entities"
          value={metrics.totalEntities}
          subtitle="Identified clearance items"
          icon={<Layers className="w-4 h-4" />}
          colorScheme="slate"
        />
        <MetricCard
          title="High Risk"
          value={metrics.highRiskCount}
          subtitle="Action required"
          icon={<AlertTriangle className="w-4 h-4 text-red-400" />}
          colorScheme="crimson"
          badge="CRITICAL"
        />
        <MetricCard
          title="Medium Risk"
          value={metrics.mediumRiskCount}
          subtitle="Licensing recommended"
          icon={<AlertTriangle className="w-4 h-4 text-amber-400" />}
          colorScheme="amber"
        />
        <MetricCard
          title="Low Risk"
          value={metrics.lowRiskCount}
          subtitle="Incidental / Fair Use"
          icon={<CheckCircle className="w-4 h-4 text-emerald-400" />}
          colorScheme="emerald"
        />
        <MetricCard
          title="Unknown"
          value={metrics.unknownRiskCount}
          subtitle="Pending evaluation"
          icon={<Shield className="w-4 h-4 text-slate-400" />}
          colorScheme="slate"
        />
        <MetricCard
          title="Visual-Only"
          value={metrics.visualOnlyCount}
          subtitle="Footage only marks"
          icon={<Eye className="w-4 h-4 text-violet-400" />}
          colorScheme="violet"
          badge="PRIORITY"
        />
        <MetricCard
          title="Script-Only"
          value={metrics.scriptOnlyCount}
          subtitle="Narrative mentions"
          icon={<FileText className="w-4 h-4 text-cyan-400" />}
          colorScheme="cyan"
        />
        <MetricCard
          title="Research Done"
          value={metrics.researchCompletedCount}
          subtitle="Parallel intelligence queries"
          icon={<Search className="w-4 h-4 text-blue-400" />}
          colorScheme="slate"
        />
        <MetricCard
          title="Verified Rights"
          value={metrics.verificationConfirmedCount}
          subtitle="Confirmed title chain"
          icon={<CheckCircle className="w-4 h-4 text-emerald-400" />}
          colorScheme="emerald"
        />
        <MetricCard
          title="Review Required"
          value={metrics.humanReviewCount}
          subtitle="Flagged for legal counsel"
          icon={<Sparkles className="w-4 h-4 text-amber-400" />}
          colorScheme="amber"
        />
      </div>

      {/* Overview Analytics Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <RiskDistributionChart
          highRisk={metrics.highRiskCount}
          medRisk={metrics.mediumRiskCount}
          lowRisk={metrics.lowRiskCount}
          unknownRisk={metrics.unknownRiskCount}
        />
        <EntitySourceChart
          visualOnly={metrics.visualOnlyCount}
          scriptOnly={metrics.scriptOnlyCount}
          both={metrics.bothCount}
          audioOnly={metrics.audioOnlyCount}
        />
      </div>
    </div>
  );
};
