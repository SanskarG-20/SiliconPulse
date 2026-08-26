import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@clerk/clerk-react';
import useSWR from 'swr';
import { LiveEvent } from '../types';
import { INITIAL_LIVE_FEED } from '../constants';
import { buildLiveFeed, createLiveEvent, getRelativeTimeLabel, rotateFeed } from '../utils/feedUtils';
import { generateRecommendationsFromFeed } from '../utils/recommendationUtils';
import { resolveTrustLevel } from '../utils/sourceMapping';
import { useSignalsWS, WSStatus } from './useSignalsWS';
import { 
  querySiliconPulse, 
  injectSignal, 
  fetchSignals, 
  QueryResponse, 
  formatEvidenceToContext, 
  generateInsight, 
  bootstrapSystem, 
  fetchRecommendations, 
  exportAnalysis, 
  verifySources, 
  setAuthTokenGetter, 
  syncAuthenticatedUser,
  BASE_URL,
  SHOULD_WARN_LOCALHOST_IN_PROD,
  checkBackendHealth,
  waitForBackend,
} from '../api/siliconpulseApi';

interface UseDashboardReturn {
  // State
  liveFeed: LiveEvent[];
  query: string;
  setQuery: (q: string) => void;
  queryResult: QueryResponse | null;
  insight: string | null;
  loading: boolean;
  error: string | null;
  setLoading: (v: boolean) => void;
  setError: (v: string | null) => void;
  toast: string | null;
  lastUpdate: string;
  recommendations: any[];
  lastSubmittedQuery: string;
  feedFilter: string;
  setFeedFilter: (f: string) => void;
  sourceTrustFilter: 'All' | 'High' | 'Medium' | 'Low';
  setSourceTrustFilter: (f: 'All' | 'High' | 'Medium' | 'Low') => void;
  watchlist: string[];
  // Modal states
  showInjectModal: boolean;
  setShowInjectModal: (v: boolean) => void;
  injectTitle: string;
  setInjectTitle: (v: string) => void;
  injectContent: string;
  setInjectContent: (v: string) => void;
  injectSource: string;
  setInjectSource: (v: string) => void;
  injectLoading: boolean;
  injectSuccess: boolean;
  showExportModal: boolean;
  setShowExportModal: (v: boolean) => void;
  showVerifyModal: boolean;
  setShowVerifyModal: (v: boolean) => void;
  exportFormat: string;
  setExportFormat: (v: string) => void;
  includeEvidence: boolean;
  setIncludeEvidence: (v: boolean) => void;
  showDigestModal: boolean;
  setShowDigestModal: (v: boolean) => void;
  digestLoading: boolean;
  dailyDigest: string | null;
  verifiedSources: any[];
  verifying: boolean;
  showMobileMenu: boolean;
  setShowMobileMenu: (v: boolean) => void;
  isLightMode: boolean;
  setIsLightMode: (v: boolean) => void;
  // Computed
  evidenceItems: any[];
  filteredEvidenceItems: any[];
  isInsightUnavailable: boolean;
  filteredFeed: LiveEvent[];
  backendOnline: boolean;
  isWakingUp: boolean;
  apiBaseUrl: string;
  shouldWarnLocalhost: boolean;
  // Functions
  notify: (message: string) => void;
  handleSubmit: (e: React.FormEvent | string) => Promise<void>;
  handleCompanyClick: (company: string) => void;
  toggleWatchlist: (company: string, e?: React.MouseEvent) => void;
  generateDailyDigest: () => Promise<void>;
  handleInjectSubmit: (e: React.FormEvent) => Promise<void>;
  handleExport: () => Promise<void>;
  handleVerify: () => Promise<void>;
  resetDashboard: () => void;
  retryInsight: () => void;
  refreshSignals: () => Promise<void>;
  waitForBackendAndRetry: () => Promise<boolean>;
  wsStatus: WSStatus;
  scrollRef: React.RefObject<HTMLDivElement>;
}

