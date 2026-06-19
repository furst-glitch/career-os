"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, apiStream } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  url: string | null;
  description: string | null;
  requirements: string[];
  salary_min: number | null;
  salary_max: number | null;
  job_type: string;
  remote_type: string;
  notes: string | null;
  is_saved: boolean;
  match_score: number | null;
  pipeline_status: string | null;
  pipeline_id: string | null;
  created_at: string;
}

const EMPTY_FORM = {
  title: "", company: "", location: "", url: "", description: "",
  requirements: "", salary_min: "", salary_max: "",
  job_type: "full_time", remote_type: "hybrid", notes: "",
};

type FormState = typeof EMPTY_FORM;

const STATUS_LABELS: Record<string, string> = {
  // Pipeline 2.0
  fundet: "Fundet", gemt: "Gemt",
  cv_genereret: "CV genereret", ansoegning_genereret: "Ansøgning genereret",
  ansoegt: "Ansøgt", samtale_1: "Samtale 1", samtale_2: "Samtale 2",
  case_stadie: "Case", tilbud: "Tilbud", ansat: "Ansat", afslag: "Afslag",
  // Pipeline 1.0
  draft: "Kladde", preparing: "Forbereder", ready: "Klar",
  submitted: "Indsendt", screening: "Screening", interviewing: "Interview",
  offer: "Tilbud", rejected: "Afvist", withdrawn: "Trukket", hired: "Ansat",
};

const STATUS_COLORS: Record<string, string> = {
  // Pipeline 2.0
  fundet: "bg-slate-100 text-slate-600",
  gemt: "bg-slate-100 text-slate-700",
  cv_genereret: "bg-sky-100 text-sky-700",
  ansoegning_genereret: "bg-blue-100 text-blue-700",
  ansoegt: "bg-violet-100 text-violet-700",
  samtale_1: "bg-purple-100 text-purple-700",
  samtale_2: "bg-fuchsia-100 text-fuchsia-700",
  case_stadie: "bg-amber-100 text-amber-700",
  tilbud: "bg-green-100 text-green-700",
  ansat: "bg-emerald-200 text-emerald-800",
  afslag: "bg-red-100 text-red-600",
  // Pipeline 1.0
  draft: "bg-slate-100 text-slate-600",
  preparing: "bg-blue-100 text-blue-700",
  ready: "bg-cyan-100 text-cyan-700",
  submitted: "bg-violet-100 text-violet-700",
  screening: "bg-yellow-100 text-yellow-700",
  interviewing: "bg-orange-100 text-orange-700",
  offer: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-600",
  withdrawn: "bg-slate-100 text-slate-500",
  hired: "bg-emerald-100 text-emerald-700",
};

// ── Quick Generate Modal ──────────────────────────────────────────────────────

const API_BASE_JOBS = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");

