import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { fallbackSignalPollInterval, useSignalsWS } from '../../hooks/useSignalsWS';
import { createSignalsWsTicket } from '../../api/siliconpulseApi';

vi.mock('../../api/siliconpulseApi', () => ({
  createSignalsWsTicket: vi.fn(),
}));

class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];
  readyState = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  constructor(public url: string) { MockWebSocket.instances.push(this); }
  send() {}
  close() {}
}

describe('useSignalsWS credentials', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    MockWebSocket.instances = [];
  });

  it('places a short-lived ticket in the WebSocket URL instead of the Clerk JWT', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.mocked(createSignalsWsTicket).mockResolvedValue('one-time-ticket');
    const { unmount } = renderHook(() => useSignalsWS({
      enabled: true,
      onSignals: vi.fn(),
      baseUrl: 'https://api.example.test/api',
    }));

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    expect(MockWebSocket.instances[0].url).toBe('wss://api.example.test/api/ws/signals?ticket=one-time-ticket');
    expect(MockWebSocket.instances[0].url).not.toContain('clerk-jwt-secret');
    unmount();
  });

  it('keeps one socket when auth tokens refresh and pauses polling only while open', async () => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.mocked(createSignalsWsTicket).mockResolvedValue('one-time-ticket');
    const { rerender, unmount } = renderHook(({ ready }: { ready: boolean }) => useSignalsWS({
      enabled: ready,
      onSignals: vi.fn(),
    }), { initialProps: { ready: true } });
    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    rerender({ ready: true });
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(fallbackSignalPollInterval('open')).toBe(0);
    expect(fallbackSignalPollInterval('connecting')).toBe(5000);
    expect(fallbackSignalPollInterval('closed')).toBe(5000);
    act(() => MockWebSocket.instances[0].onopen?.(new Event('open')));
    unmount();
  });
});
