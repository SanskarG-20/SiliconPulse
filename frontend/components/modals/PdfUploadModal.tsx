import React, { useCallback, useState } from 'react';
import { X, Upload, FileText, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { uploadPdf, triggerSecIngest } from '../../api/siliconpulseApi';

interface PdfUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (msg: string) => void;
}

export const PdfUploadModal: React.FC<PdfUploadModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [secLoading, setSecLoading] = useState(false);

  const reset = useCallback(() => {
    setFile(null);
    setResult(null);
    setError(null);
    setLoading(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const validate = (f: File): string | null => {
    if (!f.name.toLowerCase().endsWith('.pdf')) return 'Only PDF files are accepted.';
    if (f.size > 10 * 1024 * 1024) return 'File too large (max 10 MB).';
    if (f.size === 0) return 'File is empty.';
    return null;
  };

  const handleFile = (f: File) => {
    const err = validate(f);
    if (err) {
      setError(err);
      setFile(null);
      return;
    }
    setError(null);
    setFile(f);
    setResult(null);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  const onUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await uploadPdf(file);
      setResult(res);
      onSuccess(`PDF processed: ${res.added ?? 0} new signals from ${res.extracted_events ?? 0} events`);
    } catch (e: any) {
      setError(e.message || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const onSec = async () => {
    setSecLoading(true);
    setError(null);
    try {
      const res = await triggerSecIngest(3);
      setResult(res);
      onSuccess(`SEC ingest: ${res.added ?? 0} new signals from ${res.fetched ?? 0} filings`);
    } catch (e: any) {
      setError(e.message || 'SEC ingest failed');
    } finally {
      setSecLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-white/80 dark:bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-slate-50 dark:bg-[#020617] border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative">
        <button onClick={handleClose} className="absolute top-4 right-4 text-slate-500 hover:text-slate-900 dark:hover:text-white">
          <X size={18} />
        </button>

        <div className="p-6 border-b border-slate-200/50 dark:border-slate-800/50">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-sky-500/10 rounded-lg text-sky-500">
              <Upload size={18} />
            </div>
            <div>
              <h3 className="text-sm font-black text-white uppercase tracking-widest">Ingest PDF / SEC</h3>
              <p className="text-[11px] text-slate-500">Earnings reports, 8-K filings → LLM extraction → live feed</p>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-4">
          {/* Drop zone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${dragOver ? 'border-sky-500 bg-sky-500/10' : 'border-slate-200 dark:border-slate-800 bg-slate-50/30 dark:bg-slate-900/30 hover:border-slate-300 dark:border-slate-700'}`}
          >
            <FileText size={28} className={`mx-auto mb-2 ${file ? 'text-emerald-400' : 'text-slate-600'}`} />
            {file ? (
              <div>
                <p className="text-sm font-bold text-slate-800 dark:text-slate-200">{file.name}</p>
                <p className="text-[11px] text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                <button onClick={() => setFile(null)} className="mt-2 text-[11px] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white underline">Remove</button>
              </div>
            ) : (
              <>
                <p className="text-sm font-bold text-slate-700 dark:text-slate-300">Drag & drop PDF here</p>
                <p className="text-[11px] text-slate-500">or</p>
                <label className="mt-2 inline-flex px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 rounded text-xs font-bold cursor-pointer">
                  Browse Files
                  <input type="file" accept=".pdf,application/pdf" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
                </label>
                <p className="text-[10px] text-slate-600 mt-2">Max 10 MB • PDF only</p>
              </>
            )}
          </div>

          {error && (
            <div className="flex items-start space-x-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-300 text-xs">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {result && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-xs text-emerald-300 space-y-1">
              <div className="flex items-center space-x-1 font-bold">
                <CheckCircle2 size={14} /> <span>{result.status === 'ok' ? 'Success' : result.status}</span>
              </div>
              <div className="text-emerald-200/80">
                {result.filename && <div>File: {result.filename}</div>}
                {result.text_len !== undefined && <div>Text: {result.text_len} chars</div>}
                {result.extracted_events !== undefined && <div>Extracted: {result.extracted_events} events</div>}
                {result.added !== undefined && <div>Added: {result.added} new signals</div>}
                {result.fetched !== undefined && <div>Fetched filings: {result.fetched}</div>}
                {result.message && <div className="text-slate-600 dark:text-slate-400">{result.message}</div>}
              </div>
            </div>
          )}

          <div className="flex space-x-2">
            <button
              onClick={onUpload}
              disabled={!file || loading}
              className="flex-1 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-xs font-black uppercase tracking-widest flex items-center justify-center space-x-2"
            >
              {loading ? <><RefreshCw size={14} className="animate-spin" /><span>Processing…</span></> : <><Upload size={14} /><span>Upload PDF</span></>}
            </button>
            <button
              onClick={onSec}
              disabled={secLoading}
              className="px-4 py-2.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:bg-slate-700 disabled:opacity-50 text-slate-800 dark:text-slate-200 rounded-lg text-xs font-bold flex items-center space-x-1"
            >
              {secLoading ? <RefreshCw size={12} className="animate-spin" /> : null}
              <span>Fetch 8-K (3d)</span>
            </button>
          </div>

          <p className="text-[10px] text-slate-600 text-center">PDF text → Gemini extraction (earnings, guidance, capex, yield) → dedup → vector index</p>
        </div>
      </div>
    </div>
  );
};