export const useDashboard = (): UseDashboardReturn => {
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
  const [exportFormat, setExportFormat] = useState('md');
  const [includeEvidence, setIncludeEvidence] = useState(true);

  // Daily Digest Modal State
  const [showDigestModal, setShowDigestModal] = useState(false);
  const [digestLoading, setDigestLoading] = useState(false);
  const [dailyDigest, setDailyDigest] = useState<string | null>(null);
  const [verifiedSources, setVerifiedSources] = useState<any[]>([]);
  const [verifying, setVerifying] = useState(false);

  const [showMobileMenu, setShowMobileMenu] = useState(false);

  const [isLightMode, setIsLightMode] = useState(() => {
    return localStorage.getItem('siliconpulse_theme') === 'light';
  });
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [isWakingUp, setIsWakingUp] = useState<boolean>(false);

  useEffect(() => {
    console.log(`[SiliconPulse] API BASE_URL: ${BASE_URL}`);
    if (SHOULD_WARN_LOCALHOST_IN_PROD) {
      console.warn(`[SiliconPulse] VITE_API_BASE_URL points to localhost in production! Set VITE_API_BASE_URL=https://your-backend.onrender.com/api in Vercel env vars.`);
    }
    // Initial health probe
    checkBackendHealth().then(ok => {
      setBackendOnline(ok);
      if (!ok) console.warn(`[SiliconPulse] Backend health check failed for ${BASE_URL}`);
    });
  }, []);

  useEffect(() => {
    if (isLightMode) {
      document.documentElement.classList.add('light-theme');
      localStorage.setItem('siliconpulse_theme', 'light');
    } else {
      document.documentElement.classList.remove('light-theme');
      localStorage.setItem('siliconpulse_theme', 'dark');
    }
  }, [isLightMode]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const feedRotationRef = useRef(0);
  const recommendationKeysRef = useRef<Set<string>>(new Set());
  const remoteRecommendationsRef = useRef<any[]>([]);
  const seenSignalIdsRef = useRef<Set<string>>(new Set());
  const initialFeedLoadedRef = useRef<boolean>(false);

  const notify = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    setAuthTokenGetter(() => getToken());
    return () => setAuthTokenGetter(null);
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

  const processSignals = useCallback((signals: any[]) => {
    if (signals && signals.length > 0) {
      setBackendOnline(true);
      setIsWakingUp(false);
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

    // Empty signals but not error = backend online but no data yet
    setBackendOnline(true);
    setLiveFeed(INITIAL_LIVE_FEED);
    const fallbackResult = generateRecommendationsFromFeed(
      INITIAL_LIVE_FEED,
      recommendationKeysRef.current,
      remoteRecommendationsRef.current
    );
    recommendationKeysRef.current = fallbackResult.nextKeys;
    setRecommendations(fallbackResult.recommendations);
  }, []);

  const refreshSignals = useCallback(async () => {
    try {
      const signals = await fetchSignals();
      processSignals(signals);
    } catch (err) {
      console.error("Failed to refresh signals:", err);
      setBackendOnline(false);
      notify("Live feed refresh failed. Showing cached signals.");
    }
  }, [notify, processSignals]);

  // WebSocket live feed state (declared before SWR so refreshInterval can read it)
  const wsStatusRef = useRef<WSStatus>('closed');
  const handleWSStatus = useCallback((s: WSStatus) => {
    wsStatusRef.current = s;
    setWsStatus(s);
    if (s === 'open') setBackendOnline(true);
  }, []);
  const [wsStatus, setWsStatus] = useState<WSStatus>('closed');
  const [wsToken, setWsToken] = useState<string | null>(null);

  // SWR: poll signals (paused when WS live; fallback when WS closed/error)
  const { data: swrSignals, error: swrError, mutate: mutateSignals } = useSWR('signals', fetchSignals, {
    refreshInterval: (wsStatus === 'open') ? 0 : 5000,
    dedupingInterval: 4000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    fallbackData: [],
    shouldRetryOnError: true,
    errorRetryInterval: 5000,
    errorRetryCount: 3,
  });

  // Process SWR data when it changes
  useEffect(() => {
    if (swrError) {
      setBackendOnline(false);
      if (SHOULD_WARN_LOCALHOST_IN_PROD) {
        console.error(`Backend offline - localhost in prod: ${BASE_URL}`);
      }
    }
    if (swrSignals) {
      processSignals(swrSignals);
    }
  }, [swrSignals, swrError, processSignals]);

  // Refresh WS auth token periodically (Clerk tokens expire ~60s)
  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const t = await getToken();
        if (!cancelled) setWsToken(t);
      } catch { /* ignore */ }
    };
    refresh();
    const iv = window.setInterval(refresh, 45000);
    return () => { cancelled = true; window.clearInterval(iv); };
  }, [getToken]);

  useSignalsWS({
    token: wsToken,
    enabled: true,
    onSignals: processSignals,
    onStatusChange: handleWSStatus,
  });

  const waitForBackendAndRetry = useCallback(async (): Promise<boolean> => {
    setIsWakingUp(true);
    const ok = await waitForBackend((attempt) => {
      notify(`Backend waking up... retry ${attempt}/6`);
    });
    setIsWakingUp(false);
    setBackendOnline(ok);
    if (ok) {
      notify("Backend online — retrying your request...");
      mutateSignals();
    }
    return ok;
  }, [notify, mutateSignals]);

  useEffect(() => {
    const init = async () => {
      try {
        await syncAuthenticatedUser();
      } catch (err) {
        console.error('Authenticated user sync failed:', err);
      }

      await bootstrapSystem();
      // Trigger SWR revalidation instead of manual refresh
      mutateSignals();

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
  }, [mutateSignals]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [queryResult]);

  const handleSubmit = useCallback(async (e: React.FormEvent | string) => {
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
      const result = await querySiliconPulse(finalQuery.trim());
      setBackendOnline(true);
      setIsWakingUp(false);
      setQueryResult(result);
      setLoading(false);

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
      const msg = err.message || 'Intelligence failure. Connection to core reasoning lost.';
      if (msg.includes('Backend offline') || msg.includes('tried')) {
        setBackendOnline(false);
      }
      setError(msg);
      setLoading(false);
    }
  }, [query, loading]);

  const handleCompanyClick = useCallback((company: string) => {
    setFeedFilter(company);
    const newQuery = `Recent activity and strategic impact of ${company}`;
    setQuery(newQuery);
    handleSubmit(newQuery);
    setShowMobileMenu(false);
  }, [handleSubmit]);

  const toggleWatchlist = useCallback((company: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setWatchlist(prev => {
      const next = prev.includes(company) ? prev.filter(c => c !== company) : [...prev, company];
      localStorage.setItem('siliconpulse_watchlist', JSON.stringify(next));
      return next;
    });
  }, []);

  const generateDailyDigest = useCallback(async () => {
    setShowDigestModal(true);
    setDigestLoading(true);
    setDailyDigest(null);
    try {
      const result = await querySiliconPulse("Summarize the top 3 most strategic and high-impact tech events from the last 24 hours.");
      const context = formatEvidenceToContext(result.evidence ?? []);
      const insight = await generateInsight("Write a concise Morning Briefing detailing the top 3 tech events of the last 24 hours.", context);
      setDailyDigest(insight);
    } catch (err) {
      console.error(err);
      setDailyDigest("Failed to generate the morning briefing.");
    } finally {
      setDigestLoading(false);
    }
  }, []);

  const handleInjectSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!injectTitle.trim() || !injectContent.trim()) return;

    setInjectLoading(true);
    try {
      await injectSignal(injectTitle, injectContent, injectSource);
      setInjectSuccess(true);
      setInjectTitle('');
      setInjectContent('');
      setInjectSource('ManualInject');

      await mutateSignals();
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
  }, [injectTitle, injectContent, injectSource, mutateSignals, notify]);

  const handleExport = useCallback(async () => {
    if (!queryResult || !insight) return;
    const evidenceItems = Array.isArray(queryResult?.evidence) ? queryResult.evidence : [];
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
  }, [queryResult, insight, exportFormat, includeEvidence, notify]);

  const handleVerify = useCallback(async () => {
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
  }, [queryResult, notify]);

  const resetDashboard = useCallback(() => {
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
  }, []);

  const retryInsight = useCallback(() => {
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
  }, [queryResult]);

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

  return {
    // State
    liveFeed,
    query,
    setQuery,
    queryResult,
    insight,
    loading,
    error,
    toast,
    lastUpdate,
    recommendations,
    lastSubmittedQuery,
    feedFilter,
    setFeedFilter,
    sourceTrustFilter,
    setSourceTrustFilter,
    watchlist,
    // Modal states
    showInjectModal,
    setShowInjectModal,
    injectTitle,
    setInjectTitle,
    injectContent,
    setInjectContent,
    injectSource,
    setInjectSource,
    injectLoading,
    injectSuccess,
    showExportModal,
    setShowExportModal,
    showVerifyModal,
    setShowVerifyModal,
    exportFormat,
    setExportFormat,
    includeEvidence,
    setIncludeEvidence,
    showDigestModal,
    setShowDigestModal,
    digestLoading,
    dailyDigest,
    verifiedSources,
    verifying,
    showMobileMenu,
    setShowMobileMenu,
    isLightMode,
    setIsLightMode,
    // Computed
    evidenceItems,
    filteredEvidenceItems,
    isInsightUnavailable,
    filteredFeed,
    backendOnline,
    isWakingUp,
    apiBaseUrl: BASE_URL,
    shouldWarnLocalhost: SHOULD_WARN_LOCALHOST_IN_PROD,
    // Functions
    notify,
    handleSubmit,
    handleCompanyClick,
    toggleWatchlist,
    generateDailyDigest,
    handleInjectSubmit,
    handleExport,
    handleVerify,
    resetDashboard,
    retryInsight,
    refreshSignals,
    waitForBackendAndRetry,
    wsStatus,
    scrollRef,
    setLoading,
    setError,
  };
};