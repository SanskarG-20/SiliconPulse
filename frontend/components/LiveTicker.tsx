import React from 'react';
import { LiveEvent } from '../types';
import { SourceBadge } from './SourceBadge';
import { getRelativeTimeLabel } from '../utils/feedUtils';

interface LiveTickerProps {
  events: LiveEvent[];
}

export const LiveTicker: React.FC<LiveTickerProps> = ({ events }) => {
  const TICKER_SPEED_SECONDS = 80;
  const safeEvents = Array.isArray(events) ? events.filter(Boolean) : [];

  if (safeEvents.length === 0) return null;

  return (
    <div className="w-full bg-white dark:bg-[#050B1A] border-y border-[#1C3553]/50 h-[36px] overflow-hidden flex items-center relative z-30">
      {/* Oscilloscope trace bg */}
      <div className="absolute inset-0 opacity-[0.04] pointer-events-none" style={{
        backgroundImage: `repeating-linear-gradient(90deg, #22D3EE 0 1px, transparent 1px 32px), linear-gradient(to bottom, transparent 49%, rgba(34,211,238,0.18) 50%, transparent 51%)`,
        backgroundSize: '32px 100%'
      }} />
      <div className="shrink-0 bg-[#22D3EE] text-[#050B1A] mono text-[10px] font-bold px-3 h-full flex items-center gap-2 tracking-[0.12em]">
        <span className="w-1.5 h-1.5 rounded-full bg-white dark:bg-[#050B1A] animate-pulse" />
        LIVE_PULSE
        <span className="hidden md:inline opacity-60 font-normal">• {safeEvents.length} SIGNALS</span>
      </div>
      <div className="flex-1 overflow-hidden relative h-full flex items-center fade-edge-x">
        <div className="ticker-scroll flex whitespace-nowrap will-change-transform" style={{ animationDuration: `${TICKER_SPEED_SECONDS}s` }}>
          {[...safeEvents, ...safeEvents].map((event, idx) => (
            <span key={`${event.id}-${idx}`} className="inline-flex items-center gap-2.5 px-6 border-r border-[#1C3553]/30 last:border-0">
              <span className="mono text-[10px] tracking-[0.06em] text-[#475569]">{getRelativeTimeLabel(event.timestamp)}</span>
              <span className="w-1 h-1 rounded-full bg-[#E8A253]/60" />
              <span title={event.title} className="text-[12px] font-medium tracking-tight text-[#E2E8F0] max-w-[320px] truncate">
                {event.title || 'Untitled Signal'}
              </span>
              <SourceBadge source={event.source} size="sm" />
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
