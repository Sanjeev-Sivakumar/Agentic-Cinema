import React, { useState } from 'react';
import { Clock, Eye, Sparkles } from 'lucide-react';
import { DetectionTimelineChart } from '../components/charts/DetectionTimelineChart';
import { SignatureInspector } from '../components/live-analysis/SignatureInspector';
import { Entity } from '../types';

interface TimelineProps {
  entities: Entity[];
}

export const Timeline: React.FC<TimelineProps> = ({ entities }) => {
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(entities[0] || null);

  return (
    <div className="space-y-4">
      <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-400" />
            <h2 className="text-sm font-bold font-mono uppercase text-slate-100">
              TELEMETRY &amp; DETECTION TIMELINE
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Synchronized timeline of screenplay events, video keyframes, and risk exposure points.
          </p>
        </div>
      </div>

      <div className="h-64">
        <DetectionTimelineChart
          entities={entities}
          onSelectEntity={(e) => setSelectedEntity(e)}
          selectedEntityId={selectedEntity?.id}
        />
      </div>

      <div className="h-96">
        <SignatureInspector entity={selectedEntity} />
      </div>
    </div>
  );
};
