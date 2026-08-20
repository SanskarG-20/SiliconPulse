import React from 'react';
import { X, Coffee, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface DigestModalProps {
  isOpen: boolean;
  onClose: () => void;
  loading: boolean;
  content: string | null;
}

export const DigestModal: React.FC<DigestModalProps> = ({
  isOpen,
  onClose,
  loading,
  content,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-[#020617] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>
        <div className="p-4 md:p-6 border-b border-slate-800/50">
          <h3 className="text-lg font-black text-white uppercase tracking-tight flex items-center">
            <Coffee size={20} className="mr-2 text-emerald-500" /> Morning Briefing
          </h3>
        </div>
        <div className="p-4 md:p-6 max-h-[70vh] overflow-y-auto custom-scrollbar">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <RefreshCw size={24} className="text-emerald-500 animate-spin" />
              <p className="text-slate-400 text-sm font-medium">Brewing your daily digest...</p>
            </div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none text-slate-300">
              <ReactMarkdown>{content || ''}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};