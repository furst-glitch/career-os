"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CvTemplateSelector, AppTemplateSelector, type CvTemplate, type AppTemplate } from "@/components/TemplateSelector";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Prefs {
  industries:        string[];
  company_sizes:     string[];
  work_styles:       string[];
  values:            string[];
  location_prefs:    Record<string, string>;
  deal_breakers:     string[];
  salary_min:        number | null;
  salary_max:        number | null;
  salary_currency:   string;
  role_types:        string[];
  remote_preference: string;
  ai_preferences:    Record<string, string>;
}

interface ProviderInfo {
  provider: string;
  key_hint: string;
  is_active: boolean;
  created_at: string;
}

const DEFAULT_PREFS: Prefs = {
  industries: [], company_sizes: [], work_styles: [], values: [], location_prefs: {},
  deal_breakers: [], salary_min: null, salary_max: null, salary_currency: "DKK",
  role_types: [], remote_preference: "hybrid", ai_preferences: {},
};

// ── Shared ────────────────────────────────────────────────────────────────────

const I = "w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500";

function F({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

function TagInput({ value, onChange, placeholder }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [input, setInput] = useState("");
  function add() {
    const v = input.trim();
    if (v && !value.includes(v)) onChange([...value, v]);
    setInput("");
  }
  return (
    <div className="rounded-md border border-slate-200 p-2">
      <div className="mb-2 flex flex-wrap gap-1">
        {value.map(tag => (
          <span key={tag} className="flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
            {tag}
            <button onClick={() => onChange(value.filter(t => t !== tag))} className="text-blue-400 hover:text-blue-700">✕</button>
          </span>
        ))}
      </div>
      <div className="flex gap-1">
        <input
          className="flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-slate-300"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); } }}
          placeholder={placeholder ?? "Skriv og tryk Enter"}
        />
        <button onClick={add} className="rounded px-2 py-0.5 text-xs text-blue-600 hover:bg-blue-50">+ Tilføj</button>
      </div>
    </div>
  );
}

// ── API Keys Section ──────────────────────────────────────────────────────────

const PROVIDERS = [
  {
    id: "anthropic",
    label: "Anthropic",
    hint: "Begynder med sk-ant-…",
    placeholder: "sk-ant-api03-…",
    docs: "https://console.anthropic.com/account/keys",
    models: "Claude Opus 4, Claude Sonnet 4",
  },
  {
    id: "openai",
    label: "OpenAI",
    hint: "Begynder med sk-…",
    placeholder: "sk-proj-…",
    docs: "https://platform.openai.com/api-keys",
    models: "GPT-4o, GPT-4o Mini",
  },
] as const;

type ProviderId = typeof PROVIDERS[number]["id"];

