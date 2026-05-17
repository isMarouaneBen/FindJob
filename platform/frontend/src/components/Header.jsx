import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { LogOut, Menu, Sparkles, User as UserIcon, X } from "lucide-react";
import Logo from "./Logo";
import { useAuth } from "../auth/AuthContext";
import { cn } from "../lib/cn";

function Avatar({ user, size = 32 }) {
  const initial = (user.full_name || user.fullName || user.email)?.[0]?.toUpperCase();
  if (user.picture) {
    return (
      <img src={user.picture} alt=""
           style={{ width: size, height: size }}
           className="rounded-full ring-1 ring-line-strong object-cover" />
    );
  }
  return (
    <div style={{ width: size, height: size }}
         className="rounded-full bg-gradient-cta grid place-items-center
                    text-white font-medium text-sm ring-1 ring-line-strong">
      {initial}
    </div>
  );
}

function UserMenu({ user, onSignOut }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)}
              className="flex items-center gap-2 p-0.5 rounded-full hover:bg-white/[0.04] transition-colors">
        <Avatar user={user} />
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-64 glass shadow-pop z-50 animate-scale-in origin-top-right p-1.5">
          <div className="px-3 py-2.5 border-b border-line">
            <p className="text-sm font-medium text-text truncate">
              {user.full_name || user.fullName}
            </p>
            <p className="text-xs text-text-dim truncate">{user.email}</p>
          </div>
          <Link to="/profile" onClick={() => setOpen(false)}
                className="flex items-center gap-2 px-3 py-2 mt-1 text-sm rounded-lg
                           text-text-mute hover:bg-white/[0.05] hover:text-text transition-colors">
            <UserIcon size={15} /> Profile preferences
          </Link>
          <button onClick={() => { setOpen(false); onSignOut(); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg
                             text-rose-300 hover:bg-rose-500/10 transition-colors">
            <LogOut size={15} /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Header() {
  const { user, isAuthenticated, signOut } = useAuth();
  const navigate = useNavigate();
  const [mobile, setMobile] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 4);
    window.addEventListener("scroll", on, { passive: true });
    on();
    return () => window.removeEventListener("scroll", on);
  }, []);

  const navLink = ({ isActive }) =>
    cn("px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
       isActive
         ? "text-text bg-white/[0.06]"
         : "text-text-mute hover:text-text hover:bg-white/[0.04]");

  return (
    <header className={cn(
      "sticky top-0 z-40 transition-all border-b",
      scrolled
        ? "bg-bg/80 backdrop-blur-xl border-line"
        : "bg-transparent border-transparent",
    )}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/" className="shrink-0"><Logo /></Link>
          {isAuthenticated && (
            <nav className="hidden md:flex items-center gap-0.5">
              <NavLink to="/recommendations" className={navLink}>
                <span className="inline-flex items-center gap-1.5">
                  <Sparkles size={13} className="text-brand-400" /> Recommendations
                </span>
              </NavLink>
              <NavLink to="/profile" className={navLink}>Profile</NavLink>
              <NavLink to="/onboarding/cv" className={navLink}>CV</NavLink>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <UserMenu user={user} onSignOut={() => { signOut(); navigate("/"); }} />
          ) : (
            <div className="hidden sm:flex items-center gap-1">
              <Link to="/login" className="btn-ghost btn-sm">Sign in</Link>
              <Link to="/register" className="btn-primary btn-sm">Get started</Link>
            </div>
          )}
          {isAuthenticated && (
            <button onClick={() => setMobile(m => !m)}
                    className="md:hidden p-2 rounded-lg hover:bg-white/[0.05] text-text-mute">
              {mobile ? <X size={18}/> : <Menu size={18}/>}
            </button>
          )}
        </div>
      </div>

      {mobile && isAuthenticated && (
        <div className="md:hidden border-t border-line bg-bg/95 backdrop-blur px-3 py-2 space-y-1">
          {[
            ["/recommendations", "Recommendations"],
            ["/profile", "Profile"],
            ["/onboarding/cv", "CV"],
          ].map(([to, label]) => (
            <NavLink key={to} to={to} onClick={() => setMobile(false)} className={navLink}>
              {label}
            </NavLink>
          ))}
        </div>
      )}
    </header>
  );
}
