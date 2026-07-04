import { LiveEvent } from '../types';

export interface RecommendationItem {
  label: string;
  query: string;
  icon?: string;
  color?: string;
  category?: string;
}

type CategoryKey =
  | 'semiconductors'
  | 'aiInfrastructure'
  | 'supplyChain'
  | 'productLaunch'
  | 'foundryUpdates'
  | 'datacenterHardware'
  | 'enterpriseTech'
  | 'globalNews';

type CategoryPool = {
  key: CategoryKey;
  icon: string;
  color: string;
  templates: Array<(company?: string) => RecommendationItem>;
};

const SEMI_COMPANIES = ['NVIDIA', 'AMD', 'Intel', 'TSMC'];
const AI_ENTERPRISE = ['Google', 'OpenAI', 'Microsoft', 'Anthropic', 'Meta', 'Amazon', 'Mistral'];
const ALL_COMPANIES = [...SEMI_COMPANIES, ...AI_ENTERPRISE];

const CATEGORY_POOLS: CategoryPool[] = [
  {
    key: 'semiconductors',
    icon: 'Zap',
    color: 'text-amber-400',
    templates: [
      (company) => ({
        label: `${company ?? 'Semiconductor'} Momentum`,
        query: `What changed in ${company ?? 'the semiconductor'} roadmap or capacity in the last 24 hours?`,
        icon: 'Zap',
        color: 'text-amber-400',
        category: 'semiconductors',
      }),
      (company) => ({
        label: `${company ?? 'Foundry'} Signal Check`,
        query: `Any contract wins, yield signals, or customer shifts for ${company ?? 'leading foundries'} today?`,
        icon: 'Zap',
        color: 'text-amber-400',
        category: 'semiconductors',
      }),
    ],
  },
  {
    key: 'aiInfrastructure',
    icon: 'Cpu',
    color: 'text-sky-400',
    templates: [
      (company) => ({
        label: `${company ?? 'AI'} Infrastructure Moves`,
        query: `Which AI infrastructure moves are emerging for ${company ?? 'hyperscalers'} right now?`,
        icon: 'Cpu',
        color: 'text-sky-400',
        category: 'aiInfrastructure',
      }),
      (company) => ({
        label: `${company ?? 'AI'} Compute Signals`,
        query: `Any cluster expansions, model launches, or spend signals tied to ${company ?? 'AI platforms'}?`,
        icon: 'Cpu',
        color: 'text-sky-400',
        category: 'aiInfrastructure',
      }),
    ],
  },
  {
    key: 'supplyChain',
    icon: 'ShieldAlert',
    color: 'text-red-400',
    templates: [
      (company) => ({
        label: 'Supply Chain Watch',
        query: `Any supply chain bottlenecks or export controls impacting ${company ?? 'GPU and accelerator'} availability?`,
        icon: 'ShieldAlert',
        color: 'text-red-400',
        category: 'supplyChain',
      }),
      () => ({
        label: 'HBM & Packaging Pulse',
        query: 'Are there new HBM, CoWoS, or advanced packaging constraints today?',
        icon: 'ShieldAlert',
        color: 'text-red-400',
        category: 'supplyChain',
      }),
    ],
  },
  {
    key: 'productLaunch',
    icon: 'CheckCircle2',
    color: 'text-emerald-400',
    templates: [
      () => ({
        label: 'Launch Radar',
        query: 'Which AI chip, platform, or datacenter product launches surfaced in the last 48 hours?',
        icon: 'CheckCircle2',
        color: 'text-emerald-400',
        category: 'productLaunch',
      }),
      (company) => ({
        label: `${company ?? 'Vendor'} Roadmap Drops`,
        query: `Any fresh roadmap reveals or product announcements tied to ${company ?? 'key vendors'}?`,
        icon: 'CheckCircle2',
        color: 'text-emerald-400',
        category: 'productLaunch',
      }),
    ],
  },
  {
    key: 'foundryUpdates',
    icon: 'Activity',
    color: 'text-emerald-400',
    templates: [
      () => ({
        label: 'Foundry Node Update',
        query: 'Foundry updates: yield shifts, node progress, or capacity moves for TSMC / Intel?',
        icon: 'Activity',
        color: 'text-emerald-400',
        category: 'foundryUpdates',
      }),
      (company) => ({
        label: `${company ?? 'Foundry'} Yield Watch`,
        query: `Any yield or process node developments around ${company ?? 'leading foundries'}?`,
        icon: 'Activity',
        color: 'text-emerald-400',
        category: 'foundryUpdates',
      }),
    ],
  },
  {
    key: 'datacenterHardware',
    icon: 'TrendingUp',
    color: 'text-indigo-400',
    templates: [
      () => ({
        label: 'Datacenter Hardware Pulse',
        query: 'Datacenter hardware updates: GPUs, networking, power, or cooling signals today?',
        icon: 'TrendingUp',
        color: 'text-indigo-400',
        category: 'datacenterHardware',
      }),
      () => ({
        label: 'Server Refresh Signals',
        query: 'Any signs of hyperscaler server refresh cycles or new hardware deployments?',
        icon: 'TrendingUp',
        color: 'text-indigo-400',
        category: 'datacenterHardware',
      }),
    ],
  },
  {
    key: 'enterpriseTech',
    icon: 'Layers',
    color: 'text-slate-300',
    templates: [
      (company) => ({
        label: 'Enterprise Signal Check',
        query: `Enterprise tech moves: cloud spend shifts, platform wins, or security signals tied to ${company ?? 'major vendors'}?`,
        icon: 'Layers',
        color: 'text-slate-300',
        category: 'enterpriseTech',
      }),
    ],
  },
  {
    key: 'globalNews',
    icon: 'AlertCircle',
    color: 'text-amber-400',
    templates: [
      () => ({
        label: 'Global Policy Watch',
        query: 'Any global policy, subsidy, or export-control headlines affecting semiconductors today?',
        icon: 'AlertCircle',
        color: 'text-amber-400',
        category: 'globalNews',
      }),
      () => ({
        label: 'Geopolitical Risk Pulse',
        query: 'Which geopolitical updates could impact chip supply chains this week?',
        icon: 'AlertCircle',
        color: 'text-amber-400',
        category: 'globalNews',
      }),
    ],
  },
];

