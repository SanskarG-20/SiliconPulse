import { afterEach, describe, expect, it, vi } from 'vitest';
import { generateInsight, setAuthTokenGetter } from '../../api/siliconpulseApi';

describe('generateInsight SSE', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setAuthTokenGetter(null);
  });

  it('parses streamed deltas and returns the final report', async () => {
    const events = [
      'event: status\ndata: {"stage":"generating"}\n\n',
      'event: delta\ndata: {"text":"{\\"sections\\":"}\n\n',
      'event: delta\ndata: {"text":"[]}"}\n\n',
      'event: done\ndata: {"insight":"{\\"sections\\":[]}"}\n\n',
    ].join('');
    const encoder = new TextEncoder();
    const response = new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(events.slice(0, 31)));
        controller.enqueue(encoder.encode(events.slice(31)));
        controller.close();
      },
    }), { headers: { 'content-type': 'text/event-stream' } });
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal('fetch', fetchMock);
    setAuthTokenGetter(async () => 'test-token');
    const chunks: string[] = [];

    const result = await generateInsight('NVIDIA', 'evidence', (chunk) => chunks.push(chunk));

    expect(result).toBe('{"sections":[]}');
    expect(chunks).toEqual(['{"sections":', '{"sections":[]}', '{"sections":[]}']);
    expect(fetchMock.mock.calls[0][1].headers.Accept).toBe('text/event-stream');
  });
});
