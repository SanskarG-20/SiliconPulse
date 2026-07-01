
import React from 'react';
import { LiveEvent } from '../types';
import { SourceBadge } from './SourceBadge';
import { getRelativeTimeLabel } from '../utils/feedUtils';

interface LiveTickerProps {
  events: LiveEvent[];
}

export const LiveTicker: React.FC<LiveTickerProps> = ({ events }) => {
  // Tweak this to control scroll speed (seconds)
  const TICKER_SPEED_SECONDS = 100;
  const safeEvents = Array.isArray(events) ? events.filter(Boolean) : [];

  return (
    <div className="w-full bg-slate-950/80 border-y border-slate-800 h-10 overflow-hidden flex items-center relative z-30">
      <div className="bg-sky-500 text-white text-[9px] font-black px-3 md:px-4 h-full flex items-center z-40 whitespace-nowrap tracking-tighter shadow-[5px_0_15px_rgba(0,0,0,0.5)]">
        LIVE_PULSE
      </div>
      <div className="flex-1 overflow-x-auto md:overflow-hidden relative h-full flex items-center fade-edge-x no-scrollbar touch-pan-x">
        <div
          className="ticker-scroll flex space-x-8 md:space-x-16 whitespace-nowrap pl-4 md:pl-8"
          style={{ animationDuration: `${TICKER_SPEED_SECONDS}s` }}
        >
          {[...safeEvents, ...safeEvents].map((event, idx) => (
            <div key={`${event.id}-${idx}-${idx >= safeEvents.length ? 'copy' : 'orig'}`} className="flex items-center space-x-2 md:space-x-3 text-[11px] md:text-[13px]">
              <span className="text-slate-500 font-mono text-[9px] md:text-[11px] font-medium tracking-tight">
                {getRelativeTimeLabel(event.timestamp)}
              </span>
              <span title={event.title} className="text-slate-100 font-semibold tracking-tight max-w-[220px] md:max-w-[360px] truncate">
                {event.title || 'Untitled Signal'}
              </span>
              <SourceBadge source={event.source} size="sm" />
              <span className="w-1 h-1 bg-slate-700 rounded-full mx-1 md:mx-2"></span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
