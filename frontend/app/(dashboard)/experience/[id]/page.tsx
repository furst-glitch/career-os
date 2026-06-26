"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiGet, apiPost, apiPatch, apiStream, apiUploadStreamWithFields, UploadProgressEvent } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

type Employment = {
  id: string;
  title: string;
  organisation: string | null;
  period_start: string | null;
  period_end: string | null;
  experience_type: string;
  description: string | null;
};

type Doc = {
  id: string;
  doc_type: string;
  file_name: string;
  file_size: number;
  created_at: string;
};

type Fact = {
  id: string;
  fact_type: string;
  value: string;
  unit: string | null;
  confidence: "high" | "medium" | "low";
  requires_confirmation: boolean;
  source_text: string;
  source_page: number | null;
};

type Analysis = {
  id: string;
  analysis_type: string;
  discrepancies_found: number;
  created_at: string;
};

type Recommendation = {
  id: string;
  recommendation_type: string;
  severity: "high" | "medium" | "low" | "info";
  title: string;
  description: string;
  status: "pending" | "confirmed" | "dismissed" | "resolved";
  created_at: string;
};

type Graph = {
  employment: Employment;
  documents: Doc[];
  facts: Fact[];
  analyses: Analysis[];
  recommendations: Recommendation[];
  summary: {
    facts_total: number;
    facts_requiring_confirmation: number;
    open_recommendations: number;
  };
};

type ChatMessage = { role: "user" | "assistant"; content: string };

// ── Style helpers ─────────────────────────────────────────────────────────────

const CONFIDENCE_BADGE: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-red-100 text-red-800",
};

const CONFIDENCE_LABELS: Record<string, string> = {
  high: "Høj", medium: "Middel", low: "Lav",
};

const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-red-200 text-red-900",
  high: "bg-red-100 text-red-800",
  medium: "bg-orange-100 text-orange-800",
  low: "bg-gray-100 text-gray-700",
  info: "bg-blue-100 text-blue-800",
};

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Kritisk", high: "Høj", medium: "Middel", low: "Lav", info: "Info",
};

