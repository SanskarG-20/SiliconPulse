import React, { useEffect, useState } from 'react';
import { KeyRound, Webhook, Plus, Trash2, Copy, Check, Send } from 'lucide-react';
import {
  fetchApiKeys,
  createApiKey,
  rotateApiKey,
  revokeApiKey,
  fetchWebhooks,
  addWebhook,
  deleteWebhook,
  testWebhook,
} from '../api/siliconpulseApi';

export const TeamIntegrations: React.FC = () => {
  const [keys, setKeys] = useState<any[]>([]);
  const [keyName, setKeyName] = useState('');
  const [keyScopes, setKeyScopes] = useState(['signals:read', 'query:read', 'trends:read', 'compare:read', 'reports:generate']);
  const [keyExpiryDays, setKeyExpiryDays] = useState(90);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [hooks, setHooks] = useState<any[]>([]);
  const [hookUrl, setHookUrl] = useState('');
  const [hookError, setHookError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [tested, setTested] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchApiKeys().then((k) => { if (!cancelled) setKeys(k); }).catch(() => {});
    fetchWebhooks().then((w) => { if (!cancelled) setHooks(w); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const handleCreateKey = async () => {
    const res = await createApiKey(keyName.trim() || 'default', keyScopes, keyExpiryDays);
    if (res?.key) {
      setNewKey(res.key);
      setCopied(false);
      setKeys(await fetchApiKeys());
      setKeyName('');
    }
  };

  const handleRotateKey = async (id: string) => {
    const res = await rotateApiKey(id);
    if (res?.key) {
      setNewKey(res.key);
      setCopied(false);
      setKeys(await fetchApiKeys());
    }
  };

  const handleCopyKey = async () => {
    if (!newKey) return;
    try {
      await navigator.clipboard.writeText(newKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const handleAddHook = async () => {
    setHookError(null);
    const res = await addWebhook(hookUrl.trim());
    if (res === null) setHookError('Only Slack (hooks.slack.com) or Discord (discord.com/api) URLs are accepted.');
    else {
      setHooks(res);
      setHookUrl('');
    }
  };

  const handleTestHook = async () => {
    if (!hookUrl.trim()) return;
    setTesting(true);
    setTested(null);
    const ok = await testWebhook(hookUrl.trim());
    setTested(ok ? 'Test message delivered.' : 'Webhook rejected the test message.');
    setTesting(false);
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="flex items-center gap-1.5 mono text-[10px] font-bold tracking-[0.12em] text-[#64748B] mb-2">
          <KeyRound size={12} /> API KEYS FOR BOTS & CI
        </p>
        <p className="text-[12px] leading-relaxed text-[#64748B] mb-2">
          Send as the <span className="mono text-[11px] text-[#94A3B8]">X-API-Key</span> header to use signals, query, trends and compare programmatically.
        </p>
        <div className="flex gap-2 mb-2">
          <input
            value={keyName}
            onChange={(e) => setKeyName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleCreateKey(); }}
            placeholder="Key name, e.g. ci-bot"
            className="flex-1 min-w-[140px] px-2.5 py-1.5 rounded-full bg-white dark:bg-[#050B1A] border border-slate-300 dark:border-[#1C3553]/60 text-[12px] text-slate-800 dark:text-[#E2E8F0] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE]/40"
            aria-label="API key name"
          />
          <button onClick={handleCreateKey} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-[#0E1E32] border border-slate-300 dark:border-[#1C3553] text-[11px] font-semibold text-slate-600 dark:text-[#94A3B8] hover:text-slate-900 dark:hover:text-white transition-colors">
            <Plus size={13} /> Create
          </button>
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 mb-2 text-[10px] text-[#64748B]">
          {['signals:read', 'query:read', 'trends:read', 'compare:read', 'reports:generate'].map((scope) => (
            <label key={scope} className="inline-flex items-center gap-1"><input type="checkbox" checked={keyScopes.includes(scope)} onChange={(e) => setKeyScopes((current) => e.target.checked ? [...current, scope] : current.filter((value) => value !== scope))} />{scope}</label>
          ))}
        </div>
        <label className="flex items-center gap-2 mb-2 text-[10px] text-[#64748B]">Expires in
          <select value={keyExpiryDays} onChange={(e) => setKeyExpiryDays(Number(e.target.value))} className="rounded-md border border-slate-300 dark:border-[#1C3553] bg-white dark:bg-[#050B1A] px-2 py-1 text-[11px]">
            {[30, 90, 180, 365].map((days) => <option key={days} value={days}>{days} days</option>)}
          </select>
        </label>
        {newKey && (
          <button
            onClick={handleCopyKey}
            className="mb-2 flex w-full items-center gap-2 rounded-[10px] border border-[#E8A253]/25 bg-[#E8A253]/[0.07] px-3 py-2 text-left mono text-[11px] text-[#B45309] dark:text-[#E8A253] hover:bg-[#E8A253]/[0.12] transition-colors"
            title="Click to copy (shown once)"
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
            <span className="truncate">{copied ? 'Copied — store it now' : newKey}</span>
          </button>
        )}
        {keys.length > 0 ? (
          <ul className="space-y-1">
            {keys.map((k: any) => (
              <li key={k.id} className="flex items-center gap-2 rounded-full bg-white dark:bg-[#050B1A] border border-slate-200 dark:border-[#1C3553]/40 px-2.5 py-1.5">
                <span className="text-[12px] font-semibold text-slate-800 dark:text-[#E2E8F0] truncate">{k.name}</span>
                <span className="mono text-[10px] text-[#475569]">{k.key_prefix}…{k.revoked ? ' • revoked' : ''} • {Array.isArray(k.scopes) ? k.scopes.join(',') : 'legacy scopes'}{k.expires_at ? ` • exp ${new Date(k.expires_at).toLocaleDateString()}` : ''}</span>
                {!k.revoked && (
                  <button onClick={() => handleRotateKey(k.id)} className="ml-auto p-1 rounded-full text-[#475569] hover:text-amber-500 transition-colors" aria-label={`Rotate ${k.name}`}>Rotate</button>
                )}
                {!k.revoked && (
                  <button onClick={async () => setKeys(await revokeApiKey(k.id))} className="ml-auto p-1 rounded-full text-[#475569] hover:text-red-400 transition-colors" aria-label={`Revoke ${k.name}`}>
                    <Trash2 size={12} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mono text-[11px] tracking-[0.04em] text-[#475569]">No keys yet.</p>
        )}
      </div>

      <div>
        <p className="flex items-center gap-1.5 mono text-[10px] font-bold tracking-[0.12em] text-[#64748B] mb-2">
          <Webhook size={12} /> TEAM CHANNEL FOR SPIKE ALERTS
        </p>
        <div className="flex gap-2 mb-2">
          <input
            value={hookUrl}
            onChange={(e) => setHookUrl(e.target.value)}
            placeholder="https://hooks.slack.com/…"
            className="flex-1 min-w-[140px] px-2.5 py-1.5 rounded-full bg-white dark:bg-[#050B1A] border border-slate-300 dark:border-[#1C3553]/60 text-[12px] text-slate-800 dark:text-[#E2E8F0] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE]/40 mono"
            aria-label="Webhook URL"
          />
          <button onClick={handleAddHook} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-[#0E1E32] border border-slate-300 dark:border-[#1C3553] text-[11px] font-semibold text-slate-600 dark:text-[#94A3B8] hover:text-slate-900 dark:hover:text-white transition-colors">
            <Plus size={13} /> Add
          </button>
          <button onClick={handleTestHook} disabled={testing || !hookUrl.trim()} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-[#0E1E32] border border-slate-300 dark:border-[#1C3553] text-[11px] font-semibold text-slate-600 dark:text-[#94A3B8] hover:text-slate-900 dark:hover:text-white transition-colors disabled:opacity-40" title="Send test message">
            <Send size={12} /> {testing ? '…' : 'Test'}
          </button>
        </div>
        {hookError && <p className="mb-2 text-[11px] text-red-400">{hookError}</p>}
        {tested && <p className="mb-2 mono text-[11px] text-[#64748B]">{tested}</p>}
        {hooks.length > 0 ? (
          <ul className="space-y-1">
            {hooks.map((h: any) => (
              <li key={h.id} className="flex items-center gap-2 rounded-full bg-white dark:bg-[#050B1A] border border-slate-200 dark:border-[#1C3553]/40 px-2.5 py-1.5">
                <span className="mono text-[11px] text-[#94A3B8] truncate">{h.url_host || 'webhook'}</span>
                <span className="mono text-[10px] text-[#475569]">spike.alert • 1/day cap</span>
                <button onClick={async () => setHooks(await deleteWebhook(h.id))} className="ml-auto p-1 rounded-full text-[#475569] hover:text-red-400 transition-colors" aria-label="Delete webhook">
                  <Trash2 size={12} />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mono text-[11px] tracking-[0.04em] text-[#475569]">No team channel yet. Spike days post here automatically.</p>
        )}
      </div>
    </div>
  );
};
