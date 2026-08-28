import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { SignedIn, SignedOut, SignIn, SignUp, UserButton } from '@clerk/clerk-react';
import { Activity, ArrowRight, ShieldAlert, FileText, Zap } from 'lucide-react';
import Dashboard from './components/dashboard/Dashboard';
import { BackgroundLayer } from './components/BackgroundLayer';

const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col text-[#F1F5F9] relative">
      <BackgroundLayer />

      <header className="h-[56px] border-b border-[#1C3553]/50 flex items-center justify-between px-4 md:px-6 bg-[#050B1A]/70 backdrop-blur-xl">
        <div className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-[8px] bg-[#0E1E32] border border-[#1C3553] flex items-center justify-center">
            <span className="w-[18px] h-[18px] rounded-[5px] bg-[#22D3EE] flex items-center justify-center">
              <Activity size={11} className="text-[#050B1A]" strokeWidth={2.5} />
            </span>
          </span>
          <span className="display text-[13px] font-bold tracking-[-0.02em] text-white">
            SILICON<span className="text-[#22D3EE]">PULSE</span>
          </span>
          <span className="hidden sm:inline-flex mono text-[9px] tracking-[0.14em] text-[#475569] border border-[#1C3553]/50 rounded-full px-2 py-0.5 bg-[#0E1E32]">RETICLE OK</span>
        </div>

        <div className="flex items-center gap-2">
          <SignedIn>
            <Link to="/dashboard" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#0E1E32] border border-[#1C3553] text-[11px] font-semibold tracking-[0.04em] text-[#94A3B8] hover:text-white hover:border-[#22D3EE]/30 transition-colors">
              Dashboard <ArrowRight size={12} />
            </Link>
            <UserButton afterSignOutUrl="/" />
          </SignedIn>
          <SignedOut>
            <Link to="/sign-in" className="px-3 py-1.5 rounded-full bg-[#0E1E32] border border-[#1C3553] text-[11px] font-semibold tracking-[0.04em] text-[#94A3B8] hover:text-white transition-colors">
              Sign in
            </Link>
            <Link to="/sign-up" className="px-3.5 py-1.5 rounded-full bg-[#E8A253] text-[#050B1A] text-[11px] font-bold tracking-[0.04em] hover:bg-[#F0A85E] shadow-[0_0_14px_rgba(232,162,83,0.28)] transition-colors">
              Create account
            </Link>
          </SignedOut>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 md:px-6 py-10 md:py-16">
        <div className="w-full max-w-[980px] grid md:grid-cols-[1.15fr_0.85fr] gap-8 md:gap-10 items-center">
          <div className="space-y-5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#22D3EE]/10 border border-[#22D3EE]/15 text-[#22D3EE] mono text-[10px] font-semibold tracking-[0.1em]">
              <Zap size={12} /> SIGNAL-FIRST INTELLIGENCE
            </span>
            <h1 className="display text-[36px] md:text-[52px] font-bold leading-[0.9] tracking-[-0.04em] text-white">
              Intelligence
              <br />
              <span className="text-[#22D3EE]">for the</span> silicon
              <br />
              stack.
            </h1>
            <p className="serif text-[16px] md:text-[18px] leading-relaxed text-[#94A3B8] max-w-[560px]">
              Live supply-chain signals, yield notes and market shifts — cross-referenced, scored and briefed with fab-aware Graph RAG. One query, one confident report.
            </p>
            <div className="flex flex-wrap gap-2.5 pt-1">
              <SignedIn>
                <Link to="/dashboard" className="inline-flex items-center gap-1.5 px-5 py-3 rounded-full bg-[#E8A253] text-[#050B1A] text-[12px] font-bold tracking-[0.04em] hover:bg-[#F0A85E] shadow-[0_0_18px_rgba(232,162,83,0.3)] transition-colors">
                  Enter bench <ArrowRight size={14} />
                </Link>
              </SignedIn>
              <SignedOut>
                <Link to="/sign-up" className="inline-flex items-center gap-1.5 px-5 py-3 rounded-full bg-[#E8A253] text-[#050B1A] text-[12px] font-bold tracking-[0.04em] hover:bg-[#F0A85E] shadow-[0_0_18px_rgba(232,162,83,0.3)] transition-colors">
                  Get started <ArrowRight size={14} />
                </Link>
                <Link to="/sign-in" className="px-5 py-3 rounded-full bg-[#0E1E32] border border-[#1C3553] text-[#CBD5E1] text-[12px] font-semibold tracking-[0.04em] hover:border-[#22D3EE]/30 hover:text-white transition-colors">
                  Sign in
                </Link>
              </SignedOut>
            </div>
            <div className="flex flex-wrap gap-2 mono text-[10px] tracking-[0.08em] text-[#475569] pt-1">
              <span className="px-2 py-1 rounded-full bg-[#0E1E32] border border-[#1C3553]/60">HYBRID VECTOR ≥0.72</span>
              <span className="px-2 py-1 rounded-full bg-[#0E1E32] border border-[#1C3553]/60">GRAPH RAG 19 EDGES</span>
              <span className="px-2 py-1 rounded-full bg-[#0E1E32] border border-[#1C3553]/60 hidden sm:inline">E2E VERIFIED</span>
            </div>
          </div>

          <div className="relative rounded-[20px] border border-[#1C3553]/50 bg-[#0E1E32]/40 p-4 md:p-5 blueprint-grid overflow-hidden">
            <div className="absolute inset-0 pointer-events-none opacity-[0.04]" style={{ background: 'radial-gradient(circle at 70% 20%, #E8A253 1px, transparent 1.6px)', backgroundSize: '18px 18px' }} />
            <div className="relative rounded-[14px] border border-[#1C3553]/40 bg-[#050B1A]/80 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="mono text-[10px] tracking-[0.1em] font-semibold text-[#22D3EE]">LIVE RETICLE • TSMC N2</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)] animate-pulse" />
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { k: 'Yield', v: '94.2%', sub: '+1.3 pts' },
                  { k: 'WIP', v: '12.4k', sub: 'wafers' },
                  { k: 'HBM', v: 'Short', sub: '−12% cap' },
                ].map((s) => (
                  <div key={s.k} className="rounded-[12px] bg-[#0E1E32] border border-[#1C3553]/40 p-2.5">
                    <p className="mono text-[9px] tracking-[0.1em] font-semibold text-[#64748B]">{s.k}</p>
                    <p className="display text-[16px] font-bold tracking-[-0.02em] text-white leading-none mt-1">{s.v}</p>
                    <p className="mono text-[10px] text-[#64748B] mt-1">{s.sub}</p>
                  </div>
                ))}
              </div>
              <div className="rounded-[10px] bg-[#0E1E32] border border-[#1C3553]/30 p-3 flex items-center gap-2.5">
                <span className="w-7 h-7 rounded-[8px] bg-[#E8A253]/10 border border-[#E8A253]/15 flex items-center justify-center shrink-0">
                  <FileText size={13} className="text-[#E8A253]" />
                </span>
                <div className="min-w-0">
                  <p className="text-[12px] font-semibold leading-tight text-[#E2E8F0] truncate">TSMC N2 yield hits 90% ahead of Apple ramp</p>
                  <p className="mono text-[10px] tracking-[0.06em] text-[#64748B]">CoWoS • N3 → N2 • 2h ago</p>
                </div>
              </div>
              <div className="flex items-center justify-between mono text-[10px] tracking-[0.08em] text-[#475569] pt-1 border-t border-[#1C3553]/30">
                <span>IMPACT 88 • HIGH CONFIDENCE</span>
                <span className="text-[#22D3EE]">View report →</span>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2">
              {[
                { title: 'Live Radar', desc: '12h freshness, deduped' },
                { title: 'Graph RAG', desc: 'ASML → TSMC → NVIDIA' },
                { title: 'Verified', desc: 'Trust • provenance' },
              ].map((f) => (
                <div key={f.title} className="rounded-[12px] bg-[#050B1A]/60 border border-[#1C3553]/30 p-2.5">
                  <p className="display text-[10px] font-semibold tracking-[0.08em] text-white">{f.title}</p>
                  <p className="mt-1 text-[11px] leading-snug text-[#64748B]">{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-[#1C3553]/30 py-4 px-6 flex flex-wrap items-center justify-between gap-3 mono text-[10px] tracking-[0.08em] text-[#475569]">
        <span>© 2026 SiliconPulse • Fab-aware intelligence</span>
        <span className="flex items-center gap-2">
          <ShieldAlert size={12} className="text-[#64748B]" /> Analyst advisory • Not financial advice
        </span>
      </footer>
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
            <div className="flex bg-[#050B1A] items-center justify-center min-h-screen w-screen p-4">
              <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" forceRedirectUrl="/dashboard" />
            </div>
          }
        />
        <Route
          path="/sign-up/*"
          element={
            <div className="flex bg-[#050B1A] items-center justify-center min-h-screen w-screen p-4">
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
