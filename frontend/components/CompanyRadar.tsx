
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
}

export const CompanyRadar: React.FC<CompanyRadarProps> = ({ onCompanyClick }) => {
  const [radarData, setRadarData] = useState<RadarItem[]>([]);

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
        <span className="text-[9px] font-mono text-slate-600">LIVE</span>
      </div>
      <div className="space-y-1">
        {radarData.length === 0 ? (
          <div className="text-center py-4 text-slate-600 text-xs">Scanning...</div>
        ) : (
          radarData.map((item) => (
            <div 
              key={item.company} 
              onClick={() => onCompanyClick?.(item.company)}
              className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-800/80 transition-colors cursor-pointer"
            >
              <span className="text-sm font-medium text-slate-300">{item.company}</span>
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
