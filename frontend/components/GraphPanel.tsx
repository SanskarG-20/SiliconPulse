import React, { useEffect, useState } from 'react';
import { Network, ArrowRight, Layers } from 'lucide-react';
import { fetchGraphExplain } from '../api/siliconpulseApi';

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
        </>
      ) : (
        !loading && <p className="text-[11px] text-slate-500">No graph data for {company}</p>
      )}
    </div>
  );
};
