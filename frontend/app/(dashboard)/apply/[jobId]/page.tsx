"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPost, apiPut, apiStream, type GenerateProgressEvent } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  url: string | null;
  description: string | null;
  full_description: string | null;
  requirements: string[];
  match_score: number | null;
  pipeline_id: string | null;
  pipeline_status: string | null;
  is_saved: boolean;
}

interface GenResult {
  document_id: string;
  content: string;
  pipeline_id: string;
  pipeline_status: string;
}

type Step = "idle" | "generating" | "done" | "error";

interface DocState {
  step: Step;
  pct: number;
  msg: string;
  content: string;
  docId: string | null;
  error: string | null;
}

const EMPTY_DOC: DocState = {
  step: "idle", pct: 0, msg: "", content: "", docId: null, error: null,
};

const STATUS_FLOW = [
  { key: "gemt", label: "Gemt" },
  { key: "cv_genereret", label: "CV genereret" },
  { key: "ansoegning_genereret", label: "Ansøgning genereret" },
  { key: "ansoegt", label: "Ansøgt" },
  { key: "samtale_1", label: "Samtale 1" },
  { key: "samtale_2", label: "Samtale 2" },
  { key: "tilbud", label: "Tilbud" },
  { key: "ansat", label: "Ansat" },
];

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");

// ── Score badge ───────────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null) return null;
  const color =
    score >= 80 ? "bg-emerald-100 text-emerald-700 border-emerald-200" :
    score >= 60 ? "bg-sky-100 text-sky-700 border-sky-200" :
    score >= 40 ? "bg-amber-100 text-amber-700 border-amber-200" :
    "bg-red-100 text-red-600 border-red-200";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-semibold ${color}`}>
      Match {score}%
    </span>
  );
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ pct, msg }: { pct: number; msg: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{msg || "Behandler..."}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
        <div
          className="h-full rounded-full bg-blue-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Document preview ──────────────────────────────────────────────────────────

function DocPreview({
  docId,
  content,
  label,
  filename,
}: {
  docId: string;
  content: string;
  label: string;
  filename: string;
}) {
  async function download(fmt: "pdf" | "docx") {
    const { createClient } = await import("@/lib/supabase");
    const sb = createClient();
    const { data } = await sb.auth.getSession();
    const token = data.session?.access_token;
    const res = await fetch(`${API_BASE}/api/v1/export/document/${docId}/${fmt}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.${fmt}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        <div className="flex gap-2">
          <button
            onClick={() => download("pdf")}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
          >
            PDF
          </button>
          <button
            onClick={() => download("docx")}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            DOCX
          </button>
          <Link
            href={`/applications`}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Åbn i Ansøgninger →
          </Link>
        </div>
      </div>
      <pre className="max-h-64 overflow-y-auto p-4 text-xs leading-relaxed text-slate-700 whitespace-pre-wrap">
        {content}
      </pre>
    </div>
  );
}

// ── Pipeline status tracker ───────────────────────────────────────────────────

