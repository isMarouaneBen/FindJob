import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import OfferCard from "../components/OfferCard";
import { recommendFromCV, recommendFromForm } from "../api/recommendations";

const CV_KEY = "findjob.cvId";
const PROFILE_KEY = "findjob.profile";

export default function Recommendations() {
  const [topK, setTopK] = useState(10);
  const cvId = localStorage.getItem(CV_KEY);
  const profile = useMemo(() => {
    try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || "null"); }
    catch { return null; }
  }, []);

  // Prefer the structured profile if the user filled it; fall back to CV.
  const mode = profile ? "form" : cvId ? "cv" : null;

  const query = useQuery({
    queryKey: ["recommendations", mode, cvId, profile, topK],
    enabled: !!mode,
    staleTime: 60_000,
    queryFn: () =>
      mode === "form"
        ? recommendFromForm({ profile, top_k: topK })
        : recommendFromCV(cvId, topK),
  });

  if (!mode) {
    return (
      <div className="max-w-2xl mx-auto card p-8 text-center">
        <h1 className="text-xl font-semibold text-slate-900">Nothing to recommend yet</h1>
        <p className="text-sm text-slate-600 mt-1">
          Upload a CV or fill the profile form to get personalised offers.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Link to="/onboarding/cv" className="btn-primary">Upload CV</Link>
          <Link to="/onboarding/profile" className="btn-secondary">Fill profile</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Your top matches</h1>
          <p className="text-sm text-slate-600 mt-1">
            Based on your {mode === "form" ? "profile" : "CV"} ·{" "}
            <Link to={mode === "form" ? "/onboarding/profile" : "/onboarding/cv"}
                  className="text-brand-600 hover:underline">edit</Link>
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="topk" className="text-slate-600">Show</label>
          <select id="topk" className="field-input py-1 w-20"
                  value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
            {[5, 10, 20, 30, 50].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </header>

      {query.isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) =>
            <div key={i} className="card p-6 animate-pulse">
              <div className="h-4 bg-slate-200 rounded w-2/3 mb-3" />
              <div className="h-3 bg-slate-200 rounded w-1/2 mb-5" />
              <div className="h-3 bg-slate-100 rounded w-full mb-2" />
              <div className="h-3 bg-slate-100 rounded w-5/6" />
            </div>
          )}
        </div>
      )}

      {query.isError && (
        <div className="card p-6 text-sm text-red-700 bg-red-50 border-red-200">
          Could not load recommendations: {query.error.response?.data?.detail ?? query.error.message}
        </div>
      )}

      {query.data && query.data.count === 0 && (
        <div className="card p-8 text-center text-slate-600">
          No offers matched. Try widening your filters or re-uploading your CV.
        </div>
      )}

      {query.data && query.data.items?.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {query.data.items.map((item) => (
            <OfferCard key={item.offer.offer_id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
