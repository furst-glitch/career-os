"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiPut, apiStream } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CompletenessScore } from "@/components/CompletenessScore";
import { CvTemplateSelector, type CvTemplate } from "@/components/TemplateSelector";

// ── Types ─────────────────────────────────────────────────────────────────────

interface MasterCVContent {
  content: string;
  is_generated: boolean;
  language: "da" | "en";
  updated_at: string | null;
}

interface CVVersion {
  id: string;
  version_number: number;
  title: string;
  language: "da" | "en";
  generated_by: "user" | "ai" | "ai_assisted";
  created_at: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("da-DK", {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

// ── Page ─────────────────────────────────────────────────────────────────────

type ViewMode = "edit" | "preview";

export default function MasterCVPage() {
  const [content, setContent]       = useState("");
  const [language, setLanguage]     = useState<"da" | "en">("da");
  const [updatedAt, setUpdatedAt]   = useState<string | null>(null);
  const [loading, setLoading]       = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving]         = useState(false);
  const [savingVer, setSavingVer]   = useState(false);
  const [mode, setMode]             = useState<ViewMode>("edit");
  const [versions, setVersions]     = useState<CVVersion[]>([]);
  const [showVer, setShowVer]       = useState(false);
  const [loadingVer, setLoadingVer] = useState(false);
  const [toast, setToast]           = useState<{ msg: string; ok: boolean } | null>(null);
  const [copied, setCopied]         = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"pdf" | "docx" | null>(null);
  const [cvTemplate, setCvTemplate]   = useState<CvTemplate>("ats_professional");
  const [showTempl, setShowTempl]     = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadAll();
    // Load saved template preference
    apiGet<{ default_cv_template: string }>("/export/preferences")
      .then(p => { if (p.default_cv_template) setCvTemplate(p.default_cv_template as CvTemplate); })
      .catch(() => {});
  }, []);

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  }

  async function loadAll() {
    setLoading(true);
    try {
      const data = await apiGet<MasterCVContent>("/cv/master/content");
      setContent(data.content ?? "");
      setLanguage(data.language ?? "da");
      setUpdatedAt(data.updated_at ?? null);
    } catch {
      // Not yet generated — empty state
    } finally {
      setLoading(false);
    }
  }

  async function loadVersions() {
    setLoadingVer(true);
    try {
      const vers = await apiGet<CVVersion[]>("/cv/master/versions");
      setVersions(vers);
    } finally {
      setLoadingVer(false);
    }
  }

  async function generate() {
    setGenerating(true);
    setError(null);
    setContent("");
    setMode("edit");
    try {
      await apiStream(
        "/cv/master/generate",
        {},
        (chunk) => setContent(prev => prev + chunk),
        async () => {
          setGenerating(false);
          showToast("Master CV genereret og gemt automatisk");
          if (showVer) await loadVersions();
          try {
            const d = await apiGet<MasterCVContent>("/cv/master/content");
            setUpdatedAt(d.updated_at ?? null);
          } catch {}
        },
        (err) => { setError(err); setGenerating(false); }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generering mislykkedes");
      setGenerating(false);
    }
  }

  async function save() {
    if (!content.trim()) return;
    setSaving(true);
    try {
      await apiPut("/cv/master", { raw_content: content });
      const d = await apiGet<MasterCVContent>("/cv/master/content");
      setUpdatedAt(d.updated_at ?? null);
      showToast("Gemt");
    } catch {
      showToast("Kunne ikke gemme", false);
    } finally {
      setSaving(false);
    }
  }

  async function saveVersion() {
    if (!content.trim()) return;
    setSavingVer(true);
    try {
      await apiPut("/cv/master", { raw_content: content });
      const ver = await apiPost<CVVersion>("/cv/master/version");
      setVersions(prev => [ver, ...prev]);
      setShowVer(true);
      showToast(`Gemt som ${ver.title}`);
    } catch {
      showToast("Kunne ikke gemme version", false);
    } finally {
      setSavingVer(false);
    }
  }

  async function restoreVersion(verId: string, verTitle: string) {
    try {
      const data = await apiGet<{ content: string }>(`/cv/master/versions/${verId}`);
      setContent(data.content);
      setMode("edit");
      showToast(`Gendannet fra ${verTitle}`);
    } catch {
      showToast("Kunne ikke gendanne version", false);
    }
  }

  async function changeLanguage(lang: "da" | "en") {
    setLanguage(lang);
    try {
      await apiPut("/cv/master", { language: lang });
      showToast(
        lang === "da"
          ? "Sprog sat til dansk — regenerér for at oversætte"
          : "Language set to English — regenerate to translate"
      );
    } catch {}
  }

  async function copy() {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function toggleVersionHistory() {
    const next = !showVer;
    setShowVer(next);
    if (next && versions.length === 0) await loadVersions();
  }

  async function _downloadCv(format: "pdf" | "docx") {
    setDownloading(format);
    try {
      const { createClient } = await import("@/lib/supabase");
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      const base = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");
      const url = `${base}/api/v1/export/cv/${format}?template=${cvTemplate}`;
      const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!res.ok) { showToast("Download fejlede", false); return; }
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `master_cv_${cvTemplate}.${format}`;
      link.click();
      URL.revokeObjectURL(link.href);
      showToast(`CV downloadet som ${format.toUpperCase()}`);
    } finally {
      setDownloading(null);
    }
  }

  async function downloadCvPdf() { await _downloadCv("pdf"); }
  async function downloadCvDocx() { await _downloadCv("docx"); }

  // ── Loading ─────────────────────────────────────────────────────────────────

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

  // ── Layout ───────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full gap-6">
      {/* Toast notification */}
      {toast && (
        <div className={`fixed right-6 top-6 z-50 rounded-lg px-4 py-3 text-sm font-medium shadow-lg ${
          toast.ok ? "bg-green-600 text-white" : "bg-red-600 text-white"
        }`}>
          {toast.msg}
        </div>
      )}

      {/* ── Main editor area ── */}
      <div className="flex min-w-0 flex-1 flex-col">

        {/* Header */}
        <div className="mb-5 flex flex-wrap items-start gap-3">
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-slate-900">Master CV</h1>
            <p className="mt-1 text-sm text-slate-500">
              Genereret af AI — redigér direkte, gem versioner, skift sprog
              {updatedAt && (
                <span className="ml-2 text-slate-400">· Sidst opdateret {fmtDate(updatedAt)}</span>
              )}
            </p>
          </div>

          {/* Action toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Language toggle */}
            <div className="flex overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
              {(["da", "en"] as const).map(lang => (
                <button key={lang} onClick={() => changeLanguage(lang)}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                    language === lang ? "bg-white text-slate-900 shadow-sm" : "text-slate-400 hover:text-slate-700"
                  }`}>
                  {lang.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Edit / Preview toggle */}
            {content && (
              <div className="flex overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                {(["edit", "preview"] as const).map(m => (
                  <button key={m} onClick={() => setMode(m)}
                    className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                      mode === m ? "bg-white text-slate-900 shadow-sm" : "text-slate-400 hover:text-slate-700"
                    }`}>
                    {m === "edit" ? "Rediger" : "Preview"}
                  </button>
                ))}
              </div>
            )}

            {content && (
              <Button variant="outline" size="sm" loading={savingVer} onClick={saveVersion}>
                Gem version
              </Button>
            )}
            {content && (
              <Button variant="outline" size="sm" onClick={copy}>
                {copied ? "Kopieret!" : "Kopiér"}
              </Button>
            )}
            {content && (
              <Button variant="outline" size="sm" onClick={() => setShowTempl(true)}>
                Download ↓
              </Button>
            )}
            {content && (
              <Button variant="secondary" size="sm" loading={saving} onClick={save}>
                Gem
              </Button>
            )}
            <Button onClick={generate} loading={generating}>
              {content ? "Regenerér" : "Generér Master CV"}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Empty state */}
        {!content && !generating && (
          <Card className="flex flex-1 flex-col items-center justify-center gap-4 py-16">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-50">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
            </div>
            <div className="text-center">
              <p className="font-medium text-slate-900">Intet Master CV endnu</p>
              <p className="mt-1 text-sm text-slate-500">
                Klik &quot;Generér Master CV&quot; — AI bygger dit CV fra din kandidatprofil
              </p>
            </div>
            <Button onClick={generate} size="lg">Generér Master CV</Button>
          </Card>
        )}

        {/* Streaming indicator */}
        {generating && (
          <div className="mb-3 flex items-center gap-2 text-sm text-blue-600">
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            AI genererer{language === "en" ? " in English" : ""}…
          </div>
        )}

        {/* Edit textarea */}
        {(content || generating) && mode === "edit" && (
          <div className="flex flex-1 flex-col">
            <textarea
              ref={textareaRef}
              value={content}
              onChange={e => setContent(e.target.value)}
              disabled={generating}
              className="flex-1 rounded-xl border border-slate-200 bg-white p-6 font-mono text-sm text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-slate-50"
              spellCheck={false}
              style={{ minHeight: 600, resize: "vertical" }}
            />
            {content && !generating && (
              <div className="mt-3 flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={copy}>{copied ? "Kopieret!" : "Kopiér alt"}</Button>
                <Button variant="secondary" size="sm" loading={saving} onClick={save}>Gem</Button>
                <Button size="sm" loading={generating} onClick={generate}>Regenerér</Button>
              </div>
            )}
          </div>
        )}

        {/* Preview mode */}
        {content && mode === "preview" && (
          <div
            className="flex-1 overflow-auto rounded-xl border border-slate-200 bg-white p-8 text-sm leading-relaxed text-slate-800"
            style={{ minHeight: 600, whiteSpace: "pre-wrap", fontFamily: "Georgia, serif" }}
          >
            {content}
          </div>
        )}
      </div>

      {/* ── Right sidebar ── */}
      <aside className="w-64 shrink-0 space-y-4">
        <div className="sticky top-0 space-y-4">
          {/* Completeness score */}
          <div className="rounded-xl border border-slate-200 bg-slate-900 p-4">
            <h2 className="mb-4 text-sm font-semibold text-slate-200">Profil fuldstændighed</h2>
            <CompletenessScore />
          </div>

          {/* Template selector */}
          <Card padding="sm">
            <CardHeader>
              <CardTitle>Template</CardTitle>
              <button
                onClick={() => setShowTempl(v => !v)}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {showTempl ? "Skjul" : "Vælg"}
              </button>
            </CardHeader>
            <p className="mt-1 text-xs text-slate-400">
              Aktiv: <span className="font-medium text-slate-600">{cvTemplate.replace(/_/g, " ")}</span>
            </p>
            {showTempl && (
              <div className="mt-3">
                <CvTemplateSelector
                  selected={cvTemplate}
                  onSelect={t => { setCvTemplate(t); }}
                  columns={3}
                />
                <div className="mt-3 flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    loading={downloading === "pdf"}
                    onClick={downloadCvPdf}
                    disabled={!content}
                  >
                    PDF ↓
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    loading={downloading === "docx"}
                    onClick={downloadCvDocx}
                    disabled={!content}
                  >
                    DOCX ↓
                  </Button>
                </div>
              </div>
            )}
          </Card>

          {/* Version history */}
          <Card padding="sm">
            <CardHeader>
              <CardTitle>Versionshistorik</CardTitle>
              <button onClick={toggleVersionHistory} className="text-xs text-blue-600 hover:text-blue-800">
                {showVer ? "Skjul" : "Vis"}
              </button>
            </CardHeader>

            {showVer && (
              <div className="mt-3 space-y-2">
                {loadingVer && (
                  <p className="text-center text-xs text-slate-400">Henter versioner…</p>
                )}
                {!loadingVer && versions.length === 0 && (
                  <p className="text-xs text-slate-400">
                    Ingen versioner endnu — klik &ldquo;Gem version&rdquo; for at oprette et snapshot.
                  </p>
                )}
                {versions.map(v => (
                  <div key={v.id} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-xs font-medium text-slate-700">v{v.version_number}</span>
                      <div className="flex gap-1">
                        <Badge variant={v.generated_by === "ai" ? "info" : "default"}>
                          {v.generated_by === "ai" ? "AI" : "Manuel"}
                        </Badge>
                        <Badge>{v.language.toUpperCase()}</Badge>
                      </div>
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{fmtDate(v.created_at)}</p>
                    <button
                      onClick={() => restoreVersion(v.id, v.title)}
                      className="mt-1.5 text-xs text-blue-600 hover:text-blue-800"
                    >
                      Gendan →
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Info card */}
          <Card padding="sm">
            <h3 className="mb-2 text-xs font-semibold text-slate-700">Om Master CV</h3>
            <ul className="space-y-1.5 text-xs text-slate-500">
              <li>· Genereres fra din fulde kandidatprofil</li>
              <li>· AI gemmer automatisk efter generering</li>
              <li>· Rediger direkte og klik &quot;Gem&quot;</li>
              <li>· &quot;Gem version&quot; opretter et snapshot</li>
              <li>· Gendannelse erstatter nuværende indhold</li>
            </ul>
            <div className="mt-3 rounded-lg border border-dashed border-slate-200 p-2 text-center">
              <p className="text-xs text-slate-400">PDF / DOCX export</p>
              <p className="text-xs text-slate-300">kommer i Sprint 3</p>
            </div>
          </Card>
        </div>
      </aside>
    </div>
  );
}