const TOPIC_KEYWORDS: Record<CategoryKey, string[]> = {
  semiconductors: ['chip', 'semiconductor', 'foundry', 'fab', 'wafer', 'node', 'nm', 'yield', 'tsmc', 'intel', 'nvidia', 'amd'],
  aiInfrastructure: ['ai', 'model', 'llm', 'inference', 'training', 'gpu', 'accelerator', 'cluster', 'datacenter', 'data center'],
  supplyChain: ['supply', 'shortage', 'export', 'tariff', 'capacity', 'hbm', 'cowos', 'packaging', 'substrate'],
  productLaunch: ['launch', 'unveil', 'announce', 'release', 'roadmap', 'debut'],
  foundryUpdates: ['foundry', 'fab', 'node', 'process', 'yield', 'wafer'],
  datacenterHardware: ['server', 'rack', 'network', 'switch', 'infiniband', 'ethernet', 'power', 'cooling', 'optics'],
  enterpriseTech: ['enterprise', 'cloud', 'saas', 'platform', 'security', 'compliance'],
  globalNews: ['policy', 'subsidy', 'sanction', 'geopolitical', 'government', 'regulator', 'export control', 'tariff'],
};

const normalize = (value: string | undefined | null) => (value ?? '').toLowerCase();

const buildKey = (rec: RecommendationItem) => `${rec.label}|${rec.query}`.toLowerCase();

const uniqueArray = <T>(items: T[]): T[] => Array.from(new Set(items));

