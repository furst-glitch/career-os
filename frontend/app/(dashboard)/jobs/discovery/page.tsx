"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface JobSource {
  name: string;
  display_name: string;
  requires_api_key: boolean;
  available: boolean;
  is_default: boolean;
}

interface DiscoveredJob {
  title: string;
  company: string;
  location: string | null;
  url: string | null;
  description: string | null;
  requirements: string[];
  job_type: string;
  remote_type: string;
  salary_min: number | null;
  salary_max: number | null;
  source: string;
  external_id: string | null;
  deadline: string | null;
  match_score: number;
  match_breakdown: {
    skills: number;
    experience: number;
    preferences: number;
    certifications: number;
  };
  matched_skills: string[];
  ai_summary?: string;
}

interface SearchResult {
  search_id: string | null;
  query: string;
  location: string | null;
  total: number;
  source_stats: Record<string, number>;
  results: DiscoveredJob[];
}

interface SearchHistory {
  id: string;
  query: string;
  location: string | null;
  results_count: number;
  sources: string[];
  created_at: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const JOB_TYPE_LABELS: Record<string, string> = {
  full_time: "Fuldtid", part_time: "Deltid",
  contract: "Kontrakt", freelance: "Freelance", internship: "Praktik",
};

const REMOTE_LABELS: Record<string, string> = {
  remote: "Remote", hybrid: "Hybrid", onsite: "På kontoret",
};

const SOURCE_COLORS: Record<string, string> = {
  jobnet: "bg-blue-100 text-blue-700",
  jobindex: "bg-violet-100 text-violet-700",
  ofir: "bg-orange-100 text-orange-700",
  linkedin: "bg-sky-100 text-sky-700",
  indeed: "bg-indigo-100 text-indigo-700",
};

// ── Match Badge ───────────────────────────────────────────────────────────────

function MatchBadge({ score }: { score: number }) {
  const pct = Math.round(score);
  const color =
    pct >= 70 ? "bg-green-100 text-green-700 ring-green-300" :
    pct >= 45 ? "bg-yellow-100 text-yellow-700 ring-yellow-300" :
                "bg-slate-100 text-slate-600 ring-slate-200";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${color}`}>
      {pct}% match
    </span>
  );
}

// ── Job Card ──────────────────────────────────────────────────────────────────

function JobCard({
  job,
  onSave,
  onGenerateApplication,
  savedIds,
}: {
  job: DiscoveredJob;
  onSave: (job: DiscoveredJob) => void;
  onGenerateApplication: (job: DiscoveredJob, savedJobId: string) => void;
  savedIds: Set<string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const isSaved = savedIds.has(job.external_id ?? `${job.title}|${job.company}`);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      {/* Header */}
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-slate-900">{job.title}</h3>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${SOURCE_COLORS[job.source] ?? "bg-slate-100 text-slate-600"}`}>
                {job.source}
              </span>
            </div>
            <p className="mt-0.5 text-sm font-medium text-slate-600">{job.company}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-400">
              {job.location && <span>{job.location}</span>}
              {job.location && <span>·</span>}
              <span>{REMOTE_LABELS[job.remote_type] ?? job.remote_type}</span>
              <span>·</span>
              <span>{JOB_TYPE_LABELS[job.job_type] ?? job.job_type}</span>
              {job.deadline && (
                <>
                  <span>·</span>
                  <span className="text-amber-600">Frist: {job.deadline}</span>
                </>
              )}
            </div>
            {job.ai_summary && (
              <p className="mt-2 text-xs italic text-slate-500">{job.ai_summary}</p>
            )}
          </div>
          <div className="shrink-0">
            <MatchBadge score={job.match_score} />
          </div>
        </div>

