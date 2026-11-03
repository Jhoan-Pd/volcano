"use client";

import { ChevronDown, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState, useSyncExternalStore, useTransition } from "react";
import { revalidarAhora } from "@/app/acciones";
import { PATRONES, REVALIDAR_TABLEROS, type Patron } from "@/lib/patrones";

// ---------------------------------------------------------------------------
// "Tiendas" del navegador: en el servidor devuelven null, así el HTML inicial
// nunca depende de la hora del cliente (no hay errores de hidratación).
// ---------------------------------------------------------------------------
function suscribirReloj(cb: () => void) {
  const id = setInterval(cb, 1000);
  return () => clearInterval(id);
}
const leerSegundo = () => Math.floor(Date.now() / 1000) * 1000;
const sinSuscripcion = () => () => {};

/** Time To First Byte de la carga de este documento (ms), o -1 si se llegó navegando en el cliente. */
function leerTTFB() {
  const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  if (!nav) return -1;
  const url = new URL(nav.name);
  return url.pathname + url.search === location.pathname + location.search ? Math.round(nav.responseStart) : -1;
}

const hora = (iso: string) => new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const fecha = (iso: string) => new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
function hace(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `hace ${s} s`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86_400) return `hace ${Math.floor(s / 3600)} h`;
  return `hace ${Math.floor(s / 86_400)} d`;
}

const GENERADO: Record<Patron, string> = {
  SSG: "HTML generado en el build",
  ISR: "HTML generado a las",
  SSR: "HTML generado a las",
  CSR: "Datos recibidos a las",
};

interface Props {
  patron: Patron;
  /** Cuándo se generaron los datos de esta vista (ISO). En CSR, cuándo llegó la respuesta. */
  generadoEn: string | null;
  /** Solo ISR: ruta que se puede revalidar bajo demanda. */
  ruta?: string;
  detalles?: { etiqueta: string; valor: string }[];
  porQue?: string;
}

/**
 * Panel plegable que explica cómo se renderizó la página que se está viendo. Expone
 * `data-render-patron` y `data-render-generado` para que la página /patrones los mida.
 */
export function RenderPanel({ patron, generadoEn, ruta, detalles = [], porQue }: Props) {
  const info = PATRONES[patron];
  const [abierto, setAbierto] = useState(false);
  const ahora = useSyncExternalStore(suscribirReloj, leerSegundo, () => null);
  const ttfb = useSyncExternalStore(sinSuscripcion, leerTTFB, () => null);
  const [revalidando, iniciar] = useTransition();
  const [mensaje, setMensaje] = useState<string | null>(null);

  const generadoMs = generadoEn ? new Date(generadoEn).getTime() : null;
  const edad = ahora !== null && generadoMs !== null ? ahora - generadoMs : null;
  const restante = patron === "ISR" && generadoMs !== null && ahora !== null
    ? generadoMs + REVALIDAR_TABLEROS * 1000 - ahora : null;
  const color = `var(--pat-${patron.toLowerCase()})`;

  return (
    <aside data-render-patron={patron} data-render-generado={generadoEn ?? ""}
      className="rounded-lg print:hidden border bg-surface text-sm"
      style={{ borderColor: `color-mix(in srgb, ${color} 45%, var(--line))` }}>
      <button type="button" onClick={() => setAbierto((v) => !v)} aria-expanded={abierto}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 text-left">
        <span className="rounded-md px-2 py-0.5 font-mono text-xs font-bold text-white" style={{ background: color }}>{patron}</span>
        <strong className="font-medium text-ink">{info.nombre}</strong>
        <span className="min-w-0 flex-1 truncate text-xs text-muted">
          {generadoEn ? `${GENERADO[patron]} ${patron === "SSG" ? fecha(generadoEn) : hora(generadoEn)}` : "Esperando datos…"}
          {edad !== null && ` · ${hace(edad)}`}
        </span>
        <ChevronDown size={15} className={`text-muted transition ${abierto ? "rotate-180" : ""}`} aria-hidden />
      </button>

      {abierto && (
        <div className="entrar border-t border-line px-4 py-3">
          {process.env.NODE_ENV === "development" && (
            <p className="mb-3 rounded-md bg-surface-2 px-3 py-2 text-xs text-ink-2">
              Modo desarrollo: Next.js renderiza todas las páginas en cada petición. Para ver SSG e ISR de verdad usa
              {" "}<code>npm run build && npm start</code> o la versión desplegada.
            </p>
          )}
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Dato etiqueta={GENERADO[patron]} valor={generadoEn ? (patron === "SSG" ? `${fecha(generadoEn)}, ${hora(generadoEn)}` : hora(generadoEn)) : "—"} />
            <Dato etiqueta="Antigüedad del contenido" valor={edad !== null ? hace(edad) : "—"} />
            {patron === "ISR" && (
              <Dato etiqueta={`Ventana de ISR (${REVALIDAR_TABLEROS / 60} min)`}
                valor={restante === null ? "—" : restante > 0 ? `Vigente: vence en ${Math.ceil(restante / 60_000)} min`
                  : "Vencida: la próxima visita la regenera"} />
            )}
            <Dato etiqueta="TTFB de esta carga" valor={ttfb === null ? "—" : ttfb < 0 ? "Recarga para medir" : `${ttfb} ms`} />
            {detalles.map((d) => <Dato key={d.etiqueta} etiqueta={d.etiqueta} valor={d.valor} />)}
          </dl>
          <div className="mt-3 grid gap-1 text-xs text-ink-2 md:grid-cols-3">
            <p><b className="font-medium text-ink">Dónde:</b> {info.donde}</p>
            <p><b className="font-medium text-ink">SEO:</b> {info.seo}</p>
            <p><b className="font-medium text-ink">Frescura:</b> {info.frescura}</p>
          </div>
          <p className="mt-2 text-xs text-ink-2"><b className="font-medium text-ink">¿Por qué {patron} aquí?</b> {porQue ?? info.porQue}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:bg-surface-2">
              <RefreshCw size={13} aria-hidden /> Recargar
            </button>
            {patron === "ISR" && ruta && (
              <button type="button" disabled={revalidando}
                onClick={() => iniciar(async () => {
                  const r = await revalidarAhora(ruta);
                  setMensaje(r.ok ? "Listo: recarga para ver la versión regenerada." : r.mensaje);
                })}
                className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:bg-surface-2 disabled:opacity-50">
                {revalidando ? "Revalidando…" : "Revalidar ahora (bajo demanda)"}
              </button>
            )}
            <span className="text-[11px] text-muted">{mensaje ?? info.pista}</span>
            <Link href="/patrones" className="subrayar ml-auto text-[11px] text-ink-2">Comparar los 4 patrones →</Link>
          </div>
        </div>
      )}
    </aside>
  );
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div>
      <dt className="text-[11px] text-muted">{etiqueta}</dt>
      <dd className="tabular font-medium text-ink">{valor}</dd>
    </div>
  );
}
