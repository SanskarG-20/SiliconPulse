import React from 'react';
import { Layers, Zap, Cpu, CheckCircle2, AlertCircle, Activity, ExternalLink, TrendingUp, Globe, BarChart3, ShieldAlert, FileText, HelpCircle, X, ArrowRight, RefreshCw, Clock } from 'lucide-react';
import { QueryResponse, EvidenceItem, ConfidenceInfo } from '../../types';
import { MarkdownRenderer } from '../MarkdownRenderer';
import { StrategicInsightReport } from '../StrategicInsightReport';
import { SourceBadge } from '../SourceBadge';
import { resolveTrustLevel } from '../../utils/sourceMapping';
import { getRelativeTimeLabel } from '../../utils/feedUtils';

interface QueryZoneProps {
  queryResult: QueryResponse | null;
  loading: boolean;
  error: string | null;
  insight: string | null;
  lastSubmittedQuery: string;
  filteredEvidenceItems: EvidenceItem[];
  isInsightUnavailable: boolean;
  sourceTrustFilter: 'All' | 'High' | 'Medium' | 'Low';
  setSourceTrustFilter: (f: 'All' | 'High' | 'Medium' | 'Low') => void;
  recommendations: any[];
  lastUpdate: string;
  scrollRef: React.RefObject<HTMLDivElement>;
  onSubmit: (query: string) => void;
  onRetryInsight: () => void;
  onCheckBackend: () => Promise<void>;
  onDismissError: () => void;
  onShowExport: () => void;
  onShowVerify: () => void;
}

const QuickQueryItem: React.FC<{ 
  item: any; 
  onClick: () => void; 
  idx: number;
}> = ({ item, onClick, idx }) => {
  const IconComponent = typeof item.icon === 'string'
    ? (item.icon === 'Activity' ? Activity :
      item.icon === 'Cpu' ? Cpu :
        item.icon === 'Globe' ? ExternalLink :
          item.icon === 'TrendingUp' ? TrendingUp :
            item.icon === 'Zap' ? Zap :
              item.icon === 'ShieldAlert' ? ShieldAlert :
                item.icon === 'CheckCircle2' ? CheckCircle2 :
                  item.icon === 'AlertCircle' ? AlertCircle : Layers)
    : (item.icon || Layers);

  return (
    <button
      key={`${item.label}-${idx}`}
      onClick={onClick}
      className="glass glass-hover p-4 md:p-5 text-left rounded-2xl transition-all flex items-start space-x-4 group"
    >
      <div className={`p-2 md:p-3 bg-slate-900 rounded-xl group-hover:bg-slate-800 transition-colors ${item.color}`}>
        <IconComponent size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <span className="text-[10px] font-black uppercase tracking-[0.1em] text-slate-500 mb-1 block group-hover:text-slate-300 transition-colors">{item.label}</span>
        <p className="text-xs md:text-sm font-medium text-slate-300 group-hover:text-white leading-tight truncate">{item.query}</p>
      </div>
    </button>
  );
};

