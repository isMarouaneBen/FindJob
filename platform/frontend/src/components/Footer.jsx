import Logo from "./Logo";

export default function Footer() {
  return (
    <footer className="border-t border-line bg-bg-subtle/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <Logo size={22} />
        <p className="text-xs text-text-dim">
          © {new Date().getFullYear()} FindJob · Developed by Marouane Ben Haddou - Data Engineering Student
        </p>
        <div className="flex items-center gap-5 text-xs text-text-dim">
          <a className="hover:text-text transition-colors" href="#">Privacy</a>
          <a className="hover:text-text transition-colors" href="#">Terms</a>
          <a className="hover:text-text transition-colors" href="#">Contact</a>
        </div>
      </div>
    </footer>
  );
}
