"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface DashboardSummary {
  top_job_matches: JobMatch[];
  active_applications: Application[];
  application_counts: Record<string, number>;
  upcoming_interviews: Interview[];
  recent_jobs: RecentJob[];
  notifications: Notification[];
  unread_notifications: number;
  coach_sessions: CoachSession[];
  saved_jobs_count: number;
  profile: { cv_completeness: number; has_master_cv: boolean };
}

interface JobMatch {
  id: string; title: string; company: string; location?: string;
  match_score: number; is_saved: boolean; created_at: string; url?: string;
}
interface Application {
  id: string; current_status: string; priority: string; deadline?: string;
  jobs?: { title: string; company: string };
}
interface Interview {
  id: string; current_status?: string; deadline?: string | null; notes?: string;
  jobs?: { title: string; company: string };
}
interface RecentJob {
  id: string; title: string; company: string; match_score?: number;
  created_at: string; source?: string;
}
interface Notification {
  id: string; event_type: string; title: string; body: string;
  is_read: boolean; created_at: string;
}
interface CoachSession { id: string; title: string; created_at: string; }
interface AnalyticsSummary {
  applications: {
    total: number; submitted: number; interviewing: number;
    interview_rate_pct: number; offer_rate_pct: number;
  };
  jobs: { total: number; avg_match_score: number; top_match_score: number };
  cv: { completeness_pct: number; has_master_cv: boolean };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

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
  submitted: "bg-indigo-100 text-indigo-700",
  screening: "bg-violet-100 text-violet-700",
  interviewing: "bg-amber-100 text-amber-700",
  offer: "bg-emerald-100 text-emerald-700",
  hired: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-600",
};

