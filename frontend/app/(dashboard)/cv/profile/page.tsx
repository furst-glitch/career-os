"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import type {
  CVExperience,
  CVEducation,
  CVAchievement,
  CVProject,
  CVSystem,
  CVSkill,
  CVLeadership,
  CVCertification,
  ProfileScore,
  ProfileGap,
} from "@/types";

// ── Shared styles ─────────────────────────────────────────────────────────────
const I = "w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-400";

// ── Date helpers ──────────────────────────────────────────────────────────────
const toMonth = (d?: string | null) => d?.slice(0, 7) ?? "";
const fromMonth = (m: string) => (m ? m + "-01" : null);

// ── Reusable primitives ───────────────────────────────────────────────────────

function F({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">
        {label}{required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}

function Sel({ value, onChange, options, placeholder }: {
  value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
}) {
  return (
    <select className={I + " bg-white"} value={value} onChange={e => onChange(e.target.value)}>
      {placeholder && <option value="">{placeholder}</option>}
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function ItemActions({ onEdit, onDelete, onUp, onDown, first, last }: {
  onEdit: () => void; onDelete: () => void;
  onUp?: () => void; onDown?: () => void;
  first?: boolean; last?: boolean;
}) {
  return (
    <div className="flex shrink-0 items-center gap-0.5">
      {onUp && (
        <button disabled={first} onClick={onUp} title="Flyt op"
          className="rounded p-1.5 text-slate-300 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-20 text-xs">▲</button>
      )}
      {onDown && (
        <button disabled={last} onClick={onDown} title="Flyt ned"
          className="rounded p-1.5 text-slate-300 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-20 text-xs">▼</button>
      )}
      <button onClick={onEdit}
        className="rounded px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800">
        Rediger
      </button>
      <button onClick={onDelete}
        className="rounded px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-50 hover:text-red-600">
        Slet
      </button>
    </div>
  );
}

function FormFooter({ onSave, onCancel, saving }: { onSave: () => void; onCancel: () => void; saving: boolean }) {
  return (
    <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3">
      <Button size="sm" loading={saving} onClick={onSave}>Gem</Button>
      <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>Annuller</Button>
    </div>
  );
}

function DeletePrompt({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
      <span className="text-sm text-red-700">Slet dette element?</span>
      <Button size="sm" variant="danger" onClick={onConfirm}>Ja, slet</Button>
      <Button size="sm" variant="ghost" onClick={onCancel}>Annuller</Button>
    </div>
  );
}

function SectionWrap({ title, onAdd, children }: { title: string; onAdd: () => void; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
        <Button size="sm" variant="outline" onClick={onAdd}>+ Tilføj</Button>
      </div>
      {children}
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <Card padding="sm">
      <p className="py-1 text-center text-sm text-slate-400">
        Ingen {label} endnu — klik &ldquo;+ Tilføj&rdquo; for at tilføje
      </p>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type SectionKey = "experiences" | "educations" | "achievements" | "projects" | "systems" | "skills" | "leadership" | "certifications";

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "experiences",    label: "Erfaringer" },
  { key: "educations",     label: "Uddannelse" },
  { key: "achievements",   label: "Præstationer" },
  { key: "projects",       label: "Projekter" },
  { key: "skills",         label: "Kompetencer" },
  { key: "systems",        label: "Systemer" },
  { key: "leadership",     label: "Lederskab" },
  { key: "certifications", label: "Certifikater" },
];

interface ProfileData {
  experiences:    CVExperience[];
  educations:     CVEducation[];
  achievements:   CVAchievement[];
  projects:       CVProject[];
  systems:        CVSystem[];
  skills:         CVSkill[];
  leadership:     CVLeadership[];
  certifications: CVCertification[];
  gaps:           ProfileGap[];
}

export default function ProfilePage() {
  const [active, setActive] = useState<SectionKey>("experiences");
  const [data, setData] = useState<ProfileData | null>(null);
  const [score, setScore] = useState<ProfileScore | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);

  useEffect(() => { loadAll(); }, []);

  async function loadAll() {
    setLoading(true);
    const [exp, edu, ach, proj, sys, ski, lead, cert, gaps, sc] = await Promise.allSettled([
      apiGet<CVExperience[]>("/profile/experiences"),
      apiGet<CVEducation[]>("/profile/educations"),
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
      experiences:    exp.status    === "fulfilled" ? exp.value    : [],
      educations:     edu.status    === "fulfilled" ? edu.value    : [],
      achievements:   ach.status    === "fulfilled" ? ach.value    : [],
      projects:       proj.status   === "fulfilled" ? proj.value   : [],
      systems:        sys.status    === "fulfilled" ? sys.value    : [],
      skills:         ski.status    === "fulfilled" ? ski.value    : [],
      leadership:     lead.status   === "fulfilled" ? lead.value   : [],
      certifications: cert.status   === "fulfilled" ? cert.value   : [],
      gaps:           gaps.status   === "fulfilled" ? gaps.value   : [],
    });
    if (sc.status === "fulfilled") setScore(sc.value);
    setLoading(false);
  }

  async function recalculate() {
    setRecalculating(true);
    try {
      const s = await apiPost<ProfileScore>("/profile/score/recalculate");
      setScore(s);
    } finally { setRecalculating(false); }
  }

  const count = (k: SectionKey) => data?.[k]?.length ?? 0;
  const sScore = (k: SectionKey) => ((score?.sections as unknown) as Record<string, number>)?.[k] ?? 0;

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <svg className="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
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
            Alt hvad systemet ved om dig — rediger, tilføj og organiser frit
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div className="text-right">
            <p className="text-2xl font-bold text-blue-600">{score?.overall ?? "–"}%</p>
            <p className="text-xs text-slate-500">Fuldstændighed</p>
          </div>
          <Button variant="outline" size="sm" loading={recalculating} onClick={recalculate}>
            Opdater
          </Button>
        </div>
      </div>

      {/* Section tabs */}
      <div className="flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-1">
        {SECTIONS.map(s => (
          <button key={s.key} onClick={() => setActive(s.key)}
            className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              active === s.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}>
            {s.label}
            <span className={`rounded-full px-1.5 py-0.5 text-xs ${
              active === s.key ? "bg-blue-100 text-blue-700" : "bg-slate-200 text-slate-600"
            }`}>{count(s.key)}</span>
          </button>
        ))}
      </div>

      {/* Section score bar */}
      {score && (
        <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
          <span className="text-sm text-slate-600">{SECTIONS.find(s => s.key === active)?.label}</span>
          <Progress value={sScore(active)} colorByScore className="flex-1" />
          <span className="text-sm font-semibold text-slate-700">{sScore(active)}%</span>
        </div>
      )}

      {/* Active section */}
      {data && (
        <>
          {active === "experiences"    && <ExperiencesSection    init={data.experiences} />}
          {active === "educations"     && <EducationsSection     init={data.educations} />}
          {active === "achievements"   && <AchievementsSection   init={data.achievements} />}
          {active === "projects"       && <ProjectsSection       init={data.projects} />}
          {active === "skills"         && <SkillsSection         init={data.skills} />}
          {active === "systems"        && <SystemsSection        init={data.systems} />}
          {active === "leadership"     && <LeadershipSection     init={data.leadership} />}
          {active === "certifications" && <CertificationsSection init={data.certifications} />}
        </>
      )}

      {/* Open gaps */}
      {(data?.gaps?.length ?? 0) > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Åbne gaps</CardTitle>
            <Badge variant="warning">{data!.gaps.length}</Badge>
          </CardHeader>
          <div className="space-y-2">
            {data!.gaps.map(gap => (
              <div key={gap.id} className="flex items-start gap-2">
                <Badge variant={gap.priority === "high" ? "danger" : gap.priority === "medium" ? "warning" : "default"}>
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

// ── Experiences ───────────────────────────────────────────────────────────────

function ExperiencesSection({ init }: { init: CVExperience[] }) {
  const [items, setItems] = useState(init);
  const [editId, setEditId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setItems(init); }, [init]);

  async function create(d: Partial<CVExperience>) {
    setSaving(true);
    try {
      const item = await apiPost<CVExperience>("/profile/experiences", d);
      setItems(p => [item, ...p]);
      setAdding(false);
    } finally { setSaving(false); }
  }
  async function update(id: string, d: Partial<CVExperience>) {
    setSaving(true);
    try {
      const item = await apiPut<CVExperience>(`/profile/experiences/${id}`, d);
      setItems(p => p.map(i => i.id === id ? item : i));
      setEditId(null);
    } finally { setSaving(false); }
  }
  async function remove(id: string) {
    setSaving(true);
    try {
      await apiDelete(`/profile/experiences/${id}`);
      setItems(p => p.filter(i => i.id !== id));
      setDelId(null);
    } finally { setSaving(false); }
  }

  return (
    <SectionWrap title="Erfaringer" onAdd={() => { setAdding(true); setEditId(null); }}>
      {adding && (
        <Card padding="sm">
          <ExperienceForm saving={saving} onSave={create} onCancel={() => setAdding(false)} />
        </Card>
      )}
      {!items.length && !adding && <Empty label="erfaringer" />}
      {items.map(exp => (
        <div key={exp.id}>
          {delId === exp.id ? (
            <DeletePrompt onConfirm={() => remove(exp.id)} onCancel={() => setDelId(null)} />
          ) : editId === exp.id ? (
            <Card padding="sm">
              <ExperienceForm item={exp} saving={saving} onSave={d => update(exp.id, d)} onCancel={() => setEditId(null)} />
            </Card>
          ) : (
            <Card padding="sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-slate-900">{exp.title}</p>
                  <p className="text-sm text-slate-600">{exp.company}</p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {formatDate(exp.period_start)} — {exp.is_current ? "nu" : formatDate(exp.period_end)}
                    {exp.location && ` · ${exp.location}`}
                  </p>
                  {exp.description && <p className="mt-2 text-sm text-slate-600">{exp.description}</p>}
                  {exp.achievements?.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {exp.achievements.map((a, i) => (
                        <li key={i} className="flex gap-2 text-sm text-slate-600"><span className="text-blue-500">·</span>{a}</li>
                      ))}
                    </ul>
                  )}
                  {exp.technologies?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {exp.technologies.map(t => <Badge key={t}>{t}</Badge>)}
                    </div>
                  )}
                </div>
                <ItemActions
                  onEdit={() => { setEditId(exp.id); setAdding(false); }}
                  onDelete={() => setDelId(exp.id)}
                />
              </div>
            </Card>
          )}
        </div>
      ))}
    </SectionWrap>
  );
}

function ExperienceForm({ item, saving, onSave, onCancel }: {
  item?: CVExperience; saving: boolean;
  onSave: (d: Partial<CVExperience>) => void;
  onCancel: () => void;
}) {
  const [d, setD] = useState({
    title:        item?.title ?? "",
    company:      item?.company ?? "",
    location:     item?.location ?? "",
    period_start: toMonth(item?.period_start),
    period_end:   toMonth(item?.period_end),
    is_current:   item?.is_current ?? false,
    description:  item?.description ?? "",
    achievements: (item?.achievements ?? []).join("\n"),
    technologies: (item?.technologies ?? []).join(", "),
  });
  const s = (k: string, v: unknown) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({
    ...d,
    period_start: fromMonth(d.period_start),
    period_end:   d.is_current ? null : fromMonth(d.period_end),
    achievements: d.achievements.split("\n").map(x => x.trim()).filter(Boolean),
    technologies: d.technologies.split(",").map(x => x.trim()).filter(Boolean),
  });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <F label="Stilling" required><input className={I} value={d.title} onChange={e => s("title", e.target.value)} placeholder="Senior Developer" /></F>
        <F label="Virksomhed" required><input className={I} value={d.company} onChange={e => s("company", e.target.value)} placeholder="Acme A/S" /></F>
      </div>
      <div className="grid grid-cols-4 gap-3">
        <F label="Lokation"><input className={I} value={d.location} onChange={e => s("location", e.target.value)} placeholder="København" /></F>
        <F label="Startdato"><input type="month" className={I} value={d.period_start} onChange={e => s("period_start", e.target.value)} /></F>
        <F label="Slutdato"><input type="month" className={I} value={d.period_end} onChange={e => s("period_end", e.target.value)} disabled={d.is_current} /></F>
        <F label="Nuværende">
          <div className="flex h-9 items-center gap-2">
            <input type="checkbox" checked={d.is_current} onChange={e => s("is_current", e.target.checked)} className="h-4 w-4 rounded border-slate-300 text-blue-600" />
            <span className="text-sm text-slate-600">Ja</span>
          </div>
        </F>
      </div>
      <F label="Beskrivelse">
        <textarea className={I + " resize-none"} rows={3} value={d.description} onChange={e => s("description", e.target.value)} placeholder="Beskriv din rolle og ansvar" />
      </F>
      <div className="grid grid-cols-2 gap-3">
        <F label="Præstationer (én per linje)">
          <textarea className={I + " resize-none"} rows={3} value={d.achievements} onChange={e => s("achievements", e.target.value)} placeholder={"Reducerede deploymenttid med 60%\nØgede testdækning fra 40% til 85%"} />
        </F>
        <F label="Teknologier (kommasepareret)">
          <textarea className={I + " resize-none"} rows={3} value={d.technologies} onChange={e => s("technologies", e.target.value)} placeholder="Python, React, PostgreSQL" />
        </F>
      </div>
      <FormFooter onSave={() => onSave(payload())} onCancel={onCancel} saving={saving} />
    </div>
  );
}

// ── Educations ────────────────────────────────────────────────────────────────

function EducationsSection({ init }: { init: CVEducation[] }) {
  const [items, setItems] = useState(init);
  const [editId, setEditId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setItems(init); }, [init]);

  async function create(d: Partial<CVEducation>) {
    setSaving(true);
    try {
      const item = await apiPost<CVEducation>("/profile/educations", d);
      setItems(p => [item, ...p]);
      setAdding(false);
    } finally { setSaving(false); }
  }
  async function update(id: string, d: Partial<CVEducation>) {
    setSaving(true);
    try {
      const item = await apiPut<CVEducation>(`/profile/educations/${id}`, d);
      setItems(p => p.map(i => i.id === id ? item : i));
      setEditId(null);
    } finally { setSaving(false); }
  }
  async function remove(id: string) {
    setSaving(true);
    try {
      await apiDelete(`/profile/educations/${id}`);
      setItems(p => p.filter(i => i.id !== id));
      setDelId(null);
    } finally { setSaving(false); }
  }

  return (
    <SectionWrap title="Uddannelse" onAdd={() => { setAdding(true); setEditId(null); }}>
      {adding && (
        <Card padding="sm">
          <EducationForm saving={saving} onSave={create} onCancel={() => setAdding(false)} />
        </Card>
      )}
      {!items.length && !adding && <Empty label="uddannelse" />}
      {items.map(edu => (
        <div key={edu.id}>
          {delId === edu.id ? (
            <DeletePrompt onConfirm={() => remove(edu.id)} onCancel={() => setDelId(null)} />
          ) : editId === edu.id ? (
            <Card padding="sm">
              <EducationForm item={edu} saving={saving} onSave={d => update(edu.id, d)} onCancel={() => setEditId(null)} />
            </Card>
          ) : (
            <Card padding="sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">{edu.degree}</p>
                  <p className="text-sm text-slate-600">{edu.institution}</p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {formatDate(edu.period_start)} — {formatDate(edu.period_end)}
                  </p>
                  {edu.description && <p className="mt-2 text-sm text-slate-600">{edu.description}</p>}
                </div>
                <ItemActions onEdit={() => { setEditId(edu.id); setAdding(false); }} onDelete={() => setDelId(edu.id)} />
              </div>
            </Card>
          )}
        </div>
      ))}
    </SectionWrap>
  );
}

function EducationForm({ item, saving, onSave, onCancel }: {
  item?: CVEducation; saving: boolean;
  onSave: (d: Partial<CVEducation>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({
    degree:       item?.degree ?? "",
    institution:  item?.institution ?? "",
    period_start: toMonth(item?.period_start),
    period_end:   toMonth(item?.period_end),
    description:  item?.description ?? "",
  });
  const s = (k: string, v: unknown) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({ ...d, period_start: fromMonth(d.period_start), period_end: fromMonth(d.period_end) });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <F label="Uddannelse" required><input className={I} value={d.degree} onChange={e => s("degree", e.target.value)} placeholder="Cand.it · Datavidenskab" /></F>
        <F label="Institution" required><input className={I} value={d.institution} onChange={e => s("institution", e.target.value)} placeholder="Aarhus Universitet" /></F>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <F label="Startdato"><input type="month" className={I} value={d.period_start} onChange={e => s("period_start", e.target.value)} /></F>
        <F label="Slutdato"><input type="month" className={I} value={d.period_end} onChange={e => s("period_end", e.target.value)} /></F>
      </div>
      <F label="Beskrivelse">
        <textarea className={I + " resize-none"} rows={2} value={d.description} onChange={e => s("description", e.target.value)} placeholder="Specialisering, afhandling m.m." />
      </F>
      <FormFooter onSave={() => onSave(payload())} onCancel={onCancel} saving={saving} />
    </div>
  );
}

// ── Achievements ──────────────────────────────────────────────────────────────

const IMPACT_OPTS = [
  { value: "low", label: "Lav" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "Høj" },
];

function AchievementsSection({ init }: { init: CVAchievement[] }) {
  const [items, setItems] = useState(init);
  const [editId, setEditId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setItems(init); }, [init]);

  async function create(d: Partial<CVAchievement>) {
    setSaving(true);
    try { const item = await apiPost<CVAchievement>("/profile/achievements", d); setItems(p => [...p, item]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function update(id: string, d: Partial<CVAchievement>) {
    setSaving(true);
    try { const item = await apiPut<CVAchievement>(`/profile/achievements/${id}`, d); setItems(p => p.map(i => i.id === id ? item : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function remove(id: string) {
    setSaving(true);
    try { await apiDelete(`/profile/achievements/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }
  async function move(id: string, dir: "up" | "down") {
    const idx = items.findIndex(i => i.id === id);
    const ni = dir === "up" ? idx - 1 : idx + 1;
    if (ni < 0 || ni >= items.length) return;
    const n = [...items]; [n[idx], n[ni]] = [n[ni], n[idx]]; setItems(n);
    await Promise.all([
      apiPut(`/profile/achievements/${n[idx].id}`, { sort_order: idx }),
      apiPut(`/profile/achievements/${n[ni].id}`, { sort_order: ni }),
    ]).catch(() => setItems(items));
  }

  return (
    <SectionWrap title="Præstationer" onAdd={() => { setAdding(true); setEditId(null); }}>
      {adding && <Card padding="sm"><AchievementForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!items.length && !adding && <Empty label="præstationer" />}
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((a, idx) => (
          <div key={a.id}>
            {delId === a.id ? (
              <DeletePrompt onConfirm={() => remove(a.id)} onCancel={() => setDelId(null)} />
            ) : editId === a.id ? (
              <Card padding="sm"><AchievementForm item={a} saving={saving} onSave={d => update(a.id, d)} onCancel={() => setEditId(null)} /></Card>
            ) : (
              <Card padding="sm">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-slate-900">{a.title}</p>
                  <ItemActions
                    onEdit={() => { setEditId(a.id); setAdding(false); }} onDelete={() => setDelId(a.id)}
                    onUp={() => move(a.id, "up")} onDown={() => move(a.id, "down")} first={idx === 0} last={idx === items.length - 1}
                  />
                </div>
                <Badge variant={a.impact_level === "high" ? "success" : a.impact_level === "medium" ? "warning" : "default"}>{a.impact_level}</Badge>
                {a.metric && <p className="mt-2 text-lg font-bold text-blue-600">{a.metric}</p>}
                {a.description && <p className="mt-1 text-sm text-slate-600">{a.description}</p>}
                {a.year && <p className="mt-2 text-xs text-slate-400">{a.year}</p>}
              </Card>
            )}
          </div>
        ))}
      </div>
    </SectionWrap>
  );
}

function AchievementForm({ item, saving, onSave, onCancel }: {
  item?: CVAchievement; saving: boolean;
  onSave: (d: Partial<CVAchievement>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({
    title: item?.title ?? "", metric: item?.metric ?? "",
    description: item?.description ?? "", impact_level: item?.impact_level ?? "medium",
    year: item?.year?.toString() ?? "",
  });
  const s = (k: string, v: unknown) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({ ...d, year: d.year ? parseInt(d.year) : null });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <F label="Titel" required><input className={I} value={d.title} onChange={e => s("title", e.target.value)} placeholder="Reducerede serveromkostninger" /></F>
        <F label="Metric"><input className={I} value={d.metric} onChange={e => s("metric", e.target.value)} placeholder="40% besparelse · 2,5M DKK" /></F>
      </div>
      <F label="Beskrivelse">
        <textarea className={I + " resize-none"} rows={2} value={d.description} onChange={e => s("description", e.target.value)} placeholder="Uddyb kontekst og metode" />
      </F>
      <div className="grid grid-cols-2 gap-3">
        <F label="Impact"><Sel value={d.impact_level} onChange={v => s("impact_level", v)} options={IMPACT_OPTS} /></F>
        <F label="År"><input type="number" className={I} value={d.year} onChange={e => s("year", e.target.value)} placeholder="2023" min="1990" max="2030" /></F>
      </div>
      <FormFooter onSave={() => onSave(payload())} onCancel={onCancel} saving={saving} />
    </div>
  );
}

// ── Projects ──────────────────────────────────────────────────────────────────

function ProjectsSection({ init }: { init: CVProject[] }) {
  const [items, setItems] = useState(init);
  const [editId, setEditId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setItems(init); }, [init]);

  async function create(d: Partial<CVProject>) {
    setSaving(true);
    try { const item = await apiPost<CVProject>("/profile/projects", d); setItems(p => [...p, item]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function update(id: string, d: Partial<CVProject>) {
    setSaving(true);
    try { const item = await apiPut<CVProject>(`/profile/projects/${id}`, d); setItems(p => p.map(i => i.id === id ? item : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function remove(id: string) {
    setSaving(true);
    try { await apiDelete(`/profile/projects/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }
  async function move(id: string, dir: "up" | "down") {
    const idx = items.findIndex(i => i.id === id);
    const ni = dir === "up" ? idx - 1 : idx + 1;
    if (ni < 0 || ni >= items.length) return;
    const n = [...items]; [n[idx], n[ni]] = [n[ni], n[idx]]; setItems(n);
    await Promise.all([
      apiPut(`/profile/projects/${n[idx].id}`, { sort_order: idx }),
      apiPut(`/profile/projects/${n[ni].id}`, { sort_order: ni }),
    ]).catch(() => setItems(items));
  }

  return (
    <SectionWrap title="Projekter" onAdd={() => { setAdding(true); setEditId(null); }}>
      {adding && <Card padding="sm"><ProjectForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!items.length && !adding && <Empty label="projekter" />}
      {items.map((p, idx) => (
        <div key={p.id}>
          {delId === p.id ? (
            <DeletePrompt onConfirm={() => remove(p.id)} onCancel={() => setDelId(null)} />
          ) : editId === p.id ? (
            <Card padding="sm"><ProjectForm item={p} saving={saving} onSave={d => update(p.id, d)} onCancel={() => setEditId(null)} /></Card>
          ) : (
            <Card padding="sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-slate-900">{p.name}</p>
                  {p.role && <p className="text-sm text-slate-500">{p.role}</p>}
                  {p.description && <p className="mt-2 text-sm text-slate-600">{p.description}</p>}
                  {p.outcomes && (
                    <div className="mt-2 rounded-lg bg-green-50 px-3 py-2">
                      <p className="text-xs font-medium text-green-700">Resultat</p>
                      <p className="text-sm text-green-800">{p.outcomes}</p>
                    </div>
                  )}
                  {p.technologies?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">{p.technologies.map(t => <Badge key={t}>{t}</Badge>)}</div>
                  )}
                </div>
                <ItemActions
                  onEdit={() => { setEditId(p.id); setAdding(false); }} onDelete={() => setDelId(p.id)}
                  onUp={() => move(p.id, "up")} onDown={() => move(p.id, "down")} first={idx === 0} last={idx === items.length - 1}
                />
              </div>
            </Card>
          )}
        </div>
      ))}
    </SectionWrap>
  );
}

function ProjectForm({ item, saving, onSave, onCancel }: {
  item?: CVProject; saving: boolean;
  onSave: (d: Partial<CVProject>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({
    name: item?.name ?? "", role: item?.role ?? "",
    description: item?.description ?? "", outcomes: item?.outcomes ?? "",
    technologies: (item?.technologies ?? []).join(", "),
    period_start: toMonth(item?.period_start), period_end: toMonth(item?.period_end),
  });
  const s = (k: string, v: unknown) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({
    ...d,
    technologies: d.technologies.split(",").map(x => x.trim()).filter(Boolean),
    period_start: fromMonth(d.period_start), period_end: fromMonth(d.period_end),
  });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <F label="Projektnavn" required><input className={I} value={d.name} onChange={e => s("name", e.target.value)} placeholder="CareerOS Platform" /></F>
        <F label="Rolle"><input className={I} value={d.role} onChange={e => s("role", e.target.value)} placeholder="Tech Lead" /></F>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <F label="Teknologier"><input className={I} value={d.technologies} onChange={e => s("technologies", e.target.value)} placeholder="Next.js, FastAPI" /></F>
        <F label="Startdato"><input type="month" className={I} value={d.period_start} onChange={e => s("period_start", e.target.value)} /></F>
        <F label="Slutdato"><input type="month" className={I} value={d.period_end} onChange={e => s("period_end", e.target.value)} /></F>
      </div>
      <F label="Beskrivelse">
        <textarea className={I + " resize-none"} rows={2} value={d.description} onChange={e => s("description", e.target.value)} placeholder="Hvad handlede projektet om?" />
      </F>
      <F label="Resultater">
        <textarea className={I + " resize-none"} rows={2} value={d.outcomes} onChange={e => s("outcomes", e.target.value)} placeholder="Hvad blev opnået?" />
      </F>
      <FormFooter onSave={() => onSave(payload())} onCancel={onCancel} saving={saving} />
    </div>
  );
}

// ── Skills ────────────────────────────────────────────────────────────────────

const LEVEL_OPTS = [
  { value: "beginner", label: "Begynder" }, { value: "intermediate", label: "Mellemniveau" },
  { value: "advanced", label: "Avanceret" }, { value: "expert", label: "Ekspert" },
];
const LEVEL_LABEL: Record<string, string> = { beginner: "Begynder", intermediate: "Mellemniveau", advanced: "Avanceret", expert: "Ekspert" };

function SkillsSection({ init }: { init: CVSkill[] }) {
  const [items, setItems] = useState(init);
  const [editId, setEditId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setItems(init); }, [init]);

  async function create(d: Partial<CVSkill>) {
    setSaving(true);
    try { const item = await apiPost<CVSkill>("/profile/skills", d); setItems(p => [...p, item]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function update(id: string, d: Partial<CVSkill>) {
    setSaving(true);
    try { const item = await apiPut<CVSkill>(`/profile/skills/${id}`, d); setItems(p => p.map(i => i.id === id ? item : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function remove(id: string) {
    setSaving(true);
    try { await apiDelete(`/profile/skills/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }

  const byCategory = items.reduce((acc, s) => { (acc[s.category ?? "Andet"] ??= []).push(s); return acc; }, {} as Record<string, CVSkill[]>);

  return (
    <SectionWrap title="Kompetencer" onAdd={() => { setAdding(true); setEditId(null); }}>
      {adding && <Card padding="sm"><SkillForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!items.length && !adding && <Empty label="kompetencer" />}
      {Object.entries(byCategory).map(([cat, skills]) => (
        <Card key={cat} padding="sm">
          <p className="mb-3 text-sm font-medium capitalize text-slate-700">{cat}</p>
          <div className="flex flex-wrap gap-2">
            {skills.map(sk => (
              <div key={sk.id} className="group relative">
                {delId === sk.id ? (
                  <DeletePrompt onConfirm={() => remove(sk.id)} onCancel={() => setDelId(null)} />
                ) : editId === sk.id ? (
                  <div className="w-72 rounded-lg border border-blue-200 bg-blue-50 p-3">
                    <SkillForm item={sk} saving={saving} onSave={d => update(sk.id, d)} onCancel={() => setEditId(null)} />
                  </div>
                ) : (
                  <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 py-1 pl-3 pr-1">
                    <span className="text-sm font-medium text-slate-700">{sk.name}</span>
                    {sk.level && <span className="text-xs text-slate-400">· {LEVEL_LABEL[sk.level] ?? sk.level}</span>}
                    <button onClick={() => { setEditId(sk.id); setAdding(false); }} className="rounded-full p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600 text-xs">✏</button>
                    <button onClick={() => setDelId(sk.id)} className="rounded-full p-0.5 text-red-300 hover:bg-red-100 hover:text-red-500 text-xs">✕</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      ))}
    </SectionWrap>
  );
}

function SkillForm({ item, saving, onSave, onCancel }: {
  item?: CVSkill; saving: boolean;
  onSave: (d: Partial<CVSkill>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState<{ name: string; category: string; level: string }>({ name: item?.name ?? "", category: item?.category ?? "technical", level: item?.level ?? "" });
  const s = (k: string, v: unknown) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({ ...d, level: (d.level || null) as CVSkill["level"] });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <F label="Kompetence" required><input className={I} value={d.name} onChange={e => s("name", e.target.value)} placeholder="Python" /></F>
        <F label="Kategori"><input className={I} value={d.category} onChange={e => s("category", e.target.value)} placeholder="technical" /></F>
        <F label="Niveau"><Sel value={d.level} onChange={v => s("level", v)} options={LEVEL_OPTS} placeholder="Vælg niveau" /></F>
      </div>
      <FormFooter onSave={() => onSave(payload())} onCancel={onCancel} saving={saving} />
    </div>
  );
}

// ── Systems ───────────────────────────────────────────────────────────────────

function SystemsSection({ init }: { init: CVSystem[] }) {
  const [items, setItems] = useState(init);
  const [editId, setEditId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setItems(init); }, [init]);

  async function create(d: Partial<CVSystem>) {
    setSaving(true);
    try { const item = await apiPost<CVSystem>("/profile/systems", d); setItems(p => [...p, item]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function update(id: string, d: Partial<CVSystem>) {
    setSaving(true);
    try { const item = await apiPut<CVSystem>(`/profile/systems/${id}`, d); setItems(p => p.map(i => i.id === id ? item : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function remove(id: string) {
    setSaving(true);
    try { await apiDelete(`/profile/systems/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }

  const byCategory = items.reduce((acc, s) => { (acc[s.category ?? "Andet"] ??= []).push(s); return acc; }, {} as Record<string, CVSystem[]>);

  return (
    <SectionWrap title="Systemer" onAdd={() => { setAdding(true); setEditId(null); }}>
      {adding && <Card padding="sm"><SystemForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!items.length && !adding && <Empty label="systemer" />}
      {Object.entries(byCategory).map(([cat, systems]) => (
        <Card key={cat} padding="sm">
          <CardHeader><CardTitle>{cat}</CardTitle><Badge>{systems.length}</Badge></CardHeader>
          <div className="grid gap-2 sm:grid-cols-2">
            {systems.map(sys => (
              <div key={sys.id}>
                {delId === sys.id ? (
                  <DeletePrompt onConfirm={() => remove(sys.id)} onCancel={() => setDelId(null)} />
                ) : editId === sys.id ? (
                  <SystemForm item={sys} saving={saving} onSave={d => update(sys.id, d)} onCancel={() => setEditId(null)} />
                ) : (
                  <div className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2">
                    <span className="text-sm font-medium text-slate-800">{sys.name}</span>
                    <div className="flex items-center gap-2">
                      <Badge variant={sys.proficiency === "expert" || sys.proficiency === "advanced" ? "success" : sys.proficiency === "intermediate" ? "info" : "default"}>
                        {LEVEL_LABEL[sys.proficiency] ?? sys.proficiency}
                      </Badge>
                      <button onClick={() => { setEditId(sys.id); setAdding(false); }} className="text-xs text-slate-400 hover:text-slate-700">✏</button>
                      <button onClick={() => setDelId(sys.id)} className="text-xs text-red-300 hover:text-red-600">✕</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      ))}
    </SectionWrap>
  );
}

function SystemForm({ item, saving, onSave, onCancel }: {
  item?: CVSystem; saving: boolean;
  onSave: (d: Partial<CVSystem>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({ name: item?.name ?? "", category: item?.category ?? "", proficiency: item?.proficiency ?? "intermediate" });
  const s = (k: string, v: unknown) => setD(p => ({ ...p, [k]: v }));
  return (
    <div className="space-y-3 rounded-lg border border-blue-100 bg-blue-50 p-3">
      <div className="grid grid-cols-3 gap-3">
        <F label="System" required><input className={I} value={d.name} onChange={e => s("name", e.target.value)} placeholder="Salesforce" /></F>
        <F label="Kategori"><input className={I} value={d.category} onChange={e => s("category", e.target.value)} placeholder="CRM" /></F>
        <F label="Niveau"><Sel value={d.proficiency} onChange={v => s("proficiency", v)} options={LEVEL_OPTS} /></F>
      </div>
      <FormFooter onSave={() => onSave(d)} onCancel={onCancel} saving={saving} />
    </div>
  );
}

// ── Leadership ────────────────────────────────────────────────────────────────

function LeadershipSection({ init }: { init: CVLeadership[] }) {
  const [items, setItems] = useState(init);
  const [editId, setEditId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setItems(init); }, [init]);

  async function create(d: Partial<CVLeadership>) {
    setSaving(true);
    try { const item = await apiPost<CVLeadership>("/profile/leadership", d); setItems(p => [...p, item]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function update(id: string, d: Partial<CVLeadership>) {
    setSaving(true);
    try { const item = await apiPut<CVLeadership>(`/profile/leadership/${id}`, d); setItems(p => p.map(i => i.id === id ? item : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function remove(id: string) {
    setSaving(true);
    try { await apiDelete(`/profile/leadership/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }
  async function move(id: string, dir: "up" | "down") {
    const idx = items.findIndex(i => i.id === id);
    const ni = dir === "up" ? idx - 1 : idx + 1;
    if (ni < 0 || ni >= items.length) return;
    const n = [...items]; [n[idx], n[ni]] = [n[ni], n[idx]]; setItems(n);
    await Promise.all([
      apiPut(`/profile/leadership/${n[idx].id}`, { sort_order: idx }),
      apiPut(`/profile/leadership/${n[ni].id}`, { sort_order: ni }),
    ]).catch(() => setItems(items));
  }

  return (
    <SectionWrap title="Lederskab" onAdd={() => { setAdding(true); setEditId(null); }}>
      {adding && <Card padding="sm"><LeadershipForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!items.length && !adding && <Empty label="lederskabserfaring" />}
      {items.map((l, idx) => (
        <div key={l.id}>
          {delId === l.id ? (
            <DeletePrompt onConfirm={() => remove(l.id)} onCancel={() => setDelId(null)} />
          ) : editId === l.id ? (
            <Card padding="sm"><LeadershipForm item={l} saving={saving} onSave={d => update(l.id, d)} onCancel={() => setEditId(null)} /></Card>
          ) : (
            <Card padding="sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-900">{l.title}</p>
                  {l.scope && <p className="text-sm text-slate-500">{l.scope}</p>}
                  {l.direct_reports != null && l.direct_reports > 0 && (
                    <p className="mt-1 text-sm text-slate-600"><span className="font-medium">{l.direct_reports}</span> direkte rapporterende</p>
                  )}
                  {l.responsibilities?.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {l.responsibilities.map((r, i) => (
                        <li key={i} className="flex gap-2 text-sm text-slate-600"><span className="text-blue-500">·</span>{r}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <ItemActions
                  onEdit={() => { setEditId(l.id); setAdding(false); }} onDelete={() => setDelId(l.id)}
                  onUp={() => move(l.id, "up")} onDown={() => move(l.id, "down")} first={idx === 0} last={idx === items.length - 1}
                />
              </div>
            </Card>
          )}
        </div>
      ))}
    </SectionWrap>
  );
}

function LeadershipForm({ item, saving, onSave, onCancel }: {
  item?: CVLeadership; saving: boolean;
  onSave: (d: Partial<CVLeadership>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({
    title: item?.title ?? "", scope: item?.scope ?? "",
    direct_reports: item?.direct_reports?.toString() ?? "",
    responsibilities: (item?.responsibilities ?? []).join("\n"),
  });
  const s = (k: string, v: unknown) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({
    ...d,
    direct_reports: d.direct_reports ? parseInt(d.direct_reports) : null,
    responsibilities: d.responsibilities.split("\n").map(x => x.trim()).filter(Boolean),
  });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <F label="Titel" required><input className={I} value={d.title} onChange={e => s("title", e.target.value)} placeholder="Engineering Manager" /></F>
        <F label="Omfang"><input className={I} value={d.scope} onChange={e => s("scope", e.target.value)} placeholder="Backend platform team" /></F>
      </div>
      <F label="Direkte rapporterende">
        <input type="number" className={I} value={d.direct_reports} onChange={e => s("direct_reports", e.target.value)} placeholder="8" min="0" />
      </F>
      <F label="Ansvarsområder (én per linje)">
        <textarea className={I + " resize-none"} rows={3} value={d.responsibilities} onChange={e => s("responsibilities", e.target.value)}
          placeholder={"Rekruttering og onboarding af ingeniører\nTeknisk vejledning og code reviews\nKvartalsplanlægning og roadmap"} />
      </F>
      <FormFooter onSave={() => onSave(payload())} onCancel={onCancel} saving={saving} />
    </div>
  );
}

// ── Certifications ────────────────────────────────────────────────────────────

function CertificationsSection({ init }: { init: CVCertification[] }) {
  const [items, setItems] = useState(init);
  const [editId, setEditId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [delId, setDelId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setItems(init); }, [init]);

  async function create(d: Partial<CVCertification>) {
    setSaving(true);
    try { const item = await apiPost<CVCertification>("/profile/certifications", d); setItems(p => [...p, item]); setAdding(false); }
    finally { setSaving(false); }
  }
  async function update(id: string, d: Partial<CVCertification>) {
    setSaving(true);
    try { const item = await apiPut<CVCertification>(`/profile/certifications/${id}`, d); setItems(p => p.map(i => i.id === id ? item : i)); setEditId(null); }
    finally { setSaving(false); }
  }
  async function remove(id: string) {
    setSaving(true);
    try { await apiDelete(`/profile/certifications/${id}`); setItems(p => p.filter(i => i.id !== id)); setDelId(null); }
    finally { setSaving(false); }
  }
  async function move(id: string, dir: "up" | "down") {
    const idx = items.findIndex(i => i.id === id);
    const ni = dir === "up" ? idx - 1 : idx + 1;
    if (ni < 0 || ni >= items.length) return;
    const n = [...items]; [n[idx], n[ni]] = [n[ni], n[idx]]; setItems(n);
    await Promise.all([
      apiPut(`/profile/certifications/${n[idx].id}`, { sort_order: idx }),
      apiPut(`/profile/certifications/${n[ni].id}`, { sort_order: ni }),
    ]).catch(() => setItems(items));
  }

  return (
    <SectionWrap title="Certifikater" onAdd={() => { setAdding(true); setEditId(null); }}>
      {adding && <Card padding="sm"><CertificationForm saving={saving} onSave={create} onCancel={() => setAdding(false)} /></Card>}
      {!items.length && !adding && <Empty label="certifikater" />}
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((c, idx) => (
          <div key={c.id}>
            {delId === c.id ? (
              <DeletePrompt onConfirm={() => remove(c.id)} onCancel={() => setDelId(null)} />
            ) : editId === c.id ? (
              <Card padding="sm"><CertificationForm item={c} saving={saving} onSave={d => update(c.id, d)} onCancel={() => setEditId(null)} /></Card>
            ) : (
              <Card padding="sm">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-900">{c.name}</p>
                    {c.issuer && <p className="text-sm text-slate-500">{c.issuer}</p>}
                    <div className="mt-1 flex gap-3 text-xs text-slate-400">
                      {c.issued_at && <span>Udstedt: {formatDate(c.issued_at)}</span>}
                      {c.expires_at && <span>Udløber: {formatDate(c.expires_at)}</span>}
                    </div>
                  </div>
                  <ItemActions
                    onEdit={() => { setEditId(c.id); setAdding(false); }} onDelete={() => setDelId(c.id)}
                    onUp={() => move(c.id, "up")} onDown={() => move(c.id, "down")} first={idx === 0} last={idx === items.length - 1}
                  />
                </div>
              </Card>
            )}
          </div>
        ))}
      </div>
    </SectionWrap>
  );
}

function CertificationForm({ item, saving, onSave, onCancel }: {
  item?: CVCertification; saving: boolean;
  onSave: (d: Partial<CVCertification>) => void; onCancel: () => void;
}) {
  const [d, setD] = useState({
    name: item?.name ?? "", issuer: item?.issuer ?? "",
    issued_at: item?.issued_at?.slice(0, 10) ?? "", expires_at: item?.expires_at?.slice(0, 10) ?? "",
  });
  const s = (k: string, v: unknown) => setD(p => ({ ...p, [k]: v }));
  const payload = () => ({ ...d, issued_at: d.issued_at || null, expires_at: d.expires_at || null });
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <F label="Certifikat" required><input className={I} value={d.name} onChange={e => s("name", e.target.value)} placeholder="AWS Solutions Architect" /></F>
        <F label="Udsteder"><input className={I} value={d.issuer} onChange={e => s("issuer", e.target.value)} placeholder="Amazon Web Services" /></F>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <F label="Udstedt"><input type="date" className={I} value={d.issued_at} onChange={e => s("issued_at", e.target.value)} /></F>
        <F label="Udløber"><input type="date" className={I} value={d.expires_at} onChange={e => s("expires_at", e.target.value)} /></F>
      </div>
      <FormFooter onSave={() => onSave(payload())} onCancel={onCancel} saving={saving} />
    </div>
  );
}
