import { sanitizeContent as _sanitizeContent, sanitizeTitle as _sanitizeTitle, sanitizeUrl as _sanitizeUrl } from '../utils/sanitize';
export const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api").replace(/\/$/, "");
export const IS_LOCALHOST_API = BASE_URL.includes("127.0.0.1") || BASE_URL.includes("localhost");
export const IS_PROD = typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1";
export const SHOULD_WARN_LOCALHOST_IN_PROD = IS_PROD && IS_LOCALHOST_API;
// Render free tier needs ~30s to wake up
const DEFAULT_TIMEOUT_MS = 15000;
const QUERY_TIMEOUT_MS = 20000;
const INSIGHT_TIMEOUT_MS = 30000;
const HEALTH_TIMEOUT_MS = 30000;

type AuthTokenGetter = (() => Promise<string | null>) | null;
let authTokenGetter: AuthTokenGetter = null;

export const setAuthTokenGetter = (getter: AuthTokenGetter): void => {
    authTokenGetter = getter;
};

const getAuthHeaders = async (): Promise<Record<string, string>> => {
    if (!authTokenGetter) return {};
    const token = await authTokenGetter();
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
};

const withTimeout = async (
    request: Promise<Response>,
    controller: AbortController,
    timeoutMs: number
): Promise<Response> => {
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
        return await request;
    } finally {
        window.clearTimeout(timeoutId);
    }
};