function PipelineTracker({ current }: { current: string | null }) {
  const idx = STATUS_FLOW.findIndex(s => s.key === current);
  return (
    <div className="flex items-center gap-0 overflow-x-auto pb-1">
      {STATUS_FLOW.map((s, i) => {
        const done = i < idx;
        const active = i === idx;
        return (
          <div key={s.key} className="flex items-center">
            <div className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium whitespace-nowrap
              ${active ? "bg-blue-600 text-white" : done ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400"}`}
            >
              {done && <span>✓</span>}
              {s.label}
            </div>
            {i < STATUS_FLOW.length - 1 && (
              <div className={`h-px w-4 flex-shrink-0 ${i < idx ? "bg-emerald-300" : "bg-slate-200"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ApplyWorkspacePage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<string | null>(null);
  const [cv, setCv] = useState<DocState>(EMPTY_DOC);
  const [app, setApp] = useState<DocState>(EMPTY_DOC);
  const [markingApplied, setMarkingApplied] = useState(false);
  const [lang, setLang] = useState<"da" | "en">("da");
  const [style, setStyle] = useState("professional");
  const [showReqs, setShowReqs] = useState(false);

  const loadJob = useCallback(async () => {
    try {
      const data = await apiGet<Job>(`/jobs/${jobId}`);
      setJob(data);
      if (data.pipeline_id) {
        setPipelineId(data.pipeline_id);
        setPipelineStatus(data.pipeline_status);
        // Hent eksisterende dokumenter så de ikke forsvinder ved navigation
        try {
          const docsRes = await apiGet<{
            documents: Array<{
              document_role: string;
              document_versions: {
                id: string;
                title: string;
                content: string;
                document_type: string;
              } | null;
            }>;
          }>(`/applications/${data.pipeline_id}/documents`);

          for (const doc of docsRes.documents ?? []) {
            const dv = doc.document_versions;
            if (!dv?.content) continue;
            const loaded: DocState = {
              step: "done",
              pct: 100,
              msg: "",
              content: dv.content,
              docId: dv.id,
              error: null,
            };
            if (doc.document_role === "cv") setCv(loaded);
            else if (doc.document_role === "cover_letter") setApp(loaded);
          }
        } catch (err) {
          console.error("[apply] Kunne ikke hente eksisterende dokumenter:", err);
        }
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => { loadJob(); }, [loadJob]);

  async function ensurePipeline(): Promise<string> {
    if (pipelineId) return pipelineId;
    const entry = await apiPost<{ id: string; current_status: string }>(
      "/applications",
      { job_id: jobId, status: "gemt", priority: "medium" },
    );
    setPipelineId(entry.id);
    setPipelineStatus(entry.current_status);
    return entry.id;
  }

  async function generateDoc(docType: "cv" | "cover_letter") {
    const setter = docType === "cv" ? setCv : setApp;
    setter({ step: "generating", pct: 0, msg: "Starter multi-agent pipeline...", content: "", docId: null, error: null });

    try {
      await ensurePipeline();
      await apiStream(
        `/jobs/${jobId}/quickgen`,
        { doc_type: docType, language: lang, writing_style: style },
        () => {},
        (payload) => {
          if (payload?.content) setter(s => ({ ...s, content: payload.content as string }));
          if (payload?.document_id) setter(s => ({ ...s, docId: payload.document_id as string, step: "done" }));
          if (payload?.pipeline_id) setPipelineId(payload.pipeline_id as string);
          if (payload?.pipeline_status) setPipelineStatus(payload.pipeline_status as string);
        },
        (errMsg) => {
          setter(s => ({
            ...s, step: "error",
            error: errMsg?.includes("no_api_key")
              ? "Ingen API-nøgle — gå til Indstillinger → AI-udbydere."
              : errMsg || "Generering fejlede",
          }));
        },
        (evt: GenerateProgressEvent) => {
          setter(s => ({ ...s, pct: evt.pct, msg: evt.msg }));
        },
      );
    } catch (err) {
      setter(s => ({ ...s, step: "error", error: err instanceof Error ? err.message : "Fejl" }));
    }
  }

  async function markApplied() {
    if (!pipelineId) return;
    setMarkingApplied(true);
    try {
      await apiPut(`/applications/${pipelineId}`, { current_status: "ansoegt" });
      setPipelineStatus("ansoegt");
    } finally {
      setMarkingApplied(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-slate-400 text-sm">Henter job...</div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <p className="text-slate-500">Job ikke fundet.</p>
        <Link href="/jobs" className="text-blue-600 text-sm hover:underline">← Tilbage til jobs</Link>
      </div>
    );
  }

  const cvFilename = `cv_${job.company.replace(/\s+/g, "_")}`;
  const appFilename = `ansoegning_${job.company.replace(/\s+/g, "_")}`;

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-slate-500 mb-1">
            <Link href="/jobs" className="hover:text-blue-600">Jobs</Link>
            <span>/</span>
            <span>Oversigt</span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">{job.title}</h1>
          <p className="text-slate-500">{job.company}{job.location ? ` · ${job.location}` : ""}</p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <ScoreBadge score={job.match_score} />
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Se opslag ↗
            </a>
          )}
        </div>
      </div>

      {/* Pipeline tracker */}
      {pipelineStatus && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium text-slate-500 mb-3 uppercase tracking-wide">Ansøgningsstatus</p>
          <PipelineTracker current={pipelineStatus} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.6fr]">
        {/* Left: Job details */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Stillingsbeskrivelse</h2>
            <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap line-clamp-12">
              {job.full_description || job.description || "Ingen beskrivelse tilgængelig."}
            </p>
          </div>

          {job.requirements && job.requirements.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <button
                onClick={() => setShowReqs(r => !r)}
                className="flex w-full items-center justify-between text-sm font-semibold text-slate-700"
              >
                <span>Krav ({job.requirements.length})</span>
                <span className="text-slate-400">{showReqs ? "▲" : "▼"}</span>
              </button>
              {showReqs && (
                <ul className="mt-3 space-y-1.5">
                  {job.requirements.map((r, i) => (
                    <li key={i} className="flex gap-2 text-sm text-slate-600">
                      <span className="mt-0.5 text-blue-500 flex-shrink-0">•</span>
                      {r}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* Right: Generation workspace */}
        <div className="space-y-5">
          {/* Options */}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-500 mb-3 uppercase tracking-wide">Indstillinger</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Sprog</label>
                <select
                  value={lang}
                  onChange={e => setLang(e.target.value as "da" | "en")}
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="da">Dansk</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Skrivestil</label>
                <select
                  value={style}
                  onChange={e => setStyle(e.target.value)}
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="professional">Professionel</option>
                  <option value="direct">Direkte</option>
                  <option value="warm">Varm og personlig</option>
                  <option value="technical">Teknisk</option>
                  <option value="narrative">Narrativ</option>
                </select>
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Template-stil hentes fra Indstillinger → Layout og bruges automatisk.
            </p>
          </div>

          {/* Step 1: CV */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-slate-800">Trin 1 — Generér CV</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Multi-agent pipeline: CVAgent → ATSAgent → CriticAgent → DesignerAgent → ReviewBoardAgent
                </p>
              </div>
              {cv.step === "done" && (
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">✓ Klar</span>
              )}
            </div>

            {cv.step === "idle" && (
              <button
                onClick={() => generateDoc("cv")}
                className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
              >
                Generér job-specifikt CV
              </button>
            )}

            {cv.step === "generating" && (
              <div className="space-y-3">
                <ProgressBar pct={cv.pct} msg={cv.msg} />
                <p className="text-center text-xs text-slate-400">
                  5 agenter kører — estimeret 80-110 sekunder...
                </p>
              </div>
            )}

            {cv.step === "error" && (
              <div className="space-y-3">
                <p className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{cv.error}</p>
                <button
                  onClick={() => generateDoc("cv")}
                  className="w-full rounded-lg border border-slate-200 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  Prøv igen
                </button>
              </div>
            )}

            {cv.step === "done" && cv.docId && (
              <div className="space-y-3">
                <DocPreview docId={cv.docId} content={cv.content} label="CV" filename={cvFilename} />
                <button
                  onClick={() => { setCv(EMPTY_DOC); generateDoc("cv"); }}
                  className="text-xs text-slate-400 hover:text-slate-600"
                >
                  Regenerér ↺
                </button>
              </div>
            )}
          </div>

          {/* Step 2: Application */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-slate-800">Trin 2 — Generér ansøgning</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Multi-agent pipeline: JobAgent → HRAgent + HMAgent + ATS → CriticAgent → DesignerAgent → ReviewBoardAgent → ApplicationAgent
                </p>
              </div>
              {app.step === "done" && (
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">✓ Klar</span>
              )}
            </div>

            {app.step === "idle" && (
              <button
                onClick={() => generateDoc("cover_letter")}
                className="w-full rounded-lg bg-violet-600 py-2.5 text-sm font-medium text-white hover:bg-violet-700"
              >
                Generér ansøgning
              </button>
            )}

            {app.step === "generating" && (
              <div className="space-y-3">
                <ProgressBar pct={app.pct} msg={app.msg} />
                <p className="text-center text-xs text-slate-400">
                  8 agenter kører — estimeret 75-110 sekunder...
                </p>
              </div>
            )}

            {app.step === "error" && (
              <div className="space-y-3">
                <p className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{app.error}</p>
                <button
                  onClick={() => generateDoc("cover_letter")}
                  className="w-full rounded-lg border border-slate-200 py-2 text-sm text-slate-700 hover:bg-slate-50"
                >
                  Prøv igen
                </button>
              </div>
            )}

            {app.step === "done" && app.docId && (
              <div className="space-y-3">
                <DocPreview docId={app.docId} content={app.content} label="Ansøgning" filename={appFilename} />
                <button
                  onClick={() => { setApp(EMPTY_DOC); generateDoc("cover_letter"); }}
                  className="text-xs text-slate-400 hover:text-slate-600"
                >
                  Regenerér ↺
                </button>
              </div>
            )}
          </div>

          {/* Step 3: Mark as applied */}
          {(cv.step === "done" || app.step === "done") && pipelineStatus !== "ansoegt" && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="font-semibold text-slate-800 mb-3">Trin 3 — Ansøgt</h3>
              <p className="text-sm text-slate-500 mb-4">
                Har du sendt ansøgningen? Markér den som ansøgt for at opdatere din pipeline.
              </p>
              <button
                onClick={markApplied}
                disabled={markingApplied}
                className="w-full rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {markingApplied ? "Opdaterer..." : "✓ Markér som ansøgt"}
              </button>
            </div>
          )}

          {pipelineStatus === "ansoegt" && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-center">
              <p className="text-emerald-700 font-medium">Ansøgning registreret!</p>
              <p className="text-sm text-emerald-600 mt-1">
                Følg status i{" "}
                <Link href="/applications" className="underline hover:text-emerald-700">
                  Ansøgninger
                </Link>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
