import { Outlet } from "react-router-dom";
import Header from "./Header";

export default function Layout() {
  return (
    <div className="min-h-full flex flex-col bg-slate-50">
      <Header />
      <main className="flex-1">
        <div className="max-w-6xl mx-auto px-4 py-8">
          <Outlet />
        </div>
      </main>
      <footer className="text-center py-6 text-xs text-slate-500">
        FindJob — pgvector + FastAPI + React
      </footer>
    </div>
  );
}
