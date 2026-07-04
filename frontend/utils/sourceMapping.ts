import { LucideIcon } from 'lucide-react';

export interface SourceConfig {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon?: LucideIcon;
  trustLevel: 'High' | 'Medium' | 'Low';
}

export const SOURCE_MAPPING: Record<string, SourceConfig> = {
  // New News APIs
  'NewsData.io': {
    label: 'NEWSDATA',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/20',
    trustLevel: 'High',
  },
  'newsdata': {
    label: 'NEWSDATA',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/20',
    trustLevel: 'High',
  },
  'newsdata.io': {
    label: 'NEWSDATA',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/20',
    trustLevel: 'High',
  },
  'NewsAPI': {
    label: 'NEWSAPI',
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/20',
    trustLevel: 'High',
  },
  'newsapi': {
    label: 'NEWSAPI',
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/20',
    trustLevel: 'High',
  },
  'newsapi.org': {
    label: 'NEWSAPI',
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/20',
    trustLevel: 'High',
  },
  'GNews': {
    label: 'GNEWS',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'Medium',
  },
  'gnews': {
    label: 'GNEWS',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'Medium',
  },
  'Mediastack': {
    label: 'MEDIASTACK',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/20',
    trustLevel: 'Medium',
  },
  'mediastack': {
    label: 'MEDIASTACK',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/20',
    trustLevel: 'Medium',
  },

  // Existing Sources
  'GDELT': {
    label: 'GDELT',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/20',
    trustLevel: 'Medium',
  },
  'gdelt': {
    label: 'GDELT',
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/20',
    trustLevel: 'Medium',
  },
  'HackerNews': {
    label: 'HACKERNEWS',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/20',
    trustLevel: 'Medium',
  },
  'hackernews': {
    label: 'HACKERNEWS',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/20',
    trustLevel: 'Medium',
  },

  // High Trust Sources
  'Reuters': {
    label: 'REUTERS',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'reuters': {
    label: 'REUTERS',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'Bloomberg': {
    label: 'BLOOMBERG',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'bloomberg': {
    label: 'BLOOMBERG',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'CNBC': {
    label: 'CNBC',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'cnbc': {
    label: 'CNBC',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'WSJ': {
    label: 'WSJ',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'wsj': {
    label: 'WSJ',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'Nikkei Asia': {
    label: 'NIKKEI',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },
  'nikkei asia': {
    label: 'NIKKEI',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
    trustLevel: 'High',
  },

  // Manual/System Sources
  'ManualInject': {
    label: 'MANUAL',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/20',
    trustLevel: 'Low',
  },
  'manualinject': {
    label: 'MANUAL',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/20',
    trustLevel: 'Low',
  },
  'PathwayTester': {
    label: 'TEST',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/20',
    trustLevel: 'Low',
  },
  'pathwaytester': {
    label: 'TEST',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/20',
    trustLevel: 'Low',
  },
  'SiliconWire': {
    label: 'SILICONWIRE',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/20',
    trustLevel: 'Low',
  },
  'siliconwire': {
    label: 'SILICONWIRE',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/20',
    trustLevel: 'Low',
  },
  'MarketWire': {
    label: 'MARKETWIRE',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/20',
    trustLevel: 'Low',
  },
  'marketwire': {
    label: 'MARKETWIRE',
    color: 'text-sky-400',
    bgColor: 'bg-sky-500/10',
    borderColor: 'border-sky-500/20',
    trustLevel: 'Low',
  },

  // Fallback for unknown sources
  'Unknown': {
    label: 'UNKNOWN',
    color: 'text-slate-400',
    bgColor: 'bg-slate-800',
    borderColor: 'border-slate-700',
    trustLevel: 'Low',
  },
  'unknown': {
    label: 'UNKNOWN',
    color: 'text-slate-400',
    bgColor: 'bg-slate-800',
    borderColor: 'border-slate-700',
    trustLevel: 'Low',
  },
};

export function getSourceConfig(sourceName: string | undefined | null): SourceConfig {
  if (!sourceName) {
    return SOURCE_MAPPING['Unknown'];
  }

  const normalizedKey = sourceName.toLowerCase().trim();
  return SOURCE_MAPPING[normalizedKey] || SOURCE_MAPPING['Unknown'];
}

export function getSourceLabel(sourceName: string | undefined | null): string {
  return getSourceConfig(sourceName).label;
}

export function getSourceColor(sourceName: string | undefined | null): string {
  return getSourceConfig(sourceName).color;
}

export function getSourceBgColor(sourceName: string | undefined | null): string {
  return getSourceConfig(sourceName).bgColor;
}

export function getSourceBorderColor(sourceName: string | undefined | null): string {
  return getSourceConfig(sourceName).borderColor;
}

export function getSourceTrustLevel(sourceName: string | undefined | null): 'High' | 'Medium' | 'Low' {
  return getSourceConfig(sourceName).trustLevel;
}

export function resolveTrustLevel(
  sourceName: string | undefined | null,
  backendTrustLevel?: string | null
): 'High' | 'Medium' | 'Low' {
  const normalizedKey = (sourceName || '').toLowerCase().trim();
  const mapped = SOURCE_MAPPING[normalizedKey];
  if (mapped) {
    return mapped.trustLevel;
  }

  if (backendTrustLevel === 'High' || backendTrustLevel === 'Medium' || backendTrustLevel === 'Low') {
    return backendTrustLevel;
  }

  return 'Low';
}