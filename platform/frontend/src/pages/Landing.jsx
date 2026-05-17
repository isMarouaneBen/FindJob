import { Link } from "react-router-dom";
import {
  ArrowRight, BarChart3, CheckCircle2, FileText, Gauge,
  ShieldCheck, Sparkles, Target, Zap,
} from "lucide-react";
import AnimatedBackground from "../components/AnimatedBackground";
import Logo from "../components/Logo";
import { useAuth } from "../auth/AuthContext";
import { nextStepFor } from "../auth/flow";

const FEATURES = [
  { icon: Sparkles, title: "Semantic match",
    text: "Vector embeddings on offer descriptions and your CV — not naive keyword matching." },
  { icon: Target,   title: "Canonical skill graph",
    text: "Python on your CV maps to Python on the offer. K8s → Kubernetes. No silent mismatches." },
  { icon: Gauge,    title: "Explainable scoring",
    text: "Every match shows a per-signal breakdown: skills, seniority, location, language." },
  { icon: Zap,      title: "Daily re-indexing",
    text: "Adzuna, Rekrute and Emploi-Public are scraped and embedded every morning." },
  { icon: ShieldCheck, title: "Privacy-first",
    text: "Your CV stays in a private bucket. Bcrypt-hashed passwords. Server-side Google verification." },
  { icon: BarChart3, title: "Built for candidates",
    text: "No recruiter dashboard, no newsletter, no sponsored offers — just the ranking." },
];

const STEPS = [
  { icon: FileText, title: "Upload your CV",
    text: "PDF, DOCX or TXT. We extract skills, languages, years and seniority — even from poorly extracted PDFs." },
  { icon: Target,   title: "Refine (optional)",
    text: "Target role, contract type, location, salary floor. Adds extra signals on top of the CV vector." },
  { icon: Sparkles, title: "See ranked offers",
    text: "Real-time semantic + lexical match across thousands of fresh offers, with a transparent score." },
];

// Mock preview offers shown in the hero card
const PREVIEW_OFFERS = [
  { score: 87, title: "Senior Data Engineer · GCP",     loc: "Casablanca", country: "Maroc",
    matched: ["python","sql","bigquery","airflow"] },
  { score: 81, title: "ML Engineer · LLM Platform",     loc: "Paris",      country: "France",
    matched: ["python","pytorch","mlops","docker"] },
  { score: 74, title: "Data Scientist · Fraud",         loc: "Lyon",       country: "France",
    matched: ["machine learning","python","sql"] },
];

