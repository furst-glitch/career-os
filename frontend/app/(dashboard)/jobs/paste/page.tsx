"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ImportedJob {
  id: string;
  title: string;
  company: string;
  location: string | null;
  url: string | null;
  match_score: number | null;
  match_breakdown: Record<string, number> | null;
  matched_skills: string[] | null;
  missing_requirements: string[] | null;
  extracted_deadline: string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const BREAKDOWN_LABELS: Record<string, string> = {
  skills: "Kompetencer",
  experience: "Erfaring",
  profile: "Profil",
  preferences: "Præferencer",
  certifications: "Certifikater",
};

// ── Components ────────────────────────────────────────────────────────────────

function MatchBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const pct = Math.round(score);
  const color =
    pct >= 70 ? "bg-green-100 text-green-700 ring-green-300" :
    pct >= 45 ? "bg-yellow-100 text-yellow-700 ring-yellow-300" :
                "bg-slate-100 text-slate-600 ring-slate-200";
  const label =
    pct >= 70 ? "Godt match" :
    pct >= 45 ? "Muligt match" :
                "Svagt match";
  return (
    <div className="flex flex-col items-end gap-0.5">
      <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-bold ring-1 ${color}`}>
        {pct}%
      </span>
      <span className="text-xs text-slate-400">{label}</span>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Mode = "url" | "text";

export default function PasteJobPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("url");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportedJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inp =
    "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const payload: Record<string, string> =
        mode === "url" ? { url: url.trim() } : { text: text.trim() };
      const job = await apiPost<ImportedJob>("/jobs/paste", payload);
      setResult(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Noget gik galt — prøv igen");
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setResult(null);
    setUrl("");
    setText("");
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Indsæt jobopslag</h1>
        <p className="mt-1 text-sm text-slate-500">
          Indsæt et link eller kopiér jobteksten — AI udtrækker titel, firma og deadline automatisk
        </p>
      </div>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Mode switcher */}
          <div className="flex rounded-xl border border-slate-200 bg-slate-50 p-1">
            {(["url", "text"] as Mode[]).map(m => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
                  mode === m
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {m === "url" ? "Link / URL" : "Kopiér tekst"}
              </button>
            ))}
          </div>

          {/* Main input */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            {mode === "url" ? (
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Job-URL</label>
                <input
                  type="url"
                  className={inp}
                  placeholder="https://www.jobindex.dk/vis-job/..."
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  autoFocus
                  required
                />
                <p className="mt-1 text-xs text-slate-400">
                  Jobindex, Jobnet, Ofir og de fleste andre jobportaler understøttes
                </p>
              </div>
            ) : (
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-600">Jobtekst</label>
                <textarea
                  className={`${inp} min-h-52 resize-y leading-relaxed`}
                  placeholder="Kopiér og indsæt hele jobopslaget her — stillingsbeskrivelse, krav, virksomhedsinfo…"
                  value={text}
                  onChange={e => setText(e.target.value)}
                  autoFocus
                  required
                />
              </div>
            )}
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || (mode === "url" ? !url.trim() : !text.trim())}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? (
              <>
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {mode === "url" ? "Henter og analyserer opslaget…" : "Analyserer jobtekst…"}
              </>
            ) : (
              "Importér og beregn match"
            )}
          </button>
        </form>
      ) : (
        /* ── Result preview ── */
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
            {/* Job header */}
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <h2 className="text-lg font-semibold text-slate-900 leading-snug">{result.title}</h2>
                <p className="mt-0.5 text-sm font-medium text-slate-600">{result.company}</p>
                {result.location && (
                  <p className="mt-0.5 text-xs text-slate-400">{result.location}</p>
                )}
                {result.extracted_deadline && (
                  <p className="mt-1 text-xs text-amber-600 font-medium">
                    Frist: {new Date(result.extracted_deadline).toLocaleDateString("da-DK", { day: "numeric", month: "long", year: "numeric" })}
                  </p>
                )}
              </div>
              <MatchBadge score={result.match_score} />
            </div>

            {/* Match breakdown bars */}
            {result.match_breakdown && Object.keys(result.match_breakdown).length > 0 && (
              <div className="grid grid-cols-5 gap-1 border-t border-slate-100 pt-4">
                {Object.entries(result.match_breakdown).map(([key, val]) => (
                  <div key={key}>
                    <div className="mb-1 truncate text-xs text-slate-400">
                      {BREAKDOWN_LABELS[key] ?? key}
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-blue-500 transition-all"
                        style={{ width: `${Math.min(100, val)}%` }}
                      />
                    </div>
                    <div className="mt-0.5 text-xs text-slate-400">{Math.round(val)}%</div>
                  </div>
                ))}
              </div>
            )}

            {/* Skills pills */}
            {((result.matched_skills?.length ?? 0) > 0 || (result.missing_requirements?.length ?? 0) > 0) && (
              <div className="space-y-2 border-t border-slate-100 pt-4">
                {(result.matched_skills?.length ?? 0) > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {result.matched_skills!.map(s => (
                      <span key={s} className="rounded bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-200">
                        ✓ {s}
                      </span>
                    ))}
                  </div>
                )}
                {(result.missing_requirements?.length ?? 0) > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {result.missing_requirements!.map(r => (
                      <span key={r} className="rounded bg-red-50 px-2 py-0.5 text-xs font-medium text-red-600 ring-1 ring-red-200">
                        − {r}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Status + link */}
            <div className="flex items-center gap-3 border-t border-slate-100 pt-4">
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                Gemt i Mine Jobs ✓
              </span>
              {result.url && (
                <a
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline"
                >
                  Vis originalt opslag ↗
                </a>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={resetForm}
              className="flex-1 rounded-xl border border-slate-200 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Indsæt et til
            </button>
            <button
              onClick={() => router.push(`/apply/${result.id}`)}
              className="flex-1 rounded-xl border border-emerald-200 bg-emerald-50 py-3 text-sm font-medium text-emerald-700 hover:bg-emerald-100"
            >
              Åbn workspace ✦
            </button>
            <button
              onClick={() => router.push("/jobs")}
              className="flex-1 rounded-xl bg-blue-600 py-3 text-sm font-medium text-white hover:bg-blue-700"
            >
              Mine Jobs →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
