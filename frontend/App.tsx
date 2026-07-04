import React, { useState, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { SignedIn, SignedOut, SignIn, SignUp, useAuth, UserButton } from '@clerk/clerk-react';
import {
  Search, Zap, Activity, Cpu, ShieldAlert,
  TrendingUp, Layers, FileText, CheckCircle2,
  AlertCircle, RefreshCw, Terminal, Clock,
  ExternalLink, BarChart3, HelpCircle, X,
  ArrowRight,
  Home,
  Menu
} from 'lucide-react';
import { LiveTicker } from './components/LiveTicker';
import { CompanyRadar } from './components/CompanyRadar';
import { MarkdownRenderer } from './components/MarkdownRenderer';
import { StrategicInsightReport } from './components/StrategicInsightReport';
import { BackgroundLayer } from './components/BackgroundLayer';
import { SourceBadge } from './components/SourceBadge';
import { querySiliconPulse, injectSignal, fetchSignals, QueryResponse, formatEvidenceToContext, generateInsight, bootstrapSystem, fetchRecommendations, exportAnalysis, verifySources, setAuthTokenGetter, syncAuthenticatedUser } from './api/siliconpulseApi';
import { INITIAL_LIVE_FEED } from './constants';
import { LiveEvent } from './types';
import { buildLiveFeed, createLiveEvent, getRelativeTimeLabel, rotateFeed } from './utils/feedUtils';
import { resolveTrustLevel } from './utils/sourceMapping';
import { generateRecommendationsFromFeed } from './utils/recommendationUtils';

const Dashboard: React.FC = () => {
  const { getToken } = useAuth();
  const [liveFeed, setLiveFeed] = useState<LiveEvent[]>(INITIAL_LIVE_FEED);
  const [query, setQuery] = useState('');
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [insight, setInsight] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState(new Date().toLocaleTimeString());
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [lastSubmittedQuery, setLastSubmittedQuery] = useState('');
  const [feedFilter, setFeedFilter] = useState<string>('');
  const [sourceTrustFilter, setSourceTrustFilter] = useState<'All' | 'High' | 'Medium' | 'Low'>('All');
  const [watchlist, setWatchlist] = useState<string[]>(() => {
    const saved = localStorage.getItem('siliconpulse_watchlist');
    return saved ? JSON.parse(saved) : [];
  });

  // Injection Modal State
  const [showInjectModal, setShowInjectModal] = useState(false);
  const [injectTitle, setInjectTitle] = useState('');
  const [injectContent, setInjectContent] = useState('');
  const [injectSource, setInjectSource] = useState('ManualInject');
  const [injectLoading, setInjectLoading] = useState(false);
  const [injectSuccess, setInjectSuccess] = useState(false);

  // Export & Verify State
  const [showExportModal, setShowExportModal] = useState(false);
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [exportFormat, setExportFormat] = useState('md');
  const [includeEvidence, setIncludeEvidence] = useState(true);
  const [verifiedSources, setVerifiedSources] = useState<any[]>([]);
  const [verifying, setVerifying] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const feedRotationRef = useRef(0);
  const recommendationKeysRef = useRef<Set<string>>(new Set());
  const remoteRecommendationsRef = useRef<any[]>([]);
  const seenSignalIdsRef = useRef<Set<string>>(new Set());
  const initialFeedLoadedRef = useRef<boolean>(false);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 3500);
  };

  useEffect(() => {
    setAuthTokenGetter(() => getToken());

    return () => {
      setAuthTokenGetter(null);
    };
  }, [getToken]);

  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  useEffect(() => {
    if (!initialFeedLoadedRef.current) {
      if (liveFeed.length > 0 && liveFeed !== INITIAL_LIVE_FEED) {
        liveFeed.forEach(ev => seenSignalIdsRef.current.add(ev.id));
        initialFeedLoadedRef.current = true;
      }
      return;
    }

    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    if (watchlist.length === 0) return;

    liveFeed.forEach(event => {
      if (!seenSignalIdsRef.current.has(event.id)) {
        seenSignalIdsRef.current.add(event.id);
        
        if (watchlist.includes(event.company) && event.impactScore > 75) {
          new Notification(`SiliconPulse Alert: ${event.company}`, {
            body: event.title,
          });
        }
      }
    });
  }, [liveFeed, watchlist]);

  useEffect(() => {
    const init = async () => {
      try {
        await syncAuthenticatedUser();
      } catch (err) {
        console.error('Authenticated user sync failed:', err);
      }

      // 1. Bootstrap System (Generate Fresh News)
      await bootstrapSystem();

      // 2. Refresh Signals
      refreshSignals();

      // 3. Fetch Recommendations
      fetchRecommendations().then(recs => {
        if (recs && recs.length > 0) {
          remoteRecommendationsRef.current = recs;
        }
        const fallbackFeed = liveFeed.length > 0 ? liveFeed : INITIAL_LIVE_FEED;
        const result = generateRecommendationsFromFeed(
          fallbackFeed,
          recommendationKeysRef.current,
          remoteRecommendationsRef.current
        );
        recommendationKeysRef.current = result.nextKeys;
        setRecommendations(result.recommendations);
      });
    };

    init();

    // Auto-refresh signals every 5 seconds
    const interval = setInterval(refreshSignals, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [queryResult]);

  const refreshSignals = async () => {
    try {
      const signals = await fetchSignals();
      if (signals && signals.length > 0) {
        const mappedSignals: LiveEvent[] = signals.map((s: any, idx: number) => createLiveEvent(s, idx));
        const ordered = buildLiveFeed(mappedSignals, 10);

        if (ordered.length === 0) {
          setLiveFeed(INITIAL_LIVE_FEED);
          return;
        }

        feedRotationRef.current = (feedRotationRef.current + 1) % ordered.length;
        const rotated = rotateFeed(ordered, feedRotationRef.current);
        setLiveFeed(rotated);
        const recommendationsResult = generateRecommendationsFromFeed(
          ordered,
          recommendationKeysRef.current,
          remoteRecommendationsRef.current
        );
        recommendationKeysRef.current = recommendationsResult.nextKeys;
        setRecommendations(recommendationsResult.recommendations);
        return;
      }

      setLiveFeed(INITIAL_LIVE_FEED);
      const fallbackResult = generateRecommendationsFromFeed(
        INITIAL_LIVE_FEED,
        recommendationKeysRef.current,
        remoteRecommendationsRef.current
      );
      recommendationKeysRef.current = fallbackResult.nextKeys;
      setRecommendations(fallbackResult.recommendations);
    } catch (err) {
      console.error("Failed to refresh signals:", err);
      notify("Live feed refresh failed. Showing cached signals.");
    }
  };

  const handleSubmit = async (e: React.FormEvent | string) => {
    const finalQuery = typeof e === 'string' ? e : query;
    if (typeof e !== 'string') e.preventDefault();
    if (!finalQuery.trim() || loading) return;

    setLoading(true);
    setError(null);
    setQueryResult(null);
    setInsight(null);
    setLastSubmittedQuery(finalQuery.trim());
    window.history.replaceState(null, '', `#q=${encodeURIComponent(finalQuery.trim())}`);

    try {
      // 1. Get Evidence FIRST - show immediately
      const result = await querySiliconPulse(finalQuery.trim());
      setQueryResult(result);
      setLoading(false); // Stop loading spinner immediately after evidence is shown

      // 2. Generate Insight ASYNCHRONOUSLY in background
      // NEW RULE: Always request insight, backend handles zero-evidence fallbacks
      const context = formatEvidenceToContext(result.evidence ?? []);
      generateInsight(finalQuery.trim(), context)
        .then(generatedInsight => {
          setInsight(generatedInsight);
        })
        .catch(err => {
          console.error("Insight generation failed:", err);
          setInsight("Insight generation unavailable. Evidence displayed above.");
        });

      setQuery('');
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (err: any) {
      setError(err.message || 'Intelligence failure. Connection to core reasoning lost.');
      setLoading(false);
    }
  };

  const handleCompanyClick = (company: string) => {
    setFeedFilter(company);
    const newQuery = `Recent activity and strategic impact of ${company}`;
    setQuery(newQuery);
    handleSubmit(newQuery);
    setShowMobileMenu(false);
  };

  useEffect(() => {
    const hash = window.location.hash;
    if (hash.startsWith('#q=')) {
      const q = decodeURIComponent(hash.substring(3));
      if (q) {
        setQuery(q);
        // Delay to allow initial feed data to load if needed
        setTimeout(() => handleSubmit(q), 500);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleWatchlist = (company: string, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
    }
    setWatchlist(prev => {
      const next = prev.includes(company) ? prev.filter(c => c !== company) : [...prev, company];
      localStorage.setItem('siliconpulse_watchlist', JSON.stringify(next));
      return next;
    });
  };

  const handleInjectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!injectTitle.trim() || !injectContent.trim()) return;

    setInjectLoading(true);
    try {
      await injectSignal(injectTitle, injectContent, injectSource);
      setInjectSuccess(true);
      setInjectTitle('');
      setInjectContent('');
      setInjectSource('ManualInject');

      // Refresh signals and close modal after short delay
      await refreshSignals();
      notify("Signal injected and feed refreshed.");
      setTimeout(() => {
        setInjectSuccess(false);
        setShowInjectModal(false);
      }, 1500);

      setLastUpdate(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("Injection failed:", err);
      notify("Signal injection failed. Please retry.");
    } finally {
      setInjectLoading(false);
    }
  };

  const handleExport = async () => {
    if (!queryResult || !insight) return;
    try {
      await exportAnalysis(
        queryResult.query,
        insight,
        evidenceItems,
        exportFormat,
        includeEvidence
      );
      setShowExportModal(false);
      notify("Analysis exported.");
    } catch (err) {
      console.error("Export failed:", err);
      notify("Export failed. Please retry.");
    }
  };

  const handleVerify = async () => {
    if (!queryResult) return;
    setVerifying(true);
    setShowVerifyModal(true);
    try {
      const data = await verifySources(queryResult.query);
      setVerifiedSources(Array.isArray(data?.sources) ? data.sources : []);
    } catch (err) {
      console.error("Verification failed:", err);
      setVerifiedSources([]);
      notify("Source verification failed. Please retry.");
    } finally {
      setVerifying(false);
    }
  };

  const resetDashboard = () => {
    setQuery('');
    setQueryResult(null);
    setInsight(null);
    setError(null);
    setLoading(false);
    setLastSubmittedQuery('');
    setFeedFilter('');
    window.history.replaceState(null, '', window.location.pathname);
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const retryInsight = () => {
    if (!queryResult) return;
    setInsight(null);
    const context = formatEvidenceToContext(queryResult.evidence ?? []);
    generateInsight(queryResult.query, context)
      .then(generatedInsight => {
        setInsight(generatedInsight);
      })
      .catch(() => {
        setInsight("Insight generation unavailable. Please try again later.");
      });
  };

  const evidenceItems = Array.isArray(queryResult?.evidence) ? queryResult.evidence : [];
  const filteredEvidenceItems = evidenceItems.filter((item: any) => {
    if (sourceTrustFilter === 'All') return true;
    const tl = resolveTrustLevel(item.source, item.trust_level);
    return tl === sourceTrustFilter;
  });
  const isInsightUnavailable = typeof insight === 'string' && insight.toLowerCase().includes('unavailable');

  const filteredFeed = feedFilter 
    ? liveFeed.filter(f => 
        (f.company || '').toLowerCase().includes(feedFilter.toLowerCase()) || 
        (f.title || '').toLowerCase().includes(feedFilter.toLowerCase()) ||
        (f.event_type || '').toLowerCase().includes(feedFilter.toLowerCase())
      ) 
    : liveFeed;

  return (
    <div className="flex flex-col h-screen overflow-hidden text-slate-200 relative">
      <BackgroundLayer />
      {toast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[120] px-4 py-2 rounded-lg border border-sky-500/30 bg-slate-950/95 text-sky-100 text-xs font-bold uppercase tracking-widest shadow-2xl">
          {toast}
        </div>
      )}
      {/* INJECTION MODAL */}
      {showInjectModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-lg bg-[#020617] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative">
            <button
              onClick={() => setShowInjectModal(false)}
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

            {injectSuccess ? (
              <div className="p-12 flex flex-col items-center justify-center text-center space-y-4">
                <div className="w-16 h-16 bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-500 mb-2">
                  <CheckCircle2 size={32} />
                </div>
                <h4 className="text-xl font-bold text-white">Signal Injected</h4>
                <p className="text-slate-400 text-sm">Data stream updated successfully.</p>
              </div>
            ) : (
              <form onSubmit={handleInjectSubmit} className="p-6 space-y-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Title</label>
                  <input
                    type="text"
                    value={injectTitle}
                    onChange={(e) => setInjectTitle(e.target.value)}
                    className="w-full bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/50 outline-none transition-all"
                    placeholder="e.g. TSMC Yield Report"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Source</label>
                  <input
                    type="text"
                    value={injectSource}
                    onChange={(e) => setInjectSource(e.target.value)}
                    className="w-full bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/50 outline-none transition-all"
                    placeholder="e.g. ManualInject"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Content Payload</label>
                  <textarea
                    value={injectContent}
                    onChange={(e) => setInjectContent(e.target.value)}
                    className="w-full bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-3 text-sm text-white focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/50 outline-none transition-all h-32 resize-none"
                    placeholder="Enter raw signal data..."
                    required
                  />
                </div>

                <div className="pt-4">
                  <button
                    type="submit"
                    disabled={injectLoading}
                    className="w-full py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                  >
                    {injectLoading ? (
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
      )}

      {/* EXPORT MODAL */}
      {showExportModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-md bg-[#020617] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative">
            <button onClick={() => setShowExportModal(false)} className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors"><X size={20} /></button>
            <div className="p-6 border-b border-slate-800/50">
              <h3 className="text-lg font-black text-white uppercase tracking-tight flex items-center">
                <BarChart3 size={20} className="mr-2 text-sky-500" /> Export Analysis
              </h3>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-2">
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Select Format</label>
                <div className="grid grid-cols-2 gap-3">
                  {['md', 'json', 'txt', 'pdf'].map(fmt => (
                    <button
                      key={fmt}
                      onClick={() => setExportFormat(fmt)}
                      className={`p-3 rounded-lg border text-sm font-bold uppercase tracking-widest transition-all ${exportFormat === fmt
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
                onClick={handleExport}
                className="w-full py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)] mt-4"
              >
                Download Report
              </button>
            </div>
          </div>
        </div>
      )}

      {/* VERIFY SOURCES MODAL */}
      {showVerifyModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-2xl bg-[#020617] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden relative flex flex-col max-h-[80vh]">
            <button onClick={() => setShowVerifyModal(false)} className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors"><X size={20} /></button>
            <div className="p-6 border-b border-slate-800/50 shrink-0">
              <h3 className="text-lg font-black text-white uppercase tracking-tight flex items-center">
                <HelpCircle size={20} className="mr-2 text-emerald-500" /> Source Verification
              </h3>
            </div>
            <div className="p-6 overflow-y-auto custom-scrollbar">
              {verifying ? (
                <div className="flex flex-col items-center justify-center py-12 space-y-4">
                  <RefreshCw size={32} className="animate-spin text-emerald-500" />
                  <span className="text-sm font-mono text-slate-400 uppercase tracking-widest">Verifying Source Integrity...</span>
                </div>
              ) : (
                <div className="space-y-3">
                  {verifiedSources.length === 0 ? (
                    <div className="text-center py-12">
                      <p className="text-slate-500 text-sm italic">No sources found for this query.</p>
                    </div>
                  ) : (
                    verifiedSources.map((src, idx) => {
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
      )}
      {/* MOBILE DRAWER */}
      {showMobileMenu && (
        <div className="fixed inset-0 z-[110] lg:hidden animate-in fade-in duration-200">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-md" onClick={() => setShowMobileMenu(false)}></div>
          <div className="absolute inset-y-0 left-0 w-80 bg-[#020617] border-r border-slate-800 p-6 space-y-8 animate-in slide-in-from-left duration-300">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-[10px] font-black text-sky-500 uppercase tracking-[0.2em]">Command Center</h3>
              <button onClick={() => setShowMobileMenu(false)} className="text-slate-500 hover:text-white">
                <X size={20} />
              </button>
            </div>

            <CompanyRadar 
              onCompanyClick={handleCompanyClick} 
              watchlist={watchlist} 
              onToggleWatchlist={toggleWatchlist} 
            />

            <div className="space-y-4">
              <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] flex items-center">
                <Zap size={14} className="mr-2 text-amber-500" />
                High Priority Signals
              </h3>
              <div className="space-y-3">
                {filteredFeed.filter(f => f.impactScore > 80).slice(0, 3).map(ev => (
                  <div key={ev.id} className="glass p-3 rounded-xl border-slate-800/50 hover:border-sky-500/30 transition-all cursor-pointer group">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[9px] font-mono text-sky-500">{getRelativeTimeLabel(ev.timestamp)}</span>
                      <span className="px-1.5 py-0.5 rounded-[4px] bg-red-500/10 text-red-500 text-[8px] font-black uppercase tracking-tighter border border-red-500/20">Critical</span>
                    </div>
                    <h4 title={ev.title} className="text-xs font-bold text-slate-100 group-hover:text-sky-400 leading-tight transition-colors mb-1 truncate">{ev.title}</h4>
                    <div className="flex items-center text-[9px] text-slate-500 font-bold uppercase tracking-widest">
                      <span>{ev.company}</span>
                      <span className="mx-1.5 opacity-20">|</span>
                      <span>{ev.impactScore} IMPACT</span>
                      <button 
                        onClick={(e) => { e.stopPropagation(); toggleWatchlist(ev.company); }}
                        className={`ml-auto ${watchlist.includes(ev.company) ? 'text-sky-400' : 'text-slate-600 hover:text-sky-400'}`}
                        title={watchlist.includes(ev.company) ? "Remove from Watchlist" : "Add to Watchlist"}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill={watchlist.includes(ev.company) ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* HEADER SECTION */}
      <header className="h-14 border-b border-slate-800/60 flex items-center justify-between px-4 md:px-6 bg-slate-950/40 backdrop-blur-xl z-50">
        <div className="flex items-center space-x-3 md:space-x-4">
          <button
            onClick={() => setShowMobileMenu(true)}
            className="lg:hidden p-2 -ml-2 text-slate-400 hover:text-white transition-colors"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-sky-600 rounded flex items-center justify-center shadow-[0_0_15px_rgba(2,132,199,0.3)]">
              <Cpu size={18} className="text-white" />
            </div>
            <div className="leading-tight">
              <h1 className="text-sm font-black tracking-tighter uppercase text-white flex items-center">
                Silicon<span className="text-sky-500">Pulse</span>
                <span className="ml-2 px-1 py-0.5 bg-sky-500/10 text-sky-500 border border-sky-500/20 rounded-[4px] text-[8px] tracking-[0.1em] hidden sm:inline-block">OS_v4</span>
              </h1>
            </div>
          </div>
          <div className="h-4 w-[1px] bg-slate-800 hidden md:block"></div>
          <div className="hidden md:flex items-center space-x-4">
            <div className="flex items-center space-x-1.5 group cursor-help">
              <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></div>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest group-hover:text-emerald-400 transition-colors">Nodes_Online</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Activity size={12} className="text-sky-500" />
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Latency: 12ms</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 md:space-x-3">
          <div className="relative hidden lg:block mr-2">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Filter live feed..."
              value={feedFilter}
              onChange={(e) => setFeedFilter(e.target.value)}
              className="pl-7 pr-6 py-1.5 bg-slate-900 border border-slate-800 rounded-md text-[10px] text-slate-300 focus:outline-none focus:border-sky-500/50 w-32 focus:w-48 transition-all"
            />
            {feedFilter && (
              <button onClick={() => setFeedFilter('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                <X size={10} />
              </button>
            )}
          </div>
          <Link
            to="/"
            className="flex items-center space-x-2 px-2 md:px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-slate-300 border border-slate-800 transition-all active:scale-95"
          >
            <Home size={12} />
            <span className="hidden sm:inline">Home</span>
          </Link>
          <button
            onClick={resetDashboard}
            className="flex items-center space-x-2 px-2 md:px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-slate-300 border border-slate-800 transition-all active:scale-95"
          >
            <RefreshCw size={12} />
            <span className="hidden sm:inline">Reset</span>
          </button>
          <button
            onClick={() => setShowInjectModal(true)}
            className="flex items-center space-x-2 px-2 md:px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-sky-400 border border-slate-800 transition-all active:scale-95"
          >
            <Zap size={12} />
            <span className="hidden sm:inline">Inject_Signal</span>
            <span className="sm:hidden">Inject</span>
          </button>
        </div>
      </header>

      {/* LIVE SIGNALS ZONE */}
      <LiveTicker events={filteredFeed} />

      {/* CORE LAYOUT GRID */}
      <main className="flex-1 flex overflow-hidden">

        {/* RADAR ZONE (SIDEBAR) */}
        <aside className="w-80 border-r border-slate-800/40 bg-slate-950/20 p-6 space-y-8 hidden lg:block overflow-y-auto custom-scrollbar">
          <CompanyRadar 
            onCompanyClick={handleCompanyClick} 
            watchlist={watchlist} 
            onToggleWatchlist={toggleWatchlist} 
          />

          <div className="space-y-4">
            <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] flex items-center">
              <Zap size={14} className="mr-2 text-amber-500" />
              High Priority Signals
            </h3>
            <div className="space-y-3">
              {filteredFeed.filter(f => f.impactScore > 80).slice(0, 3).map(ev => (
                <div key={ev.id} className="glass p-3 rounded-xl border-slate-800/50 hover:border-sky-500/30 transition-all cursor-pointer group">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[9px] font-mono text-sky-500">{getRelativeTimeLabel(ev.timestamp)}</span>
                    <span className="px-1.5 py-0.5 rounded-[4px] bg-red-500/10 text-red-500 text-[8px] font-black uppercase tracking-tighter border border-red-500/20">Critical</span>
                  </div>
                  <h4 title={ev.title} className="text-xs font-bold text-slate-100 group-hover:text-sky-400 leading-tight transition-colors mb-1 truncate">{ev.title}</h4>
                  <div className="flex items-center text-[9px] text-slate-500 font-bold uppercase tracking-widest">
                    <span>{ev.company}</span>
                    <span className="mx-1.5 opacity-20">|</span>
                    <span>{ev.impactScore} IMPACT</span>
                    <button 
                      onClick={(e) => { e.stopPropagation(); toggleWatchlist(ev.company); }}
                      className={`ml-auto ${watchlist.includes(ev.company) ? 'text-sky-400' : 'text-slate-600 hover:text-sky-400'}`}
                      title={watchlist.includes(ev.company) ? "Remove from Watchlist" : "Add to Watchlist"}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill={watchlist.includes(ev.company) ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-sky-500/5 border border-sky-500/10">
            <div className="flex items-center space-x-2 mb-3">
              <div className="p-1.5 bg-sky-500/20 rounded-lg">
                <ShieldAlert size={14} className="text-sky-500" />
              </div>
              <span className="text-[10px] font-black text-sky-500 uppercase tracking-widest">Analyst Advisory</span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium italic leading-relaxed">
              "Focus on TSMC N2 yield milestones. Early reports suggest Apple/NVIDIA bidding war for initial capacity. Cross-ref with GlobalFoundries delays."
            </p>
          </div>
        </aside>

        {/* QUERY & REPORT ZONE */}
        <section className="flex-1 flex flex-col bg-transparent relative overflow-hidden">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-10 custom-scrollbar">

            {/* INITIAL / IDLE STATE (QUICK QUERIES) */}
            {!queryResult && !loading && !error && (
              <div className="h-full flex flex-col justify-center max-w-4xl mx-auto space-y-8 md:space-y-12">
                <div className="space-y-4">
                  <div className="inline-flex items-center space-x-2 px-3 py-1 bg-sky-500/10 border border-sky-500/20 rounded-full text-sky-500 text-[10px] font-black uppercase tracking-widest animate-pulse">
                    <Layers size={12} />
                    <span>Ready for Intelligence Generation</span>
                  </div>
                  <h2 className="text-3xl md:text-5xl font-black text-white tracking-tighter uppercase leading-none">
                    Strategic <br /> Intelligence <span className="text-sky-500">Node</span>
                  </h2>
                  <p className="text-slate-500 text-base md:text-lg font-medium max-w-xl">
                    Monitor live supply chain signals, yield reports, and geopolitical shifts. Select a directive or enter a custom query.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
                  {(Array.isArray(recommendations) && recommendations.length > 0 ? recommendations : [
                    { label: "NVIDIA-TSMC Pipeline", query: "Any new NVIDIA-TSMC contract today?", icon: Zap, color: "text-amber-400" },
                    { label: "Foundry Design Wins", query: "Status of Intel 18A design wins and foundry clients?", icon: CheckCircle2, color: "text-emerald-400" },
                    { label: "AI Infra Analysis", query: "What is the impact of Meta's new AI infra updates?", icon: Cpu, color: "text-sky-400" },
                    { label: "High Impact Summary", "query": "What are the top 3 high-impact events in last 2 hours?", icon: AlertCircle, color: "text-red-400" }
                  ]).map((item: any, idx: number) => {
                    // Map string icon names to components if needed, or use defaults
                    const IconComponent = typeof item.icon === 'string'
                      ? (item.icon === 'Activity' ? Activity :
                        item.icon === 'Cpu' ? Cpu :
                          item.icon === 'Globe' ? ExternalLink :
                            item.icon === 'TrendingUp' ? TrendingUp :
                              item.icon === 'Zap' ? Zap :
                                item.icon === 'ShieldAlert' ? ShieldAlert :
                                  item.icon === 'CheckCircle2' ? CheckCircle2 :
                                    item.icon === 'AlertCircle' ? AlertCircle : Search)
                      : (item.icon || Search);

                    return (
                      <button
                        key={`${item.label}-${idx}`}
                        onClick={() => handleSubmit(item.query)}
                        className="glass glass-hover p-4 md:p-5 text-left rounded-2xl transition-all flex items-start space-x-4 group"
                      >
                        <div className={`p-2 md:p-3 bg-slate-900 rounded-xl group-hover:bg-slate-800 transition-colors ${item.color}`}>
                          <IconComponent size={18} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="text-[10px] font-black uppercase tracking-[0.1em] text-slate-500 mb-1 block group-hover:text-slate-300 transition-colors">{item.label}</span>
                          <p className="text-xs md:text-sm font-medium text-slate-300 group-hover:text-white leading-tight truncate">{item.query}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ERROR STATE */}
            {error && (
              <div className="h-full flex flex-col items-center justify-center max-w-3xl mx-auto space-y-8 px-8">
                <div className="p-8 rounded-2xl bg-red-500/5 border border-red-500/20 w-full">
                  <div className="flex items-start space-x-4">
                    <AlertCircle size={32} className="text-red-500 shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <h3 className="text-xl font-black text-red-500 uppercase tracking-tight mb-2">Intelligence Synthesis Failed</h3>
                      <p className="text-slate-300 font-medium mb-4">{error}</p>

                      {error.includes("Backend offline") ? (
                        <button
                          onClick={async () => {
                            setError(null);
                            setLoading(true);
                            // Import dynamically to avoid circular dependency issues if any
                            const { checkBackendHealth } = await import('./api/siliconpulseApi');
                            const isOnline = await checkBackendHealth();
                            if (isOnline) {
                              setLoading(false);
                              // Retry the query if it was a query failure
                              if (lastSubmittedQuery) handleSubmit(lastSubmittedQuery);
                            } else {
                              setLoading(false);
                              setError("Backend still offline. Please ensure server is running on port 8000.");
                            }
                          }}
                          className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-xs font-black uppercase tracking-widest transition-all border border-red-500/30 flex items-center space-x-2"
                        >
                          <RefreshCw size={12} />
                          <span>Check Connection & Retry</span>
                        </button>
                      ) : (
                        <button
                          onClick={() => setError(null)}
                          className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg text-xs font-black uppercase tracking-widest transition-all border border-red-500/30"
                        >
                          Dismiss
                        </button>
                      )}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setError(null)}
                  className="flex items-center space-x-2 px-6 py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)]"
                >
                  <RefreshCw size={14} />
                  <span>Return to Dashboard</span>
                </button>
              </div>
            )}

            {/* LOADING STATE */}
            {loading && (
              <div className="h-full flex flex-col items-center justify-center space-y-6">
                <div className="relative">
                  <div className="w-20 h-20 border-[3px] border-sky-500/10 border-t-sky-500 rounded-full animate-spin"></div>
                  <Activity className="absolute inset-0 m-auto text-sky-500 animate-pulse" size={32} />
                </div>
                <div className="text-center space-y-2">
                  <h3 className="text-sky-500 font-black text-xs uppercase tracking-[0.4em] animate-pulse">Synthesizing Signals</h3>
                  <p className="text-slate-500 text-[11px] font-mono tracking-widest uppercase">Cross-referencing global supply chain nodes...</p>
                </div>
              </div>
            )}

            {/* REPORT VIEW */}
            {queryResult && (
              <div className="pb-24 pt-4 animate-in fade-in slide-in-from-bottom-8 duration-700 ease-out">
                <div className="flex items-center justify-between mb-8">
                  <div>
                    <h2 className="text-2xl font-black text-white uppercase tracking-tight mb-2">Intelligence Report</h2>
                    <p className="text-slate-500 font-mono text-xs uppercase tracking-widest">Query: "{queryResult.query}"</p>
                  </div>
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Signal Strength</div>
                      <div className="text-xl font-black text-sky-500">{queryResult.signal_strength}%</div>
                    </div>
                    <div className="w-12 h-12 rounded-full border-4 border-slate-800 flex items-center justify-center relative">
                      <svg className="absolute inset-0 transform -rotate-90 w-full h-full">
                        <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="4" fill="transparent" className="text-slate-800" />
                        <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="4" fill="transparent" className="text-sky-500" strokeDasharray={`${queryResult.signal_strength * 1.13} 113`} />
                      </svg>
                      <Activity size={16} className="text-sky-500" />
                    </div>
                  </div>
                </div>

                {/* INSIGHT SECTION */}
                {queryResult && (
                  <div className="mb-8 p-6 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="flex items-center space-x-2 mb-4">
                      <div className="p-1.5 bg-indigo-500/20 rounded-lg">
                        <Zap size={18} className="text-indigo-400" />
                      </div>
                      <h3 className="text-sm font-black text-indigo-400 uppercase tracking-widest">Strategic Insight</h3>
                    </div>
                    {insight ? (
                      <div className="max-w-none space-y-3">
                        <StrategicInsightReport data={insight} />
                        {isInsightUnavailable && (
                          <button
                            onClick={retryInsight}
                            className="inline-flex items-center space-x-2 px-3 py-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 rounded-md text-[10px] font-black uppercase tracking-widest border border-indigo-500/30 transition-all"
                          >
                            <RefreshCw size={12} />
                            <span>Try Again</span>
                          </button>
                        )}
                      </div>
                    ) : (
                      <div className="flex items-center space-x-3 text-slate-400">
                        <RefreshCw size={16} className="animate-spin" />
                        <span className="text-sm font-medium">Generating strategic insight...</span>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center">
                    <FileText size={14} className="mr-2 text-sky-500" /> Evidence Base
                  </h3>
                  <div className="flex space-x-1.5 md:space-x-2 overflow-x-auto no-scrollbar pb-1">
                    {['All', 'High', 'Medium', 'Low'].map(level => (
                      <button
                        key={level}
                        onClick={() => setSourceTrustFilter(level as any)}
                        className={`whitespace-nowrap px-2 py-1 text-[9px] md:text-[10px] font-black uppercase tracking-widest rounded transition-colors border ${
                          sourceTrustFilter === level 
                            ? 'bg-sky-500/10 text-sky-400 border-sky-500/30 shadow-[0_0_10px_rgba(14,165,233,0.1)]' 
                            : 'bg-slate-900/50 text-slate-500 hover:text-slate-300 border-slate-800/80 hover:bg-slate-800'
                        }`}
                      >
                        {level === 'All' ? 'All Sources' : `${level} Trust`}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-6">
                  {filteredEvidenceItems.length === 0 ? (
                    <div className="p-8 rounded-2xl bg-slate-900/50 border border-slate-800 text-center">
                      <ShieldAlert size={32} className="mx-auto text-slate-600 mb-4" />
                      <h3 className="text-lg font-bold text-slate-400 mb-2">No Direct Evidence Found</h3>
                      <p className="text-slate-500 text-sm">The current data stream does not contain specific signals matching your query parameters and filters.</p>
                    </div>
                  ) : (
                    filteredEvidenceItems.map((item: any, idx: number) => {
                      const itemTrust = resolveTrustLevel(item.source, item.trust_level);
                      return (
                      <div key={idx} className="glass p-6 rounded-2xl border-slate-800/60 hover:border-sky-500/30 transition-all group">
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex items-center space-x-3">
                            <div className="p-2 bg-slate-900 rounded-lg text-sky-500 group-hover:text-sky-400 transition-colors">
                              <FileText size={18} />
                            </div>
                            <div>
                              <h3 className="text-base font-bold text-slate-200 group-hover:text-white transition-colors">{item.title}</h3>
                              <div className="flex items-center space-x-2 text-[10px] font-black text-slate-500 uppercase tracking-widest mt-0.5">
                                <span className={`px-1.5 py-0.5 rounded text-[8px] border ${itemTrust === 'High' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' :
                                  itemTrust === 'Medium' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
                                    'bg-red-500/10 text-red-500 border-red-500/20'
                                  }`}>
                                  {itemTrust}
                                </span>
                                <SourceBadge source={item.source} size="sm" />
                                <span className="w-1 h-1 bg-slate-700 rounded-full"></span>
                                <span>{item.timestamp ? new Date(item.timestamp).toLocaleString() : 'N/A'}</span>
                              </div>
                            </div>
                          </div>
                          {item.company && (
                            <span className="px-2 py-1 rounded bg-slate-800 text-slate-400 text-[10px] font-bold uppercase tracking-wider">
                              {item.company}
                            </span>
                          )}
                        </div>
                        {item.snippet && item.snippet !== "..." && item.snippet.length >= 20 && (
                          <p className="text-sm text-slate-400 leading-relaxed pl-12 border-l-2 border-slate-800 group-hover:border-sky-500/30 transition-colors">
                            {item.snippet}
                          </p>
                        )}
                      </div>
                      );
                    })
                  )}
                </div>

                <div className="mt-16 flex items-center justify-between p-6 glass rounded-2xl border-slate-800/40">
                  <div className="flex space-x-3">
                    <button
                      onClick={() => setShowExportModal(true)}
                      className="flex items-center space-x-2 px-4 py-2 bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest hover:bg-sky-400 transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)]"
                    >
                      <BarChart3 size={14} />
                      <span>Export Analysis</span>
                    </button>
                    <button
                      onClick={handleVerify}
                      className="flex items-center space-x-2 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-xs font-black uppercase tracking-widest hover:bg-slate-700 transition-all"
                    >
                      <HelpCircle size={14} />
                      <span>Verify Sources</span>
                    </button>
                  </div>
                  <div className="flex items-center space-x-3 text-[10px] font-mono text-slate-600">
                    <span className="uppercase tracking-widest">Last Updated: {queryResult.last_updated}</span>
                    <span className="w-1 h-1 bg-slate-800 rounded-full"></span>
                    <span className="uppercase tracking-widest">SID: SP-94-ALPHA</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* INPUT BAR (STICKY BOTTOM) */}
          <div className="p-4 md:p-8 bg-slate-950/60 backdrop-blur-2xl border-t border-slate-800/60 relative z-40">
            <div className="max-w-4xl mx-auto space-y-3 md:space-y-4">
              <form onSubmit={handleSubmit} className="relative group">
                <div className="absolute inset-0 -m-[1px] bg-gradient-to-r from-sky-500/40 via-indigo-500/40 to-sky-500/40 rounded-2xl opacity-0 group-focus-within:opacity-100 blur-[6px] transition-all duration-500"></div>
                <div className="relative flex items-center bg-slate-900 border border-slate-700/60 rounded-2xl overflow-hidden px-4 md:px-5 focus-within:border-sky-500/50 shadow-2xl transition-all">
                  <Terminal className="text-slate-500 mr-3 md:mr-4 hidden sm:block" size={20} />
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="ENTER COMMAND OR QUERY..."
                    className="flex-1 py-4 md:py-5 bg-transparent outline-none text-slate-100 placeholder-slate-600 font-mono text-xs md:text-sm tracking-tight"
                    disabled={loading}
                  />
                  <div className="flex items-center space-x-2 md:space-x-4">
                    <div className="hidden md:flex items-center space-x-2 px-2 py-1 bg-slate-800/50 rounded-md border border-slate-700/50">
                      <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">ENTER</span>
                    </div>
                    <button
                      type="submit"
                      disabled={loading || !query.trim()}
                      className={`p-2.5 md:p-3 rounded-xl transition-all ${loading || !query.trim()
                        ? 'text-slate-600 bg-slate-800/50'
                        : 'text-white bg-sky-600 hover:bg-sky-500 shadow-[0_0_20px_rgba(14,165,233,0.4)] active:scale-95'
                        }`}
                    >
                      <Search size={20} />
                    </button>
                  </div>
                </div>
              </form>

              <div className="flex items-center justify-between px-2">
                <div className="flex items-center space-x-4 md:space-x-6">
                  <div className="flex items-center space-x-1.5 md:space-x-2">
                    <Clock size={10} className="text-slate-500" />
                    <span className="text-[8px] md:text-[10px] font-black text-slate-500 uppercase tracking-widest">Freshness: <span className="text-sky-500">{lastUpdate}</span></span>
                  </div>
                  <div className="flex items-center space-x-1.5 md:space-x-2">
                    <TrendingUp size={10} className="text-emerald-500" />
                    <span className="text-[8px] md:text-[10px] font-black text-slate-500 uppercase tracking-widest">Active: <span className="text-emerald-500">{filteredFeed.length}</span></span>
                  </div>
                </div>
                <div className="hidden sm:flex items-center space-x-4 text-[10px] font-black text-slate-600 uppercase tracking-widest">
                  <span className="text-sky-500/60 font-mono">GEMINI_ACTIVE</span>
                  <UserButton afterSignOutUrl="/sign-in" />
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};

const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col text-slate-200 relative overflow-hidden">
      <BackgroundLayer />
      <header className="h-16 border-b border-slate-800/60 flex items-center justify-between px-4 md:px-6 bg-slate-950/40 backdrop-blur-xl">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 bg-sky-600 rounded flex items-center justify-center shadow-[0_0_15px_rgba(2,132,199,0.3)]">
            <Cpu size={18} className="text-white" />
          </div>
          <div className="leading-tight">
            <h1 className="text-sm font-black tracking-tighter uppercase text-white flex items-center">
              Silicon<span className="text-sky-500">Pulse</span>
            </h1>
            <span className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Home Node</span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <SignedIn>
            <Link
              to="/dashboard"
              className="flex items-center space-x-2 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-slate-300 border border-slate-800 transition-all"
            >
              <Home size={12} />
              <span>Dashboard</span>
            </Link>
            <UserButton afterSignOutUrl="/" />
          </SignedIn>
          <SignedOut>
            <Link
              to="/sign-in"
              className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 rounded-md text-[10px] font-black uppercase tracking-widest text-slate-300 border border-slate-800 transition-all"
            >
              Sign In
            </Link>
            <Link
              to="/sign-up"
              className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 rounded-md text-[10px] font-black uppercase tracking-widest text-white transition-all shadow-[0_0_15px_rgba(14,165,233,0.3)]"
            >
              Create Account
            </Link>
          </SignedOut>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="max-w-4xl w-full text-center space-y-8">
          <div className="inline-flex items-center space-x-2 px-3 py-1 bg-sky-500/10 border border-sky-500/20 rounded-full text-sky-400 text-[10px] font-black uppercase tracking-widest">
            <Zap size={12} />
            <span>Real-Time Strategic Intelligence</span>
          </div>
          <h2 className="text-3xl md:text-5xl font-black text-white tracking-tighter uppercase leading-tight">
            Signal-First Intelligence for the Semiconductor Stack
          </h2>
          <p className="text-slate-500 text-base md:text-lg font-medium max-w-2xl mx-auto">
            Monitor live supply chain signals, competitive shifts, and macro events with a tactical, evidence-driven briefing system.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <SignedIn>
              <Link
                to="/dashboard"
                className="flex items-center space-x-2 px-5 py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(14,165,233,0.4)]"
              >
                <span>Enter Dashboard</span>
                <ArrowRight size={14} />
              </Link>
            </SignedIn>
            <SignedOut>
              <Link
                to="/sign-up"
                className="flex items-center space-x-2 px-5 py-3 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-black uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(14,165,233,0.4)]"
              >
                <span>Get Started</span>
                <ArrowRight size={14} />
              </Link>
              <Link
                to="/sign-in"
                className="px-5 py-3 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-lg text-xs font-black uppercase tracking-widest transition-all border border-slate-800"
              >
                Sign In
              </Link>
            </SignedOut>
          </div>
        </div>
      </main>

      <section className="px-6 pb-12">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              title: 'Live Signal Radar',
              description: 'Continuous ingestion of high-impact market and supply chain events.',
              icon: Activity,
              color: 'text-emerald-400'
            },
            {
              title: 'Strategic Reports',
              description: 'Evidence-backed analysis with competitor impact and outlook.',
              icon: FileText,
              color: 'text-sky-400'
            },
            {
              title: 'Source Verification',
              description: 'Transparent trust scores and supporting provenance.',
              icon: ShieldAlert,
              color: 'text-amber-400'
            }
          ].map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.title} className="glass p-5 rounded-2xl border-slate-800/60 bg-slate-950/40">
                <div className={`p-2 w-fit bg-slate-900 rounded-lg ${item.color}`}>
                  <Icon size={16} />
                </div>
                <h3 className="mt-3 text-sm font-black text-white uppercase tracking-widest">{item.title}</h3>
                <p className="mt-2 text-xs text-slate-500 leading-relaxed">{item.description}</p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route
          path="/sign-in/*"
          element={
            <div className="flex bg-slate-950 items-center justify-center h-screen w-screen">
              <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" forceRedirectUrl="/dashboard" />
            </div>
          }
        />
        <Route
          path="/sign-up/*"
          element={
            <div className="flex bg-slate-950 items-center justify-center h-screen w-screen">
              <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" forceRedirectUrl="/dashboard" />
            </div>
          }
        />
        <Route
          path="/dashboard/*"
          element={
            <>
              <SignedIn>
                <Dashboard />
              </SignedIn>
              <SignedOut>
                <Navigate to="/sign-in" replace />
              </SignedOut>
            </>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
