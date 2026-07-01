import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
          <div className="max-w-md w-full bg-[#020617] border border-red-500/20 rounded-2xl p-8 shadow-2xl text-center space-y-6">
            <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto text-red-500">
              <AlertCircle size={32} />
            </div>
            <div>
              <h2 className="text-xl font-black text-white uppercase tracking-tighter mb-2">System Failure</h2>
              <p className="text-sm text-slate-400 font-medium">
                The frontend node encountered a critical rendering exception.
              </p>
              {this.state.error && (
                <div className="mt-4 p-3 bg-red-500/5 border border-red-500/10 rounded-lg text-left overflow-hidden text-ellipsis whitespace-nowrap">
                  <code className="text-xs text-red-400 font-mono">
                    {this.state.error.message}
                  </code>
                </div>
              )}
            </div>
            <button
              onClick={() => window.location.reload()}
              className="w-full flex items-center justify-center space-x-2 py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)]"
            >
              <RefreshCw size={14} />
              <span>Recover Session</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
