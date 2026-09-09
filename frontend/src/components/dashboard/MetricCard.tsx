import React from 'react';

interface MetricCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: string;
  colorScheme?: 'amber' | 'violet' | 'cyan' | 'emerald' | 'crimson' | 'slate';
  badge?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  colorScheme = 'slate',
  badge,
}) => {
  const colorMap = {
    amber: 'border-amber-500/30 bg-amber-500/5 text-amber-400',
    violet: 'border-violet-500/30 bg-violet-500/5 text-violet-400',
    cyan: 'border-cyan-500/30 bg-cyan-500/5 text-cyan-400',
    emerald: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-400',
    crimson: 'border-red-500/30 bg-red-500/5 text-red-400',
    slate: 'border-[#1e293b] bg-[#121826] text-slate-300',
  };

  return (
    <div className={`p-4 rounded border transition-all hover:border-slate-600 ${colorMap[colorScheme]}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400">{title}</span>
        {icon && <div className="text-slate-400">{icon}</div>}
      </div>

      <div className="flex items-baseline justify-between">
        <span className="text-2xl font-bold font-mono text-slate-100">{value}</span>
        {badge && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-slate-300">
            {badge}
          </span>
        )}
      </div>

      {subtitle && <p className="text-[11px] text-slate-400 mt-1">{subtitle}</p>}
    </div>
  );
};
