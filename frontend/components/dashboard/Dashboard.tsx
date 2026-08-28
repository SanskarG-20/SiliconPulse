import React from 'react';
import { LiveTicker } from '../../components/LiveTicker';
import { BackgroundLayer } from '../../components/BackgroundLayer';
import { Header } from '../layout/Header';
import { Sidebar } from '../layout/Sidebar';
import { QueryZone } from './QueryZone';
import { InputBar } from '../layout/InputBar';
import { InjectModal } from '../modals/InjectModal';
import { ExportModal } from '../modals/ExportModal';
import { VerifyModal } from '../modals/VerifyModal';
import { DigestModal } from '../modals/DigestModal';
import { MobileDrawer } from '../modals/MobileDrawer';
import { useDashboard } from '../../hooks/useDashboard';

const Dashboard: React.FC = () => {
  const {
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
    apiBaseUrl,
    shouldWarnLocalhost,
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
    scrollRef,
    setLoading,
    setError,
  } = useDashboard();

  const [dismissedWarn, setDismissedWarn] = React.useState(() => localStorage.getItem('dismissedLocalhostWarn') === '1');

  return (
    <div className="flex flex-col h-screen overflow-hidden text-slate-200 relative">
      <BackgroundLayer />
      {shouldWarnLocalhost && !dismissedWarn && (
        <div className="fixed inset-0 z-[200] bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-amber-500/30 rounded-2xl p-6 shadow-2xl">
            <h2 className="text-amber-400 font-black uppercase tracking-widest text-sm mb-2">⚠️ Misconfigured API URL</h2>
            <p className="text-slate-300 text-sm mb-3">Production is using <code className="bg-amber-500/20 px-1.5 py-0.5 rounded text-amber-200">{apiBaseUrl}</code> (localhost). Browsers block this → “Backend offline”.</p>
            <ol className="text-slate-400 text-xs list-decimal list-inside space-y-1 mb-4">
              <li>Vercel → Project → Settings → Environment Variables</li>
              <li>Add <code className="bg-slate-800 px-1 rounded">VITE_API_BASE_URL</code> = <code className="bg-slate-800 px-1 rounded">https://your-backend.onrender.com/api</code></li>
              <li>Save → **Redeploy** (Vercel → Deployments → … → Redeploy)</li>
              <li>Hard refresh this page</li>
            </ol>
            <p className="text-[11px] text-slate-500 mb-4">Current: <code>{apiBaseUrl}</code> — Render URL is shown in Render Dashboard → your service → top bar.</p>
            <div className="flex space-x-2">
              <button onClick={() => window.location.reload()} className="flex-1 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-black uppercase">Reload after fix</button>
              <button onClick={() => { localStorage.setItem('dismissedLocalhostWarn', '1'); setDismissedWarn(true); }} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-bold">Dismiss</button>
            </div>
          </div>
        </div>
      )}
      {shouldWarnLocalhost && dismissedWarn && (
        <div className="bg-amber-500/20 border-b border-amber-500/30 text-amber-200 text-[11px] font-bold text-center py-2 px-4 z-50">
          ⚠️ Production is using localhost API ({apiBaseUrl}). Set <code className="bg-amber-500/20 px-1 rounded">VITE_API_BASE_URL=https://your-backend.onrender.com/api</code> in Vercel → Settings → Environment Variables → Redeploy.
          <button onClick={() => { localStorage.removeItem('dismissedLocalhostWarn'); setDismissedWarn(false); }} className="ml-2 underline">Show fix</button>
        </div>
      )}
      {!backendOnline && (
        <div className="bg-red-500/10 border-b border-red-500/20 text-red-300 text-xs text-center py-2 px-4 z-50 flex items-center justify-center space-x-2">
          <span>{isWakingUp ? "⏳ Backend is waking up (Render free tier, ~30s) — retrying automatically every 15s..." : `🔴 Backend offline (tried ${apiBaseUrl}) — auto-retrying...`}</span>
          {!isWakingUp && (
            <button onClick={async () => {
              const ok = await waitForBackendAndRetry();
              if (ok && lastSubmittedQuery) handleSubmit(lastSubmittedQuery);
              else if (!ok) setError(`Backend still offline after retries (tried ${apiBaseUrl}). Check Render dashboard logs and that VITE_API_BASE_URL is not localhost.`);
            }} className="ml-2 px-2 py-0.5 bg-red-500/20 hover:bg-red-500/30 rounded text-[10px] font-black uppercase tracking-widest">Retry Now</button>
          )}
        </div>
      )}
      {toast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[120] px-4 py-2 rounded-lg border border-sky-500/30 bg-slate-950/95 text-sky-100 text-xs font-bold uppercase tracking-widest shadow-2xl">
          {toast}
        </div>
      )}

      {/* INJECTION MODAL */}
      <InjectModal
        isOpen={showInjectModal}
        onClose={() => setShowInjectModal(false)}
        onSubmit={handleInjectSubmit}
        title={injectTitle}
        setTitle={setInjectTitle}
        content={injectContent}
        setContent={setInjectContent}
        source={injectSource}
        setSource={setInjectSource}
        loading={injectLoading}
        success={injectSuccess}
      />

      {/* EXPORT MODAL */}
      <ExportModal
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
        onExport={handleExport}
        format={exportFormat}
        setFormat={setExportFormat}
        includeEvidence={includeEvidence}
        setIncludeEvidence={setIncludeEvidence}
      />

      {/* VERIFY SOURCES MODAL */}
      <VerifyModal
        isOpen={showVerifyModal}
        onClose={() => setShowVerifyModal(false)}
        verifying={verifying}
        sources={verifiedSources}
      />

      {/* DIGEST MODAL */}
      <DigestModal
        isOpen={showDigestModal}
        onClose={() => setShowDigestModal(false)}
        loading={digestLoading}
        content={dailyDigest}
      />

      {/* MOBILE DRAWER */}
      <MobileDrawer
        isOpen={showMobileMenu}
        onClose={() => setShowMobileMenu(false)}
        feed={filteredFeed}
        watchlist={watchlist}
        onCompanyClick={handleCompanyClick}
        onToggleWatchlist={toggleWatchlist}
      />

      {/* HEADER */}
      <Header
        feedFilter={feedFilter}
        onFeedFilterChange={setFeedFilter}
        onReset={resetDashboard}
        onGenerateDigest={generateDailyDigest}
        onToggleTheme={() => setIsLightMode(!isLightMode)}
        onOpenInject={() => setShowInjectModal(true)}
        onOpenMobileMenu={() => setShowMobileMenu(true)}
        isLightMode={isLightMode}
        showMobileMenu={showMobileMenu}
      />

      {/* LIVE SIGNALS ZONE */}
      <LiveTicker events={filteredFeed} />

      {/* CORE LAYOUT GRID */}
      <main className="flex-1 flex overflow-hidden">
        {/* RADAR ZONE (SIDEBAR) */}
        <Sidebar
          feed={filteredFeed}
          watchlist={watchlist}
          onCompanyClick={handleCompanyClick}
          onToggleWatchlist={toggleWatchlist}
        />

        {/* QUERY & REPORT ZONE */}
        <section className="flex-1 flex flex-col bg-transparent relative overflow-hidden">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-10 custom-scrollbar">
            <QueryZone
              queryResult={queryResult}
              loading={loading}
              error={error}
              insight={insight}
              lastSubmittedQuery={lastSubmittedQuery}
              filteredEvidenceItems={filteredEvidenceItems}
              isInsightUnavailable={isInsightUnavailable}
              sourceTrustFilter={sourceTrustFilter}
              setSourceTrustFilter={setSourceTrustFilter}
              recommendations={recommendations}
              lastUpdate={lastUpdate}
              scrollRef={scrollRef}
              onSubmit={handleSubmit}
              onRetryInsight={retryInsight}
              onCheckBackend={async () => {
                setLoading(true);
                const ok = await waitForBackendAndRetry();
                setLoading(false);
                if (ok && lastSubmittedQuery) {
                  handleSubmit(lastSubmittedQuery);
                } else if (!ok) {
                  setError(`Backend still offline after retries (tried ${apiBaseUrl}). Render free tier needs 30-50s to wake. Check Render logs or set VITE_API_BASE_URL correctly.`);
                }
              }}
              onDismissError={() => setError(null)}
              onShowExport={() => setShowExportModal(true)}
              onShowVerify={() => setShowVerifyModal(true)}
            />
          </div>

          {/* INPUT BAR (STICKY BOTTOM) */}
          <InputBar
            query={query}
            onQueryChange={setQuery}
            onSubmit={handleSubmit}
            loading={loading}
            lastUpdate={lastUpdate}
            activeCount={filteredFeed.length}
          />
        </section>
      </main>
    </div>
  );
};

export default Dashboard;