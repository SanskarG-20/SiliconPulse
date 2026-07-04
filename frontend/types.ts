
export interface LiveEvent {
  id: string;
  timestamp: string;
  source: string;
  title: string;
  snippet?: string;
  url?: string;
  content: string;
  impactScore: number;
  company: string;
}

export interface EvidenceItem {
  timestamp?: string;
  source?: string;
  title: string;
  snippet: string;
  company?: string;
  event_type?: string;
  url?: string;
  event_id?: string;
}

export interface ConfidenceInfo {
  score: number;
  label: string;
  reason: string;
}

export interface QueryResponse {
  query: string;
  evidence: EvidenceItem[];
  signal_strength: number;
  last_updated: string;
  report: string | null;
  llm_status: 'pending' | 'completed' | 'failed';
  confidence?: ConfidenceInfo;
  stream_path_used?: string;
}

export enum ConfidenceLevel {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH'
}

export interface RadarStatus {
  company: string;
  status: 'High' | 'Moderate' | 'Low';
  trend: 'up' | 'down' | 'neutral';
}
