import { cn } from "../lib/cn";

/**
 * Circular score 0..1. Adapts color and glow for dark surfaces.
 */
export default function ScoreRing({ value = 0, size = 52, stroke = 4, className }) {
  const pct = Math.max(0, Math.min(1, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - pct * c;

  const tone = pct >= 0.66 ? "emerald" : pct >= 0.45 ? "brand" : "amber";
  const stroke_color = {
    emerald: "stroke-emerald-400",
    brand:   "stroke-brand-400",
    amber:   "stroke-amber-400",
  }[tone];
  const text_color = {
    emerald: "text-emerald-300",
    brand:   "text-brand-200",
    amber:   "text-amber-300",
  }[tone];

  return (
    <div className={cn("relative shrink-0", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={r}
                className="stroke-white/[0.06]" strokeWidth={stroke} fill="none" />
        <circle cx={size/2} cy={size/2} r={r}
                className={cn(stroke_color, "transition-[stroke-dashoffset] duration-700")}
                strokeWidth={stroke} fill="none"
                strokeLinecap="round"
                strokeDasharray={c} strokeDashoffset={offset}
                style={{ filter: "drop-shadow(0 0 6px currentColor)" }} />
      </svg>
      <div className={cn("absolute inset-0 grid place-items-center tabular-nums font-semibold", text_color)}
           style={{ fontSize: size * 0.34 }}>
        {Math.round(pct * 100)}
      </div>
    </div>
  );
}