const STATUS_LABELS: Record<string, string> = {
  // Pipeline 2.0
  fundet: "Fundet", gemt: "Gemt",
  cv_genereret: "CV genereret", ansoegning_genereret: "Ansøgning genereret",
  ansoegt: "Ansøgt", samtale_1: "1. samtale", samtale_2: "2. samtale",
  case_stadie: "Case", tilbud: "Tilbud", ansat: "Ansat", afslag: "Afslag",
  // Pipeline 1.0
  draft: "Kladde", preparing: "Forbereder", ready: "Klar",
  submitted: "Sendt", screening: "Screening", interviewing: "Interview",
  offer: "Tilbud", hired: "Ansat", rejected: "Afvist", withdrawn: "Trukket tilbage",
};

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? "text-green-600 bg-green-50" :
    score >= 60 ? "text-amber-600 bg-amber-50" : "text-slate-500 bg-slate-50";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold ${color}`}>
      {score}%
    </span>
  );
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diff === 0) return "I dag";
  if (diff === 1) return "I går";
  if (diff < 7) return `${diff} dage siden`;
  return d.toLocaleDateString("da-DK", { day: "numeric", month: "short" });
}

function fmtDeadline(iso: string | null | undefined) {
  if (!iso) return { label: "Ingen dato", cls: "text-slate-400" };
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((d.getTime() - now.getTime()) / 86400000);
  if (diff < 0) return { label: "Overskredet", cls: "text-red-600" };
  if (diff === 0) return { label: "I dag!", cls: "text-red-600 font-bold" };
  if (diff === 1) return { label: "I morgen", cls: "text-amber-600" };
  if (diff <= 7) return { label: `Om ${diff} dage`, cls: "text-amber-600" };
  return {
    label: d.toLocaleDateString("da-DK", { day: "numeric", month: "short" }),
    cls: "text-slate-500",
  };
}

// ── Widgets ───────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color }: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
      <p className={`mt-1.5 text-3xl font-bold ${color ?? "text-slate-900"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

function SectionHeader({ title, href, linkLabel = "Se alle" }: {
  title: string; href?: string; linkLabel?: string;
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-base font-semibold text-slate-800">{title}</h2>
      {href && (
        <Link href={href} className="text-xs text-blue-600 hover:text-blue-800">
          {linkLabel} →
        </Link>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet<DashboardSummary>("/dashboard/summary"),
      apiGet<AnalyticsSummary>("/analytics/summary"),
    ])
      .then(([s, a]) => { setSummary(s); setAnalytics(a); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function markAllRead() {
    await apiPost("/notifications/read-all", {});
    if (summary) {
      setSummary({
        ...summary,
        unread_notifications: 0,
        notifications: summary.notifications.map(n => ({ ...n, is_read: true })),
      });
    }
  }

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

  const s = summary;
  const a = analytics;

  const isNewUser = a
    ? a.applications.total === 0 && a.jobs.total === 0 && !a.cv.has_master_cv
    : false;

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">Dit karriere-overblik i realtid</p>
      </div>

      {/* ── Onboarding guide (new users only) ── */}
      {isNewUser && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-6">
          <h2 className="text-base font-semibold text-blue-900 mb-1">Kom i gang på 3 trin</h2>
          <p className="text-sm text-blue-700 mb-4">
            Velkommen til CareerOS! Her er hvad du kan gøre først:
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              {
                step: "1",
                title: "Generer dit Master CV",
                desc: "Upload dit eksisterende CV og lad AI optimere det.",
                href: "/cv",
                cta: "Gå til CV Studio →",
              },
              {
                step: "2",
                title: "Find relevante jobs",
                desc: "Søg job og se AI-matchscore baseret på din profil.",
                href: "/jobs",
                cta: "Søg jobs →",
              },
              {
                step: "3",
                title: "Analyser din kontrakt",
                desc: "Upload ansættelseskontrakt og få AI til at finde vigtige fakta.",
                href: "/experience",
                cta: "Gå til Arbejdsliv →",
              },
            ].map(({ step, title, desc, href, cta }) => (
              <Link key={step} href={href} className="block rounded-lg bg-white border border-blue-100 p-4 hover:border-blue-300 transition-colors">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-white text-xs font-bold mb-2">
                  {step}
                </span>
                <p className="text-sm font-medium text-slate-800">{title}</p>
                <p className="text-xs text-slate-500 mt-0.5 mb-2">{desc}</p>
                <span className="text-xs text-blue-600 font-medium">{cta}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* ── Stat row ── */}
      {a && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            label="Ansøgninger i alt"
            value={a.applications.total}
            sub={`${a.applications.submitted} sendt`}
            color="text-blue-700"
          />
          <StatCard
            label="Interview-rate"
            value={`${a.applications.interview_rate_pct}%`}
            sub={`${a.applications.interviewing} aktive`}
            color={a.applications.interview_rate_pct >= 30 ? "text-green-700" : "text-slate-700"}
          />
          <StatCard
            label="Gns. matchscore"
            value={`${a.jobs.avg_match_score}%`}
            sub={`Bedste: ${a.jobs.top_match_score}%`}
            color="text-indigo-700"
          />
          <StatCard
            label="Profil fuldstændighed"
            value={`${a.cv.completeness_pct}%`}
            sub={a.cv.has_master_cv ? "Master CV klar" : "Generer Master CV"}
            color={a.cv.completeness_pct >= 70 ? "text-green-700" : "text-amber-700"}
          />
        </div>
      )}

      {/* ── Pipeline funnel ── */}
      {s && (
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          {[
            { label: "Gemte jobs",   key: null,          count: s.saved_jobs_count,                   color: "text-slate-700",   href: "/jobs" },
            { label: "Ansøgninger",  key: "ansoegt",     count: s.application_counts["ansoegt"] ?? 0, color: "text-violet-700",  href: "/applications" },
            { label: "1. samtale",   key: "samtale_1",   count: s.application_counts["samtale_1"] ?? 0, color: "text-purple-700", href: "/applications" },
            { label: "2. samtale",   key: "samtale_2",   count: s.application_counts["samtale_2"] ?? 0, color: "text-fuchsia-700", href: "/applications" },
            { label: "Tilbud",       key: "tilbud",      count: s.application_counts["tilbud"] ?? 0,  color: "text-green-700",   href: "/applications" },
            { label: "Afslag",       key: "afslag",      count: s.application_counts["afslag"] ?? 0,  color: "text-red-600",     href: "/applications" },
          ].map(({ label, count, color, href }) => (
            <Link
              key={label}
              href={href}
              className="rounded-xl border border-slate-200 bg-white p-4 text-center hover:border-blue-200 hover:shadow-sm transition-all"
            >
              <p className={`text-2xl font-bold ${color}`}>{count}</p>
              <p className="mt-0.5 text-xs text-slate-500">{label}</p>
            </Link>
          ))}
        </div>
      )}

      {/* ── CV alert if no master CV ── */}
      {s && !s.profile.has_master_cv && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex items-center justify-between gap-4">
          <div>
            <p className="font-medium text-amber-800">Du har ikke et Master CV endnu</p>
            <p className="text-sm text-amber-600 mt-0.5">Upload dit CV eller generer Master CV for at aktivere AI-funktioner fuldt ud.</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Link href="/cv" className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100">
              Upload CV
            </Link>
            <Link href="/cv/master" className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">
              Generér
            </Link>
          </div>
        </div>
      )}

      {/* ── Main grid ── */}
      <div className="grid gap-6 lg:grid-cols-3">

        {/* Left + center (2/3) */}
        <div className="space-y-6 lg:col-span-2">

          {/* Top job matches */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <SectionHeader title="Top Job Matches" href="/jobs" linkLabel="Alle jobs" />
            {(!s?.top_job_matches?.length) ? (
              <div className="py-8 text-center">
                <p className="text-sm text-slate-400">Ingen job med matchscore endnu</p>
                <Link href="/jobs/discovery" className="mt-3 inline-block text-sm text-blue-600 hover:text-blue-800">
                  Start Job Discovery →
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {s.top_job_matches.map((job) => (
                  <Link
                    key={job.id}
                    href={`/jobs`}
                    className="flex items-center justify-between rounded-lg p-3 hover:bg-slate-50 transition-colors group"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-slate-800 group-hover:text-blue-700 truncate">{job.title}</p>
                      <p className="text-sm text-slate-500 truncate">{job.company}{job.location ? ` · ${job.location}` : ""}</p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <ScoreBadge score={job.match_score} />
                      <span className="text-xs text-slate-400">{fmtDate(job.created_at)}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Active applications pipeline */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <SectionHeader title="Ansøgninger i pipeline" href="/applications" />

            {/* Status summary pills */}
            {s?.application_counts && Object.keys(s.application_counts).length > 0 && (
              <div className="mb-4 flex flex-wrap gap-1.5">
                {Object.entries(s.application_counts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([status, count]) => (
                    <span
                      key={status}
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[status] ?? "bg-slate-100 text-slate-600"}`}
                    >
                      {count} {STATUS_LABELS[status] ?? status}
                    </span>
                  ))}
              </div>
            )}

            {(!s?.active_applications?.length) ? (
              <div className="py-6 text-center">
                <p className="text-sm text-slate-400">Ingen aktive ansøgninger</p>
                <Link href="/jobs" className="mt-2 inline-block text-sm text-blue-600 hover:text-blue-800">
                  Find og gem et job →
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {s.active_applications.slice(0, 6).map((app) => (
                  <Link
                    key={app.id}
                    href="/applications"
                    className="flex items-center justify-between rounded-lg p-3 hover:bg-slate-50 transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-slate-800 truncate">
                        {app.jobs?.title ?? "Ukendt stilling"}
                      </p>
                      <p className="text-xs text-slate-500">{app.jobs?.company}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[app.current_status] ?? "bg-slate-100 text-slate-600"}`}>
                        {STATUS_LABELS[app.current_status] ?? app.current_status}
                      </span>
                      {app.deadline && (() => {
                        const d = fmtDeadline(app.deadline);
                        return <span className={`text-xs ${d.cls}`}>{d.label}</span>;
                      })()}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Kommende samtaler */}
          {(s?.upcoming_interviews?.length ?? 0) > 0 && (
            <div className="rounded-xl border border-purple-100 bg-purple-50 p-5">
              <SectionHeader title="Kommende samtaler" href="/applications" />
              <div className="space-y-3">
                {s!.upcoming_interviews.map((iv) => {
                  const d = fmtDeadline(iv.deadline);
                  const statusLabel = STATUS_LABELS[iv.current_status ?? ""] ?? iv.current_status ?? "";
                  const statusColor = STATUS_COLORS[iv.current_status ?? ""] ?? "bg-slate-100 text-slate-600";
                  return (
                    <div key={iv.id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-slate-800 truncate">{iv.jobs?.title}</p>
                        <p className="text-xs text-slate-500">{iv.jobs?.company}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {statusLabel && (
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor}`}>
                            {statusLabel}
                          </span>
                        )}
                        <span className={`text-xs font-semibold ${d.cls}`}>{d.label}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right column (1/3) */}
        <div className="space-y-6">

          {/* Notifications */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-slate-800">Notifikationer</h2>
                {(s?.unread_notifications ?? 0) > 0 && (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white">
                    {s!.unread_notifications}
                  </span>
                )}
              </div>
              {(s?.unread_notifications ?? 0) > 0 && (
                <button onClick={markAllRead} className="text-xs text-blue-600 hover:text-blue-800">
                  Marker alle læst
                </button>
              )}
            </div>

            {(!s?.notifications?.length) ? (
              <p className="py-4 text-center text-xs text-slate-400">Ingen notifikationer</p>
            ) : (
              <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
                {s.notifications.slice(0, 8).map((n) => (
                  <div
                    key={n.id}
                    className={`rounded-lg p-2.5 ${n.is_read ? "bg-slate-50" : "bg-blue-50 border border-blue-100"}`}
                  >
                    <p className={`text-xs font-semibold ${n.is_read ? "text-slate-600" : "text-blue-800"}`}>
                      {n.title}
                    </p>
                    {n.body && <p className="mt-0.5 text-xs text-slate-500 line-clamp-2">{n.body}</p>}
                    <p className="mt-0.5 text-[10px] text-slate-400">{fmtDate(n.created_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent discoveries */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <SectionHeader title="Seneste job" href="/jobs/discovery" linkLabel="Discovery" />
            {(!s?.recent_jobs?.length) ? (
              <div className="py-4 text-center">
                <p className="text-xs text-slate-400">Ingen jobs endnu</p>
                <Link href="/jobs/discovery" className="mt-2 inline-block text-xs text-blue-600">
                  Start discovery →
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {s.recent_jobs.map((j) => (
                  <div key={j.id} className="flex items-center justify-between py-1">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-700 truncate">{j.title}</p>
                      <p className="text-xs text-slate-400 truncate">{j.company}</p>
                    </div>
                    {j.match_score != null && <ScoreBadge score={j.match_score} />}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Career Coach quick access */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <SectionHeader title="Career Coach" href="/career-coach" />
            {(s?.coach_sessions?.length ?? 0) > 0 ? (
              <div className="space-y-2 mb-3">
                {s!.coach_sessions.slice(0, 3).map((session) => (
                  <div key={session.id} className="rounded-lg bg-slate-50 p-2.5">
                    <p className="text-xs font-medium text-slate-700 truncate">{session.title}</p>
                    <p className="text-[10px] text-slate-400">{fmtDate(session.created_at)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mb-3 text-xs text-slate-400">Start en karriere-coaching session</p>
            )}
            <Link
              href="/career-coach"
              className="block w-full rounded-lg bg-blue-600 py-2 text-center text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Åbn Career Coach
            </Link>
          </div>

          {/* Quick actions */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-base font-semibold text-slate-800">Hurtige handlinger</h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "Upload CV", href: "/cv", emoji: "📄" },
                { label: "Find jobs", href: "/jobs/discovery", emoji: "🔍" },
                { label: "Master CV", href: "/cv/master", emoji: "✨" },
                { label: "Ansøgning", href: "/applications", emoji: "📝" },
              ].map((a) => (
                <Link
                  key={a.href}
                  href={a.href}
                  className="flex flex-col items-center gap-1 rounded-lg border border-slate-100 p-3 text-center hover:border-blue-200 hover:bg-blue-50 transition-colors"
                >
                  <span className="text-lg">{a.emoji}</span>
                  <span className="text-xs font-medium text-slate-600">{a.label}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
