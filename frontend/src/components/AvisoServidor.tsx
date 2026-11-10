"use client";

import { CircleCheck, CloudOff, LoaderCircle, RotateCw } from "lucide-react";
import { useEffect, useState } from "react";
import { reportarFalloDeRed, useEstadoServidor, vigilarServidor } from "@/lib/estadoServidor";

const DURACION_TIPICA_S = 60;
const PASOS = [
  { hasta: 15, texto: "Render recibe la petición y asigna la instancia" },
  { hasta: 35, texto: "Arrancan la base de datos, las migraciones y el motor gRPC" },
  { hasta: 60, texto: "La API carga los modelos y queda lista" },
  { hasta: Infinity, texto: "Casi listo: algunos arranques tardan un poco más" },
];

/**
 * Aviso global mientras el backend (Render, plan gratis) despierta. Muestra cuánto lleva, en
 * qué paso va el arranque y, al responder la API, confirma y desaparece. Las vistas que
 * fallaron por el arranque se recargan solas con el evento `servidor-listo`.
 */
export default function AvisoServidor() {
  const { fase, desde } = useEstadoServidor();
  const [ahora, setAhora] = useState(() => Date.now());
  const [visibleListo, setVisibleListo] = useState(false);

  useEffect(() => { void vigilarServidor(); }, []);

  useEffect(() => {
    if (fase !== "despertando") return;
    const id = setInterval(() => setAhora(Date.now()), 500);
    return () => clearInterval(id);
  }, [fase]);

  // Tras despertar se muestra «Servidor listo» unos segundos
  const [estuvoDormido, setEstuvoDormido] = useState(false);
  useEffect(() => {
    if (fase === "despertando") setEstuvoDormido(true);
    if (fase === "listo" && estuvoDormido) {
      setVisibleListo(true);
      const id = setTimeout(() => { setVisibleListo(false); setEstuvoDormido(false); }, 3_500);
      return () => clearTimeout(id);
    }
  }, [fase, estuvoDormido]);

  if (fase === "listo" && visibleListo) {
    return (
      <Contenedor tono="ok">
        <CircleCheck size={18} className="shrink-0" aria-hidden />
        <p className="text-sm font-medium">Servidor listo · los datos se están actualizando</p>
      </Contenedor>
    );
  }

  if (fase === "caido") {
    return (
      <Contenedor tono="error">
        <CloudOff size={18} className="shrink-0" aria-hidden />
        <p className="flex-1 text-sm">
          <span className="font-medium">El servidor no respondió en 3 minutos.</span>{" "}
          Las páginas guardadas siguen disponibles; los datos en vivo volverán cuando la API responda.
        </p>
        <button type="button" onClick={reportarFalloDeRed}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-current/30 px-3 py-1.5 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/10">
          <RotateCw size={14} aria-hidden /> Reintentar
        </button>
      </Contenedor>
    );
  }

  if (fase !== "despertando") return null;

  const segundos = Math.max(0, Math.round((ahora - desde) / 1000));
  // Avance estimado: rápido al principio y asintótico al final (nunca llega a 100 % antes de tiempo)
  const avance = Math.min(96, 100 * (1 - Math.exp(-segundos / (DURACION_TIPICA_S / 2.2))));
  const paso = PASOS.find((p) => segundos < p.hasta) ?? PASOS[PASOS.length - 1];

  return (
    <Contenedor tono="info">
      <LoaderCircle size={18} className="shrink-0 animate-spin" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <p className="text-sm font-medium text-ink">
            Despertando el servidor <span className="tabular-nums text-muted">· {segundos} s</span>
          </p>
          <p className="text-xs text-muted">El plan gratuito de Render se duerme tras 15 min sin uso; tarda ~1 minuto.</p>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuemin={0}
          aria-valuemax={100} aria-valuenow={Math.round(avance)} aria-label="Arranque del servidor">
          <div className="h-full rounded-full bg-ink transition-[width] duration-500 ease-out" style={{ width: `${avance}%` }} />
        </div>
        <p className="mt-1.5 text-xs text-ink-2">{paso.texto}</p>
      </div>
    </Contenedor>
  );
}

function Contenedor({ tono, children }: { tono: "info" | "ok" | "error"; children: React.ReactNode }) {
  const estilos = {
    info: "bg-surface text-ink",
    ok: "bg-[color-mix(in_srgb,var(--st-verde)_10%,var(--surface))] text-[var(--st-verde-ink)]",
    error: "bg-[color-mix(in_srgb,var(--st-rojo)_8%,var(--surface))] text-[var(--st-rojo-ink)]",
  }[tono];
  return (
    <div className={`entrar-arriba border-b border-line ${estilos}`} role="status" aria-live="polite">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">{children}</div>
    </div>
  );
}
