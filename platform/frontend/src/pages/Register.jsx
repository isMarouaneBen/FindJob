import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { Lock, Mail, User as UserIcon } from "lucide-react";
import AuthShell from "../components/AuthShell";
import { useAuth } from "../auth/AuthContext";
import { nextStepFor } from "../auth/flow";

export default function Register() {
  const { signUp, signInWithGoogle } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (password.length < 6) { setError("Password must be at least 6 characters."); return; }
    setSubmitting(true);
    try {
      const u = await signUp({ email, password, fullName });
      navigate(nextStepFor(u.user_id), { replace: true });
    } catch (err) { setError(err.message); }
    finally { setSubmitting(false); }
  };

  const hasGoogle = !!import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const padded = { paddingLeft: "2.4rem" };

  return (
    <AuthShell title="Create your account"
               subtitle="Two minutes to your first ranked offer list.">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="field-label" htmlFor="name">Full name</label>
          <div className="relative">
            <UserIcon size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
            <input id="name" type="text" required autoComplete="name"
                   value={fullName} onChange={(e) => setFullName(e.target.value)}
                   className="field-input" style={padded}
                   placeholder="Jane Doe" />
          </div>
        </div>
        <div>
          <label className="field-label" htmlFor="email">Email</label>
          <div className="relative">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
            <input id="email" type="email" required autoComplete="email"
                   value={email} onChange={(e) => setEmail(e.target.value)}
                   className="field-input" style={padded}
                   placeholder="you@example.com" />
          </div>
        </div>
        <div>
          <label className="field-label" htmlFor="password">Password</label>
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dim" />
            <input id="password" type="password" required autoComplete="new-password"
                   value={password} onChange={(e) => setPassword(e.target.value)}
                   className="field-input" style={padded}
                   placeholder="At least 6 characters" />
          </div>
          <p className="field-hint">Bcrypt-hashed server-side. We never see your plain password.</p>
        </div>

        {error && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 px-3 py-2 text-sm text-rose-300">
            {error}
          </div>
        )}

        <button type="submit" disabled={submitting} className="btn-primary btn-lg w-full">
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>

      {hasGoogle && (
        <>
          <div className="divider-or my-6">or</div>
          <div className="flex justify-center [color-scheme:light]">
            <GoogleLogin
              size="large" theme="filled_black" text="signup_with"
              onSuccess={async (resp) => {
                try {
                  const u = await signInWithGoogle(resp.credential);
                  navigate(nextStepFor(u.user_id), { replace: true });
                } catch (err) { setError(err.message); }
              }}
              onError={() => setError("Google sign-up failed.")}
            />
          </div>
        </>
      )}

      <p className="mt-8 text-sm text-text-mute text-center">
        Already have an account?{" "}
        <Link to="/login" className="btn-link">Sign in</Link>
      </p>
    </AuthShell>
  );
}
