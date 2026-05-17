import { Outlet, useLocation } from "react-router-dom";
import Header from "./Header";
import Footer from "./Footer";

export default function Layout() {
  const { pathname } = useLocation();
  const bare = pathname === "/login" || pathname === "/register";

  if (bare) {
    return (
      <div className="min-h-full bg-bg">
        <Outlet />
      </div>
    );
  }

  return (
    <div className="min-h-full flex flex-col bg-bg">
      <Header />
      <main className="flex-1 relative">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
