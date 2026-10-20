import { BrainCircuit, History, Play } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { mensajeError } from "../../api/cliente";
import { catalogoApi, modeloApi } from "../../api/servicios";
import type { Enfermedad, EstadoEntrenamiento, ModeloEntrenado } from "../../api/tipos";
import { fmtFecha, fmtNum } from "../../lib/formato";
import { Aviso, Boton, claseInput, Spinner } from "../ui";

const NOMBRES_ALGORITMO: Record<string, string> = {
  promedio_movil: "Promedio móvil (línea base)",
  random_forest: "Random Forest",
  gradient_boosting: "Gradient Boosting",
};

const fmtHora = (iso: string) => fmtFecha(iso, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

export default function PanelModelo() {
  const [enfermedades, setEnfermedades] = useState<Enfermedad[]>([]);
  const [historial, setHistorial] = useState<ModeloEntrenado[] | null>(null);
  const [estado, setEstado] = useState<EstadoEntrenamiento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [objetivo, setObjetivo] = useState<number | "">("");
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const sondeo = useRef<number | null>(null);

  const cargar = useCallback(() => {
    modeloApi.historial(undefined, 60).then(setHistorial).catch((e) => setError(mensajeError(e)));
  }, []);

  const detenerSondeo = () => { if (sondeo.current) window.clearInterval(sondeo.current); sondeo.current = null; };

  // El entrenamiento corre en segundo plano en el servidor: se consulta su estado cada 3 s
  const vigilar = useCallback(() => {
    detenerSondeo();
    sondeo.current = window.setInterval(async () => {
      try {
        const e = await modeloApi.estado();
        setEstado(e);
        if (!e.en_curso) { detenerSondeo(); cargar(); }
      } catch { detenerSondeo(); }
    }, 3000);
  }, [cargar]);

  useEffect(() => {
    catalogoApi.enfermedades().then(setEnfermedades).catch(() => undefined);
    cargar();
    modeloApi.estado().then((e) => { setEstado(e); if (e.en_curso) vigilar(); }).catch(() => undefined);
    return detenerSondeo;
  }, [cargar, vigilar]);

  async function reentrenar() {
    setError(null);
    try {
      setEstado(await modeloApi.reentrenar(objetivo === "" ? undefined : objetivo));
      vigilar();
    } catch (e) {
      setError(mensajeError(e));
    }
  }

  const activos = useMemo(() => (historial ?? []).filter((m) => m.activo), [historial]);
  const elegido = activos.find((m) => m.id === seleccionado) ?? activos[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="titulo-seccion text-2xl">Modelo predictivo</h2>
          <p className="max-w-2xl text-xs text-muted">
            Para cada enfermedad se comparan la línea base (promedio móvil de 4 semanas), Random Forest y Gradient Boosting
            con validación temporal (últimas 52 semanas). Se guarda el de menor MAE con su fecha y métricas.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <div className="w-full sm:w-56">
            <select className={claseInput} value={objetivo} aria-label="Enfermedad a reentrenar"
              onChange={(e) => setObjetivo(e.target.value === "" ? "" : Number(e.target.value))}>
              <option value="">Todas las enfermedades</option>
              {enfermedades.filter((e) => e.activo).map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
            </select>
          </div>
          <Boton onClick={reentrenar} cargando={estado?.en_curso}>
            <Play size={15} /> {estado?.en_curso ? "Entrenando…" : "Reentrenar modelo"}
          </Boton>
        </div>
      </div>

      {error && <Aviso tipo="error">{error}</Aviso>}
      {estado && (estado.en_curso || estado.fin) && (
        <Aviso tipo={estado.en_curso ? "info" : estado.errores.length ? "error" : "ok"}>
          {estado.en_curso
            ? `Entrenando desde ${fmtHora(estado.inicio ?? "")}. En el plan gratuito de Render puede tardar unos minutos; puedes seguir usando el panel.`
            : `${estado.mensaje} · terminó ${fmtHora(estado.fin ?? "")}`}
          {estado.errores.length > 0 && <ul className="mt-1 list-disc pl-5">{estado.errores.map((e) => <li key={e}>{e}</li>)}</ul>}
        </Aviso>
      )}

      {historial == null ? <Spinner /> : activos.length === 0 ? (
        <Aviso>Aún no hay modelos entrenados. Pulsa «Reentrenar modelo».</Aviso>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-line bg-surface-2 text-left text-xs text-muted">
                  <th className="px-3 py-2 font-medium">Enfermedad</th>
                  <th className="px-3 py-2 font-medium">Modelo elegido</th>
                  <th className="px-3 py-2 text-right font-medium">MAE base</th>
                  <th className="px-3 py-2 text-right font-medium">MAE modelo</th>
                  <th className="px-3 py-2 text-right font-medium">RMSE base</th>
                  <th className="px-3 py-2 text-right font-medium">RMSE modelo</th>
                  <th className="px-3 py-2 text-right font-medium">Mejora MAE</th>
                  <th className="px-3 py-2 font-medium">Entrenado</th>
                </tr>
              </thead>
              <tbody>
                {activos.map((m) => (
                  <tr key={m.id} onClick={() => setSeleccionado(m.id)}
                    className={`cursor-pointer border-b border-line/70 last:border-0 hover:bg-surface-2 ${elegido?.id === m.id ? "bg-surface-2" : ""}`}>
                    <td className="px-3 py-2 font-medium">{m.enfermedad}</td>
                    <td className="px-3 py-2">{m.algoritmo}</td>
                    <td className="px-3 py-2 text-right tabular">{fmtNum(m.mae_base, 3)}</td>
                    <td className="px-3 py-2 text-right font-semibold tabular">{fmtNum(m.mae_modelo, 3)}</td>
                    <td className="px-3 py-2 text-right tabular">{fmtNum(m.rmse_base, 3)}</td>
                    <td className="px-3 py-2 text-right font-semibold tabular">{fmtNum(m.rmse_modelo, 3)}</td>
                    <td className="px-3 py-2 text-right tabular">
                      {m.mejora_mae_pct == null ? "—" : `${m.mejora_mae_pct > 0 ? "−" : "+"}${fmtNum(Math.abs(m.mejora_mae_pct), 1)} %`}
                    </td>
                    <td className="px-3 py-2 text-xs text-ink-2">{fmtHora(m.fecha_entrenamiento)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="-mt-3 text-[11px] text-muted">
            MAE y RMSE en casos por semana y municipio, promedio de los horizontes de 1 a 4 semanas. «Mejora» = cuánto
            menos se equivoca el modelo que el promedio móvil. Haz clic en una fila para ver su detalle.
          </p>
          {elegido && <DetalleModelo m={elegido} />}
        </>
      )}

      {historial && historial.length > 0 && (
        <div>
          <h3 className="titulo-seccion mb-2 flex items-center gap-2 text-[15px]"><History size={15} className="text-muted" /> Historial de entrenamientos</h3>
          <ul className="divide-y divide-line rounded-xl border border-line text-sm">
            {historial.slice(0, 15).map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span><b className="font-medium">{m.enfermedad}</b> · {m.algoritmo} <span className="text-muted">v{m.version}</span></span>
                <span className="flex items-center gap-3 text-xs text-ink-2 tabular">
                  MAE {fmtNum(m.mae_modelo, 3)} (base {fmtNum(m.mae_base, 3)})
                  {m.activo
                    ? <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent">ACTIVO</span>
                    : <span className="text-muted">{fmtHora(m.fecha_entrenamiento)}</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function DetalleModelo({ m }: { m: ModeloEntrenado }) {
  const comparacion = Object.entries(m.metricas?.resumen ?? {});
  const grupos = Object.entries(m.importancias?.grupos ?? {}).map(([grupo, valor]) => ({ grupo, valor }));
  const mejorMae = Math.min(...comparacion.map(([, v]) => v.mae));

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-xl border border-line p-4">
        <p className="flex items-center gap-2 font-medium"><BrainCircuit size={16} className="text-muted" /> Comparación de algoritmos · {m.enfermedad}</p>
        <p className="mt-0.5 text-xs text-muted">Validación con las últimas {m.metricas?.semanas_prueba ?? 52} semanas · {fmtNum(m.n_muestras)} filas de entrenamiento</p>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              <th className="py-1.5 font-medium">Algoritmo</th>
              <th className="py-1.5 text-right font-medium">MAE</th>
              <th className="py-1.5 text-right font-medium">RMSE</th>
            </tr>
          </thead>
          <tbody>
            {comparacion.map(([clave, v]) => (
              <tr key={clave} className="border-b border-line/60 last:border-0">
                <td className="py-1.5">
                  {NOMBRES_ALGORITMO[clave] ?? clave}
                  {v.mae === mejorMae && <span className="ml-2 rounded-full bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold text-accent">MEJOR</span>}
                </td>
                <td className="py-1.5 text-right tabular">{fmtNum(v.mae, 3)}</td>
                <td className="py-1.5 text-right tabular">{fmtNum(v.rmse, 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="rounded-xl border border-line p-4">
        <p className="font-medium">Importancia de las variables</p>
        <p className="mt-0.5 text-xs text-muted">{m.importancias?.metodo ?? "Permutación"} · porcentaje del total</p>
        {grupos.length === 0 ? <p className="py-6 text-center text-sm text-muted">Sin datos.</p> : (
          <div className="mt-2 h-56">
            <ResponsiveContainer>
              <BarChart data={grupos} layout="vertical" margin={{ top: 4, right: 36, left: 8, bottom: 0 }}>
                <CartesianGrid stroke="var(--line)" horizontal={false} />
                <XAxis type="number" tickLine={false} axisLine={false} unit=" %" domain={[0, "auto"]} />
                <YAxis type="category" dataKey="grupo" tickLine={false} axisLine={false} width={142} />
                <Tooltip cursor={{ fill: "var(--surface-2)" }} formatter={(v) => [`${fmtNum(Number(v), 1)} %`, "Importancia"]}
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, fontSize: 12 }} />
                <Bar dataKey="valor" fill="var(--series-1)" radius={[0, 4, 4, 0]} barSize={14} isAnimationActive={false}
                  label={{ position: "right", fill: "var(--ink-2)", fontSize: 11, formatter: (v: unknown) => `${fmtNum(Number(v), 0)} %` }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
