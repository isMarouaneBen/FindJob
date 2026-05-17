import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Sparkles, X } from "lucide-react";
import Stepper from "../components/Stepper";
import AnimatedBackground from "../components/AnimatedBackground";
import { useAuth } from "../auth/AuthContext";
import { clearProfile, getProfile, setProfile } from "../auth/flow";

const STEPS = ["Upload CV", "Profile", "Recommendations"];

const METIERS = [
  { v: "",           l: "—" },
  { v: "DATA_ENG",   l: "Data Engineer" },
  { v: "DATA_SCI",   l: "Data Scientist / ML" },
  { v: "DATA_ANA",   l: "Data Analyst" },
  { v: "BI",         l: "Business Intelligence" },
  { v: "DATA_ARCH",  l: "Data Architect" },
  { v: "DEVOPS",     l: "DevOps / SRE" },
  { v: "CLOUD",      l: "Cloud Engineer" },
  { v: "CYBER",      l: "Cybersécurité" },
  { v: "DEV_BACK",   l: "Backend Developer" },
  { v: "DEV_FRONT",  l: "Frontend Developer" },
  { v: "DEV_FULL",   l: "Fullstack Developer" },
  { v: "DEV_MOBILE", l: "Mobile Developer" },
  { v: "ADMIN_SYS",  l: "Admin Système / Réseau" },
  { v: "CONSULT",    l: "Consultant" },
];
const SENIORITIES = ["Stage","Alternance","Junior","Intermediaire","Confirme","Senior","Expert"];
const REMOTES = [
  { v: "Non",      l: "On-site" },
  { v: "Hybride",  l: "Hybrid" },
  { v: "Total",    l: "Fully remote" },
  { v: "Possible", l: "Occasional" },
];
const CONTRACTS = ["CDI","CDD","Stage","Alternance","Freelance","Interim"];

function ChipsInput({ value, onChange, placeholder }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (v && !value.includes(v)) onChange([...value, v]);
    setDraft("");
  };
  return (
    <div className="rounded-xl border border-line bg-white/[0.03] px-2 py-1.5
                    focus-within:border-brand-500/60 focus-within:bg-white/[0.05] transition-colors">
      <div className="flex flex-wrap gap-1.5">
        {value.map((t) => (
          <span key={t} className="badge-brand pl-2 pr-1 py-1">
            {t}
            <button type="button" onClick={() => onChange(value.filter(x => x !== t))}
                    className="ml-1 p-0.5 rounded hover:bg-brand-500/20">
              <X size={10} />
            </button>
          </span>
        ))}
        <input value={draft}
               onChange={(e) => setDraft(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); }
                 if (e.key === "Backspace" && !draft && value.length)
                   onChange(value.slice(0, -1));
               }}
               onBlur={add}
               placeholder={value.length ? "" : placeholder}
               className="flex-1 min-w-[140px] px-2 py-1 text-sm bg-transparent text-text
                          placeholder:text-text-faint focus:outline-none" />
      </div>
    </div>
  );
}

