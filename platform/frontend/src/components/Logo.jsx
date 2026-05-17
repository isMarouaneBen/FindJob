import logo from "../assets/logo.png";
import { cn } from "../lib/cn";

/**
 * FindJob logo — white circle mark with tie. The source is white-on-transparent,
 * so on the dark background it renders directly.
 *
 *   variant="wordmark" (default)  →  mark + "FindJob" text
 *   variant="mark"                →  icon only (header, favicons, mobile)
 */
export default function Logo({ variant = "wordmark", size = 34, className }) {
  const dim = { width: size, height: size };

  const Mark = (
    <img src={logo} alt="FindJob" style={dim}
         className="object-contain shrink-0
                    drop-shadow-[0_2px_8px_rgba(255,255,255,0.06)]" />
  );

  if (variant === "mark") return <span className={className}>{Mark}</span>;

  // Hero variant — large featured icon with a soft brand glow halo.
  if (variant === "hero") {
    return (
      <div className={cn("relative inline-flex items-center justify-center", className)}>
        <div className="absolute inset-0 -m-6 rounded-full bg-brand-500/25 blur-2xl animate-pulse-soft" />
        <img src={logo} alt="FindJob"
             style={{ width: size, height: size }}
             className="relative object-contain drop-shadow-[0_4px_24px_rgba(99,102,241,0.35)]" />
      </div>
    );
  }

  // Default wordmark (header)
  const textSize = size >= 32 ? "text-base" : "text-[15px]";
  return (
    <span className={cn("inline-flex items-center gap-2.5 select-none", className)}>
      {Mark}
      <span className={cn("font-display font-semibold tracking-tight text-text", textSize)}>
        FindJob
      </span>
    </span>
  );
}
