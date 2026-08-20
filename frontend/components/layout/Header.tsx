import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Search, Home, RefreshCw, Coffee, Moon, Sun, Menu, Zap, Activity, X 
} from 'lucide-react';

interface HeaderProps {
  feedFilter: string;
  onFeedFilterChange: (v: string) => void;
  onReset: () => void;
  onGenerateDigest: () => void;
  onToggleTheme: () => void;
  onOpenInject: () => void;
  onOpenMobileMenu: () => void;
  isLightMode: boolean;
  showMobileMenu: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  feedFilter,
  onFeedFilterChange,
  onReset,
  onGenerateDigest,
  onToggleTheme,
  onOpenInject,
  onOpenMobileMenu,
  isLightMode,
  showMobileMenu,
}) => {
  return (
    <header className="h-14 border-b border-slate-800/60 flex items-center justify-between px-4 md:px-6 bg-slate-950/40 backdrop-blur-xl z-50">
      <div className="flex items-center space-x-3 md:space-x-4">
        <button
          onClick={onOpenMobileMenu}
          className="lg:hidden p-2 -ml-2 text-slate-400 hover:text-white transition-colors"
        >
          <Menu size={20} />
        </button>
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 bg-sky-600 rounded flex items-center justify-center shadow-[0_0_15px_rgba(2,132,199,0.3)]">
            <Activity size={18} className="text-white" />
          </div>
          <div className="leading-tight">
            <h1 className="text-sm font-black tracking-tighter uppercase text-white flex items-center">
              Silicon<span className="text-sky-500">Pulse</span>
              <span className="ml-2 px-1 py-0.5 bg-sky-500/10 text-sky-500 border border-sky-500/20 rounded-[4px] text-[8px] tracking-[0.1em] hidden sm:inline-block">OS_v4</span>
            </h1>
          </div>
        </div>
        <div className="h-4 w-[1px] bg-slate-800 hidden md:block"></div>
        <div className="hidden md:flex items-center space-x-4">
          <div className="flex items-center space-x-1.5 group cursor-help">
            <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></div>
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest group-hover:text-emerald-400 transition-colors">Nodes_Online</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <Activity size={12} className="text-sky-500" />
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Latency: 12ms</span>
          </div>
        </div>
      </div>

      <div className="flex items-center space-x-2 md:space-x-3">
        <div className="relative hidden lg:block mr-2">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Filter live feed..."
            value={feedFilter}
            onChange={(e) => onFeedFilterChange(e.target.value)}
            className="pl-7 pr-6 py-1.5 bg-slate-900 border border-slate-800 rounded-md text-[10px] text-slate-300 focus:outline-none focus:border-sky-500/50 w-32 focus:w-48 transition-all"
          />
          {feedFilter && (
            <button onClick={() => onFeedFilterChange('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
              <X size={10} />
            </button>
          )}
        </div>
        <Link
          to="/"
          className="flex items-center space-x-2 px-2 md:px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-slate-300 border border-slate-800 transition-all active:scale-95"
        >
          <Home size={12} />
          <span className="hidden sm:inline">Home</span>
        </Link>
        <button
          onClick={onReset}
          className="flex items-center space-x-2 px-2 md:px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-slate-300 border border-slate-800 transition-all active:scale-95"
        >
          <RefreshCw size={12} />
          <span className="hidden sm:inline">Reset</span>
        </button>
        <button
          onClick={onGenerateDigest}
          className="flex items-center space-x-2 px-2 md:px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-emerald-400 border border-emerald-500/20 transition-all active:scale-95"
        >
          <Coffee size={12} />
          <span className="hidden sm:inline">Digest</span>
        </button>
        <button
          onClick={onToggleTheme}
          className="flex items-center space-x-2 px-2 md:px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-slate-400 border border-slate-800 transition-all active:scale-95"
          title="Toggle Theme"
        >
          {isLightMode ? <Moon size={12} /> : <Sun size={12} />}
        </button>
        <button
          onClick={onOpenInject}
          className="flex items-center space-x-2 px-2 md:px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-sky-400 border border-slate-800 transition-all active:scale-95"
        >
          <Zap size={12} />
          <span className="hidden sm:inline">Inject_Signal</span>
          <span className="sm:hidden">Inject</span>
        </button>
      </div>
    </header>
  );
};