const apiFetch = async (path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Response> => {
    const authHeaders = await getAuthHeaders();
    const controller = new AbortController();
    const headers = {
        ...(init.headers || {}),
        ...authHeaders,
    };

    return withTimeout(fetch(`${BASE_URL}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
    }), controller, timeoutMs);
};

export const createSignalsWsTicket = async (): Promise<string | null> => {
    try {
        const response = await apiFetch('/auth/ws-ticket', { method: 'POST' });
        if (!response.ok) return null;
        const data = await parseJsonSafely(response, { ticket: '' });
        return typeof (data as any)?.ticket === 'string' ? (data as any).ticket : null;
    } catch {
        return null;
    }
};

const parseJsonSafely = async <T>(response: Response, fallback: T): Promise<T> => {
    try {
        return await response.json();
    } catch {
        return fallback;
    }
};
const _cleanEvidence = (item: any): any => {
  if (!item || typeof item !== 'object') return item;
  const out: any = { ...item };
  if (typeof out.title === 'string') out.title = _sanitizeTitle(out.title);
  if (typeof out.snippet === 'string') out.snippet = _sanitizeContent(out.snippet, 500);
  if (typeof out.content === 'string') out.content = _sanitizeContent(out.content, 800);
  if (typeof out.source === 'string') out.source = _sanitizeTitle(out.source);
  if (typeof out.company === 'string') out.company = _sanitizeTitle(out.company);
  if (typeof out.url === 'string') out.url = _sanitizeUrl(out.url) || out.url;
  return out;
};
const normalizeEvidence = (value: any): any[] => Array.isArray(value) ? value.map(_cleanEvidence) : [];

import { QueryResponse as QueryResponseType } from '../types';

export type QueryResponse = QueryResponseType;

export interface InjectResponse {
    status: string;
    injected_at: string;
}

const normalizeQueryResponse = (data: any, query: string): QueryResponse => ({
    query: data?.query || query,
    evidence: normalizeEvidence(data?.evidence),
    signal_strength: Number.isFinite(Number(data?.signal_strength)) ? Number(data.signal_strength) : 0,
    last_updated: data?.last_updated || new Date().toISOString(),
    report: data?.report ?? null,
    llm_status: data?.llm_status || "pending",
});

const normalizeError = (error: any): Error => {
    if (error?.name === "AbortError") {
        if (SHOULD_WARN_LOCALHOST_IN_PROD) {
            return new Error(`Backend timed out (tried ${BASE_URL}). You're in production but VITE_API_BASE_URL points to localhost. Set it to your Render URL in Vercel env vars.`);
        }
        return new Error(`Backend timed out (tried ${BASE_URL}). Render free tier may be waking up — retrying automatically.`);
    }
    if (error?.name === "TypeError" && error?.message === "Failed to fetch") {
        if (SHOULD_WARN_LOCALHOST_IN_PROD) {
            return new Error(`Backend offline (tried ${BASE_URL}). VITE_API_BASE_URL is localhost in production. Set VITE_API_BASE_URL=https://your-backend.onrender.com/api in Vercel.`);
        }
        return new Error(`Backend offline (tried ${BASE_URL}). Render may be waking up (30-50s). Retrying automatically...`);
    }
    return error instanceof Error ? error : new Error(`Unexpected API failure (tried ${BASE_URL}).`);
};

export const checkBackendHealth = async (): Promise<boolean> => {
    const healthUrl = `${BASE_URL.replace('/api', '')}/health`;
    // Retry 3 times for Render wake-up (30s total)
    for (let attempt = 0; attempt < 3; attempt++) {
        try {
            const controller = new AbortController();
            const response = await withTimeout(fetch(healthUrl, { signal: controller.signal }), controller, HEALTH_TIMEOUT_MS);
            if (response.ok) return true;
        } catch {}
        if (attempt < 2) await new Promise(r => setTimeout(r, 5000));
    }
    return false;
};

export const waitForBackend = async (onRetry?: (attempt: number) => void): Promise<boolean> => {
    for (let i = 0; i < 6; i++) {
        const ok = await checkBackendHealth();
        if (ok) return true;
        onRetry?.(i + 1);
        await new Promise(r => setTimeout(r, 5000));
    }
    return false;
};

export const bootstrapSystem = async (): Promise<any> => {
    try {
        const response = await apiFetch(`/bootstrap`, { method: "POST" }, 15000);
        return await parseJsonSafely(response, { status: "error" });
    } catch {
        return { status: "error" };
    }
};

export const syncAuthenticatedUser = async (): Promise<any> => {
    const response = await apiFetch(`/auth/me`);
    if (!response.ok) {
        throw new Error(`Failed to sync authenticated user. Status: ${response.status}`);
    }
    return parseJsonSafely(response, { authenticated: false });
};

export const querySiliconPulse = async (query: string, k: number = 5): Promise<QueryResponse> => {
    try {
        const response = await apiFetch(`/query`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ query, k }),
        }, QUERY_TIMEOUT_MS);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await parseJsonSafely(response, {});
        return normalizeQueryResponse(data, query);
    } catch (error: any) {
        throw normalizeError(error);
    }
};

export const injectSignal = async (title: string, content: string, source: string = "ManualInject"): Promise<InjectResponse> => {
    try {
        const response = await apiFetch(`/inject`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ title, content, source }),
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await parseJsonSafely(response, { status: "success", injected_at: new Date().toISOString() });
    } catch (error) {
        throw normalizeError(error);
    }
};

