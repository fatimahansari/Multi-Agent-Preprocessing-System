import { Link, useLocation } from "react-router-dom";
import { useState, useEffect } from "react";

const NAV_LINKS = [
  { to: "/", label: "Home" },
  { to: "/try", label: "Try Now" },
];

export default function Navbar() {
  const { pathname } = useLocation();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
      transition: "all 0.3s ease",
      background: scrolled ? "rgba(7,7,26,0.9)" : "transparent",
      backdropFilter: scrolled ? "blur(16px)" : "none",
      borderBottom: scrolled ? "1px solid rgba(255,255,255,0.06)" : "1px solid transparent",
    }}>
      <div className="container navbar-shell" style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: 64,
      }}>
        <Link to="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontWeight: 700, fontSize: "1.05rem", color: "var(--text)" }}>
            Intelli<span style={{ color: "var(--primary-glow)" }}>Prep</span>
            <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: "0.8rem", marginLeft: 6 }}>MAS</span>
          </span>
        </Link>

        <nav className="navbar-actions" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {NAV_LINKS.map(({ to, label }) => (
            <Link key={to} to={to} style={{
              padding: "6px 16px",
              borderRadius: 50,
              textDecoration: "none",
              fontWeight: 500,
              fontSize: "0.9rem",
              color: pathname === to ? "var(--primary-glow)" : "var(--text-muted)",
              background: pathname === to ? "rgba(249,115,22,0.16)" : "transparent",
              border: pathname === to ? "1px solid rgba(249,115,22,0.35)" : "1px solid transparent",
              transition: "all 0.2s ease",
            }}>{label}</Link>
          ))}
          <Link to="/try" className="btn btn-primary" style={{ padding: "8px 20px", fontSize: "0.85rem", marginLeft: 8 }}>
            Run Pipeline →
          </Link>
        </nav>
      </div>
    </header>
  );
}
