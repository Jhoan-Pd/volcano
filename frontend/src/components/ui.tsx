import { CircleAlert, CircleCheck, LoaderCircle, OctagonAlert, TriangleAlert, X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { Nivel } from "../api/tipos";
import { NIVELES } from "../lib/formato";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-line bg-surface shadow-[0_1px_2px_rgba(0,0,0,0.04)] ${className}`}>
      {children}
    </section>
  );
}

export function CardHeader({ titulo, subtitulo, accion, icono }: {
  titulo: string; subtitulo?: ReactNode; accion?: ReactNode; icono?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4 pb-2">
      <div className="flex items-start gap-2.5">
        {icono && <span className="mt-0.5 text-muted">{icono}</span>}
        <div>
          <h2 className="titulo-seccion text-[17px] text-ink">{titulo}</h2>
          {subtitulo && <p className="mt-0.5 text-xs text-muted">{subtitulo}</p>}
        </div>
      </div>
      {accion}
    </header>
  );
}

const ICONOS: Record<Nivel, typeof CircleCheck> = {
  VERDE: CircleCheck, AMARILLO: CircleAlert, NARANJA: TriangleAlert, ROJO: OctagonAlert,
};

/** Indicador de nivel: SIEMPRE icono + texto, nunca solo color (accesibilidad). */
export function NivelChip({ nivel, texto, grande = false }: { nivel: Nivel; texto?: string; grande?: boolean }) {
  const n = NIVELES[nivel] ?? NIVELES.VERDE;
  const Icono = ICONOS[nivel] ?? CircleCheck;
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-semibold ${grande ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs"}`}
      style={{ color: n.tinta, background: `color-mix(in srgb, ${n.color} 16%, transparent)` }}
    >
      <Icono size={grande ? 16 : 13} strokeWidth={2.4} style={{ color: n.color }} aria-hidden />
      {texto ?? n.etiqueta}
    </span>
  );
}

export function Spinner({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted" role="status">
      <LoaderCircle className="animate-spin" size={18} aria-hidden /> {texto}
    </div>
  );
}

export function Aviso({ tipo = "info", children }: { tipo?: "info" | "error" | "ok"; children: ReactNode }) {
  const estilos = {
    info: "border-line bg-surface-2 text-ink-2",
    error: "border-[color-mix(in_srgb,var(--st-rojo)_40%,transparent)] bg-[color-mix(in_srgb,var(--st-rojo)_8%,transparent)] text-[var(--st-rojo-ink)]",
    ok: "border-[color-mix(in_srgb,var(--st-verde)_40%,transparent)] bg-[color-mix(in_srgb,var(--st-verde)_8%,transparent)] text-[var(--st-verde-ink)]",
  }[tipo];
  return <div className={`rounded-xl border px-4 py-3 text-sm ${estilos}`} role={tipo === "error" ? "alert" : "status"}>{children}</div>;
}

type Variante = "primario" | "secundario" | "peligro" | "fantasma";
export function Boton({ variante = "primario", cargando, children, className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; cargando?: boolean }) {
  const base = "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
  const v = {
    primario: "bg-ink text-page hover:opacity-90",
    secundario: "border border-line bg-surface text-ink hover:bg-surface-2",
    peligro: "bg-[var(--st-rojo)] text-white hover:opacity-90",
    fantasma: "text-ink-2 hover:bg-surface-2",
  }[variante];
  return (
    <button className={`${base} ${v} ${className}`} disabled={cargando || props.disabled} {...props}>
      {cargando && <LoaderCircle size={15} className="animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Modal({ abierto, titulo, onCerrar, children, ancho = "max-w-lg" }: {
  abierto: boolean; titulo: string; onCerrar: () => void; children: ReactNode; ancho?: string;
}) {
  useEffect(() => {
    if (!abierto) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [abierto, onCerrar]);
  if (!abierto) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 pt-[8vh]" onMouseDown={onCerrar}>
      <div role="dialog" aria-modal="true" aria-label={titulo}
        className={`w-full ${ancho} rounded-2xl border border-line bg-surface shadow-xl`}
        onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h3 className="titulo-seccion text-lg">{titulo}</h3>
          <button onClick={onCerrar} className="rounded-md p-1 text-muted hover:bg-surface-2" aria-label="Cerrar"><X size={18} /></button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

export const claseInput =
  "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25";

export function Etiqueta({ texto, children, ayuda }: { texto: string; children: ReactNode; ayuda?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-2">{texto}</span>
      {children}
      {ayuda && <span className="mt-1 block text-[11px] text-muted">{ayuda}</span>}
    </label>
  );
}

export function SimuladoBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-line px-2 py-0.5 text-[11px] font-medium text-muted"
      title="Datos de prueba generados por el seed. Se reemplazan al sincronizar SIVIGILA o cargar un CSV con datos oficiales.">
      Datos simulados
    </span>
  );
}
