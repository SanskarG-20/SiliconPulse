const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api").replace(/\/$/, "");
const DEFAULT_TIMEOUT_MS = 10000;
const QUERY_TIMEOUT_MS = 12000;
const INSIGHT_TIMEOUT_MS = 20000;

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

const parseJsonSafely = async <T>(response: Response, fallback: T): Promise<T> => {
    try {
        return await response.json();
    } catch {
        return fallback;
    }
};

const normalizeEvidence = (value: any): any[] => Array.isArray(value) ? value : [];

export interface QueryResponse {
    query: string;
    evidence: any[];
    signal_strength: number;
    last_updated: string;
    report?: string | null;
    llm_status?: string;
}

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
        return new Error("Request timed out. Please retry once the backend catches up.");
    }
    if (error?.name === "TypeError" && error?.message === "Failed to fetch") {
        return new Error("Backend offline. Please check connection.");
    }
    return error instanceof Error ? error : new Error("Unexpected API failure.");
};

export const checkBackendHealth = async (): Promise<boolean> => {
    try {
        const controller = new AbortController();
        const healthUrl = `${BASE_URL.replace('/api', '')}/health`;
        const response = await withTimeout(fetch(healthUrl, {
            signal: controller.signal,
        }), controller, 5000);
        return response.ok;
    } catch {
        return false;
    }
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
        return Array.isArray(data) ? data : [];
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
        return Array.isArray(data) ? data : [];
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
    });

    return context;
};

export const generateInsight = async (query: string, context: string): Promise<string> => {
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
        const data = await parseJsonSafely(response, { insight: "" });
        return data?.insight || "Insight generation returned an empty response.";
    } catch {
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
