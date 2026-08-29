import React from 'react';
import { Clock, TrendingUp, Search } from 'lucide-react';
import { UserButton } from '@clerk/clerk-react';

interface InputBarProps {
  query: string;
  onQueryChange: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  lastUpdate: string;
  activeCount: number;
}

export const InputBar: React.FC<InputBarProps> = ({ query, onQueryChange, onSubmit, loading, lastUpdate, activeCount }) => {
  return (
    <div className="p-3 md:p-4 bg-white dark:bg-[#050B1A]/80 backdrop-blur-xl border-t border-[#1C3553]/50">
      <div className="max-w-[760px] mx-auto space-y-2.5">
        <form onSubmit={onSubmit} className="relative group">
          <div className="absolute -inset-[1px] rounded-[16px] bg-gradient-to-r from-[#22D3EE]/0 via-[#22D3EE]/20 to-[#E8A253]/20 opacity-0 group-focus-within:opacity-100 blur-[8px] transition-opacity duration-300 pointer-events-none" />
          <div className="relative flex items-center gap-2 bg-[#0E1E32] border border-[#1C3553] rounded-[16px] px-3 md:px-4 py-2 shadow-[0_8px_24px_rgba(2,8,23,0.4)] focus-within:border-[#22D3EE]/40 focus-within:shadow-[0_0_0_3px_rgba(34,211,238,0.12)] transition-all">
            <Search className="text-[#475569] hidden sm:block shrink-0" size={16} />
            <input
              type="text"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder="Ask about yield, supply, or a company…"
              className="flex-1 min-w-0 py-2.5 bg-transparent outline-none text-[13.5px] text-slate-800 dark:text-[#F1F5F9] placeholder:text-[#475569] placeholder:mono placeholder:text-[12px] placeholder:tracking-[0.02em]"
              disabled={loading}
              aria-label="Query"
            />
            <span className="hidden md:inline-flex items-center mono text-[10px] tracking-[0.08em] text-[#475569] border border-[#1C3553] rounded-full px-2 py-1 bg-white dark:bg-[#050B1A]">ENTER</span>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition-all ${loading || !query.trim() ? 'bg-[#1C3553] text-[#475569]' : 'bg-[#E8A253] text-[#050B1A] hover:bg-[#F0A85E] shadow-[0_0_14px_rgba(232,162,83,0.32)] active:scale-95'}`}
              aria-label="Submit query"
            >
              <Search size={16} />
            </button>
          </div>
        </form>

        <div className="flex items-center justify-between px-1 mono text-[10px] tracking-[0.08em]">
          <span className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 text-slate-500 dark:text-[#64748B]">
              <Clock size={11} /> FRESH <span className="text-[#22D3EE]">{lastUpdate}</span>
            </span>
            <span className="hidden sm:inline-flex items-center gap-1.5 text-slate-500 dark:text-[#64748B]">
              <TrendingUp size={11} className="text-emerald-400" /> ACTIVE <span className="text-emerald-400">{activeCount}</span>
            </span>
          </span>
          <span className="hidden sm:flex items-center gap-2 text-[#475569]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> GEMINI ACTIVE
            <UserButton afterSignOutUrl="/sign-in" />
          </span>
        </div>
      </div>
    </div>
  );
};
