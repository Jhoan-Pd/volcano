import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import type { Nivel, RiesgoEnfermedad } from "../../api/tipos";
import { fmtNum, NIVELES } from "../../lib/formato";
import { NivelChip } from "../ui";

/** Barra del canal endémico: muestra dónde cae la semana actual respecto a los umbrales. */
function BarraCanal({ r }: { r: RiesgoEnfermedad }) {
  const { amarillo, naranja, rojo } = r.umbrales;
  const tope = Math.max(rojo * 1.35, r.casos * 1.1, 1);
  const pct = (v: number) => `${Math.min(100, (v / tope) * 100)}%`;
  const zonas = [
    { desde: 0, hasta: amarillo, color: NIVELES.VERDE.color },
    { desde: amarillo, hasta: naranja, color: NIVELES.AMARILLO.color },
    { desde: naranja, hasta: rojo, color: NIVELES.NARANJA.color },
    { desde: rojo, hasta: tope, color: NIVELES.ROJO.color },
  ];
  return (
    <div className="mt-4" aria-hidden>
      <div className="relative h-2">
        <div className="absolute inset-0 flex gap-[2px] overflow-hidden rounded-full">
          {zonas.map((z, i) => (
            <div key={i} style={{ width: pct(Math.max(0, z.hasta - z.desde)), background: z.color, opacity: 0.35 }} />
          ))}
        </div>
        <div className="absolute -top-1 h-4 w-1 -translate-x-1/2 rounded-full bg-ink ring-2 ring-surface" style={{ left: pct(r.casos) }} />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] text-muted tabular">
        <span>0</span>
        <span>P50 {fmtNum(amarillo, amarillo < 10 ? 1 : 0)}</span>
        <span>P90 {fmtNum(rojo, rojo < 10 ? 1 : 0)}</span>
      </div>
    </div>
  );
}

export default function SemaforoCard({ r, activo, onClick }: { r: RiesgoEnfermedad; activo: boolean; onClick: () => void }) {
  const v = r.variacion_pct;
  const Tendencia = v == null || Math.abs(v) < 5 ? Minus : v > 0 ? TrendingUp : TrendingDown;
  const borde = NIVELES[r.nivel].color;
  return (
    <button onClick={onClick} aria-pressed={activo}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border bg-surface p-4 text-left transition hover:-translate-y-0.5 hover:shadow-md ${
        activo ? "border-ink/40 shadow-md" : "border-line"}`}>
      <span className="absolute inset-x-0 top-0 h-1" style={{ background: borde }} />
      <div className="flex items-start justify-between gap-2">
        <p className="titulo-seccion text-[15px] leading-tight">{r.nombre}</p>
        <NivelChip nivel={r.nivel} />
      </div>
      <div className="mt-3 flex items-end gap-2">
        <span className="cifra text-5xl">{fmtNum(r.casos)}</span>
        <span className="pb-0.5 text-xs text-muted">casos · S{r.semana_epi}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-3 text-xs text-ink-2">
        <span className="inline-flex items-center gap-1">
          <Tendencia size={14} aria-hidden />
          {v != null
            ? `${v > 0 ? "+" : ""}${fmtNum(v, 1)} % vs. semana anterior`
            : r.casos_semana_anterior != null ? `${fmtNum(r.casos_semana_anterior)} casos la semana anterior` : "sin dato previo"}
        </span>
      </div>
      <p className="mt-0.5 text-xs text-muted">{fmtNum(r.tasa_x_100k, 1)} por 100.000 hab.</p>
      <BarraCanal r={r} />
      <div className="mt-4 border-t border-line pt-3">
        {r.prediccion ? (
          <>
            <div className="flex items-center justify-between gap-2">
              <span className="etiqueta text-muted">Próximas 4 semanas</span>
              <NivelChip nivel={r.prediccion.nivel_max as Nivel} />
            </div>
            <p className="mt-1 text-xs text-ink-2 tabular">
              S{r.semana_epi + 1 > 53 ? 1 : r.semana_epi + 1}: {fmtNum(r.prediccion.casos_esperados_h1, r.prediccion.casos_esperados_h1 < 10 ? 1 : 0)} casos
              <span className="text-muted"> ({fmtNum(r.prediccion.limite_inferior_h1, 0)}–{fmtNum(r.prediccion.limite_superior_h1, 0)})</span>
              {r.prediccion.nivel_max !== "VERDE" && <> · pico {r.prediccion.semana_pico.replace(/^\d+-/, "")}</>}
            </p>
          </>
        ) : (
          <p className="text-[11px] text-muted">Predicción pendiente: el modelo aún no se ha entrenado.</p>
        )}
      </div>
    </button>
  );
}
