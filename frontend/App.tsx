import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { SignedIn, SignedOut, SignIn, SignUp, UserButton } from '@clerk/clerk-react';
import {
  Activity, Cpu, ShieldAlert, FileText,
  CheckCircle2, ArrowRight, Zap, Home, X
} from 'lucide-react';
import Dashboard from './components/dashboard/Dashboard';
import { BackgroundLayer } from './components/BackgroundLayer';

const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col text-slate-200 relative overflow-hidden">
      <BackgroundLayer />
      <header className="h-16 border-b border-slate-800/60 flex items-center justify-between px-4 md:px-6 bg-slate-950/40 backdrop-blur-xl">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 bg-sky-600 rounded flex items-center justify-center shadow-[0_0_15px_rgba(2,132,199,0.3)]">
            <Activity size={18} className="text-white" />
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