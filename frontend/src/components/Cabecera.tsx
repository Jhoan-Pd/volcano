"use client";

import {
  BookOpen, FileText, FlaskConical, Home, Layers, LogIn, LogOut, Map as IconoMapa, Moon, Pill, Settings, Siren, Sun,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useAuth } from "@/context/AuthContext";
import { useTema } from "@/context/ThemeContext";

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

function Enlace({ href, icono, children }: { href: string; icono: ReactNode; children: string }) {
  const ruta = usePathname();
  const activo = href === "/" ? ruta === "/" || ruta.startsWith("/municipio") : ruta.startsWith(href);
  return (
    <Link href={href} aria-current={activo ? "page" : undefined}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-[520ms] ease-[var(--ease-fondo)] ${
        activo ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
      {icono}
      <span className="rodar inline-block"><span data-texto={children}>{children}</span></span>
    </Link>
  );
}

/** Navegación principal. Es un componente de cliente porque depende de la sesión y la ruta actual. */
export default function Cabecera() {
  const { usuario, logout, tieneRol } = useAuth();
  const { tema, alternar } = useTema();
  const router = useRouter();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-page/85 backdrop-blur print:static">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5">
          <Logo />
          <div className="leading-tight">
            <p className="titulo-seccion text-[15px]">Predictor de Brotes</p>
            <p className="text-[11px] text-muted">Pasto · Zona Volcán Galeras</p>
          </div>
        </Link>
        <div className="flex items-center gap-1">
          <button onClick={alternar} className="rounded-lg p-2 text-ink-2 hover:bg-surface-2"
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
              <button onClick={() => { logout(); router.push("/"); }}
                className="rounded-lg p-2 text-ink-2 hover:bg-surface-2" aria-label="Cerrar sesión" title="Cerrar sesión">
                <LogOut size={17} />
              </button>
            </div>
          ) : (
            <Enlace href="/login" icono={<LogIn size={16} />}>Ingresar</Enlace>
          )}
        </div>
      </div>
      <nav aria-label="Principal" className="mx-auto max-w-7xl overflow-x-auto px-2 pb-2 sm:px-4 print:hidden">
        <div className="flex w-max items-center gap-1">
          <Enlace href="/" icono={<Home size={16} />}>Inicio</Enlace>
          <Enlace href="/mapa" icono={<IconoMapa size={16} />}>Mapa en vivo</Enlace>
          <Enlace href="/alertas" icono={<Siren size={16} />}>Alertas</Enlace>
          <Enlace href="/simulador" icono={<FlaskConical size={16} />}>Simulador</Enlace>
          <Enlace href="/reportes" icono={<FileText size={16} />}>Reportes</Enlace>
          <Enlace href="/enfermedades" icono={<BookOpen size={16} />}>Enfermedades</Enlace>
          <Enlace href="/patrones" icono={<Layers size={16} />}>Patrones</Enlace>
          {tieneRol("FARMACIA", "ADMIN") && <Enlace href="/farmacia" icono={<Pill size={16} />}>Farmacia</Enlace>}
          {tieneRol("ADMIN") && <Enlace href="/admin" icono={<Settings size={16} />}>Administración</Enlace>}
        </div>
      </nav>
    </header>
  );
}