const pickRandom = <T>(items: T[], count: number): T[] => {
  const pool = [...items];
  const picks: T[] = [];
  while (pool.length && picks.length < count) {
    const index = Math.floor(Math.random() * pool.length);
    picks.push(pool.splice(index, 1)[0]);
  }
  return picks;
};

const extractActiveCompanies = (events: LiveEvent[]): string[] => {
  const counts = new Map<string, number>();
  const text = events.map((event) => `${event.title} ${event.snippet ?? ''} ${event.company ?? ''}`).join(' ').toLowerCase();

  ALL_COMPANIES.forEach((company) => {
    const key = company.toLowerCase();
    if (text.includes(key)) {
      counts.set(company, (counts.get(company) ?? 0) + 1);
    }
  });

  events.forEach((event) => {
    const company = event.company?.trim();
    if (company) {
      counts.set(company, (counts.get(company) ?? 0) + 1);
    }
  });

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([company]) => company)
    .slice(0, 4);
};

const detectCategories = (events: LiveEvent[]): CategoryKey[] => {
  const text = normalize(events.map((event) => `${event.title} ${event.snippet ?? ''} ${event.company ?? ''}`).join(' '));
  const scores: Array<[CategoryKey, number]> = CATEGORY_POOLS.map((pool) => {
    const keywords = TOPIC_KEYWORDS[pool.key] ?? [];
    const score = keywords.reduce((acc, keyword) => (text.includes(keyword) ? acc + 1 : acc), 0);
    return [pool.key, score];
  });

  return scores
    .filter(([, score]) => score > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([key]) => key);
};

const normalizeRemote = (items: any[]): RecommendationItem[] => {
  return items
    .map((item, index) => {
      const query = item?.query || item?.text || item?.prompt || item?.label || '';
      if (!query) {
        return null;
      }
      return {
        label: item?.label || item?.title || `Signal ${index + 1}`,
        query,
        icon: item?.icon,
        color: item?.color,
        category: 'remote',
      } as RecommendationItem;
    })
    .filter(Boolean) as RecommendationItem[];
};

export const generateRecommendationsFromFeed = (
  events: LiveEvent[],
  previousKeys: Set<string>,
  remoteRecommendations: any[] = [],
  maxItems: number = 4
): { recommendations: RecommendationItem[]; nextKeys: Set<string> } => {
  const activeCompanies = extractActiveCompanies(events);
  const companyPool = activeCompanies.length ? activeCompanies : pickRandom(ALL_COMPANIES, 4);
  const detected = detectCategories(events);
  const orderedCategories = uniqueArray([
    ...detected,
    'semiconductors',
    'aiInfrastructure',
    'supplyChain',
    'productLaunch',
    'foundryUpdates',
    'datacenterHardware',
    'enterpriseTech',
    'globalNews',
  ]) as CategoryKey[];

  const candidates: RecommendationItem[] = [];
  orderedCategories.forEach((category) => {
    const pool = CATEGORY_POOLS.find((item) => item.key === category);
    if (!pool) {
      return;
    }
    const company = companyPool[Math.floor(Math.random() * companyPool.length)];
    const template = pool.templates[Math.floor(Math.random() * pool.templates.length)];
    candidates.push(template(company));
  });

  candidates.push(...normalizeRemote(remoteRecommendations));

  const uniqueCandidates = candidates.filter((candidate, index, self) =>
    self.findIndex((item) => buildKey(item) === buildKey(candidate)) === index
  );

  const fresh = uniqueCandidates.filter((candidate) => !previousKeys.has(buildKey(candidate)));
  const fallback = uniqueCandidates;

  const pool = fresh.length >= maxItems ? fresh : uniqueArray([...fresh, ...fallback]);
  const selected = pickRandom(pool, maxItems);

  const nextKeys = new Set<string>();
  selected.forEach((rec) => nextKeys.add(buildKey(rec)));

  return { recommendations: selected, nextKeys };
};

export const getRecommendationCategoryPool = () => CATEGORY_POOLS.map((pool) => pool.key);
