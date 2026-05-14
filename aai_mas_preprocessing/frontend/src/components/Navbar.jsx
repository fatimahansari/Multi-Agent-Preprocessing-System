import { Link, useLocation } from "react-router-dom";
import { useState, useEffect } from "react";

const SECTION_LINKS = [
  { hash: "hero", label: "Home" },
  { hash: "about", label: "About" },
  { hash: "workflow", label: "Workflow" },
  { hash: "design", label: "Design" },
  { hash: "stack", label: "Stack" },
  { hash: "cta", label: "Get started" },
  { hash: "team", label: "Team" },
];

export default function Navbar() {
  const { pathname, hash } = useLocation();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const isLanding = pathname === "/";
  const tryActive = pathname === "/try";
  const currentHash = (hash || "").toLowerCase();

  const sectionActive = (h) => {
    if (!isLanding) return false;
    if (h === "hero") return !currentHash || currentHash === "#hero";
    return currentHash === `#${h}`;
  };

  return (
    <header style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
      transition: "all 0.3s ease",
      background: scrolled
        ? "linear-gradient(180deg, rgba(255,253,250,0.94) 0%, rgba(255,241,220,0.88) 100%)"
        : "transparent",
      backdropFilter: scrolled ? "blur(18px)" : "none",
      WebkitBackdropFilter: scrolled ? "blur(18px)" : "none",
      borderBottom: scrolled ? "1px solid rgba(234,108,0,0.14)" : "1px solid transparent",
      boxShadow: scrolled ? "0 8px 32px rgba(234,108,0,0.06)" : "none",
    }}>
      <div className="container navbar-shell" style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        minHeight: 64, gap: 12,
      }}>
        <Link to="/#hero" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <span style={{ fontWeight: 700, fontSize: "1.05rem", color: "var(--text)" }}>
            Intelli<span style={{ color: "var(--primary)" }}>Prep</span>
            <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: "0.8rem", marginLeft: 6 }}>MAS</span>
          </span>
        </Link>

        <nav
          className="navbar-actions"
          aria-label="Primary"
          style={{
            display: "flex", alignItems: "center", justifyContent: "flex-end",
            flexWrap: "wrap", gap: 4, rowGap: 6,
          }}
        >
          {SECTION_LINKS.map(({ hash: h, label }) => {
            const active = sectionActive(h);
            return (
              <Link
                key={h}
                to={`/#${h}`}
                style={{
                  padding: "5px 10px",
                  borderRadius: 50,
                  textDecoration: "none",
                  fontWeight: 500,
                  fontSize: "clamp(0.72rem, 1.8vw, 0.88rem)",
                  color: active ? "var(--primary)" : "var(--text-muted)",
                  background: active ? "rgba(234,108,0,0.10)" : "transparent",
                  border: active ? "1px solid rgba(234,108,0,0.28)" : "1px solid transparent",
                  transition: "all 0.2s ease",
                  whiteSpace: "nowrap",
                }}
              >
                {label}
              </Link>
            );
          })}
          <Link
            to="/try"
            className="btn btn-primary"
            style={{
              padding: "7px 16px",
              fontSize: "clamp(0.75rem, 1.9vw, 0.85rem)",
              marginLeft: 4,
              boxShadow: tryActive ? "0 0 0 2px rgba(234,108,0,0.4), 0 4px 20px rgba(234,88,0,0.32)" : undefined,
            }}
            aria-current={tryActive ? "page" : undefined}
          >
            Try Now
          </Link>
        </nav>
      </div>
    </header>
  );
}
