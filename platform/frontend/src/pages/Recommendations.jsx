import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight, FileText, ListFilter, MapPin,
  RefreshCw, Search, SlidersHorizontal, Sparkles,
} from "lucide-react";
import OfferCard from "../components/OfferCard";
import EmptyState from "../components/EmptyState";
import AnimatedBackground from "../components/AnimatedBackground";
import { recommendFromCV, recommendFromForm } from "../api/recommendations";
import { useAuth } from "../auth/AuthContext";
import { getCV, getProfile } from "../auth/flow";

const SORTS = {
  score:  { label: "Best match",   fn: (a, b) => b.score - a.score },
  recent: { label: "Most recent",  fn: (a, b) =>
    new Date(b.offer.date_publication || 0) - new Date(a.offer.date_publication || 0) },
  salary: { label: "Highest salary", fn: (a, b) =>
    (b.offer.salaire_max_mensuel_eur || 0) - (a.offer.salaire_max_mensuel_eur || 0) },
};

function FilterChip({ label, active, onClick, count }) {
  return (
    <button onClick={onClick} className={`chip ${active ? "chip-active" : ""}`}>
      {label} {count != null && <span className="opacity-60">·&nbsp;{count}</span>}
    </button>
  );
}

function StatCard({ label, value, hint }) {
  return (
    <div className="card p-4">
      <p className="text-[10px] uppercase tracking-[0.16em] text-text-faint font-semibold">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-text tabular-nums">{value}</p>
      {hint && <p className="text-xs text-text-dim mt-0.5">{hint}</p>}
    </div>
  );
}

