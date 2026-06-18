"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// ── Types ─────────────────────────────────────────────────────────────────────

interface CoachResult {
  content: string;
  analysis_type: string;
  language: string;
  profile_summary: {
    target_title?: string;
    skills_count: number;
    experience_count: number;
    goals_count: number;
  };
}

// ── Analysis types ─────────────────────────────────────────────────────────────

const ANALYSES = [
  {
    id: "full",
    label: "Komplet analyse",
    desc: "Styrker, gaps, karrierevej, handlingsplan og certifikatanbefalinger",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
      </svg>
    ),
  },
  {
    id: "skills_gap",
    label: "Kompetencegap",
    desc: "De vigtigste kompetencer du mangler til dit næste karrieretrin",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M2 20h20M6 20V10M12 20V4M18 20v-8"/>
      </svg>
    ),
  },
  {
    id: "career_path",
    label: "Karrierevej",
    desc: "Realistiske næste roller baseret på din baggrund",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M3 12h18M12 3l9 9-9 9"/>
      </svg>
    ),
  },
  {
    id: "next_steps",
    label: "Næste skridt",
    desc: "5 konkrete handlinger du kan tage de næste 30 dage",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
      </svg>
    ),
  },
];

// ── Markdown renderer ─────────────────────────────────────────────────────────

function RenderMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="mt-5 mb-2 text-base font-semibold text-blue-700">
          {trimmed.slice(3)}
        </h2>
      );
    } else if (trimmed.startsWith("# ")) {
      elements.push(
        <h1 key={i} className="mt-4 mb-2 text-lg font-bold text-slate-900">
          {trimmed.slice(2)}
        </h1>
      );
    } else if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
      elements.push(
        <div key={i} className="flex items-start gap-2 py-0.5">
          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
          <span className="text-sm text-slate-700">{trimmed.slice(2)}</span>
        </div>
      );
    } else if (trimmed === "" || trimmed === "---") {
      elements.push(<div key={i} className="h-2" />);
    } else if (trimmed.startsWith("**") && trimmed.endsWith("**")) {
      elements.push(
        <p key={i} className="py-0.5 text-sm font-semibold text-slate-800">{trimmed.slice(2, -2)}</p>
      );
    } else {
      elements.push(
        <p key={i} className="py-0.5 text-sm text-slate-700">{trimmed}</p>
      );
    }
  });

  return <div className="space-y-0.5">{elements}</div>;
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function CareerCoachPage() {
  const [analysisType, setAnalysisType] = useState("full");
  const [language, setLanguage] = useState("da");
  const [targetRole, setTargetRole] = useState("");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CoachResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiPost<CoachResult>("/career-coach/analyze", {
        analysis_type: analysisType,
        language,
        target_role: targetRole || undefined,
        question: question || undefined,
      });
      setResult(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Analyse fejlede";
      if (msg.includes("402") || msg.includes("no_api_key")) {
        setError("Ingen API-nøgle konfigureret — gå til Indstillinger → API-nøgler og tilføj din Anthropic eller OpenAI nøgle.");
      } else if (msg.includes("422")) {
        setError("Din karriereprofil er for tom til en meningsfuld analyse. Upload dit CV og udfyld din profil først.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Career Coach</h1>
        <p className="mt-1 text-sm text-slate-500">
          AI-baseret karriererådgivning baseret på din komplette karriereprofil
        </p>
      </div>

      {/* Analysis Type Selection */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {ANALYSES.map(a => (
          <button
            key={a.id}
            onClick={() => setAnalysisType(a.id)}
            className={`rounded-xl border p-4 text-left transition-all ${
              analysisType === a.id
                ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500"
                : "border-slate-200 bg-white hover:border-blue-200"
            }`}
          >
            <div className={`mb-2 ${analysisType === a.id ? "text-blue-600" : "text-slate-400"}`}>
              {a.icon}
            </div>
            <p className={`text-sm font-medium ${analysisType === a.id ? "text-blue-700" : "text-slate-700"}`}>
              {a.label}
            </p>
            <p className="mt-0.5 text-xs text-slate-400">{a.desc}</p>
          </button>
        ))}
      </div>

      {/* Config */}
      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Sprog</label>
            <select
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
              value={language}
              onChange={e => setLanguage(e.target.value)}
            >
              <option value="da">Dansk</option>
              <option value="en">English</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Målrolle (valgfri)</label>
            <input
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
              placeholder="Engineering Manager, CTO, Senior Dev…"
              value={targetRole}
              onChange={e => setTargetRole(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Dit spørgsmål (valgfri)</label>
            <input
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
              placeholder="Hvad skal jeg fokusere på nu?"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === "Enter" && runAnalysis()}
            />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <Button loading={loading} onClick={runAnalysis}>
            {loading ? "Analyserer…" : "Kør analyse"}
          </Button>
        </div>
      </Card>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Profile summary */}
          {result.profile_summary && (
            <div className="flex flex-wrap gap-3">
              {result.profile_summary.target_title && (
                <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">
                  {result.profile_summary.target_title}
                </span>
              )}
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                {result.profile_summary.skills_count} kompetencer
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                {result.profile_summary.experience_count} erfaringer
              </span>
              {result.profile_summary.goals_count > 0 && (
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                  {result.profile_summary.goals_count} aktive mål
                </span>
              )}
            </div>
          )}

          <Card>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">
                {ANALYSES.find(a => a.id === result.analysis_type)?.label ?? "Analyse"}
              </h2>
              <button
                onClick={runAnalysis}
                className="text-xs text-blue-600 hover:text-blue-700"
              >
                Generer ny ↺
              </button>
            </div>
            <RenderMarkdown content={result.content} />
          </Card>
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && !error && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-16 text-center">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 text-slate-300">
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
            <path d="M12 8v4l3 3"/>
          </svg>
          <p className="font-medium text-slate-500">Vælg en analysetype og klik "Kør analyse"</p>
          <p className="mt-1 text-sm text-slate-400">
            AI-coachen bruger din karriereprofil, kompetencer, mål og historik som grundlag.
          </p>
        </div>
      )}
    </div>
  );
}
