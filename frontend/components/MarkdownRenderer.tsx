
import React from 'react';
import { Activity, ShieldAlert, Cpu, BarChart3, Globe } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  const lines = content.split('\n');
  
  return (
    <div className="space-y-6 text-slate-700 dark:text-slate-300 max-w-3xl mx-auto">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (trimmed === '') return <div key={idx} className="h-2"></div>;

        if (line.startsWith('≡ƒƒª')) {
          return (
            <div key={idx} className="border-b border-slate-200 dark:border-slate-800 pb-6 mb-8">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-black text-sky-500 uppercase tracking-widest">Strategic Intelligence Report</span>
                <span className="text-[10px] font-mono text-slate-600 uppercase">Classified / Internal Use</span>
              </div>
              <h2 className="text-3xl font-black text-white tracking-tight leading-none uppercase">
                {line.replace('≡ƒƒª ', '')}
              </h2>
            </div>
          );
        }

        if (line.startsWith('≡ƒô░') || line.startsWith('≡ƒöü') || line.startsWith('≡ƒºá') || line.startsWith('≡ƒÄ»') || line.startsWith('≡ƒö«') || line.startsWith('≡ƒôî') || line.startsWith('≡ƒº╛')) {
          const title = line.substring(3).trim();
          const Icon = line.startsWith('≡ƒô░') ? Globe : 
                     line.startsWith('≡ƒºá') ? Cpu :
                     line.startsWith('≡ƒöü') ? Activity :
                     line.startsWith('≡ƒÄ»') ? BarChart3 : ShieldAlert;

          return (
            <h3 key={idx} className="flex items-center text-xs font-black text-slate-500 uppercase tracking-[0.2em] mt-10 mb-4 pt-4 border-t border-slate-900">
              <Icon size={14} className="mr-2 text-sky-500" />
              {title}
            </h3>
          );
        }

        if (line.startsWith('≡ƒÜ¿')) {
          return (
            <div key={idx} className="bg-red-500/5 border border-red-500/20 p-5 rounded-xl my-6 flex items-start space-x-4">
               <ShieldAlert size={20} className="text-red-500 shrink-0 mt-0.5" />
               <div>
                  <span className="text-red-500 font-black text-[10px] uppercase tracking-widest block mb-1">Impact Alert</span>
                  <p className="text-red-100/90 text-sm font-medium leading-relaxed">{line.replace('≡ƒÜ¿ High Impact Alert:', '')}</p>
               </div>
            </div>
          );
        }

        if (line.startsWith('CEO Summary:')) {
          return (
            <div key={idx} className="bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl mt-12 relative overflow-hidden">
               <div className="absolute top-0 right-0 p-3 opacity-10">
                 <Cpu size={80} />
               </div>
               <span className="font-black text-[9px] uppercase tracking-[0.3em] text-sky-500 block mb-2">Executive Summary</span>
               <p className="text-lg font-bold text-slate-900 dark:text-slate-100 leading-snug relative z-10">
                 {line.replace('CEO Summary:', '').trim()}
               </p>
            </div>
          );
        }

        if (line.startsWith('Signal Strength:')) {
            const scoreMatch = line.match(/\d+/);
            const score = scoreMatch ? parseInt(scoreMatch[0]) : 0;
            return (
              <div key={idx} className="bg-slate-50/30 dark:bg-slate-900/30 p-4 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Signal Reliability</span>
                  <div className="h-1 w-32 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div 
                      className={`h-full transition-all duration-1000 ${score > 80 ? 'bg-emerald-500' : score > 50 ? 'bg-amber-500' : 'bg-red-500'}`} 
                      style={{ width: `${score}%` }}
                    ></div>
                  </div>
                </div>
                <span className="text-white font-black font-mono text-sm">{score}%</span>
              </div>
            )
        }

        if (trimmed.startsWith('-')) {
          return (
            <div key={idx} className="flex items-start space-x-3 mb-2 last:mb-0">
              <div className="w-1 h-1 rounded-full bg-sky-500 mt-2 shrink-0"></div>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
                {trimmed.replace('-', '').trim()}
              </p>
            </div>
          );
        }

        if (trimmed.startsWith('(A)') || trimmed.startsWith('(B)') || trimmed.startsWith('(C)')) {
          return (
            <div key={idx} className="ml-4 pl-4 border-l border-slate-200 dark:border-slate-800 py-1 mb-2">
               <span className="text-sky-500 font-bold mr-2 text-sm">{trimmed.substring(0, 3)}</span>
               <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{trimmed.substring(3).trim()}</span>
            </div>
          )
        }
        
        return <p key={idx} className="text-sm leading-relaxed text-slate-600 dark:text-slate-400 font-medium">{trimmed}</p>;
      })}
    </div>
  );
};
