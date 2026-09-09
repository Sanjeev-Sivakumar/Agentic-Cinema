import React from 'react';
import { Search, Globe, Building2, Shield, ExternalLink, Bookmark } from 'lucide-react';
import { Entity } from '../types';

interface ResearchProps {
  entities: Entity[];
}

export const Research: React.FC<ResearchProps> = ({ entities }) => {
  return (
    <div className="space-y-4">
      <div className="bg-[#0e1320] border border-[#1e293b] rounded p-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-bold font-mono uppercase text-slate-100">
              PARALLEL WEB &amp; CORPORATE INTELLIGENCE
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Automated deep research dossiers, parent companies, trademark filings, and licensing contacts.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {entities.map((ent) => (
          <div key={ent.id} className="bg-[#0e1320] border border-[#1e293b] rounded p-4 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#1e293b]">
              <div>
                <span className="font-bold text-sm text-slate-200">{ent.name}</span>
                <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                  QUERY: "{ent.name}" corporate rights holder
                </div>
              </div>
              <span className="telemetry-badge badge-script-only">
                <Globe className="w-3 h-3" /> PARALLEL
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex items-start gap-2">
                <Building2 className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <div className="text-slate-400 text-[10px] uppercase font-mono">Registered Owner / Parent</div>
                  <div className="text-slate-200 font-semibold">{ent.rights_holder || 'Global Enterprises LLC'}</div>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <Bookmark className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <div className="text-slate-400 text-[10px] uppercase font-mono">Registry Class</div>
                  <div className="text-slate-300 font-mono text-[11px]">
                    IC 030 - Coffee, tea, cocoa, beverages &amp; restaurant services
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-[#1e293b] flex items-center justify-between text-[11px] font-mono text-slate-400">
              <span>CONFIDENCE: 95%</span>
              <span className="text-blue-400 flex items-center gap-1 cursor-pointer hover:underline">
                USPTO File Record <ExternalLink className="w-3 h-3" />
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