function QuickGenModal({ job, onClose }: { job: Job; onClose: (refreshNeeded: boolean) => void }) {
  const [docType, setDocType] = useState<"cover_letter" | "cv">("cover_letter");
  const [lang, setLang] = useState<"da" | "en">("da");
  const [style, setStyle] = useState("professional");
  const [loading, setLoading] = useState(false);
  const [progressPct, setProgressPct] = useState(0);
  const [progressMsg, setProgressMsg] = useState("");
  const [content, setContent] = useState("");
  const [docId, setDocId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    setProgressPct(0);
    setProgressMsg(lang === "da" ? "Starter..." : "Starting...");
    try {
      await apiStream(
        `/jobs/${job.id}/quickgen`,
        { doc_type: docType, language: lang, writing_style: style },
        () => {},
        (payload) => {
          if (payload?.content) setContent(payload.content as string);
          if (payload?.document_id) setDocId(payload.document_id as string);
        },
        (errMsg) => {
          if (errMsg?.includes("no_api_key")) {
            setError("Ingen API-nøgle konfigureret — gå til Indstillinger → AI-udbydere.");
          } else {
            setError(errMsg || "Generering fejlede");
          }
        },
        (evt) => {
          setProgressPct(evt.pct);
          setProgressMsg(evt.msg);
        },
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Generering fejlede";
      setError(msg);
    } finally {
      setLoading(false);
      setProgressPct(100);
    }
  }

  async function download(format: "pdf" | "docx") {
    if (!docId) return;
    const { createClient } = await import("@/lib/supabase");
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    const res = await fetch(`${API_BASE_JOBS}/api/v1/export/document/${docId}/${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${docType === "cv" ? "cv" : "ansoegning"}_${job.company}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">
              {docType === "cv" ? "Genér job-specifikt CV" : "Genér ansøgning"}
            </h2>
            <p className="text-sm text-slate-500">{job.title} hos {job.company}</p>
          </div>
          <button onClick={() => onClose(!!docId)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {!content && (
          <div className="border-b border-slate-100 px-6 py-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Dokumenttype</label>
                <select
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                  value={docType}
                  onChange={e => setDocType(e.target.value as "cover_letter" | "cv")}
                >
                  <option value="cover_letter">Ansøgning</option>
                  <option value="cv">CV (tilpasset)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Sprog</label>
                <select
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                  value={lang}
                  onChange={e => setLang(e.target.value as "da" | "en")}
                >
                  <option value="da">Dansk</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Stil</label>
                <select
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                  value={style}
                  onChange={e => setStyle(e.target.value)}
                >
                  <option value="professional">Professionel</option>
                  <option value="direct">Direkte</option>
                  <option value="warm">Varm</option>
                  <option value="technical">Teknisk</option>
                </select>
              </div>
            </div>
            {error && (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>
            )}
          </div>
        )}

        <div className="flex-1 overflow-auto px-6 py-4">
          {content ? (
            <textarea
              className="h-full w-full resize-none border-0 text-sm text-slate-700 outline-none leading-relaxed"
              value={content}
              onChange={e => setContent(e.target.value)}
            />
          ) : loading ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 px-8">
              <div className="w-full max-w-sm">
                <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
                  <span>{progressMsg}</span>
                  <span>{progressPct}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all duration-500"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                <p className="mt-3 text-center text-xs text-slate-400">
                  ATS, HR og hiring manager gennemgår udkastet parallelt...
                </p>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-center text-slate-400">
              <div>
                <p className="text-sm">Klik &quot;Generér&quot; for at starte</p>
                <p className="mt-1 text-xs text-slate-400">
                  Dokumentet gemmes automatisk og linkes til dette job
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 px-6 py-4">
          <div className="flex gap-2">
            {docId && (
              <>
                <button onClick={() => download("pdf")} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">PDF</button>
                <button onClick={() => download("docx")} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">DOCX</button>
              </>
            )}
          </div>
          <div className="flex gap-2">
            {content && (
              <button
                onClick={() => { setContent(""); setDocId(null); }}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                Ny version
              </button>
            )}
            <button
              onClick={loading ? undefined : generate}
              disabled={loading}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {loading ? "Genererer…" : content ? "Regenerér" : "Generér"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const JOB_TYPE_LABELS: Record<string, string> = {
  full_time: "Fuldtid", part_time: "Deltid",
  contract: "Kontrakt", freelance: "Freelance", internship: "Praktik",
};

const REMOTE_LABELS: Record<string, string> = {
  remote: "Remote", hybrid: "Hybrid", onsite: "På kontoret",
};

// ── Shared UI ─────────────────────────────────────────────────────────────────

const I = "w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 bg-white";

function F({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      {children}
    </div>
  );
}

function MatchBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-slate-400">–</span>;
  const color = score >= 70 ? "bg-green-100 text-green-700" : score >= 45 ? "bg-yellow-100 text-yellow-700" : "bg-red-100 text-red-600";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>{score}%</span>;
}

function Spinner() {
  return (
    <div className="flex h-64 items-center justify-center">
      <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
    </div>
  );
}

// ── Add Job Form ──────────────────────────────────────────────────────────────

function AddJobForm({ onSave, onCancel }: { onSave: (job: Job) => void; onCancel: () => void }) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  function upd(k: keyof FormState, v: string) {
    setForm(prev => ({ ...prev, [k]: v }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.company.trim()) return;
    setSaving(true);
    try {
      const payload = {
        ...form,
        requirements: form.requirements ? form.requirements.split("\n").map(r => r.trim()).filter(Boolean) : [],
        salary_min: form.salary_min ? parseInt(form.salary_min) : null,
        salary_max: form.salary_max ? parseInt(form.salary_max) : null,
        is_saved: true,
      };
      const job = await apiPost<Job>("/jobs", payload);
      onSave(job);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <F label="Jobtitel *">
          <input className={I} value={form.title} onChange={e => upd("title", e.target.value)} placeholder="Senior Developer" required />
        </F>
        <F label="Virksomhed *">
          <input className={I} value={form.company} onChange={e => upd("company", e.target.value)} placeholder="Acme ApS" required />
        </F>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <F label="Lokation">
          <input className={I} value={form.location} onChange={e => upd("location", e.target.value)} placeholder="København" />
        </F>
        <F label="Job URL">
          <input className={I} type="url" value={form.url} onChange={e => upd("url", e.target.value)} placeholder="https://..." />
        </F>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <F label="Ansættelsestype">
          <select className={I} value={form.job_type} onChange={e => upd("job_type", e.target.value)}>
            {Object.entries(JOB_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </F>
        <F label="Remote">
          <select className={I} value={form.remote_type} onChange={e => upd("remote_type", e.target.value)}>
            {Object.entries(REMOTE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </F>
        <div className="grid grid-cols-2 gap-2">
          <F label="Løn min">
            <input className={I} type="number" value={form.salary_min} onChange={e => upd("salary_min", e.target.value)} placeholder="600000" />
          </F>
          <F label="Løn max">
            <input className={I} type="number" value={form.salary_max} onChange={e => upd("salary_max", e.target.value)} placeholder="800000" />
          </F>
        </div>
      </div>
      <F label="Jobopslag / Beskrivelse">
        <textarea className={I} rows={4} value={form.description} onChange={e => upd("description", e.target.value)} placeholder="Indsæt jobopslag her for bedre match score…" />
      </F>
      <F label="Krav (ét per linje)">
        <textarea className={I} rows={3} value={form.requirements} onChange={e => upd("requirements", e.target.value)} placeholder="Python\nFastAPI\nLederskab" />
      </F>
      <F label="Private noter">
        <textarea className={I} rows={2} value={form.notes} onChange={e => upd("notes", e.target.value)} placeholder="Interessant kultur, kend til CEO…" />
      </F>
      <div className="flex justify-end gap-3 border-t border-slate-100 pt-4">
        <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">Annuller</button>
        <button type="submit" disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
          {saving ? "Gemmer…" : "Tilføj job"}
        </button>
      </div>
    </form>
  );
}

// ── Job Card ──────────────────────────────────────────────────────────────────

function JobCard({ job, onToggleSave, onDelete, onRefreshMatch, onQuickGen }: {
  job: Job;
  onToggleSave: (id: string) => void;
  onDelete: (id: string) => void;
  onRefreshMatch: (id: string) => void;
  onQuickGen: (job: Job) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-slate-900 truncate">{job.title}</h3>
            {job.pipeline_status && (
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[job.pipeline_status] ?? "bg-slate-100 text-slate-600"}`}>
                {STATUS_LABELS[job.pipeline_status] ?? job.pipeline_status}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-sm text-slate-600">{job.company}</p>
          <div className="mt-1.5 flex items-center gap-2 flex-wrap text-xs text-slate-400">
            {job.location && <span>{job.location}</span>}
            {job.location && <span>·</span>}
            <span>{REMOTE_LABELS[job.remote_type] ?? job.remote_type}</span>
            <span>·</span>
            <span>{JOB_TYPE_LABELS[job.job_type] ?? job.job_type}</span>
            {job.salary_min && (
              <>
                <span>·</span>
                <span>{(job.salary_min / 1000).toFixed(0)}k{job.salary_max ? `–${(job.salary_max / 1000).toFixed(0)}k` : "+"} DKK</span>
              </>
            )}
          </div>
          {job.requirements.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {job.requirements.slice(0, 5).map(r => (
                <span key={r} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{r}</span>
              ))}
              {job.requirements.length > 5 && <span className="text-xs text-slate-400">+{job.requirements.length - 5}</span>}
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-400">Match</span>
            <MatchBadge score={job.match_score} />
          </div>
          <button
            onClick={() => onToggleSave(job.id)}
            className={`text-lg transition-colors ${job.is_saved ? "text-yellow-500" : "text-slate-300 hover:text-yellow-400"}`}
            title={job.is_saved ? "Fjern fra gemte" : "Gem job"}
          >★</button>
        </div>
      </div>

      {job.notes && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 italic">{job.notes}</p>
      )}

      {/* Quick-gen knapper */}
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => onQuickGen(job)}
          className="flex-1 rounded-lg border border-blue-200 bg-blue-50 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-100 transition-colors"
        >
          Genér CV
        </button>
        <button
          onClick={() => onQuickGen(job)}
          className="flex-1 rounded-lg border border-indigo-200 bg-indigo-50 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-100 transition-colors"
        >
          Genér ansøgning
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3">
        {job.url && (
          <a href={job.url} target="_blank" rel="noopener noreferrer"
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
            Vis opslag
          </a>
        )}
        <button
          onClick={async () => {
            setRefreshing(true);
            try { await apiGet(`/jobs/${job.id}/match`); onRefreshMatch(job.id); }
            finally { setRefreshing(false); }
          }}
          disabled={refreshing}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {refreshing ? "…" : "Genberegn match"}
        </button>
        <div className="flex-1" />
        <button
          onClick={() => { if (!deleting) { setDeleting(true); onDelete(job.id); } }}
          disabled={deleting}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50 disabled:opacity-50"
        >
          {deleting ? "…" : "Slet"}
        </button>
      </div>
    </div>
  );
}

