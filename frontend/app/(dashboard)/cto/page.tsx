"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

type HealthComponent = {
  score: number;
  weight: number;
  label: string;
  detail: string;
};

type HealthData = {
  score: number;
  grade: string;
  trend: string;
  components: Record<string, HealthComponent>;
};

type AnalyticsData = {
  period_days: number;
  documents: { uploaded: number; analyzed: number; failed: number; analysis_success_rate_pct: number; avg_analysis_time_ms: number | null };
  facts: { total: number; verified: number; verification_rate_pct: number };
  recommendations: { total: number; resolved_or_dismissed: number; resolution_rate_pct: number; resolved_this_period: number; dismissed_this_period: number };
  chat: { completed: number; avg_chat_time_ms: number | null };
  ai: { cost_usd_period: number; cost_usd_7d: number };
  users: { active_in_period: number; time_to_first_value_days: number | null; retention: { d7_pct: number | null; active_prev_week: number; active_this_week: number } };
  revenue: { subscriptions_total: number; subscriptions_paid: number; subscriptions_free: number; mrr_dkk: number; arr_dkk: number; conversion_rate_pct: number };
};

type OperationalData = {
  top_errors: { event_type: string; count: number; label: string }[];
  doc_type_health: { doc_type: string; uploaded: number; failed: number; failure_rate_pct: number; alert: boolean }[];
  slowest_analyses: { doc_type: string | null; facts: number | null; duration_ms: number; occurred_at: string }[];
  budget_alerts: { user_id: string; cost_usd_7d: number }[];
  daily_active_users_7d: { date: string; active_users: number }[];
};

type Priority = { title: string; evidence: string; impact: string; effort?: string; suggestion?: string };

type PriorityData = {
  generated_at: string;
  top_fixes: Priority[];
  top_ux_improvements: Priority[];
  top_opportunities: Priority[];
};

type ReportData = {
  period: string;
  generated_at: string;
  summary: string;
  product_health: { score: number; grade: string; trend: string };
  highlights: string[];
  concerns: string[];
  analytics_snapshot: { docs_analyzed: number; analysis_success_pct: number; facts_verified_pct: number; active_users: number; mrr_dkk: number; ai_cost_usd: number };
  top_operational_issues: { event_type: string; count: number; label: string }[];
  action_items: { priority: number; title: string; evidence: string; impact: string; suggestion?: string }[];
};

// ── Helpers ──────────────────────────────────────────────────────────────────

const GRADE_COLOR: Record<string, string> = {
  A: "text-green-600",
  B: "text-blue-600",
  C: "text-yellow-600",
  D: "text-red-600",
};

const IMPACT_COLOR: Record<string, string> = {
  high:   "bg-red-100 text-red-800",
  medium: "bg-yellow-100 text-yellow-800",
  low:    "bg-gray-100 text-gray-700",
};

function ScoreRing({ score, grade }: { score: number; grade: string }) {
  const pct = score / 100;
  const r = 40;
  const circ = 2 * Math.PI * r;
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#e5e7eb" strokeWidth="10" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={score >= 80 ? "#16a34a" : score >= 65 ? "#2563eb" : score >= 50 ? "#d97706" : "#dc2626"}
          strokeWidth="10"
          strokeDasharray={`${pct * circ} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
        <text x="50" y="46" textAnchor="middle" dominantBaseline="middle" fontSize="18" fontWeight="700" fill="#111">
          {score}
        </text>
        <text x="50" y="63" textAnchor="middle" dominantBaseline="middle" fontSize="11" fill="#6b7280">
          /100
        </text>
      </svg>
      <span className={`text-2xl font-bold ${GRADE_COLOR[grade] ?? "text-gray-600"}`}>Grade {grade}</span>
    </div>
  );
}

function KpiCard({ label, value, sub, alert }: { label: string; value: string | number; sub?: string; alert?: boolean }) {
  return (
    <div className={`rounded-xl border p-4 ${alert ? "border-red-300 bg-red-50" : "border-gray-200 bg-white"}`}>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${alert ? "text-red-700" : "text-gray-900"}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function ImpactBadge({ impact }: { impact: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${IMPACT_COLOR[impact] ?? "bg-gray-100 text-gray-700"}`}>
      {impact === "high" ? "Høj" : impact === "medium" ? "Middel" : "Lav"}
    </span>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
      Henter data...
    </div>
  );
}

