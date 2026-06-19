"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { apiUploadStream, type UploadProgressEvent } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { UploadResult } from "@/types";

const ACCEPTED = ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"];
const ACCEPTED_EXT = ".pdf, .doc, .docx, .txt";

type UploadState = "idle" | "uploading" | "success" | "error";

const SECTION_LABELS: Record<string, string> = {
  experiences: "Erfaringer",
  educations: "Uddannelse",
  skills: "Kompetencer",
  projects: "Projekter",
  achievements: "Præstationer",
  systems: "Systemer",
  leadership: "Lederskab",
  certifications: "Certifikater",
};

const STEP_LABELS: Record<string, string> = {
  extract:  "Læser fil",
  ai_parse: "AI analyserer",
  saving:   "Gemmer profil",
  done:     "Færdig",
};

export default function CVUploadPage() {
  const router = useRouter();
  const [state, setState] = useState<UploadState>("idle");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [progress, setProgress] = useState<UploadProgressEvent>({ step: "extract", pct: 0, message: "" });

  async function uploadFile(file: File) {
    const EXT_MAP: Record<string, string> = {
      pdf: "application/pdf",
      doc: "application/msword",
      docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      txt: "text/plain",
    };
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    const effectiveType = file.type || EXT_MAP[ext] || "";

    if (!ACCEPTED.includes(effectiveType)) {
      setError("Kun PDF, DOCX og TXT understøttes.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Filen må maksimalt være 10 MB.");
      return;
    }

    setFileName(file.name);
    setState("uploading");
    setError(null);
    setProgress({ step: "extract", pct: 5, message: "Starter upload..." });

    try {
      const data = await apiUploadStream<UploadResult>(
        "/cv/upload",
        file,
        (evt) => setProgress(evt),
      );
      setResult(data);
      setState("success");
      if (data.session_id) {
        localStorage.setItem("careeros_session_id", data.session_id);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload mislykkedes.";
      setError(msg);
      setState("error");
    }
  }

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) uploadFile(file);
    },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Upload dit CV</h1>
        <p className="mt-1 text-sm text-slate-500">
          AI'en analyserer dit CV og identificerer, hvad der mangler for at bygge din Master-profil.
        </p>
      </div>

      {state !== "success" && (
        <Card
          className={`cursor-pointer border-2 border-dashed transition-colors ${
            dragOver
              ? "border-blue-500 bg-blue-50"
              : state === "uploading"
              ? "border-blue-300 bg-blue-50/40"
              : "border-slate-300 hover:border-blue-400"
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <label className={`flex flex-col items-center gap-4 py-8 ${state === "uploading" ? "pointer-events-none" : "cursor-pointer"}`}>
            <div className={`rounded-full p-4 ${dragOver ? "bg-blue-100" : state === "uploading" ? "bg-blue-50" : "bg-slate-100"}`}>
              {state === "uploading" ? (
                <svg className="h-8 w-8 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
              ) : (
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={dragOver ? "#2563eb" : "#94a3b8"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              )}
            </div>

            <div className="w-full max-w-sm text-center">
              <p className="font-medium text-slate-900">
                {state === "uploading"
                  ? `Analyserer ${fileName}…`
                  : "Træk dit CV hertil eller klik for at vælge"}
              </p>
              {state !== "uploading" && (
                <p className="mt-1 text-sm text-slate-500">{ACCEPTED_EXT} · Maks. 10 MB</p>
              )}
            </div>

            {state === "uploading" && (
              <div className="w-full max-w-sm space-y-3">
                {/* Progress bar */}
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all duration-500"
                    style={{ width: `${progress.pct}%` }}
                  />
                </div>
                {/* Step label */}
                <div className="flex items-center justify-between text-xs text-slate-500">
                  {(["extract", "ai_parse", "saving", "done"] as const).map((step) => (
                    <span
                      key={step}
                      className={progress.step === step ? "font-semibold text-blue-600" : ""}
                    >
                      {STEP_LABELS[step]}
                    </span>
                  ))}
                </div>
                {/* Current message */}
                <p className="text-center text-sm text-blue-700">{progress.message}</p>
              </div>
            )}

            <input
              type="file"
              accept={ACCEPTED_EXT}
              className="sr-only"
              onChange={handleFileChange}
              disabled={state === "uploading"}
            />
          </label>
        </Card>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
          <button
            className="ml-3 underline"
            onClick={() => { setError(null); setState("idle"); }}
          >
            Prøv igen
          </button>
        </div>
      )}

      {state === "success" && result && (
        <div className="space-y-6">
          {/* Success header */}
          <div className="flex items-center gap-3 rounded-xl border border-green-200 bg-green-50 px-5 py-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-green-100">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <div>
              <p className="font-medium text-green-800">CV analyseret</p>
              <p className="text-sm text-green-600">{fileName}</p>
            </div>
          </div>

          {/* Parsed sections */}
          <Card>
            <h2 className="mb-4 font-semibold text-slate-900">Hvad AI&apos;en fandt</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Object.entries(result.parsed_sections).map(([key, count]) => (
                count > 0 && (
                  <div key={key} className="rounded-lg bg-slate-50 p-3 text-center">
                    <p className="text-2xl font-bold text-blue-600">{count}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {SECTION_LABELS[key] ?? key}
                    </p>
                  </div>
                )
              ))}
            </div>

            {result.personal?.name && (
              <div className="mt-4 border-t border-slate-100 pt-4">
                <p className="text-sm text-slate-600">
                  <span className="font-medium">Kandidat:</span>{" "}
                  {result.personal.name}
                  {result.personal.current_title && (
                    <> · {result.personal.current_title}</>
                  )}
                </p>
              </div>
            )}
          </Card>

          {/* Gaps */}
          {result.gaps.length > 0 && (
            <Card>
              <h2 className="mb-3 font-semibold text-slate-900">
                AI-interviewet vil dække
              </h2>
              <div className="space-y-2">
                {result.gaps.slice(0, 6).map((gap, i) => (
                  <div key={i} className="flex items-start gap-2">
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
                    <p className="text-sm text-slate-700">{gap.description}</p>
                  </div>
                ))}
                {result.gaps.length > 6 && (
                  <p className="text-xs text-slate-400">
                    + {result.gaps.length - 6} flere punkter
                  </p>
                )}
              </div>
            </Card>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              size="lg"
              className="flex-1"
              onClick={() => router.push("/cv/interview")}
            >
              Start AI-interview
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </Button>
            <Button
              variant="secondary"
              size="lg"
              onClick={() => { setState("idle"); setResult(null); setFileName(null); }}
            >
              Upload nyt
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
