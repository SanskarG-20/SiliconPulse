import React from 'react';
import { X, BarChart3 } from 'lucide-react';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExport: () => Promise<void>;
  format: string;
  setFormat: (v: string) => void;
  includeEvidence: boolean;
  setIncludeEvidence: (v: boolean) => void;
}

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  onExport,
  format,
  setFormat,
  includeEvidence,
  setIncludeEvidence,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-md bg-[#020617] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors"><X size={20} /></button>
        <div className="p-4 md:p-6 border-b border-slate-800/50">
          <h3 className="text-lg font-black text-white uppercase tracking-tight flex items-center">
            <BarChart3 size={20} className="mr-2 text-sky-500" /> Export Analysis
          </h3>
        </div>
        <div className="p-4 md:p-6 space-y-4">
          <div className="space-y-2">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Select Format</label>
            <div className="grid grid-cols-2 gap-3">
              {['md', 'json', 'txt', 'pdf'].map(fmt => (
                <button
                  key={fmt}
                  onClick={() => setFormat(fmt)}
                  className={`p-3 rounded-lg border text-sm font-bold uppercase tracking-widest transition-all ${format === fmt
                    ? 'bg-sky-500/20 border-sky-500 text-sky-400'
                    : 'bg-slate-900 border-slate-800 text-slate-500 hover:border-slate-700'
                    }`}
                >
                  .{fmt}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-3 p-3 bg-slate-900/50 border border-slate-800 rounded-xl">
            <input
              type="checkbox"
              id="includeEvidence"
              checked={includeEvidence}
              onChange={(e) => setIncludeEvidence(e.target.checked)}
              className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-sky-500 focus:ring-sky-500/50"
            />
            <label htmlFor="includeEvidence" className="text-xs font-bold text-slate-300 cursor-pointer">Include evidence items in report</label>
          </div>

          <button
            onClick={onExport}
            className="w-full py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)] mt-4"
          >
            Download Report
          </button>
        </div>
      </div>
    </div>
  );
};