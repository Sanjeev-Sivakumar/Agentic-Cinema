import React from 'react';
import {
  LayoutDashboard,
  Activity,
  Boxes,
  Image as ImageIcon,
  AlertTriangle,
  CheckCircle2,
  Search,
  Scale,
  Clock,
  FileText,
  Cpu,
} from 'lucide-react';

export type PageId =
  | 'overview'
  | 'orchestration'
  | 'live-analysis'
  | 'entities'
  | 'evidence'
  | 'risk'
  | 'verification'
  | 'research'
  | 'clearance'
  | 'timeline'
  | 'reports';

interface SidebarProps {
  currentPage: PageId;
  onSelectPage: (page: PageId) => void;
  visualOnlyCount: number;
  highRiskCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage,
  onSelectPage,
  visualOnlyCount,
  highRiskCount,
}) => {
  const navItems: { id: PageId; label: string; icon: React.ReactNode; badge?: number; badgeText?: string; badgeColor?: string }[] = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: 'orchestration', label: 'ADK Orchestrator', icon: <Cpu className="w-4 h-4 text-cyan-400" />, badgeText: 'ADK', badgeColor: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' },
    { id: 'live-analysis', label: 'Live Analysis', icon: <Activity className="w-4 h-4 text-cyan-400" /> },
    { id: 'entities', label: 'Entities', icon: <Boxes className="w-4 h-4" />, badge: visualOnlyCount, badgeColor: 'bg-violet-500/20 text-violet-300 border-violet-500/40' },
    { id: 'evidence', label: 'Evidence', icon: <ImageIcon className="w-4 h-4" /> },
    { id: 'risk', label: 'Risk Matrix', icon: <AlertTriangle className="w-4 h-4 text-amber-400" />, badge: highRiskCount, badgeColor: 'bg-red-500/20 text-red-300 border-red-500/40' },
    { id: 'verification', label: 'Verification', icon: <CheckCircle2 className="w-4 h-4 text-emerald-400" /> },
    { id: 'research', label: 'Parallel Research', icon: <Search className="w-4 h-4 text-blue-400" /> },
    { id: 'clearance', label: 'Clearance & Resolution', icon: <Scale className="w-4 h-4 text-amber-400" /> },
    { id: 'timeline', label: 'Telemetry Timeline', icon: <Clock className="w-4 h-4 text-indigo-400" /> },
    { id: 'reports', label: 'Audit Reports', icon: <FileText className="w-4 h-4" /> },
  ];

  return (
    <aside className="w-64 border-r border-[#1e293b] bg-[#090d16] flex flex-col justify-between select-none">
      <div className="py-4">
        <div className="px-5 mb-4 text-[10px] font-mono tracking-widest text-slate-400 uppercase font-semibold">
          PRE-CLEARANCE CONTROL
        </div>

        <nav className="space-y-1 px-3">
          {navItems.map((item) => {
            const isActive = currentPage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectPage(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-[#1b2438] text-amber-400 border-l-2 border-amber-500 pl-2.5 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#121826]'
                }`}
              >
                <div className="flex items-center gap-3">
                  {item.icon}
                  <span>{item.label}</span>
                </div>

                {item.badgeText && (
                  <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${item.badgeColor}`}>
                    {item.badgeText}
                  </span>
                )}
                {item.badge !== undefined && item.badge > 0 && (
                  <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${item.badgeColor}`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-4 border-t border-[#1e293b] bg-[#07090e]">
        <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mb-1">
          <span>PIPELINE ENGINE</span>
          <span className="text-emerald-400">ONLINE</span>
        </div>
        <div className="text-[10px] text-slate-400">Local-First ADK Root Agent</div>
      </div>
    </aside>
  );
};
