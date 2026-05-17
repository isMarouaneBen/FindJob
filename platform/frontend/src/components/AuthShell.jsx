import { Link } from "react-router-dom";
import { Sparkles, Quote } from "lucide-react";
import Logo from "./Logo";
import AnimatedBackground from "./AnimatedBackground";

export default function AuthShell({ children, title, subtitle }) {
  return (
    <div className="min-h-full grid grid-cols-1 lg:grid-cols-[1.05fr_1fr] bg-bg">
      {/* LEFT — brand panel */}
      <aside className="hidden lg:flex flex-col justify-between p-12 relative overflow-hidden border-r border-line">
        <AnimatedBackground variant="auth" />

        <div className="relative">
          <Link to="/" className="inline-flex items-center"><Logo /></Link>
        </div>

        <div className="relative max-w-md">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                          bg-white/[0.04] border border-line text-[11px] text-text-mute">
            <Sparkles size={11} className="text-brand-400"/> Semantic match · pgvector
          </div>
          <h2 className="mt-5 text-4xl font-display font-medium leading-[1.1] text-text">
            Stop scrolling job boards.<br/>
            <span className="text-gradient-brand">Get offers built for your CV.</span>
          </h2>
          <p className="mt-4 text-text-mute leading-relaxed">
            FindJob ranks thousands of tech offers from France and Morocco against your skills,
            seniority and preferences — with a transparent score.
          </p>

          <figure className="mt-10 relative">
            <div className="absolute inset-0 bg-gradient-cta opacity-20 blur-2xl rounded-2xl" />
            <div className="relative glass p-5">
              <Quote className="text-brand-300/50" size={16} />
              <blockquote className="mt-2 text-sm text-text/90 leading-relaxed">
                "Finally a tool that explains why an offer matches my profile.
                The skill-gap view alone tells me where to focus."
              </blockquote>
              <figcaption className="mt-3 text-xs text-text-dim">
                — Data Engineer, beta tester
              </figcaption>
            </div>
          </figure>
        </div>

        <div className="relative text-xs text-text-faint">
          © {new Date().getFullYear()} FindJob
        </div>
      </aside>

      {/* RIGHT — form */}
      <main className="flex flex-col p-6 sm:p-10 lg:p-16 bg-bg">
        <div className="lg:hidden mb-6">
          <Link to="/"><Logo /></Link>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="w-full max-w-sm animate-fade-up">
            <h1 className="text-3xl font-display font-medium tracking-tight text-text">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-text-mute">{subtitle}</p>}
            <div className="mt-8">{children}</div>
          </div>
        </div>
      </main>
    </div>
  );
}
