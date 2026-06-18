"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiStream } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CompletenessScore } from "@/components/CompletenessScore";

interface MasterCVContent {
  raw_content: string | null;
  is_generated: boolean;
}

export default function MasterCVPage() {
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadContent();
  }, []);

  async function loadContent() {
    setLoading(true);
    try {
      const data = await apiGet<MasterCVContent>("/cv/master/content");
      if (data.raw_content) {
        setContent(data.raw_content);
      }
    } catch {
      // Not yet generated — empty state
    } finally {
      setLoading(false);
    }
  }

  async function generate() {
    setGenerating(true);
    setError(null);
    setContent("");

    try {
      await apiStream(
        "/cv/master/generate",
        {},
        (chunk) => setContent((prev) => prev + chunk),
        () => {
          setGenerating(false);
          setSaved(true);
          setTimeout(() => setSaved(false), 3000);
        },
        (err) => {
          setError(err);
          setGenerating(false);
        }
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Generering mislykkedes."
      );
      setGenerating(false);
    }
  }

  async function copy() {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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

  return (
    <div className="flex h-full gap-6">
      {/* Main area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Master CV</h1>
            <p className="mt-1 text-sm text-slate-500">
              Genereret og opdateret af AI baseret på din fulde kandidatprofil
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {content && (
              <Button variant="outline" size="sm" onClick={copy}>
                {copied ? (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    Kopieret
                  </>
                ) : (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    Kopiér
                  </>
                )}
              </Button>
            )}
            <Button
              onClick={generate}
              loading={generating}
              size="md"
            >
              {content ? "Regenerér" : "Generér Master CV"}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {saved && (
          <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            Master CV gemt automatisk
          </div>
        )}

        {/* Empty state */}
        {!content && !generating && (
          <Card className="flex flex-1 flex-col items-center justify-center gap-4 py-16">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-50">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
            </div>
            <div className="text-center">
              <p className="font-medium text-slate-900">Intet Master CV endnu</p>
              <p className="mt-1 text-sm text-slate-500">
                Klik på &quot;Generér Master CV&quot; for at bygge dit CV fra din profil
              </p>
            </div>
            <Button onClick={generate} size="lg">
              Generér Master CV
            </Button>
          </Card>
        )}

        {/* CV content */}
        {(content || generating) && (
          <div className="flex flex-1 flex-col">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs text-slate-500">
                Redigér dit CV direkte i tekstfeltet
              </p>
              {generating && (
                <div className="flex items-center gap-2 text-xs text-blue-600">
                  <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  AI genererer…
                </div>
              )}
            </div>
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              disabled={generating}
              className="flex-1 rounded-xl border border-slate-200 bg-white p-6 font-mono text-sm text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-slate-50"
              spellCheck={false}
              style={{ minHeight: "600px", resize: "vertical" }}
            />

            {content && !generating && (
              <div className="mt-3 flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={copy}>
                  {copied ? "Kopieret!" : "Kopiér alt"}
                </Button>
                <Button size="sm" onClick={generate} loading={generating}>
                  Regenerér
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Score sidebar */}
      <aside className="w-64 shrink-0">
        <div className="sticky top-0 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-slate-900 p-4">
            <h2 className="mb-4 text-sm font-semibold text-slate-200">
              Profil fuldstændighed
            </h2>
            <CompletenessScore />
          </div>

          <Card padding="sm">
            <h3 className="mb-2 text-xs font-semibold text-slate-700">
              Om Master CV
            </h3>
            <ul className="space-y-1.5 text-xs text-slate-500">
              <li>· Genereres fra din fulde profil</li>
              <li>· Gemmes automatisk efter generering</li>
              <li>· Kan regenereres når som helst</li>
              <li>· Redigér direkte i tekstfeltet</li>
            </ul>
          </Card>
        </div>
      </aside>
    </div>
  );
}
