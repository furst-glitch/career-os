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
  source_text: string | null;
  source_page: number | null;
  document_id: string;
  career_memory_id: string | null;
  created_at: string;
  ai_model: string | null;
  extraction_run_id: string | null;
  // Human verification audit trail (WP4)
  verified_by: string | null;
  verified_at: string | null;
  previous_value: string | null;
  verification_reason: string | null;
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
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string;
  fact_types: string[];
  affected_fact_ids: string[];
  analysis_id: string | null;
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

type ChatMessage = { role: "user" | "assistant"; content: string; basedOn?: BasedOnPayload };

type BasedOnPayload = {
  documents: { id: string; file_name: string; doc_type: string; label: string }[];
  facts_count: number;
  pending_recommendations: { id: string; title: string; severity: string }[];
  analyses_count: number;
};

type TimelineEvent = {
  type: string;
  ts: string;
  label: string;
  icon: string;
  document_id?: string;
  fact_id?: string;
  recommendation_id?: string;
  analysis_id?: string;
  severity?: string;
};

type RecommendationExplain = {
  recommendation: Recommendation;
  facts_used: Fact[];
  documents_used: Doc[];
  rule: { label?: string; description?: string; rule?: string; calculation?: string };
  confidence_reasons: string[];
  analysis_run_at: string | null;
};

type TrustMetrics = {
  facts_total: number;
  facts_verified: number;
  facts_high_confidence: number;
  facts_needing_confirmation: number;
  docs_count: number;
  active_recs: number;
  resolved_recs: number;
  confidence_score: number;
};

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

