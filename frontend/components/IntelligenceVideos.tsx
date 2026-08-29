import React, { useState, useEffect } from 'react';
import { fetchVideos } from '../api/siliconpulseApi';
import { Play, RefreshCw, AlertCircle } from 'lucide-react';

interface VideoItem {
  video_id: string;
  title: string;
  description: string;
  thumbnail: string;
  channel: string;
  published_at: string;
  url: string;
  category: string;
}

interface IntelligenceVideosProps {
  lastSubmittedQuery: string | null;
}

const CATEGORIES = [
  { id: 'all', label: 'All' },
  { id: 'ai', label: 'AI' },
  { id: 'semiconductor', label: 'Semiconductor' },
  { id: 'product_launch', label: 'Product Launches' },
  { id: 'gpu', label: 'GPUs' },
  { id: 'supply_chain', label: 'Supply Chain' },
  { id: 'company_update', label: 'Company Updates' },
];

export const IntelligenceVideos: React.FC<IntelligenceVideosProps> = ({ lastSubmittedQuery }) => {
  const [showVideos, setShowVideos] = useState(() => localStorage.getItem('siliconpulse_showVideos') !== '0');
  const [activeCategory, setActiveCategory] = useState('all');
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!showVideos) return;
    loadVideos(lastSubmittedQuery, activeCategory);
  }, [showVideos, activeCategory, lastSubmittedQuery]);

  const loadVideos = async (query: string | null, category: string) => {
    setLoading(true);
    setError(false);
    try {
      // Use query only if activeCategory is 'all' or if we want to augment specific searches
      const queryParam = (category === 'all' && query) ? query : undefined;
      const res = await fetchVideos(queryParam, category, 6);
      if (res && res.length > 0) {
        setVideos(res);
      } else {
        // Only set error if we couldn't even get defaults
        if (videos.length === 0) setError(true);
      }
    } catch (e) {
      if (videos.length === 0) setError(true);
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = () => {
    const next = !showVideos;
    setShowVideos(next);
    localStorage.setItem('siliconpulse_showVideos', next ? '1' : '0');
  };

  const getRelativeTimeLabel = (timestamp: string) => {
    if (!timestamp) return 'Recent';
    try {
      const msPerMinute = 60 * 1000;
      const msPerHour = msPerMinute * 60;
      const msPerDay = msPerHour * 24;
      const elapsed = Date.now() - new Date(timestamp).getTime();
      
      if (elapsed < msPerHour) return `${Math.floor(elapsed / msPerMinute)}m ago`;
      if (elapsed < msPerDay) return `${Math.floor(elapsed / msPerHour)}h ago`;
      return `${Math.floor(elapsed / msPerDay)}d ago`;
    } catch {
      return 'Recent';
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200/60 dark:border-slate-800/60 bg-white/30 dark:bg-slate-950/30 backdrop-blur-sm mb-6">
      <button
        onClick={toggleSection}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <span className="text-[11px] font-black uppercase tracking-widest text-slate-600 dark:text-slate-400">
          {showVideos ? '▾' : '▸'} Intelligence Videos
        </span>
        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">
          {showVideos ? 'Hide' : 'Show'} • YouTube • Context-Aware
        </span>
      </button>

      {showVideos && (
        <div className="px-4 pb-4">
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {CATEGORIES.map(cat => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded transition-colors ${
                  activeCategory === cat.id
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                    : 'bg-slate-50/50 dark:bg-slate-900/50 text-slate-500 hover:text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:bg-slate-800'
                }`}
              >
                {cat.label}
              </button>
            ))}
            <div className="flex-1" />
            <button
              onClick={() => loadVideos(lastSubmittedQuery, activeCategory)}
              disabled={loading}
              className="text-slate-500 hover:text-sky-400 transition-colors p-1"
              title="Refresh Videos"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>

          {error && !loading && (
            <div className="rounded-xl border border-red-500/15 bg-red-500/[0.06] p-4 flex items-center justify-center space-x-2">
              <AlertCircle size={16} className="text-red-400" />
              <span className="text-red-300 text-xs font-bold uppercase tracking-widest">
                Video feed temporarily unavailable.
              </span>
              <button 
                onClick={() => loadVideos(lastSubmittedQuery, activeCategory)}
                className="ml-2 text-[10px] font-black uppercase tracking-widest text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:text-slate-200"
              >
                Retry
              </button>
            </div>
          )}

          {loading && videos.length === 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="rounded-xl bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 animate-pulse h-48" />
              ))}
            </div>
          )}

          {!error && videos.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {videos.map((video, idx) => (
                <a
                  key={idx}
                  href={video.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 overflow-hidden hover:border-sky-500/30 transition-all flex flex-col cursor-pointer"
                >
                  <div className="relative aspect-video bg-black overflow-hidden">
                    <img 
                      src={video.thumbnail} 
                      alt={video.title} 
                      className="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300"
                      loading="lazy"
                    />
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Play className="text-white fill-white" size={32} />
                    </div>
                    <div className="absolute bottom-2 right-2 px-1.5 py-0.5 bg-black/80 rounded text-[9px] font-mono text-slate-700 dark:text-slate-300">
                      YouTube
                    </div>
                  </div>
                  <div className="p-3 flex-1 flex flex-col">
                    <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 line-clamp-2 leading-tight mb-2 group-hover:text-sky-100">
                      {video.title}
                    </h4>
                    <div className="mt-auto flex items-center justify-between text-[10px] text-slate-500 font-medium">
                      <span className="truncate pr-2">{video.channel}</span>
                      <span className="shrink-0">{getRelativeTimeLabel(video.published_at)}</span>
                    </div>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
