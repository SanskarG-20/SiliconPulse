/**
 * Frontend HTML sanitization — defense-in-depth for article rendering.
 * Mirrors backend/utils sanitize_content but lightweight for browser.
 * Decodes entities, strips <a href> tracking, removes raw tags.
 */

const TRACKING = new Set([
  'utm_source','utm_medium','utm_campaign','utm_term','utm_content','utm_id','utm_name',
  'utm_reader','utm_viz_id','fbclid','gclid','igshid','mc_eid','mkt_tok','_hsenc','_hsmi'
]);

function decodeEntities(str: string): string {
  if (!str || !str.includes('&')) return str;
  // Use DOMParser for robust entity decoding (handles &#x2F; etc.)
  try {
    const doc = new DOMParser().parseFromString(str, 'text/html');
    // Decode twice for double-encoded
    let prev = str;
    let cur = doc.documentElement.textContent || str;
    // DOMParser already decodes once; do extra pass via textarea
    const ta = document.createElement('textarea');
    for (let i=0;i<2;i++) {
      ta.innerHTML = cur;
      const decoded = ta.value;
      if (decoded === cur) break;
      cur = decoded;
    }
    // If still contains entities, fallback to textarea
    if (cur.includes('&') && cur.includes(';')) {
      ta.innerHTML = cur;
      cur = ta.value;
    }
    return cur;
  } catch {
    // Fallback regex
    return str.replace(/&#x2F;/gi, '/').replace(/&#47;/g, '/').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&apos;/g, "'");
  }
}

function cleanUrl(url: string): string {
  if (!url) return '';
  try {
    const decoded = decodeEntities(url).trim();
    const isTruncated = decoded.endsWith('...') || decoded.endsWith('…');
    const base = isTruncated ? decoded.slice(0, -3) : decoded;
    const parsed = new URL(base);
    if (!['http:', 'https:'].includes(parsed.protocol)) return '';
    // Strip tracking params
    const params = new URLSearchParams(parsed.search);
    let changed = false;
    for (const k of Array.from(params.keys())) {
      if (TRACKING.has(k.toLowerCase())) {
        params.delete(k);
        changed = true;
      }
    }
    parsed.search = params.toString() ? `?${params.toString()}` : '';
    let cleaned = parsed.toString();
    if (isTruncated && !cleaned.endsWith('...')) cleaned += '...';
    return cleaned;
  } catch {
    // If URL parsing fails (truncated mid-token), try to clean via regex
    try {
      return decodeEntities(url).replace(/([?&])(utm_[^&]+|fbclid[^&]*|gclid[^&]*)/gi, '').replace(/[?&]$/, '').replace(/\?&/, '?');
    } catch {
      return url;
    }
  }
}

function stripHtml(html: string): string {
  if (!html) return '';
  // Decode first
  let text = decodeEntities(html);
  // Replace anchors with href when display is truncated URL
  text = text.replace(/<a[^>]*href\s*=\s*["']([^"']+)["'][^>]*>(.*?)<\/a>/gi, (_m, href: string, display: string) => {
    const hrefClean = cleanUrl(href);
    const displayClean = stripHtml(display).trim();
    if (displayClean.startsWith('http') && displayClean.replace(/\.\.\.$/, '').length < hrefClean.length && hrefClean.toLowerCase().includes(displayClean.replace(/\.\.\.$/, '').toLowerCase())) {
      return hrefClean + ' ';
    }
    if (displayClean && displayClean !== hrefClean) return displayClean + ' ';
    return hrefClean + ' ';
  });
  // Handle malformed <a href="..."> without closing
  text = text.replace(/<a[^>]*href\s*=\s*["']?([^"'\s>]+)["']?[^>]*>?/gi, (_m, href: string) => cleanUrl(href) + ' ');

  // Replace block tags with space/newline
  text = text.replace(/<\/p\s*>/gi, '\n').replace(/<br\s*\/?>/gi, '\n').replace(/<\/div\s*>/gi, '\n').replace(/<li[^>]*>/gi, '• ');
  // Strip remaining tags (including malformed)
  text = text.replace(/<[^>]*>/g, ' ');
  // Remove any remaining stray < fragments
  text = text.replace(/<[^>\s]*/g, ' ');
  // Decode again
  text = decodeEntities(text);
  // Collapse whitespace
  text = text.replace(/\s+/g, ' ').replace(/\s*\n\s*/g, '\n').trim();
  // Clean URLs in text
  text = text.replace(/https?:\/\/[^\s"'<>]+/gi, (m) => cleanUrl(m));
  // Deduplicate consecutive duplicate URLs
  const parts = text.split(' ');
  const seen = new Set<string>();
  const deduped: string[] = [];
  for (const p of parts) {
    if (p.startsWith('http')) {
      try {
        const u = new URL(p.replace(/\.\.\.$/, ''));
        const key = `${u.hostname}${u.pathname}`.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
      } catch {}
    }
    deduped.push(p);
  }
  text = deduped.join(' ').replace(/\s+([.,;:!?])/g, '$1').replace(/\(\s+/g, '(').replace(/\s+\)/g, ')').trim();
  return text;
}

export function sanitizeContent(raw: string, maxLen = 800): string {
  if (!raw) return '';
  if (!raw.includes('<') && !raw.includes('&')) {
    // Plain text — just clean URLs and decode
    let decoded = decodeEntities(raw);
    decoded = decoded.replace(/https?:\/\/[^\s"'<>]+/gi, (m) => cleanUrl(m));
    decoded = decoded.replace(/\s+/g, ' ').trim();
    if (decoded.length > maxLen) {
      const sliced = decoded.slice(0, maxLen);
      const lastSpace = sliced.lastIndexOf(' ');
      return (lastSpace > 0 ? sliced.slice(0, lastSpace) : sliced) + '…';
    }
    return decoded;
  }
  let text = stripHtml(raw);
  if (text.length > maxLen) {
    const sliced = text.slice(0, maxLen);
    const lastSpace = sliced.lastIndexOf(' ');
    return (lastSpace > 0 ? sliced.slice(0, lastSpace) : sliced) + '…';
  }
  return text;
}

export function sanitizeTitle(raw: string): string {
  if (!raw) return '';
  let t = decodeEntities(raw);
  t = t.replace(/<[^>]*>/g, '');
  t = decodeEntities(t);
  t = t.replace(/\s+/g, ' ').trim();
  return t;
}

export function sanitizeUrl(raw: string): string {
  if (!raw) return '';
  const cleaned = cleanUrl(raw);
  return cleaned || raw;
}

export function extractCleanText(html: string): string {
  return stripHtml(html);
}