function ApiKeysTab() {
  const [configured, setConfigured] = useState<Record<string, ProviderInfo>>({});
  const [inputs, setInputs] = useState<Record<ProviderId, string>>({ anthropic: "", openai: "" });
  const [saving, setSaving] = useState<Record<ProviderId, boolean>>({ anthropic: false, openai: false });
  const [deleting, setDeleting] = useState<Record<ProviderId, boolean>>({ anthropic: false, openai: false });
  const [feedback, setFeedback] = useState<Record<ProviderId, { ok: boolean; msg: string } | null>>({ anthropic: null, openai: null });
  const [loading, setLoading] = useState(true);
  const [defaultProvider, setDefaultProvider] = useState<string | null>(null);
  const [savingDefault, setSavingDefault] = useState(false);
  const [defaultSaved, setDefaultSaved] = useState(false);

  async function loadProviders() {
    try {
      const [{ providers }, { default_provider }] = await Promise.all([
        apiGet<{ providers: ProviderInfo[] }>("/providers"),
        apiGet<{ default_provider: string | null }>("/providers/default"),
      ]);
      const map: Record<string, ProviderInfo> = {};
      for (const p of providers) map[p.provider] = p;
      setConfigured(map);
      setDefaultProvider(default_provider ?? null);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  async function saveDefault(provider: string) {
    setSavingDefault(true);
    try {
      await apiPut("/providers/default", { provider });
      setDefaultProvider(provider);
      setDefaultSaved(true);
      setTimeout(() => setDefaultSaved(false), 2000);
    } catch {
      // ignore
    } finally {
      setSavingDefault(false);
    }
  }

  useEffect(() => { loadProviders(); }, []);

  function setFb(provider: ProviderId, ok: boolean, msg: string) {
    setFeedback(prev => ({ ...prev, [provider]: { ok, msg } }));
    setTimeout(() => setFeedback(prev => ({ ...prev, [provider]: null })), 4000);
  }

  async function saveKey(provider: ProviderId) {
    const key = inputs[provider].trim();
    if (!key) return;
    setSaving(prev => ({ ...prev, [provider]: true }));
    try {
      await apiPost("/providers", { provider, key });
      setInputs(prev => ({ ...prev, [provider]: "" }));
      await loadProviders();
      setFb(provider, true, "API-nøgle gemt");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setFb(provider, false, msg || "Kunne ikke gemme nøglen");
    } finally {
      setSaving(prev => ({ ...prev, [provider]: false }));
    }
  }

  async function deleteKey(provider: ProviderId) {
    setDeleting(prev => ({ ...prev, [provider]: true }));
    try {
      await apiDelete(`/providers/${provider}`);
      await loadProviders();
      setFb(provider, true, "API-nøgle fjernet");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setFb(provider, false, msg || "Kunne ikke fjerne nøglen");
    } finally {
      setDeleting(prev => ({ ...prev, [provider]: false }));
    }
  }

  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <svg className="h-6 w-6 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
        <p className="text-sm font-medium text-blue-800">Bring Your Own Key (BYOK)</p>
        <p className="mt-1 text-xs text-slate-600">
          Dine API-nøgler krypteres med AES-256 og gemmes sikkert. Ingen CareerOS-medarbejder har adgang til dem.
          Nøglerne bruges direkte i dine AI-kald — du betaler selv til udbyderen.
        </p>
      </div>

      {/* Standard AI-udbyder */}
      <Card>
        <CardHeader>
          <CardTitle>Standard AI-udbyder</CardTitle>
        </CardHeader>
        <div className="mt-4 space-y-3">
          <p className="text-xs text-slate-500">
            Vælg hvilken AI-udbyder der bruges til alle kald. Kræver at nøglen er tilføjet nedenfor.
          </p>
          <div className="flex items-center gap-3">
            <select
              className={I + " flex-1"}
              value={defaultProvider ?? ""}
              onChange={e => saveDefault(e.target.value)}
              disabled={savingDefault}
            >
              <option value="">Standard (Anthropic)</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="openai">OpenAI (GPT-4o)</option>
            </select>
            {savingDefault && (
              <svg className="h-4 w-4 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
            )}
            {defaultSaved && <span className="text-xs font-medium text-green-600">✓ Gemt</span>}
          </div>
          {defaultProvider === "openai" && !configured["openai"] && (
            <p className="text-xs text-amber-600">Husk at tilføje din OpenAI-nøgle nedenfor.</p>
          )}
          {defaultProvider === "anthropic" && !configured["anthropic"] && (
            <p className="text-xs text-amber-600">Husk at tilføje din Anthropic-nøgle nedenfor.</p>
          )}
        </div>
      </Card>

      {PROVIDERS.map(p => {
        const info = configured[p.id];
        const fb = feedback[p.id];
        return (
          <Card key={p.id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{p.label}</span>
                {info ? (
                  <span className="flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                    Konfigureret — …{info.key_hint}
                  </span>
                ) : (
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500">
                    Ikke konfigureret
                  </span>
                )}
              </CardTitle>
            </CardHeader>

            <div className="mt-4 space-y-4">
              <p className="text-xs text-slate-500">Modeller: {p.models}</p>

              {info ? (
                <div className="flex items-center gap-3">
                  <p className="flex-1 text-sm text-slate-600">
                    Aktiv nøgle: <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">…{info.key_hint}</code>
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={deleting[p.id]}
                    onClick={() => deleteKey(p.id)}
                  >
                    Fjern nøgle
                  </Button>
                </div>
              ) : (
                <F label={`${p.label} API-nøgle`} hint={p.hint}>
                  <div className="flex gap-2">
                    <input
                      type="password"
                      className={I + " flex-1 font-mono text-xs"}
                      placeholder={p.placeholder}
                      value={inputs[p.id]}
                      onChange={e => setInputs(prev => ({ ...prev, [p.id]: e.target.value }))}
                      onKeyDown={e => { if (e.key === "Enter") saveKey(p.id); }}
                    />
                    <Button
                      size="sm"
                      loading={saving[p.id]}
                      disabled={!inputs[p.id].trim()}
                      onClick={() => saveKey(p.id)}
                    >
                      Gem
                    </Button>
                  </div>
                </F>
              )}

              {fb && (
                <p className={`text-xs font-medium ${fb.ok ? "text-green-600" : "text-red-600"}`}>
                  {fb.ok ? "✓" : "✗"} {fb.msg}
                </p>
              )}
            </div>
          </Card>
        );
      })}

      <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-xs text-slate-500">
        Du kan hente dine API-nøgler hos{" "}
        <a href="https://console.anthropic.com/account/keys" target="_blank" rel="noreferrer" className="text-blue-600 underline">Anthropic Console</a>
        {" "}og{" "}
        <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer" className="text-blue-600 underline">OpenAI Platform</a>.
      </div>
    </div>
  );
}

// ── Layout Tab ────────────────────────────────────────────────────────────────

function DokumenterTab() {
  const [cvTpl, setCvTpl]     = useState<CvTemplate>("nordic_executive");
  const [appTpl, setAppTpl]   = useState<AppTemplate>("corporate");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [saved, setSaved]     = useState(false);
  const [err, setErr]         = useState("");

  useEffect(() => {
    apiGet<{ default_cv_template: string; default_app_template: string }>("/export/preferences")
      .then(p => {
        const NEW_CV_TEMPLATES = ["nordic_executive", "clean_professional", "modern_nordic", "minimal_nordic", "bold_impact"];
        if (p.default_cv_template && NEW_CV_TEMPLATES.includes(p.default_cv_template)) {
          setCvTpl(p.default_cv_template as CvTemplate);
        }
        if (p.default_app_template) setAppTpl(p.default_app_template as AppTemplate);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true); setErr("");
    try {
      await apiPut("/export/preferences", {
        default_cv_template: cvTpl,
        default_app_template: appTpl,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Kunne ikke gemme");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <svg className="h-6 w-6 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* CV templates */}
      <Card>
        <CardHeader>
          <CardTitle>Standard CV-template</CardTitle>
        </CardHeader>
        <p className="mt-1 mb-4 text-xs text-slate-500">
          Bruges som standard ved download fra Master CV-siden. Du kan altid vælge et andet template ved download.
        </p>
        <CvTemplateSelector selected={cvTpl} onSelect={setCvTpl} columns={5} />
      </Card>

      {/* Application templates */}
      <Card>
        <CardHeader>
          <CardTitle>Standard ansøgnings-template</CardTitle>
        </CardHeader>
        <p className="mt-1 mb-4 text-xs text-slate-500">
          Bruges som standard ved download af ansøgninger og breve.
        </p>
        <AppTemplateSelector selected={appTpl} onSelect={setAppTpl} columns={5} />
      </Card>

      {/* Save + feedback */}
      {err && (
        <p className="text-sm text-red-600">✗ {err}</p>
      )}
      {saved && (
        <p className="text-sm text-green-600">✓ Template-præferencer gemt</p>
      )}
      <div className="flex justify-end border-t border-slate-100 pt-4">
        <Button loading={saving} onClick={save}>Gem template-valg</Button>
      </div>
    </div>
  );
}

// ── Billing Tab ───────────────────────────────────────────────────────────────

type PlanInfo = {
  name: string;
  price_dkk: number | null;
  interval: string | null;
  features: string[];
  stripe_price_id: string | null;
};

type SubscriptionData = {
  plan: string;
  status: string;
  current_period_end: string | null;
  has_stripe_subscription: boolean;
  ai_budget: {
    monthly_limit_usd: number;
    current_spend_usd: number;
    warning_threshold: number;
    hard_limit: boolean;
    period_reset_at: string | null;
  };
  plan_features: PlanInfo;
};

function BillingTab() {
  const searchParams = useSearchParams();
  const [sub, setSub] = useState<SubscriptionData | null>(null);
  const [plans, setPlans] = useState<Record<string, PlanInfo>>({});
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [openingPortal, setOpeningPortal] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (searchParams.get("success") === "1") setNotice("Abonnement aktiveret — tak!");
    if (searchParams.get("canceled") === "1") setNotice("Checkout annulleret — ingen ændringer.");
  }, [searchParams]);

  useEffect(() => {
    Promise.all([
      apiGet<SubscriptionData>("/billing/subscription"),
      apiGet<{ plans: Record<string, PlanInfo> }>("/billing/plans"),
    ])
      .then(([s, { plans: p }]) => { setSub(s); setPlans(p); })
      .finally(() => setLoading(false));
  }, []);

  async function upgrade(planKey: string) {
    setUpgrading(planKey);
    try {
      const { checkout_url } = await apiPost<{ checkout_url: string }>("/billing/create-checkout", { plan: planKey });
      window.location.href = checkout_url;
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Checkout fejlede");
      setUpgrading(null);
    }
  }

  async function openPortal() {
    setOpeningPortal(true);
    try {
      const { portal_url } = await apiPost<{ portal_url: string }>("/billing/create-portal", {});
      window.location.href = portal_url;
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Portal fejlede");
      setOpeningPortal(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <svg className="h-6 w-6 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  const budget = sub?.ai_budget;
  const spendPct = budget ? Math.min(100, Math.round((budget.current_spend_usd / budget.monthly_limit_usd) * 100)) : 0;
  const isFreePlan = !sub || sub.plan === "free";
  const STATUS_LABEL: Record<string, string> = {
    active: "Aktiv", trialing: "Prøveperiode", past_due: "Betaling forfalden", canceled: "Opsagt",
  };

  return (
    <div className="space-y-6">
      {notice && (
        <div className={`rounded-lg border p-4 text-sm font-medium ${notice.includes("tak") ? "border-green-200 bg-green-50 text-green-800" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
          {notice}
        </div>
      )}

      {/* Aktuel plan */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Aktuel plan</span>
            <span className={`rounded-full px-3 py-0.5 text-xs font-medium ${isFreePlan ? "bg-slate-100 text-slate-600" : "bg-blue-100 text-blue-700"}`}>
              {sub?.plan_features?.name ?? "Free"}
            </span>
          </CardTitle>
        </CardHeader>
        <div className="mt-4 space-y-3">
          {sub && sub.status !== "active" && (
            <p className="text-sm font-medium text-amber-600">
              Status: {STATUS_LABEL[sub.status] ?? sub.status}
            </p>
          )}
          {sub?.current_period_end && (
            <p className="text-xs text-slate-500">
              Næste faktura: {new Date(sub.current_period_end).toLocaleDateString("da-DK")}
            </p>
          )}
          <ul className="space-y-1">
            {(sub?.plan_features?.features ?? []).map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm text-slate-700">
                <span className="text-green-500">✓</span> {f}
              </li>
            ))}
          </ul>
          {sub?.has_stripe_subscription && (
            <Button variant="secondary" loading={openingPortal} onClick={openPortal}>
              Administrér abonnement
            </Button>
          )}
        </div>
      </Card>

      {/* AI-forbrug */}
      {budget && (
        <Card>
          <CardHeader><CardTitle>AI-forbrug denne måned</CardTitle></CardHeader>
          <div className="mt-4 space-y-3">
            <div className="flex justify-between text-xs text-slate-500">
              <span>${budget.current_spend_usd.toFixed(3)} brugt</span>
              <span>Grænse: ${budget.monthly_limit_usd.toFixed(2)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full transition-all ${spendPct > 90 ? "bg-red-500" : spendPct > 70 ? "bg-amber-500" : "bg-blue-500"}`}
                style={{ width: `${spendPct}%` }}
              />
            </div>
            {budget.hard_limit && (
              <p className="text-xs font-medium text-red-600">AI-grænse nået — opgrader for at fortsætte</p>
            )}
          </div>
        </Card>
      )}

      {/* Plansammenligning */}
      {isFreePlan && (
        <div className="space-y-3">
          <h3 className="font-semibold text-slate-800">Opgrader din plan</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {(["pro", "professional"] as const).map((key) => {
              const p = plans[key];
              if (!p) return null;
              return (
                <div key={key} className="rounded-lg border border-slate-200 p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{p.name}</span>
                    <span className="text-slate-600 text-sm">
                      {p.price_dkk != null ? `${p.price_dkk} kr/md` : "Kontakt os"}
                    </span>
                  </div>
                  <ul className="space-y-1">
                    {p.features.map((f) => (
                      <li key={f} className="flex items-center gap-2 text-xs text-slate-600">
                        <span className="text-blue-500">✓</span> {f}
                      </li>
                    ))}
                  </ul>
                  <Button
                    className="w-full"
                    loading={upgrading === key}
                    disabled={!!upgrading || !p.stripe_price_id}
                    onClick={() => upgrade(key)}
                  >
                    {p.stripe_price_id ? `Vælg ${p.name}` : "Kommer snart"}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

type Tab = "job" | "ai" | "keys" | "docs" | "billing";

export default function SettingsPage() {
  const [tab, setTab]       = useState<Tab>("job");
  const [prefs, setPrefs]   = useState<Prefs>(DEFAULT_PREFS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [saved, setSaved]     = useState(false);

  useEffect(() => {
    apiGet<Prefs>("/memory/preferences")
      .then(p => setPrefs({ ...DEFAULT_PREFS, ...p }))
      .finally(() => setLoading(false));
  }, []);

  function upd<K extends keyof Prefs>(key: K, value: Prefs[K]) {
    setPrefs(prev => ({ ...prev, [key]: value }));
  }

  async function save() {
    setSaving(true);
    try {
      const updated = await apiPut<Prefs>("/memory/preferences", prefs);
      setPrefs({ ...DEFAULT_PREFS, ...updated });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally { setSaving(false); }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {saved && (
        <div className="fixed right-6 top-6 z-50 rounded-lg bg-green-600 px-4 py-3 text-sm font-medium text-white shadow-lg">
          Præferencer gemt
        </div>
      )}

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Indstillinger</h1>
          <p className="mt-1 text-sm text-slate-500">Dine karrierepræferencer bruges af alle agenter til personaliserede anbefalinger</p>
        </div>
        {tab !== "keys" && tab !== "docs" && tab !== "billing" && <Button loading={saving} onClick={save}>Gem præferencer</Button>}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
        {([
          { key: "job",     label: "Jobpræferencer" },
          { key: "ai",      label: "AI-præferencer" },
          { key: "keys",    label: "API-nøgler" },
          { key: "docs",    label: "Layout" },
          { key: "billing", label: "Abonnement" },
        ] as { key: Tab; label: string }[]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
              tab === t.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Job Preferences ── */}
      {tab === "job" && (
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Lokation og arbejdsstil</CardTitle></CardHeader>
            <div className="mt-4 grid grid-cols-2 gap-5">
              <F label="Remote-præference">
                <select className={I + " bg-white"} value={prefs.remote_preference} onChange={e => upd("remote_preference", e.target.value)}>
                  <option value="remote">Fuldt remote</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="onsite">På kontoret</option>
                  <option value="flexible">Fleksibelt</option>
                </select>
              </F>
              <F label="Foretrukket lokation">
                <input className={I} value={prefs.location_prefs?.city ?? ""} placeholder="København, Aarhus…"
                  onChange={e => upd("location_prefs", { ...prefs.location_prefs, city: e.target.value })} />
              </F>
            </div>
            <div className="mt-5">
              <F label="Arbejdsstil-tags" hint="f.eks. Agil, Scrum, DevOps, startup-kultur">
                <TagInput value={prefs.work_styles} onChange={v => upd("work_styles", v)} placeholder="Agil, startup, DevOps…" />
              </F>
            </div>
          </Card>

          <Card>
            <CardHeader><CardTitle>Løn</CardTitle></CardHeader>
            <div className="mt-4 grid grid-cols-3 gap-5">
              <F label="Minimum (DKK/år)">
                <input type="number" className={I} value={prefs.salary_min ?? ""} min="0" step="10000"
                  onChange={e => upd("salary_min", e.target.value ? parseInt(e.target.value) : null)} placeholder="600000" />
              </F>
              <F label="Maximum (DKK/år)">
                <input type="number" className={I} value={prefs.salary_max ?? ""} min="0" step="10000"
                  onChange={e => upd("salary_max", e.target.value ? parseInt(e.target.value) : null)} placeholder="900000" />
              </F>
              <F label="Valuta">
                <select className={I + " bg-white"} value={prefs.salary_currency} onChange={e => upd("salary_currency", e.target.value)}>
                  <option value="DKK">DKK</option><option value="EUR">EUR</option><option value="USD">USD</option>
                </select>
              </F>
            </div>
          </Card>

          <Card>
            <CardHeader><CardTitle>Brancher og rolletyper</CardTitle></CardHeader>
            <div className="mt-4 space-y-5">
              <F label="Foretrukne brancher" hint="f.eks. Tech, Fintech, ESG, SaaS, Facility Management">
                <TagInput value={prefs.industries} onChange={v => upd("industries", v)} placeholder="Tech, Fintech, ESG…" />
              </F>
              <F label="Rolletyper" hint="f.eks. Engineering Manager, CTO, Senior Developer, Architect">
                <TagInput value={prefs.role_types} onChange={v => upd("role_types", v)} placeholder="Engineering Manager, Senior Developer…" />
              </F>
            </div>
          </Card>

          <Card>
            <CardHeader><CardTitle>Virksomhedsstørrelse og værdier</CardTitle></CardHeader>
            <div className="mt-4 space-y-5">
              <F label="Virksomhedsstørrelse">
                <TagInput value={prefs.company_sizes} onChange={v => upd("company_sizes", v)} placeholder="Startup, SME, Enterprise, Børsnoteret…" />
              </F>
              <F label="Vigtige værdier" hint="Hvad er vigtigst for dig i et job?">
                <TagInput value={prefs.values} onChange={v => upd("values", v)} placeholder="Teknisk frihed, formål, læringsmuligheder…" />
              </F>
              <F label="Deal breakers">
                <TagInput value={prefs.deal_breakers} onChange={v => upd("deal_breakers", v)} placeholder="Overarbejde-kultur, ingen remote-mulighed…" />
              </F>
            </div>
          </Card>
        </div>
      )}

      {/* ── AI Preferences ── */}
      {tab === "ai" && (
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>AI-skrivestil</CardTitle></CardHeader>
            <div className="mt-4 space-y-5">
              <F label="Foretrukken skrivestil" hint="Påvirker tone i genererede CV-tekster, coverlettere og anbefalinger">
                <select className={I + " bg-white"}
                  value={prefs.ai_preferences?.writing_style ?? "professional"}
                  onChange={e => upd("ai_preferences", { ...prefs.ai_preferences, writing_style: e.target.value })}>
                  <option value="professional">Professionel og formel</option>
                  <option value="direct">Direkte og konkret</option>
                  <option value="warm">Varm og personlig</option>
                  <option value="technical">Teknisk og præcis</option>
                  <option value="narrative">Fortællende og engagerende</option>
                </select>
              </F>
              <F label="CV-sprog" hint="Standardsprog til genererede CV-tekster">
                <select className={I + " bg-white"}
                  value={prefs.ai_preferences?.cv_language ?? "da"}
                  onChange={e => upd("ai_preferences", { ...prefs.ai_preferences, cv_language: e.target.value })}>
                  <option value="da">Dansk</option>
                  <option value="en">Engelsk</option>
                </select>
              </F>
              <F label="Fokusområder i anbefalinger" hint="Hvad skal AI fokusere på?">
                <input className={I}
                  value={prefs.ai_preferences?.focus_areas ?? ""}
                  onChange={e => upd("ai_preferences", { ...prefs.ai_preferences, focus_areas: e.target.value })}
                  placeholder="Lederskab, teknisk dybde, forretningsmæssig impact…" />
              </F>
            </div>
          </Card>

          <Card>
            <CardHeader><CardTitle>AI-udbyder</CardTitle></CardHeader>
            <div className="mt-4 space-y-3">
              <p className="text-sm text-slate-600">
                Tilføj dine API-nøgler under{" "}
                <button onClick={() => setTab("keys")} className="text-blue-600 underline">API-nøgler</button>.
              </p>
              <F label="Foretrukken AI-model til generering" hint="Kræver tilsvarende API-nøgle">
                <select className={I + " bg-white"}
                  value={prefs.ai_preferences?.preferred_model ?? "claude-opus-4-8"}
                  onChange={e => upd("ai_preferences", { ...prefs.ai_preferences, preferred_model: e.target.value })}>
                  <option value="claude-opus-4-8">Claude Opus 4.8 (Anthropic)</option>
                  <option value="claude-sonnet-4-6">Claude Sonnet 4.6 (Anthropic)</option>
                  <option value="gpt-4o">GPT-4o (OpenAI)</option>
                  <option value="gpt-4o-mini">GPT-4o Mini (OpenAI)</option>
                </select>
              </F>
            </div>
          </Card>

          <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
            <p className="text-sm font-medium text-blue-800">AI Memory Snapshot</p>
            <p className="mt-1 text-xs text-slate-600">
              Alle dine præferencer gemmes og inkluderes automatisk i AI-agenternes kontekst.
              Ingen manuel konfiguration nødvendig per agent.
            </p>
          </div>
        </div>
      )}

      {/* ── API Keys ── */}
      {tab === "keys" && <ApiKeysTab />}

      {/* ── Layout ── */}
      {tab === "docs" && <DokumenterTab />}

      {/* ── Billing ── */}
      {tab === "billing" && <BillingTab />}

      {tab !== "keys" && tab !== "docs" && tab !== "billing" && (
        <div className="flex justify-end border-t border-slate-100 pt-4">
          <Button loading={saving} onClick={save}>Gem præferencer</Button>
        </div>
      )}
    </div>
  );
}
