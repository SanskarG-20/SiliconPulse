import React from 'react';
import { Link } from 'react-router-dom';
import { Search, Home, RefreshCw, Coffee, Moon, Sun, Menu, Activity, X, Upload, Zap } from 'lucide-react';

interface HeaderProps {
  feedFilter: string;
  onFeedFilterChange: (v: string) => void;
  onReset: () => void;
  onGenerateDigest: () => void;
  onToggleTheme: () => void;
  onOpenInject: () => void;
  onOpenPdf: () => void;
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
  onOpenPdf,
  onOpenMobileMenu,
}) => {
  return (
    <header className="h-[56px] shrink-0 border-b border-[#1C3553]/60 flex items-center justify-between px-4 md:px-5 bg-[#0E1E32]/70 backdrop-blur-xl z-50">
      {/* Left: brand + status */}
      <div className="flex items-center gap-3 md:gap-5">
        <button
          onClick={onOpenMobileMenu}
          className="lg:hidden -ml-1 p-2 text-[#94A3B8] hover:text-white transition-colors"
          aria-label="Open menu"
        >
          <Menu size={18} />
        </button>

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-[8px] bg-[#0E1E32] border border-[#1C3553] flex items-center justify-center shadow-[0_0_0_1px_rgba(34,211,238,0.08)]">
            <div className="w-[18px] h-[18px] rounded-[4px] bg-[#22D3EE] flex items-center justify-center">
              <Activity size={11} className="text-[#050B1A]" strokeWidth={2.5} />
            </div>
          </div>
          <div className="leading-none">
            <h1 className="display text-[13px] font-bold tracking-[-0.02em] text-white flex items-center gap-1.5">
              SILICON<span className="text-[#22D3EE]">PULSE</span>
              <span className="hidden sm:inline-flex ml-1 px-1.5 py-0.5 rounded-[5px] bg-[#E8A253]/10 text-[#E8A253] border border-[#E8A253]/20 text-[8px] tracking-[0.12em] font-semibold leading-none">
                OS v4
              </span>
            </h1>
            <p className="hidden sm:block mono text-[9px] tracking-[0.14em] text-[#64748B] font-medium mt-0.5">FAB • SUPPLY • INTELLIGENCE</p>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-4 pl-4 ml-1 border-l border-[#1C3553]/60">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)] animate-pulse" />
            <span className="mono text-[10px] tracking-[0.12em] font-semibold text-[#94A3B8]">NODES ONLINE</span>
          </span>
          <span className="mono text-[10px] tracking-[0.08em] text-[#475569] hidden xl:inline">LAT 12ms • RETICLE OK</span>
        </div>
      </div>

      {/* Right: filter + actions */}
      <div className="flex items-center gap-1.5 md:gap-2">
        <div className="relative hidden lg:block mr-1">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#475569]" />
          <input
            type="text"
            placeholder="Filter live feed…"
            value={feedFilter}
            onChange={(e) => onFeedFilterChange(e.target.value)}
            className="pl-7 pr-7 py-1.5 bg-[#050B1A] border border-[#1C3553]/70 rounded-full text-[12px] text-[#E2E8F0] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE]/40 focus:bg-[#0E1E32] w-[160px] focus:w-[200px] transition-all mono"
          />
          {feedFilter && (
            <button onClick={() => onFeedFilterChange('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-[#475569] hover:text-white p-0.5" aria-label="Clear filter">
              <X size={12} />
            </button>
          )}
        </div>

        <div className="hidden md:flex items-center gap-1.5">
          <Link to="/" className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-[#0E1E32] border border-[#1C3553]/60 text-[11px] font-semibold tracking-[0.04em] text-[#94A3B8] hover:text-white hover:border-[#22D3EE]/30 hover:bg-[#122742] transition-all">
            <Home size={13} /> Home
          </Link>
          <button onClick={onReset} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-[#0E1E32] border border-[#1C3553]/60 text-[11px] font-semibold tracking-[0.04em] text-[#94A3B8] hover:text-white hover:bg-[#122742] transition-colors">
            <RefreshCw size={13} /> Reset
          </button>
          <button onClick={onGenerateDigest} className="hidden xl:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-[#22D3EE]/10 border border-[#22D3EE]/20 text-[11px] font-semibold tracking-[0.04em] text-[#22D3EE] hover:bg-[#22D3EE]/15 hover:border-[#22D3EE]/30 transition-colors">
            <Coffee size={13} /> Digest
          </button>
        </div>

        <div className="flex items-center gap-1.5 pl-1.5 ml-0.5 border-l border-[#1C3553]/40">
          <button onClick={onToggleTheme} className="p-1.5 rounded-full bg-[#0E1E32] border border-[#1C3553]/60 text-[#64748B] hover:text-white transition-colors" aria-label="Toggle theme">
            <Sun size={14} className="hidden dark:block" />
            <Moon size={14} className="block dark:hidden" />
          </button>
          <button onClick={onOpenPdf} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#E8A253]/25 bg-[#E8A253]/10 text-[11px] font-semibold tracking-[0.04em] text-[#E8A253] hover:bg-[#E8A253]/15 hover:border-[#E8A253]/35 transition-colors">
            <Upload size={13} /> <span className="hidden sm:inline">PDF</span>
          </button>
          <button onClick={onOpenInject} className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#E8A253] text-[#050B1A] text-[11px] font-bold tracking-[0.04em] hover:bg-[#F0A85E] shadow-[0_0_14px_rgba(232,162,83,0.28)] active:scale-[0.98] transition-all">
            <Zap size={13} strokeWidth={2.5} /> <span className="hidden sm:inline">Inject</span>
          </button>
        </div>
      </div>
    </header>
  );
};
