import React from 'react';
import { Zap, Activity, ShieldAlert, TrendingUp, Layers, FileText, CheckCircle2, AlertCircle } from 'lucide-react';

interface EvidenceItem {
    source: string;
    timestamp: string;
    title: string;
}

interface Section {
    id: string;
    title: string;
    points?: string[];
    evidence?: EvidenceItem[];
    value?: string;
    reason?: string;
    text?: string;
}

interface ReportData {
    sections: Section[];
}

interface StrategicInsightReportProps {
    data: string | ReportData;
}

export const StrategicInsightReport: React.FC<StrategicInsightReportProps> = ({ data }) => {
    let report: ReportData | null = null;

    // Parse data if it's a string
    if (typeof data === 'string') {
        try {
            // Clean up potential markdown code blocks if passed raw
            let cleanData = data.trim();
            // Remove markdown code blocks
            cleanData = cleanData.replace(/^```json\s*/, '').replace(/^```\s*/, '').replace(/\s*```$/, '');

            report = JSON.parse(cleanData);
        } catch (e) {
            console.error("Failed to parse insight JSON:", e);
            // Fallback for raw text (legacy or error)
            return (
                <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 text-slate-300 font-mono text-sm whitespace-pre-wrap">
                    {data}
                </div>
            );
        }
    } else {
        report = data;
    }

    if (!report || !Array.isArray(report.sections)) {
        return (
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 text-slate-400 text-center">
                Insufficient data to render report.
            </div>
        );
    }

    const getIconForSection = (id: string) => {
        switch (id) {
            case 'evidence': return <Activity size={18} className="text-sky-400" />;
            case 'change': return <TrendingUp size={18} className="text-emerald-400" />;
            case 'impact': return <Zap size={18} className="text-amber-400" />;
            case 'competitors': return <ShieldAlert size={18} className="text-red-400" />;
            case 'outlook': return <Layers size={18} className="text-indigo-400" />;
            case 'confidence': return <CheckCircle2 size={18} className="text-teal-400" />;
            case 'ceo': return <FileText size={18} className="text-slate-200" />;
            default: return <FileText size={18} className="text-slate-400" />;
        }
    };

    return (
        <div className="space-y-4 md:space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {report.sections.map((section, idx) => (
                <div key={idx} className="glass p-4 md:p-6 rounded-2xl border-slate-800/60 hover:border-sky-500/20 transition-all group">
                    <div className="flex items-center space-x-3 mb-4">
                        <div className="p-2 bg-slate-900 rounded-lg group-hover:bg-slate-800 transition-colors">
                            {getIconForSection(section.id)}
                        </div>
                        <h3 className="text-xs md:text-sm font-black text-slate-200 uppercase tracking-widest group-hover:text-white transition-colors">
                            {section.title}
                        </h3>
                    </div>

                    <div className="pl-0 md:pl-11">
                        {/* Points List */}
                        {Array.isArray(section.points) && (
                            <ul className="space-y-2 md:space-y-3 mb-4">
                                {section.points.map((point, pIdx) => (
                                    <li key={pIdx} className="text-xs md:text-sm text-slate-400 leading-relaxed flex items-start">
                                        <span className="mr-3 mt-1.5 w-1.5 h-1.5 bg-slate-700 rounded-full shrink-0 group-hover:bg-sky-500/50 transition-colors"></span>
                                        <span>{point}</span>
                                    </li>
                                ))}
                            </ul>
                        )}

                        {/* Evidence Chips */}
                        {Array.isArray(section.evidence) && section.evidence.length > 0 && (
                            <div className="flex flex-wrap gap-2 mt-3">
                                {section.evidence.map((ev, eIdx) => (
                                    <div key={eIdx} className="flex items-center space-x-2 px-2 md:px-3 py-1 md:py-1.5 bg-slate-900/80 border border-slate-800 rounded-lg text-[9px] md:text-[10px] uppercase tracking-wide text-slate-400 hover:border-sky-500/30 hover:text-sky-400 transition-colors cursor-default max-w-full overflow-hidden">
                                        <span className="font-black text-slate-500 shrink-0">{ev.source}</span>
                                        <span className="w-0.5 h-3 bg-slate-800 shrink-0"></span>
                                        <span className="truncate">{ev.title}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Confidence Meter */}
                        {section.id === 'confidence' && (
                            <div className="mt-2">
                                <div className="flex flex-col md:flex-row md:items-center space-y-2 md:space-y-0 md:space-x-4 mb-2">
                                    <div className={`inline-block px-3 py-1 rounded-md text-[10px] md:text-xs font-black uppercase tracking-widest ${(section.value || '').toLowerCase() === 'high' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' :
                                        (section.value || '').toLowerCase() === 'medium' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' :
                                            'bg-red-500/10 text-red-500 border border-red-500/20'
                                        }`}>
                                        {section.value} Confidence
                                    </div>
                                    {section.reason && <p className="text-[10px] md:text-xs text-slate-500 italic">{section.reason}</p>}
                                </div>

                                {/* Dynamic Score Bar (if available) */}
                                {section.id === 'confidence' && (
                                    <div className="w-full max-w-xs h-1 bg-slate-800 rounded-full overflow-hidden mt-3">
                                        <div
                                            className={`h-full transition-all duration-1000 ${(section.value || '').toLowerCase() === 'high' ? 'bg-emerald-500' :
                                                (section.value || '').toLowerCase() === 'medium' ? 'bg-amber-500' :
                                                    'bg-red-500'
                                                }`}
                                            style={{ width: `${(section.value || '').toLowerCase() === 'high' ? 85 : (section.value || '').toLowerCase() === 'medium' ? 55 : 25}%` }}
                                        ></div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* CEO Summary Text */}
                        {section.text && (
                            <p className="text-xs md:text-sm font-medium text-slate-300 leading-relaxed border-l-2 border-sky-500/50 pl-4 italic">
                                "{section.text}"
                            </p>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
};
