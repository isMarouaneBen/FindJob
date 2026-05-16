import { cn } from "../lib/cn";

function ScoreBar({ label, value }) {
  const pct = Math.round((value || 0) * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-slate-500">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-brand-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right tabular-nums text-slate-600">{pct}</span>
    </div>
  );
}

function Badge({ children, color = "slate" }) {
  const tones = {
    slate:  "bg-slate-100 text-slate-700",
    green:  "bg-emerald-100 text-emerald-700",
    amber:  "bg-amber-100 text-amber-700",
    brand:  "bg-brand-100 text-brand-700",
  };
  return <span className={cn("badge", tones[color])}>{children}</span>;
}

export default function OfferCard({ item }) {
  const { offer, score, breakdown, matched_technologies = [], missing_technologies = [] } = item;
  const scorePct = Math.round((score || 0) * 100);

  return (
    <article className="card p-5 flex flex-col gap-3">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-900 truncate">{offer.poste}</h3>
          <p className="text-sm text-slate-600 truncate">
            {offer.societe_nom} · {offer.ville_nom}, {offer.pays_nom}
          </p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold text-brand-700 tabular-nums">{scorePct}</div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500">match</div>
        </div>
      </header>

      <div className="flex flex-wrap gap-1.5">
        {offer.metier_libelle && offer.metier_libelle !== "Non spécifié" &&
          <Badge color="brand">{offer.metier_libelle}</Badge>}
        {offer.contrat_libelle && offer.contrat_libelle !== "Non spécifié" &&
          <Badge>{offer.contrat_libelle}</Badge>}
        {offer.seniorite_libelle && offer.seniorite_libelle !== "Non spécifié" &&
          <Badge>{offer.seniorite_libelle}</Badge>}
        {offer.teletravail_libelle && offer.teletravail_libelle !== "Non spécifié" &&
          <Badge>{offer.teletravail_libelle}</Badge>}
        {offer.salaire_min_mensuel_eur > 0 &&
          <Badge color="green">{offer.salaire_min_mensuel_eur}–{offer.salaire_max_mensuel_eur} €/mo</Badge>}
      </div>

      {matched_technologies.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-700 mb-1">You match</p>
          <div className="flex flex-wrap gap-1.5">
            {matched_technologies.map((t) => <Badge key={t} color="green">{t}</Badge>)}
          </div>
        </div>
      )}
      {missing_technologies.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-700 mb-1">You may want to learn</p>
          <div className="flex flex-wrap gap-1.5">
            {missing_technologies.slice(0, 6).map((t) => <Badge key={t} color="amber">{t}</Badge>)}
          </div>
        </div>
      )}

      <details className="text-xs">
        <summary className="cursor-pointer text-slate-500 hover:text-slate-700">
          Score breakdown
        </summary>
        <div className="mt-2 space-y-1">
          {Object.entries(breakdown || {}).map(([k, v]) => (
            <ScoreBar key={k} label={k} value={v} />
          ))}
        </div>
      </details>

      <footer className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs text-slate-500">
        <span>{offer.date_publication ?? "—"}</span>
        {offer.url && (
          <a href={offer.url} target="_blank" rel="noreferrer"
             className="text-brand-600 hover:underline font-medium">
            View offer →
          </a>
        )}
      </footer>
    </article>
  );
}