export const QueryZone: React.FC<QueryZoneProps> = ({
  queryResult,
  loading,
  error,
  insight,
  lastSubmittedQuery,
  filteredEvidenceItems,
  isInsightUnavailable,
  sourceTrustFilter,
  setSourceTrustFilter,
  recommendations,
  lastUpdate,
  scrollRef,
  onSubmit,
  onRetryInsight,
  onCheckBackend,
  onDismissError,
  onShowExport,
  onShowVerify,
}) => {
  const defaultRecs = [
    { label: "NVIDIA-TSMC Pipeline", query: "Any new NVIDIA-TSMC contract today?", icon: Zap, color: "text-amber-400" },
    { label: "Foundry Design Wins", query: "Status of Intel 18A design wins and foundry clients?", icon: CheckCircle2, color: "text-emerald-400" },
    { label: "AI Infra Analysis", query: "What is the impact of Meta's new AI infra updates?", icon: Cpu, color: "text-sky-400" },
    { label: "High Impact Summary", query: "What are the top 3 high-impact events in last 2 hours?", icon: AlertCircle, color: "text-red-400" }
  ];

  // INITIAL / IDLE STATE
  if (!queryResult && !loading && !error) {
    return (
      <div className="h-full flex flex-col justify-center max-w-4xl mx-auto space-y-8 md:space-y-12">
        <div className="space-y-4">
          <div className="inline-flex items-center space-x-2 px-3 py-1 bg-sky-500/10 border border-sky-500/20 rounded-full text-sky-500 text-[10px] font-black uppercase tracking-widest animate-pulse">
            <Layers size={12} />
            <span>Ready for Intelligence Generation</span>
          </div>
          <h2 className="text-3xl md:text-5xl font-black text-white tracking-tighter uppercase leading-none">
            Strategic <br /> Intelligence <span className="text-sky-500">Node</span>
          </h2>
          <p className="text-slate-500 text-base md:text-lg font-medium max-w-xl">
            Monitor live supply chain signals, yield reports, and geopolitical shifts. Select a directive or enter a custom query.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
          {(Array.isArray(recommendations) && recommendations.length > 0 ? recommendations : defaultRecs).map((item: any, idx: number) => (
            <QuickQueryItem 
              item={item} 
              onClick={() => onSubmit(item.query)} 
              idx={idx} 
            />
          ))}
        </div>
      </div>
    );
  }

  // ERROR STATE
  if (error) {
    return (
      <div className="h-full flex flex-col items-center justify-center max-w-3xl mx-auto space-y-8 px-8">
        <div className="p-8 rounded-2xl bg-red-500/5 border border-red-500/20 w-full">
          <div className="flex items-start space-x-4">
            <AlertCircle size={32} className="text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="text-xl font-black text-red-500 uppercase tracking-tight mb-2">Intelligence Synthesis Failed</h3>
              <p className="text-slate-300 font-medium mb-4">{error}</p>

              {error.includes("Backend offline") ? (
                <button
                  onClick={onCheckBackend}
                  className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-xs font-black uppercase tracking-widest transition-all border border-red-500/30 flex items-center space-x-2"
                >
                  <RefreshCw size={12} />
                  <span>Check Connection & Retry</span>
                </button>
              ) : (
                <button
                  onClick={onDismissError}
                  className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-xs font-black uppercase tracking-widest transition-all border border-red-500/30"
                >
                  Dismiss
                </button>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={onDismissError}
          className="flex items-center space-x-2 px-6 py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)]"
        >
          <RefreshCw size={14} />
          <span>Return to Dashboard</span>
        </button>
      </div>
    );
  }

  // LOADING STATE
  if (loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center space-y-6">
        <div className="relative">
          <div className="w-20 h-20 border-[3px] border-sky-500/10 border-t-sky-500 rounded-full animate-spin"></div>
          <Activity className="absolute inset-0 m-auto text-sky-500 animate-pulse" size={32} />
        </div>
        <div className="text-center space-y-2">
          <h3 className="text-sky-500 font-black text-xs uppercase tracking-[0.4em] animate-pulse">Synthesizing Signals</h3>
          <p className="text-slate-500 text-[11px] font-mono tracking-widest uppercase">Cross-referencing global supply chain nodes...</p>
        </div>
      </div>
    );
  }

  // REPORT VIEW
  if (queryResult) {
    return (
      <div className="pb-24 pt-4 animate-in fade-in slide-in-from-bottom-8 duration-700 ease-out">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-black text-white uppercase tracking-tight mb-2">Intelligence Report</h2>
            <p className="text-slate-500 font-mono text-xs uppercase tracking-widest">Query: "{queryResult.query}"</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Signal Strength</div>
              <div className="text-xl font-black text-sky-500">{queryResult.signal_strength}%</div>
            </div>
            <div className="w-12 h-12 rounded-full border-4 border-slate-800 flex items-center justify-center relative">
              <svg className="absolute inset-0 transform -rotate-90 w-full h-full">
                <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="4" fill="transparent" className="text-slate-800" />
                <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="4" fill="transparent" className="text-sky-500" strokeDasharray={`${queryResult.signal_strength * 1.13} 113`} />
              </svg>
              <Activity size={16} className="text-sky-500" />
            </div>
          </div>
        </div>

        {/* INSIGHT SECTION */}
        {queryResult && (
          <div className="mb-8 p-4 md:p-6 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-1.5 bg-indigo-500/20 rounded-lg">
                <Zap size={18} className="text-indigo-400" />
              </div>
              <h3 className="text-sm font-black text-indigo-400 uppercase tracking-widest">Strategic Insight</h3>
            </div>
            {insight ? (
              <div className="max-w-none space-y-3">
                <StrategicInsightReport data={insight} />
                {isInsightUnavailable && (
                  <button
                    onClick={onRetryInsight}
                    className="inline-flex items-center space-x-2 px-3 py-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 rounded-md text-[10px] font-black uppercase tracking-widest border border-indigo-500/30 transition-all"
                  >
                    <RefreshCw size={12} />
                    <span>Try Again</span>
                  </button>
                )}
              </div>
            ) : (
              <div className="flex items-center space-x-3 text-slate-400">
                <RefreshCw size={16} className="animate-spin" />
                <span className="text-sm font-medium">Generating strategic insight...</span>
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center">
            <FileText size={14} className="mr-2 text-sky-500" /> Evidence Base
          </h3>
          <div className="flex space-x-1.5 md:space-x-2 overflow-x-auto no-scrollbar pb-1">
            {['All', 'High', 'Medium', 'Low'].map(level => (
              <button
                key={level}
                onClick={() => setSourceTrustFilter(level as any)}
                className={`whitespace-nowrap px-2 py-1 text-[9px] md:text-[10px] font-black uppercase tracking-widest rounded transition-colors border ${
                  sourceTrustFilter === level 
                    ? 'bg-sky-500/10 text-sky-400 border-sky-500/30 shadow-[0_0_10px_rgba(14,165,233,0.1)]' 
                    : 'bg-slate-900/50 text-slate-500 hover:text-slate-300 border-slate-800/80 hover:bg-slate-800'
                }`}
              >
                {level === 'All' ? 'All Sources' : `${level} Trust`}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          {filteredEvidenceItems.length === 0 ? (
            <div className="p-8 rounded-2xl bg-slate-900/50 border border-slate-800 text-center">
              <ShieldAlert size={32} className="mx-auto text-slate-600 mb-4" />
              <h3 className="text-lg font-bold text-slate-400 mb-2">No Direct Evidence Found</h3>
              <p className="text-slate-500 text-sm">The current data stream does not contain specific signals matching your query parameters and filters.</p>
            </div>
          ) : (
            <div className="relative border-l-2 border-slate-800 ml-4 md:ml-6 space-y-8 pb-4">
              {filteredEvidenceItems.map((item: EvidenceItem, idx: number) => {
                const itemTrust = resolveTrustLevel(item.source, item.trust_level);
                return (
                  <div key={idx} className="relative pl-6 md:pl-8">
                    <div className="absolute -left-[9px] top-6 w-4 h-4 rounded-full bg-slate-900 border-2 border-sky-500 shadow-[0_0_10px_rgba(14,165,233,0.5)] z-10"></div>
                    <div className="glass p-4 md:p-6 rounded-2xl border-slate-800/60 hover:border-sky-500/30 transition-all group active:scale-[0.98]">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center space-x-3">
                          <div className="p-2 bg-slate-900 rounded-lg text-sky-500 group-hover:text-sky-400 transition-colors">
                            <FileText size={18} />
                          </div>
                          <div>
                            <h3 className="text-base font-bold text-slate-200 group-hover:text-white transition-colors">{item.title}</h3>
                            <div className="flex items-center space-x-2 text-[10px] font-black text-slate-500 uppercase tracking-widest mt-0.5">
                              <span className={`px-1.5 py-0.5 rounded text-[8px] border ${itemTrust === 'High' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' :
                                itemTrust === 'Medium' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
                                  'bg-red-500/10 text-red-500 border-red-500/20'
                                }`}>
                                {itemTrust}
                              </span>
                              <SourceBadge source={item.source} size="sm" />
                              <span className="w-1 h-1 bg-slate-700 rounded-full"></span>
                              <span>{item.timestamp ? new Date(item.timestamp).toLocaleString() : 'N/A'}</span>
                            </div>
                          </div>
                        </div>
                        {item.company && (
                          <span className="px-2 py-1 rounded bg-slate-800 text-slate-400 text-[10px] font-bold uppercase tracking-wider">
                            {item.company}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-400 leading-relaxed border-l-2 border-slate-800 pl-4">
                        {item.content || item.snippet}
                      </p>
                      {item.url && (
                        <p className="mt-4">
                          <a href={item.url} target="_blank" rel="noreferrer" className="text-xs font-bold text-sky-400 hover:text-sky-300 flex items-center transition-colors">
                            <ExternalLink size={12} className="mr-1" /> View Source Document
                          </a>
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

        <div className="mt-16 flex items-center justify-between p-6 glass rounded-2xl border-slate-800/40">
          <div className="flex space-x-3">
            <button
              onClick={onShowExport}
              className="flex items-center space-x-2 px-4 py-2 bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest hover:bg-sky-400 transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)]"
            >
              <BarChart3 size={14} />
              <span>Export Analysis</span>
            </button>
            <button
              onClick={onShowVerify}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-xs font-black uppercase tracking-widest hover:bg-slate-700 transition-all"
            >
              <HelpCircle size={14} />
              <span>Verify Sources</span>
            </button>
          </div>
          <div className="flex items-center space-x-3 text-[10px] font-mono text-slate-600">
            <span className="uppercase tracking-widest">Last Updated: {queryResult.last_updated}</span>
            <span className="w-1 h-1 bg-slate-800 rounded-full"></span>
            <span className="uppercase tracking-widest">SID: SP-94-ALPHA</span>
          </div>
        </div>
      </div>
    </div>
    );
  }

  return null;
};