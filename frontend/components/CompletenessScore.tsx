"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { Progress } from "@/components/ui/progress";
import { cn, scoreColor } from "@/lib/utils";
import type { ProfileScore } from "@/types";

const SECTION_LABELS: Record<string, string> = {
  experiences: "Erfaringer",
  achievements: "Præstationer",
  projects: "Projekter",
  systems: "Systemer",
  education: "Uddannelse",
  leadership: "Lederskab",
  contact: "Kontakt",
  certifications: "Certifikater",
  skills: "Kompetencer",
};

interface CompletenessScoreProps {
  compact?: boolean;
  onScoreLoad?: (score: ProfileScore) => void;
  refreshKey?: string | number;
}

export function CompletenessScore({
  compact = false,
  onScoreLoad,
  refreshKey,
}: CompletenessScoreProps) {
  const [score, setScore] = useState<ProfileScore | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiGet<ProfileScore>("/profile/score");
        setScore(data);
        onScoreLoad?.(data);
      } catch {
        // Score might not exist yet — try recalculating
        try {
          const data = await apiPost<ProfileScore>("/profile/score/recalculate");
          setScore(data);
          onScoreLoad?.(data);
        } catch {
          setScore(null);
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="space-y-2 animate-pulse">
        <div className="h-4 rounded bg-slate-200" />
        <div className="h-2 rounded bg-slate-200" />
      </div>
    );
  }

  if (!score) {
    return (
      <p className="text-xs text-slate-400">Upload et CV for at se din score</p>
    );
  }

  if (compact) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-slate-300">Profil</span>
          <span className={cn("text-sm font-bold", scoreColor(score.overall))}>
            {score.overall}%
          </span>
        </div>
        <Progress value={score.overall} colorByScore showLabel={false} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className={cn("text-2xl font-bold", scoreColor(score.overall))}>
          {score.overall}%
        </div>
        <div>
          <p className="text-xs font-medium text-slate-300">Profil fuldstændighed</p>
          {score.missing_areas.length > 0 && (
            <p className="text-xs text-slate-500">
              {score.missing_areas.length} mangler
            </p>
          )}
        </div>
      </div>

      <Progress value={score.overall} colorByScore />

      <div className="space-y-1.5 pt-1">
        {Object.entries(score.sections)
          .sort(([, a], [, b]) => a - b)
          .map(([key, val]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="w-20 truncate text-xs text-slate-400">
                {SECTION_LABELS[key] ?? key}
              </span>
              <Progress
                value={val}
                colorByScore
                className="flex-1"
              />
              <span className="w-7 text-right text-xs text-slate-400">
                {val}%
              </span>
            </div>
          ))}
      </div>

      {score.missing_areas.length > 0 && (
        <div className="rounded-lg bg-slate-800 p-2">
          <p className="mb-1 text-xs font-medium text-slate-400">Mangler:</p>
          {score.missing_areas.map((area) => (
            <p key={area} className="text-xs text-amber-400">
              · {area}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
