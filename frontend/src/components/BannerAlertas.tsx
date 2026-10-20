import { ChevronDown, X } from "lucide-react";
import { useEffect, useState } from "react";
import { alertaApi } from "../api/servicios";
import type { Alerta } from "../api/tipos";
import { NIVELES } from "../lib/formato";
import { NivelChip } from "./ui";

const CLAVE = "alertas-ocultas";

function leerOcultas(): string {
  try { return sessionStorage.getItem(CLAVE) ?? ""; } catch { return ""; }
}

/**
 * Banner de alertas tempranas: aparece en todas las páginas cuando hay riesgo alto o muy
 * alto (observado o predicho). Se puede ocultar durante la sesión; si cambian las alertas
 * vuelve a aparecer.
 */
export default function BannerAlertas() {
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [abierto, setAbierto] = useState(false);
  const [ocultas, setOcultas] = useState(leerOcultas);

  useEffect(() => {
    const cargar = () => alertaApi.activas().then(setAlertas).catch(() => undefined);
    cargar();
    const id = window.setInterval(cargar, 5 * 60_000);
    return () => window.clearInterval(id);
  }, []);

  const firma = alertas.map((a) => `${a.id}:${a.nivel_riesgo}`).join(",");
  if (!alertas.length || ocultas === firma) return null;

  const hayRojo = alertas.some((a) => a.nivel_riesgo === "ROJO");
  const nivel = hayRojo ? "ROJO" : "NARANJA";
  const municipios = [...new Set(alertas.map((a) => a.municipio))];

  function ocultar() {
    try { sessionStorage.setItem(CLAVE, firma); } catch { /* sin almacenamiento: solo se oculta ahora */ }
    setOcultas(firma);
  }

  return (
    <div role="alert" className="entrar-arriba border-b"
      style={{ borderColor: `color-mix(in srgb, ${NIVELES[nivel].color} 35%, transparent)`,
               background: `color-mix(in srgb, ${NIVELES[nivel].color} 9%, var(--page))` }}>
      <div className="mx-auto max-w-7xl px-4 py-2.5 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline-flex">
            <NivelChip nivel={nivel} texto={hayRojo ? "Alerta: riesgo muy alto" : "Alerta: riesgo alto"} />
          </span>
          <span className="sm:hidden"><NivelChip nivel={nivel} texto={hayRojo ? "Muy alto" : "Alto"} /></span>
          <p className="min-w-0 flex-1 truncate text-sm text-ink">
            <b className="font-semibold">{alertas.length} alerta{alertas.length > 1 ? "s" : ""} temprana{alertas.length > 1 ? "s" : ""}</b>
            <span className="text-ink-2"> en {municipios.join(", ")}</span>
          </p>
          <button onClick={() => setAbierto((v) => !v)} aria-expanded={abierto}
            className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-ink-2 hover:bg-surface-2">
            <span className="hidden sm:inline">{abierto ? "Ocultar detalle" : "Ver detalle"}</span>
            <span className="sm:hidden">{abierto ? "Ocultar" : "Ver"}</span>
            <ChevronDown size={14} className={`transition ${abierto ? "rotate-180" : ""}`} />
          </button>
          <button onClick={ocultar} className="shrink-0 rounded-md p-1 text-muted hover:bg-surface-2" aria-label="Ocultar alertas">
            <X size={16} />
          </button>
        </div>
        {abierto && (
          <ul className="mt-2 space-y-1.5 pb-1">
            {alertas.map((a, i) => (
              <li key={a.id} style={{ animationDelay: `${i * 60}ms` }} className="entrar flex flex-col gap-1 rounded-lg bg-surface/70 px-3 py-2 text-[13px] sm:flex-row sm:items-center sm:gap-3">
                <span className="flex shrink-0 items-center gap-2">
                  <NivelChip nivel={a.nivel_riesgo} />
                  <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
                    {a.origen === "OBSERVADO" ? "Observado" : "Predicho"}
                  </span>
                </span>
                <span className="text-ink-2">{a.mensaje}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
