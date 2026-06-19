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
  full_description: string | null;
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
    profile: number;
    preferences: number;
    certifications: number;
  };
  matched_skills: string[];
  missing_requirements: string[];
  text_chars_used: number;
  ai_summary?: string;
}

interface SearchResult {
  search_id: string | null;
  query: string;
  location: string | null;
  total: number;
  scraped_count: number;
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

const BREAKDOWN_LABELS: Record<string, string> = {
  skills: "Kompetencer",
  experience: "Erfaring",
  profile: "Profil",
  preferences: "Præferencer",
  certifications: "Certifikater",
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
      {pct}%
    </span>
  );
}

// ── Job Card ──────────────────────────────────────────────────────────────────

function JobCard({
  job,
  onSave,
  savedIds,
}: {
  job: DiscoveredJob;
  onSave: (job: DiscoveredJob) => void;
  savedIds: Set<string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const isSaved = savedIds.has(job.external_id ?? `${job.title}|${job.company}`);

  const displayText = job.full_description || job.description || null;
  const isScraped = !!job.full_description;

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
              {isScraped && (
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-600 ring-1 ring-emerald-200">
                  fuld tekst
                </span>
              )}
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
          <div className="shrink-0 text-right">
            <MatchBadge score={job.match_score} />
            {job.text_chars_used > 0 && (
              <p className="mt-1 text-xs text-slate-300">{(job.text_chars_used / 1000).toFixed(1)}k tegn</p>
            )}
          </div>
        </div>

        {/* ── Match forklaring ── */}
        {(job.matched_skills.length > 0 || job.missing_requirements.length > 0) && (
          <div className="mt-3 space-y-1.5">
            {/* Matches — grønne pills */}
            {job.matched_skills.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {job.matched_skills.map(s => (
                  <span key={s} className="rounded bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-200">
                    ✓ {s}
                  </span>
                ))}
              </div>
            )}
            {/* Mangler — røde pills */}
            {job.missing_requirements.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {job.missing_requirements.map(r => (
                  <span key={r} className="rounded bg-red-50 px-2 py-0.5 text-xs font-medium text-red-600 ring-1 ring-red-200">
                    − {r}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Match breakdown — 5 søjler */}
        {job.match_score > 0 && (
          <div className="mt-3 grid grid-cols-5 gap-1">
            {Object.entries(job.match_breakdown).map(([key, val]) => (
              <div key={key}>
                <div className="mb-1 text-xs text-slate-400 truncate">{BREAKDOWN_LABELS[key] ?? key}</div>
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
      </div>

      {/* Udvidbar beskrivelse */}
      {displayText && (
        <div className="border-t border-slate-100 px-5 py-3">
          <button
            onClick={() => setExpanded(v => !v)}
            className="flex w-full items-center justify-between text-xs font-medium text-slate-500 hover:text-slate-700"
          >
            <span>{isScraped ? "Fuldt jobopslag" : "Beskrivelse (teaser)"}</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              className={`transition-transform ${expanded ? "rotate-180" : ""}`}>
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          {expanded && (
            <div className="mt-2 max-h-80 overflow-y-auto rounded-lg bg-slate-50 p-3">
              <p className="whitespace-pre-line text-xs leading-relaxed text-slate-600">
                {displayText.slice(0, 4000)}{displayText.length > 4000 ? "\n\n[Vis resten via jobopslaget →]" : ""}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Krav-pills (fra AI-berigelse) */}
      {job.requirements.length > 0 && !expanded && (
        <div className="border-t border-slate-100 px-5 pb-3 pt-2">
          <div className="flex flex-wrap gap-1">
            {job.requirements.slice(0, 6).map(r => (
              <span key={r} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{r}</span>
            ))}
            {job.requirements.length > 6 && (
              <span className="text-xs text-slate-400">+{job.requirements.length - 6}</span>
            )}
          </div>
        </div>
      )}

      {/* Handlinger */}
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
      apiGet<SearchHistory[]>("/job-discovery/history").then(setHistory).catch(() => {});
    } catch {
      showToast("Søgning fejlede — prøv igen");
    } finally {
      setSearching(false);
    }
  }

  async function handleSave(job: DiscoveredJob) {
    try {
      await apiPost<{ id: string }>("/job-discovery/save", { result: job });
      const key = job.external_id ?? `${job.title}|${job.company}`;
      setSavedIds(prev => new Set([...prev, key]));
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
          Søg på tværs af Jobnet, Jobindex og Ofir — med fuld jobtekst-scraping og AI-matchscore
        </p>
      </div>

      {/* Søgeformular */}
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
                placeholder="Stillingstitel — fx Teamleder, Facility Manager, Indkøbschef…"
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
                  Søger + scraper…
                </>
              ) : "Søg jobs"}
            </button>
          </div>

          {/* Kildevælger */}
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

      {/* Søgehistorik */}
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

      {/* Stats-linje */}
      {result && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-slate-700">
            {result.total} job{result.total !== 1 ? "s" : ""} fundet
          </span>
          {result.scraped_count > 0 && (
            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
              {result.scraped_count} med fuld tekst
            </span>
          )}
          <span className="text-slate-300">|</span>
          {Object.entries(result.source_stats).map(([src, count]) => (
            <span key={src} className={`rounded-full px-2.5 py-1 text-xs font-medium ${SOURCE_COLORS[src] ?? "bg-slate-100 text-slate-600"}`}>
              {src}: {count}
            </span>
          ))}
        </div>
      )}

      {/* Ingen resultater */}
      {result && result.results.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-16 text-center">
          <p className="text-3xl">🔍</p>
          <p className="mt-3 font-semibold text-slate-700">Ingen jobs fundet</p>
          <p className="mt-1 text-sm text-slate-400">
            Prøv en anden stillingstitel eller søg uden lokationsfilter
          </p>
        </div>
      )}

      {/* Godt match (≥50%) */}
      {topResults.length > 0 && (
        <div className="space-y-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-green-500 text-xs text-white">✓</span>
            Godt match — {topResults.length} job{topResults.length !== 1 ? "s" : ""}
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {topResults.map((job, i) => (
              <JobCard key={`top-${i}`} job={job} onSave={handleSave} savedIds={savedIds} />
            ))}
          </div>
        </div>
      )}

      {/* Andre resultater (<50%) */}
      {otherResults.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-500">
            Andre resultater — {otherResults.length} job{otherResults.length !== 1 ? "s" : ""}
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {otherResults.map((job, i) => (
              <JobCard key={`other-${i}`} job={job} onSave={handleSave} savedIds={savedIds} />
            ))}
          </div>
        </div>
      )}

      {/* Empty state — ingen søgning endnu */}
      {!result && !searching && history.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-20 text-center">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 text-slate-300">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <p className="text-lg font-semibold text-slate-600">Søg efter ledige stillinger</p>
          <p className="mt-2 max-w-xs text-sm text-slate-400">
            CareerOS søger på Jobnet, Jobindex og Ofir, scraper fuld jobtekst
            og matcher mod din karriereprofil med forklaret matchscore.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2 text-xs text-slate-400">
            <span className="rounded bg-green-50 px-2 py-0.5 text-green-700 ring-1 ring-green-200">✓ Kompetencer der matcher</span>
            <span className="rounded bg-red-50 px-2 py-0.5 text-red-600 ring-1 ring-red-200">− Manglende krav</span>
          </div>
        </div>
      )}
    </div>
  );
}
