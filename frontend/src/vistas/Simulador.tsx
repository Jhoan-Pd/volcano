"use client";

import { Cpu, FlaskConical, Grid3x3, RotateCcw, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, ErrorBar, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { mensajeError } from "../api/cliente";
import { catalogoApi, motorApi, urlSimulador } from "../api/servicios";
import type { Escenario, PronosticoMotor } from "../api/tipos";
import { RenderPanel } from "../components/render/RenderPanel";
import { Aviso, Boton, Card, CardHeader, claseInput, Etiqueta, NivelChip, Spinner } from "../components/ui";
import { fmtNum, NIVELES } from "../lib/formato";
import { useDatos } from "../lib/useDatos";
import { useFps } from "../lib/useFps";
import { useMatrizSensibilidad } from "../lib/useMatrizSensibilidad";
import { useSimulador } from "../lib/useSimulador";
import type { CampoEscenario } from "../workers/sensibilidad/mensajes";

type Ajustes = Omit<Escenario, "id" | "municipio_id" | "enfermedad_id">;
const SIN_CAMBIOS: Ajustes = { delta_temperatura_c: 0, cambio_lluvia_pct: 0, cambio_busquedas_pct: 0, cambio_farmacias_pct: 0, ceniza: false };

const CONTROLES: { campo: CampoEscenario; etiqueta: string; min: number; max: number; paso: number; unidad: string; grilla: number[] }[] = [
  { campo: "delta_temperatura_c", etiqueta: "Temperatura", min: -5, max: 5, paso: 0.5, unidad: " °C", grilla: [-3, -2, -1, 0, 1, 2, 3] },
  { campo: "cambio_lluvia_pct", etiqueta: "Lluvia", min: -100, max: 200, paso: 10, unidad: " %", grilla: [-80, -40, 0, 40, 80, 120, 160] },
  { campo: "cambio_busquedas_pct", etiqueta: "Búsquedas de síntomas", min: -100, max: 300, paso: 10, unidad: " %", grilla: [-60, -30, 0, 50, 100, 150, 200] },
  { campo: "cambio_farmacias_pct", etiqueta: "Ventas en farmacias", min: -100, max: 300, paso: 10, unidad: " %", grilla: [-60, -30, 0, 50, 100, 150, 200] },
];
const control = (c: CampoEscenario) => CONTROLES.find((x) => x.campo === c)!;
const conSigno = (v: number, unidad: string) => `${v > 0 ? "+" : ""}${fmtNum(v, Number.isInteger(v) ? 0 : 1)}${unidad}`;

export default function Simulador() {
  const municipios = useDatos(() => catalogoApi.municipios().then((ms) => ms.filter((m) => m.activo)), []);
  const enfermedades = useDatos(() => catalogoApi.enfermedades().then((es) => es.filter((e) => e.activo)), []);
  const [municipioId, setMunicipioId] = useState<number | null>(null);
  const [enfermedadId, setEnfermedadId] = useState<number | null>(null);
  const [ajustes, setAjustes] = useState<Ajustes>(SIN_CAMBIOS);
  const sim = useSimulador();

  useEffect(() => { if (municipioId == null && municipios.datos?.length) setMunicipioId(municipios.datos[0].id); }, [municipios.datos, municipioId]);
  useEffect(() => { if (enfermedadId == null && enfermedades.datos?.length) setEnfermedadId(enfermedades.datos[0].id); }, [enfermedades.datos, enfermedadId]);

  // Cada cambio envía un escenario por el WebSocket (con 120 ms de pausa para no saturar al mover un control)
  const { enviar, estado } = sim;
  useEffect(() => {
    if (municipioId == null || enfermedadId == null || estado !== "abierto") return;
    const t = setTimeout(() => enviar({ municipio_id: municipioId, enfermedad_id: enfermedadId, ...ajustes }), 120);
    return () => clearTimeout(t);
  }, [municipioId, enfermedadId, ajustes, estado, enviar]);

  const r = sim.resultado;
  const datosGrafica = useMemo(() => (r?.escenario ?? []).map((p, i) => {
    const b = r?.base?.[i];
    return {
      semana: p.etiqueta.replace(/^\d+-/, ""), base: b?.casos_esperados ?? 0, escenario: p.casos_esperados,
      error: [p.casos_esperados - p.limite_inferior, p.limite_superior - p.casos_esperados],
    };
  }), [r]);

  return (
    <div className="space-y-5">
      <RenderPanel patron="CSR" generadoEn={sim.recibidoEn}
        porQue="El simulador es una conversación en tiempo real con el motor: cada control envía un mensaje por WebSocket y la respuesta se pinta al llegar. No tiene sentido renderizarlo en el servidor."
        detalles={[
          { etiqueta: "WebSocket ↔ gRPC bidireccional", valor: sim.estado },
          { etiqueta: "Mensajes enviados / recibidos", valor: `${sim.cuenta.enviados} / ${sim.cuenta.recibidos}` },
        ]} />

      <header>
        <p className="titulo-seccion text-[13px] text-muted">¿Qué pasa si…?</p>
        <h1 className="titulo-display mt-2 text-5xl sm:text-6xl">Simulador de escenarios</h1>
        <p className="mt-2 max-w-3xl text-ink-2">Cambia las señales de la última semana y mira cómo responde el modelo. No es un pronóstico del clima:
          sirve para entender a qué es sensible la predicción. El modelo no se reentrena; se vuelve a aplicar con los valores modificados.</p>
      </header>

      {sim.error && (
        <Aviso tipo="error">
          {sim.error}{" "}
          <button type="button" className="underline" onClick={sim.reconectar}>Reconectar</button>
        </Aviso>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="min-w-0 lg:col-span-2">
          <CardHeader titulo="Escenario" icono={<FlaskConical size={17} />}
            accion={<Boton variante="fantasma" onClick={() => setAjustes(SIN_CAMBIOS)}><RotateCcw size={14} /> Sin cambios</Boton>} />
          <div className="space-y-4 px-5 pb-5">
            <div className="grid grid-cols-2 gap-3">
              <Etiqueta texto="Municipio">
                <select className={claseInput} value={municipioId ?? ""} onChange={(e) => setMunicipioId(Number(e.target.value))}>
                  {municipios.datos?.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
                </select>
              </Etiqueta>
              <Etiqueta texto="Enfermedad">
                <select className={claseInput} value={enfermedadId ?? ""} onChange={(e) => setEnfermedadId(Number(e.target.value))}>
                  {enfermedades.datos?.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
                </select>
              </Etiqueta>
            </div>
            {CONTROLES.map((c) => (
              <label key={c.campo} className="block">
                <span className="flex items-baseline justify-between text-xs">
                  <span className="font-medium text-ink-2">{c.etiqueta}</span>
                  <span className="tabular font-medium">{conSigno(ajustes[c.campo], c.unidad)}</span>
                </span>
                <input type="range" min={c.min} max={c.max} step={c.paso} value={ajustes[c.campo]}
                  onChange={(e) => setAjustes((a) => ({ ...a, [c.campo]: Number(e.target.value) }))}
                  className="mt-1 w-full accent-[var(--accent)]" />
              </label>
            ))}
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={ajustes.ceniza} className="accent-[var(--accent)]"
                onChange={(e) => setAjustes((a) => ({ ...a, ceniza: e.target.checked }))} />
              Caída de ceniza esta semana
            </label>
          </div>
        </Card>

        <Card className="min-w-0 lg:col-span-3">
          <CardHeader titulo="Resultado" icono={<Zap size={17} />}
            subtitulo={r?.duracion_ms != null ? `Motor: ${fmtNum(r.duracion_ms, 1)} ms · ida y vuelta: ${sim.idaVueltaMs ?? "—"} ms` : "Esperando la primera respuesta…"}
            accion={r?.nivel_max && <NivelChip nivel={r.nivel_max} />} />
          <div className="px-5 pb-5">
            {!r ? <Spinner texto={sim.estado === "abierto" ? "Calculando…" : "Conectando con el simulador…"} /> : r.error ? (
              <Aviso tipo="error">{r.error}</Aviso>
            ) : (
              <>
                <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
                  <div>
                    <p className="text-xs text-muted">Variación en 4 semanas</p>
                    <p className="cifra text-4xl tabular">{conSigno(r.variacion_pct ?? 0, " %")}</p>
                  </div>
                  <p className="min-w-0 flex-1 text-sm text-ink-2">{r.resumen}</p>
                </div>
                <div className="mt-4 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={datosGrafica} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                      <CartesianGrid stroke="var(--line)" vertical={false} />
                      <XAxis dataKey="semana" tickLine={false} axisLine={{ stroke: "var(--axis)" }} />
                      <YAxis tickLine={false} axisLine={false} allowDecimals={false} />
                      <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }}
                        formatter={(v) => fmtNum(Number(v), 1)} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="base" name="Sin cambios" fill="var(--axis)" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="escenario" name="Escenario" fill="var(--series-2)" radius={[4, 4, 0, 0]}>
                        <ErrorBar dataKey="error" width={4} stroke="var(--ink-2)" />
                      </Bar>
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-1 text-[11px] text-muted">Casos esperados por semana; la línea es el intervalo del 80 % del escenario.</p>
              </>
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        {municipioId != null && enfermedadId != null && (
          <PronosticoUnario municipioId={municipioId} enfermedadId={enfermedadId} />
        )}
        {municipioId != null && enfermedadId != null && (
          <MatrizSensibilidad base={{ municipio_id: municipioId, enfermedad_id: enfermedadId, ...ajustes }} />
        )}
      </div>
    </div>
  );
}

/** Llamada unary al motor: pronóstico calculado al momento con el modelo en memoria. */
function PronosticoUnario({ municipioId, enfermedadId }: { municipioId: number; enfermedadId: number }) {
  const [p, setP] = useState<PronosticoMotor | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  useEffect(() => { setP(null); setError(null); }, [municipioId, enfermedadId]);

  async function pedir() {
    setCargando(true); setError(null);
    try { setP(await motorApi.pronostico(municipioId, enfermedadId)); } catch (e) { setError(mensajeError(e)); } finally { setCargando(false); }
  }

  return (
    <Card className="min-w-0 lg:col-span-2">
      <CardHeader titulo="Pronóstico al momento" icono={<Cpu size={17} />} subtitulo="RPC unary Predecir: una petición, una respuesta"
        accion={<Boton variante="secundario" onClick={pedir} cargando={cargando}>Pedir</Boton>} />
      <div className="px-5 pb-5 text-sm">
        {error && <Aviso tipo="error">{error}</Aviso>}
        {!p && !error && <p className="text-xs text-muted">Pide dos veces: la segunda el modelo ya está en la caché del motor y responde más rápido.</p>}
        {p && (
          <>
            <p className="text-xs text-muted">{p.algoritmo} · base {p.semana_base} · {fmtNum(p.duracion_ms, 1)} ms en el motor
              {p.desde_cache ? " · modelo en memoria" : " · modelo cargado ahora"}</p>
            <table className="mt-2 w-full text-xs tabular">
              <thead className="text-muted"><tr><th className="text-left font-medium">Semana</th><th className="text-right font-medium">Casos</th><th className="text-right font-medium">80 %</th><th className="text-right font-medium">Nivel</th></tr></thead>
              <tbody>
                {p.puntos.map((x) => (
                  <tr key={x.horizonte} className="border-t border-line">
                    <td className="py-1">{x.etiqueta}</td><td className="text-right">{fmtNum(x.casos_esperados, 1)}</td>
                    <td className="text-right text-muted">{fmtNum(x.limite_inferior, 0)}–{fmtNum(x.limite_superior, 0)}</td>
                    <td className="text-right">{x.nivel && <NivelChip nivel={x.nivel} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </Card>
  );
}

/** Matriz de sensibilidad calculada por un Web Worker con su propio WebSocket. */
function MatrizSensibilidad({ base }: { base: Omit<Escenario, "id"> }) {
  const [ejeX, setEjeX] = useState<CampoEscenario>("cambio_lluvia_pct");
  const [ejeY, setEjeY] = useState<CampoEscenario>("cambio_busquedas_pct");
  const { calcular, avance, resultado, error, calculando } = useMatrizSensibilidad();
  const fps = useFps(calculando);
  const cx = control(ejeX);
  const cy = control(ejeY);

  return (
    <Card className="min-w-0 lg:col-span-3">
      <CardHeader titulo="Matriz de sensibilidad" icono={<Grid3x3 size={17} />}
        subtitulo={`Un Web Worker envía ${cx.grilla.length * cy.grilla.length} escenarios por su propio WebSocket y arma la matriz sin bloquear la página.`} />
      <div className="space-y-3 px-5 pb-5">
        <div className="flex flex-wrap items-end gap-2">
          <Etiqueta texto="Eje horizontal">
            <select className={claseInput} value={ejeX} onChange={(e) => setEjeX(e.target.value as CampoEscenario)}>
              {CONTROLES.filter((c) => c.campo !== ejeY).map((c) => <option key={c.campo} value={c.campo}>{c.etiqueta}</option>)}
            </select>
          </Etiqueta>
          <Etiqueta texto="Eje vertical">
            <select className={claseInput} value={ejeY} onChange={(e) => setEjeY(e.target.value as CampoEscenario)}>
              {CONTROLES.filter((c) => c.campo !== ejeX).map((c) => <option key={c.campo} value={c.campo}>{c.etiqueta}</option>)}
            </select>
          </Etiqueta>
          <Boton cargando={calculando} onClick={() => calcular({ url: urlSimulador(), base, ejeX: { campo: ejeX, valores: cx.grilla }, ejeY: { campo: ejeY, valores: cy.grilla } })}>
            Calcular
          </Boton>
        </div>
        {avance && (
          <div className="text-xs" aria-live="polite">
            <div className="flex justify-between"><span>{avance.recibidos} de {avance.total} escenarios</span><span className="tabular text-muted">Hilo principal: {fps ?? "—"} fps</span></div>
            <div className="mt-1 h-1.5 rounded-full bg-surface-2"><div className="h-1.5 rounded-full bg-ink" style={{ width: `${(avance.recibidos / avance.total) * 100}%` }} /></div>
          </div>
        )}
        {error && <Aviso tipo="error">{error}</Aviso>}
        {resultado && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full border-separate border-spacing-0.5 text-center text-[11px] tabular">
                <thead>
                  <tr><th className="p-1 text-left font-medium text-muted">{cy.etiqueta} ↓ · {cx.etiqueta} →</th>
                    {cx.grilla.map((v) => <th key={v} className="p-1 font-medium text-muted">{conSigno(v, cx.unidad)}</th>)}</tr>
                </thead>
                <tbody>
                  {resultado.celdas.map((fila, i) => (
                    <tr key={cy.grilla[i]}>
                      <th className="p-1 text-left font-medium text-muted">{conSigno(cy.grilla[i], cy.unidad)}</th>
                      {fila.map((c, j) => {
                        const color = NIVELES[c.nivel ?? "VERDE"].color;
                        const peso = resultado.maximo > resultado.minimo ? (c.total - resultado.minimo) / (resultado.maximo - resultado.minimo) : 0;
                        return (
                          <td key={cx.grilla[j]} title={`${fmtNum(c.total, 1)} casos (${conSigno(c.variacion, " %")})`}
                            className="rounded p-1.5" style={{ background: `color-mix(in srgb, ${color} ${Math.round(18 + peso * 50)}%, transparent)` }}>
                            {fmtNum(c.total, 0)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-muted">
              Casos esperados en 4 semanas (sin cambios: {fmtNum(resultado.totalBase, 0)}). El color es el nivel de riesgo máximo.
              {" "}{resultado.escenarios} escenarios en {fmtNum(resultado.duracionMs, 0)} ms ({fmtNum(resultado.motorMs, 0)} ms de cálculo en el motor).
            </p>
          </>
        )}
      </div>
    </Card>
  );
}
