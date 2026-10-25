import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useSignalsWS } from '../../hooks/useSignalsWS';
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
      token: 'clerk-jwt-secret',
      enabled: true,
      onSignals: vi.fn(),
      baseUrl: 'https://api.example.test/api',
    }));

    await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
    expect(MockWebSocket.instances[0].url).toBe('wss://api.example.test/api/ws/signals?ticket=one-time-ticket');
    expect(MockWebSocket.instances[0].url).not.toContain('clerk-jwt-secret');
    unmount();
  });
});
