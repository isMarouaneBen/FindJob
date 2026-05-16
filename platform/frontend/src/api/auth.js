import { apiClient } from "./client";

export async function register({ email, password, fullName }) {
  const { data } = await apiClient.post("/auth/register", {
    email, password, full_name: fullName,
  });
  return data; // { access_token, token_type, user }
}

export async function login({ email, password }) {
  const { data } = await apiClient.post("/auth/login", { email, password });
  return data;
}

export async function googleSignIn(credential) {
  const { data } = await apiClient.post("/auth/google", { credential });
  return data;
}

export async function fetchMe() {
  const { data } = await apiClient.get("/auth/me");
  return data;
}