export const fetchSignals = async (): Promise<any[]> => {
    try {
        const response = await apiFetch(`/signals`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await parseJsonSafely(response, []);
        return Array.isArray(data) ? data.map(_cleanEvidence) : [];
    } catch {
        return [];
    }
};

export const fetchRadar = async (): Promise<any[]> => {
    try {
        const response = await apiFetch(`/radar`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await parseJsonSafely(response, []);
        return Array.isArray(data) ? data.map(_cleanEvidence) : [];
    } catch {
        return [];
    }
};

export const formatEvidenceToContext = (evidence: any[]): string => {
    const safeEvidence = normalizeEvidence(evidence);
    if (safeEvidence.length === 0) return "";

    let context = "LIVE UPDATES CONTEXT:\n";
    safeEvidence.forEach(item => {
        context += `[${item?.timestamp || 'N/A'} | ${item?.source || 'Unknown'}] ${item?.title || 'Untitled'}\n`;
        context += `Company: ${item?.company || 'N/A'} | Event: ${item?.event_type || 'General'}\n`;
        context += `Snippet: ${item?.snippet || item?.content || ''}\n\n`;
        if (item?.url) context += `URL: ${item.url}\n`;
    });

    return context;
};

export const generateInsight = async (query: string, context: string, onChunk?: (chunk: string) => void): Promise<string> => {
    try {
        const response = await apiFetch(`/generate`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ query, context }),
        }, INSIGHT_TIMEOUT_MS);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("text/plain")) {
            // Handle streaming text
            if (!response.body) throw new Error("ReadableStream not yet supported in this browser.");
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                if (value) {
                    const chunk = decoder.decode(value, { stream: true });
                    fullText += chunk;
                    if (onChunk) onChunk(fullText);
                }
            }
            // Final decode
            const lastChunk = decoder.decode();
            if (lastChunk) {
                fullText += lastChunk;
                if (onChunk) onChunk(fullText);
            }
            return fullText || "Insight generation returned an empty response.";
        } else {
            // Handle legacy JSON object response
            const data = await parseJsonSafely(response, { insight: "" });
            const insightText = data?.insight || "Insight generation returned an empty response.";
            if (onChunk) onChunk(insightText);
            return insightText;
        }
    } catch (error: any) {
        // Surface the actual failure mode instead of a generic line: timeouts
        // (slow/quota-hit Gemini cascade) need different user action than HTTP errors.
        if (error?.name === "AbortError") {
            return "Insight generation timed out after 30 seconds — Gemini is slow or over quota. The evidence above is still live. Wait a moment, then try again.";
        }
        const status = error?.message?.match(/status:\s*(\d{3})/)?.[1];
        if (status === "429") {
            return "Insight request failed (429): Gemini quota exceeded. The evidence above is still live. Wait a minute, then try again.";
        }
        if (status === "401" || status === "403") {
            return "Insight request failed: authentication expired. Sign out and back in, then try again.";
        }
        if (status) {
            return `Insight request failed (HTTP ${status}). The evidence above is still live. Try again.`;
        }
        return "Insight generation unavailable. Please try again later.";
    }
};

export const fetchRecommendations = async (): Promise<any[]> => {
    try {
        const response = await apiFetch(`/recommendations`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await parseJsonSafely(response, { recommended_queries: [] });
        return Array.isArray(data?.recommended_queries) ? data.recommended_queries : [];
    } catch {
        return [];
    }
};

export const exportAnalysis = async (
    query: string,
    report: string,
    evidence: any[],
    format: string,
    include_evidence: boolean = true
): Promise<void> => {
    try {
        const response = await apiFetch(`/export`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ query, report, evidence: normalizeEvidence(evidence), format, include_evidence }),
        }, 15000);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `siliconpulse_report_${Date.now()}.${format}`;
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
            if (filenameMatch && filenameMatch.length === 2) {
                filename = filenameMatch[1];
            }
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        throw normalizeError(error);
    }
};

