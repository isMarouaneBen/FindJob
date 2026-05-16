import { apiClient } from "./client";

/** Form-based recommendations. `profile` matches the backend ProfileForm schema. */
export async function recommendFromForm({ profile, top_k = 20, only_pays, min_salary_eur, only_remote }) {
  const { data } = await apiClient.post("/recommendations", {
    profile,
    top_k,
    only_pays,
    min_salary_eur,
    only_remote,
  });
  return data;
}

/** CV-based recommendations using a cv_id from POST /cv/upload. */
export async function recommendFromCV(cvId, topK = 20) {
  const { data } = await apiClient.post(
    `/recommendations/from-cv/${encodeURIComponent(cvId)}`,
    null,
    { params: { top_k: topK } },
  );
  return data;
}