export default function Landing() {
  const { user, isAuthenticated } = useAuth();
  const ctaTarget = isAuthenticated ? nextStepFor(user?.user_id) : "/register";

  return (
    <div className="overflow-hidden">
      {/* ============= HERO ============= */}
      <section className="relative">
        <AnimatedBackground variant="hero" />

        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-16 sm:pt-24 pb-20 text-center">
          {/* Featured logo */}
          <div className="flex justify-center animate-fade-up">
            <Logo variant="hero" size={88} />
          </div>

          {/* announcement chip */}
          <div className="mt-8 inline-flex items-center gap-2 px-3 py-1 rounded-full
                          bg-white/[0.04] border border-line text-xs text-text-mute
                          animate-fade-in backdrop-blur">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75 animate-ping" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-brand-400" />
            </span>
            Powered by pgvector · sentence-transformers · FastAPI
          </div>

          <h1 className="mt-7 text-4xl sm:text-6xl lg:text-7xl font-display font-medium tracking-tight
                         text-text leading-[1.05] animate-fade-up"
              style={{ animationDelay: "60ms" }}>
            Tech offers that{" "}
            <span className="text-gradient-brand">actually fit</span><br/>
            your résumé.
          </h1>
          <p className="mt-6 max-w-2xl mx-auto text-lg text-text-mute leading-relaxed animate-fade-up"
             style={{ animationDelay: "150ms" }}>
            Upload your CV once. Get a ranked list of relevant offers from France and Morocco —
            with a transparent score, so you know exactly why each one matches.
          </p>

          <div className="mt-9 flex items-center justify-center gap-3 animate-fade-up"
               style={{ animationDelay: "240ms" }}>
            <Link to={ctaTarget} className="btn-primary btn-xl group">
              {isAuthenticated ? "See your recommendations" : "Get started — it's free"}
              <ArrowRight size={17} className="transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a href="#how" className="btn-secondary btn-xl">How it works</a>
          </div>

          {/* trust line */}
          <div className="mt-12 flex items-center justify-center gap-x-7 gap-y-3 flex-wrap text-xs text-text-dim
                          animate-fade-up" style={{ animationDelay: "320ms" }}>
            {[
              "1,300+ live offers",
              "Adzuna · Rekrute · Emploi-Public",
              "Daily re-indexing",
              "Bcrypt + JWT auth",
            ].map((t) => (
              <span key={t} className="inline-flex items-center gap-1.5">
                <CheckCircle2 size={12} className="text-emerald-400" /> {t}
              </span>
            ))}
          </div>

          {/* PREVIEW CARD */}
          <div className="mt-16 sm:mt-20 relative animate-fade-up" style={{ animationDelay: "420ms" }}>
            {/* glow */}
            <div className="absolute -inset-x-12 -bottom-12 -top-4 bg-gradient-cta opacity-25 blur-[80px] pointer-events-none" />
            <div className="relative card-elevated overflow-hidden">
              {/* "browser" chrome */}
              <div className="px-4 py-2.5 border-b border-line flex items-center gap-2 text-[11px] font-mono text-text-dim
                              bg-bg-elevated">
                <div className="flex gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-white/10" />
                  <span className="w-2.5 h-2.5 rounded-full bg-white/10" />
                  <span className="w-2.5 h-2.5 rounded-full bg-white/10" />
                </div>
                <span className="ml-2">POST</span>
                <span className="text-text-mute">/api/v1/recommendations</span>
                <span className="ml-auto text-text-faint">200 · 38ms</span>
              </div>

              <div className="p-5 sm:p-6 grid grid-cols-1 md:grid-cols-3 gap-4 text-left">
                {PREVIEW_OFFERS.map((o) => (
                  <div key={o.title}
                       className="rounded-xl border border-line bg-bg-card p-4 hover:border-line-strong transition">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-text text-sm truncate">{o.title}</p>
                        <p className="text-xs text-text-dim mt-1">{o.loc} · {o.country}</p>
                      </div>
                      <div className="text-right">
                        <div className="text-xl font-semibold text-brand-300 tabular-nums">{o.score}</div>
                        <div className="text-[9px] uppercase tracking-wide text-text-faint">match</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1">
                      {o.matched.map((t) => <span key={t} className="badge-success">{t}</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============= HOW IT WORKS ============= */}
      <section id="how" className="relative">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-24 sm:py-32">
          <div className="text-center max-w-2xl mx-auto">
            <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-[0.16em]">How it works</p>
            <h2 className="mt-3 text-3xl sm:text-5xl font-display font-medium tracking-tight text-text">
              From CV to ranked offers <br/>in 60 seconds.
            </h2>
          </div>

          <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-px bg-line rounded-2xl overflow-hidden border border-line">
            {STEPS.map((s, i) => (
              <div key={s.title}
                   className="relative bg-bg-card p-7 hover:bg-bg-elevated transition-colors group">
                <div className="text-[11px] font-mono text-text-faint">{String(i + 1).padStart(2, "0")}</div>
                <div className="mt-4 w-9 h-9 rounded-xl bg-brand-500/10 border border-brand-500/20
                                text-brand-300 grid place-items-center group-hover:bg-brand-500/15">
                  <s.icon size={17} />
                </div>
                <h3 className="mt-4 font-medium text-text">{s.title}</h3>
                <p className="mt-1.5 text-sm text-text-mute leading-relaxed">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============= FEATURES ============= */}
      <section className="relative border-y border-line bg-bg-subtle/40">
        {/* subtle dot grid */}
        <div className="absolute inset-0 bg-dot-grid opacity-30 mask-radial-center pointer-events-none" />

        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 py-24 sm:py-32">
          <div className="text-center max-w-2xl mx-auto">
            <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-[0.16em]">Why it works</p>
            <h2 className="mt-3 text-3xl sm:text-5xl font-display font-medium tracking-tight text-text">
              Not just keyword search.
            </h2>
            <p className="mt-4 text-text-mute">
              Vector embeddings, a canonical skill graph, and a transparent scoring formula — open by design.
            </p>
          </div>

          <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title}
                   className="group glass p-6 hover:bg-white/[0.05] hover:border-line-strong transition-all">
                <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20
                                text-brand-300 grid place-items-center
                                group-hover:bg-brand-500/15 group-hover:shadow-glow transition-all">
                  <f.icon size={17} />
                </div>
                <h3 className="mt-4 font-medium text-text">{f.title}</h3>
                <p className="mt-1.5 text-sm text-text-mute leading-relaxed">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============= CTA ============= */}
      <section className="relative">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-24 sm:py-32">
          <div className="relative overflow-hidden rounded-3xl border border-line bg-bg-card p-10 sm:p-16 text-center">
            {/* animated orbs inside */}
            <div className="absolute -top-20 -left-20 w-96 h-96 rounded-full bg-brand-500/20 blur-[100px] animate-aurora-1" />
            <div className="absolute -bottom-20 -right-20 w-96 h-96 rounded-full bg-fuchsia-500/[0.12] blur-[100px] animate-aurora-2" />

            <h2 className="relative text-3xl sm:text-5xl font-display font-medium tracking-tight text-text">
              Ready to skip the recruiter pipe?
            </h2>
            <p className="relative mt-4 text-text-mute max-w-xl mx-auto">
              Sign up, drop a CV, see ranked offers. No newsletter, no recruiter pings.
            </p>
            <Link to={ctaTarget}
                  className="relative inline-flex items-center gap-2 mt-8 btn-primary btn-xl group">
              {isAuthenticated ? "Open your dashboard" : "Create your account"}
              <ArrowRight size={17} className="transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
