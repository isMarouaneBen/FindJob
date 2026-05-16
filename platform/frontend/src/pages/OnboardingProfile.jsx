import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const PROFILE_KEY = "findjob.profile";

const METIERS = [
  ["", "—"],
  ["DATA_ENG", "Data Engineer"],
  ["DATA_SCI", "Data Scientist / ML"],
  ["DATA_ANA", "Data Analyst"],
  ["BI",       "Business Intelligence"],
  ["DATA_ARCH","Data Architect"],
  ["DEVOPS",   "DevOps / SRE"],
  ["CLOUD",    "Cloud Engineer"],
  ["CYBER",    "Cybersécurité"],
  ["DEV_BACK", "Backend Developer"],
  ["DEV_FRONT","Frontend Developer"],
  ["DEV_FULL", "Fullstack Developer"],
  ["DEV_MOBILE","Mobile Developer"],
  ["ADMIN_SYS","Admin Système / Réseau"],
  ["CONSULT",  "Consultant"],
];
const SENIORITIES = ["", "Stage", "Alternance", "Junior", "Intermediaire", "Confirme", "Senior", "Expert"];
const REMOTES    = ["", "Non", "Hybride", "Total", "Possible"];
const CONTRACTS  = ["CDI", "CDD", "Stage", "Alternance", "Freelance", "Interim"];

const splitList = (s) =>
  s.split(",").map((x) => x.trim()).filter(Boolean);

export default function OnboardingProfile() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    poste_recherche: "",
    metier_code: "",
    seniority: "",
    annees_experience: 0,
    tech_stack: "",
    competences: "",
    langues: "",
    contrats: [],
    remote: "",
    villes: "",
    pays: "",
    salaire_min_mensuel_eur: "",
    description_libre: "",
  });

  const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const toggleContract = (c) =>
    setForm((f) => ({
      ...f,
      contrats: f.contrats.includes(c)
        ? f.contrats.filter((x) => x !== c)
        : [...f.contrats, c],
    }));

  const submit = (e) => {
    e.preventDefault();
    const profile = {
      poste_recherche: form.poste_recherche.trim() || "Job seeker",
      metier_code: form.metier_code || null,
      seniority: form.seniority || null,
      annees_experience: Number(form.annees_experience) || 0,
      tech_stack: splitList(form.tech_stack),
      competences: splitList(form.competences),
      langues: splitList(form.langues),
      contrats: form.contrats,
      remote: form.remote || null,
      villes: splitList(form.villes),
      pays: splitList(form.pays),
      salaire_min_mensuel_eur: form.salaire_min_mensuel_eur ? Number(form.salaire_min_mensuel_eur) : null,
      description_libre: form.description_libre.trim() || null,
    };
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    navigate("/recommendations");
  };

  return (
    <form onSubmit={submit} className="max-w-3xl mx-auto card p-6 space-y-5">
      <ol className="flex items-center text-xs text-slate-500">
        <li>1 · Upload CV</li>
        <span className="mx-3 text-slate-300">›</span>
        <li className="font-semibold text-brand-700">2 · Profile</li>
        <span className="mx-3 text-slate-300">›</span>
        <li>3 · Recommendations</li>
      </ol>

      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Refine your preferences</h1>
        <p className="text-sm text-slate-600 mt-1">
          All fields are optional. They sharpen the ranking on top of your CV.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="sm:col-span-2">
          <label className="field-label">Target role</label>
          <input className="field-input" placeholder="e.g. Data Engineer"
                 value={form.poste_recherche} onChange={update("poste_recherche")} />
        </div>

        <div>
          <label className="field-label">Job family</label>
          <select className="field-input" value={form.metier_code} onChange={update("metier_code")}>
            {METIERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>

        <div>
          <label className="field-label">Seniority</label>
          <select className="field-input" value={form.seniority} onChange={update("seniority")}>
            {SENIORITIES.map((s) => <option key={s} value={s}>{s || "—"}</option>)}
          </select>
        </div>

        <div>
          <label className="field-label">Years of experience</label>
          <input className="field-input" type="number" min={0} max={50}
                 value={form.annees_experience} onChange={update("annees_experience")} />
        </div>

        <div>
          <label className="field-label">Min salary (€/month)</label>
          <input className="field-input" type="number" min={0}
                 placeholder="e.g. 3000"
                 value={form.salaire_min_mensuel_eur} onChange={update("salaire_min_mensuel_eur")} />
        </div>

        <div className="sm:col-span-2">
          <label className="field-label">Tech stack <span className="text-slate-400">(comma-separated)</span></label>
          <input className="field-input" placeholder="Python, SQL, Spark, AWS, Airflow"
                 value={form.tech_stack} onChange={update("tech_stack")} />
        </div>

        <div className="sm:col-span-2">
          <label className="field-label">Other skills</label>
          <input className="field-input" placeholder="ETL, data modeling, dashboarding"
                 value={form.competences} onChange={update("competences")} />
        </div>

        <div>
          <label className="field-label">Languages</label>
          <input className="field-input" placeholder="français, anglais"
                 value={form.langues} onChange={update("langues")} />
        </div>

        <div>
          <label className="field-label">Remote preference</label>
          <select className="field-input" value={form.remote} onChange={update("remote")}>
            {REMOTES.map((r) => <option key={r} value={r}>{r || "—"}</option>)}
          </select>
        </div>

        <div>
          <label className="field-label">Cities</label>
          <input className="field-input" placeholder="Paris, Casablanca"
                 value={form.villes} onChange={update("villes")} />
        </div>

        <div>
          <label className="field-label">Countries</label>
          <input className="field-input" placeholder="France, Maroc"
                 value={form.pays} onChange={update("pays")} />
        </div>

        <div className="sm:col-span-2">
          <label className="field-label">Contracts open to</label>
          <div className="flex flex-wrap gap-2 mt-1">
            {CONTRACTS.map((c) => (
              <button type="button" key={c} onClick={() => toggleContract(c)}
                      className={`badge cursor-pointer ${
                        form.contrats.includes(c)
                          ? "bg-brand-600 text-white"
                          : "bg-slate-100 text-slate-700"
                      }`}>
                {c}
              </button>
            ))}
          </div>
        </div>

        <div className="sm:col-span-2">
          <label className="field-label">Free-text bio</label>
          <textarea rows={3} className="field-input"
                    placeholder="Anything else relevant — past achievements, focus areas, goals…"
                    value={form.description_libre} onChange={update("description_libre")} />
        </div>
      </div>

      <div className="flex items-center justify-between pt-2">
        <Link to="/onboarding/cv" className="btn-ghost">Back</Link>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => { localStorage.removeItem(PROFILE_KEY); navigate("/recommendations"); }}
            className="btn-secondary"
          >Skip</button>
          <button type="submit" className="btn-primary">See offers</button>
        </div>
      </div>
    </form>
  );
}
