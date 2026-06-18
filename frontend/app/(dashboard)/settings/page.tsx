"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

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

// ── Page ─────────────────────────────────────────────────────────────────────

type Tab = "job" | "ai";

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
        <Button loading={saving} onClick={save}>Gem præferencer</Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
        {([
          { key: "job", label: "Jobpræferencer" },
          { key: "ai",  label: "AI-præferencer" },
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
                Administrér dine API-nøgler under{" "}
                <a href="/cv" className="text-blue-600 underline">Indstillinger → API-nøgler</a>.
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

      <div className="flex justify-end border-t border-slate-100 pt-4">
        <Button loading={saving} onClick={save}>Gem præferencer</Button>
      </div>
    </div>
  );
}
