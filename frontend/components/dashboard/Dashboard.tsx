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
    scrollRef,
  } = useDashboard();

  return (
    <div className="flex flex-col h-screen overflow-hidden text-slate-200 relative">
      <BackgroundLayer />
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
                const { checkBackendHealth } = await import('../../api/siliconpulseApi');
                const isOnline = await checkBackendHealth();
                if (isOnline) {
                  setLoading(false);
                  if (lastSubmittedQuery) handleSubmit(lastSubmittedQuery);
                } else {
                  setLoading(false);
                  setError("Backend still offline. Please ensure server is running on port 8000.");
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