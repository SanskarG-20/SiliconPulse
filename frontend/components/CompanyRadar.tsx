import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { fetchRadar } from '../api/siliconpulseApi';

interface RadarItem {
  company: string;
  activity_level: string;
  count: number;
}

interface CompanyRadarProps {
  onCompanyClick?: (company: string) => void;
  watchlist?: string[];
  onToggleWatchlist?: (company: string, e?: React.MouseEvent) => void;
}

export const CompanyRadar: React.FC<CompanyRadarProps> = ({ onCompanyClick, watchlist = [], onToggleWatchlist }) => {
  const [radarData, setRadarData] = useState<RadarItem[]>([]);
  const [viewMode, setViewMode] = useState<'global' | 'watchlist'>('global');

  useEffect(() => {
    const loadRadar = async () => {
      try {
        const data = await fetchRadar();
        setRadarData(data);
      } catch {}
    };
    loadRadar();
    const id = setInterval(loadRadar, 5000);
    return () => clearInterval(id);
  }, []);

  const getTrendIcon = (count: number) => {
    if (count >= 5) return <TrendingUp size={12} />;
    if (count >= 2) return <Minus size={12} />;
    return <TrendingDown size={12} />;
  };

  const getTrendColor = (count: number) => {
    if (count >= 5) return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/15';
    if (count >= 2) return 'text-slate-500 dark:text-[#64748B] bg-[#0E1E32] border-[#1C3553]/40';
    return 'text-[#475569] bg-white dark:bg-[#050B1A] border-[#1C3553]/30';
  };

  const list = viewMode === 'global' ? radarData : radarData.filter((i) => watchlist.includes(i.company));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="display flex items-center gap-1.5 text-[10px] font-semibold tracking-[0.14em] text-slate-500 dark:text-[#64748B]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#22D3EE] shadow-[0_0_8px_rgba(34,211,238,0.6)] animate-pulse" />
          COMPANY RADAR
        </h3>
        <div className="flex rounded-full bg-white dark:bg-[#050B1A] border border-[#1C3553]/50 p-0.5">
          <button onClick={() => setViewMode('global')} className={`px-2.5 py-1 rounded-full mono text-[10px] font-semibold tracking-[0.06em] transition-colors ${viewMode === 'global' ? 'bg-[#0E1E32] text-[#22D3EE] border border-[#1C3553]' : 'text-[#475569] hover:text-slate-600 dark:text-[#94A3B8]'}`}>
            Global
          </button>
          <button onClick={() => setViewMode('watchlist')} className={`px-2.5 py-1 rounded-full mono text-[10px] font-semibold tracking-[0.06em] flex items-center gap-1 transition-colors ${viewMode === 'watchlist' ? 'bg-[#0E1E32] text-[#E8A253] border border-[#1C3553]' : 'text-[#475569] hover:text-slate-600 dark:text-[#94A3B8]'}`}>
            Pinned <span className="px-1 py-0 rounded-full bg-[#1C3553]/50 text-[9px]">{watchlist.length}</span>
          </button>
        </div>
      </div>

      <div className="space-y-1">
        {list.length === 0 ? (
          <div className="rounded-[12px] border border-dashed border-[#1C3553]/40 bg-[#0B1426]/40 py-6 text-center">
            <p className="mono text-[11px] tracking-[0.06em] text-[#475569]">{viewMode === 'watchlist' ? 'No pinned companies' : 'Scanning fab nodes…'}</p>
          </div>
        ) : (
          list.map((item) => (
            <button
              key={item.company}
              onClick={() => onCompanyClick?.(item.company)}
              className="w-full flex items-center justify-between gap-2 rounded-[12px] border border-transparent hover:border-[#1C3553]/40 hover:bg-[#0E1E32]/70 bg-[#0E1E32]/30 px-2.5 py-2 text-left transition-colors group"
            >
              <span className="flex items-center gap-2 min-w-0">
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleWatchlist?.(item.company, e);
                  }}
                  className={`w-6 h-6 rounded-full flex items-center justify-center border transition-colors shrink-0 ${watchlist.includes(item.company) ? 'bg-[#E8A253]/10 border-[#E8A253]/20 text-[#E8A253]' : 'bg-white dark:bg-[#050B1A] border-[#1C3553]/40 text-[#334155] group-hover:text-[#22D3EE] group-hover:border-[#22D3EE]/20'}`}
                  aria-label="toggle watchlist"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill={watchlist.includes(item.company) ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 17v5" />
                    <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
                  </svg>
                </span>
                <span className="text-[13px] font-medium tracking-[-0.01em] text-[#CBD5E1] group-hover:text-slate-900 dark:hover:text-white truncate">{item.company}</span>
              </span>
              <span className="flex items-center gap-1.5 shrink-0">
                <span className={`mono text-[9px] font-bold px-1.5 py-0.5 rounded-full border tracking-[0.06em] ${item.activity_level === 'High' ? 'bg-red-500/10 text-red-400 border-red-500/15' : item.activity_level === 'Moderate' ? 'bg-[#E8A253]/10 text-[#E8A253] border-[#E8A253]/15' : 'bg-[#0E1E32] text-slate-500 dark:text-[#64748B] border-[#1C3553]/40'}`}>
                  {item.activity_level}
                </span>
                <span className={`w-6 h-6 rounded-full border flex items-center justify-center ${getTrendColor(item.count)}`}>{getTrendIcon(item.count)}</span>
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
};
