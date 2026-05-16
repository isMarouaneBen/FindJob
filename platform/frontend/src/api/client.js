import axios from "axios";

const TOKEN_KEY = "findjob.token";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1",
  timeout: 60_000,
});

// Inject the bearer token on every request when present.
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401 from the backend, clear the stored token. The AuthContext will
// notice on its next render and redirect to /login.
apiClient.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
    }
    return Promise.reject(err);
  },
);

export const TOKEN_STORAGE_KEY = TOKEN_KEY;
export const setStoredToken = (t) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);
export const getStoredToken = () => localStorage.getItem(TOKEN_KEY);
