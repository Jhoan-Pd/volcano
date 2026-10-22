import { ArrowDownRight, ArrowUpRight, HelpCircle } from "lucide-react";
import { dashboardApi } from "../../api/servicios";
import { fmtNum } from "../../lib/formato";
import { useDatos } from "../../lib/useDatos";
import { Card, CardHeader, NivelChip, Spinner } from "../ui";

/**
 * "¿Por qué este nivel de riesgo?" — explicabilidad local de la predicción.
 * Cada barra es cuántos casos aporta un grupo de variables frente a su valor típico en el
 * municipio (método de oclusión). Hacia la derecha empuja la predicción hacia arriba.
 */
export default function PanelExplicacion({ municipioId, enfermedadId }: { municipioId: number; enfermedadId: number }) {
  const { datos: exp, cargando } = useDatos(() => dashboardApi.explicacion(municipioId, enfermedadId),
    [municipioId, enfermedadId]);

  // Los grupos sin efecto apreciable y sin nada que contar se resumen en una línea
  const todos = exp?.factores ?? [];
  const factores = todos.filter((f) => Math.abs(f.contribucion) >= 0.05 || f.mensaje);
  const sinEfecto = todos.filter((f) => !factores.includes(f)).map((f) => f.grupo.toLowerCase());
  const maximo = Math.max(0.01, ...factores.map((f) => Math.abs(f.contribucion)));
  const globales = Object.entries(exp?.importancia_global?.grupos ?? {}).slice(0, 3);

  return (
    <Card className="min-w-0">
      <CardHeader titulo="¿Por qué este nivel de riesgo?" icono={<HelpCircle size={17} />}
        subtitulo={exp ? `${exp.enfermedad} · ${exp.municipio} · semana ${exp.etiqueta.replace(/^\d+-/, "")}` : "Explicación de la predicción"}
        accion={exp && <NivelChip nivel={exp.nivel} />} />
      <div className="px-5 pb-5">
        {cargando ? <Spinner /> : !exp ? (
          <p className="py-6 text-center text-sm text-muted">Aún no hay predicciones para explicar. Un administrador debe entrenar el modelo.</p>
        ) : (
          <>
            <p className="text-sm text-ink">{exp.resumen}</p>
            <div className="mt-4 space-y-2.5" role="list" aria-label="Aporte de cada grupo de variables, en casos">
              {factores.map((f) => {
                const ancho = `${(Math.abs(f.contribucion) / maximo) * 50}%`;
                const sube = f.contribucion > 0;
                return (
                  <div key={f.grupo} role="listitem">
                    <div className="flex items-baseline justify-between gap-2 text-xs">
                      <span className="font-medium text-ink">{f.grupo}</span>
                      <span className="flex items-center gap-0.5 text-ink-2 tabular">
                        {f.direccion === "sube" ? <ArrowUpRight size={12} aria-hidden /> : f.direccion === "baja" ? <ArrowDownRight size={12} aria-hidden /> : null}
                        {f.contribucion > 0 ? "+" : f.contribucion < 0 ? "−" : ""}{fmtNum(Math.abs(f.contribucion), 1)} casos
                      </span>
                    </div>
                    <div className="relative mt-1 h-2 rounded-full bg-surface-2">
                      <span className="absolute inset-y-[-3px] left-1/2 w-px" style={{ background: "var(--axis)" }} aria-hidden />
                      {f.contribucion !== 0 && (
                        <span className="absolute inset-y-0 rounded-full"
                          style={{ width: ancho, left: sube ? "50%" : undefined, right: sube ? undefined : "50%",
                                   background: sube ? "var(--series-2)" : "var(--series-1)" }} />
                      )}
                    </div>
                    {f.mensaje && <p className="mt-1 text-[11px] text-muted">{f.mensaje}</p>}
                  </div>
                );
              })}
            </div>
            {sinEfecto.length > 0 && <p className="mt-3 text-[11px] text-muted">Sin efecto apreciable esta semana: {sinEfecto.join(", ")}.</p>}
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-3 text-[11px] text-ink-2">
              <span className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-full" style={{ background: "var(--series-2)" }} />Empuja hacia arriba</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-full" style={{ background: "var(--series-1)" }} />Empuja hacia abajo</span>
              {globales.length > 0 && (
                <span className="text-muted">En general, lo que más pesa en el modelo: {globales.map(([g, v]) => `${g.toLowerCase()} (${fmtNum(v, 0)} %)`).join(", ")}.</span>
              )}
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
