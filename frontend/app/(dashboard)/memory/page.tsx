"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Memory {
  id: string;
  content: string;
  memory_type: string;
  source: string;
  relevance_score: number;
  created_at: string;
  updated_at: string;
}

interface Goal {
  id: string;
  title: string;
  description: string | null;
  goal_type: "short_term" | "long_term" | "aspirational";
  target_date: string | null;
  status: "active" | "achieved" | "abandoned";
  priority: number;
  created_at: string;
}

interface Milestone {
  id: string;
  title: string;
  description: string | null;
  occurred_at: string;
  impact_level: "low" | "medium" | "high" | "defining";
  category: string;
  created_at: string;
}

// ── Shared helpers ────────────────────────────────────────────────────────────

const I = "w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500";

function F({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">
        {label}{required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}

function DelPrompt({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
      <span className="text-sm text-red-700">Slet dette element?</span>
      <Button size="sm" variant="danger" onClick={onConfirm}>Ja, slet</Button>
      <Button size="sm" variant="ghost" onClick={onCancel}>Annuller</Button>
    </div>
  );
}

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString("da-DK", { day: "numeric", month: "short", year: "numeric" });
}

const IMPACT_V: Record<string, "danger" | "warning" | "info" | "default"> = { defining: "danger", high: "warning", medium: "info", low: "default" };
const IMPACT_L: Record<string, string> = { low: "Lav", medium: "Medium", high: "Høj", defining: "Afgørende" };
const CAT_L: Record<string, string> = { promotion: "Forfremmelse", award: "Pris", project: "Projekt", pivot: "Karriereskift", skill: "Kompetence", education: "Uddannelse", personal: "Personlig" };
const STATUS_L: Record<string, string> = { active: "Aktiv", achieved: "Opnået", abandoned: "Opgivet" };
const GT_L: Record<string, string> = { short_term: "Kortsigtet", long_term: "Langsigtet", aspirational: "Aspiration" };

const MEMORY_TYPES = [
  { value: "career_note", label: "Karrierenote" }, { value: "achievement", label: "Præstation" },
  { value: "reflection",  label: "Refleksion" },   { value: "experience",  label: "Erfaring" },
  { value: "goal",        label: "Mål" },           { value: "skill",       label: "Kompetence" },
  { value: "project",     label: "Projekt" },       { value: "milestone",   label: "Milepæl" },
  { value: "lesson",      label: "Lærdom" },        { value: "insight",     label: "Indsigt" },
  { value: "preference",  label: "Præference" },
];
const typeLabel = (t: string) => MEMORY_TYPES.find(o => o.value === t)?.label ?? t;

// ── Main page ─────────────────────────────────────────────────────────────────

type Tab = "goals" | "milestones" | "notes";

export default function MemoryPage() {
  const [tab, setTab] = useState<Tab>("goals");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Career Memory</h1>
        <p className="mt-1 text-sm text-slate-500">
          CareerOS husker dig over tid — mål, milepæle og noter bruges af alle agenter
        </p>
      </div>
      <div className="flex gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
        {([
          { key: "goals", label: "Mål" },
          { key: "milestones", label: "Milepæle" },
          { key: "notes", label: "Karrierenotes" },
        ] as { key: Tab; label: string }[]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
              tab === t.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "goals"      && <GoalsSection />}
      {tab === "milestones" && <MilestonesSection />}
      {tab === "notes"      && <NotesSection />}
    </div>
  );
}

// ── Goals ─────────────────────────────────────────────────────────────────────

function GoalsSection() {
  const [items, setItems] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [editId, setEditId]  = useState<string | null>(null);
  const [adding, setAdding]  = useState(false);
  const [delId, setDelId]    = useState<string | null>(null);
  const [saving, setSaving]  = useState(false);

  useEffect(() => { apiGet<Goal[]>("/memory/goals").then(setItems).finally(() => setLoading(false)); }, []);

  async function create(d: Partial<Goal>) {
    setSaving(true);
    try { const g = await apiPost<Goal>("/memory/goals", d); setItems(p => [...p, g]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function upd(id: string, d: Partial<Goal>) {
    setSaving(true);
    try { const g = await apiPut<Goal>(`/memory/goals/${id}`, d); setItems(p => p.map(i => i.id === id ? g : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function del(id: string) {
    setSaving(true);
    try { await apiDelete(`/memory/goals/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }

  const byType = items.reduce<Record<string, Goal[]>>((a, g) => { (a[g.goal_type] ??= []).push(g); return a; }, {});

  if (loading) return <p className="py-8 text-center text-sm text-slate-400">Henter mål…</p>;

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" onClick={() => { setAdding(true); setEditId(null); }}>+ Tilføj mål</Button>
      </div>
      {adding && <Card padding="sm"><GoalForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!items.length && !adding && <Card padding="sm"><p className="py-4 text-center text-sm text-slate-400">Ingen mål endnu</p></Card>}
      {Object.entries(byType).map(([type, goals]) => (
        <div key={type}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{GT_L[type] ?? type}</p>
          <div className="space-y-2">
            {goals.map(g => (
              <div key={g.id}>
                {delId === g.id ? <DelPrompt onConfirm={() => del(g.id)} onCancel={() => setDelId(null)} />
                : editId === g.id ? <Card padding="sm"><GoalForm item={g} saving={saving} onSave={d => upd(g.id, d)} onCancel={() => setEditId(null)} /></Card>
                : (
                  <Card padding="sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-slate-900">{g.title}</p>
                          <Badge variant={g.status === "achieved" ? "success" : g.status === "abandoned" ? "danger" : "info"}>{STATUS_L[g.status]}</Badge>
                          <Badge>P{g.priority}</Badge>
                        </div>
                        {g.description && <p className="mt-1 text-sm text-slate-600">{g.description}</p>}
                        {g.target_date && <p className="mt-1 text-xs text-slate-400">Deadline: {fmtDate(g.target_date)}</p>}
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        {g.status === "active" && (
                          <button onClick={() => upd(g.id, { status: "achieved" })} className="rounded px-2 py-1 text-xs text-green-600 hover:bg-green-50">✓ Opnået</button>
                        )}
                        <button onClick={() => { setEditId(g.id); setAdding(false); }} className="rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100">Rediger</button>
                        <button onClick={() => setDelId(g.id)} className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-50">Slet</button>
                      </div>
                    </div>
                  </Card>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function GoalForm({ item, saving, onSave, onCancel }: {
  item?: Goal; saving: boolean; onSave: (d: Partial<Goal>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({ title: item?.title ?? "", description: item?.description ?? "", goal_type: item?.goal_type ?? "short_term", target_date: item?.target_date?.slice(0, 10) ?? "", priority: item?.priority?.toString() ?? "3", status: item?.status ?? "active" });
  const s = (k: string, v: string) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({ ...d, priority: parseInt(d.priority), target_date: d.target_date || null });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2"><F label="Titel" required><input className={I} value={d.title} onChange={e => s("title", e.target.value)} placeholder="Bliv engineering manager" /></F></div>
        <F label="Prioritet (1=høj)"><input type="number" min="1" max="5" className={I} value={d.priority} onChange={e => s("priority", e.target.value)} /></F>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <F label="Beskrivelse"><textarea className={I + " resize-none"} rows={2} value={d.description} onChange={e => s("description", e.target.value)} /></F>
        <F label="Type">
          <select className={I + " bg-white"} value={d.goal_type} onChange={e => s("goal_type", e.target.value)}>
            <option value="short_term">Kortsigtet</option><option value="long_term">Langsigtet</option><option value="aspirational">Aspiration</option>
          </select>
        </F>
        <div className="space-y-3">
          <F label="Deadline"><input type="date" className={I} value={d.target_date} onChange={e => s("target_date", e.target.value)} /></F>
          {item && <F label="Status"><select className={I + " bg-white"} value={d.status} onChange={e => s("status", e.target.value)}><option value="active">Aktiv</option><option value="achieved">Opnået</option><option value="abandoned">Opgivet</option></select></F>}
        </div>
      </div>
      <div className="flex gap-2 border-t border-slate-100 pt-3">
        <Button size="sm" loading={saving} onClick={() => onSave(payload())}>Gem</Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>Annuller</Button>
      </div>
    </div>
  );
}

// ── Milestones ────────────────────────────────────────────────────────────────

function MilestonesSection() {
  const [items, setItems] = useState<Milestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [editId, setEditId]  = useState<string | null>(null);
  const [adding, setAdding]  = useState(false);
  const [delId, setDelId]    = useState<string | null>(null);
  const [saving, setSaving]  = useState(false);

  useEffect(() => { apiGet<Milestone[]>("/memory/milestones").then(setItems).finally(() => setLoading(false)); }, []);

  async function create(d: Partial<Milestone>) {
    setSaving(true);
    try { const m = await apiPost<Milestone>("/memory/milestones", d); setItems(p => [m, ...p]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function upd(id: string, d: Partial<Milestone>) {
    setSaving(true);
    try { const m = await apiPut<Milestone>(`/memory/milestones/${id}`, d); setItems(p => p.map(i => i.id === id ? m : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function del(id: string) {
    setSaving(true);
    try { await apiDelete(`/memory/milestones/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }

  if (loading) return <p className="py-8 text-center text-sm text-slate-400">Henter milepæle…</p>;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" onClick={() => { setAdding(true); setEditId(null); }}>+ Tilføj milepæl</Button>
      </div>
      {adding && <Card padding="sm"><MilestoneForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!items.length && !adding && <Card padding="sm"><p className="py-4 text-center text-sm text-slate-400">Ingen milepæle endnu</p></Card>}
      {items.map(m => (
        <div key={m.id}>
          {delId === m.id ? <DelPrompt onConfirm={() => del(m.id)} onCancel={() => setDelId(null)} />
          : editId === m.id ? <Card padding="sm"><MilestoneForm item={m} saving={saving} onSave={d => upd(m.id, d)} onCancel={() => setEditId(null)} /></Card>
          : (
            <Card padding="sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-slate-900">{m.title}</p>
                    <Badge variant={IMPACT_V[m.impact_level]}>{IMPACT_L[m.impact_level]}</Badge>
                    <Badge>{CAT_L[m.category] ?? m.category}</Badge>
                  </div>
                  {m.description && <p className="mt-1 text-sm text-slate-600">{m.description}</p>}
                  <p className="mt-1 text-xs text-slate-400">{fmtDate(m.occurred_at)}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button onClick={() => { setEditId(m.id); setAdding(false); }} className="rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100">Rediger</button>
                  <button onClick={() => setDelId(m.id)} className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-50">Slet</button>
                </div>
              </div>
            </Card>
          )}
        </div>
      ))}
    </div>
  );
}

function MilestoneForm({ item, saving, onSave, onCancel }: {
  item?: Milestone; saving: boolean; onSave: (d: Partial<Milestone>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({ title: item?.title ?? "", description: item?.description ?? "", occurred_at: item?.occurred_at?.slice(0, 10) ?? new Date().toISOString().slice(0, 10), impact_level: item?.impact_level ?? "medium", category: item?.category ?? "project" });
  const s = (k: string, v: string) => setD(p => ({ ...p, [k]: v }));
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <F label="Titel" required><input className={I} value={d.title} onChange={e => s("title", e.target.value)} placeholder="Forfremmet til Tech Lead" /></F>
        <div className="grid grid-cols-2 gap-3">
          <F label="Dato"><input type="date" className={I} value={d.occurred_at} onChange={e => s("occurred_at", e.target.value)} /></F>
          <F label="Impact"><select className={I + " bg-white"} value={d.impact_level} onChange={e => s("impact_level", e.target.value)}><option value="low">Lav</option><option value="medium">Medium</option><option value="high">Høj</option><option value="defining">Afgørende</option></select></F>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <F label="Beskrivelse"><textarea className={I + " resize-none"} rows={2} value={d.description} onChange={e => s("description", e.target.value)} /></F>
        <F label="Kategori"><select className={I + " bg-white"} value={d.category} onChange={e => s("category", e.target.value)}>{Object.entries(CAT_L).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></F>
      </div>
      <div className="flex gap-2 border-t border-slate-100 pt-3">
        <Button size="sm" loading={saving} onClick={() => onSave(d)}>Gem</Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>Annuller</Button>
      </div>
    </div>
  );
}

// ── Career Notes ──────────────────────────────────────────────────────────────

interface SearchResult { results: Memory[]; method: string; }

function NotesSection() {
  const [items, setItems]     = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [editId, setEditId]   = useState<string | null>(null);
  const [adding, setAdding]   = useState(false);
  const [delId, setDelId]     = useState<string | null>(null);
  const [saving, setSaving]   = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [searchRes, setSearchRes] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => { apiGet<Memory[]>("/memory/memories").then(setItems).finally(() => setLoading(false)); }, []);

  async function create(d: Partial<Memory>) {
    setSaving(true);
    try { const m = await apiPost<Memory>("/memory/memories", d); setItems(p => [m, ...p]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function upd(id: string, d: Partial<Memory>) {
    setSaving(true);
    try { const m = await apiPut<Memory>(`/memory/memories/${id}`, d); setItems(p => p.map(i => i.id === id ? m : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function del(id: string) {
    setSaving(true);
    try { await apiDelete(`/memory/memories/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }
  async function doSearch() {
    if (!searchQ.trim()) { setSearchRes(null); return; }
    setSearching(true);
    try { setSearchRes(await apiGet<SearchResult>(`/memory/memories/search?q=${encodeURIComponent(searchQ)}`)); }
    finally { setSearching(false); }
  }

  const display = searchRes ? searchRes.results : items;
  if (loading) return <p className="py-8 text-center text-sm text-slate-400">Henter noter…</p>;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input className={I + " flex-1"} value={searchQ}
          onChange={e => { setSearchQ(e.target.value); if (!e.target.value) setSearchRes(null); }}
          onKeyDown={e => e.key === "Enter" && doSearch()}
          placeholder="Søg: ERP, ServiceNow, ESG, Facility Management…" />
        <Button size="sm" loading={searching} onClick={doSearch}>Søg</Button>
        {searchRes && <Button size="sm" variant="ghost" onClick={() => { setSearchRes(null); setSearchQ(""); }}>Ryd</Button>}
      </div>
      {searchRes && (
        <p className="text-xs text-slate-500">
          {searchRes.results.length} resultater · <strong>{searchRes.method === "semantic" ? "semantisk søgning" : "nøgleordssøgning"}</strong>
        </p>
      )}
      <div className="flex justify-end">
        <Button size="sm" variant="outline" onClick={() => { setAdding(true); setEditId(null); }}>+ Tilføj note</Button>
      </div>
      {adding && <Card padding="sm"><MemoryForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!display.length && !adding && (
        <Card padding="sm"><p className="py-4 text-center text-sm text-slate-400">{searchRes ? "Ingen resultater" : "Ingen noter endnu"}</p></Card>
      )}
      {display.map(m => (
        <div key={m.id}>
          {delId === m.id ? <DelPrompt onConfirm={() => del(m.id)} onCancel={() => setDelId(null)} />
          : editId === m.id ? <Card padding="sm"><MemoryForm item={m} saving={saving} onSave={d => upd(m.id, d)} onCancel={() => setEditId(null)} /></Card>
          : (
            <Card padding="sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <Badge>{typeLabel(m.memory_type)}</Badge>
                    <span className="text-xs text-slate-400">{fmtDate(m.created_at)}</span>
                    <span className="text-xs text-slate-300">· {Math.round(m.relevance_score * 100)}% relevans</span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-slate-800">{m.content}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button onClick={() => { setEditId(m.id); setAdding(false); }} className="rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100">Rediger</button>
                  <button onClick={() => setDelId(m.id)} className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-50">Slet</button>
                </div>
              </div>
            </Card>
          )}
        </div>
      ))}
    </div>
  );
}

function MemoryForm({ item, saving, onSave, onCancel }: {
  item?: Memory; saving: boolean; onSave: (d: Partial<Memory>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({ content: item?.content ?? "", memory_type: item?.memory_type ?? "career_note", relevance_score: item?.relevance_score?.toString() ?? "0.5" });
  const s = (k: string, v: string) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({ ...d, relevance_score: parseFloat(d.relevance_score) || 0.5 });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-3">
        <div className="col-span-3">
          <F label="Indhold" required>
            <textarea className={I + " resize-none"} rows={3} value={d.content} onChange={e => s("content", e.target.value)} placeholder="Beskriv en erfaring, indsigt, lærdom eller karrierenote…" />
          </F>
        </div>
        <div className="space-y-3">
          <F label="Type">
            <select className={I + " bg-white"} value={d.memory_type} onChange={e => s("memory_type", e.target.value)}>
              {MEMORY_TYPES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </F>
          <F label="Relevans (0–1)">
            <input type="number" step="0.1" min="0" max="1" className={I} value={d.relevance_score} onChange={e => s("relevance_score", e.target.value)} />
          </F>
        </div>
      </div>
      <div className="flex gap-2 border-t border-slate-100 pt-3">
        <Button size="sm" loading={saving} onClick={() => onSave(payload())}>Gem</Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>Annuller</Button>
      </div>
    </div>
  );
}