function formatDate(d: string | null): string {
  if (!d) return "nu";
  return new Date(d).toLocaleDateString("da-DK", { year: "numeric", month: "short" });
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${Math.round(b / 1024)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Documents tab ─────────────────────────────────────────────────────────────

function DocumentsTab({
  graph,
  onRefresh,
  employmentId,
}: {
  graph: Graph;
  onRefresh: () => Promise<void>;
  employmentId: string;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("contract");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgressEvent | null>(null);
  const [error, setError] = useState("");

  async function upload() {
    if (!file) return;
    setUploading(true);
    setProgress(null);
    setError("");
    try {
      await apiUploadStreamWithFields<unknown>(
        "/document-intelligence/analyze",
        file,
        { doc_type: docType, employment_id: employmentId },
        (evt) => setProgress(evt),
      );
      setFile(null);
      setProgress(null);
      await onRefresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload fejlede");
    } finally {
      setUploading(false);
    }
  }

  const DOC_TYPE_LABELS: Record<string, string> = {
    contract: "Kontrakt",
    payslip: "Lønseddel",
    agreement: "Overenskomst",
    pension: "Pensionsopgørelse",
  };

  return (
    <div className="space-y-6">
      <div className="border rounded-lg p-4 space-y-3">
        <h2 className="font-semibold text-sm">Upload dokument</h2>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="text-xs text-gray-600 block mb-0.5">Dokumenttype</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm"
            >
              <option value="contract">Kontrakt</option>
              <option value="payslip">Lønseddel</option>
              <option value="agreement">Overenskomst</option>
              <option value="pension">Pensionsopgørelse</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-600 block mb-0.5">Fil (PDF / DOCX / TXT)</label>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
          </div>
          <button
            onClick={upload}
            disabled={!file || uploading}
            className="px-3 py-1.5 bg-black text-white rounded text-sm disabled:opacity-50"
          >
            {uploading ? "Analyserer..." : "Upload & Analyser"}
          </button>
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        {uploading && progress && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-gray-600">
              <span>{progress.message}</span>
              <span>{progress.pct}%</span>
            </div>
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${progress.pct}%` }}
              />
            </div>
          </div>
        )}
        {uploading && !progress && (
          <p className="text-gray-500 text-sm text-xs">Forbinder til server...</p>
        )}
      </div>

      <div className="space-y-2">
        {graph.documents.length === 0 ? (
          <p className="text-gray-500 text-sm">Ingen dokumenter uploadet endnu.</p>
        ) : (
          graph.documents.map((doc) => (
            <div key={doc.id} className="border rounded p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-gray-400"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <div>
                  <span className="text-sm font-medium">{doc.file_name}</span>
                  <span className="ml-2 px-1.5 py-0.5 rounded bg-gray-100 text-xs">
                    {DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-500">{formatBytes(doc.file_size)}</p>
                <p className="text-xs text-gray-400">
                  {new Date(doc.created_at).toLocaleDateString("da-DK")}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── Facts tab ─────────────────────────────────────────────────────────────────

function FactsTab({ graph, onRefresh }: { graph: Graph; onRefresh: () => Promise<void> }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState<string | null>(null);

  async function approveFact(factId: string) {
    setSaving(factId);
    try {
      await apiPatch(`/document-intelligence/facts/${factId}`, {
        requires_confirmation: false,
        confidence: "high",
      });
      await onRefresh();
    } finally {
      setSaving(null);
    }
  }

  async function correctFact(factId: string, value: string) {
    setSaving(factId);
    try {
      await apiPatch(`/document-intelligence/facts/${factId}`, {
        value,
        requires_confirmation: false,
        confidence: "high",
      });
      setEditing(null);
      await onRefresh();
    } finally {
      setSaving(null);
    }
  }

  if (graph.facts.length === 0) {
    return (
      <p className="text-gray-500 text-sm">
        Ingen fakta ekstraheret endnu. Upload et dokument under &quot;Dokumenter&quot; for at begynde.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {graph.facts.map((fact) => (
        <div
          key={fact.id}
          className={`border rounded-lg p-3 ${
            fact.requires_confirmation ? "border-yellow-300 bg-yellow-50" : ""
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  {fact.fact_type.replace(/_/g, " ")}
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                    CONFIDENCE_BADGE[fact.confidence] ?? "bg-gray-100"
                  }`}
                >
                  {CONFIDENCE_LABELS[fact.confidence] ?? fact.confidence}
                </span>
                {fact.requires_confirmation && (
                  <span className="px-1.5 py-0.5 rounded text-xs bg-yellow-200 text-yellow-900">
                    kræver bekræftelse
                  </span>
                )}
              </div>

              {editing === fact.id ? (
                <div className="flex gap-2 mt-1">
                  <input
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="border rounded px-2 py-1 text-sm flex-1"
                    autoFocus
                  />
                  <button
                    onClick={() => correctFact(fact.id, editValue)}
                    disabled={saving === fact.id}
                    className="px-2 py-1 bg-black text-white rounded text-xs disabled:opacity-50"
                  >
                    Gem
                  </button>
                  <button
                    onClick={() => setEditing(null)}
                    className="px-2 py-1 border rounded text-xs"
                  >
                    Annuller
                  </button>
                </div>
              ) : (
                <p className="font-medium text-sm">
                  {fact.value}
                  {fact.unit ? ` ${fact.unit}` : ""}
                </p>
              )}

              {fact.source_page != null && (
                <p className="text-xs text-gray-400 mt-1">Side {fact.source_page}</p>
              )}
            </div>

            {editing !== fact.id && fact.requires_confirmation && (
              <div className="flex gap-1 shrink-0">
                <button
                  onClick={() => approveFact(fact.id)}
                  disabled={saving === fact.id}
                  className="px-2 py-1 bg-green-600 text-white rounded text-xs disabled:opacity-50"
                >
                  {saving === fact.id ? "..." : "Godkend"}
                </button>
                <button
                  onClick={() => {
                    setEditing(fact.id);
                    setEditValue(fact.value);
                  }}
                  className="px-2 py-1 border rounded text-xs"
                >
                  Ret
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Analysis tab ──────────────────────────────────────────────────────────────

function AnalysisTab({
  graph,
  onRefresh,
  employmentId,
}: {
  graph: Graph;
  onRefresh: () => Promise<void>;
  employmentId: string;
}) {
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);

  async function runAnalysis() {
    setAnalyzing(true);
    setAnalyzeError("");
    try {
      await apiPost(`/employment-graph/${employmentId}/analyze`);
      await onRefresh();
    } catch (e: unknown) {
      setAnalyzeError(e instanceof Error ? e.message : "Analyse fejlede");
    } finally {
      setAnalyzing(false);
    }
  }

  async function updateRec(recId: string, status: string) {
    setSaving(recId);
    try {
      await apiPatch(`/employment-graph/recommendations/${recId}`, { status });
      await onRefresh();
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold">Krydsdokument-analyse</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Sammenligner løn, pension og arbejdstid på tværs af kontrakt og lønseddel
          </p>
        </div>
        <button
          onClick={runAnalysis}
          disabled={analyzing || graph.documents.length < 2}
          title={
            graph.documents.length < 2
              ? "Kræver mindst 2 dokumenter (kontrakt + lønseddel)"
              : undefined
          }
          className="px-3 py-1.5 bg-black text-white rounded text-sm disabled:opacity-50"
        >
          {analyzing ? "Analyserer..." : "Kør analyse"}
        </button>
      </div>

      {analyzeError && <p className="text-red-600 text-sm">{analyzeError}</p>}

      {graph.documents.length < 2 && (
        <p className="text-sm text-gray-500">
          Upload mindst 2 dokumenter (kontrakt + lønseddel) for at køre krydsdokument-analyse.
        </p>
      )}

      {graph.analyses.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-700">Analysehistorik</h3>
          {graph.analyses.map((a) => (
            <div key={a.id} className="border rounded p-3 flex items-center justify-between">
              <span className="text-sm capitalize">{a.analysis_type.replace(/_/g, " ")}</span>
              <div className="flex items-center gap-3">
                <span
                  className={`text-sm font-medium ${
                    a.discrepancies_found > 0 ? "text-red-600" : "text-green-600"
                  }`}
                >
                  {a.discrepancies_found === 0
                    ? "Ingen afvigelser"
                    : `${a.discrepancies_found} afvigelse${a.discrepancies_found > 1 ? "r" : ""}`}
                </span>
                <span className="text-xs text-gray-400">
                  {new Date(a.created_at).toLocaleDateString("da-DK")}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {graph.recommendations.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-700">Anbefalinger</h3>
          {graph.recommendations.map((rec) => (
            <div
              key={rec.id}
              className={`border rounded p-3 ${
                rec.status === "pending"
                  ? "border-orange-200 bg-orange-50"
                  : "opacity-60 bg-gray-50"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span
                      className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                        SEVERITY_BADGE[rec.severity] ?? "bg-gray-100"
                      }`}
                    >
                      {SEVERITY_LABELS[rec.severity] ?? rec.severity}
                    </span>
                    <span className="text-sm font-medium">{rec.title}</span>
                  </div>
                  <p className="text-sm text-gray-600">{rec.description}</p>
                </div>
                {rec.status === "pending" ? (
                  <div className="flex gap-1 shrink-0">
                    <button
                      onClick={() => updateRec(rec.id, "resolved")}
                      disabled={saving === rec.id}
                      className="px-2 py-1 bg-green-600 text-white rounded text-xs disabled:opacity-50"
                    >
                      {saving === rec.id ? "..." : "Løst"}
                    </button>
                    <button
                      onClick={() => updateRec(rec.id, "dismissed")}
                      disabled={saving === rec.id}
                      className="px-2 py-1 border rounded text-xs disabled:opacity-50"
                    >
                      Afvis
                    </button>
                  </div>
                ) : (
                  <span className="text-xs text-gray-500 capitalize shrink-0">{rec.status}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {graph.analyses.length === 0 &&
        graph.recommendations.length === 0 &&
        graph.documents.length >= 2 && (
          <p className="text-sm text-gray-500">
            Klik &quot;Kør analyse&quot; for at sammenligne fakta på tværs af dine dokumenter.
          </p>
        )}
    </div>
  );
}

// ── Chat tab ──────────────────────────────────────────────────────────────────

function ChatTab({ employmentId }: { employmentId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamContent]);

  async function send() {
    if (!input.trim() || streaming) return;
    const userMsg: ChatMessage = { role: "user", content: input.trim() };
    const allMessages = [...messages, userMsg];
    setMessages(allMessages);
    setInput("");
    setStreaming(true);
    setStreamContent("");

    let acc = "";
    try {
      await apiStream(
        `/employment-graph/${employmentId}/chat`,
        { messages: allMessages },
        (chunk) => {
          acc += chunk;
          setStreamContent(acc);
        },
        () => {
          setMessages((prev) => [...prev, { role: "assistant", content: acc }]);
          setStreamContent("");
          setStreaming(false);
        },
        (err) => {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `Fejl: ${err}` },
          ]);
          setStreamContent("");
          setStreaming(false);
        },
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Ukendt fejl";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Fejl: ${msg}` },
      ]);
      setStreamContent("");
      setStreaming(false);
    }
  }

  return (
    <div className="flex flex-col" style={{ height: "480px" }}>
      <div className="flex-1 overflow-y-auto space-y-3 pb-3">
        {messages.length === 0 && !streaming && (
          <p className="text-gray-400 text-sm">
            Stil spørgsmål om dette ansættelsesforhold — AI&apos;en kender alle ekstraherede fakta
            fra dine dokumenter.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-black text-white"
                  : "bg-gray-100 text-gray-900"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {streamContent && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-900 whitespace-pre-wrap">
              {streamContent}
              <span className="animate-pulse">▊</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 pt-3 border-t">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Stil et spørgsmål om kontrakten eller lønsedlen..."
          className="flex-1 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-black"
          disabled={streaming}
        />
        <button
          onClick={send}
          disabled={streaming || !input.trim()}
          className="px-4 py-2 bg-black text-white rounded text-sm disabled:opacity-50"
        >
          {streaming ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function EmploymentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const [graph, setGraph] = useState<Graph | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"documents" | "facts" | "analysis" | "chat">("documents");

  const loadGraph = useCallback(async () => {
    try {
      const data = await apiGet<Graph>(`/employment-graph/${id}`);
      setGraph(data);
    } catch {
      router.push("/experience");
    } finally {
      setLoading(false);
    }
  }, [id, router]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  if (loading) {
    return <div className="p-8 text-gray-500 text-sm">Indlæser...</div>;
  }
  if (!graph) return null;

  const { employment, summary } = graph;

  const TABS = [
    { key: "documents" as const, label: "Dokumenter" },
    { key: "facts" as const, label: `Fakta${summary.facts_total > 0 ? ` (${summary.facts_total})` : ""}` },
    { key: "analysis" as const, label: `Analyse${summary.open_recommendations > 0 ? ` (${summary.open_recommendations})` : ""}` },
    { key: "chat" as const, label: "Chat" },
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => router.push("/experience")}
          className="text-sm text-gray-500 hover:text-gray-900 mb-3 flex items-center gap-1"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
          Tilbage til Arbejdsgraf
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{employment.title}</h1>
            <p className="text-gray-500 mt-0.5">
              {employment.organisation && `${employment.organisation} · `}
              {formatDate(employment.period_start)} – {formatDate(employment.period_end)}
            </p>
          </div>
          <div className="flex gap-2 text-xs flex-wrap justify-end">
            {summary.facts_total > 0 && (
              <span className="px-2 py-1 rounded bg-gray-100 text-gray-700">
                {summary.facts_total} fakta
              </span>
            )}
            {summary.facts_requiring_confirmation > 0 && (
              <span className="px-2 py-1 rounded bg-yellow-100 text-yellow-800">
                {summary.facts_requiring_confirmation} afventer
              </span>
            )}
            {summary.open_recommendations > 0 && (
              <span className="px-2 py-1 rounded bg-red-100 text-red-800">
                {summary.open_recommendations} anbefalinger
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b flex gap-6">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`pb-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === key
                ? "border-black text-black"
                : "border-transparent text-gray-500 hover:text-gray-900"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "documents" && (
        <DocumentsTab graph={graph} onRefresh={loadGraph} employmentId={id} />
      )}
      {tab === "facts" && <FactsTab graph={graph} onRefresh={loadGraph} />}
      {tab === "analysis" && (
        <AnalysisTab graph={graph} onRefresh={loadGraph} employmentId={id} />
      )}
      {tab === "chat" && <ChatTab employmentId={id} />}
    </div>
  );
}
