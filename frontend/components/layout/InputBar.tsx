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

export const InputBar: React.FC<InputBarProps> = ({
  query,
  onQueryChange,
  onSubmit,
  loading,
  lastUpdate,
  activeCount,
}) => {
  return (
    <div className="p-4 md:p-8 bg-slate-950/60 backdrop-blur-2xl border-t border-slate-800/60 relative z-40">
      <div className="max-w-4xl mx-auto space-y-3 md:space-y-4">
        <form onSubmit={onSubmit} className="relative group">
          <div className="absolute inset-0 -m-[1px] bg-gradient-to-r from-sky-500/40 via-indigo-500/40 to-sky-500/40 rounded-2xl opacity-0 group-focus-within:opacity-100 blur-[6px] transition-all duration-500"></div>
          <div className="relative flex items-center bg-slate-900 border border-slate-700/60 rounded-2xl overflow-hidden px-4 md:px-5 focus-within:border-sky-500/50 shadow-2xl transition-all">
            <Search className="text-slate-500 mr-3 md:mr-4 hidden sm:block" size={20} />
            <input
              type="text"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder="ENTER COMMAND OR QUERY..."
              className="flex-1 py-4 md:py-5 bg-transparent outline-none text-slate-100 placeholder-slate-600 font-mono text-xs md:text-sm tracking-tight"
              disabled={loading}
            />
            <div className="flex items-center space-x-2 md:space-x-4">
              <div className="hidden md:flex items-center space-x-2 px-2 py-1 bg-slate-800/50 rounded-md border border-slate-700/50">
                <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">ENTER</span>
              </div>
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className={`p-2.5 md:p-3 rounded-xl transition-all ${loading || !query.trim()
                  ? 'text-slate-600 bg-slate-800/50'
                  : 'text-white bg-sky-600 hover:bg-sky-500 shadow-[0_0_20px_rgba(14,165,233,0.4)] active:scale-95'
                  }`}
              >
                <Search size={20} />
              </button>
            </div>
          </div>
        </form>

        <div className="flex items-center justify-between px-2">
          <div className="flex items-center space-x-4 md:space-x-6">
            <div className="flex items-center space-x-1.5 md:space-x-2">
              <Clock size={10} className="text-slate-500" />
              <span className="text-[8px] md:text-[10px] font-black text-slate-500 uppercase tracking-widest">Freshness: <span className="text-sky-500">{lastUpdate}</span></span>
            </div>
            <div className="flex items-center space-x-1.5 md:space-x-2">
              <TrendingUp size={10} className="text-emerald-500" />
              <span className="text-[8px] md:text-[10px] font-black text-slate-500 uppercase tracking-widest">Active: <span className="text-emerald-500">{activeCount}</span></span>
            </div>
          </div>
          <div className="hidden sm:flex items-center space-x-4 text-[10px] font-black text-slate-600 uppercase tracking-widest">
            <span className="text-sky-500/60 font-mono">GEMINI_ACTIVE</span>
            <UserButton afterSignOutUrl="/sign-in" />
          </div>
        </div>
      </div>
    </div>
  );
};