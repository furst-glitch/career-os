"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Template {
  id: string;
  name: string;
  type: string;
  language: string;
  content: string;
  writing_style: string;
  focus_areas: string[];
  created_at: string;
  updated_at: string;
}

const EMPTY_FORM = {
  name: "",
  type: "cover_letter",
  language: "da",
  content: "",
  writing_style: "professional",
  focus_areas: [] as string[],
};

const TYPE_LABELS: Record<string, string> = {
  cover_letter: "Ansøgningsbrev",
  cv_summary: "CV Sammenfatning",
  custom: "Brugerdefineret",
};

const STYLE_LABELS: Record<string, string> = {
  professional: "Professionel",
  enthusiastic: "Entusiastisk",
  concise: "Kortfattet",
  storytelling: "Fortælling",
};

const FOCUS_OPTIONS = [
  "lederskab", "tekniske kompetencer", "resultater", "teamwork",
  "innovation", "kundekontakt", "projektledelse", "kommunikation",
];

const I = "w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 bg-white";

// ── Template Form ─────────────────────────────────────────────────────────────

function TemplateForm({
  initial,
  onSave,
  onCancel,
  saving,
}: {
  initial: typeof EMPTY_FORM;
  onSave: (data: typeof EMPTY_FORM) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState(initial);

  function upd<K extends keyof typeof EMPTY_FORM>(k: K, v: (typeof EMPTY_FORM)[K]) {
    setForm(prev => ({ ...prev, [k]: v }));
  }

  function toggleFocus(f: string) {
    setForm(prev => ({
      ...prev,
      focus_areas: prev.focus_areas.includes(f)
        ? prev.focus_areas.filter(x => x !== f)
        : [...prev.focus_areas, f],
    }));
  }

  return (
    <form
      onSubmit={e => { e.preventDefault(); onSave(form); }}
      className="space-y-4"
    >
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Navn *</label>
          <input
            className={I}
            value={form.name}
            onChange={e => upd("name", e.target.value)}
            placeholder="Min standard-skabelon"
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Type</label>
          <select className={I} value={form.type} onChange={e => upd("type", e.target.value)}>
            {Object.entries(TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Sprog</label>
          <select className={I} value={form.language} onChange={e => upd("language", e.target.value)}>
            <option value="da">Dansk</option>
            <option value="en">English</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Skrivestil</label>
          <select className={I} value={form.writing_style} onChange={e => upd("writing_style", e.target.value)}>
            {Object.entries(STYLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="mb-2 block text-xs font-medium text-slate-600">Fokusområder</label>
        <div className="flex flex-wrap gap-2">
          {FOCUS_OPTIONS.map(f => (
            <button
              key={f}
              type="button"
              onClick={() => toggleFocus(f)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                form.focus_areas.includes(f)
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">
          Skabelonindhold
          <span className="ml-1 font-normal text-slate-400">(brug {"{job_title}"}, {"{company}"}, {"{candidate_name}"} som pladsholdere)</span>
        </label>
        <textarea
          className={I}
          rows={8}
          value={form.content}
          onChange={e => upd("content", e.target.value)}
          placeholder="Kære {company},&#10;&#10;Jeg søger hermed stillingen som {job_title}…"
        />
      </div>

      <div className="flex justify-end gap-3 border-t border-slate-100 pt-4">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
        >
          Annuller
        </button>
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {saving ? "Gemmer…" : "Gem skabelon"}
        </button>
      </div>
    </form>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type FilterType = "all" | "cover_letter" | "cv_summary" | "custom";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState<Template | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  }

  async function loadTemplates() {
    try {
      const data = await apiGet<Template[]>("/templates");
      setTemplates(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadTemplates(); }, []);

  async function handleSave(form: typeof EMPTY_FORM) {
    setSaving(true);
    try {
      if (editTarget) {
        const updated = await apiPut<Template>(`/templates/${editTarget.id}`, form);
        setTemplates(prev => prev.map(t => t.id === editTarget.id ? updated : t));
        showToast("Skabelon opdateret");
      } else {
        const created = await apiPost<Template>("/templates", form);
        setTemplates(prev => [created, ...prev]);
        showToast("Skabelon oprettet");
      }
      setShowForm(false);
      setEditTarget(null);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await apiDelete(`/templates/${id}`);
      setTemplates(prev => prev.filter(t => t.id !== id));
      showToast("Skabelon slettet");
    } finally {
      setDeletingId(null);
    }
  }

  function openEdit(t: Template) {
    setEditTarget(t);
    setShowForm(true);
  }

  const filtered = templates.filter(t => filterType === "all" || t.type === filterType);

  const counts = {
    all: templates.length,
    cover_letter: templates.filter(t => t.type === "cover_letter").length,
    cv_summary: templates.filter(t => t.type === "cv_summary").length,
    custom: templates.filter(t => t.type === "custom").length,
  };

  return (
    <div className="space-y-6">
      {toast && (
        <div className="fixed right-6 top-6 z-50 rounded-lg bg-slate-900 px-4 py-3 text-sm font-medium text-white shadow-lg">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Skabeloner</h1>
          <p className="mt-1 text-sm text-slate-500">
            Gem genanvendelige skabeloner til ansøgningsbreve og CV-tekster
          </p>
        </div>
        <button
          onClick={() => { setEditTarget(null); setShowForm(v => !v); }}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {showForm && !editTarget ? "Luk" : "+ Ny skabelon"}
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-6">
          <h2 className="mb-4 font-semibold text-slate-900">
            {editTarget ? `Rediger: ${editTarget.name}` : "Ny skabelon"}
          </h2>
          <TemplateForm
            initial={editTarget ? {
              name: editTarget.name,
              type: editTarget.type,
              language: editTarget.language,
              content: editTarget.content,
              writing_style: editTarget.writing_style,
              focus_areas: editTarget.focus_areas,
            } : EMPTY_FORM}
            onSave={handleSave}
            onCancel={() => { setShowForm(false); setEditTarget(null); }}
            saving={saving}
          />
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
        {(["all", "cover_letter", "cv_summary", "custom"] as FilterType[]).map(t => (
          <button
            key={t}
            onClick={() => setFilterType(t)}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
              filterType === t ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t === "all" ? "Alle" : TYPE_LABELS[t]}
            <span className="ml-1.5 rounded-full bg-slate-200 px-1.5 py-0.5 text-xs font-semibold text-slate-600">
              {counts[t]}
            </span>
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        </div>
      )}

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-16 text-center">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 text-slate-300">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <p className="font-medium text-slate-600">Ingen skabeloner endnu</p>
          <p className="mt-1 text-sm text-slate-400">
            Opret en skabelon og brug den næste gang du genererer et ansøgningsbrev
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            + Opret første skabelon
          </button>
        </div>
      )}

      {/* Template grid */}
      {!loading && filtered.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map(t => (
            <div
              key={t.id}
              className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <h3 className="truncate font-semibold text-slate-900">{t.name}</h3>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                      {TYPE_LABELS[t.type] ?? t.type}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                      {t.language === "da" ? "Dansk" : "English"}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                      {STYLE_LABELS[t.writing_style] ?? t.writing_style}
                    </span>
                  </div>
                </div>
              </div>

              {t.focus_areas.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {t.focus_areas.map(f => (
                    <span key={f} className="rounded bg-slate-50 px-1.5 py-0.5 text-xs text-slate-500 ring-1 ring-slate-200">
                      {f}
                    </span>
                  ))}
                </div>
              )}

              {t.content && (
                <p className="mt-3 flex-1 text-xs leading-relaxed text-slate-500 line-clamp-3">
                  {t.content}
                </p>
              )}

              <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-3">
                <span className="flex-1 text-xs text-slate-400">
                  {new Date(t.updated_at).toLocaleDateString("da-DK")}
                </span>
                <button
                  onClick={() => openEdit(t)}
                  className="rounded-lg px-3 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
                >
                  Rediger
                </button>
                <button
                  disabled={deletingId === t.id}
                  onClick={() => handleDelete(t.id)}
                  className="rounded-lg px-3 py-1 text-xs font-medium text-red-500 hover:bg-red-50 disabled:opacity-50"
                >
                  {deletingId === t.id ? "…" : "Slet"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
