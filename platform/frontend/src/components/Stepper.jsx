import { Check } from "lucide-react";
import { cn } from "../lib/cn";

export default function Stepper({ steps, current = 0, className }) {
  return (
    <ol className={cn("flex items-center w-full", className)}>
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={label} className="flex items-center flex-1 last:flex-none">
            <div className="flex items-center gap-2">
              <span className={cn(
                "w-7 h-7 rounded-full grid place-items-center text-[11px] font-semibold transition-all",
                done && "bg-gradient-cta text-white shadow-glow",
                active && "bg-bg-card text-brand-300 ring-1 ring-brand-500/60 shadow-glow",
                !done && !active && "bg-white/[0.04] text-text-dim ring-1 ring-line",
              )}>
                {done ? <Check size={14} strokeWidth={3} /> : i + 1}
              </span>
              <span className={cn(
                "text-sm font-medium hidden sm:inline transition-colors",
                (done || active) ? "text-text" : "text-text-dim",
              )}>
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className="flex-1 h-px mx-3 sm:mx-4 bg-line relative overflow-hidden">
                {done && <div className="absolute inset-0 bg-gradient-cta" />}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