export const verifySources = async (query: string): Promise<any> => {
    try {
        const response = await apiFetch(`/sources/verify?query=${encodeURIComponent(query)}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await parseJsonSafely(response, { query, sources: [] });
        return {
            query: data?.query || query,
            sources: Array.isArray(data?.sources) ? data.sources : [],
        };
    } catch (error) {
        throw normalizeError(error);
    }
};

export const fetchGraphExplain = async (company: string, depth: number = 2): Promise<any | null> => {
    try {
        const response = await apiFetch(`/graph/explain/${encodeURIComponent(company)}?depth=${depth}`);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const fetchGraphImpact = async (company: string, depth: number = 2): Promise<any | null> => {
    try {
        const response = await apiFetch(`/graph/impact/${encodeURIComponent(company)}?depth=${depth}`);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const simulateGraph = async (company: string, shock: number, depth: number = 2, metric: string = "yield"): Promise<any | null> => {
    try {
        const response = await apiFetch(`/graph/simulate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ company, shock, depth, metric }),
        });
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const fetchMetrics = async (): Promise<any | null> => {
    try {
        const base = BASE_URL.replace('/api', '');
        const response = await withTimeout(fetch(`${base}/metrics`), new AbortController(), 5000);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const uploadPdf = async (file: File): Promise<any> => {
    const form = new FormData();
    form.append('file', file);
    // Don't set Content-Type — browser will set multipart boundary
    const response = await apiFetch(`/ingest/pdf`, { method: 'POST', body: form }, 60000);
    if (!response.ok) {
        const err = await parseJsonSafely(response, { detail: response.statusText });
        throw new Error((err as any)?.detail || `Upload failed: ${response.status}`);
    }
    return parseJsonSafely(response, {});
};

export const triggerSecIngest = async (daysBack: number = 3): Promise<any> => {
    const response = await apiFetch(`/ingest/sec?days_back=${daysBack}`, { method: 'POST' }, 60000);
    if (!response.ok) {
        const err = await parseJsonSafely(response, { detail: response.statusText });
        throw new Error((err as any)?.detail || `SEC ingest failed: ${response.status}`);
    }
    return parseJsonSafely(response, {});
};

export const fetchWatchlist = async (): Promise<{ companies: string[]; persisted: boolean }> => {
    try {
        const response = await apiFetch(`/watchlist`);
        if (!response.ok) return { companies: [], persisted: false };
        const data = await parseJsonSafely(response, { companies: [], persisted: false });
        return { companies: Array.isArray((data as any)?.companies) ? (data as any).companies : [], persisted: !!(data as any)?.persisted };
    } catch {
        return { companies: [], persisted: false };
    }
};

export const addWatchlistCompany = async (company: string): Promise<string[]> => {
    try {
        const response = await apiFetch(`/watchlist`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ company }) });
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { companies: [] });
        return Array.isArray((data as any)?.companies) ? (data as any).companies : [];
    } catch {
        return [];
    }
};

export const removeWatchlistCompany = async (company: string): Promise<string[]> => {
    try {
        const response = await apiFetch(`/watchlist/${encodeURIComponent(company)}`, { method: 'DELETE' });
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { companies: [] });
        return Array.isArray((data as any)?.companies) ? (data as any).companies : [];
    } catch {
        return [];
    }
};

export const fetchWatchlistAlerts = async (limit = 10): Promise<{ alerts: any[]; companies: string[] }> => {
    try {
        const response = await apiFetch(`/watchlist/alerts?limit=${limit}`);
        if (!response.ok) return { alerts: [], companies: [] };
        const data = await parseJsonSafely(response, { alerts: [], companies: [] });
        return { alerts: Array.isArray((data as any)?.alerts) ? (data as any).alerts : [], companies: (data as any)?.companies || [] };
    } catch {
        return { alerts: [], companies: [] };
    }
};

export const shareBrief = async (query: string, insight: string, evidence: any[]): Promise<{ id: string; path: string } | null> => {
    try {
        const response = await apiFetch(`/briefs/share`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, insight, evidence: (evidence || []).slice(0, 20) }),
        });
        if (!response.ok) return null;
        const data = await parseJsonSafely(response, null);
        if (!data || !(data as any)?.id) return null;
        return { id: (data as any).id, path: (data as any).path || `/b/${(data as any).id}` };
    } catch {
        return null;
    }
};

