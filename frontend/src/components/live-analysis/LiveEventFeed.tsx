import React, { useRef, useEffect } from 'react';
import { Terminal, Sparkles, ShieldAlert, CheckCircle, Search, Eye } from 'lucide-react';
import { ProcessingEvent } from '../../types';

interface LiveEventFeedProps {
  events: ProcessingEvent[];
  onSelectEvent?: (event: ProcessingEvent) => void;
}

export const LiveEventFeed: React.FC<LiveEventFeedProps> = ({ events, onSelectEvent }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  const formatTimecode = (sec?: number) => {
    if (sec === undefined) return '--:--.-';
    const mins = Math.floor(sec / 60);
    const remainingSec = (sec % 60).toFixed(1);
    return `${String(mins).padStart(2, '0')}:${String(remainingSec).padStart(4, '0')}`;
  };

  const getEventBadge = (event: ProcessingEvent) => {
    if (event.event_type === 'VISUAL_ONLY_DISCOVERED') {
      return (
        <span className="telemetry-badge badge-visual-only">
          <Eye className="w-3 h-3" /> VISUAL ONLY
        </span>
      );
    }
    if (event.event_type === 'ENTITY_DETECTED') {
      return (
        <span className="telemetry-badge badge-both">
          <Sparkles className="w-3 h-3" /> DETECTED
        </span>
      );
    }
    if (event.event_type === 'RISK_ASSESSMENT_STARTED') {
      return (
        <span className="telemetry-badge badge-script-only">
          <ShieldAlert className="w-3 h-3" /> RISK START
        </span>
      );
    }
    if (event.event_type === 'RISK_SIGNAL_CALCULATED') {
      return (
        <span className="telemetry-badge badge-both">
          <Sparkles className="w-3 h-3" /> SIGNAL
        </span>
      );
    }
    if (event.event_type === 'RISK_CALCULATED') {
      return (
        <span className="telemetry-badge badge-high-risk">
          <ShieldAlert className="w-3 h-3" /> RISK {event.risk_score !== undefined ? Math.round(event.risk_score) : ''}
        </span>
      );
    }
    if (event.event_type === 'RISK_ASSESSMENT_COMPLETED') {
      return (
        <span className="telemetry-badge badge-low-risk">
          <CheckCircle className="w-3 h-3" /> RISK DONE
        </span>
      );
    }
    if (event.event_type === 'RISK_ASSESSMENT_FAILED') {
      return (
        <span className="telemetry-badge badge-high-risk">
          <ShieldAlert className="w-3 h-3 text-red-400" /> RISK FAIL
        </span>
      );
    }
    if (event.event_type === 'RESEARCH_COMPLETED') {
      return (
        <span className="telemetry-badge badge-script-only">
          <Search className="w-3 h-3" /> RESEARCH
        </span>
      );
    }
    if (event.event_type === 'VERIFICATION_STARTED') {
      return (
        <span className="telemetry-badge badge-script-only">
          <ShieldAlert className="w-3 h-3 text-cyan-400" /> VERIFY START
        </span>
      );
    }
    if (event.event_type === 'VERIFICATION_CHECK_COMPLETED') {
      return (
        <span className="telemetry-badge badge-both">
          <CheckCircle className="w-3 h-3 text-emerald-400" /> CHECK DONE
        </span>
      );
    }
    if (event.event_type === 'VERIFICATION_CONTRADICTION_FOUND') {
      return (
        <span className="telemetry-badge badge-high-risk">
          <ShieldAlert className="w-3 h-3 text-rose-400" /> CONTRADICTION
        </span>
      );
    }
    if (event.event_type === 'VERIFICATION_COMPLETED') {
      return (
        <span className="telemetry-badge badge-confirmed">
          <CheckCircle className="w-3 h-3 text-emerald-400" /> VERIFIED {event.verification_decision || ''}
        </span>
      );
    }
    if (event.event_type === 'VERIFICATION_FAILED') {
      return (
        <span className="telemetry-badge badge-high-risk">
          <ShieldAlert className="w-3 h-3 text-rose-400" /> VERIFY FAIL
        </span>
      );
    }
    if (event.event_type === 'RESOLUTION_STARTED') {
      return (
        <span className="telemetry-badge badge-script-only">
          <Sparkles className="w-3 h-3 text-amber-400" /> RESOLUTION START
        </span>
      );
    }
    if (event.event_type === 'RESOLUTION_ACTION_RECOMMENDED') {
      return (
        <span className="telemetry-badge badge-both">
          <CheckCircle className="w-3 h-3 text-amber-400" /> ACTION: {event.resolution_action || 'RECOMMENDED'}
        </span>
      );
    }
    if (event.event_type === 'RESOLUTION_ESCALATED') {
      return (
        <span className="telemetry-badge badge-high-risk">
          <ShieldAlert className="w-3 h-3 text-rose-400" /> ESCALATED
        </span>
      );
    }
    if (event.event_type === 'RESOLUTION_COMPLETED') {
      return (
        <span className="telemetry-badge badge-confirmed">
          <CheckCircle className="w-3 h-3 text-emerald-400" /> RESOLVED
        </span>
      );
    }
    if (event.event_type === 'RESOLUTION_FAILED') {
      return (
        <span className="telemetry-badge badge-high-risk">
          <ShieldAlert className="w-3 h-3 text-rose-400" /> RESOLUTION FAIL
        </span>
      );
    }
    return (
      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
        {event.event_type.replace(/_/g, ' ')}
      </span>
    );
  };

  return (
    <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between pb-3 border-b border-[#1e293b] mb-3">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
            REAL-TIME EVENT STREAM
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="live-pulse-dot" />
          <span className="text-[10px] font-mono text-emerald-400 uppercase">LIVE SSE</span>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-2 pr-1">
        {events.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400 font-mono text-xs">
            <Terminal className="w-8 h-8 mb-2 opacity-30 text-slate-400" />
            <span>Awaiting telemetry stream...</span>
            <span className="text-[10px] text-slate-400 mt-1">
              Trigger an analysis job to begin live event ingestion
            </span>
          </div>
        ) : (
          events.map((evt) => {
            const isVisualOnly = evt.event_type === 'VISUAL_ONLY_DISCOVERED';
            return (
              <div
                key={evt.event_id}
                onClick={() => onSelectEvent && onSelectEvent(evt)}
                className={`p-2.5 rounded border transition-all cursor-pointer ${
                  isVisualOnly
                    ? 'bg-violet-950/20 border-violet-500/40 hover:border-violet-400 shadow-[0_0_10px_rgba(139,92,246,0.1)]'
                    : 'bg-[#121826] border-[#1e293b] hover:border-slate-500'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-amber-400 font-semibold">
                      {formatTimecode(evt.video_timestamp)}
                    </span>
                    {evt.scene_number && (
                      <span className="text-[10px] font-mono text-slate-400">
                        SCENE {String(evt.scene_number).padStart(2, '0')}
                      </span>
                    )}
                  </div>
                  {getEventBadge(evt)}
                </div>

                <p className="text-xs text-slate-300 font-sans leading-relaxed">{evt.message}</p>

                {evt.entity_name && (
                  <div className="mt-2 flex items-center justify-between pt-1.5 border-t border-white/5 text-[11px] font-mono">
                    <span className="text-slate-300 font-medium">{evt.entity_name}</span>
                    {evt.confidence && (
                      <span className="text-emerald-400">
                        CONF: {Math.round(evt.confidence * 100)}%
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
