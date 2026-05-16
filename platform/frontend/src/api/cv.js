import { apiClient } from "./client";

/** Uploads a CV file to the backend. Returns { cv_id, object_key, bucket }. */
export async function uploadCV(file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post("/cv/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
    },
  });
  return data;
}
