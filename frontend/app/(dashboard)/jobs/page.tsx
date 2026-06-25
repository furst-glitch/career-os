"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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

// ── Job Intake Interview Modal ────────────────────────────────────────────────

interface ChatMsg {
  role: "assistant" | "user";
  content: string;
  streaming?: boolean;
}

function JobInterviewModal({ job, onClose }: { job: Job; onClose: () => void }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [initializing, setInitializing] = useState(true);
  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Hent første spørgsmål fra AI
  useEffect(() => {
    let cancelled = false;
    setMessages([{ role: "assistant", content: "", streaming: true }]);
    apiStream(
      `/jobs/${job.id}/interview`,
      { messages: [], extract: false },
      (chunk) => {
        if (cancelled) return;
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, content: m.content + chunk } : m
        ));
      },
      () => {
        if (cancelled) return;
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, streaming: false } : m
        ));
        setInitializing(false);
      },
      (err) => {
        if (cancelled) return;
        const msg = err?.includes("no_api_key") || err?.includes("API-nøgle")
          ? "Ingen AI-nøgle konfigureret. Gå til Indstillinger → AI-udbydere."
          : (err || "AI-intervieweren kunne ikke starte. Prøv igen.");
        setMessages([{ role: "assistant", content: msg, streaming: false }]);
        setInitializing(false);
      },
    ).catch(() => {
      if (!cancelled) {
        setMessages([{ role: "assistant", content: "Forbindelsen til AI fejlede. Prøv at lukke og åbne dialogen igen.", streaming: false }]);
        setInitializing(false);
      }
    });
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || sending || saving || saved) return;

    const userMsg: ChatMsg = { role: "user", content: text };
    const aiPlaceholder: ChatMsg = { role: "assistant", content: "", streaming: true };
    setInput("");
    setSending(true);
    setMessages(prev => [...prev, userMsg, aiPlaceholder]);

    const history = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }));

    await apiStream(
      `/jobs/${job.id}/interview`,
      { messages: history, extract: false },
      (chunk) => {
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, content: m.content + chunk } : m
        ));
      },
      () => {
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, streaming: false } : m
        ));
        setSending(false);
      },
      (err) => {
        const msg = err || "AI-svaret fejlede. Prøv igen.";
        setMessages(prev => prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, content: msg, streaming: false } : m
        ));
        setSending(false);
      },
    ).catch(() => {
      setMessages(prev => prev.map((m, i) =>
        i === prev.length - 1 ? { ...m, content: "Forbindelsesfejl. Prøv igen.", streaming: false } : m
      ));
      setSending(false);
    });
  }, [input, messages, sending, saving, saved, job.id]);

  async function handleSaveClose() {
    setSaving(true);
    const history = messages.map(m => ({ role: m.role, content: m.content }));
    try {
      await apiPost(`/jobs/${job.id}/interview`, { messages: history, extract: true });
      setSaved(true);
      setTimeout(onClose, 800);
    } catch {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center">
      <div className="flex h-[85vh] w-full max-w-lg flex-col rounded-2xl bg-white shadow-2xl sm:h-[70vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">AI-interview om jobbet</h2>
            <p className="text-xs text-slate-400">{job.title} · {job.company}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-800"
              }`}>
                {msg.content || (msg.streaming ? (
                  <span className="inline-flex gap-1">
                    <span className="animate-bounce">·</span>
                    <span className="animate-bounce [animation-delay:0.15s]">·</span>
                    <span className="animate-bounce [animation-delay:0.3s]">·</span>
                  </span>
                ) : "")}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        {saved ? (
          <div className="border-t border-slate-100 px-5 py-4 text-center text-sm text-emerald-600 font-medium">
            Gemt ✓
          </div>
        ) : (
          <div className="border-t border-slate-100 px-5 py-3">
            <div className="flex gap-2">
              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                placeholder="Skriv dit svar…"
                disabled={initializing || sending || saving}
                className="flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || initializing || sending || saving}
                className="rounded-xl bg-blue-600 px-3 py-2 text-white hover:bg-blue-700 disabled:opacity-40"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="m22 2-7 20-4-9-9-4 20-7z"/>
                </svg>
              </button>
            </div>
            <div className="mt-2 flex justify-end">
              <button
                onClick={handleSaveClose}
                disabled={saving || messages.length < 2}
                className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
              >
                {saving ? "Gemmer…" : "Gem og luk"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Quick Generate Modal ──────────────────────────────────────────────────────

const API_BASE_JOBS = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");

function QuickGenModal({ job, initialDocType = "cover_letter", onClose }: { job: Job; initialDocType?: "cover_letter" | "cv"; onClose: (refreshNeeded: boolean) => void }) {
  const router = useRouter();
  const [docType, setDocType] = useState<"cover_letter" | "cv">(initialDocType);
  const [lang, setLang] = useState<"da" | "en">("da");
  const [style, setStyle] = useState("professional");
  const [loading, setLoading] = useState(false);
  const [progressPct, setProgressPct] = useState(0);
  const [progressMsg, setProgressMsg] = useState("");
  const [content, setContent] = useState("");
  const [docId, setDocId] = useState<string | null>(null);
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [markedAnsoegt, setMarkedAnsoegt] = useState(false);
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
          if (payload?.pipeline_id) setPipelineId(payload.pipeline_id as string);
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
          <button
            onClick={() => {
              if (docId) {
                onClose(true);
                router.push(`/apply/${job.id}`);
              } else {
                onClose(false);
              }
            }}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {!content && (
          <div className="border-b border-slate-100 px-6 py-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
                  <span>{progressMsg || "Genererer..."}</span>
                  <span>{progressPct}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all duration-500"
                    style={{ width: `${Math.max(progressPct, 5)}%` }}
                  />
                </div>
                <p className="mt-3 text-center text-xs text-slate-400">
                  Typisk 60-90 sekunder...
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
                <button
                  onClick={() => { onClose(true); router.push(`/apply/${job.id}`); }}
                  className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
                >
                  Åbn i workspace
                </button>
              </>
            )}
          </div>
          <div className="flex gap-2">
            {content && (
              <button
                onClick={() => { setContent(""); setDocId(null); setMarkedAnsoegt(false); }}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                Ny version
              </button>
            )}
            {content && pipelineId && !markedAnsoegt && (
              <button
                onClick={async () => {
                  await apiPut(`/applications/${pipelineId}`, { current_status: "ansoegt" });
                  setMarkedAnsoegt(true);
                  onClose(true);
                }}
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700"
              >
                Ansøgt
              </button>
            )}
            {markedAnsoegt && (
              <span className="rounded-lg bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 border border-violet-200">
                Markeret som ansøgt
              </span>
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

// Pipeline-status dropdown (erstatter den gamle "Ansøgt"-knap)
const PIPELINE_OPTIONS: { value: string; label: string }[] = [
  { value: "gemt",        label: "Gemt" },
  { value: "preparing",   label: "Forbereder" },
  { value: "ansoegt",     label: "Ansøgt" },
  { value: "samtale_1",   label: "1. Samtale" },
  { value: "samtale_2",   label: "2. Samtale" },
  { value: "case_stadie", label: "Case" },
  { value: "tilbud",      label: "Tilbud" },
  { value: "afslag",      label: "Afslag" },
  { value: "ansat",       label: "Ansat" },
];

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

function StatusDropdown({ job, onStatusChange }: {
  job: Job;
  onStatusChange: (jobId: string, pipelineId: string, status: string) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  if (!job.pipeline_id) return null;
  const cur = job.pipeline_status ?? "gemt";
  const cls = STATUS_COLORS[cur] ?? "bg-slate-100 text-slate-700";
  return (
    <div className={`relative flex-1 rounded-lg ${cls}`}>
      <select
        value={cur}
        disabled={saving}
        onChange={async (e) => {
          const s = e.target.value;
          setSaving(true);
          try { await onStatusChange(job.id, job.pipeline_id!, s); }
          finally { setSaving(false); }
        }}
        className="w-full appearance-none bg-transparent py-1.5 pl-2.5 pr-6 text-xs font-medium cursor-pointer disabled:opacity-60 outline-none"
      >
        {PIPELINE_OPTIONS.map(o => (
          <option key={o.value} value={o.value} className="bg-white text-slate-900">
            {o.label}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 opacity-50 text-[10px]">▾</span>
    </div>
  );
}

// ── Add Job Form ──────────────────────────────────────────────────────────────

function AddJobForm({ onSave, onCancel }: { onSave: (job: Job) => void; onCancel: () => void }) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [showOptional, setShowOptional] = useState(false);

  function upd(k: keyof FormState, v: string) {
    setForm(prev => ({ ...prev, [k]: v }));
  }

  const hasDescription = form.description.trim().length >= 100;
  const hasTitle = form.title.trim().length > 0;
  const canSubmit = hasDescription || hasTitle;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
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
      {/* Primær input: jobopslaget */}
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">
          Jobopslag
          <span className="ml-2 rounded bg-blue-50 px-1.5 py-0.5 text-blue-600 font-normal">
            AI udtrækker stilling, firma og deadline automatisk
          </span>
        </label>
        <textarea
          className={`${I} min-h-36 resize-y leading-relaxed`}
          rows={6}
          value={form.description}
          onChange={e => upd("description", e.target.value)}
          placeholder="Indsæt hele jobopslaget her — AI læser stilling, firma, ansøgningsfrist og krav ud af teksten…"
          autoFocus
        />
      </div>

      {/* Valgfri detaljer */}
      <div>
        <button
          type="button"
          onClick={() => setShowOptional(v => !v)}
          className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600"
        >
          <span>{showOptional ? "▾" : "▸"}</span>
          {showOptional ? "Skjul detaljer" : "Tilføj detaljer manuelt (valgfrit)"}
        </button>

        {showOptional && (
          <div className="mt-3 space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <F label="Jobtitel">
                <input className={I} value={form.title} onChange={e => upd("title", e.target.value)} placeholder="Senior Developer" />
              </F>
              <F label="Virksomhed">
                <input className={I} value={form.company} onChange={e => upd("company", e.target.value)} placeholder="Acme ApS" />
              </F>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <F label="Lokation">
                <input className={I} value={form.location} onChange={e => upd("location", e.target.value)} placeholder="København" />
              </F>
              <F label="Job URL">
                <input className={I} type="url" value={form.url} onChange={e => upd("url", e.target.value)} placeholder="https://..." />
              </F>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <F label="Løn min">
                <input className={I} type="number" value={form.salary_min} onChange={e => upd("salary_min", e.target.value)} placeholder="600000" />
              </F>
              <F label="Løn max">
                <input className={I} type="number" value={form.salary_max} onChange={e => upd("salary_max", e.target.value)} placeholder="800000" />
              </F>
            </div>
            <F label="Private noter">
              <textarea className={I} rows={2} value={form.notes} onChange={e => upd("notes", e.target.value)} placeholder="Interessant kultur, kend til CEO…" />
            </F>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-slate-100 pt-4">
        <p className="text-xs text-slate-400">
          {hasDescription
            ? "AI analyserer opslaget og åbner interview-dialog"
            : hasTitle
            ? "Tilføj jobopslag for bedre match og AI-analyse"
            : "Indsæt jobopslaget for at fortsætte"}
        </p>
        <div className="flex gap-3">
          <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">
            Annuller
          </button>
          <button
            type="submit"
            disabled={saving || !canSubmit}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving
              ? hasDescription && !hasTitle
                ? "Analyserer opslag…"
                : "Gemmer…"
              : "Tilføj job"}
          </button>
        </div>
      </div>
    </form>
  );
}

// ── Job Card ──────────────────────────────────────────────────────────────────

function JobCard({ job, onToggleSave, onDelete, onRefreshMatch, onQuickGen, onStatusChange, onInterview }: {
  job: Job;
  onToggleSave: (id: string) => void;
  onDelete: (id: string) => void;
  onRefreshMatch: (id: string) => void;
  onQuickGen: (job: Job, docType: "cv" | "cover_letter") => void;
  onStatusChange: (jobId: string, pipelineId: string, status: string) => Promise<void>;
  onInterview: (job: Job) => void;
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

      {/* Quick-gen og Oversigt */}
      <div className="mt-3 flex gap-2">
        <Link
          href={`/apply/${job.id}`}
          className="flex-1 rounded-lg border border-emerald-200 bg-emerald-50 py-1.5 text-center text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
        >
          Oversigt ✦
        </Link>
        <button
          onClick={() => onQuickGen(job, "cv")}
          className="flex-1 rounded-lg border border-blue-200 bg-blue-50 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-100 transition-colors"
        >
          Hurtig CV
        </button>
        <button
          onClick={() => onQuickGen(job, "cover_letter")}
          className="flex-1 rounded-lg border border-indigo-200 bg-indigo-50 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-100 transition-colors"
        >
          Hurtig ansøgning
        </button>
        <button
          onClick={() => onInterview(job)}
          title="AI-interview om jobbet"
          className="rounded-lg border border-violet-200 bg-violet-50 px-2.5 py-1.5 text-xs font-medium text-violet-600 hover:bg-violet-100 transition-colors"
        >
          ✦ AI
        </button>
        <StatusDropdown job={job} onStatusChange={onStatusChange} />
      </div>

      <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3">
        {job.url && (
          <a href={job.url} target="_blank" rel="noopener noreferrer"
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
            Vis opslag
          </a>
        )}
        {job.pipeline_id && ["samtale_1", "samtale_2", "case_stadie", "interviewing"].includes(job.pipeline_status ?? "") && (
          <a href={`/interview-center/${job.pipeline_id}`}
            className="rounded-lg border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100">
            Forberedelsespakke
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
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [tab, setTab] = useState<FilterTab>("alle");
  const [view, setView] = useState<"list" | "kanban">("list");
  const [toast, setToast] = useState<string | null>(null);
  const [quickGenJob, setQuickGenJob] = useState<{ job: Job; docType: "cv" | "cover_letter" } | null>(null);
  const [interviewJob, setInterviewJob] = useState<Job | null>(null);

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
    setInterviewJob(job);
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

  async function handleStatusChange(jobId: string, pipelineId: string, status: string) {
    await apiPut(`/applications/${pipelineId}`, { current_status: status });
    setJobs(prev => prev.map(j => j.id === jobId ? { ...j, pipeline_status: status } : j));
    const toasts: Record<string, string> = {
      ansoegt:     "Markeret som ansøgt — ansøgningsdato gemt",
      samtale_1:   "1. samtale markeret — forberedelsespakke genereres i baggrunden",
      samtale_2:   "2. samtale markeret — forberedelsespakke opdateres",
      tilbud:      "Tillykke — tilbud registreret",
      afslag:      "Afslag registreret",
      ansat:       "Ansat — tillykke med jobbet",
    };
    showToast(toasts[status] ?? "Status opdateret");
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
              onQuickGen={(j, dt) => setQuickGenJob({ job: j, docType: dt })}
              onStatusChange={handleStatusChange}
              onInterview={setInterviewJob}
            />
          ))}
        </div>
      )}

      {quickGenJob && (
        <QuickGenModal
          job={quickGenJob.job}
          initialDocType={quickGenJob.docType}
          onClose={(refreshNeeded) => {
            setQuickGenJob(null);
            if (refreshNeeded) loadJobs();
          }}
        />
      )}

      {interviewJob && (
        <JobInterviewModal
          job={interviewJob}
          onClose={() => {
            setInterviewJob(null);
            showToast("Job-noter opdateret ✓");
          }}
        />
      )}
    </div>
  );
}
