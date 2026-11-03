"use client";

import { Gauge } from "lucide-react";
import { useState } from "react";
import { Boton, Card, CardHeader } from "@/components/ui";
import { ORDEN, type Patron } from "@/lib/patrones";

/** Una página representativa de cada patrón. */
const RUTAS: Record<Patron, string> = {
  SSG: "/enfermedades/ira",
  ISR: "/",
  SSR: "/alertas?estado=todas",
  CSR: "/mapa",
};

const RONDAS = 3;
const PAUSA_MS = 2000;

interface Medicion {
  ttfb: number;
  total: number;
  kb: number;
  generado: string | null;
  datos: number;
  cache: string | null;
}

type Resultados = Record<Patron, Medicion[]>;
const vacio = (): Resultados => ({ SSG: [], ISR: [], SSR: [], CSR: [] });
const esperar = (ms: number) => new Promise((r) => setTimeout(r, ms));
const hora = (iso: string) => new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const promedio = (xs: number[]) => (xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : 0);

/** Pide la página como lo haría un visitante y analiza el HTML que devuelve el servidor. */
async function medir(ruta: string): Promise<Medicion> {
  const t0 = performance.now();
  const r = await fetch(ruta, { cache: "no-store" }); // evita la caché del navegador, no la de la CDN
  const ttfb = performance.now() - t0;
  const html = await r.text();
  const total = performance.now() - t0;
  return {
    ttfb: Math.round(ttfb),
    total: Math.round(total),
    kb: new Blob([html]).size / 1024,
    generado: html.match(/data-render-generado="([^"]+)"/)?.[1] ?? null,
    // Elementos con datos que ya vienen dentro del HTML (municipios, fichas, alertas)
    datos: (html.match(/data-(municipio|ficha|alerta)="/g) ?? []).length,
    cache: r.headers.get("x-vercel-cache") ?? r.headers.get("x-nextjs-cache")
      ?? (r.headers.get("x-nextjs-prerender") ? "PRERENDER" : null),
  };
}

function conclusion(p: Patron, m: Medicion[]) {
  if (m.length === 0) return "";
  const horas = m.map((x) => x.generado);
  if (horas.every((h) => h === null)) return "El HTML llega sin datos: los pide el navegador después.";
  const distintas = new Set(horas).size;
  if (distintas === 1) return "Misma hora en todas las rondas: se sirvió una versión ya generada.";
  if (distintas === m.length) return "Hora distinta en cada ronda: el servidor generó un HTML nuevo por petición.";
  return p === "ISR" ? "Cambió entre rondas: la versión se regeneró." : "La hora cambió en algunas rondas.";
}

export function Medidor() {
  const [resultados, setResultados] = useState<Resultados>(vacio);
  const [progreso, setProgreso] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ejecutar() {
    setResultados(vacio());
    setError(null);
    try {
      for (let ronda = 1; ronda <= RONDAS; ronda++) {
        for (const p of ORDEN) {
          setProgreso(`Ronda ${ronda} de ${RONDAS}: pidiendo ${RUTAS[p]} (${p})…`);
          const m = await medir(RUTAS[p]);
          setResultados((prev) => ({ ...prev, [p]: [...prev[p], m] }));
        }
        if (ronda < RONDAS) {
          setProgreso(`Esperando ${PAUSA_MS / 1000} s antes de la ronda ${ronda + 1}…`);
          await esperar(PAUSA_MS);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error de red");
    } finally {
      setProgreso(null);
    }
  }

  const hay = ORDEN.some((p) => resultados[p].length > 0);
  const promedios = ORDEN.map((p) => ({ p, ms: promedio(resultados[p].map((m) => m.ttfb)) }));
  const maximo = Math.max(1, ...promedios.map((x) => x.ms));

  return (
    <Card>
      <CardHeader titulo="Medición en vivo" icono={<Gauge size={17} />}
        subtitulo={`${RONDAS} rondas con ${PAUSA_MS / 1000} s de pausa. Tu navegador pide una página de cada patrón y analiza el HTML que llega.`}
        accion={<Boton onClick={ejecutar} cargando={progreso !== null}>{hay ? "Medir de nuevo" : "Medir los 4 patrones"}</Boton>} />
      <div className="space-y-4 px-5 pb-5 text-sm">
        {process.env.NODE_ENV === "development" && (
          <p className="rounded-md bg-surface-2 px-3 py-2 text-xs text-ink-2">
            Modo desarrollo: todo se renderiza por petición, así que SSG e ISR se verán como SSR. Mide sobre
            {" "}<code>npm run build && npm start</code> o la versión desplegada.
          </p>
        )}
        {progreso && <p role="status" className="text-xs text-muted">{progreso}</p>}
        {error && <p className="text-xs text-[var(--st-rojo-ink)]">No se pudo completar la medición: {error}</p>}
        {hay && (
          <>
            <figure>
              <figcaption className="text-xs text-muted">Tiempo hasta el primer byte (≈TTFB), promedio en ms · menos es mejor</figcaption>
              <ul className="mt-2 space-y-2">
                {promedios.map(({ p, ms }) => (
                  <li key={p} className="grid grid-cols-[3.5rem_1fr_4.5rem] items-center gap-3"
                    aria-label={`${p}: ${ms} ms en promedio`}>
                    <span className="font-mono text-xs font-bold" style={{ color: `var(--pat-${p.toLowerCase()})` }}>{p}</span>
                    <span className="h-3 rounded-full bg-surface-2">
                      <span className="block h-3 rounded-full" style={{ width: `${Math.max(2, (ms / maximo) * 100)}%`, background: `var(--pat-${p.toLowerCase()})` }} />
                    </span>
                    <span className="tabular text-right text-xs">{ms} ms</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-muted">Ojo con CSR: su HTML llega rápido porque viene vacío; los datos aparecen después, cuando el
                navegador ejecuta el JavaScript y llama a la API. SSR tarda más en responder pero entrega la página completa.</p>
            </figure>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-xs">
                <thead className="border-b border-line text-muted">
                  <tr><th className="py-2 pr-3">Patrón</th><th className="pr-3">≈TTFB por ronda</th><th className="pr-3">HTML</th>
                    <th className="pr-3">Datos en el HTML</th><th className="pr-3">Hora escrita en el HTML</th><th className="pr-3">Caché</th><th>Conclusión</th></tr>
                </thead>
                <tbody>
                  {ORDEN.map((p) => {
                    const m = resultados[p];
                    const u = m[m.length - 1];
                    return (
                      <tr key={p} className="border-b border-line align-top">
                        <td className="py-2 pr-3"><b className="font-mono" style={{ color: `var(--pat-${p.toLowerCase()})` }}>{p}</b><br /><span className="text-muted">{RUTAS[p]}</span></td>
                        <td className="py-2 pr-3 tabular">{m.map((x) => `${x.ttfb} ms`).join(" · ") || "—"}</td>
                        <td className="py-2 pr-3 tabular">{u ? `${u.kb.toFixed(1)} KB` : "—"}</td>
                        <td className="py-2 pr-3">{u ? (u.datos > 0 ? `Sí (${u.datos})` : "No: solo el esqueleto") : "—"}</td>
                        <td className="py-2 pr-3 tabular">{m.map((x) => (x.generado ? hora(x.generado) : "—")).join(" · ") || "—"}</td>
                        <td className="py-2 pr-3">{m.map((x) => x.cache ?? "—").join(" · ") || "—"}</td>
                        <td className="py-2">{conclusion(p, m)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
