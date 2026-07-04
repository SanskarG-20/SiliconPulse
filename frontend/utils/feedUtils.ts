import { LiveEvent } from '../types';

const normalizeText = (value?: string | null): string => (value ?? '').toString().trim();

export const parseTimestamp = (value?: string | null): number => {
  if (!value) {
    return Date.now();
  }

  const direct = Date.parse(value);
  if (!Number.isNaN(direct)) {
    return direct;
  }

  const normalized = value.replace(' ', 'T');
  const fallback = Date.parse(normalized);
  return Number.isNaN(fallback) ? Date.now() : fallback;
};

export const getRelativeTimeLabel = (value?: string | null): string => {
  const now = Date.now();
  const timestamp = parseTimestamp(value);
  const diffSeconds = Math.max(0, Math.floor((now - timestamp) / 1000));

  if (diffSeconds < 60) {
    return 'JUST NOW';
  }

  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) {
    return `${minutes}M AGO`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}H AGO`;
  }

  const days = Math.floor(hours / 24);
  return `${days}D AGO`;
};

const buildHeadlineKey = (event: LiveEvent): string => {
  const titleKey = normalizeText(event.title).toLowerCase();
  const urlKey = normalizeText(event.url).toLowerCase();
  return titleKey || urlKey || event.id;
};

const shuffleArray = <T>(items: T[]): T[] => {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
};

const avoidConsecutiveSources = (events: LiveEvent[]): LiveEvent[] => {
  if (events.length <= 1) {
    return events;
  }

  const groups = new Map<string, LiveEvent[]>();
  events.forEach((event) => {
    const sourceKey = normalizeText(event.source) || 'Unknown';
    if (!groups.has(sourceKey)) {
      groups.set(sourceKey, []);
    }
    groups.get(sourceKey)!.push(event);
  });

  const sources = Array.from(groups.keys());
  sources.forEach((source) => {
    const items = groups.get(source);
    if (items) {
      groups.set(source, shuffleArray(items));
    }
  });

  const result: LiveEvent[] = [];
  let lastSource: string | null = null;
  const remaining = () => Array.from(groups.values()).reduce((sum, items) => sum + items.length, 0);

  while (remaining() > 0) {
    const available = sources.filter((source) => (groups.get(source)?.length ?? 0) > 0 && source !== lastSource);
    const pool = available.length > 0
      ? available
      : sources.filter((source) => (groups.get(source)?.length ?? 0) > 0);

    if (!pool.length) {
      break;
    }

    const pick = pool[Math.floor(Math.random() * pool.length)];
    const bucket = groups.get(pick) ?? [];
    const next = bucket.shift();
    if (next) {
      result.push(next);
      lastSource = pick;
    }
  }

  if (result.length > 1 && result[0].source === result[result.length - 1].source) {
    const swapIndex = result.findIndex((item, idx) => idx > 0 && item.source !== result[0].source);
    if (swapIndex > 0) {
      [result[result.length - 1], result[swapIndex]] = [result[swapIndex], result[result.length - 1]];
    }
  }

  return result;
};

export const createLiveEvent = (raw: any, index: number): LiveEvent => {
  const title = normalizeText(raw?.title)
    || normalizeText(raw?.snippet)
    || normalizeText(raw?.content)
    || 'Untitled Signal';

  const timestamp = normalizeText(raw?.timestamp) || new Date().toISOString();

  return {
    id: raw?.event_id ? `event-${raw.event_id}` : `api-${timestamp}-${index}`,
    timestamp,
    source: normalizeText(raw?.source) || 'Unknown',
    title,
    snippet: normalizeText(raw?.snippet) || normalizeText(raw?.content) || '',
    url: normalizeText(raw?.url) || '',
    content: normalizeText(raw?.content) || normalizeText(raw?.snippet) || title,
    impactScore: typeof raw?.impactScore === 'number' ? raw.impactScore : 50,
    company: normalizeText(raw?.company) || 'Unknown',
  };
};

export const buildLiveFeed = (events: LiveEvent[], maxItems: number = 10): LiveEvent[] => {
  if (!events.length) {
    return [];
  }

  const sorted = [...events].sort((a, b) => parseTimestamp(b.timestamp) - parseTimestamp(a.timestamp));
  const unique: LiveEvent[] = [];
  const seen = new Set<string>();

  for (const event of sorted) {
    const key = buildHeadlineKey(event);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(event);
  }

  const latest = unique.slice(0, maxItems);
  const shuffled = shuffleArray(latest);
  return avoidConsecutiveSources(shuffled);
};

export const rotateFeed = (events: LiveEvent[], offset: number): LiveEvent[] => {
  if (!events.length) {
    return events;
  }

  const normalizedOffset = ((offset % events.length) + events.length) % events.length;
  return [...events.slice(normalizedOffset), ...events.slice(0, normalizedOffset)];
};