function ErrorState({ msg }: { msg: string }) {
  return (
    <div className="flex items-center justify-center h-64 text-red-600 text-sm">
      {msg}
    </div>
  );
}

// ── Tab components ────────────────────────────────────────────────────────────

function OverviewTab({ health, analytics }: { health: HealthData | null; analytics: AnalyticsData | null }) {
  if (!health || !analytics) return <LoadingState />;
  return (
    <div className="space-y-6">
      {/* Health score + components */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-gray-500 mb-4">Platform Sundhedsscore</h2>
        <div className="flex gap-10 items-start flex-wrap">
          <ScoreRing score={health.score} grade={health.grade} />
          <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-3 min-w-0">
            {Object.values(health.components).map((c) => (
              <div key={c.label} className="text-sm">
                <div className="flex justify-between mb-1">
                  <span className="text-gray-700 font-medium">{c.label}</span>
                  <span className="text-gray-500">{c.score}/100</span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${c.score}%`,
                      background: c.score >= 80 ? "#16a34a" : c.score >= 60 ? "#2563eb" : c.score >= 40 ? "#d97706" : "#dc2626",
                    }}
                  />
                </div>
                <p className="text-xs text-gray-400 mt-0.5">{c.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* KPI overview */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard label="Dokumenter analyseret" value={analytics.documents.analyzed} sub={`${analytics.documents.analysis_success_rate_pct}% succesrate`} alert={analytics.documents.analysis_success_rate_pct < 80} />
        <KpiCard label="Fakta verificeret" value={`${analytics.facts.verification_rate_pct}%`} sub={`${analytics.facts.verified} / ${analytics.facts.total}`} alert={analytics.facts.verification_rate_pct < 20 && analytics.facts.total >= 5} />
        <KpiCard label="Aktive brugere" value={analytics.users.active_in_period} sub={`${analytics.period_days}d periode`} />
        <KpiCard label="MRR" value={`${analytics.revenue.mrr_dkk} kr`} sub={`ARR: ${analytics.revenue.arr_dkk} kr`} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard label="AI-forbrug (periode)" value={`$${analytics.ai.cost_usd_period.toFixed(4)}`} sub={`Seneste 7d: $${analytics.ai.cost_usd_7d.toFixed(4)}`} />
        <KpiCard label="Chat-samtaler" value={analytics.chat.completed} sub={analytics.chat.avg_chat_time_ms ? `Gns. ${Math.round(analytics.chat.avg_chat_time_ms / 1000)}s` : undefined} />
        <KpiCard label="Anbefalinger løst" value={`${analytics.recommendations.resolution_rate_pct}%`} sub={`${analytics.recommendations.resolved_or_dismissed} / ${analytics.recommendations.total}`} alert={analytics.recommendations.resolution_rate_pct < 30 && analytics.recommendations.total >= 3} />
        <KpiCard label="Konvertering" value={`${analytics.revenue.conversion_rate_pct}%`} sub={`${analytics.revenue.subscriptions_paid} betaler / ${analytics.revenue.subscriptions_total} total`} />
      </div>
    </div>
  );
}

function AnalyticsTab({ analytics, days, setDays }: { analytics: AnalyticsData | null; days: number; setDays: (d: number) => void }) {
  if (!analytics) return <LoadingState />;
  const ret = analytics.users.retention;
  return (
    <div className="space-y-6">
      <div className="flex gap-2 text-sm">
        {[7, 30, 90].map((d) => (
          <button key={d} onClick={() => setDays(d)} className={`px-3 py-1 rounded-full border transition-colors ${days === d ? "bg-black text-white border-black" : "text-gray-600 border-gray-200 hover:border-gray-400"}`}>
            {d}d
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Documents */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Dokumenter</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100">
              <tr><td className="py-1.5 text-gray-500">Uploadet</td><td className="text-right font-medium">{analytics.documents.uploaded}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Analyseret</td><td className="text-right font-medium text-green-700">{analytics.documents.analyzed}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Fejlet</td><td className="text-right font-medium text-red-700">{analytics.documents.failed}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Succesrate</td><td className="text-right font-medium">{analytics.documents.analysis_success_rate_pct}%</td></tr>
              {analytics.documents.avg_analysis_time_ms && (
                <tr><td className="py-1.5 text-gray-500">Gns. analysetid</td><td className="text-right font-medium">{(analytics.documents.avg_analysis_time_ms / 1000).toFixed(1)}s</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Fakta */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Fakta & Trust</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100">
              <tr><td className="py-1.5 text-gray-500">Total fakta</td><td className="text-right font-medium">{analytics.facts.total}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Verificeret af bruger</td><td className="text-right font-medium text-green-700">{analytics.facts.verified}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Verifikationsrate</td><td className="text-right font-medium">{analytics.facts.verification_rate_pct}%</td></tr>
            </tbody>
          </table>
        </div>

        {/* Revenue */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Omsætning</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100">
              <tr><td className="py-1.5 text-gray-500">MRR</td><td className="text-right font-medium">{analytics.revenue.mrr_dkk} DKK</td></tr>
              <tr><td className="py-1.5 text-gray-500">ARR</td><td className="text-right font-medium">{analytics.revenue.arr_dkk} DKK</td></tr>
              <tr><td className="py-1.5 text-gray-500">Betalende brugere</td><td className="text-right font-medium">{analytics.revenue.subscriptions_paid}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Gratis brugere</td><td className="text-right font-medium">{analytics.revenue.subscriptions_free}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Konverteringsrate</td><td className="text-right font-medium">{analytics.revenue.conversion_rate_pct}%</td></tr>
            </tbody>
          </table>
        </div>

        {/* Retention */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Brugeraktivitet & Retention</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100">
              <tr><td className="py-1.5 text-gray-500">Aktive (periode)</td><td className="text-right font-medium">{analytics.users.active_in_period}</td></tr>
              <tr><td className="py-1.5 text-gray-500">D7 Retention</td><td className="text-right font-medium">{ret.d7_pct !== null ? `${ret.d7_pct}%` : "—"}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Aktive forrige uge</td><td className="text-right font-medium">{ret.active_prev_week}</td></tr>
              <tr><td className="py-1.5 text-gray-500">Aktive denne uge</td><td className="text-right font-medium">{ret.active_this_week}</td></tr>
              {analytics.users.time_to_first_value_days !== null && (
                <tr><td className="py-1.5 text-gray-500">Time To First Value</td><td className="text-right font-medium">{analytics.users.time_to_first_value_days} dage (median)</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function OperationalTab({ data }: { data: OperationalData | null }) {
  if (!data) return <LoadingState />;
  return (
    <div className="space-y-6">
      {/* Budget alerts */}
      {data.budget_alerts.length > 0 && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-4">
          <h3 className="text-sm font-semibold text-red-800 mb-2">Budgetalerter</h3>
          {data.budget_alerts.map((a, i) => (
            <p key={i} className="text-sm text-red-700">{a.user_id.slice(0, 8)}… — ${a.cost_usd_7d.toFixed(4)} seneste 7d</p>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top errors */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Hyppigste fejl (30d)</h3>
          {data.top_errors.length === 0 ? (
            <p className="text-sm text-gray-400">Ingen fejl registreret</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {data.top_errors.map((e, i) => (
                <div key={i} className="flex justify-between py-2 text-sm">
                  <span className="text-gray-700">{e.label}</span>
                  <span className={`font-medium ${e.count >= 5 ? "text-red-700" : e.count >= 2 ? "text-yellow-700" : "text-gray-600"}`}>{e.count}×</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Doc type health */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Dokumenttype sundhed</h3>
          {data.doc_type_health.length === 0 ? (
            <p className="text-sm text-gray-400">Ingen uploads registreret</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {data.doc_type_health.map((d, i) => (
                <div key={i} className={`py-2 text-sm ${d.alert ? "text-red-700" : "text-gray-700"}`}>
                  <div className="flex justify-between">
                    <span className="font-medium">{d.doc_type}</span>
                    <span>{d.failure_rate_pct}% fejlrate {d.alert && "⚠️"}</span>
                  </div>
                  <p className="text-xs text-gray-400">{d.uploaded} uploads, {d.failed} fejl</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Slowest analyses */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Langsomste analyser</h3>
          {data.slowest_analyses.length === 0 ? (
            <p className="text-sm text-gray-400">Ingen timing-data endnu</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {data.slowest_analyses.slice(0, 5).map((a, i) => (
                <div key={i} className="flex justify-between py-2 text-sm">
                  <span className="text-gray-700">{a.doc_type ?? "ukendt"}</span>
                  <span className="font-medium">{(a.duration_ms / 1000).toFixed(1)}s</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Daily active users */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Daglige aktive brugere (7d)</h3>
          {data.daily_active_users_7d.length === 0 ? (
            <p className="text-sm text-gray-400">Ingen aktivitet registreret</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {data.daily_active_users_7d.map((d, i) => (
                <div key={i} className="flex justify-between py-2 text-sm">
                  <span className="text-gray-500">{d.date}</span>
                  <span className="font-medium">{d.active_users} brugere</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PriorityTab({ data }: { data: PriorityData | null }) {
  if (!data) return <LoadingState />;

  const Section = ({ title, items, emptyText }: { title: string; items: Priority[]; emptyText: string }) => (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-gray-400">{emptyText}</p>
      ) : (
        <div className="space-y-3">
          {items.map((p, i) => (
            <div key={i} className="border border-gray-100 rounded-lg p-3">
              <div className="flex gap-2 items-start mb-1">
                <span className="text-xs font-bold text-gray-400 mt-0.5 w-5 shrink-0">#{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex gap-2 items-center flex-wrap mb-1">
                    <span className="text-sm font-semibold text-gray-900">{p.title}</span>
                    <ImpactBadge impact={p.impact} />
                  </div>
                  <p className="text-xs text-gray-500">{p.evidence}</p>
                  {p.suggestion && <p className="text-xs text-blue-600 mt-1">→ {p.suggestion}</p>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <Section title="Top Fejl at Løse" items={data.top_fixes} emptyText="Ingen kritiske fejl identificeret" />
      <Section title="Top UX-Forbedringer" items={data.top_ux_improvements} emptyText="Ingen UX-problemer identificeret" />
      <Section title="Top Muligheder" items={data.top_opportunities} emptyText="Ingen muligheder identificeret endnu" />
    </div>
  );
}

function ReportTab({ data }: { data: ReportData | null }) {
  if (!data) return <LoadingState />;
  const snap = data.analytics_snapshot;
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <div className="flex justify-between items-start mb-2">
          <h2 className="text-lg font-bold text-gray-900">Ugentlig Eksekutivrapport</h2>
          <span className={`text-2xl font-bold ${GRADE_COLOR[data.product_health.grade] ?? "text-gray-600"}`}>
            Grade {data.product_health.grade} ({data.product_health.score}/100)
          </span>
        </div>
        <p className="text-xs text-gray-400 mb-4">{data.period}</p>
        <p className="text-sm text-gray-700 leading-relaxed">{data.summary}</p>
      </div>

      {/* Snapshot */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <KpiCard label="Dokumenter analyseret" value={snap.docs_analyzed} sub={`${snap.analysis_success_pct}% succesrate`} />
        <KpiCard label="Fakta verificeret" value={`${snap.facts_verified_pct}%`} alert={snap.facts_verified_pct < 20} />
        <KpiCard label="Aktive brugere" value={snap.active_users} />
        <KpiCard label="MRR" value={`${snap.mrr_dkk} kr`} />
        <KpiCard label="AI-forbrug" value={`$${snap.ai_cost_usd.toFixed(4)}`} />
      </div>

      {/* Highlights & Concerns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.highlights.length > 0 && (
          <div className="rounded-xl border border-green-200 bg-green-50 p-4">
            <h3 className="text-sm font-semibold text-green-800 mb-2">Highlights</h3>
            <ul className="space-y-1">
              {data.highlights.map((h, i) => <li key={i} className="text-sm text-green-700">✓ {h}</li>)}
            </ul>
          </div>
        )}
        {data.concerns.length > 0 && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <h3 className="text-sm font-semibold text-red-800 mb-2">Bekymringer</h3>
            <ul className="space-y-1">
              {data.concerns.map((c, i) => <li key={i} className="text-sm text-red-700">⚠ {c}</li>)}
            </ul>
          </div>
        )}
      </div>

      {/* Action Items */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Anbefalede handlinger</h3>
        {data.action_items.length === 0 ? (
          <p className="text-sm text-gray-400">Ingen prioriterede handlinger</p>
        ) : (
          <div className="space-y-3">
            {data.action_items.map((a) => (
              <div key={a.priority} className="flex gap-3 items-start">
                <span className="w-6 h-6 rounded-full bg-gray-900 text-white text-xs flex items-center justify-center shrink-0 mt-0.5">{a.priority}</span>
                <div>
                  <div className="flex gap-2 items-center">
                    <span className="text-sm font-semibold text-gray-900">{a.title}</span>
                    <ImpactBadge impact={a.impact} />
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{a.evidence}</p>
                  {a.suggestion && <p className="text-xs text-blue-600 mt-0.5">→ {a.suggestion}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const TABS = [
  { key: "overview",     label: "Overblik" },
  { key: "analytics",   label: "Analyse" },
  { key: "operational", label: "Drift" },
  { key: "priorities",  label: "Prioritering" },
  { key: "report",      label: "Rapport" },
] as const;

type TabKey = typeof TABS[number]["key"];

export default function CTODashboardPage() {
  const [tab, setTab] = useState<TabKey>("overview");
  const [analyticsDays, setAnalyticsDays] = useState(30);
  const [forbidden, setForbidden] = useState(false);

  const [health,      setHealth]      = useState<HealthData | null>(null);
  const [analytics,   setAnalytics]   = useState<AnalyticsData | null>(null);
  const [operational, setOperational] = useState<OperationalData | null>(null);
  const [priorities,  setPriorities]  = useState<PriorityData | null>(null);
  const [report,      setReport]      = useState<ReportData | null>(null);

  const [errors, setErrors] = useState<Record<string, string>>({});

  const fetchJSON = async <T,>(path: string, setter: (d: T) => void, key: string) => {
    try {
      const data = await apiGet<T>(path);
      setter(data);
    } catch (e: unknown) {
      const status = (e as { status?: number }).status;
      if (status === 403) {
        setForbidden(true);
        return;
      }
      setErrors((prev) => ({ ...prev, [key]: "Fejl ved hentning" }));
    }
  };

  useEffect(() => {
    fetchJSON<HealthData>("/intelligence/health", setHealth, "health");
    fetchJSON<AnalyticsData>(`/intelligence/analytics?days=${analyticsDays}`, setAnalytics, "analytics");
    fetchJSON<OperationalData>("/intelligence/operational", setOperational, "operational");
    fetchJSON<PriorityData>("/intelligence/priorities", setPriorities, "priorities");
    fetchJSON<ReportData>("/intelligence/report", setReport, "report");
  }, [analyticsDays]);

  if (forbidden) {
    return (
      <div className="p-8 max-w-lg mx-auto mt-20 text-center">
        <p className="text-4xl mb-3">🔒</p>
        <h1 className="text-xl font-bold text-gray-900 mb-2">Admin-adgang krævet</h1>
        <p className="text-gray-500 text-sm">Kun platformens administrator kan tilgå dette dashboard.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Platform Intelligence</h1>
        <p className="text-sm text-gray-500 mt-1">Internt CTO-dashboard — ikke synligt for brugere</p>
      </div>

      {/* Tabs */}
      <div className="border-b flex gap-6">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`pb-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === key ? "border-black text-black" : "border-transparent text-gray-500 hover:text-gray-900"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {errors[tab] && <ErrorState msg={errors[tab]} />}
      {tab === "overview"     && <OverviewTab     health={health} analytics={analytics} />}
      {tab === "analytics"    && <AnalyticsTab    analytics={analytics} days={analyticsDays} setDays={setAnalyticsDays} />}
      {tab === "operational"  && <OperationalTab  data={operational} />}
      {tab === "priorities"   && <PriorityTab     data={priorities} />}
      {tab === "report"       && <ReportTab       data={report} />}
    </div>
  );
}
