"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Job {
  id: string;
  title: string;
  company: string;
  location?: string;
  salary_min?: number;
  salary_max?: number;
  match_score?: number;
  job_type?: string;
  remote_type?: string;
}

interface Application {
  id: string;
  current_status: string;
  priority: string;
  deadline?: string;
  notes?: string;
  created_at: string;
  jobs: Job;
}

interface Document {
  id: string;
  document_role: string;
  added_at: string;
  document_versions: {
    id: string;
    title: string;
    version_number: number;
    language: string;
    document_type: string;
    generated_by: string;
    created_at: string;
  };
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  // Pipeline 2.0
  fundet:               { label: "Fundet",              color: "bg-slate-100 text-slate-600" },
  gemt:                 { label: "Gemt",                color: "bg-slate-100 text-slate-700" },
  cv_genereret:         { label: "CV genereret",        color: "bg-sky-100 text-sky-700" },
  ansoegning_genereret: { label: "Ansøgning genereret", color: "bg-blue-100 text-blue-700" },
  ansoegt:              { label: "Ansøgt",              color: "bg-violet-100 text-violet-700" },
  samtale_1:            { label: "Samtale 1",           color: "bg-purple-100 text-purple-700" },
  samtale_2:            { label: "Samtale 2",           color: "bg-fuchsia-100 text-fuchsia-700" },
  case_stadie:          { label: "Case",                color: "bg-amber-100 text-amber-700" },
  tilbud:               { label: "Tilbud",              color: "bg-green-100 text-green-700" },
  ansat:                { label: "Ansat!",              color: "bg-green-200 text-green-800" },
  afslag:               { label: "Afslag",              color: "bg-red-100 text-red-600" },
  // Pipeline 1.0 (bagudkompatibilitet)
  draft:        { label: "Kladde",       color: "bg-slate-100 text-slate-600" },
  preparing:    { label: "Forbereder",   color: "bg-blue-100 text-blue-700" },
  ready:        { label: "Klar",         color: "bg-indigo-100 text-indigo-700" },
  submitted:    { label: "Sendt",        color: "bg-yellow-100 text-yellow-700" },
  screening:    { label: "Screening",    color: "bg-orange-100 text-orange-700" },
  interviewing: { label: "Interview",    color: "bg-purple-100 text-purple-700" },
  offer:        { label: "Tilbud",       color: "bg-green-100 text-green-700" },
  rejected:     { label: "Afvist",       color: "bg-red-100 text-red-600" },
  withdrawn:    { label: "Trukket",      color: "bg-slate-100 text-slate-500" },
  hired:        { label: "Ansat!",       color: "bg-green-200 text-green-800" },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low:    { label: "Lav",    color: "bg-slate-100 text-slate-500" },
  medium: { label: "Medium", color: "bg-blue-100 text-blue-600" },
  high:   { label: "Høj",   color: "bg-orange-100 text-orange-600" },
  dream:  { label: "Dream",  color: "bg-purple-100 text-purple-700" },
};

const STATUS_ORDER = [
  "fundet", "gemt", "cv_genereret", "ansoegning_genereret",
  "ansoegt", "samtale_1", "samtale_2", "case_stadie",
  "tilbud", "ansat", "afslag",
  // Pipeline 1.0
  "draft", "preparing", "ready", "submitted",
  "screening", "interviewing", "offer", "hired", "rejected", "withdrawn",
];

const INTERVIEW_STATUSES = new Set(["samtale_1", "samtale_2"]);

