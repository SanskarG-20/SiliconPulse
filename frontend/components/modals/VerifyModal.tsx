import React from 'react';
import { X, ShieldCheck, ExternalLink, RefreshCw } from 'lucide-react';
import { SourceBadge } from '../SourceBadge';
import { resolveTrustLevel } from '../../utils/sourceMapping';

interface VerifySourceItem {
  timestamp?: string;
  source: string;
  title: string;
  url?: string;
  trust_level?: string;
  reason: string;
}

interface VerifyModalProps {
  isOpen: boolean;
  onClose: () => void;
  verifying: boolean;
  sources: VerifySourceItem[];
}

export const VerifyModal: React.FC<VerifyModalProps> = ({
  isOpen,
  onClose,
  verifying,
  sources,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-[#020617] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative flex flex-col max-h-[80vh]">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors z-10"><X size={20} /></button>
        <div className="p-4 md:p-6 border-b border-slate-800/50 shrink-0">
          <h3 className="text-lg font-black text-white uppercase tracking-tight flex items-center">
            <ShieldCheck size={20} className="mr-2 text-emerald-500" /> Source Verification
          </h3>
          <p className="text-xs text-slate-500 mt-2">Checking real-time credibility of retrieved intelligence across global databases.</p>
        </div>
        <div className="p-4 md:p-6 overflow-y-auto custom-scrollbar">
          {verifying ? (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <RefreshCw size={32} className="animate-spin text-emerald-500" />
              <span className="text-sm font-mono text-slate-400 uppercase tracking-widest">Verifying Source Integrity...</span>
            </div>
          ) : (
            <div className="space-y-3">
              {sources.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-slate-500 text-sm italic">No sources found for this query.</p>
                </div>
              ) : (
                sources.map((src, idx) => {
                  const trustLevel = resolveTrustLevel(src.source, src.trust_level);
                  return (
                    <div key={idx} className="p-4 rounded-xl bg-slate-900/50 border border-slate-800 flex items-start justify-between">
                      <div className="flex-1 pr-4">
                        <div className="flex items-center space-x-2 mb-1">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border ${trustLevel === 'High' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' :
                            trustLevel === 'Medium' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
                              'bg-red-500/10 text-red-500 border-red-500/20'
                            }`}>
                            {trustLevel} Trust
                          </span>
                          <SourceBadge source={src.source} size="sm" />
                          <span className="text-[10px] text-slate-600">•</span>
                          <span className="text-[10px] text-slate-600">{src.timestamp ? new Date(src.timestamp).toLocaleString() : 'N/A'}</span>
                        </div>
                        <h4 className="text-sm font-bold text-slate-200 mb-1">{src.title}</h4>
                        <p className="text-xs text-slate-500 italic">{src.reason}</p>
                      </div>
                      {src.url && (
                        <a href={src.url} target="_blank" rel="noreferrer" className="p-2 bg-slate-800 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors">
                          <ExternalLink size={16} />
                        </a>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};