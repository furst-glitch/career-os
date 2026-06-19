"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiGet, apiPost, apiPut } from "@/lib/api";

interface Pipeline {
  id: string;
  current_status: string;
  jobs: {
    id: string;
    title: string;
    company: string;
    location: string | null;
    url: string | null;
    description: string | null;
    requirements: string[];
  };
}

interface Document {
  id: string;
  document_role: string;
  document_versions: {
    id: string;
    title: string;
    content: string;
    document_type: string;
    version_number: number;
    created_at: string;
  };
}

interface InterviewPrep {
  id: string;
  content: string;
  status: string;
  generated_at: string;
}

const STATUS_LABELS: Record<string, string> = {
  samtale_1: "Samtale 1",
  samtale_2: "Samtale 2",
  case_stadie: "Case",
  ansoegt: "Ansøgt",
  ansoegning_genereret: "Ansøgning genereret",
  cv_genereret: "CV genereret",
  interviewing: "Interview",
};

export default function InterviewPrepPage() {
  const params = useParams();
  const router = useRouter();
  const pipelineId = params.pipelineId as string;

  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [preps, setPreps] = useState<InterviewPrep[]>([]);
  const [activeDoc, setActiveDoc] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, [pipelineId]);

  async function load() {
    setLoading(true);
    try {
      const [pipelineData, docsData, prepData] = await Promise.all([
        apiGet<Pipeline>(`/applications/${pipelineId}`),
        apiGet<Document[]>(`/applications/${pipelineId}/documents`),
        apiGet<{ preps: InterviewPrep[] }>(`/applications/${pipelineId}/interview-prep`),
      ]);
      setPipeline(pipelineData);
      setDocuments(docsData ?? []);
      setPreps(prepData.preps ?? []);
    } catch {
      setError("Kunne ikke hente forberedelsespakke");
    } finally {
      setLoading(false);
    }
  }

  async function generatePrep() {
    setGenerating(true);
    setError(null);
    try {
      const result = await apiPost<{ content: string; status: string }>(`/applications/${pipelineId}/interview-prep`);
      setPreps((p) => [{ id: Date.now().toString(), content: result.content, status: result.status, generated_at: new Date().toISOString() }, ...p]);
      if (pipeline) setPipeline({ ...pipeline, current_status: result.status });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generering fejlede");
    } finally {
      setGenerating(false);
    }
  }

  async function updateStatus(status: string) {
    if (!pipeline) return;
    await apiPut(`/applications/${pipelineId}`, { current_status: status });
    setPipeline({ ...pipeline, current_status: status });
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!pipeline) {
    return (
      <div className="p-8 text-center">
        <p className="text-slate-500">Ansøgning ikke fundet.</p>
        <button onClick={() => router.push("/interview-center")} className="mt-4 text-sm text-blue-600 hover:underline">
          Tilbage til Interview Center
        </button>
      </div>
    );
  }

  const job = pipeline.jobs;
  const latestPrep = preps[0] ?? null;
  const cvDoc = documents.find((d) => d.document_role === "cv" || d.document_versions?.document_type === "cv");
  const coverLetterDoc = documents.find((d) => d.document_role === "cover_letter" || d.document_versions?.document_type === "cover_letter");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <button onClick={() => router.push("/interview-center")} className="mb-2 text-xs text-slate-400 hover:text-slate-600">
            ← Interview Center
          </button>
          <h1 className="text-2xl font-bold text-slate-900">{job?.title ?? "Ukendt stilling"}</h1>
          <p className="text-slate-600">{job?.company}{job?.location ? ` · ${job.location}` : ""}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-purple-100 px-3 py-1 text-sm font-medium text-purple-700">
            {STATUS_LABELS[pipeline.current_status] ?? pipeline.current_status}
          </span>
          {job?.url && (
            <a href={job.url} target="_blank" rel="noopener noreferrer"
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">
              Vis jobopslag
            </a>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Venstre: Dokumenter + Status */}
        <div className="space-y-4 lg:col-span-1">
          {/* Status opdatering */}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Status</p>
            <div className="flex flex-col gap-1.5">
              {["samtale_1", "samtale_2", "case_stadie", "tilbud", "ansat", "afslag"].map((s) => (
                <button
                  key={s}
                  onClick={() => updateStatus(s)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium text-left transition-colors ${
                    pipeline.current_status === s
                      ? "bg-purple-100 text-purple-800"
                      : "hover:bg-slate-50 text-slate-600"
                  }`}
                >
                  {STATUS_LABELS[s] ?? s}
                </button>
              ))}
            </div>
          </div>

          {/* Dokumenter */}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Dokumenter sendt
            </p>
            {documents.length === 0 ? (
              <p className="text-xs text-slate-400">Ingen dokumenter tilknyttet endnu.</p>
            ) : (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => setActiveDoc(activeDoc === doc.id ? null : doc.id)}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                      activeDoc === doc.id
                        ? "border-blue-200 bg-blue-50 text-blue-700"
                        : "border-slate-100 hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    <span className="font-medium">{doc.document_versions?.title ?? doc.document_role}</span>
                    <span className="ml-1.5 text-slate-400">v{doc.document_versions?.version_number}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Jobopslag */}
          {job?.description && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Jobopslag</p>
              <p className="text-xs text-slate-600 line-clamp-6">{job.description}</p>
              {job.requirements?.length > 0 && (
                <div className="mt-3">
                  <p className="mb-1 text-xs font-medium text-slate-500">Krav</p>
                  <div className="flex flex-wrap gap-1">
                    {job.requirements.slice(0, 8).map((r) => (
                      <span key={r} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{r}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Højre: Forberedelsespakke */}
        <div className="lg:col-span-2">
          {activeDoc ? (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-900">
                  {documents.find((d) => d.id === activeDoc)?.document_versions?.title ?? "Dokument"}
                </p>
                <button onClick={() => setActiveDoc(null)} className="text-xs text-slate-400 hover:text-slate-600">
                  Luk
                </button>
              </div>
              <pre className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed font-sans">
                {documents.find((d) => d.id === activeDoc)?.document_versions?.content ?? ""}
              </pre>
            </div>
          ) : latestPrep ? (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="font-semibold text-slate-900">Forberedelsespakke</p>
                  <p className="text-xs text-slate-400">
                    Genereret {new Date(latestPrep.generated_at).toLocaleDateString("da-DK")}
                    {" · "}
                    {STATUS_LABELS[latestPrep.status] ?? latestPrep.status}
                  </p>
                </div>
                <button
                  onClick={generatePrep}
                  disabled={generating}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {generating ? "Genererer…" : "Regenerér"}
                </button>
              </div>
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed font-sans">
                  {latestPrep.content}
                </pre>
              </div>
            </div>
          ) : (
            <div className="flex h-80 flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-white">
              <div className="text-center px-6">
                <div className="mb-4 text-4xl">📋</div>
                <h3 className="font-semibold text-slate-900">Ingen forberedelsespakke endnu</h3>
                <p className="mt-1 text-sm text-slate-500">
                  Generer en AI-drevet forberedelsespakke med virksomhedsanalyse, rolleforståelse og samtaleguide.
                </p>
                <button
                  onClick={generatePrep}
                  disabled={generating}
                  className="mt-5 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
                >
                  {generating ? (
                    <span className="flex items-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      Genererer (30-60 sek)...
                    </span>
                  ) : (
                    "Generer forberedelsespakke"
                  )}
                </button>
                {pipeline.current_status !== "samtale_1" && pipeline.current_status !== "samtale_2" && (
                  <p className="mt-2 text-xs text-slate-400">
                    Status opdateres automatisk til &quot;Samtale 1&quot; ved generering.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
