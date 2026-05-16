import { createContext, useContext, useEffect, useMemo, useState } from "react";
import * as authApi from "../api/auth";
import { getStoredToken, setStoredToken } from "../api/client";

const AuthContext = createContext(null);

const toApiError = (err, fallback = "Something went wrong.") =>
  new Error(err.response?.data?.detail ?? err.message ?? fallback);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // Until we've hit /auth/me at least once, gate the UI so protected routes
  // don't bounce people off mid-refresh.
  const [bootstrapping, setBootstrapping] = useState(!!getStoredToken());

  useEffect(() => {
    if (!getStoredToken()) return;
    authApi.fetchMe()
      .then(setUser)
      .catch(() => setStoredToken(null))
      .finally(() => setBootstrapping(false));
  }, []);

  const accept = (token, u) => {
    setStoredToken(token);
    setUser(u);
    return u;
  };

  const value = useMemo(() => ({
    user,
    isAuthenticated: !!user,
    bootstrapping,

    async signUp({ email, password, fullName }) {
      try {
        const { access_token, user: u } = await authApi.register({ email, password, fullName });
        return accept(access_token, u);
      } catch (e) { throw toApiError(e); }
    },

    async signIn({ email, password }) {
      try {
        const { access_token, user: u } = await authApi.login({ email, password });
        return accept(access_token, u);
      } catch (e) { throw toApiError(e); }
    },

    async signInWithGoogle(credential) {
      try {
        const { access_token, user: u } = await authApi.googleSignIn(credential);
        return accept(access_token, u);
      } catch (e) { throw toApiError(e); }
    },

    signOut() {
      setStoredToken(null);
      setUser(null);
    },
  }), [user, bootstrapping]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
};