export default function Recommendations() {
  const [topK, setTopK] = useState(20);
  const [sort, setSort] = useState("score");
  const [q, setQ]   = useState("");
  const [country, setCountry] = useState("all");
  const [contract, setContract] = useState("all");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const { user } = useAuth();
  const userId = user?.user_id;
  const cvId = userId ? getCV(userId) : null;
  const profile = useMemo(
    () => (userId ? getProfile(userId) : null),
    [userId],
  );
  const mode = profile ? "form" : cvId ? "cv" : null;

  const query = useQuery({
    queryKey: ["recommendations", userId, mode, cvId, profile, topK],
    enabled: !!mode && !!userId,
    staleTime: 60_000,
    queryFn: () =>
      mode === "form"
        ? recommendFromForm({ profile, top_k: topK })
        : recommendFromCV(cvId, topK),
  });

  const items = query.data?.items ?? [];

  const facets = useMemo(() => {
    const countries = new Map(); const contracts = new Map();
    for (const i of items) {
      const c = i.offer.pays_nom;
      if (c && c !== "Non spécifié") countries.set(c, (countries.get(c) || 0) + 1);
      const k = i.offer.contrat_libelle;
      if (k && k !== "Non spécifié") contracts.set(k, (contracts.get(k) || 0) + 1);
    }
    return { countries: [...countries], contracts: [...contracts] };
  }, [items]);

  const filtered = useMemo(() => {
    let arr = items.filter((i) => {
      if (q && !i.offer.poste.toLowerCase().includes(q.toLowerCase())
           && !(i.offer.societe_nom || "").toLowerCase().includes(q.toLowerCase()))
        return false;
      if (country !== "all" && i.offer.pays_nom !== country) return false;
      if (contract !== "all" && i.offer.contrat_libelle !== contract) return false;
      if (remoteOnly && (i.offer.teletravail_libelle === "Non" || i.offer.teletravail_libelle === "Non spécifié"))
        return false;
      return true;
    });
    arr = [...arr].sort(SORTS[sort].fn);
    return arr;
  }, [items, q, country, contract, remoteOnly, sort]);

  const stats = useMemo(() => {
    if (!items.length) return null;
    const avg = items.reduce((s, i) => s + i.score, 0) / items.length;
    const top = items[0]?.score ?? 0;
    return {
      total: items.length,
      avg: Math.round(avg * 100),
      top: Math.round(top * 100),
      countries: facets.countries.length,
    };
  }, [items, facets]);

  if (!mode) {
    return (
      <div className="relative">
        <AnimatedBackground variant="app" />
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 py-20">
          <EmptyState
            icon={Sparkles}
            title="Nothing to recommend yet"
            description="Upload a CV or fill the profile form to get personalised offers ranked against your skills."
            action={
              <div className="flex gap-2">
                <Link to="/onboarding/cv" className="btn-primary">
                  <FileText size={15}/> Upload CV
                </Link>
                <Link to="/onboarding/profile" className="btn-secondary">
                  <SlidersHorizontal size={15}/> Fill profile
                </Link>
              </div>
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      <AnimatedBackground variant="app" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        {/* HEADER */}
        <div className="flex flex-col gap-5 mb-6">
          <div className="flex items-start sm:items-center justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-3xl sm:text-4xl font-display font-medium tracking-tight text-text">
                Your top matches
              </h1>
              <p className="mt-1.5 text-sm text-text-mute">
                Ranked from your {mode === "form" ? "profile form" : "CV"} ·{" "}
                <Link to={mode === "form" ? "/onboarding/profile" : "/onboarding/cv"}
                      className="btn-link inline-flex items-center gap-1">
                  edit <ArrowUpRight size={11} />
                </Link>
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => query.refetch()} className="btn-secondary btn-sm">
                <RefreshCw size={13} className={query.isFetching ? "animate-spin" : ""} />
                Refresh
              </button>
              <select value={sort} onChange={(e) => setSort(e.target.value)}
                      className="field-input py-1.5 text-sm w-40 cursor-pointer">
                {Object.entries(SORTS).map(([v, m]) => (
                  <option key={v} value={v}>Sort: {m.label}</option>
                ))}
              </select>
              <select value={topK} onChange={(e) => setTopK(Number(e.target.value))}
                      className="field-input py-1.5 text-sm w-24 cursor-pointer">
                {[10, 20, 30, 50, 100].map((n) => <option key={n} value={n}>Top {n}</option>)}
              </select>
            </div>
          </div>

          {/* STAT STRIP */}
          {stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-fade-up">
              <StatCard label="Offers"     value={stats.total} hint="ranked candidates" />
              <StatCard label="Top score"  value={`${stats.top}%`} hint="best match" />
              <StatCard label="Avg score"  value={`${stats.avg}%`} hint="across ranked" />
              <StatCard label="Countries"  value={stats.countries} />
            </div>
          )}

          {/* SEARCH + FILTERS */}
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
              <input value={q} onChange={(e) => setQ(e.target.value)}
                     placeholder="Filter by role or company…"
                     className="field-input pl-9.5" style={{ paddingLeft: "2.4rem" }} />
            </div>
            <button onClick={() => setShowFilters(s => !s)} className="btn-secondary sm:w-auto">
              <ListFilter size={15}/>
              Filters
              {(country !== "all" || contract !== "all" || remoteOnly) && (
                <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-soft" />
              )}
            </button>
          </div>

          {showFilters && (
            <div className="card p-4 animate-fade-in">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint mr-1">
                    <MapPin size={11} className="inline -mt-0.5" /> Country
                  </span>
                  <FilterChip label="All" active={country === "all"} onClick={() => setCountry("all")} />
                  {facets.countries.map(([c, n]) => (
                    <FilterChip key={c} label={c} count={n}
                                active={country === c} onClick={() => setCountry(c)} />
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint mr-1">
                    Contract
                  </span>
                  <FilterChip label="All" active={contract === "all"} onClick={() => setContract("all")} />
                  {facets.contracts.map(([c, n]) => (
                    <FilterChip key={c} label={c} count={n}
                                active={contract === c} onClick={() => setContract(c)} />
                  ))}
                </div>
                <div className="flex items-center gap-2 pt-2 border-t border-line">
                  <label className="inline-flex items-center gap-2 text-sm text-text-mute cursor-pointer">
                    <input type="checkbox" checked={remoteOnly}
                           onChange={(e) => setRemoteOnly(e.target.checked)}
                           className="rounded border-line bg-white/[0.04] text-brand-500 focus:ring-brand-500/30" />
                    Remote-friendly only
                  </label>
                </div>
              </div>
            </div>
          )}

          <div className="text-xs text-text-dim flex items-center gap-2">
            Showing <span className="font-semibold text-text">{filtered.length}</span>
            of {items.length} offers
            {query.isFetching && (
              <span className="ml-1 inline-flex items-center gap-1 text-brand-400">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-soft" />
                updating…
              </span>
            )}
          </div>
        </div>

        {/* CONTENT */}
        {query.isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="card p-6">
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 rounded-full skeleton" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 skeleton w-3/4" />
                    <div className="h-3 skeleton w-1/2" />
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <div className="h-5 w-16 skeleton rounded-full" />
                  <div className="h-5 w-20 skeleton rounded-full" />
                  <div className="h-5 w-12 skeleton rounded-full" />
                </div>
                <div className="mt-4 h-3 skeleton w-1/4" />
              </div>
            ))}
          </div>
        )}

        {query.isError && (
          <div className="card p-5 text-sm text-rose-300 bg-rose-500/10 border-rose-500/30">
            Could not load recommendations: {query.error.response?.data?.detail ?? query.error.message}
          </div>
        )}

        {query.data && filtered.length === 0 && (
          <EmptyState
            icon={Search}
            title="No offers match your filters"
            description="Try removing some filters or widening your preferences."
          />
        )}

        {filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-fade-up">
            {filtered.map((item) => (
              <OfferCard key={item.offer.offer_id} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