// ── Kanban ────────────────────────────────────────────────────────────────────

const KANBAN_COLS: { id: string; label: string; statuses: (string | null)[] }[] = [
  { id: "fundet",       label: "Fundet / Gemt",  statuses: [null, "fundet", "gemt"] },
  { id: "genereret",    label: "Genereret",       statuses: ["cv_genereret", "ansoegning_genereret", "draft", "preparing", "ready"] },
  { id: "ansoegt",      label: "Ansøgt",          statuses: ["ansoegt", "submitted", "screening"] },
  { id: "interview",    label: "Interview",       statuses: ["samtale_1", "samtale_2", "case_stadie", "interviewing"] },
  { id: "udfald",       label: "Udfald",          statuses: ["tilbud", "ansat", "afslag", "offer", "hired", "rejected", "withdrawn"] },
];

function KanbanBoard({ jobs, onToggleSave, onDelete, onRefreshMatch }: {
  jobs: Job[];
  onToggleSave: (id: string) => void;
  onDelete: (id: string) => void;
  onRefreshMatch: (id: string) => void;
}) {
  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {KANBAN_COLS.map(col => {
        const colJobs = jobs.filter(j =>
          col.statuses.includes(j.pipeline_status ?? null)
        );
        return (
          <div key={col.id} className="flex w-64 shrink-0 flex-col gap-2">
            <div className="flex items-center justify-between rounded-t-lg bg-slate-100 px-3 py-2">
              <span className="text-sm font-semibold text-slate-700">{col.label}</span>
              <span className="rounded-full bg-white px-2 py-0.5 text-xs font-bold text-slate-500">{colJobs.length}</span>
            </div>
            <div className="flex flex-col gap-2 min-h-24">
              {colJobs.map(job => (
                <div key={job.id} className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                  <div className="flex items-start justify-between gap-1">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-900">{job.title}</p>
                      <p className="truncate text-xs text-slate-500">{job.company}</p>
                    </div>
                    <MatchBadge score={job.match_score} />
                  </div>
                  {job.pipeline_status && (
                    <span className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[job.pipeline_status] ?? "bg-slate-100 text-slate-600"}`}>
                      {STATUS_LABELS[job.pipeline_status]}
                    </span>
                  )}
                  <div className="mt-2 flex items-center gap-1 border-t border-slate-100 pt-2">
                    {job.url && (
                      <a href={job.url} target="_blank" rel="noopener noreferrer"
                        className="rounded px-2 py-0.5 text-xs text-blue-600 hover:bg-blue-50">
                        Vis
                      </a>
                    )}
                    <button
                      onClick={() => onToggleSave(job.id)}
                      className={`text-sm ${job.is_saved ? "text-yellow-500" : "text-slate-300 hover:text-yellow-400"}`}
                      title={job.is_saved ? "Fjern fra gemte" : "Gem job"}
                    >★</button>
                    <div className="flex-1" />
                    <button onClick={() => onDelete(job.id)} className="text-xs text-red-400 hover:text-red-600">×</button>
                  </div>
                </div>
              ))}
              {colJobs.length === 0 && (
                <div className="rounded-lg border-2 border-dashed border-slate-200 px-3 py-6 text-center text-xs text-slate-400">
                  Ingen jobs
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type FilterTab = "alle" | "gemt" | "aktiv" | "afsluttet";

const ACTIVE_STATUSES = new Set([
  "draft", "preparing", "ready", "submitted", "screening", "interviewing", "offer",
  "fundet", "gemt", "cv_genereret", "ansoegning_genereret", "ansoegt",
  "samtale_1", "samtale_2", "case_stadie", "tilbud",
]);
const DONE_STATUSES = new Set(["rejected", "withdrawn", "hired", "afslag", "ansat"]);

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [tab, setTab] = useState<FilterTab>("alle");
  const [view, setView] = useState<"list" | "kanban">("list");
  const [toast, setToast] = useState<string | null>(null);
  const [quickGenJob, setQuickGenJob] = useState<Job | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  }

  async function loadJobs() {
    try {
      const data = await apiGet<Job[]>("/jobs");
      setJobs(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadJobs(); }, []);

  function handleJobAdded(job: Job) {
    setJobs(prev => [job, ...prev]);
    setShowForm(false);
    showToast("Job tilføjet — match score beregnet");
  }

  async function handleToggleSave(id: string) {
    const updated = await apiPost<Job>(`/jobs/${id}/save`, {});
    setJobs(prev => prev.map(j => j.id === id ? { ...j, is_saved: updated.is_saved } : j));
  }

  async function handleDelete(id: string) {
    await apiDelete(`/jobs/${id}`);
    setJobs(prev => prev.filter(j => j.id !== id));
    showToast("Job slettet");
  }

  async function handleRefreshMatch(id: string) {
    const match = await apiGet<{ total: number }>(`/jobs/${id}/match`);
    setJobs(prev => prev.map(j => j.id === id ? { ...j, match_score: match.total } : j));
    showToast("Match score opdateret");
  }

  const filtered = jobs.filter(j => {
    if (tab === "gemt") return j.is_saved && !j.pipeline_status;
    if (tab === "aktiv") return j.pipeline_status && ACTIVE_STATUSES.has(j.pipeline_status);
    if (tab === "afsluttet") return j.pipeline_status && DONE_STATUSES.has(j.pipeline_status);
    return true;
  });

  const counts = {
    alle: jobs.length,
    gemt: jobs.filter(j => j.is_saved && !j.pipeline_status).length,
    aktiv: jobs.filter(j => j.pipeline_status && ACTIVE_STATUSES.has(j.pipeline_status)).length,
    afsluttet: jobs.filter(j => j.pipeline_status && DONE_STATUSES.has(j.pipeline_status)).length,
  };

  if (loading) return <Spinner />;

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
          <h1 className="text-2xl font-bold text-slate-900">Jobs</h1>
          <p className="mt-1 text-sm text-slate-500">Spor jobmuligheder og se dit match mod din karriereprofil</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-slate-200 bg-slate-50">
            <button
              onClick={() => setView("list")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${view === "list" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
              title="Listevisning"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button
              onClick={() => setView("kanban")}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${view === "kanban" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
              title="Kanban"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="5" height="18" rx="1"/><rect x="10" y="3" width="5" height="12" rx="1"/><rect x="17" y="3" width="5" height="15" rx="1"/></svg>
            </button>
          </div>
          <button
            onClick={() => setShowForm(v => !v)}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {showForm ? "Luk" : "+ Tilføj job"}
          </button>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-6">
          <h2 className="mb-4 font-semibold text-slate-900">Tilføj nyt job</h2>
          <AddJobForm onSave={handleJobAdded} onCancel={() => setShowForm(false)} />
        </div>
      )}

      {/* Tabs — hidden in kanban mode */}
      {view === "list" && (
        <div className="flex gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
          {(["alle", "gemt", "aktiv", "afsluttet"] as FilterTab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 rounded-lg py-2 text-sm font-medium capitalize transition-colors ${
                tab === t ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
              <span className="ml-1.5 rounded-full bg-slate-200 px-1.5 py-0.5 text-xs font-semibold text-slate-600">
                {counts[t]}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Kanban view */}
      {view === "kanban" ? (
        <KanbanBoard
          jobs={jobs}
          onToggleSave={handleToggleSave}
          onDelete={handleDelete}
          onRefreshMatch={handleRefreshMatch}
        />
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 py-16 text-center">
          <p className="text-2xl">💼</p>
          <p className="mt-3 font-medium text-slate-700">Ingen jobs her endnu</p>
          <p className="mt-1 text-sm text-slate-400">Klik "+ Tilføj job" for at starte din job-tracking</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
          {filtered.map(job => (
            <JobCard
              key={job.id}
              job={job}
              onToggleSave={handleToggleSave}
              onDelete={handleDelete}
              onRefreshMatch={handleRefreshMatch}
              onQuickGen={j => setQuickGenJob(j)}
            />
          ))}
        </div>
      )}

      {quickGenJob && (
        <QuickGenModal
          job={quickGenJob}
          onClose={(refreshNeeded) => {
            setQuickGenJob(null);
            if (refreshNeeded) loadJobs();
          }}
        />
      )}
    </div>
  );
}