export const fetchPublicBrief = async (id: string): Promise<any | null> => {
    try {
        const base = BASE_URL.replace('/api', '');
        const response = await fetch(`${base}/api/briefs/public/${encodeURIComponent(id)}`);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const fetchQueryHistory = async (limit = 8): Promise<any[]> => {
    try {
        const response = await apiFetch(`/history/queries?limit=${limit}`);
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { items: [] });
        return Array.isArray((data as any)?.items) ? (data as any).items : [];
    } catch {
        return [];
    }
};

export const fetchTrends = async (company?: string, days: number = 30): Promise<any | null> => {
    try {
        const params = new URLSearchParams();
        if (company) params.append('company', company);
        params.append('days', String(Math.max(1, Math.min(days, 90))));
        const response = await apiFetch(`/trends?${params.toString()}`);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const fetchCompare = async (companies: string[], query = '', k = 5, depth = 2): Promise<any | null> => {
    try {
        const response = await apiFetch(`/compare`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ companies, query, k, depth }),
        }, 30000);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const fetchDigestPrefs = async (): Promise<any> => {
    try {
        const response = await apiFetch(`/digest/prefs`);
        if (!response.ok) return { enabled: false, hour_utc: 11, email: '', webhook_url: '', persisted: false };
        return await parseJsonSafely(response, { enabled: false, hour_utc: 11, email: '', webhook_url: '', persisted: false });
    } catch {
        return { enabled: false, hour_utc: 11, email: '', webhook_url: '', persisted: false };
    }
};

export const saveDigestPrefs = async (prefs: { enabled: boolean; hour_utc: number; email: string; webhook_url: string }): Promise<any | null> => {
    try {
        const response = await apiFetch(`/digest/prefs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(prefs),
        });
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const sendDigestNow = async (deliver: boolean): Promise<any | null> => {
    try {
        const response = await apiFetch(`/digest/send-now`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ deliver }),
        }, 60000);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const fetchApiKeys = async (): Promise<any[]> => {
    try {
        const response = await apiFetch(`/keys`);
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { keys: [] });
        return Array.isArray((data as any)?.keys) ? (data as any).keys : [];
    } catch {
        return [];
    }
};

export const createApiKey = async (name: string): Promise<any | null> => {
    try {
        const response = await apiFetch(`/keys`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const revokeApiKey = async (id: string): Promise<any[]> => {
    try {
        const response = await apiFetch(`/keys/${encodeURIComponent(id)}`, { method: 'DELETE' });
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { keys: [] });
        return Array.isArray((data as any)?.keys) ? (data as any).keys : [];
    } catch {
        return [];
    }
};

export const fetchWebhooks = async (): Promise<any[]> => {
    try {
        const response = await apiFetch(`/webhooks`);
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { webhooks: [] });
        return Array.isArray((data as any)?.webhooks) ? (data as any).webhooks : [];
    } catch {
        return [];
    }
};

export const addWebhook = async (url: string, events: string[] = ['spike.alert']): Promise<any[] | null> => {
    try {
        const response = await apiFetch(`/webhooks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, events }),
        });
        if (!response.ok) return null;
        const data = await parseJsonSafely(response, { webhooks: [] });
        return Array.isArray((data as any)?.webhooks) ? (data as any).webhooks : [];
    } catch {
        return null;
    }
};

export const deleteWebhook = async (id: string): Promise<any[]> => {
    try {
        const response = await apiFetch(`/webhooks/${encodeURIComponent(id)}`, { method: 'DELETE' });
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { webhooks: [] });
        return Array.isArray((data as any)?.webhooks) ? (data as any).webhooks : [];
    } catch {
        return [];
    }
};

export const testWebhook = async (url: string): Promise<boolean> => {
    try {
        const response = await apiFetch(`/webhooks/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        return response.ok;
    } catch {
        return false;
    }
};

export const fetchBriefComments = async (id: string): Promise<any[]> => {
    try {
        const base = BASE_URL.replace('/api', '');
        const response = await fetch(`${base}/api/briefs/public/${encodeURIComponent(id)}/comments`);
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { comments: [] });
        return Array.isArray((data as any)?.comments) ? (data as any).comments : [];
    } catch {
        return [];
    }
};

export const postBriefComment = async (id: string, body: string): Promise<any | null> => {
    try {
        const response = await apiFetch(`/briefs/${encodeURIComponent(id)}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ body }),
        });
        if (!response.ok) return null;
        const data = await parseJsonSafely(response, null);
        return (data as any)?.comment || null;
    } catch {
        return null;
    }
};

