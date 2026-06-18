import { cn, scoreBg } from "@/lib/utils";

interface ProgressProps {
  value: number;
  max?: number;
  className?: string;
  showLabel?: boolean;
  colorByScore?: boolean;
  color?: string;
}

export function Progress({
  value,
  max = 100,
  className,
  showLabel,
  colorByScore = false,
  color,
}: ProgressProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const barColor = color ?? (colorByScore ? scoreBg(value) : "bg-blue-600");

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn("h-full rounded-full transition-all duration-500", barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="w-8 text-right text-xs font-medium text-slate-600">
          {Math.round(value)}%
        </span>
      )}
    </div>
  );
}
