
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
      } catch (err) {
        console.error("Failed to load radar data:", err);
      }
    };

    loadRadar();
    const interval = setInterval(loadRadar, 5000); // Poll every 5s

    return () => clearInterval(interval);
  }, []);

  const getTrendIcon = (count: number) => {
    // Simple trend logic for now based on count
    if (count >= 5) return <TrendingUp size={12} />;
    if (count >= 2) return <Minus size={12} />;
    return <TrendingDown size={12} />;
  };

  const getTrendColor = (count: number) => {
    if (count >= 5) return 'text-emerald-400 bg-emerald-400/10';
    if (count >= 2) return 'text-slate-500 bg-slate-800';
    return 'text-red-400 bg-red-400/10';
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] flex items-center">
          <span className="w-1.5 h-1.5 bg-sky-500 rounded-full mr-2 shadow-[0_0_8px_#0ea5e9] animate-pulse"></span>
          Company Radar
        </h3>
        
        <div className="flex bg-slate-900 rounded-md p-0.5 border border-slate-800">
          <button 
            onClick={() => setViewMode('global')}
            className={`px-2 py-1 text-[8px] font-black uppercase tracking-widest rounded ${viewMode === 'global' ? 'bg-slate-800 text-sky-400' : 'text-slate-500 hover:text-slate-400'}`}
          >
            Global
          </button>
          <button 
            onClick={() => setViewMode('watchlist')}
            className={`px-2 py-1 text-[8px] font-black uppercase tracking-widest rounded flex items-center ${viewMode === 'watchlist' ? 'bg-slate-800 text-sky-400' : 'text-slate-500 hover:text-slate-400'}`}
          >
            Pinned <span className="ml-1 px-1 bg-slate-700/50 rounded-full text-[7px]">{watchlist.length}</span>
          </button>
        </div>
      </div>
      <div className="space-y-1">
        {(viewMode === 'global' ? radarData : radarData.filter(i => watchlist.includes(i.company))).length === 0 ? (
          <div className="text-center py-4 text-slate-600 text-xs">
            {viewMode === 'watchlist' ? 'No active pinned companies.' : 'Scanning...'}
          </div>
        ) : (
          (viewMode === 'global' ? radarData : radarData.filter(i => watchlist.includes(i.company))).map((item) => (
            <div 
              key={item.company} 
              onClick={() => onCompanyClick?.(item.company)}
              className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-800/80 transition-colors cursor-pointer"
            >
              <div className="flex items-center space-x-2">
                <button 
                  onClick={(e) => onToggleWatchlist?.(item.company, e)}
                  className={`p-1 rounded transition-colors ${watchlist.includes(item.company) ? 'text-sky-400 hover:bg-slate-700' : 'text-slate-600 hover:text-sky-400 hover:bg-slate-700'}`}
                  title={watchlist.includes(item.company) ? "Remove from Watchlist" : "Add to Watchlist"}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill={watchlist.includes(item.company) ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>
                </button>
                <span className="text-sm font-medium text-slate-300">{item.company}</span>
              </div>
              <div className="flex items-center space-x-3">
                <span className={`text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-tighter ${item.activity_level === 'High' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                    item.activity_level === 'Moderate' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      'bg-slate-800 text-slate-500 border border-slate-700'
                  }`}>
                  {item.activity_level}
                </span>
                <div className={`p-1 rounded ${getTrendColor(item.count)}`}>
                  {getTrendIcon(item.count)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
