import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { Lock, Mail } from "lucide-react";
import AuthShell from "../components/AuthShell";
import { useAuth } from "../auth/AuthContext";
import { nextStepFor } from "../auth/flow";

export default function Login() {
  const { signIn, signInWithGoogle } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectedFrom = location.state?.from?.pathname;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null); setSubmitting(true);
    try {
      const u = await signIn({ email, password });
      navigate(redirectedFrom || nextStepFor(u.user_id), { replace: true });
    } catch (err) { setError(err.message); }
    finally { setSubmitting(false); }
  };

  const hasGoogle = !!import.meta.env.VITE_GOOGLE_CLIENT_ID;

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to see your tailored offers.">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="field-label" htmlFor="email">Email</label>
          <div className="relative">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
            <input id="email" type="email" required autoComplete="email"
                   value={email} onChange={(e) => setEmail(e.target.value)}
                   className="field-input pl-9.5" style={{ paddingLeft: "2.4rem" }}
                   placeholder="you@example.com" />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between">
            <label className="field-label" htmlFor="password">Password</label>
            <a className="text-xs text-text-dim hover:text-text" href="#">Forgot?</a>
          </div>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
            <input id="password" type="password" required autoComplete="current-password"
                   value={password} onChange={(e) => setPassword(e.target.value)}
                   className="field-input" style={{ paddingLeft: "2.4rem" }}
                   placeholder="••••••••" />
          </div>
        </div>
        {error && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 px-3 py-2 text-sm text-rose-300">
            {error}
          </div>
        )}
        <button type="submit" disabled={submitting} className="btn-primary btn-lg w-full">
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {hasGoogle && (
        <>
          <div className="divider-or my-6">or</div>
          <div className="flex justify-center [color-scheme:light]">
            <GoogleLogin
              size="large" theme="filled_black"
              onSuccess={async (resp) => {
                try {
                  const u = await signInWithGoogle(resp.credential);
                  navigate(redirectedFrom || nextStepFor(u.user_id), { replace: true });
                } catch (err) { setError(err.message); }
              }}
              onError={() => setError("Google sign-in failed.")}
            />
          </div>
        </>
      )}

      <p className="mt-8 text-sm text-text-mute text-center">
        Don't have an account?{" "}
        <Link to="/register" className="btn-link">Create one</Link>
      </p>
    </AuthShell>
  );
}
