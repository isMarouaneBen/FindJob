import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Header() {
  const { user, isAuthenticated, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="bg-white border-b border-slate-200">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-slate-900 font-semibold">
          <span className="inline-block w-6 h-6 rounded-md bg-brand-600" aria-hidden />
          <span>FindJob</span>
        </Link>

        <nav className="flex items-center gap-2">
          {isAuthenticated ? (
            <>
              <Link to="/recommendations" className="btn-ghost text-sm">Recommendations</Link>
              <Link to="/profile" className="btn-ghost text-sm">Profile</Link>
              <div className="flex items-center gap-2 ml-2">
                {user.picture
                  ? <img src={user.picture} alt="" className="w-8 h-8 rounded-full" />
                  : <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 grid place-items-center font-semibold">
                      {user.fullName?.[0]?.toUpperCase() ?? "?"}
                    </div>}
                <span className="text-sm text-slate-700 hidden sm:inline">{user.fullName}</span>
                <button
                  onClick={() => { signOut(); navigate("/login"); }}
                  className="btn-secondary text-sm"
                >Sign out</button>
              </div>
            </>
          ) : (
            <>
              <Link to="/login" className="btn-ghost text-sm">Sign in</Link>
              <Link to="/register" className="btn-primary text-sm">Get started</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
