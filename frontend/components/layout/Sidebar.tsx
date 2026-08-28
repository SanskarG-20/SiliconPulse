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

export const Sidebar: React.FC<SidebarProps> = ({ feed, watchlist, onCompanyClick, onToggleWatchlist }) => {
  const filteredFeed = feed;
  const graphCompany = feed.find((f) => f.company && f.company !== 'Unknown')?.company || feed[0]?.company;

  return (
    <aside className="w-[300px] shrink-0 border-r border-[#1C3553]/40 bg-[#0B1426]/50 backdrop-blur-[6px] p-4 space-y-5 hidden lg:flex lg:flex-col overflow-y-auto custom-scrollbar">
      <CompanyRadar onCompanyClick={onCompanyClick} watchlist={watchlist} onToggleWatchlist={onToggleWatchlist} />

      <div className="space-y-3">
        <h3 className="display text-[10px] font-semibold tracking-[0.14em] text-[#64748B] flex items-center gap-1.5">
          <Zap size={12} className="text-[#E8A253]" />
          HIGH PRIORITY
        </h3>
        <div className="space-y-2.5">
          {filteredFeed
            .filter((f) => f.impactScore > 80)
            .slice(0, 3)
            .map((ev) => (
              <button
                key={ev.id}
                onClick={() => onCompanyClick(ev.company)}
                className="w-full text-left glass rounded-[14px] p-3 border-[#1C3553]/40 hover:border-[#22D3EE]/25 hover:bg-[#0E1E32]/80 transition-all group"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="mono text-[10px] tracking-[0.06em] text-[#22D3EE]">{getRelativeTimeLabel(ev.timestamp)}</span>
                  <span className="px-1.5 py-0.5 rounded-[6px] bg-red-500/10 text-red-400 text-[9px] font-bold tracking-[0.08em] border border-red-500/15">CRITICAL</span>
                </div>
                <h4 title={ev.title} className="text-[12.5px] font-semibold leading-snug text-[#E2E8F0] group-hover:text-white line-clamp-2">
                  {ev.title}
                </h4>
                <div className="mt-1.5 flex items-center gap-1.5 mono text-[10px] tracking-[0.06em] text-[#64748B]">
                  <span className="text-[#94A3B8] font-medium">{ev.company}</span>
                  <span className="opacity-30">•</span>
                  <span>{ev.impactScore} IMPACT</span>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleWatchlist(ev.company);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.stopPropagation();
                        onToggleWatchlist(ev.company);
                      }
                    }}
                    className={`ml-auto p-1 rounded-full transition-colors ${watchlist.includes(ev.company) ? 'text-[#E8A253] bg-[#E8A253]/10' : 'text-[#334155] hover:text-[#E8A253] hover:bg-[#E8A253]/10'}`}
                    aria-label={watchlist.includes(ev.company) ? 'Remove from watchlist' : 'Add to watchlist'}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill={watchlist.includes(ev.company) ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 17v5" />
                      <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
                    </svg>
                  </span>
                </div>
              </button>
            ))}
        </div>
      </div>

      <div className="rounded-[14px] bg-[#0E1E32] border border-[#1C3553]/50 p-4">
        <div className="flex items-center gap-2 mb-2.5">
          <span className="w-6 h-6 rounded-[8px] bg-[#22D3EE]/10 border border-[#22D3EE]/15 flex items-center justify-center">
            <ShieldAlert size={13} className="text-[#22D3EE]" />
          </span>
          <span className="display text-[10px] font-semibold tracking-[0.12em] text-[#22D3EE]">ANALYST ADVISORY</span>
        </div>
        <p className="serif text-[12.5px] leading-relaxed text-[#94A3B8] italic">
          “Focus on TSMC N2 yield milestones. Early reports suggest Apple/NVIDIA bidding war for initial capacity. Cross-ref with GlobalFoundries delays.”
        </p>
      </div>

      <GraphPanel company={graphCompany} />
    </aside>
  );
};
