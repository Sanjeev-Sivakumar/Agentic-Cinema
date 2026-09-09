import React from 'react';
import { Entity } from '../../types';

interface DetectionTimelineChartProps {
  entities: Entity[];
  onSelectEntity?: (entity: Entity) => void;
  selectedEntityId?: string;
  videoDuration?: number;
}

export const DetectionTimelineChart: React.FC<DetectionTimelineChartProps> = ({
  entities,
  onSelectEntity,
  selectedEntityId,
  videoDuration = 30,
}) => {
  const maxDetectedTime = Math.max(0, ...entities.map((e) => e.timestamp || 0));
  const maxDuration = Math.max(videoDuration, Math.max(30, Math.ceil((maxDetectedTime + 5) / 10) * 10));

  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col h-full">
      <div className="flex items-center justify-between pb-2 border-b border-[#1e293b] mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
            DETECTION TIMELINE (X: TIMESTAMP • Y: CONFIDENCE)
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/30">
            LIVE GRAPH
          </span>
        </div>
        <div className="flex items-center gap-4 text-[10px] font-mono">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-violet-400" /> VISUAL-ONLY
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-cyan-400" /> SCRIPT-MATCH
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-400" /> HIGH RISK RING
          </span>
        </div>
      </div>

      {/* SVG Interactive Scatter/Line Chart */}
      <div className="flex-1 w-full min-h-[140px] relative flex flex-col justify-end">
        <svg className="w-full h-full" viewBox="0 0 600 140" preserveAspectRatio="none">
          {/* Y-axis grid lines with confidence percentages */}
          <line x1="30" y1="20" x2="590" y2="20" stroke="#1e293b" strokeDasharray="3 3" />
          <text x="5" y="23" fill="#64748b" fontSize="7" fontFamily="JetBrains Mono">100%</text>

          <line x1="30" y1="55" x2="590" y2="55" stroke="#1e293b" strokeDasharray="3 3" />
          <text x="10" y="58" fill="#64748b" fontSize="7" fontFamily="JetBrains Mono">75%</text>

          <line x1="30" y1="90" x2="590" y2="90" stroke="#1e293b" strokeDasharray="3 3" />
          <text x="10" y="93" fill="#64748b" fontSize="7" fontFamily="JetBrains Mono">50%</text>

          <line x1="30" y1="125" x2="590" y2="125" stroke="#334155" />
          <text x="15" y="128" fill="#64748b" fontSize="7" fontFamily="JetBrains Mono">0%</text>

          {/* Time ticks */}
          {[0, 0.25, 0.5, 0.75, 1.0].map((frac) => {
            const t = Math.round(frac * maxDuration);
            const x = 30 + frac * 550;
            return (
              <g key={frac}>
                <line x1={x} y1="120" x2={x} y2="125" stroke="#475569" />
                <text x={x} y="136" fill="#64748b" fontSize="8" fontFamily="JetBrains Mono" textAnchor="middle">
                  {t}s
                </text>
              </g>
            );
          })}

          {/* Plotted detection points */}
          {entities.map((entity, i) => {
            const time = entity.timestamp ?? (i * (maxDuration / Math.max(1, entities.length)));
            const x = Math.min(580, Math.max(30, 30 + (time / maxDuration) * 550));
            // Y-axis: Confidence 0.0 -> 125, 1.0 -> 25
            const conf = Math.max(0.0, Math.min(1.0, entity.confidence ?? 0.85));
            const y = 125 - conf * 100;

            const isSelected = selectedEntityId === entity.id;
            const isVisualOnly = entity.classification === 'VISUAL_ONLY' || entity.sources.includes('VISUAL') && !entity.sources.includes('SCRIPT');

            const pointColor = isVisualOnly ? '#a855f7' : '#06b6d4';
            const ringColor = entity.risk_score >= 70 ? '#ef4444' : pointColor;

            return (
              <g
                key={entity.id}
                className="cursor-pointer transition-transform hover:scale-125"
                onClick={() => onSelectEntity && onSelectEntity(entity)}
              >
                {/* Connecting drop line */}
                <line x1={x} y1={y} x2={x} y2="130" stroke={pointColor} strokeOpacity="0.3" strokeDasharray="2 2" />

                {/* Outer Glow Ring if selected */}
                {isSelected && (
                  <circle cx={x} cy={y} r="9" fill="none" stroke="#f59e0b" strokeWidth="2" className="animate-ping" />
                )}

                {/* Outer Ring */}
                <circle cx={x} cy={y} r={isSelected ? 7 : 5} fill="#0d121c" stroke={ringColor} strokeWidth="2" />

                {/* Inner Core */}
                <circle cx={x} cy={y} r={isSelected ? 4 : 3} fill={pointColor} />

                {/* Tooltip Label */}
                <text
                  x={x}
                  y={y - 8}
                  fill="#f8fafc"
                  fontSize="8"
                  fontFamily="JetBrains Mono"
                  textAnchor="middle"
                  className="pointer-events-none font-semibold"
                >
                  {entity.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
