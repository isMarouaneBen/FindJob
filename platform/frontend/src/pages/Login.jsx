import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { signIn, signInWithGoogle } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const next = location.state?.from?.pathname || "/onboarding/cv";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn({ email, password });
      navigate(next, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const hasGoogle = !!import.meta.env.VITE_GOOGLE_CLIENT_ID;

  return (
    <div className="max-w-md mx-auto card p-8">
      <h1 className="text-2xl font-semibold text-slate-900">Welcome back</h1>
      <p className="text-sm text-slate-600 mt-1">Sign in to see your recommendations.</p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div>
          <label className="field-label" htmlFor="email">Email</label>
          <input id="email" type="email" required autoComplete="email"
                 value={email} onChange={(e) => setEmail(e.target.value)}
                 className="field-input" />
        </div>
        <div>
          <label className="field-label" htmlFor="password">Password</label>
          <input id="password" type="password" required autoComplete="current-password"
                 value={password} onChange={(e) => setPassword(e.target.value)}
                 className="field-input" />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={submitting} className="btn-primary w-full">
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {hasGoogle && (
        <>
          <div className="my-6 flex items-center gap-3 text-xs text-slate-500">
            <div className="flex-1 h-px bg-slate-200" />OR<div className="flex-1 h-px bg-slate-200" />
          </div>
          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={async (resp) => {
                try {
                  await signInWithGoogle(resp.credential);
                  navigate(next, { replace: true });
                } catch (err) {
                  setError(err.message);
                }
              }}
              onError={() => setError("Google sign-in failed.")}
            />
          </div>
        </>
      )}

      <p className="mt-6 text-sm text-slate-600 text-center">
        Don't have an account?{" "}
        <Link to="/register" className="text-brand-600 font-medium hover:underline">Sign up</Link>
      </p>
    </div>
  );
}
