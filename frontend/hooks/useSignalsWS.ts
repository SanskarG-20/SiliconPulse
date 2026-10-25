import { useEffect, useRef, useState, useCallback } from 'react';
import { createSignalsWsTicket } from '../api/siliconpulseApi';

export type WSStatus = 'connecting' | 'open' | 'closed' | 'error';

interface WSSignalsMessage {
  type: 'signals' | 'pong';
  count?: number;
  events?: any[];
  isAppend?: boolean;
}

interface UseSignalsWSOptions {
  enabled: boolean;
  onSignals: (events: any[], isAppend?: boolean) => void;
  onStatusChange?: (status: WSStatus) => void;
  // Derived from VITE_API_BASE_URL: http(s)://host/api -> ws(s)://host/api/ws/signals
  baseUrl?: string;
}

export const fallbackSignalPollInterval = (status: WSStatus): number => status === 'open' ? 0 : 5000;

/**
 * Live WebSocket feed for signals.
 * - Fetches a short-lived single-use ticket, then connects with that ticket.
 * - Auto-reconnects with exponential backoff (2s -> 16s, max 5 tries per burst)
 * - Sends ping every 30s to keep alive
 * - Reports status so UI can fall back to SWR polling when closed/error
 */
export const useSignalsWS = ({
  enabled,
  onSignals,
  onStatusChange,
  baseUrl,
}: UseSignalsWSOptions) => {
  const [status, setStatus] = useState<WSStatus>('closed');
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const pingTimerRef = useRef<number | null>(null);
  const pongTimeoutRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const onSignalsRef = useRef(onSignals);
  onSignalsRef.current = onSignals;
  const onStatusRef = useRef(onStatusChange);
  onStatusRef.current = onStatusChange;

  const wsUrl = useCallback((ticket: string) => {
    const base = (baseUrl || (import.meta as any).env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '');
    const wsBase = base.replace(/^http/, 'ws');
    return `${wsBase}/ws/signals?ticket=${encodeURIComponent(ticket)}`;
  }, [baseUrl]);

  const clearTimers = () => {
    if (pingTimerRef.current) { window.clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
    if (pongTimeoutRef.current) { window.clearTimeout(pongTimeoutRef.current); pongTimeoutRef.current = null; }
    if (reconnectTimerRef.current) { window.clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
  };

  useEffect(() => {
    if (!enabled) {
      setStatus('closed');
      onStatusRef.current?.('closed');
      return;
    }

    let cancelled = false;

    let connectWithRetry: () => void;
    const connect = async () => {
      if (cancelled) return;
      try { wsRef.current?.close(); } catch {}
      setStatus('connecting');
      onStatusRef.current?.('connecting');
      const ticket = await createSignalsWsTicket();
      if (cancelled) return;
      if (!ticket) throw new Error('Could not issue WebSocket ticket');
      const ws = new WebSocket(wsUrl(ticket));
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        setStatus('open');
        onStatusRef.current?.('open');
        // keep-alive ping
        if (pingTimerRef.current) window.clearInterval(pingTimerRef.current);
        pingTimerRef.current = window.setInterval(() => {
          if (ws.readyState !== WebSocket.OPEN) return;
          if (pongTimeoutRef.current) window.clearTimeout(pongTimeoutRef.current);
          ws.send('ping');
          pongTimeoutRef.current = window.setTimeout(() => {
            if (ws.readyState === WebSocket.OPEN) ws.close(4000, 'pong timeout');
          }, 10000);
        }, 30000);
      };

      ws.onmessage = (ev) => {
        try {
          const msg: WSSignalsMessage = JSON.parse(ev.data);
          if (msg.type === 'pong' && pongTimeoutRef.current) {
            window.clearTimeout(pongTimeoutRef.current);
            pongTimeoutRef.current = null;
          }
          if (msg.type === 'signals' && Array.isArray(msg.events)) {
            // Check if backend instructed to append (i.e. only new events sent)
            const isAppend = msg.isAppend === true;
            onSignalsRef.current(msg.events, isAppend);
          }
        } catch { /* ignore malformed */ }
      };

      ws.onclose = (ev) => {
        if (cancelled) return;
        setStatus('closed');
        onStatusRef.current?.('closed');
        // exponential backoff reconnect
        if (retryRef.current < 5) {
          const delay = Math.min(2000 * Math.pow(2, retryRef.current), 16000);
          retryRef.current += 1;
          reconnectTimerRef.current = window.setTimeout(connectWithRetry, delay);
        }
      };

      ws.onerror = () => {
        setStatus('error');
        onStatusRef.current?.('error');
      };
    };

    connectWithRetry = () => {
      connect().catch(() => {
        if (cancelled) return;
        setStatus('error');
        onStatusRef.current?.('error');
        if (retryRef.current < 5) {
          const delay = Math.min(2000 * Math.pow(2, retryRef.current), 16000);
          retryRef.current += 1;
          reconnectTimerRef.current = window.setTimeout(connectWithRetry, delay);
        }
      });
    };
    connectWithRetry();

    return () => {
      cancelled = true;
      clearTimers();
      try { wsRef.current?.close(); } catch {}
      wsRef.current = null;
    };
  }, [enabled, wsUrl]);

  return { status };
};
