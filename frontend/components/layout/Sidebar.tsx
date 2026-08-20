import React from 'react';
import { Zap, ShieldAlert } from 'lucide-react';
import { CompanyRadar } from '../CompanyRadar';
import { GraphPanel } from '../GraphPanel';
import { getRelativeTimeLabel } from '../../utils/feedUtils';
import { LiveEvent } from '../../types';

interface SidebarProps {
  feed: LiveEvent[];
  watchlist: string[];
  onCompanyClick: (company: string) => void;
  onToggleWatchlist: (company: string, e?: React.MouseEvent) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  feed,
  watchlist,
  onCompanyClick,
  onToggleWatchlist,
}) => {
  const filteredFeed = feed;
  const graphCompany = feed.find(f => f.company && f.company !== 'Unknown')?.company || feed[0]?.company;

  return (
    <aside className="w-80 border-r border-slate-800/40 bg-slate-950/20 p-6 space-y-8 hidden lg:block overflow-y-auto custom-scrollbar">
      <CompanyRadar 
        onCompanyClick={onCompanyClick} 
        watchlist={watchlist} 
        onToggleWatchlist={onToggleWatchlist} 
      />

      <div className="space-y-4">
        <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] flex items-center">
          <Zap size={14} className="mr-2 text-amber-500" />
          High Priority Signals
        </h3>
        <div className="space-y-3">
          {filteredFeed.filter(f => f.impactScore > 80).slice(0, 3).map(ev => (
            <div key={ev.id} className="glass p-3 rounded-xl border-slate-800/50 hover:border-sky-500/30 transition-all cursor-pointer group">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[9px] font-mono text-sky-500">{getRelativeTimeLabel(ev.timestamp)}</span>
                <span className="px-1.5 py-0.5 rounded-[4px] bg-red-500/10 text-red-500 text-[8px] font-black uppercase tracking-tighter border border-red-500/20">Critical</span>
              </div>
              <h4 title={ev.title} className="text-xs font-bold text-slate-100 group-hover:text-sky-400 leading-tight transition-colors mb-1 truncate">{ev.title}</h4>
              <div className="flex items-center text-[9px] text-slate-500 font-bold uppercase tracking-widest">
                <span>{ev.company}</span>
                <span className="mx-1.5 opacity-20">|</span>
                <span>{ev.impactScore} IMPACT</span>
                <button 
                  onClick={(e) => { e.stopPropagation(); onToggleWatchlist(ev.company); }}
                  className={`ml-auto ${watchlist.includes(ev.company) ? 'text-sky-400' : 'text-slate-600 hover:text-sky-400'}`}
                  title={watchlist.includes(ev.company) ? "Remove from Watchlist" : "Add to Watchlist"}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill={watchlist.includes(ev.company) ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="p-5 rounded-2xl bg-sky-500/5 border border-sky-500/10">
        <div className="flex items-center space-x-2 mb-3">
          <div className="p-1.5 bg-sky-500/20 rounded-lg">
            <ShieldAlert size={14} className="text-sky-500" />
          </div>
          <span className="text-[10px] font-black text-sky-500 uppercase tracking-widest">Analyst Advisory</span>
        </div>
        <p className="text-[11px] text-slate-400 font-medium italic leading-relaxed">
          "Focus on TSMC N2 yield milestones. Early reports suggest Apple/NVIDIA bidding war for initial capacity. Cross-ref with GlobalFoundries delays."
        </p>
      </div>

      <GraphPanel company={graphCompany} />
    </aside>
  );
};