"use client";

import { useRef, useState } from "react";
import { apiGet, apiPost, apiStream } from "@/lib/api";
import { createClient } from "@/lib/supabase";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// ── Local API helpers ─────────────────────────────────────────────────────────

const _apiBase = () =>
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");

async function _authHeader(): Promise<Record<string, string>> {
  const { data } = await createClient().auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function multiUpload<T>(path: string, form: FormData): Promise<T> {
  const headers = await _authHeader();
  const res = await fetch(`${_apiBase()}/api/v1${path}`, { method: "POST", headers, body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let detail = text;
    try { detail = (JSON.parse(text) as { detail?: string }).detail ?? text; } catch { /* raw */ }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function downloadBlob(path: string, filename: string) {
  const headers = await _authHeader();
  const res = await fetch(`${_apiBase()}/api/v1${path}`, { headers });
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface CoachResult { content: string; analysis_type: string; language: string; profile_summary?: { target_title?: string; skills_count: number; experience_count: number; goals_count: number }; }
interface ChatMsg { role: "user" | "assistant"; content: string; streaming?: boolean; }

// ── Markdown renderer ─────────────────────────────────────────────────────────

function MD({ content }: { content: string }) {
  return (
    <div className="space-y-0.5">
      {content.split("\n").map((line, i) => {
        const t = line.trim();
        if (t.startsWith("## ")) return <h2 key={i} className="mt-5 mb-2 text-base font-semibold text-blue-700">{t.slice(3)}</h2>;
        if (t.startsWith("# ")) return <h1 key={i} className="mt-4 mb-2 text-lg font-bold text-slate-900">{t.slice(2)}</h1>;
        if (t.startsWith("- ") || t.startsWith("• ")) return (
          <div key={i} className="flex items-start gap-2 py-0.5">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
            <span className="text-sm text-slate-700">{t.slice(2)}</span>
          </div>
        );
        if (t === "" || t === "---") return <div key={i} className="h-2" />;
        if (t.startsWith("**") && t.endsWith("**")) return <p key={i} className="py-0.5 text-sm font-semibold text-slate-800">{t.slice(2, -2)}</p>;
        return <p key={i} className="py-0.5 text-sm text-slate-700">{t}</p>;
      })}
    </div>
  );
}

// ── Shared components ─────────────────────────────────────────────────────────

function FileInput({ label, name, required, onChange }: { label: string; name: string; required?: boolean; onChange?: (f: File | null) => void }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}{required && " *"}</label>
      <input
        type="file"
        name={name}
        accept=".pdf,.docx,.doc,.txt"
        className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-blue-50 file:px-3 file:py-1 file:text-xs file:font-medium file:text-blue-700"
        onChange={e => onChange?.(e.target.files?.[0] ?? null)}
      />
      <p className="mt-1 text-xs text-slate-400">PDF, DOCX eller TXT • max 10 MB</p>
    </div>
  );
}

function Err({ msg }: { msg: string }) {
  const text = msg.includes("402") || msg.includes("no_api_key")
    ? "Ingen API-nøgle konfigureret — gå til Indstillinger → API-nøgler."
    : msg.includes("422") ? "Profilen er for tom — upload dit CV og udfyld profilen først." : msg;
  return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{text}</div>;
}

function ResultCard({ content, onRegen }: { content: string; onRegen?: () => void }) {
  return (
    <Card>
      {onRegen && <div className="mb-3 flex justify-end"><button onClick={onRegen} className="text-xs text-blue-600 hover:text-blue-700">Generer ny ↺</button></div>}
      <MD content={content} />
      <p className="mt-4 rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">
        Dette er vejledende analyse og ikke juridisk rådgivning.
      </p>
    </Card>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-16 text-center">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 text-slate-300"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/><path d="M12 8v4l3 3"/></svg>
      <p className="font-medium text-slate-500">{text}</p>
    </div>
  );
}

// ── SSE Chat helper ───────────────────────────────────────────────────────────

async function runChat(
  path: string,
  body: unknown,
  onChunk: (c: string) => void,
  onDone: () => void,
  onError: (e: string) => void,
) {
  await apiStream(path, body, onChunk, onDone, onError);
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 1 — Karriereanalyse
// ═══════════════════════════════════════════════════════════════════════════════

const ANALYSES = [
  { id: "full", label: "Komplet analyse", desc: "Styrker, gaps, karrierevej og handlingsplan" },
  { id: "skills_gap", label: "Kompetencegap", desc: "Vigtigste manglende kompetencer" },
  { id: "career_path", label: "Karrierevej", desc: "Realistiske næste roller" },
  { id: "next_steps", label: "Næste skridt", desc: "5 handlinger de næste 30 dage" },
];

function TabKarriereanalyse() {
  const [type, setType] = useState("full");
  const [lang, setLang] = useState("da");
  const [targetRole, setTargetRole] = useState("");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CoachResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await apiPost<CoachResult>("/career-coach/analyze", { analysis_type: type, language: lang, target_role: targetRole || undefined, question: question || undefined });
      setResult(res);
    } catch (e) { setError(e instanceof Error ? e.message : "Fejlede"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {ANALYSES.map(a => (
          <button key={a.id} onClick={() => setType(a.id)}
            className={`rounded-xl border p-4 text-left transition-all ${type === a.id ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500" : "border-slate-200 bg-white hover:border-blue-200"}`}>
            <p className={`text-sm font-medium ${type === a.id ? "text-blue-700" : "text-slate-700"}`}>{a.label}</p>
            <p className="mt-0.5 text-xs text-slate-400">{a.desc}</p>
          </button>
        ))}
      </div>
      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Sprog</label>
            <select className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm" value={lang} onChange={e => setLang(e.target.value)}>
              <option value="da">Dansk</option><option value="en">English</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Målrolle (valgfri)</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="Engineering Manager, CTO…" value={targetRole} onChange={e => setTargetRole(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Dit spørgsmål (valgfri)</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="Hvad skal jeg fokusere på nu?" value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => e.key === "Enter" && run()} />
          </div>
        </div>
        <div className="mt-4 flex justify-end"><Button loading={loading} onClick={run}>{loading ? "Analyserer…" : "Kør analyse"}</Button></div>
      </Card>
      {error && <Err msg={error} />}
      {result && (
        <div className="space-y-4">
          {result.profile_summary && (
            <div className="flex flex-wrap gap-3">
              {result.profile_summary.target_title && <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">{result.profile_summary.target_title}</span>}
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{result.profile_summary.skills_count} kompetencer</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{result.profile_summary.experience_count} erfaringer</span>
            </div>
          )}
          <ResultCard content={result.content} onRegen={run} />
        </div>
      )}
      {!result && !loading && !error && <EmptyState text='Vælg analysetype og klik "Kør analyse"' />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 2 — Løntjek
// ═══════════════════════════════════════════════════════════════════════════════

function TabLoentjek() {
  const [form, setForm] = useState({ title: "", industry: "", location: "", company: "", experience_years: "", education: "", management_responsibility: false, budget_responsibility: "", team_size: "", current_salary: "", pension: "", bonus: "", benefits: "" });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const set = (k: string, v: string | boolean) => setForm(f => ({ ...f, [k]: v }));

  async function run() {
    if (!form.title) { setError("Jobtitel er påkrævet."); return; }
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await apiPost<{ content: string }>("/labor-coach/salary-check", form);
      setResult(res.content);
    } catch (e) { setError(e instanceof Error ? e.message : "Fejlede"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">Analyser dit lønniveau mod markedet. Angiv stillingsprofil og nuværende kompensation.</p>
      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Jobtitel *</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="Software Engineer, Controller, HR Manager…" value={form.title} onChange={e => set("title", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Branche</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="IT, Finans, Detail, Sundhed…" value={form.industry} onChange={e => set("industry", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Lokation</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="København, Aarhus, Odense…" value={form.location} onChange={e => set("location", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Virksomhed</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="Virksomhedens navn (valgfri)" value={form.company} onChange={e => set("company", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Erfaring (år)</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="5" value={form.experience_years} onChange={e => set("experience_years", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Uddannelse</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="Cand.merc., Bachelor, Professionsbachelor…" value={form.education} onChange={e => set("education", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Budgetansvar</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="5 mio. DKK, 2 afdelinger…" value={form.budget_responsibility} onChange={e => set("budget_responsibility", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Antal medarbejdere</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="10 direkte, 50 indirekte…" value={form.team_size} onChange={e => set("team_size", e.target.value)} />
          </div>
        </div>
        <div className="mt-3">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={form.management_responsibility} onChange={e => set("management_responsibility", e.target.checked)} className="rounded" />
            Ledelsesansvar (personaleleder)
          </label>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Nuværende løn (DKK/md)</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="55.000" value={form.current_salary} onChange={e => set("current_salary", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Pension</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="12%, 4.000/md…" value={form.pension} onChange={e => set("pension", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Bonus</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="10% af årsløn, 50.000/år…" value={form.bonus} onChange={e => set("bonus", e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Personalegoder</label>
            <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="Fri bil, sundhedsforsikring, kantine…" value={form.benefits} onChange={e => set("benefits", e.target.value)} />
          </div>
        </div>
        <div className="mt-4 flex justify-end"><Button loading={loading} onClick={run}>{loading ? "Analyserer…" : "Analyser løn"}</Button></div>
      </Card>
      {error && <Err msg={error} />}
      {result && <ResultCard content={result} onRegen={run} />}
      {!result && !loading && !error && <EmptyState text="Udfyld stillingsprofilen og klik Analyser løn" />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 3 — Karriereværdi
// ═══════════════════════════════════════════════════════════════════════════════

function TabKarrierevaerdi() {
  const [currentSalary, setCurrentSalary] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ content: string; profile_summary?: CoachResult["profile_summary"] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await apiGet<typeof result>(`/labor-coach/career-value${currentSalary ? `?current_salary=${encodeURIComponent(currentSalary)}` : ""}`);
      setResult(res);
    } catch (e) { setError(e instanceof Error ? e.message : "Fejlede"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">AI beregner din markedsværdi baseret på karriereprofil, kompetencer, erfaring og resultater.</p>
      <Card>
        <div className="max-w-xs">
          <label className="mb-1 block text-xs font-medium text-slate-600">Nuværende løn (valgfri, DKK/md)</label>
          <input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="55.000" value={currentSalary} onChange={e => setCurrentSalary(e.target.value)} />
          <p className="mt-1 text-xs text-slate-400">Bruges til at beregne forskel til markedsværdi</p>
        </div>
        <div className="mt-4 flex justify-end"><Button loading={loading} onClick={run}>{loading ? "Beregner…" : "Beregn karriereværdi"}</Button></div>
      </Card>
      {error && <Err msg={error} />}
      {result && (
        <div className="space-y-4">
          {result.profile_summary && (
            <div className="flex flex-wrap gap-3">
              {result.profile_summary.target_title && <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">{result.profile_summary.target_title}</span>}
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{result.profile_summary.skills_count} kompetencer</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{result.profile_summary.experience_count} erfaringer</span>
            </div>
          )}
          <ResultCard content={result.content} onRegen={run} />
        </div>
      )}
      {!result && !loading && !error && <EmptyState text="Klik Beregn karriereværdi for at se din markedsværdi" />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 4 — Kontrakt
// ═══════════════════════════════════════════════════════════════════════════════

function TabKontrakt() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!file) { setError("Vælg en kontraktfil."); return; }
    setLoading(true); setError(null); setResult(null);
    try {
      const fd = new FormData(); fd.append("file", file);
      const res = await multiUpload<{ content: string }>("/labor-coach/contract-analysis", fd);
      setResult(res.content);
    } catch (e) { setError(e instanceof Error ? e.message : "Fejlede"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">Upload din ansættelseskontrakt. AI analyserer løn, klausuler, risici og usædvanlige vilkår.</p>
      <Card>
        <FileInput label="Ansættelseskontrakt" name="file" required onChange={setFile} />
        <div className="mt-4 flex justify-end"><Button loading={loading} onClick={run} disabled={!file}>{loading ? "Analyserer…" : "Analyser kontrakt"}</Button></div>
      </Card>
      {error && <Err msg={error} />}
      {result && <ResultCard content={result} onRegen={run} />}
      {!result && !loading && !error && <EmptyState text="Upload din kontrakt og klik Analyser" />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 5 — Overenskomst
// ═══════════════════════════════════════════════════════════════════════════════

function TabOverenskomst() {
  const [contractFile, setContractFile] = useState<File | null>(null);
  const [agreementFile, setAgreementFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"identify" | "analyze">("identify");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!contractFile) { setError("Upload mindst din kontrakt."); return; }
    setLoading(true); setError(null); setResult(null);
    try {
      const fd = new FormData();
      fd.append("contract_file", contractFile);
      if (agreementFile) fd.append("agreement_file", agreementFile);
      fd.append("mode", mode);
      const res = await multiUpload<{ content: string }>("/labor-coach/agreement-analysis", fd);
      setResult(res.content);
    } catch (e) { setError(e instanceof Error ? e.message : "Fejlede"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">AI identificerer din overenskomst fra kontrakten og analyserer dine rettigheder.</p>
      <Card>
        <div className="mb-4 flex gap-3">
          {([["identify", "Identificer overenskomst"], ["analyze", "Analyser overenskomst"]] as const).map(([v, l]) => (
            <button key={v} onClick={() => setMode(v)} className={`rounded-lg border px-4 py-2 text-sm font-medium transition-all ${mode === v ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-600 hover:border-blue-200"}`}>{l}</button>
          ))}
        </div>
        <div className="space-y-4">
          <FileInput label={mode === "identify" ? "Ansættelseskontrakt *" : "Overenskomst eller kontrakt *"} name="contract_file" required onChange={setContractFile} />
          <FileInput label="Overenskomst (valgfri — forbedrer analysen)" name="agreement_file" onChange={setAgreementFile} />
        </div>
        <div className="mt-4 flex justify-end">
          <Button loading={loading} onClick={run} disabled={!contractFile}>
            {loading ? "Analyserer…" : mode === "identify" ? "Identificer overenskomst" : "Analyser overenskomst"}
          </Button>
        </div>
      </Card>
      {error && <Err msg={error} />}
      {result && <ResultCard content={result} onRegen={run} />}
      {!result && !loading && !error && <EmptyState text="Upload din kontrakt og klik Analyser" />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 6 — Lønseddel
// ═══════════════════════════════════════════════════════════════════════════════

function TabLoenseddel() {
  const [payslipFile, setPayslipFile] = useState<File | null>(null);
  const [contractFile, setContractFile] = useState<File | null>(null);
  const [agreementFile, setAgreementFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!payslipFile) { setError("Upload din lønseddel."); return; }
    setLoading(true); setError(null); setResult(null);
    try {
      const fd = new FormData();
      fd.append("payslip_file", payslipFile);
      if (contractFile) fd.append("contract_file", contractFile);
      if (agreementFile) fd.append("agreement_file", agreementFile);
      const res = await multiUpload<{ content: string }>("/labor-coach/payslip-check", fd);
      setResult(res.content);
    } catch (e) { setError(e instanceof Error ? e.message : "Fejlede"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">AI kontrollerer din lønseddel og sammenholder med din kontrakt og overenskomst.</p>
      <Card>
        <div className="space-y-4">
          <FileInput label="Lønseddel *" name="payslip_file" required onChange={setPayslipFile} />
          <FileInput label="Ansættelseskontrakt (valgfri — forbedrer analysen)" name="contract_file" onChange={setContractFile} />
          <FileInput label="Overenskomst (valgfri — forbedrer analysen)" name="agreement_file" onChange={setAgreementFile} />
        </div>
        <div className="mt-4 flex justify-end"><Button loading={loading} onClick={run} disabled={!payslipFile}>{loading ? "Kontrollerer…" : "Kontroller lønseddel"}</Button></div>
      </Card>
      {error && <Err msg={error} />}
      {result && <ResultCard content={result} onRegen={run} />}
      {!result && !loading && !error && <EmptyState text="Upload din lønseddel og klik Kontroller" />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 7 — Arbejdstid
// ═══════════════════════════════════════════════════════════════════════════════

function TabArbejdstid() {
  const [scheduleFile, setScheduleFile] = useState<File | null>(null);
  const [agreementFile, setAgreementFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!scheduleFile) { setError("Upload din vagtplan eller timeseddel."); return; }
    setLoading(true); setError(null); setResult(null);
    try {
      const fd = new FormData();
      fd.append("schedule_file", scheduleFile);
      if (agreementFile) fd.append("agreement_file", agreementFile);
      const res = await multiUpload<{ content: string }>("/labor-coach/worktime-check", fd);
      setResult(res.content);
    } catch (e) { setError(e instanceof Error ? e.message : "Fejlede"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">AI analyserer din vagtplan for overtid, hviletid og tillæg du muligvis har ret til.</p>
      <Card>
        <div className="space-y-4">
          <FileInput label="Vagtplan eller timeseddel *" name="schedule_file" required onChange={setScheduleFile} />
          <FileInput label="Overenskomst (valgfri — forbedrer analysen)" name="agreement_file" onChange={setAgreementFile} />
        </div>
        <div className="mt-4 flex justify-end"><Button loading={loading} onClick={run} disabled={!scheduleFile}>{loading ? "Analyserer…" : "Analyser arbejdstid"}</Button></div>
      </Card>
      {error && <Err msg={error} />}
      {result && <ResultCard content={result} onRegen={run} />}
      {!result && !loading && !error && <EmptyState text="Upload din vagtplan og klik Analyser" />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 8 — Lønforhandling
// ═══════════════════════════════════════════════════════════════════════════════

function TabLoenforhandling() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [currentSalary, setCurrentSalary] = useState("");
  const [targetSalary, setTargetSalary] = useState("");
  const [minSalary, setMinSalary] = useState("");
  const [marketSalary, setMarketSalary] = useState("");
  const [chatStarted, setChatStarted] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [package_, setPackage] = useState<{ text: string; a4: string; sessionId: string } | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const accRef = useRef("");

  async function startChat() {
    setChatStarted(true); setError(null); setMessages([]);
    await sendToApi([]);
  }

  async function sendToApi(msgs: ChatMsg[]) {
    setStreaming(true);
    accRef.current = "";
    setMessages(prev => [...prev, { role: "assistant", content: "", streaming: true }]);
    await runChat(
      "/labor-coach/salary-prep/chat",
      { messages: msgs, current_salary: currentSalary, target_salary: targetSalary },
      (chunk) => {
        accRef.current += chunk;
        setMessages(prev => { const c = [...prev]; c[c.length - 1] = { role: "assistant", content: accRef.current, streaming: true }; return c; });
      },
      () => {
        setStreaming(false);
        setMessages(prev => { const c = [...prev]; c[c.length - 1] = { ...c[c.length - 1], streaming: false }; return c; });
        setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
      },
      (e) => { setError(e); setStreaming(false); },
    );
  }

  async function send() {
    if (!input.trim() || streaming) return;
    const userMsg: ChatMsg = { role: "user", content: input.trim() };
    const newMsgs = [...messages, userMsg];
    setMessages(newMsgs); setInput("");
    await sendToApi(newMsgs);
  }

  async function generatePackage() {
    setGenerating(true); setError(null);
    try {
      const res = await apiPost<{ package_text: string; package_a4_text: string; session_id: string }>("/labor-coach/salary-prep/generate", { messages, current_salary: currentSalary, target_salary: targetSalary, min_salary: minSalary, market_salary: marketSalary });
      setPackage({ text: res.package_text, a4: res.package_a4_text, sessionId: res.session_id });
    } catch (e) { setError(e instanceof Error ? e.message : "Fejlede"); }
    finally { setGenerating(false); }
  }

  async function dl(doc: "package" | "a4", fmt: "pdf" | "docx") {
    if (!package_) return;
    await downloadBlob(`/labor-coach/salary-prep/${package_.sessionId}/${fmt}?doc=${doc}`, `Loenssamtale_${doc}.${fmt}`);
  }

  if (package_) {
    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-slate-900 mr-auto">Lønsamtalepakke</h2>
          <button onClick={() => dl("a4", "pdf")} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">A4 PDF</button>
          <button onClick={() => dl("a4", "docx")} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50">A4 DOCX</button>
          <button onClick={() => dl("package", "pdf")} className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100">Pakke PDF</button>
          <button onClick={() => dl("package", "docx")} className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100">Pakke DOCX</button>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          <Card><h3 className="mb-3 font-medium text-slate-800">A4-side til mødet</h3><div className="max-h-96 overflow-y-auto"><MD content={package_.a4} /></div></Card>
          <Card><h3 className="mb-3 font-medium text-slate-800">Komplet pakke</h3><div className="max-h-96 overflow-y-auto"><MD content={package_.text} /></div></Card>
        </div>
        <button onClick={() => { setPackage(null); setChatStarted(false); setMessages([]); }} className="text-sm text-blue-600 hover:text-blue-700">← Start forfra</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">AI coachen interviewer dig om resultater og forbereder en komplet lønsamtalepakke med A4-side til mødet.</p>
      {!chatStarted ? (
        <Card>
          <p className="mb-4 text-sm font-medium text-slate-700">Lønmål (valgfri)</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div><label className="mb-1 block text-xs font-medium text-slate-600">Nuværende løn (DKK/md)</label><input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="55.000" value={currentSalary} onChange={e => setCurrentSalary(e.target.value)} /></div>
            <div><label className="mb-1 block text-xs font-medium text-slate-600">Målløn (DKK/md)</label><input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="65.000" value={targetSalary} onChange={e => setTargetSalary(e.target.value)} /></div>
            <div><label className="mb-1 block text-xs font-medium text-slate-600">Minimumsmål (DKK/md)</label><input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="60.000" value={minSalary} onChange={e => setMinSalary(e.target.value)} /></div>
            <div><label className="mb-1 block text-xs font-medium text-slate-600">Markedsløn estimat (DKK/md)</label><input className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="62.000" value={marketSalary} onChange={e => setMarketSalary(e.target.value)} /></div>
          </div>
          <div className="mt-5 flex justify-end"><Button onClick={startChat}>Start lønsamtale-forberedelse</Button></div>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="min-h-64 max-h-[480px] overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${m.role === "user" ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-800"}`}>
                  {m.content || (m.streaming ? <span className="animate-pulse">…</span> : "")}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <div className="flex gap-2">
            <input className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm" placeholder="Skriv dit svar…" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()} disabled={streaming} />
            <Button onClick={send} disabled={streaming || !input.trim()}>Send</Button>
          </div>
          {messages.filter(m => m.role === "user").length >= 2 && !streaming && (
            <div className="flex justify-center">
              <Button loading={generating} onClick={generatePackage}>
                {generating ? "Genererer pakke…" : "Generer lønsamtalepakke"}
              </Button>
            </div>
          )}
          {error && <Err msg={error} />}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB 9 — Fagforeningsassistent
// ═══════════════════════════════════════════════════════════════════════════════

function TabFagforening() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const accRef = useRef("");

  const STARTERS = [
    "Hvad er mine rettigheder ved opsigelse?",
    "Hvad er en konkurrenceklausul og hvornår er den gyldig?",
    "Hvad dækker SH-betaling og fritvalg?",
    "Hvad er mine rettigheder ved barsel?",
    "Hvad kan jeg gøre hvis min løn ikke er korrekt?",
  ];

  async function send(msg?: string) {
    const content = msg ?? input.trim();
    if (!content || streaming) return;
    const userMsg: ChatMsg = { role: "user", content };
    const newMsgs = [...messages, userMsg];
    setMessages(newMsgs); setInput(""); setStreaming(true); accRef.current = "";
    setMessages(prev => [...prev, { role: "assistant", content: "", streaming: true }]);
    await runChat(
      "/labor-coach/labor-rights",
      { messages: newMsgs },
      (chunk) => {
        accRef.current += chunk;
        setMessages(prev => { const c = [...prev]; c[c.length - 1] = { role: "assistant", content: accRef.current, streaming: true }; return c; });
      },
      () => {
        setStreaming(false);
        setMessages(prev => { const c = [...prev]; c[c.length - 1] = { ...c[c.length - 1], streaming: false }; return c; });
        setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
      },
      (e) => { setError(e); setStreaming(false); },
    );
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">Spørg om dine arbejdsretlige rettigheder, overenskomster, kontrakter og lønsedler. Al information er vejledende.</p>
      {messages.length === 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {STARTERS.map(s => (
            <button key={s} onClick={() => send(s)} className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 hover:border-blue-200 hover:bg-blue-50 transition-colors">{s}</button>
          ))}
        </div>
      )}
      <div className="min-h-64 max-h-[480px] overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
        {messages.length === 0 && <p className="text-center text-sm text-slate-400 pt-8">Vælg et spørgsmål ovenfor eller skriv dit eget</p>}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${m.role === "user" ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-800"}`}>
              {m.content || (m.streaming ? <span className="animate-pulse">…</span> : "")}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
      <div className="flex gap-2">
        <input className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm" placeholder="Stil dit spørgsmål om arbejdsret…" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()} disabled={streaming} />
        <Button onClick={() => send()} disabled={streaming || !input.trim()}>Send</Button>
      </div>
      {messages.length > 0 && <button onClick={() => setMessages([])} className="text-xs text-slate-400 hover:text-slate-600">Ryd samtale</button>}
      {error && <Err msg={error} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE — Tab navigation
// ═══════════════════════════════════════════════════════════════════════════════

const TABS = [
  { id: "karriere", label: "Karriereanalyse", component: TabKarriereanalyse },
  { id: "loen", label: "Løntjek", component: TabLoentjek },
  { id: "vaerdi", label: "Karriereværdi", component: TabKarrierevaerdi },
  { id: "kontrakt", label: "Kontrakt", component: TabKontrakt },
  { id: "overenskomst", label: "Overenskomst", component: TabOverenskomst },
  { id: "loenseddel", label: "Lønseddel", component: TabLoenseddel },
  { id: "arbejdstid", label: "Arbejdstid", component: TabArbejdstid },
  { id: "forhandling", label: "Lønforhandling", component: TabLoenforhandling },
  { id: "fagforening", label: "Fagforeningsassistent", component: TabFagforening },
];

export default function CareerCoachPage() {
  const [activeTab, setActiveTab] = useState("karriere");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Career Coach</h1>
        <p className="mt-1 text-sm text-slate-500">AI-karriererådgivning, løntjek og arbejdslivsassistance</p>
      </div>

      <div className="border-b border-slate-200">
        <div className="flex gap-0 overflow-x-auto scrollbar-hide">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`shrink-0 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                activeTab === t.id
                  ? "border-blue-600 text-blue-700"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {TABS.map(({ id, component: Tab }) => (
        <div key={id} className={activeTab === id ? undefined : "hidden"}>
          <Tab />
        </div>
      ))}
    </div>
  );
}