const API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/v1\/?$/, "")}/api/v1`
  : "http://localhost:8000/api/v1";

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, color: "bg-slate-100 text-slate-600" };
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const cfg = PRIORITY_CONFIG[priority] ?? { label: priority, color: "bg-slate-100 text-slate-500" };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

function MatchBadge({ score }: { score?: number }) {
  if (score == null) return null;
  const color = score >= 70 ? "text-green-600 bg-green-50" : score >= 45 ? "text-yellow-600 bg-yellow-50" : "text-red-500 bg-red-50";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>
      {score}% match
    </span>
  );
}

// ── Cover Letter Modal ────────────────────────────────────────────────────────

function CoverLetterModal({
  app,
  onClose,
}: {
  app: Application;
  onClose: () => void;
}) {
  const [lang, setLang] = useState<"da" | "en">("da");
  const [style, setStyle] = useState("professional");
  const [focus, setFocus] = useState("");
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState("");
  const [docId, setDocId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<Array<{ id: string; name: string; language: string; writing_style: string; focus_areas: string[] }>>([]);

  // Load templates on mount
  useEffect(() => {
    apiGet<typeof templates>("/templates?type=cover_letter")
      .then(setTemplates)
      .catch(() => {});
  }, []);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<{ content: string; document_id: string }>(
        `/applications/${app.id}/generate`,
        { language: lang, writing_style: style, focus_areas: focus || undefined }
      );
      setContent(res.content);
      setDocId(res.document_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Generering fejlede";
      if (msg.includes("402") || msg.includes("no_api_key")) {
        setError("Ingen API-nøgle konfigureret — gå til Indstillinger → API-nøgler.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  async function saveEdit() {
    if (!docId || !content) return;
    setSaving(true);
    try {
      await apiPut(`/applications/documents/${docId}`, { content });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  async function downloadPdf() {
    if (!docId) return;
    const { createClient } = await import("@/lib/supabase");
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    const res = await fetch(`${API_BASE}/export/document/${docId}/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ansoegning_${app.jobs.company}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function downloadDocx() {
    if (!docId) return;
    const { createClient } = await import("@/lib/supabase");
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    const res = await fetch(`${API_BASE}/export/document/${docId}/docx`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ansoegning_${app.jobs.company}.docx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">AI-ansøgning</h2>
            <p className="text-sm text-slate-500">
              {app.jobs.title} hos {app.jobs.company}
            </p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* Config */}
        {!content && (
          <div className="border-b border-slate-100 px-6 py-4">
            {/* Template quick-load */}
            {templates.length > 0 && (
              <div className="mb-4">
                <label className="mb-1 block text-xs font-medium text-slate-600">Brug skabelon (valgfri)</label>
                <select
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                  defaultValue=""
                  onChange={e => {
                    const t = templates.find(x => x.id === e.target.value);
                    if (t) {
                      setLang(t.language as "da" | "en");
                      setStyle(t.writing_style);
                      setFocus(t.focus_areas.join(", "));
                    }
                  }}
                >
                  <option value="">— Ingen skabelon —</option>
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            )}
            <div className="grid grid-cols-3 gap-4">
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
                  <option value="narrative">Fortællende</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Fokus (valgfri)</label>
                <input
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Lederskab, cloud, AI…"
                  value={focus}
                  onChange={e => setFocus(e.target.value)}
                />
              </div>
            </div>
            {error && (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
                {error}
              </div>
            )}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {content ? (
            <textarea
              className="h-full w-full resize-none border-0 text-sm text-slate-700 outline-none leading-relaxed"
              value={content}
              onChange={e => setContent(e.target.value)}
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="text-center text-slate-400">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mx-auto mb-3 text-slate-300">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
                <p className="text-sm">Klik på "Generer ansøgning" for at starte</p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-100 px-6 py-4">
          <div className="flex gap-2">
            {docId && (
              <>
                <Button variant="secondary" size="sm" onClick={downloadPdf}>
                  PDF
                </Button>
                <Button variant="secondary" size="sm" onClick={downloadDocx}>
                  DOCX
                </Button>
              </>
            )}
          </div>
          <div className="flex gap-2">
            {content && (
              <Button variant="secondary" size="sm" loading={saving} onClick={saveEdit}>
                {saved ? "Gemt ✓" : "Gem ændringer"}
              </Button>
            )}
            <Button
              size="sm"
              loading={loading}
              onClick={content ? () => { setContent(""); setDocId(null); } : generate}
            >
              {loading ? "Genererer…" : content ? "Generer ny" : "Generer ansøgning"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Interview Prep Modal ──────────────────────────────────────────────────────

function InterviewPrepModal({ app, onClose }: { app: Application; onClose: () => void }) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeStatus, setActiveStatus] = useState(
    INTERVIEW_STATUSES.has(app.current_status) ? app.current_status : "samtale_1"
  );

  async function loadPrep(status: string) {
    setLoading(true);
    setError(null);
    setContent("");
    try {
      const res = await apiGet<{ preps: Array<{ content: string; status: string }> }>(
        `/applications/${app.id}/interview-prep?status=${status}`
      );
      if (res.preps.length > 0) {
        setContent(res.preps[0].content);
      } else {
        // Trigger generation
        const gen = await apiPost<{ content: string }>(`/applications/${app.id}/interview-prep`, {});
        setContent(gen.content || "Ingen forberedelse genereret endnu.");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Kunne ikke hente interviewforberedelse";
      if (msg.includes("402") || msg.includes("no_api_key")) {
        setError("Ingen API-nøgle konfigureret — gå til Indstillinger → AI-udbydere.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadPrep(activeStatus); }, [activeStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-[92vh] w-full max-w-3xl flex-col rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">Interviewforberedelse</h2>
            <p className="text-sm text-slate-500">{app.jobs?.title} hos {app.jobs?.company}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className="flex gap-2 border-b border-slate-100 px-6 py-3">
          {(["samtale_1", "samtale_2"] as const).map(s => (
            <button
              key={s}
              onClick={() => setActiveStatus(s)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                activeStatus === s ? "bg-blue-600 text-white" : "border border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {STATUS_CONFIG[s]?.label ?? s}
            </button>
          ))}
          <button
            onClick={() => loadPrep(activeStatus)}
            className="ml-auto rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-50"
          >
            Regenerér
          </button>
        </div>

        <div className="flex-1 overflow-auto px-6 py-4">
          {loading ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <svg className="mx-auto mb-3 h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                <p className="text-sm text-slate-500">Genererer interviewforberedelse…</p>
                <p className="mt-1 text-xs text-slate-400">Analyserer job og din profil</p>
              </div>
            </div>
          ) : error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
          ) : (
            <div className="prose prose-sm max-w-none">
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-800">{content}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Application Card ──────────────────────────────────────────────────────────

function ApplicationCard({
  app,
  onStatusChange,
  onDelete,
  onGenerateCoverLetter,
  onInterviewPrep,
}: {
  app: Application;
  onStatusChange: (id: string, status: string) => void;
  onDelete: (id: string) => void;
  onGenerateCoverLetter: (app: Application) => void;
  onInterviewPrep: (app: Application) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const nextStatuses = STATUS_ORDER.filter(s => s !== app.current_status).slice(0, 6);
  const isInterview = INTERVIEW_STATUSES.has(app.current_status);

  return (
    <div className={`rounded-xl border bg-white p-4 shadow-sm transition-colors ${
      isInterview ? "border-purple-200 hover:border-purple-300" : "border-slate-200 hover:border-blue-200"
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <StatusBadge status={app.current_status} />
            <PriorityBadge priority={app.priority} />
            <MatchBadge score={app.jobs?.match_score ?? undefined} />
          </div>
          <h3 className="font-semibold text-slate-900 truncate">{app.jobs?.title ?? "Ukendt stilling"}</h3>
          <p className="text-sm text-slate-500">{app.jobs?.company}</p>
          {app.jobs?.location && <p className="text-xs text-slate-400">{app.jobs.location}</p>}
          {app.deadline && (
            <p className="text-xs text-orange-600 mt-1">
              Deadline: {new Date(app.deadline).toLocaleDateString("da-DK")}
            </p>
          )}
        </div>

        <div className="flex shrink-0 flex-col gap-1.5">
          {isInterview && (
            <button
              onClick={() => onInterviewPrep(app)}
              className="rounded-lg border border-purple-200 bg-purple-50 px-2.5 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100 transition-colors"
            >
              Interview-prep
            </button>
          )}
          <button
            onClick={() => onGenerateCoverLetter(app)}
            className="rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-100 transition-colors"
          >
            AI Ansøgning
          </button>
          <button
            onClick={() => setExpanded(e => !e)}
            className="self-end rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d={expanded ? "M18 15l-6-6-6 6" : "M6 9l6 6 6-6"}/>
            </svg>
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 border-t border-slate-100 pt-3 space-y-3">
          {app.notes && <p className="text-xs text-slate-600">{app.notes}</p>}

          <div>
            <p className="mb-1.5 text-xs font-medium text-slate-500">Skift status:</p>
            <div className="flex flex-wrap gap-1.5">
              {nextStatuses.map(s => (
                <button
                  key={s}
                  onClick={() => onStatusChange(app.id, s)}
                  className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 transition-colors"
                >
                  → {STATUS_CONFIG[s]?.label ?? s}
                </button>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => onDelete(app.id)}
              className="text-xs text-red-500 hover:text-red-700"
            >
              Slet ansøgning
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Add Application Modal ─────────────────────────────────────────────────────

interface JobOption { id: string; title: string; company: string; pipeline_id?: string }

function AddApplicationModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [jobs, setJobs] = useState<JobOption[]>([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [priority, setPriority] = useState("medium");
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // GET /jobs returns a raw array (not { jobs: [...] })
    apiGet<JobOption[]>("/jobs").then(r => {
      const available = (r || []).filter((j: JobOption) => !j.pipeline_id);
      setJobs(available);
    });
  }, []);

  async function create() {
    if (!selectedJob) return;
    setSaving(true);
    setError(null);
    try {
      await apiPost("/applications", {
        job_id: selectedJob,
        priority,
        deadline: deadline || undefined,
        notes: notes || undefined,
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fejl ved oprettelse");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">Ny ansøgning</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Job *</label>
            <select
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
              value={selectedJob}
              onChange={e => setSelectedJob(e.target.value)}
            >
              <option value="">Vælg et job fra din liste…</option>
              {jobs.map(j => (
                <option key={j.id} value={j.id}>{j.title} — {j.company}</option>
              ))}
            </select>
            {jobs.length === 0 && (
              <p className="mt-1 text-xs text-slate-400">
                Ingen ledige job — tilføj job under Jobs-siden først.
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Prioritet</label>
            <select
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
              value={priority}
              onChange={e => setPriority(e.target.value)}
            >
              <option value="low">Lav</option>
              <option value="medium">Medium</option>
              <option value="high">Høj</option>
              <option value="dream">Dream job</option>
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Deadline</label>
            <input
              type="date"
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
              value={deadline}
              onChange={e => setDeadline(e.target.value)}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Noter</label>
            <textarea
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
              rows={2}
              placeholder="Intern reference, kontaktperson, noter…"
              value={notes}
              onChange={e => setNotes(e.target.value)}
            />
          </div>

          {error && (
            <p className="text-xs text-red-600">{error}</p>
          )}

          <div className="flex gap-2 justify-end">
            <Button variant="secondary" size="sm" onClick={onClose}>Annuller</Button>
            <Button size="sm" loading={saving} disabled={!selectedJob} onClick={create}>
              Tilføj ansøgning
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

const FILTER_TABS = [
  { key: "all",     label: "Alle" },
  { key: "active",  label: "Aktive" },
  { key: "hired",   label: "Ansat" },
  { key: "rejected", label: "Afvist" },
];

const ACTIVE_STATUSES = new Set([
  "draft", "preparing", "ready", "submitted", "screening", "interviewing", "offer",
  "fundet", "gemt", "cv_genereret", "ansoegning_genereret", "ansoegt",
  "samtale_1", "samtale_2", "case_stadie", "tilbud",
]);

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [showAdd, setShowAdd] = useState(false);
  const [coverLetterApp, setCoverLetterApp] = useState<Application | null>(null);
  const [interviewPrepApp, setInterviewPrepApp] = useState<Application | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await apiGet<{ applications: Application[] }>("/applications");
      setApplications(res.applications || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleStatusChange(id: string, status: string) {
    await apiPut(`/applications/${id}`, { current_status: status });
    setApplications(prev =>
      prev.map(a => a.id === id ? { ...a, current_status: status } : a)
    );
  }

  async function handleDelete(id: string) {
    if (!confirm("Slet denne ansøgning?")) return;
    await apiDelete(`/applications/${id}`);
    setApplications(prev => prev.filter(a => a.id !== id));
  }

  const filtered = applications.filter(a => {
    if (filter === "all") return true;
    if (filter === "active") return ACTIVE_STATUSES.has(a.current_status);
    return a.current_status === filter;
  });

  const stats = {
    total: applications.length,
    active: applications.filter(a => ACTIVE_STATUSES.has(a.current_status)).length,
    interviews: applications.filter(a =>
      ["screening", "interviewing", "samtale_1", "samtale_2", "case_stadie"].includes(a.current_status)
    ).length,
    offers: applications.filter(a =>
      ["offer", "hired", "tilbud", "ansat"].includes(a.current_status)
    ).length,
  };

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
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Ansøgninger</h1>
          <p className="mt-1 text-sm text-slate-500">Spor dine jobansøgninger og generer AI-ansøgninger</p>
        </div>
        <Button onClick={() => setShowAdd(true)}>+ Ny ansøgning</Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "I alt", value: stats.total, color: "text-slate-900" },
          { label: "Aktive", value: stats.active, color: "text-blue-600" },
          { label: "Interviews", value: stats.interviews, color: "text-purple-600" },
          { label: "Tilbud", value: stats.offers, color: "text-green-600" },
        ].map(s => (
          <Card key={s.label} className="text-center py-4">
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-slate-500 mt-1">{s.label}</p>
          </Card>
        ))}
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
        {FILTER_TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setFilter(t.key)}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
              filter === t.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Applications List */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-16 text-center">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 text-slate-300">
            <rect x="2" y="7" width="20" height="14" rx="2"/>
            <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
            <line x1="12" y1="12" x2="12" y2="16"/>
            <line x1="10" y1="14" x2="14" y2="14"/>
          </svg>
          <p className="text-slate-500 font-medium">
            {filter === "all" ? "Ingen ansøgninger endnu" : `Ingen ${FILTER_TABS.find(t => t.key === filter)?.label.toLowerCase()}-ansøgninger`}
          </p>
          <p className="mt-1 text-sm text-slate-400">
            {filter === "all" ? "Tilføj jobs under Jobs-siden og opret ansøgninger her." : ""}
          </p>
          {filter === "all" && (
            <Button className="mt-4" onClick={() => setShowAdd(true)}>+ Tilføj første ansøgning</Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map(app => (
            <ApplicationCard
              key={app.id}
              app={app}
              onStatusChange={handleStatusChange}
              onDelete={handleDelete}
              onGenerateCoverLetter={a => setCoverLetterApp(a)}
              onInterviewPrep={a => setInterviewPrepApp(a)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showAdd && (
        <AddApplicationModal
          onClose={() => setShowAdd(false)}
          onCreated={load}
        />
      )}
      {coverLetterApp && (
        <CoverLetterModal
          app={coverLetterApp}
          onClose={() => setCoverLetterApp(null)}
        />
      )}
      {interviewPrepApp && (
        <InterviewPrepModal
          app={interviewPrepApp}
          onClose={() => setInterviewPrepApp(null)}
        />
      )}
    </div>
  );
}
