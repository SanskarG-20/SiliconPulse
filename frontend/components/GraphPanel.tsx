import React, { useEffect, useState } from 'react';
import { Network, ArrowRight, Layers, Zap, TrendingUp, AlertTriangle } from 'lucide-react';
import { fetchGraphExplain, simulateGraph } from '../api/siliconpulseApi';
import { StrategicInsightReport } from './StrategicInsightReport';

interface GraphExplain {
  company: string;
  depth: number;
  context: string;
  impact: Record<string, any>;
  suppliers: Record<string, any>;
}

export const GraphPanel: React.FC<{ company?: string }> = ({ company }) => {
  const [data, setData] = useState<GraphExplain | null>(null);
  const [loading, setLoading] = useState(false);
  const [shock, setShock] = useState<number>(-10);
  const [metric, setMetric] = useState<string>('yield');
  const [simData, setSimData] = useState<any | null>(null);
  const [simLoading, setSimLoading] = useState(false);

  useEffect(() => {
    if (!company) {
      setData(null);
      return;
    }
    setLoading(true);
    fetchGraphExplain(company)
      .then(setData)
      .finally(() => setLoading(false));
  }, [company]);

  const handleSimulate = async () => {
    if (!company) return;
    setSimLoading(true);
    setSimData(null);
    try {
      const res = await simulateGraph(company, shock / 100, 2, metric);
      setSimData(res);
    } finally {
      setSimLoading(false);
    }
  };

  if (!company) {
    return (
      <div className="rounded-[14px] border border-[#1C3553]/40 bg-[#0E1E32]/60 p-4">
        <div className="flex items-center gap-1.5 mono text-[10px] font-semibold tracking-[0.12em] text-slate-500 dark:text-[#64748B]">
          <Network size={12} className="text-[#22D3EE]" />
          SUPPLY-CHAIN GRAPH
        </div>
        <p className="mt-2 text-[12px] leading-relaxed text-slate-500 dark:text-[#64748B]">Select a company from the feed or the explorer to see upstream and downstream.</p>
      </div>
    );
  }

  return (
    <div className="rounded-[14px] border border-[#1C3553]/50 bg-[#0E1E32]/50 p-4 space-y-4">
      <div className="flex items-center gap-1.5 mono text-[10px] font-semibold tracking-[0.12em] text-[#22D3EE]">
        <Network size={12} />
        GRAPH RAG — {company}
        {loading && <span className="ml-1 text-[#475569] animate-pulse">loading…</span>}
      </div>

      {data ? (
        <>
          <div>
            <p className="display flex items-center gap-1 text-[10px] font-semibold tracking-[0.1em] text-slate-600 dark:text-[#94A3B8]">
              <Layers size={10} /> UPSTREAM
            </p>
            {Object.keys(data.suppliers).length === 0 ? (
              <p className="mt-1 text-[12px] text-[#475569]">No suppliers in graph</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {Object.entries(data.suppliers)
                  .slice(0, 4)
                  .map(([k, v]: any) => (
                    <li key={k} className="flex items-center justify-between rounded-full bg-white dark:bg-[#050B1A] border border-[#1C3553]/40 px-2.5 py-1">
                      <span className="text-[12px] font-semibold text-[#22D3EE]">{k}</span>
                      <span className="mono text-[10px] tracking-[0.06em] text-[#475569]">score {v.score}</span>
                    </li>
                  ))}
              </ul>
            )}
          </div>

          <div>
            <p className="display flex items-center gap-1 text-[10px] font-semibold tracking-[0.1em] text-slate-600 dark:text-[#94A3B8]">
              <Network size={10} /> DOWNSTREAM
            </p>
            {Object.keys(data.impact).length === 0 ? (
              <p className="mt-1 text-[12px] text-[#475569]">No downstream impact</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {Object.entries(data.impact)
                  .slice(0, 4)
                  .map(([k, v]: any) => (
                    <li key={k} className="flex items-center justify-between rounded-full bg-white dark:bg-[#050B1A] border border-[#1C3553]/40 px-2.5 py-1">
                      <span className="text-[12px] font-semibold text-[#E8A253]">{k}</span>
                      <span className="mono text-[10px] tracking-[0.06em] text-[#475569]">score {v.score}</span>
                    </li>
                  ))}
              </ul>
            )}
          </div>

          <details className="rounded-[10px] bg-white dark:bg-[#050B1A] border border-[#1C3553]/30 p-2">
            <summary className="mono cursor-pointer text-[10px] font-semibold tracking-[0.08em] text-[#475569]">Raw context</summary>
            <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-[11px] leading-relaxed text-slate-600 dark:text-[#94A3B8] custom-scrollbar">{data.context}</pre>
          </details>

          <div className="rounded-[14px] border border-[#E8A253]/15 bg-[#E8A253]/[0.06] p-3 space-y-3">
            <p className="flex items-center gap-1.5 mono text-[10px] font-bold tracking-[0.12em] text-[#E8A253]">
              <Zap size={12} /> SCENARIO — WHAT IF?
            </p>
            <div className="flex items-center gap-2">
              <select value={metric} onChange={(e) => setMetric(e.target.value)} className="rounded-full bg-white dark:bg-[#050B1A] border border-[#1C3553] px-2.5 py-1 text-[11px] font-medium text-[#CBD5E1] focus:border-[#E8A253]/30 focus:outline-none">
                <option value="yield">Yield</option>
                <option value="capacity">Capacity</option>
                <option value="supply">Supply</option>
              </select>
              <input type="range" min={-50} max={30} value={shock} onChange={(e) => setShock(parseInt(e.target.value))} className="flex-1 accent-[#E8A253]" />
              <span className={`mono min-w-[44px] text-right text-[11px] font-bold ${shock < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                {shock > 0 ? '+' : ''}
                {shock}%
              </span>
            </div>
            <button
              onClick={handleSimulate}
              disabled={simLoading}
              className="w-full inline-flex items-center justify-center gap-1.5 rounded-full bg-[#E8A253] py-1.5 text-[11px] font-bold tracking-[0.06em] text-[#050B1A] hover:bg-[#F0A85E] disabled:opacity-50 transition-colors"
            >
              {simLoading ? (
                <>
                  <TrendingUp size={13} className="animate-pulse" /> Simulating…
                </>
              ) : (
                <>
                  <AlertTriangle size={13} /> Simulate shock
                </>
              )}
            </button>
            {simData && (
              <div className="space-y-2 pt-2 border-t border-[#E8A253]/15">
                <p className="text-[11px] font-semibold text-[#E8A253]">Impact: {simData.company} {shock}% {metric}</p>
                <p className="mono text-[10px] leading-relaxed text-slate-500 dark:text-[#64748B] line-clamp-3">{simData.impact_text?.slice(0, 280)}</p>
                {simData.impact && Object.keys(simData.impact).length > 0 && (
                  <ul className="space-y-1">
                    {Object.entries(simData.impact)
                      .slice(0, 4)
                      .map(([k, v]: any) => (
                        <li key={k} className="flex items-center justify-between rounded-full bg-white dark:bg-[#050B1A] border border-[#1C3553]/40 px-2.5 py-1">
                          <span className="text-[11px] font-semibold text-[#E2E8F0]">{k}</span>
                          <span className={`mono text-[10px] font-bold ${v.severity === 'High' ? 'text-red-400' : v.severity === 'Medium' ? 'text-[#E8A253]' : 'text-emerald-400'}`}>
                            {v.delta > 0 ? '+' : ''}
                            {v.delta} • ${v.est_impact_usd_m}M
                          </span>
                        </li>
                      ))}
                  </ul>
                )}
                {simData.scenario_report && (
                  <div className="max-h-[200px] overflow-auto rounded-[10px] border border-[#1C3553]/30 bg-white dark:bg-[#050B1A] p-2 custom-scrollbar">
                    <StrategicInsightReport data={simData.scenario_report} />
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      ) : (
        !loading && <p className="text-[12px] text-[#475569]">No graph data for {company}</p>
      )}
    </div>
  );
};
