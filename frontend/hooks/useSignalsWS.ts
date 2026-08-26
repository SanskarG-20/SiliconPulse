import { useEffect, useRef, useState, useCallback } from 'react';

export type WSStatus = 'connecting' | 'open' | 'closed' | 'error';

interface WSSignalsMessage {
  type: 'signals' | 'pong';
  count?: number;
  events?: any[];
}

interface UseSignalsWSOptions {
  token: string | null;
  enabled: boolean;
  onSignals: (events: any[]) => void;
  onStatusChange?: (status: WSStatus) => void;
  // Derived from VITE_API_BASE_URL: http(s)://host/api -> ws(s)://host/api/ws/signals
  baseUrl?: string;
}

/**
 * Live WebSocket feed for signals.
 * - Connects to {baseUrl}/ws/signals?token=<jwt>
 * - Auto-reconnects with exponential backoff (2s -> 16s, max 5 tries per burst)
 * - Sends ping every 30s to keep alive
 * - Reports status so UI can fall back to SWR polling when closed/error
 */
export const useSignalsWS = ({
  token,
  enabled,
  onSignals,
  onStatusChange,
  baseUrl,
}: UseSignalsWSOptions) => {
  const [status, setStatus] = useState<WSStatus>('closed');
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const pingTimerRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const onSignalsRef = useRef(onSignals);
  onSignalsRef.current = onSignals;
  const onStatusRef = useRef(onStatusChange);
  onStatusRef.current = onStatusChange;

  const wsUrl = useCallback(() => {
    const base = (baseUrl || (import.meta as any).env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '');
    const wsBase = base.replace(/^http/, 'ws');
    return `${wsBase}/ws/signals${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }, [baseUrl, token]);

  const clearTimers = () => {
    if (pingTimerRef.current) { window.clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
    if (reconnectTimerRef.current) { window.clearTimeout(reconnectTimerRef.current); reconnectTimerRef.current = null; }
  };

  useEffect(() => {
    if (!enabled || !token) {
      setStatus('closed');
      onStatusRef.current?.('closed');
      return;
    }

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      try { wsRef.current?.close(); } catch {}
      setStatus('connecting');
      onStatusRef.current?.('connecting');
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        setStatus('open');
        onStatusRef.current?.('open');
        // keep-alive ping
        if (pingTimerRef.current) window.clearInterval(pingTimerRef.current);
        pingTimerRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 30000);
      };

      ws.onmessage = (ev) => {
        try {
          const msg: WSSignalsMessage = JSON.parse(ev.data);
          if (msg.type === 'signals' && Array.isArray(msg.events)) {
            onSignalsRef.current(msg.events);
          }
        } catch { /* ignore malformed */ }
      };

      ws.onclose = (ev) => {
        if (cancelled) return;
        setStatus('closed');
        onStatusRef.current?.('closed');
        if (ev.code === 4401) {
          // auth rejected - don't retry, SWR fallback will handle
          return;
        }
        // exponential backoff reconnect
        if (retryRef.current < 5) {
          const delay = Math.min(2000 * Math.pow(2, retryRef.current), 16000);
          retryRef.current += 1;
          reconnectTimerRef.current = window.setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        setStatus('error');
        onStatusRef.current?.('error');
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimers();
      try { wsRef.current?.close(); } catch {}
      wsRef.current = null;
    };
  }, [enabled, token, wsUrl]);

  return { status };
};
