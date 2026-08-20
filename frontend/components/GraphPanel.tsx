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
      <div className="p-4 rounded-xl bg-slate-900/30 border border-slate-800/50">
        <div className="flex items-center space-x-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">
          <Network size={12} className="text-sky-500" />
          <span>Supply-Chain Graph</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-2">Select a company to see upstream suppliers and downstream impact.</p>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-xl bg-slate-900/30 border border-slate-800/50 space-y-3">
      <div className="flex items-center space-x-2 text-[10px] font-black text-sky-500 uppercase tracking-widest">
        <Network size={12} />
        <span>Graph RAG — {company}</span>
        {loading && <span className="text-slate-500 animate-pulse">loading…</span>}
      </div>

      {data ? (
        <>
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center">
              <Layers size={10} className="mr-1" /> Upstream
            </div>
            {Object.keys(data.suppliers).length === 0 ? (
              <p className="text-[11px] text-slate-500">No suppliers in graph</p>
            ) : (
              <ul className="mt-1 space-y-1">
                {Object.entries(data.suppliers).slice(0, 4).map(([k, v]: any) => (
                  <li key={k} className="text-[11px] text-slate-300 flex items-center">
                    <span className="text-sky-400 font-bold">{k}</span>
                    <ArrowRight size={10} className="mx-1 text-slate-600" />
                    <span className="text-slate-500">score {v.score}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center">
              <Network size={10} className="mr-1" /> Downstream
            </div>
            {Object.keys(data.impact).length === 0 ? (
              <p className="text-[11px] text-slate-500">No downstream impact</p>
            ) : (
              <ul className="mt-1 space-y-1">
                {Object.entries(data.impact).slice(0, 4).map(([k, v]: any) => (
                  <li key={k} className="text-[11px] text-slate-300 flex items-center">
                    <span className="text-emerald-400 font-bold">{k}</span>
                    <ArrowRight size={10} className="mx-1 text-slate-600" />
                    <span className="text-slate-500">score {v.score}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <details className="mt-2">
            <summary className="text-[10px] font-bold text-slate-500 uppercase tracking-widest cursor-pointer">Raw context</summary>
            <pre className="mt-2 text-[10px] text-slate-400 whitespace-pre-wrap leading-relaxed bg-slate-950/50 p-2 rounded border border-slate-800">{data.context}</pre>
          </details>

          <div className="mt-3 p-3 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-2">
            <div className="flex items-center space-x-2 text-[10px] font-black text-amber-500 uppercase tracking-widest">
              <Zap size={12} />
              <span>Scenario Engine — What if?</span>
            </div>
            <div className="flex items-center space-x-2">
              <select value={metric} onChange={e => setMetric(e.target.value)} className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300">
                <option value="yield">Yield</option>
                <option value="capacity">Capacity</option>
                <option value="supply">Supply</option>
              </select>
              <input
                type="range"
                min={-50}
                max={30}
                value={shock}
                onChange={e => setShock(parseInt(e.target.value))}
                className="flex-1 accent-amber-500"
              />
              <span className={`text-[11px] font-black min-w-[40px] text-right ${shock < 0 ? 'text-red-400' : 'text-emerald-400'}`}>{shock > 0 ? '+' : ''}{shock}%</span>
            </div>
            <button
              onClick={handleSimulate}
              disabled={simLoading}
              className="w-full py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded text-[11px] font-black uppercase tracking-widest flex items-center justify-center space-x-1"
            >
              {simLoading ? <><TrendingUp size={12} className="animate-pulse" /><span>Simulating…</span></> : <><AlertTriangle size={12} /><span>Simulate Shock</span></>}
            </button>
            {simData && (
              <div className="space-y-2">
                <div className="text-[11px] text-slate-300">
                  <div className="font-bold text-amber-400">Impact: {simData.company} {shock}% {metric}</div>
                  <div className="text-[10px] text-slate-500">{simData.impact_text?.slice(0, 300)}</div>
                </div>
                {simData.impact && Object.keys(simData.impact).length > 0 && (
                  <ul className="space-y-1">
                    {Object.entries(simData.impact).slice(0, 4).map(([k, v]: any) => (
                      <li key={k} className="text-[11px] flex items-center justify-between bg-slate-900/50 px-2 py-1 rounded border border-slate-800">
                        <span className="font-bold text-slate-200">{k}</span>
                        <span className={`text-[10px] font-black ${v.severity === 'High' ? 'text-red-400' : v.severity === 'Medium' ? 'text-amber-400' : 'text-emerald-400'}`}>{v.delta > 0 ? '+' : ''}{v.delta} • ${v.est_impact_usd_m}M</span>
                      </li>
                    ))}
                  </ul>
                )}
                {simData.scenario_report && (
                  <div className="max-h-[200px] overflow-y-auto custom-scrollbar border-t border-amber-500/20 pt-2">
                    <StrategicInsightReport data={simData.scenario_report} />
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      ) : (
        !loading && <p className="text-[11px] text-slate-500">No graph data for {company}</p>
      )}
    </div>
  );
};
