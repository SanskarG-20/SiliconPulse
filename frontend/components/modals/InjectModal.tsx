import React from 'react';
import { X, Zap, CheckCircle2, RefreshCw } from 'lucide-react';

interface InjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => Promise<void>;
  title: string;
  setTitle: (v: string) => void;
  content: string;
  setContent: (v: string) => void;
  source: string;
  setSource: (v: string) => void;
  loading: boolean;
  success: boolean;
}

export const InjectModal: React.FC<InjectModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  title,
  setTitle,
  content,
  setContent,
  source,
  setSource,
  loading,
  success,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-[#020617] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>

        <div className="p-6 border-b border-slate-800/50">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-sky-500/10 rounded-lg text-sky-500">
              <Zap size={20} />
            </div>
            <h3 className="text-lg font-black text-white uppercase tracking-tight">Inject Signal</h3>
          </div>
        </div>

        {success ? (
          <div className="p-12 flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-16 h-16 bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-500 mb-2">
              <CheckCircle2 size={32} />
            </div>
            <h4 className="text-xl font-bold text-white">Signal Injected</h4>
            <p className="text-slate-400 text-sm">Data stream updated successfully.</p>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="p-6 space-y-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/50 outline-none transition-all"
                placeholder="e.g. TSMC Yield Report"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Source</label>
              <input
                type="text"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/50 outline-none transition-all"
                placeholder="e.g. ManualInject"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Content Payload</label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-3 text-sm text-white focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/50 outline-none transition-all h-32 resize-none"
                placeholder="Enter raw signal data..."
                required
              />
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Injecting...</span>
                  </>
                ) : (
                  <>
                    <Zap size={14} />
                    <span>Transmit Signal</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};