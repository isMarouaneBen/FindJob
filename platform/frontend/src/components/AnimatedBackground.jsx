import { useEffect, useRef } from "react";
import { cn } from "../lib/cn";

/**
 * Aurora-style animated background.
 *
 * variants:
 *  - "hero"      → strong gradient orbs + cursor spotlight + dot grid (landing)
 *  - "app"       → subtle drifting orbs only (dashboard)
 *  - "auth"      → vertical sweep gradient (split-screen auth panel)
 */
export default function AnimatedBackground({ variant = "app", className }) {
  const ref = useRef(null);

  // Cursor spotlight — only on the hero
  useEffect(() => {
    if (variant !== "hero" || !ref.current) return;
    const el = ref.current;
    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, [variant]);

  if (variant === "hero") {
    return (
      <div ref={ref} aria-hidden
           className={cn("absolute inset-0 -z-10 overflow-hidden pointer-events-none", className)}>
        {/* Dot grid masked to fade out edges */}
        <div className="absolute inset-0 bg-dot-grid mask-radial" />

        {/* Aurora orbs */}
        <div className="absolute -top-32 -left-32 w-[42rem] h-[42rem] rounded-full
                        bg-brand-500/[0.22] blur-[120px] animate-aurora-1" />
        <div className="absolute -top-20 right-[-10%] w-[36rem] h-[36rem] rounded-full
                        bg-fuchsia-500/[0.14] blur-[120px] animate-aurora-2" />
        <div className="absolute bottom-[-15%] left-1/3 w-[30rem] h-[30rem] rounded-full
                        bg-violet-500/[0.16] blur-[120px] animate-aurora-3" />

        {/* Cursor spotlight (uses CSS vars updated by JS) */}
        <div
          className="absolute inset-0 transition-opacity"
          style={{
            background:
              "radial-gradient(600px circle at var(--mx, 50%) var(--my, 30%), rgba(99,102,241,0.16), transparent 60%)",
          }}
        />

        {/* Subtle noise to break up the gradient banding */}
        <div className="absolute inset-0 bg-noise opacity-[0.04] mix-blend-overlay" />
      </div>
    );
  }

  if (variant === "auth") {
    return (
      <div aria-hidden
           className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
        <div className="absolute -top-20 -left-20 w-[34rem] h-[34rem] rounded-full
                        bg-brand-500/30 blur-[110px] animate-aurora-1" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[30rem] h-[30rem] rounded-full
                        bg-fuchsia-500/15 blur-[110px] animate-aurora-2" />
        <div className="absolute inset-0 bg-dot-grid opacity-50" />
        <div className="absolute inset-0 bg-noise opacity-[0.05] mix-blend-overlay" />
      </div>
    );
  }

  // App variant — quiet, eye-friendly drift
  return (
    <div aria-hidden
         className={cn("absolute inset-0 -z-10 overflow-hidden pointer-events-none", className)}>
      <div className="absolute top-[-10%] left-1/4 w-[36rem] h-[36rem] rounded-full
                      bg-brand-500/[0.10] blur-[140px] animate-aurora-1" />
      <div className="absolute top-1/3 right-[-10%] w-[28rem] h-[28rem] rounded-full
                      bg-fuchsia-500/[0.06] blur-[140px] animate-aurora-2" />
      <div className="absolute inset-0 bg-dot-grid opacity-40 mask-radial-center" />
    </div>
  );
}
