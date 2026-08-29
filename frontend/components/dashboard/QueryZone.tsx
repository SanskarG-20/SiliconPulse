import React from 'react';
import {
  Layers,
  Zap,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Activity,
  ExternalLink,
  TrendingUp,
  Globe,
  BarChart3,
  ShieldAlert,
  FileText,
  HelpCircle,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { QueryResponse, EvidenceItem } from '../../types';
import { MarkdownRenderer } from '../MarkdownRenderer';
import { StrategicInsightReport } from '../StrategicInsightReport';
import { SourceBadge } from '../SourceBadge';
import { resolveTrustLevel } from '../../utils/sourceMapping';

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

const QuickQueryItem: React.FC<{ item: any; onClick: () => void; idx: number }> = ({ item, onClick }) => {
  const IconComponent =
    typeof item.icon === 'string'
      ? item.icon === 'Activity'
        ? Activity
        : item.icon === 'Cpu'
          ? Cpu
          : item.icon === 'Globe'
            ? Globe
            : item.icon === 'TrendingUp'
              ? TrendingUp
              : item.icon === 'Zap'
                ? Zap
                : item.icon === 'ShieldAlert'
                  ? ShieldAlert
                  : item.icon === 'CheckCircle2'
                    ? CheckCircle2
                    : item.icon === 'AlertCircle'
                      ? AlertCircle
                      : Layers
      : item.icon || Layers;

  return (
    <button
      onClick={onClick}
      className="group text-left glass glass-hover rounded-[16px] p-4 flex items-start gap-3.5 w-full"
    >
      <span className={`w-9 h-9 rounded-[10px] bg-white dark:bg-[#050B1A] border border-[#1C3553]/50 flex items-center justify-center shrink-0 group-hover:border-[#22D3EE]/30 transition-colors ${item.color}`}>
        <IconComponent size={16} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="display block text-[10px] font-semibold tracking-[0.1em] text-slate-500 dark:text-[#64748B] group-hover:text-slate-600 dark:text-[#94A3B8] transition-colors">{item.label}</span>
        <span className="block text-[13px] font-medium leading-snug text-[#CBD5E1] group-hover:text-slate-900 dark:hover:text-white truncate">{item.query}</span>
      </span>
      <ArrowRight size={14} className="text-[#334155] group-hover:text-[#22D3EE] group-hover:translate-x-0.5 transition-all shrink-0 mt-1" />
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
  onSubmit,
  onRetryInsight,
  onCheckBackend,
  onDismissError,
  onShowExport,
  onShowVerify,
}) => {
  const defaultRecs = [
    { label: 'NVIDIA-TSMC Pipeline', query: 'Any new NVIDIA-TSMC contract today?', icon: Zap, color: 'text-[#E8A253]' },
    { label: 'Foundry Design Wins', query: 'Status of Intel 18A design wins and foundry clients?', icon: CheckCircle2, color: 'text-emerald-400' },
    { label: 'AI Infra Analysis', query: 'What is the impact of Meta’s new AI infra updates?', icon: Cpu, color: 'text-[#22D3EE]' },
    { label: 'High Impact Summary', query: 'What are the top 3 high-impact events in last 2 hours?', icon: AlertCircle, color: 'text-red-400' },
  ];

  if (!queryResult && !loading && !error) {
    return (
      <div className="max-w-[760px] mx-auto space-y-8 py-2">
        {/* Thesis hero - wafer reticle */}
        <div className="relative overflow-hidden rounded-[20px] border border-[#1C3553]/50 bg-[#0E1E32]/40 p-6 md:p-8 blueprint-grid">
          <div className="absolute top-0 right-0 w-64 h-64 opacity-[0.06] pointer-events-none hidden md:block" style={{
            background: 'radial-gradient(circle at center, #E8A253 1px, transparent 1.5px)',
            backgroundSize: '18px 18px'
          }} />
          <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full border border-dashed border-[#22D3EE]/15 hidden md:block" />
          <div className="relative">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#22D3EE]/10 border border-[#22D3EE]/15 text-[#22D3EE] mono text-[10px] font-semibold tracking-[0.1em]">
              <Layers size={12} /> READY FOR INTELLIGENCE
            </span>
            <h2 className="display mt-4 text-[30px] md:text-[42px] font-bold leading-[0.95] tracking-[-0.03em] text-white">
              Strategic
              <br />
              Intelligence <span className="text-[#22D3EE]">Node</span>
            </h2>
            <p className="mt-3 text-[14px] md:text-[15px] leading-relaxed text-slate-600 dark:text-[#94A3B8] max-w-[560px]">
              Live supply-chain signals, yield reports and geopolitical shifts — grounded in evidence, scored for confidence, ready to brief.
            </p>
            <div className="mt-4 flex flex-wrap gap-2 mono text-[10px] tracking-[0.08em] text-[#475569]">
              <span className="px-2 py-1 rounded-full bg-white dark:bg-[#050B1A] border border-[#1C3553]/50">RETICLE OK</span>
              <span className="px-2 py-1 rounded-full bg-white dark:bg-[#050B1A] border border-[#1C3553]/50">FRESHNESS 12h</span>
              <span className="px-2 py-1 rounded-full bg-white dark:bg-[#050B1A] border border-[#1C3553]/50 hidden sm:inline">HYBRID VECTOR ≥0.72</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {(Array.isArray(recommendations) && recommendations.length > 0 ? recommendations : defaultRecs).map((item: any, idx: number) => (
            <QuickQueryItem key={`${item.label}-${idx}`} item={item} onClick={() => onSubmit(item.query)} idx={idx} />
          ))}
        </div>

        <div className="rounded-[14px] border border-[#1C3553]/30 bg-[#0B1426]/40 p-3 flex items-center justify-between mono text-[10px] tracking-[0.08em] text-[#475569]">
          <span>Try: “TSMC N2 yield” • “ASML EUV supply” • “NVIDIA HBM”</span>
          <span className="hidden sm:inline text-slate-500 dark:text-[#64748B]">Last update {lastUpdate}</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-[640px] mx-auto py-10 space-y-6">
        <div className="rounded-[16px] border border-red-500/15 bg-red-500/[0.06] p-6 flex gap-4">
          <span className="w-10 h-10 rounded-[12px] bg-red-500/10 border border-red-500/15 flex items-center justify-center shrink-0">
            <AlertCircle size={18} className="text-red-400" />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="display text-[14px] font-semibold tracking-[-0.01em] text-red-300">Intelligence synthesis failed</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-[#FECACA]">{error}</p>
            <div className="mt-4 flex gap-2">
              {error.includes('Backend offline') ? (
                <button onClick={onCheckBackend} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-500 text-white text-[11px] font-semibold tracking-[0.04em] hover:bg-red-400 transition-colors">
                  <RefreshCw size={13} /> Check connection
                </button>
              ) : (
                <button onClick={onDismissError} className="px-3 py-1.5 rounded-full bg-[#0E1E32] border border-[#1C3553] text-[11px] font-semibold text-slate-600 dark:text-[#94A3B8] hover:text-slate-900 dark:hover:text-white transition-colors">
                  Dismiss
                </button>
              )}
            </div>
          </div>
        </div>
        <button onClick={onDismissError} className="mx-auto flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#E8A253] text-[#050B1A] text-[11px] font-bold tracking-[0.04em] hover:bg-[#F0A85E] transition-colors">
          <RefreshCw size={14} /> Return to bench
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="h-[60vh] flex flex-col items-center justify-center gap-6">
        <div className="relative w-20 h-20">
          <div className="absolute inset-0 rounded-full border-[3px] border-[#1C3553] border-t-[#E8A253] animate-spin" />
          <div className="absolute inset-3 rounded-full border border-dashed border-[#22D3EE]/20 animate-spin [animation-duration:3s]" />
          <Activity className="absolute inset-0 m-auto text-[#E8A253] animate-pulse" size={22} />
        </div>
        <div className="text-center">
          <p className="display text-[11px] font-semibold tracking-[0.18em] text-[#E8A253]">SYNTHESIZING SIGNALS</p>
          <p className="mono mt-1 text-[11px] tracking-[0.08em] text-[#475569]">Cross-referencing fab nodes • scoring confidence</p>
        </div>
      </div>
    );
  }

  if (queryResult) {
    return (
      <div className="max-w-[760px] mx-auto pb-10">
        {/* Report header - copper yield ring */}
        <div className="flex items-start justify-between gap-4 mb-6">
          <div className="min-w-0">
            <p className="mono text-[10px] tracking-[0.12em] font-semibold text-[#22D3EE]">INTELLIGENCE REPORT</p>
            <h2 className="display mt-1 text-[22px] font-bold tracking-[-0.02em] leading-tight text-white truncate">“{queryResult.query}”</h2>
            <p className="mono mt-1 text-[11px] tracking-[0.06em] text-slate-500 dark:text-[#64748B]">Last updated {queryResult.last_updated} • {filteredEvidenceItems.length} pieces of evidence</p>
          </div>
          <div className="shrink-0 flex items-center gap-3">
            <div className="hidden sm:block text-right">
              <p className="mono text-[10px] tracking-[0.1em] font-semibold text-slate-500 dark:text-[#64748B]">SIGNAL STRENGTH</p>
              <p className="display text-[18px] font-bold tracking-[-0.02em] text-[#E8A253]">{queryResult.signal_strength}%</p>
            </div>
            <div className="w-12 h-12 rounded-full p-[3px] bg-[#0E1E32] border border-[#1C3553]">
              <div className="w-full h-full rounded-full relative overflow-hidden bg-white dark:bg-[#050B1A] flex items-center justify-center">
                <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 44 44">
                  <circle cx="22" cy="22" r="18" fill="none" stroke="#1C3553" strokeWidth="4" />
                  <circle
                    cx="22"
                    cy="22"
                    r="18"
                    fill="none"
                    stroke="#E8A253"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeDasharray={`${(queryResult.signal_strength / 100) * 113} 113`}
                    style={{ filter: 'drop-shadow(0 0 6px rgba(232,162,83,0.45))' }}
                  />
                </svg>
                <Activity size={14} className="text-[#E8A253] relative" />
              </div>
            </div>
          </div>
        </div>

        {/* Insight - blueprint sheet */}
        <div className="rounded-[16px] border border-[#1C3553]/50 bg-[#0E1E32]/50 backdrop-blur-sm overflow-hidden">
          <div className="h-1 w-full bg-gradient-to-r from-[#22D3EE] via-[#E8A253] to-[#22D3EE] opacity-60" />
          <div className="p-5 md:p-6 blueprint-grid relative">
            <div className="absolute top-3 right-3 mono text-[9px] tracking-[0.12em] text-[#475569] hidden md:block">GEMINI • GRAPH RAG • VECTOR ≥0.72</div>
            <div className="flex items-center gap-2.5 mb-3">
              <span className="w-7 h-7 rounded-[8px] bg-[#E8A253]/10 border border-[#E8A253]/15 flex items-center justify-center">
                <Zap size={14} className="text-[#E8A253]" />
              </span>
              <h3 className="display text-[11px] font-semibold tracking-[0.12em] text-[#E8A253]">STRATEGIC INSIGHT</h3>
            </div>
            {insight ? (
              <div className="serif text-[14.5px] leading-[1.65] text-[#E2E8F0]">
                <StrategicInsightReport data={insight} />
                {isInsightUnavailable && (
                  <button onClick={onRetryInsight} className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#0E1E32] border border-[#1C3553] text-[11px] font-semibold text-slate-600 dark:text-[#94A3B8] hover:text-slate-900 dark:hover:text-white transition-colors">
                    <RefreshCw size={12} /> Try again
                  </button>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2.5 py-4 text-slate-500 dark:text-[#64748B] mono text-[12px]">
                <RefreshCw size={14} className="animate-spin" /> Generating insight…
              </div>
            )}
          </div>
        </div>

        {/* Evidence */}
        <div className="mt-6 flex items-center justify-between">
          <h3 className="display flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.12em] text-slate-600 dark:text-[#94A3B8]">
            <FileText size={13} className="text-[#22D3EE]" /> EVIDENCE BASE
          </h3>
          <div className="flex gap-1.5">
            {(['All', 'High', 'Medium', 'Low'] as const).map((lvl) => (
              <button
                key={lvl}
                onClick={() => setSourceTrustFilter(lvl)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-[0.02em] border transition-colors ${
                  sourceTrustFilter === lvl
                    ? 'bg-[#22D3EE] text-[#050B1A] border-[#22D3EE] shadow-[0_0_12px_rgba(34,211,238,0.25)]'
                    : 'bg-[#0E1E32] text-slate-500 dark:text-[#64748B] border-[#1C3553]/60 hover:text-slate-900 dark:hover:text-white hover:border-[#22D3EE]/20'
                }`}
              >
                {lvl === 'All' ? 'All' : lvl}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 space-y-4">
          {filteredEvidenceItems.length === 0 ? (
            <div className="rounded-[14px] border border-dashed border-[#1C3553]/50 bg-[#0B1426]/40 p-8 text-center">
              <ShieldAlert size={22} className="mx-auto text-[#334155] mb-2" />
              <p className="display text-[12px] font-semibold tracking-[0.06em] text-slate-600 dark:text-[#94A3B8]">NO DIRECT EVIDENCE</p>
              <p className="mt-1 text-[13px] text-[#475569]">No signals match your filters. Try “All” or relax the query.</p>
            </div>
          ) : (
            <div className="relative ml-3 border-l border-[#1C3553]/50 space-y-4 pl-6">
              {filteredEvidenceItems.map((item: EvidenceItem, idx: number) => {
                const trust = resolveTrustLevel(item.source, (item as any).trust_level);
                return (
                  <div key={idx} className="relative">
                    <span className="absolute -left-[25px] top-5 w-2.5 h-2.5 rounded-full bg-[#0E1E32] border-2 border-[#E8A253] shadow-[0_0_10px_rgba(232,162,83,0.35)]" />
                    <div className="glass rounded-[14px] p-4 hover:border-[#22D3EE]/20 transition-colors">
                      <div className="flex items-start justify-between gap-3">
                        <h4 className="text-[13.5px] font-semibold leading-snug text-slate-800 dark:text-[#F1F5F9]">{item.title}</h4>
                        {item.company && <span className="shrink-0 px-2 py-1 rounded-full bg-[#E8A253]/10 border border-[#E8A253]/15 text-[10px] font-bold tracking-[0.06em] text-[#E8A253]">{item.company}</span>}
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5 mono text-[10px] tracking-[0.06em]">
                        <span className={`px-1.5 py-0.5 rounded-[6px] border text-[9px] font-bold tracking-[0.06em] ${trust === 'High' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : trust === 'Medium' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>{trust}</span>
                        <SourceBadge source={item.source} size="sm" />
                        <span className="text-[#475569]">• {item.timestamp ? new Date(item.timestamp).toLocaleString() : 'N/A'}</span>
                      </div>
                      <p className="serif mt-2.5 text-[13.5px] leading-relaxed text-slate-600 dark:text-[#94A3B8] border-l-2 border-[#1C3553]/60 pl-3">{item.content || item.snippet}</p>
                      {item.url && (
                        <a href={item.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-[12px] font-medium text-[#22D3EE] hover:text-[#6CE6F7] transition-colors">
                          <ExternalLink size={12} /> View source
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-[14px] border border-[#1C3553]/40 bg-[#0B1426]/60 p-4">
          <div className="flex gap-2">
            <button onClick={onShowExport} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#E8A253] text-[#050B1A] text-[11px] font-bold tracking-[0.04em] hover:bg-[#F0A85E] transition-colors">
              <BarChart3 size={14} /> Export
            </button>
            <button onClick={onShowVerify} className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#0E1E32] border border-[#1C3553] text-[11px] font-semibold tracking-[0.04em] text-slate-600 dark:text-[#94A3B8] hover:text-slate-900 dark:hover:text-white hover:border-[#22D3EE]/20 transition-colors">
              <HelpCircle size={14} /> Verify
            </button>
          </div>
          <span className="mono text-[10px] tracking-[0.08em] text-[#475569]">SID SP-94-ALPHA • {lastSubmittedQuery ? `Q: ${lastSubmittedQuery.slice(0, 32)}` : ''}</span>
        </div>
      </div>
    );
  }

  return null;
};
