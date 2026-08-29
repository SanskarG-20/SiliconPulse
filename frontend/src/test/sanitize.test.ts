import { describe, it, expect } from 'vitest';
import { sanitizeContent, sanitizeTitle, sanitizeUrl } from '../../utils/sanitize';

describe('frontend sanitize', () => {
  it('decodes and strips HackerNews anchor', () => {
    const raw = '<a href="https:&#x2F;&#x2F;www.theinformation.com&#x2F;articles&#x2F;nvidia?utm_campaign=a&amp;utm_content=b" rel="nofollow">https:&#x2F;&#x2F;www.theinformation.com&#x2F;articles&#x2F;nvidia...</a> (paywalled)';
    const cleaned = sanitizeContent(raw);
    expect(cleaned).not.toContain('<a href');
    expect(cleaned).not.toContain('&#x2F;');
    expect(cleaned).not.toContain('utm_');
    expect(cleaned).toContain('https://www.theinformation.com/articles/nvidia');
  });

  it('handles malformed truncated anchor', () => {
    const raw = 'Letter: <a href="https:&#x2F;&#x2F;x.com&#x2F;JensenHuang&#x2F;status&#x2F;2080643682';
    const cleaned = sanitizeContent(raw);
    expect(cleaned).not.toContain('href=');
    expect(cleaned).toContain('https://x.com/JensenHuang/status/2080643682');
  });

  it('strips <em> from titles', () => {
    expect(sanitizeTitle('<em>Nvidia</em> test')).toBe('Nvidia test');
  });

  it('cleans tracking params from URL', () => {
    expect(sanitizeUrl('https://example.com/path?utm_source=x&fbclid=123')).toBe('https://example.com/path');
  });
});
