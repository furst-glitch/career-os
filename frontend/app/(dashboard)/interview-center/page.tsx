"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";

interface Application {
  id: string;
  current_status: string;
  created_at: string;
  jobs: {
    id: string;
    title: string;
    company: string;
    location: string | null;
  };
}

const STATUS_LABELS: Record<string, string> = {
  samtale_1: "Samtale 1",
  samtale_2: "Samtale 2",
  case_stadie: "Case",
  interviewing: "Interview",
};

const SAMTALE_STATUSES = new Set(["samtale_1", "samtale_2", "case_stadie", "interviewing"]);

export default function InterviewCenterPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<{ applications: Application[] }>("/applications")
      .then((d) => setApplications(
        (d.applications ?? []).filter((a) => SAMTALE_STATUSES.has(a.current_status))
      ))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Interview Center</h1>
        <p className="mt-1 text-sm text-slate-500">
          Forberedelsespakker til dine kommende samtaler — genereret af AI baseret på dit CV og jobopslaget.
        </p>
      </div>

      {applications.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-slate-200 py-16 text-center">
          <p className="text-slate-500">Ingen kommende samtaler.</p>
          <p className="mt-1 text-sm text-slate-400">
            Opdater et jobs status til &quot;Samtale 1&quot; under Jobs for at generere en forberedelsespakke.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {applications.map((app) => (
            <button
              key={app.id}
              onClick={() => router.push(`/interview-center/${app.id}`)}
              className="rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm hover:shadow-md transition-shadow hover:border-blue-200"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-slate-900 truncate">{app.jobs?.title ?? "Ukendt stilling"}</h3>
                  <p className="text-sm text-slate-600">{app.jobs?.company}</p>
                  {app.jobs?.location && (
                    <p className="mt-0.5 text-xs text-slate-400">{app.jobs.location}</p>
                  )}
                </div>
                <span className="shrink-0 rounded-full bg-purple-100 px-2.5 py-1 text-xs font-medium text-purple-700">
                  {STATUS_LABELS[app.current_status] ?? app.current_status}
                </span>
              </div>
              <div className="mt-4 rounded-lg bg-blue-50 px-3 py-2">
                <p className="text-xs font-medium text-blue-700">Se forberedelsespakke →</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
