import { useState } from "react";
import {
  ArrowUpRight, Briefcase, Building2, Calendar, ChevronDown,
  MapPin, Sparkles, Wallet,
} from "lucide-react";
import ScoreRing from "./ScoreRing";
import { cn } from "../lib/cn";

const SIGNAL_META = {
  vector:       { label: "Semantic match" },
  tech_overlap: { label: "Skills overlap" },
  seniority:    { label: "Seniority" },
  contract:     { label: "Contract" },
  location:     { label: "Location" },
  remote:       { label: "Remote" },
  language:     { label: "Languages" },
};

function MetaLine({ icon: Icon, children }) {
  if (!children || children === "Non spécifié") return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px] text-text-mute">
      <Icon size={13} className="text-text-faint" /> {children}
    </span>
  );
}

export default function OfferCard({ item }) {
  const [open, setOpen] = useState(false);
  const { offer, score, breakdown,
          matched_technologies = [], missing_technologies = [] } = item;

  const onMouseMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  return (
    <article
      onMouseMove={onMouseMove}
      className="group glow-on-hover card hover:border-line-strong transition-colors overflow-hidden">
      <div className="p-5 sm:p-6">
        {/* HEADER */}
        <div className="flex items-start gap-4">
          <ScoreRing value={score} size={56} />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-semibold text-text text-[15px] leading-snug truncate">
                {offer.poste}
              </h3>
              {offer.url && (
                <a href={offer.url} target="_blank" rel="noreferrer"
                   className="shrink-0 inline-flex items-center gap-1 text-xs text-brand-300
                              hover:text-brand-200 font-medium opacity-0 group-hover:opacity-100
                              transition-opacity">
                  Open <ArrowUpRight size={13} />
                </a>
              )}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1">
              <MetaLine icon={Building2}>{offer.societe_nom}</MetaLine>
              <MetaLine icon={MapPin}>
                {[offer.ville_nom, offer.pays_nom].filter(Boolean).filter(s => s !== "Non spécifié").join(", ")}
              </MetaLine>
              <MetaLine icon={Calendar}>{offer.date_publication}</MetaLine>
            </div>
          </div>
        </div>

        {/* META BADGES */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {offer.metier_libelle && offer.metier_libelle !== "Non spécifié" &&
            <span className="badge-brand">{offer.metier_libelle}</span>}
          {offer.contrat_libelle && offer.contrat_libelle !== "Non spécifié" &&
            <span className="badge-neutral"><Briefcase size={11}/>{offer.contrat_libelle}</span>}
          {offer.seniorite_libelle && offer.seniorite_libelle !== "Non spécifié" &&
            <span className="badge-neutral">{offer.seniorite_libelle}</span>}
          {offer.teletravail_libelle && offer.teletravail_libelle !== "Non spécifié" &&
            <span className="badge-neutral">{offer.teletravail_libelle}</span>}
          {offer.salaire_min_mensuel_eur > 0 && (
            <span className="badge-success">
              <Wallet size={11}/>
              {offer.salaire_min_mensuel_eur.toLocaleString()}–
              {offer.salaire_max_mensuel_eur.toLocaleString()} €/mo
            </span>
          )}
        </div>

        {/* MATCHED / MISSING */}
        {matched_technologies.length > 0 && (
          <div className="mt-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-dim mb-1.5">
              You match · {matched_technologies.length}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {matched_technologies.map((t) => (
                <span key={t} className="badge-success">{t}</span>
              ))}
            </div>
          </div>
        )}
        {missing_technologies.length > 0 && (
          <div className="mt-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-dim mb-1.5">
              Could be a stretch
            </p>
            <div className="flex flex-wrap gap-1.5">
              {missing_technologies.slice(0, 6).map((t) => (
                <span key={t} className="badge-warn">{t}</span>
              ))}
              {missing_technologies.length > 6 && (
                <span className="badge-neutral">+{missing_technologies.length - 6}</span>
              )}
            </div>
          </div>
        )}

        {/* BREAKDOWN */}
        <button type="button" onClick={() => setOpen(x => !x)}
                className="mt-5 inline-flex items-center gap-1.5 text-xs font-medium
                           text-text-dim hover:text-text transition-colors">
          <Sparkles size={12} className="text-brand-400" />
          Why this offer?
          <ChevronDown size={14} className={cn("transition-transform", open && "rotate-180")} />
        </button>

        {open && (
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 animate-fade-in">
            {Object.entries(breakdown || {}).map(([k, v]) => {
              const meta = SIGNAL_META[k] ?? { label: k };
              const pct = Math.round((v || 0) * 100);
              return (
                <div key={k} className="flex items-center gap-2 text-xs">
                  <span className="w-28 text-text-dim shrink-0">{meta.label}</span>
                  <div className="flex-1 h-1 bg-white/[0.06] rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-cta"
                         style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-8 text-right tabular-nums text-text-mute">{pct}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </article>
  );
}