export default function OnboardingProfile() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const existing = user ? getProfile(user.user_id) : null;

  const [form, setForm] = useState({
    poste_recherche:    existing?.poste_recherche    || "",
    metier_code:        existing?.metier_code        || "",
    seniority:          existing?.seniority          || "",
    annees_experience:  existing?.annees_experience  ?? 0,
    tech_stack:         existing?.tech_stack         || [],
    competences:        existing?.competences        || [],
    langues:            existing?.langues            || [],
    contrats:           existing?.contrats           || [],
    remote:             existing?.remote             || "",
    villes:             existing?.villes             || [],
    pays:               existing?.pays               || [],
    salaire_min_mensuel_eur: existing?.salaire_min_mensuel_eur ?? "",
    description_libre:  existing?.description_libre  || "",
  });

  const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }));
  const toggle = (c) => setForm((f) => ({
    ...f, contrats: f.contrats.includes(c) ? f.contrats.filter(x => x !== c) : [...f.contrats, c],
  }));

  const submit = (e) => {
    e.preventDefault();
    const profile = {
      ...form,
      annees_experience: Number(form.annees_experience) || 0,
      metier_code: form.metier_code || null,
      seniority: form.seniority || null,
      remote: form.remote || null,
      salaire_min_mensuel_eur: form.salaire_min_mensuel_eur ? Number(form.salaire_min_mensuel_eur) : null,
      description_libre: form.description_libre.trim() || null,
      poste_recherche: form.poste_recherche.trim() || "Job seeker",
    };
    setProfile(user.user_id, profile);
    navigate("/recommendations");
  };

  return (
    <div className="relative min-h-[calc(100vh-3.5rem)]">
      <AnimatedBackground variant="app" />
      <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-12">
        <Stepper steps={STEPS} current={1} className="mb-10" />

        <form onSubmit={submit} className="card p-8 sm:p-10 space-y-6 animate-fade-up">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                            bg-brand-500/10 border border-brand-500/20 text-[11px] text-brand-300">
              <Sparkles size={11} /> Step 2 of 3
            </div>
            <h1 className="mt-3 text-3xl font-display font-medium tracking-tight text-text">
              Refine your preferences
            </h1>
            <p className="mt-2 text-text-mute">
              All optional — these sharpen the ranking on top of your CV.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div className="sm:col-span-2">
              <label className="field-label">Target role</label>
              <input className="field-input" placeholder="e.g. Senior Data Engineer"
                     value={form.poste_recherche} onChange={update("poste_recherche")} />
            </div>

            <div>
              <label className="field-label">Job family</label>
              <select className="field-input" value={form.metier_code} onChange={update("metier_code")}>
                {METIERS.map(m => <option key={m.v} value={m.v}>{m.l}</option>)}
              </select>
            </div>
            <div>
              <label className="field-label">Seniority</label>
              <select className="field-input" value={form.seniority} onChange={update("seniority")}>
                <option value="">—</option>
                {SENIORITIES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div>
              <label className="field-label">Years of experience</label>
              <input className="field-input" type="number" min={0} max={50}
                     value={form.annees_experience} onChange={update("annees_experience")} />
            </div>
            <div>
              <label className="field-label">Min salary (€/month)</label>
              <input className="field-input" type="number" min={0} placeholder="e.g. 3000"
                     value={form.salaire_min_mensuel_eur} onChange={update("salaire_min_mensuel_eur")} />
            </div>

            <div className="sm:col-span-2">
              <label className="field-label">Tech stack</label>
              <ChipsInput value={form.tech_stack} onChange={update("tech_stack")}
                          placeholder="Type a skill and press Enter (Python, SQL, AWS…)" />
            </div>

            <div className="sm:col-span-2">
              <label className="field-label">Other skills</label>
              <ChipsInput value={form.competences} onChange={update("competences")}
                          placeholder="ETL, data modeling, dashboarding…" />
            </div>

            <div>
              <label className="field-label">Languages</label>
              <ChipsInput value={form.langues} onChange={update("langues")}
                          placeholder="anglais, français…" />
            </div>
            <div>
              <label className="field-label">Remote preference</label>
              <select className="field-input" value={form.remote} onChange={update("remote")}>
                <option value="">—</option>
                {REMOTES.map(r => <option key={r.v} value={r.v}>{r.l}</option>)}
              </select>
            </div>

            <div>
              <label className="field-label">Cities</label>
              <ChipsInput value={form.villes} onChange={update("villes")}
                          placeholder="Paris, Casablanca…" />
            </div>
            <div>
              <label className="field-label">Countries</label>
              <ChipsInput value={form.pays} onChange={update("pays")}
                          placeholder="France, Maroc…" />
            </div>

            <div className="sm:col-span-2">
              <label className="field-label">Open to contracts</label>
              <div className="flex flex-wrap gap-2">
                {CONTRACTS.map((c) => {
                  const active = form.contrats.includes(c);
                  return (
                    <button type="button" key={c} onClick={() => toggle(c)}
                            className={`chip ${active ? "chip-active" : ""}`}>
                      {c}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="sm:col-span-2">
              <label className="field-label">Free-text bio (helps the semantic match)</label>
              <textarea rows={3} className="field-input"
                        placeholder="A few sentences on focus areas, past achievements, learning goals…"
                        value={form.description_libre} onChange={update("description_libre")} />
            </div>
          </div>

          <div className="pt-2 flex items-center justify-between">
            <Link to="/onboarding/cv" className="btn-ghost">
              <ArrowLeft size={15}/> Back
            </Link>
            <div className="flex gap-2">
              <button type="button" className="btn-secondary"
                      onClick={() => { clearProfile(user.user_id); navigate("/recommendations"); }}>
                Skip
              </button>
              <button type="submit" className="btn-primary btn-lg group">
                See offers <ArrowRight size={15} className="transition-transform group-hover:translate-x-0.5" />
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