function fmtDatetime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("da-DK", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

const DOC_TYPE_LABEL: Record<string, string> = {
  contract: "Kontrakt", payslip: "Lønseddel", agreement: "Overenskomst", pension: "Pensionsopgørelse",
};

// WP3: Compute confidence explanation from fact + graph context
function getConfidenceReasons(fact: Fact, graph: Graph): string[] {
  const reasons: string[] = [];
  const doc = graph.documents.find((d) => d.id === fact.document_id);

  if (doc) {
    reasons.push(`Fundet i ${DOC_TYPE_LABEL[doc.doc_type] ?? doc.doc_type}`);
  }

  const sameFacts = graph.facts.filter((f) => f.fact_type === fact.fact_type && f.id !== fact.id);
  if (sameFacts.length > 0) {
    const otherDocs = sameFacts
      .map((f) => graph.documents.find((d) => d.id === f.document_id))
      .filter(Boolean) as Doc[];
    for (const od of otherDocs) {
      reasons.push(`Bekræftet i ${DOC_TYPE_LABEL[od.doc_type] ?? od.doc_type}`);
    }
    const values = sameFacts.map((f) => f.value);
    const conflicts = values.some((v) => v !== fact.value);
    if (!conflicts && fact.confidence === "high") reasons.push("Ingen konflikter fundet");
    if (conflicts) reasons.push("Afvigelse fundet vs. andre dokumenter");
  } else if (fact.confidence === "medium") {
    reasons.push("Kun fundet i ét dokument");
    reasons.push("Ikke verificeret af andre dokumenter");
  }

  if (fact.confidence === "low") {
    reasons.push("AI er usikker på denne oplysning");
    reasons.push("Kræver brugerbekræftelse");
  }

  if (fact.verified_at) {
    reasons.push(`Verificeret af bruger d. ${formatDate(fact.verified_at)}`);
  } else if (fact.requires_confirmation) {
    reasons.push("Afventer brugerbekræftelse");
  }

  return reasons;
}

// WP7: Compute trust metrics from existing graph data (no extra endpoint needed)
function computeTrustMetrics(graph: Graph): TrustMetrics {
  const facts = graph.facts;
  const facts_verified = facts.filter((f) => f.verified_at).length;
  const facts_high = facts.filter((f) => f.confidence === "high").length;
  const facts_medium = facts.filter((f) => f.confidence === "medium").length;
  const facts_needing = facts.filter((f) => f.requires_confirmation && !f.verified_at).length;
  const recs = graph.recommendations;
  const active_recs = recs.filter((r) => r.status === "pending").length;
  const resolved_recs = recs.filter((r) => r.status === "resolved" || r.status === "dismissed").length;

  const raw = facts.length > 0
    ? (facts_high * 100 + facts_medium * 60 + (facts.length - facts_high - facts_medium) * 20) / facts.length
    : 0;
  const verificationBonus = Math.min(20, facts_verified * 3);
  const criticalPenalty = recs.filter((r) => r.status === "pending" && (r.severity === "critical" || r.severity === "high")).length * 15;
  const confidence_score = Math.max(0, Math.min(100, Math.round(raw + verificationBonus - criticalPenalty)));

  return {
    facts_total: facts.length,
    facts_verified,
    facts_high_confidence: facts_high,
    facts_needing_confirmation: facts_needing,
    docs_count: graph.documents.length,
    active_recs,
    resolved_recs,
    confidence_score,
  };
}

// ── WP7: Trust Bar ─────────────────────────────────────────────────────────────

function TrustBar({ metrics }: { metrics: TrustMetrics }) {
  const scoreColor = metrics.confidence_score >= 75
    ? "text-green-700 bg-green-50"
    : metrics.confidence_score >= 50
    ? "text-yellow-700 bg-yellow-50"
    : "text-red-700 bg-red-50";

  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 flex flex-wrap gap-4 items-center text-sm">
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded font-semibold ${scoreColor}`}>
        <span>Tillid</span>
        <span>{metrics.confidence_score}%</span>
      </div>
      <div className="flex flex-wrap gap-3 text-gray-600">
        <span title="Dokumenter uploadet">📄 {metrics.docs_count} dok.</span>
        <span title="Fakta udtrukket af AI">🔍 {metrics.facts_total} fakta</span>
        {metrics.facts_verified > 0 && (
          <span className="text-green-700" title="Fakta verificeret af bruger">✓ {metrics.facts_verified} verificeret</span>
        )}
        {metrics.facts_needing_confirmation > 0 && (
          <span className="text-yellow-700" title="Fakta der afventer bekræftelse">⚠ {metrics.facts_needing_confirmation} afventer</span>
        )}
        {metrics.active_recs > 0 && (
          <span className="text-red-600" title="Aktive anbefalinger">● {metrics.active_recs} aktive anbefalinger</span>
        )}
        {metrics.resolved_recs > 0 && (
          <span className="text-gray-400" title="Løste anbefalinger">○ {metrics.resolved_recs} løst</span>
        )}
      </div>
      <div className="ml-auto flex-1 max-w-32">
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              metrics.confidence_score >= 75 ? "bg-green-500" : metrics.confidence_score >= 50 ? "bg-yellow-400" : "bg-red-400"
            }`}
            style={{ width: `${metrics.confidence_score}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// ── WP2: Provenance Panel ──────────────────────────────────────────────────────

function ProvenancePanel({ fact, graph }: { fact: Fact; graph: Graph }) {
  const doc = graph.documents.find((d) => d.id === fact.document_id);
  const reasons = getConfidenceReasons(fact, graph);

  return (
    <div className="mt-2 rounded bg-gray-50 border border-gray-200 p-3 space-y-2 text-xs text-gray-600">
      <div className="font-semibold text-gray-700 mb-1">Kildedokumentation</div>

      {/* Document source */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <span className="text-gray-400">Dokument</span>
        <span>{doc ? `${DOC_TYPE_LABEL[doc.doc_type] ?? doc.doc_type} — ${doc.file_name}` : "—"}</span>

        {fact.source_page != null && (
          <>
            <span className="text-gray-400">Side</span>
            <span>{fact.source_page}</span>
          </>
        )}

        <span className="text-gray-400">AI-model</span>
        <span className="font-mono">{fact.ai_model ?? "—"}</span>

        <span className="text-gray-400">Udtrukket</span>
        <span>{fmtDatetime(fact.created_at)}</span>

        {fact.verified_at && (
          <>
            <span className="text-gray-400">Verificeret</span>
            <span className="text-green-700 font-medium">{fmtDatetime(fact.verified_at)}</span>
          </>
        )}

        {fact.previous_value && (
          <>
            <span className="text-gray-400">Tidligere værdi</span>
            <span className="line-through text-gray-400">{fact.previous_value}</span>
          </>
        )}

        {fact.verification_reason && (
          <>
            <span className="text-gray-400">Årsag til rettelse</span>
            <span className="italic">{fact.verification_reason}</span>
          </>
        )}
      </div>

      {/* Source text excerpt */}
      {fact.source_text && (
        <div>
          <span className="text-gray-400 block mb-0.5">Tekstudsnit fra dokument</span>
          <blockquote className="border-l-2 border-gray-300 pl-2 italic text-gray-500 line-clamp-3">
            &quot;{fact.source_text}&quot;
          </blockquote>
        </div>
      )}

      {/* WP3: Confidence explanation */}
      <div>
        <span className="text-gray-400 block mb-0.5">Confidence-forklaring</span>
        <ul className="space-y-0.5">
          {reasons.map((r, i) => (
            <li key={i} className="flex items-start gap-1">
              <span className="text-gray-400 mt-0.5">•</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      </div>

      {fact.verified_at && (
        <div className="rounded bg-green-50 border border-green-200 px-2 py-1 text-green-800 font-medium">
          ✓ Verificeret af bruger — AI kan ikke overskrive denne beslutning
        </div>
      )}
    </div>
  );
}

// ── WP1: Recommendation Explain Drawer ────────────────────────────────────────

function RecommendationExplainDrawer({ recId, onClose }: { recId: string; onClose: () => void }) {
  const [explain, setExplain] = useState<RecommendationExplain | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<RecommendationExplain>(`/employment-graph/recommendations/${recId}/explain`)
      .then(setExplain)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Kunne ikke hente forklaring"))
      .finally(() => setLoading(false));
  }, [recId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-base">Forklaring på anbefaling</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>

        <div className="p-4 space-y-4">
          {loading && <p className="text-gray-500 text-sm">Henter forklaring...</p>}
          {error && <p className="text-red-600 text-sm">{error}</p>}

          {explain && (
            <>
              {/* The recommendation itself */}
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-1">Anbefaling</h3>
                <p className="text-sm text-gray-900 font-medium">{explain.recommendation.title}</p>
                <p className="text-sm text-gray-600 mt-0.5">{explain.recommendation.description}</p>
              </div>

              {/* Rule applied */}
              {explain.rule?.label && (
                <div className="rounded bg-blue-50 border border-blue-200 p-3 space-y-1">
                  <p className="text-xs font-semibold text-blue-800">Anvendt regel: {explain.rule.label}</p>
                  {explain.rule.description && <p className="text-xs text-blue-700">{explain.rule.description}</p>}
                  {explain.rule.rule && <p className="text-xs text-blue-600">{explain.rule.rule}</p>}
                  {explain.rule.calculation && (
                    <p className="text-xs font-mono bg-blue-100 rounded px-2 py-0.5 text-blue-800">{explain.rule.calculation}</p>
                  )}
                </div>
              )}

              {/* Documents used */}
              {explain.documents_used.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Dokumenter brugt</h3>
                  <div className="space-y-1">
                    {explain.documents_used.map((doc) => (
                      <div key={doc.id} className="flex items-center gap-2 text-sm">
                        <span className="text-gray-400">📄</span>
                        <span>{DOC_TYPE_LABEL[doc.doc_type] ?? doc.doc_type}</span>
                        <span className="text-gray-400">—</span>
                        <span className="text-gray-600 text-xs">{doc.file_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Facts compared */}
              {explain.facts_used.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Fakta sammenlignet</h3>
                  <div className="space-y-2">
                    {explain.facts_used.map((fact) => {
                      const doc = explain.documents_used.find((d) => d.id === fact.document_id);
                      return (
                        <div key={fact.id} className="rounded border border-gray-200 p-2.5 text-xs">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium text-gray-700">{fact.fact_type.replace(/_/g, " ")}</span>
                            <span className="text-gray-400">{doc ? `${DOC_TYPE_LABEL[doc.doc_type] ?? doc.doc_type} — side ${fact.source_page ?? "?"}` : ""}</span>
                          </div>
                          <p className="text-sm font-semibold text-gray-900">{fact.value}{fact.unit ? ` ${fact.unit}` : ""}</p>
                          {fact.source_text && (
                            <blockquote className="mt-1 border-l-2 border-gray-200 pl-2 italic text-gray-400 line-clamp-2">
                              &quot;{fact.source_text}&quot;
                            </blockquote>
                          )}
                          {fact.verified_at && (
                            <span className="inline-block mt-1 text-green-700 font-medium">✓ Verificeret af bruger</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Confidence reasons */}
              {explain.confidence_reasons.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Confidence-forklaring</h3>
                  <ul className="text-xs space-y-0.5 text-gray-600">
                    {explain.confidence_reasons.map((r, i) => (
                      <li key={i}>• {r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {explain.analysis_run_at && (
                <p className="text-xs text-gray-400">Analyse kørt: {fmtDatetime(explain.analysis_run_at)}</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── WP5: Timeline ──────────────────────────────────────────────────────────────

const TIMELINE_ICON: Record<string, string> = {
  work: "💼", document: "📄", ai: "🤖", check: "✓", analysis: "🔍", alert: "⚠", dismiss: "✗", fact_verified: "✓",
};

function Timeline({ employmentId }: { employmentId: string }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<{ events: TimelineEvent[] }>(`/employment-graph/${employmentId}/timeline`)
      .then((r) => setEvents(r.events))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [employmentId]);

  if (loading) return <p className="text-gray-400 text-sm">Indlæser tidslinje...</p>;
  if (events.length === 0) return <p className="text-gray-400 text-sm">Ingen historik endnu.</p>;

  return (
    <div className="relative pl-6 space-y-4">
      <div className="absolute left-2 top-0 bottom-0 w-px bg-gray-200" />
      {events.map((ev, i) => (
        <div key={i} className="relative flex items-start gap-3">
          <div className={`absolute -left-4 flex h-6 w-6 items-center justify-center rounded-full text-xs border-2 border-white ${
            ev.icon === "check" ? "bg-green-100" : ev.icon === "alert" ? "bg-orange-100" : ev.icon === "dismiss" ? "bg-gray-100" : "bg-blue-100"
          }`}>
            {TIMELINE_ICON[ev.icon] ?? "•"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-800">{ev.label}</p>
            <p className="text-xs text-gray-400 mt-0.5">{fmtDatetime(ev.ts)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── WP6: Based On (chat context references) ────────────────────────────────────

function BasedOn({ payload }: { payload: BasedOnPayload }) {
  const [open, setOpen] = useState(false);
  const total = payload.facts_count + payload.documents.length + payload.analyses_count;
  if (total === 0) return null;

  return (
    <div className="mt-1.5 text-xs">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-gray-400 hover:text-gray-600 underline underline-offset-2"
      >
        Baseret på {payload.documents.length} dok., {payload.facts_count} fakta
        {payload.pending_recommendations.length > 0 ? `, ${payload.pending_recommendations.length} anbefalinger` : ""}
        {open ? " ▲" : " ▼"}
      </button>
      {open && (
        <div className="mt-1.5 rounded border border-gray-200 bg-gray-50 p-2.5 space-y-1.5">
          {payload.documents.map((doc) => (
            <div key={doc.id} className="flex items-center gap-1.5">
              <span className="text-gray-400">📄</span>
              <span>{doc.label} — {doc.file_name}</span>
            </div>
          ))}
          {payload.facts_count > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-gray-400">🔍</span>
              <span>{payload.facts_count} fakta fra dokumenterne</span>
            </div>
          )}
          {payload.pending_recommendations.map((r) => (
            <div key={r.id} className="flex items-center gap-1.5">
              <span className="text-gray-400">⚠</span>
              <span>{r.title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
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
  const [editReason, setEditReason] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function approveFact(factId: string) {
    setSaving(factId);
    try {
      await apiPatch(`/document-intelligence/facts/${factId}`, {
        requires_confirmation: false,
        confidence: "high",
        reason: "Bruger godkendt",
      });
      await onRefresh();
    } finally {
      setSaving(null);
    }
  }

  async function correctFact(factId: string, value: string, reason: string) {
    setSaving(factId);
    try {
      await apiPatch(`/document-intelligence/facts/${factId}`, {
        value,
        requires_confirmation: false,
        confidence: "high",
        reason: reason || undefined,
      });
      setEditing(null);
      setEditReason("");
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
          className={`border rounded-lg ${
            fact.requires_confirmation && !fact.verified_at ? "border-yellow-300 bg-yellow-50" :
            fact.verified_at ? "border-green-200" : "border-gray-200"
          }`}
        >
          <div className="p-3">
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
                  {fact.verified_at ? (
                    <span className="px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-800 font-medium">
                      ✓ Verificeret
                    </span>
                  ) : fact.requires_confirmation ? (
                    <span className="px-1.5 py-0.5 rounded text-xs bg-yellow-200 text-yellow-900">
                      kræver bekræftelse
                    </span>
                  ) : null}
                </div>

                {editing === fact.id ? (
                  <div className="space-y-2 mt-1">
                    <div className="flex gap-2">
                      <input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="border rounded px-2 py-1 text-sm flex-1"
                        placeholder="Ny værdi..."
                        autoFocus
                      />
                    </div>
                    <input
                      value={editReason}
                      onChange={(e) => setEditReason(e.target.value)}
                      className="border rounded px-2 py-1 text-xs w-full"
                      placeholder="Årsag til rettelse (valgfrit)..."
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => correctFact(fact.id, editValue, editReason)}
                        disabled={saving === fact.id}
                        className="px-2 py-1 bg-black text-white rounded text-xs disabled:opacity-50"
                      >
                        Gem
                      </button>
                      <button
                        onClick={() => { setEditing(null); setEditReason(""); }}
                        className="px-2 py-1 border rounded text-xs"
                      >
                        Annuller
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="font-medium text-sm">
                    {fact.value}
                    {fact.unit ? ` ${fact.unit}` : ""}
                  </p>
                )}
              </div>

              <div className="flex gap-1 shrink-0 items-start">
                {editing !== fact.id && fact.requires_confirmation && !fact.verified_at && (
                  <>
                    <button
                      onClick={() => approveFact(fact.id)}
                      disabled={saving === fact.id}
                      className="px-2 py-1 bg-green-600 text-white rounded text-xs disabled:opacity-50"
                    >
                      {saving === fact.id ? "..." : "Godkend"}
                    </button>
                    <button
                      onClick={() => { setEditing(fact.id); setEditValue(fact.value); }}
                      className="px-2 py-1 border rounded text-xs"
                    >
                      Ret
                    </button>
                  </>
                )}
                <button
                  onClick={() => toggleExpand(fact.id)}
                  className="px-2 py-1 border rounded text-xs text-gray-500 hover:text-gray-700"
                  title="Vis kildedokumentation"
                >
                  {expanded.has(fact.id) ? "Skjul" : "Kilde"}
                </button>
              </div>
            </div>
          </div>

          {/* WP2 + WP3 + WP4: Provenance panel */}
          {expanded.has(fact.id) && <ProvenancePanel fact={fact} graph={graph} />}
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
  const [explainRec, setExplainRec] = useState<string | null>(null);
  const [showTimeline, setShowTimeline] = useState(false);

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
                  <button
                    onClick={() => setExplainRec(rec.id)}
                    className="mt-1.5 text-xs text-blue-600 hover:text-blue-800 underline underline-offset-1"
                  >
                    Forklaring →
                  </button>
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

      {/* WP5: Timeline */}
      <div className="border-t pt-4">
        <button
          onClick={() => setShowTimeline((s) => !s)}
          className="text-sm text-gray-500 hover:text-gray-900 flex items-center gap-1"
        >
          <span>{showTimeline ? "▲" : "▼"}</span>
          Hændelseslog for dette ansættelsesforhold
        </button>
        {showTimeline && (
          <div className="mt-3">
            <Timeline employmentId={employmentId} />
          </div>
        )}
      </div>

      {/* WP1: Explain drawer */}
      {explainRec && (
        <RecommendationExplainDrawer recId={explainRec} onClose={() => setExplainRec(null)} />
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
        // WP6: onDone receives the full payload including based_on from the backend
        (payload) => {
          const basedOn = payload?.based_on as BasedOnPayload | undefined;
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: acc, basedOn },
          ]);
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
    <div className="flex flex-col" style={{ height: "520px" }}>
      <div className="flex-1 overflow-y-auto space-y-3 pb-3">
        {messages.length === 0 && !streaming && (
          <p className="text-gray-400 text-sm">
            Stil spørgsmål om dette ansættelsesforhold — AI&apos;en kender alle ekstraherede fakta
            fra dine dokumenter.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] ${m.role === "user" ? "" : ""}`}>
              <div
                className={`rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-black text-white"
                    : "bg-gray-100 text-gray-900"
                }`}
              >
                {m.content}
              </div>
              {/* WP6: Show "Baseret på" for AI messages */}
              {m.role === "assistant" && m.basedOn && (
                <BasedOn payload={m.basedOn} />
              )}
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
  const trustMetrics = computeTrustMetrics(graph);

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

      {/* WP7: Trust Bar — always visible */}
      {(trustMetrics.docs_count > 0 || trustMetrics.facts_total > 0) && (
        <TrustBar metrics={trustMetrics} />
      )}

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
