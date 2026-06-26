"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

type Employment = {
  id: string;
  title: string;
  organisation: string | null;
  period_start: string | null;
  period_end: string | null;
  experience_type: string;
  created_at: string;
};

function formatDate(d: string | null): string {
  if (!d) return "nu";
  return new Date(d).toLocaleDateString("da-DK", { year: "numeric", month: "short" });
}

export default function ExperiencePage() {
  const router = useRouter();
  const [employments, setEmployments] = useState<Employment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title: "",
    organisation: "",
    experience_type: "job",
    period_start: "",
    period_end: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const data = await apiGet<Employment[]>("/employment-graph/employments");
      setEmployments(data);
    } catch {
      // noop — show empty state
    }
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function create() {
    if (!form.title.trim()) return;
    setSaving(true);
    setError("");
    try {
      await apiPost("/employment-graph/employments", {
        title: form.title,
        organisation: form.organisation || null,
        experience_type: form.experience_type,
        period_start: form.period_start || null,
        period_end: form.period_end || null,
      });
      setShowForm(false);
      setForm({ title: "", organisation: "", experience_type: "job", period_start: "", period_end: "" });
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Oprettelse fejlede");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Arbejdsgraf</h1>
          <p className="text-gray-500 text-sm mt-1">
            Analyser kontrakter og lønsedler og se afvigelser på tværs af dokumenter
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-black text-white rounded text-sm"
        >
          + Nyt ansættelsesforhold
        </button>
      </div>

      {showForm && (
        <div className="border rounded-lg p-4 space-y-4 bg-gray-50">
          <h2 className="font-semibold">Opret ansættelsesforhold</h2>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-600 block mb-0.5">Stilling *</label>
              <input
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="f.eks. Senior Controller"
                className="w-full border rounded px-2 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600 block mb-0.5">Virksomhed</label>
              <input
                value={form.organisation}
                onChange={(e) => setForm((f) => ({ ...f, organisation: e.target.value }))}
                placeholder="f.eks. ABC A/S"
                className="w-full border rounded px-2 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600 block mb-0.5">Type</label>
              <select
                value={form.experience_type}
                onChange={(e) => setForm((f) => ({ ...f, experience_type: e.target.value }))}
                className="w-full border rounded px-2 py-1.5 text-sm"
              >
                <option value="job">Fuldtidsjob</option>
                <option value="freelance">Freelance</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-600 block mb-0.5">Startdato</label>
                <input
                  type="date"
                  value={form.period_start}
                  onChange={(e) => setForm((f) => ({ ...f, period_start: e.target.value }))}
                  className="w-full border rounded px-2 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-600 block mb-0.5">Slutdato (blank = nu)</label>
                <input
                  type="date"
                  value={form.period_end}
                  onChange={(e) => setForm((f) => ({ ...f, period_end: e.target.value }))}
                  className="w-full border rounded px-2 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={create}
              disabled={saving || !form.title.trim()}
              className="px-4 py-2 bg-black text-white rounded text-sm disabled:opacity-50"
            >
              {saving ? "Opretter..." : "Opret"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border rounded text-sm"
            >
              Annuller
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-gray-500 text-sm">Indlæser...</p>
      ) : employments.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <svg
            className="mx-auto mb-4 opacity-40"
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <rect x="2" y="3" width="6" height="6" rx="1" />
            <rect x="16" y="3" width="6" height="6" rx="1" />
            <rect x="9" y="15" width="6" height="6" rx="1" />
            <line x1="5" y1="9" x2="5" y2="12" />
            <line x1="19" y1="9" x2="19" y2="12" />
            <line x1="5" y1="12" x2="12" y2="12" />
            <line x1="19" y1="12" x2="12" y2="12" />
            <line x1="12" y1="12" x2="12" y2="15" />
          </svg>
          <p className="font-medium mb-1">Ingen ansættelsesforhold endnu</p>
          <p className="text-sm">
            Opret et ansættelsesforhold og upload din kontrakt eller lønseddel for at komme i gang
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {employments.map((emp) => (
            <button
              key={emp.id}
              onClick={() => router.push(`/experience/${emp.id}`)}
              className="w-full text-left border rounded-lg p-4 hover:border-black transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{emp.title}</p>
                  <p className="text-sm text-gray-500">
                    {emp.organisation && `${emp.organisation} · `}
                    {formatDate(emp.period_start)} – {formatDate(emp.period_end)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-gray-100 text-xs">
                    {emp.experience_type === "job" ? "Fuldtidsjob" : "Freelance"}
                  </span>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M9 18l6-6-6-6" />
                  </svg>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