        {/* Matched skills */}
        {job.matched_skills.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {job.matched_skills.map(s => (
              <span key={s} className="rounded bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-200">
                {s}
              </span>
            ))}
          </div>
        )}

        {/* Match breakdown bar */}
        {job.match_score > 0 && (
          <div className="mt-3 grid grid-cols-4 gap-1">
            {Object.entries(job.match_breakdown).map(([key, val]) => {
              const labels: Record<string, string> = {
                skills: "Kompetencer", experience: "Erfaring",
                preferences: "Præferencer", certifications: "Certifikater",
              };
              return (
                <div key={key}>
                  <div className="mb-1 text-xs text-slate-400">{labels[key]}</div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-blue-500 transition-all"
                      style={{ width: `${Math.min(100, val)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Expandable description */}
      {job.description && (
        <div className="border-t border-slate-100 px-5 py-3">
          <button
            onClick={() => setExpanded(v => !v)}
            className="flex w-full items-center justify-between text-xs font-medium text-slate-500 hover:text-slate-700"
          >
            <span>Beskrivelse</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              className={`transition-transform ${expanded ? "rotate-180" : ""}`}>
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          {expanded && (
            <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-slate-600">
              {job.description.slice(0, 1000)}{job.description.length > 1000 ? "…" : ""}
            </p>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 border-t border-slate-100 px-5 py-3">
        {job.url && (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Vis opslag ↗
          </a>
        )}
        <div className="flex-1" />
        <button
          disabled={saving || isSaved}
          onClick={async () => {
            setSaving(true);
            try { onSave(job); }
            finally { setSaving(false); }
          }}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
            isSaved
              ? "bg-green-50 text-green-700 ring-1 ring-green-200"
              : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
          } disabled:opacity-60`}
        >
          {isSaved ? "Gemt ✓" : saving ? "Gemmer…" : "Gem job"}
        </button>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function JobDiscoveryPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [sources, setSources] = useState<JobSource[]>([]);
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [history, setHistory] = useState<SearchHistory[]>([]);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [savedJobMap, setSavedJobMap] = useState<Record<string, string>>({});
  const [toast, setToast] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  }

  useEffect(() => {
    apiGet<JobSource[]>("/job-discovery/sources")
      .then(s => {
        setSources(s);
        setSelectedSources(s.filter(x => x.is_default).map(x => x.name));
      })
      .catch(() => {});
    apiGet<SearchHistory[]>("/job-discovery/history")
      .then(setHistory)
      .catch(() => {});
    inputRef.current?.focus();
  }, []);

  async function handleSearch(e?: React.FormEvent) {
    e?.preventDefault();
    if (!query.trim() || searching) return;
    setSearching(true);
    setResult(null);
    try {
      const data = await apiPost<SearchResult>("/job-discovery/search", {
        query: query.trim(),
        location: location.trim() || null,
        sources: selectedSources.length ? selectedSources : null,
        ai_enrichment: true,
      });
      setResult(data);
      // Refresh history
      apiGet<SearchHistory[]>("/job-discovery/history").then(setHistory).catch(() => {});
    } catch (err) {
      showToast("Søgning fejlede — prøv igen");
    } finally {
      setSearching(false);
    }
  }

  async function handleSave(job: DiscoveredJob) {
    try {
      const saved = await apiPost<{ id: string }>("/job-discovery/save", { result: job });
      const key = job.external_id ?? `${job.title}|${job.company}`;
      setSavedIds(prev => new Set([...prev, key]));
      setSavedJobMap(prev => ({ ...prev, [key]: saved.id }));
      showToast(`"${job.title}" gemt i Jobs`);
    } catch {
      showToast("Kunne ikke gemme jobbet");
    }
  }

  function toggleSource(name: string) {
    setSelectedSources(prev =>
      prev.includes(name) ? prev.filter(s => s !== name) : [...prev, name]
    );
  }

  const topResults = result?.results.filter(j => j.match_score >= 50) ?? [];
  const otherResults = result?.results.filter(j => j.match_score < 50) ?? [];

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed right-6 top-6 z-50 rounded-lg bg-slate-900 px-4 py-3 text-sm font-medium text-white shadow-lg">
          {toast}
        </div>
      )}

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Ledige Jobs</h1>
        <p className="mt-1 text-sm text-slate-500">
          Søg på tværs af Jobnet, Jobindex og Ofir — matchet mod din karriereprofil
        </p>
      </div>

      {/* Search form */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input
                ref={inputRef}
                className="w-full rounded-lg border border-slate-200 bg-white py-3 pl-10 pr-4 text-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Stillingstitel — fx Facility Manager, Software Developer…"
                value={query}
                onChange={e => setQuery(e.target.value)}
                required
              />
            </div>
            <input
              className="w-48 rounded-lg border border-slate-200 px-4 py-3 text-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Lokation (valgfri)"
              value={location}
              onChange={e => setLocation(e.target.value)}
            />
            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {searching ? (
                <>
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Søger…
                </>
              ) : "Søg jobs"}
            </button>
          </div>

          {/* Source selector */}
          {sources.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-slate-500">Kilder:</span>
              {sources.map(s => (
                <button
                  key={s.name}
                  type="button"
                  onClick={() => toggleSource(s.name)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    selectedSources.includes(s.name)
                      ? (SOURCE_COLORS[s.name] ?? "bg-blue-100 text-blue-700") + " ring-1 ring-current"
                      : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                  }`}
                >
                  {s.display_name}
                </button>
              ))}
            </div>
          )}
        </form>
      </div>

      {/* Search history — shown before results */}
      {!result && history.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Seneste søgninger</h2>
          <div className="space-y-2">
            {history.slice(0, 5).map(h => (
              <button
                key={h.id}
                onClick={() => { setQuery(h.query); if (h.location) setLocation(h.location); }}
                className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left hover:bg-slate-50"
              >
                <div>
                  <p className="text-sm font-medium text-slate-700">{h.query}</p>
                  {h.location && <p className="text-xs text-slate-400">{h.location}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">{h.results_count} resultater</span>
                  <span className="text-xs text-slate-300">·</span>
                  <span className="text-xs text-slate-400">
                    {new Date(h.created_at).toLocaleDateString("da-DK")}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Source stats */}
      {result && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-slate-700">
            {result.total} job{result.total !== 1 ? "s" : ""} fundet
          </span>
          <span className="text-slate-300">|</span>
          {Object.entries(result.source_stats).map(([src, count]) => (
            <span key={src} className={`rounded-full px-2.5 py-1 text-xs font-medium ${SOURCE_COLORS[src] ?? "bg-slate-100 text-slate-600"}`}>
              {src}: {count}
            </span>
          ))}
        </div>
      )}

      {/* Results */}
      {result && result.results.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-16 text-center">
          <p className="text-3xl">🔍</p>
          <p className="mt-3 font-semibold text-slate-700">Ingen jobs fundet</p>
          <p className="mt-1 text-sm text-slate-400">
            Prøv en anden stillingstitel eller søg uden lokationsfilter
          </p>
        </div>
      )}

      {/* High match results */}
      {topResults.length > 0 && (
        <div className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-green-500 text-xs text-white">✓</span>
            Godt match ({topResults.length})
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {topResults.map((job, i) => (
              <JobCard
                key={`top-${i}`}
                job={job}
                onSave={handleSave}
                onGenerateApplication={() => {}}
                savedIds={savedIds}
              />
            ))}
          </div>
        </div>
      )}

      {/* Other results */}
      {otherResults.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-500">
            Andre resultater ({otherResults.length})
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {otherResults.map((job, i) => (
              <JobCard
                key={`other-${i}`}
                job={job}
                onSave={handleSave}
                onGenerateApplication={() => {}}
                savedIds={savedIds}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty state — no search yet */}
      {!result && !searching && history.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-20 text-center">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 text-slate-300">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <p className="text-lg font-semibold text-slate-600">Søg efter ledige stillinger</p>
          <p className="mt-2 max-w-xs text-sm text-slate-400">
            Skriv en stillingstitel og CareerOS søger på Jobnet, Jobindex og Ofir
            — og matcher resultaterne mod din karriereprofil.
          </p>
        </div>
      )}
    </div>
  );
}
