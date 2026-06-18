"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import type {
  CVExperience,
  CVAchievement,
  CVProject,
  CVSystem,
  CVSkill,
  CVLeadership,
  CVCertification,
  ProfileScore,
  ProfileGap,
} from "@/types";

type SectionKey =
  | "experiences"
  | "achievements"
  | "projects"
  | "systems"
  | "skills"
  | "leadership"
  | "certifications";

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "experiences", label: "Erfaringer" },
  { key: "achievements", label: "Præstationer" },
  { key: "projects", label: "Projekter" },
  { key: "systems", label: "Systemer" },
  { key: "skills", label: "Kompetencer" },
  { key: "leadership", label: "Lederskab" },
  { key: "certifications", label: "Certifikater" },
];

interface ProfileData {
  experiences: CVExperience[];
  achievements: CVAchievement[];
  projects: CVProject[];
  systems: CVSystem[];
  skills: CVSkill[];
  leadership: CVLeadership[];
  certifications: CVCertification[];
  gaps: ProfileGap[];
}

export default function ProfilePage() {
  const [active, setActive] = useState<SectionKey>("experiences");
  const [data, setData] = useState<ProfileData | null>(null);
  const [score, setScore] = useState<ProfileScore | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [exp, ach, proj, sys, ski, lead, cert, gaps, sc] = await Promise.allSettled([
        apiGet<CVExperience[]>("/profile/experiences"),
        apiGet<CVAchievement[]>("/profile/achievements"),
        apiGet<CVProject[]>("/profile/projects"),
        apiGet<CVSystem[]>("/profile/systems"),
        apiGet<CVSkill[]>("/profile/skills"),
        apiGet<CVLeadership[]>("/profile/leadership"),
        apiGet<CVCertification[]>("/profile/certifications"),
        apiGet<ProfileGap[]>("/profile/gaps"),
        apiGet<ProfileScore>("/profile/score"),
      ]);

      setData({
        experiences: exp.status === "fulfilled" ? exp.value : [],
        achievements: ach.status === "fulfilled" ? ach.value : [],
        projects: proj.status === "fulfilled" ? proj.value : [],
        systems: sys.status === "fulfilled" ? sys.value : [],
        skills: ski.status === "fulfilled" ? ski.value : [],
        leadership: lead.status === "fulfilled" ? lead.value : [],
        certifications: cert.status === "fulfilled" ? cert.value : [],
        gaps: gaps.status === "fulfilled" ? gaps.value : [],
      });

      if (sc.status === "fulfilled") setScore(sc.value);
    } finally {
      setLoading(false);
    }
  }

  async function recalculate() {
    setRecalculating(true);
    try {
      const s = await apiPost<ProfileScore>("/profile/score/recalculate");
      setScore(s);
    } finally {
      setRecalculating(false);
    }
  }

  const sectionCount = (key: SectionKey) => data?.[key]?.length ?? 0;
  const sectionScore = (key: SectionKey) => score?.sections?.[key] ?? 0;

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

  return (
    <div className="space-y-6">
      {/* Header + score */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Kandidatprofil</h1>
          <p className="mt-1 text-sm text-slate-500">
            Alt hvad AI&apos;en har lært om dig — fra dit CV og interviewet
          </p>
        </div>
        {score && (
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <div className="text-right">
              <p className="text-2xl font-bold text-blue-600">{score.overall}%</p>
              <p className="text-xs text-slate-500">Fuldstændighed</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              loading={recalculating}
              onClick={recalculate}
            >
              Opdater
            </Button>
          </div>
        )}
      </div>

      {/* Section tabs */}
      <div className="flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-1">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            onClick={() => setActive(s.key)}
            className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              active === s.key
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {s.label}
            <span
              className={`rounded-full px-1.5 py-0.5 text-xs ${
                active === s.key
                  ? "bg-blue-100 text-blue-700"
                  : "bg-slate-200 text-slate-600"
              }`}
            >
              {sectionCount(s.key)}
            </span>
          </button>
        ))}
      </div>

      {/* Section score bar */}
      {score && (
        <div className="flex items-center gap-3 rounded-lg bg-white px-4 py-3 border border-slate-200">
          <span className="text-sm text-slate-600">
            {SECTIONS.find((s) => s.key === active)?.label}
          </span>
          <Progress
            value={sectionScore(active)}
            colorByScore
            className="flex-1"
          />
          <span className="text-sm font-semibold text-slate-700">
            {sectionScore(active)}%
          </span>
        </div>
      )}

      {/* Section content */}
      {active === "experiences" && <ExperiencesSection items={data?.experiences ?? []} />}
      {active === "achievements" && <AchievementsSection items={data?.achievements ?? []} />}
      {active === "projects" && <ProjectsSection items={data?.projects ?? []} />}
      {active === "systems" && <SystemsSection items={data?.systems ?? []} />}
      {active === "skills" && <SkillsSection items={data?.skills ?? []} />}
      {active === "leadership" && <LeadershipSection items={data?.leadership ?? []} />}
      {active === "certifications" && <CertificationsSection items={data?.certifications ?? []} />}

      {/* Open gaps */}
      {(data?.gaps?.length ?? 0) > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Åbne gaps</CardTitle>
            <Badge variant="warning">{data!.gaps.length}</Badge>
          </CardHeader>
          <div className="space-y-2">
            {data!.gaps.map((gap) => (
              <div key={gap.id} className="flex items-start gap-2">
                <Badge
                  variant={
                    gap.priority === "high"
                      ? "danger"
                      : gap.priority === "medium"
                      ? "warning"
                      : "default"
                  }
                >
                  {gap.priority}
                </Badge>
                <div>
                  <p className="text-sm text-slate-700">{gap.description}</p>
                  <p className="text-xs text-slate-400">{gap.section}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ── Sections ───────────────────────────────────────────────────────────────────

function EmptyState({ label }: { label: string }) {
  return (
    <Card>
      <p className="text-center text-sm text-slate-400">
        Ingen {label} endnu — svar på AI-interviewet for at tilføje
      </p>
    </Card>
  );
}

function ExperiencesSection({ items }: { items: CVExperience[] }) {
  if (!items.length) return <EmptyState label="erfaringer" />;
  return (
    <div className="space-y-4">
      {items.map((e) => (
        <Card key={e.id}>
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-slate-900">{e.title}</p>
              <p className="text-sm text-slate-600">{e.company}</p>
              <p className="mt-0.5 text-xs text-slate-400">
                {formatDate(e.period_start)} —{" "}
                {e.is_current ? "nu" : formatDate(e.period_end)}
                {e.location && ` · ${e.location}`}
              </p>
            </div>
            {e.is_current && <Badge variant="info">Nuværende</Badge>}
          </div>
          {e.description && (
            <p className="mt-3 text-sm text-slate-600">{e.description}</p>
          )}
          {e.achievements?.length > 0 && (
            <ul className="mt-2 space-y-1">
              {e.achievements.map((a, i) => (
                <li key={i} className="flex gap-2 text-sm text-slate-600">
                  <span className="text-blue-500">·</span> {a}
                </li>
              ))}
            </ul>
          )}
          {e.technologies?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {e.technologies.map((t) => (
                <Badge key={t}>{t}</Badge>
              ))}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function AchievementsSection({ items }: { items: CVAchievement[] }) {
  if (!items.length) return <EmptyState label="præstationer" />;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {items.map((a) => (
        <Card key={a.id}>
          <div className="flex items-start justify-between gap-2">
            <p className="font-semibold text-slate-900">{a.title}</p>
            <Badge
              variant={
                a.impact_level === "high"
                  ? "success"
                  : a.impact_level === "medium"
                  ? "warning"
                  : "default"
              }
            >
              {a.impact_level}
            </Badge>
          </div>
          {a.metric && (
            <p className="mt-2 text-lg font-bold text-blue-600">{a.metric}</p>
          )}
          {a.description && (
            <p className="mt-1 text-sm text-slate-600">{a.description}</p>
          )}
          {a.year && (
            <p className="mt-2 text-xs text-slate-400">{a.year}</p>
          )}
        </Card>
      ))}
    </div>
  );
}

function ProjectsSection({ items }: { items: CVProject[] }) {
  if (!items.length) return <EmptyState label="projekter" />;
  return (
    <div className="space-y-4">
      {items.map((p) => (
        <Card key={p.id}>
          <p className="font-semibold text-slate-900">{p.name}</p>
          {p.role && <p className="text-sm text-slate-500">{p.role}</p>}
          {p.description && (
            <p className="mt-2 text-sm text-slate-600">{p.description}</p>
          )}
          {p.outcomes && (
            <div className="mt-3 rounded-lg bg-green-50 px-3 py-2">
              <p className="text-xs font-medium text-green-700">Resultat</p>
              <p className="text-sm text-green-800">{p.outcomes}</p>
            </div>
          )}
          {p.technologies?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {p.technologies.map((t) => (
                <Badge key={t}>{t}</Badge>
              ))}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function SystemsSection({ items }: { items: CVSystem[] }) {
  if (!items.length) return <EmptyState label="systemer" />;

  const byCategory = items.reduce(
    (acc, s) => {
      const cat = s.category ?? "Andet";
      (acc[cat] ??= []).push(s);
      return acc;
    },
    {} as Record<string, CVSystem[]>
  );

  const LEVEL_LABEL: Record<string, string> = {
    beginner: "Begynder",
    intermediate: "Mellemniveau",
    advanced: "Avanceret",
    expert: "Ekspert",
  };

  return (
    <div className="space-y-4">
      {Object.entries(byCategory).map(([cat, systems]) => (
        <Card key={cat}>
          <CardHeader>
            <CardTitle>{cat}</CardTitle>
            <Badge>{systems.length}</Badge>
          </CardHeader>
          <div className="grid gap-2 sm:grid-cols-2">
            {systems.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2"
              >
                <span className="text-sm font-medium text-slate-800">
                  {s.name}
                </span>
                <Badge
                  variant={
                    s.proficiency === "expert" || s.proficiency === "advanced"
                      ? "success"
                      : s.proficiency === "intermediate"
                      ? "info"
                      : "default"
                  }
                >
                  {LEVEL_LABEL[s.proficiency] ?? s.proficiency}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

function SkillsSection({ items }: { items: CVSkill[] }) {
  if (!items.length) return <EmptyState label="kompetencer" />;

  const byCategory = items.reduce(
    (acc, s) => {
      const cat = s.category ?? "Andet";
      (acc[cat] ??= []).push(s);
      return acc;
    },
    {} as Record<string, CVSkill[]>
  );

  return (
    <div className="space-y-4">
      {Object.entries(byCategory).map(([cat, skills]) => (
        <Card key={cat}>
          <p className="mb-3 text-sm font-medium text-slate-700 capitalize">
            {cat}
          </p>
          <div className="flex flex-wrap gap-2">
            {skills.map((s) => (
              <Badge key={s.id} variant="info">
                {s.name}
                {s.level && ` · ${s.level}`}
              </Badge>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

function LeadershipSection({ items }: { items: CVLeadership[] }) {
  if (!items.length) return <EmptyState label="lederskabserfaring" />;
  return (
    <div className="space-y-4">
      {items.map((l) => (
        <Card key={l.id}>
          <p className="font-semibold text-slate-900">{l.title}</p>
          {l.scope && <p className="text-sm text-slate-500">{l.scope}</p>}
          {l.direct_reports != null && l.direct_reports > 0 && (
            <p className="mt-2 text-sm text-slate-600">
              <span className="font-medium text-slate-800">
                {l.direct_reports}
              </span>{" "}
              direkte rapporterende
            </p>
          )}
          {l.responsibilities?.length > 0 && (
            <ul className="mt-2 space-y-1">
              {l.responsibilities.map((r, i) => (
                <li key={i} className="flex gap-2 text-sm text-slate-600">
                  <span className="text-blue-500">·</span> {r}
                </li>
              ))}
            </ul>
          )}
        </Card>
      ))}
    </div>
  );
}

function CertificationsSection({ items }: { items: CVCertification[] }) {
  if (!items.length) return <EmptyState label="certifikater" />;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {items.map((c) => (
        <Card key={c.id}>
          <p className="font-semibold text-slate-900">{c.name}</p>
          {c.issuer && (
            <p className="text-sm text-slate-500">{c.issuer}</p>
          )}
          <div className="mt-2 flex gap-3 text-xs text-slate-400">
            {c.issued_at && <span>Udstedt: {formatDate(c.issued_at)}</span>}
            {c.expires_at && <span>Udløber: {formatDate(c.expires_at)}</span>}
          </div>
        </Card>
      ))}
    </div>
  );
}