export const deleteBriefComment = async (commentId: string): Promise<boolean> => {
    try {
        const response = await apiFetch(`/comments/${encodeURIComponent(commentId)}`, { method: 'DELETE' });
        return response.ok;
    } catch {
        return false;
    }
};

export const fetchWorkspaces = async (): Promise<any[]> => {
    try {
        const response = await apiFetch(`/workspaces`);
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { workspaces: [] });
        return Array.isArray((data as any)?.workspaces) ? (data as any).workspaces : [];
    } catch {
        return [];
    }
};

export const createWorkspace = async (name: string): Promise<any | null> => {
    try {
        const response = await apiFetch(`/workspaces`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const joinWorkspace = async (invite_code: string): Promise<any | null> => {
    try {
        const response = await apiFetch(`/workspaces/join`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ invite_code }),
        });
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const fetchWorkspaceDetail = async (id: string): Promise<any | null> => {
    try {
        const response = await apiFetch(`/workspaces/${encodeURIComponent(id)}`);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const addWorkspaceCompany = async (id: string, company: string): Promise<string[]> => {
    try {
        const response = await apiFetch(`/workspaces/${encodeURIComponent(id)}/watchlist`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ company }),
        });
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { watchlist: [] });
        return Array.isArray((data as any)?.watchlist) ? (data as any).watchlist : [];
    } catch {
        return [];
    }
};

export const removeWorkspaceCompany = async (id: string, company: string): Promise<string[]> => {
    try {
        const response = await apiFetch(`/workspaces/${encodeURIComponent(id)}/watchlist/${encodeURIComponent(company)}`, { method: 'DELETE' });
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { watchlist: [] });
        return Array.isArray((data as any)?.watchlist) ? (data as any).watchlist : [];
    } catch {
        return [];
    }
};

export const fetchRssFeeds = async (): Promise<any[]> => {
    try {
        const response = await apiFetch(`/rss`);
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { feeds: [] });
        return Array.isArray((data as any)?.feeds) ? (data as any).feeds : [];
    } catch {
        return [];
    }
};

export const addRssFeed = async (url: string, label: string): Promise<any[] | null> => {
    try {
        const response = await apiFetch(`/rss`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, label }),
        });
        if (!response.ok) return null;
        const data = await parseJsonSafely(response, { feeds: [] });
        return Array.isArray((data as any)?.feeds) ? (data as any).feeds : [];
    } catch {
        return null;
    }
};

export const deleteRssFeed = async (id: string): Promise<any[]> => {
    try {
        const response = await apiFetch(`/rss/${encodeURIComponent(id)}`, { method: 'DELETE' });
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { feeds: [] });
        return Array.isArray((data as any)?.feeds) ? (data as any).feeds : [];
    } catch {
        return [];
    }
};

export const toggleRssFeed = async (id: string, enabled: boolean): Promise<any[]> => {
    try {
        const response = await apiFetch(`/rss/${encodeURIComponent(id)}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled }),
        });
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { feeds: [] });
        return Array.isArray((data as any)?.feeds) ? (data as any).feeds : [];
    } catch {
        return [];
    }
};

export const pullRssNow = async (): Promise<any | null> => {
    try {
        const response = await apiFetch(`/rss/pull-now`, { method: 'POST' }, 60000);
        if (!response.ok) return null;
        return await parseJsonSafely(response, null);
    } catch {
        return null;
    }
};

export const fetchVideos = async (query?: string, category: string = "all", limit: number = 8): Promise<any[]> => {
    try {
        const params = new URLSearchParams();
        if (query) params.append('query', query);
        params.append('category', category);
        params.append('limit', limit.toString());
        
        const response = await apiFetch(`/videos?${params.toString()}`);
        if (!response.ok) return [];
        const data = await parseJsonSafely(response, { videos: [] });
        return (data as any)?.videos || [];
    } catch (err) {
        console.warn("fetchVideos error:", err);
        return [];
    }
};
