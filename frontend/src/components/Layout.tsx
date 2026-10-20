import { LayoutDashboard, LogIn, LogOut, Moon, Pill, Settings, Sun } from "lucide-react";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTema } from "../context/ThemeContext";
import BannerAlertas from "./BannerAlertas";

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--ink)" />
      <path d="M4 25 L13 11 L16 14 L19 10 L28 25 Z" fill="#D4873A" />
      <path d="M13 11 L16 14 L19 10 L17.5 8 L14.5 8 Z" fill="#f2c08a" />
      <circle cx="21" cy="6" r="1.6" fill="#a8a29e" />
      <circle cx="24" cy="4" r="1.1" fill="#a8a29e" />
    </svg>
  );
}

function Enlace({ to, icono, children }: { to: string; icono: ReactNode; children: ReactNode }) {
  return (
    <NavLink to={to} end
      className={({ isActive }) =>
        `inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
          isActive ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
      {icono}<span className="hidden sm:inline">{children}</span>
    </NavLink>
  );
}

export default function Layout() {
  const { usuario, logout, tieneRol } = useAuth();
  const { tema, alternar } = useTema();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-line bg-page/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5">
            <Logo />
            <div className="leading-tight">
              <p className="titulo-seccion text-[15px]">Predictor de Brotes</p>
              <p className="text-[11px] text-muted">Pasto · Zona Volcán Galeras</p>
            </div>
          </Link>
          <nav className="flex items-center gap-1" aria-label="Principal">
            <Enlace to="/" icono={<LayoutDashboard size={16} />}>Dashboard</Enlace>
            {tieneRol("FARMACIA", "ADMIN") && <Enlace to="/farmacia" icono={<Pill size={16} />}>Farmacia</Enlace>}
            {tieneRol("ADMIN") && <Enlace to="/admin" icono={<Settings size={16} />}>Administración</Enlace>}
            <button onClick={alternar} className="ml-1 rounded-lg p-2 text-ink-2 hover:bg-surface-2"
              aria-label={tema === "oscuro" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
              title={tema === "oscuro" ? "Modo claro" : "Modo oscuro"}>
              {tema === "oscuro" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            {usuario ? (
              <div className="ml-1 flex items-center gap-2 border-l border-line pl-3">
                <div className="hidden text-right leading-tight md:block">
                  <p className="text-xs font-medium">{usuario.nombre}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted">{usuario.rol}</p>
                </div>
                <button onClick={() => { logout(); navigate("/"); }}
                  className="rounded-lg p-2 text-ink-2 hover:bg-surface-2" aria-label="Cerrar sesión" title="Cerrar sesión">
                  <LogOut size={17} />
                </button>
              </div>
            ) : (
              <Enlace to="/login" icono={<LogIn size={16} />}>Ingresar</Enlace>
            )}
          </nav>
        </div>
      </header>
      <BannerAlertas />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-col gap-1 px-4 py-5 text-xs text-muted sm:flex-row sm:justify-between sm:px-6">
          <p>Proyecto académico · Programación Orientada a la Web · Nariño, Colombia</p>
          <p>Fuentes: Open-Meteo · Google Trends · Servicio Geológico Colombiano · INS/SIVIGILA (datos.gov.co) · farmacias participantes</p>
        </div>
      </footer>
    </div>
  );
}
