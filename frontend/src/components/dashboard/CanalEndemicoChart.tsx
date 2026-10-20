import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PrediccionEnfermedad, PuntoSerie } from "../../api/tipos";
import { fmtFecha, fmtNum, NIVELES } from "../../lib/formato";

interface Fila {
  etiqueta: string;
  fecha_inicio: string;
  casos: number | null;
  p_amarillo: number | null;
  p_naranja: number | null;
  p_rojo: number | null;
  z1: number; z2: number; z3: number; z4: number;
  esperado?: number | null;
  banda?: [number, number] | null;
  validacion?: number | null;
  futuro?: boolean;
}

/**
 * Histórico vs. predicción sobre el canal endémico.
 * - Franjas: zonas de riesgo (percentiles de los 5 años anteriores para cada semana).
 * - Línea continua: casos observados.
 * - Línea discontinua + franja del color de la serie: casos esperados de las próximas
 *   4 semanas con su intervalo del 80 %.
 * - Línea punteada gris (opcional): lo que el modelo habría predicho a 1 semana en el
 *   periodo de validación, para comparar con lo observado.
 * Una sola escala Y (casos).
 */
export default function CanalEndemicoChart({ puntos, color, prediccion, mostrarValidacion = false }: {
  puntos: PuntoSerie[]; color: string; prediccion?: PrediccionEnfermedad | null; mostrarValidacion?: boolean;
}) {
  const futuros = prediccion?.puntos ?? [];
  const validacion = new Map((mostrarValidacion ? prediccion?.backtest ?? [] : []).map((b) => [b.etiqueta, b.predicho]));
  const maxCasos = Math.max(1, ...puntos.map((p) => Math.max(p.casos ?? 0, p.p_rojo ?? 0)),
    ...futuros.map((f) => Math.max(f.limite_superior, f.umbrales?.rojo ?? 0)));
  const tope = Math.ceil(maxCasos * 1.15);
  const zonas = (a: number, n: number, r: number) =>
    ({ z1: a, z2: Math.max(0, n - a), z3: Math.max(0, r - n), z4: Math.max(0, tope - r) });

  const datos: Fila[] = puntos.map((p) => {
    const a = p.p_amarillo ?? 0, n = p.p_naranja ?? a, r = p.p_rojo ?? n;
    return { ...p, ...zonas(a, n, r), validacion: validacion.get(p.etiqueta) ?? null };
  });
  // El último punto observado ancla la línea de predicción para que no quede "flotando"
  const ultimo = [...datos].reverse().find((d) => d.casos != null);
  if (futuros.length && ultimo) {
    ultimo.esperado = ultimo.casos;
    ultimo.banda = [ultimo.casos ?? 0, ultimo.casos ?? 0];
  }
  for (const f of futuros) {
    const u = f.umbrales;
    datos.push({
      etiqueta: f.etiqueta, fecha_inicio: f.fecha_inicio, casos: null, futuro: true,
      p_amarillo: u?.amarillo ?? null, p_naranja: u?.naranja ?? null, p_rojo: u?.rojo ?? null,
      ...zonas(u?.amarillo ?? 0, u?.naranja ?? 0, u?.rojo ?? 0),
      esperado: f.casos_esperados, banda: [f.limite_inferior, f.limite_superior],
    });
  }
  const inicioFuturo = futuros[0]?.etiqueta;

  return (
    <div>
      <div className="h-72 w-full sm:h-[22rem]">
        <ResponsiveContainer>
          <ComposedChart data={datos} margin={{ top: 22, right: 12, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="etiqueta" tickLine={false} axisLine={{ stroke: "var(--axis)" }} minTickGap={36}
              tickFormatter={(e: string) => e.replace("-S", " · S")} />
            <YAxis tickLine={false} axisLine={false} width={44} domain={[0, tope]} allowDecimals={false} />
            {(["z1", "z2", "z3", "z4"] as const).map((z, i) => (
              <Area key={z} dataKey={z} stackId="canal" type="stepAfter" stroke="none" isAnimationActive={false}
                fill={[NIVELES.VERDE.color, NIVELES.AMARILLO.color, NIVELES.NARANJA.color, NIVELES.ROJO.color][i]}
                fillOpacity={0.16} activeDot={false} />
            ))}
            {inicioFuturo && (
              <ReferenceLine x={inicioFuturo} stroke="var(--axis)" strokeDasharray="2 3"
                label={{ value: "Predicción →", position: "top", fill: "var(--muted)", fontSize: 11 }} />
            )}
            {futuros.length > 0 && (
              <Area dataKey="banda" type="monotone" stroke="none" fill={color} fillOpacity={0.22}
                isAnimationActive={false} activeDot={false} connectNulls />
            )}
            {mostrarValidacion && (
              <Line dataKey="validacion" type="monotone" stroke="var(--muted)" strokeWidth={1.5} strokeDasharray="1 3"
                dot={false} activeDot={false} isAnimationActive={false} connectNulls />
            )}
            <Line dataKey="casos" type="monotone" stroke={color} strokeWidth={2} dot={false}
              activeDot={{ r: 4.5, stroke: "var(--surface)", strokeWidth: 2 }} isAnimationActive={false} connectNulls />
            {futuros.length > 0 && (
              <Line dataKey="esperado" type="monotone" stroke={color} strokeWidth={2} strokeDasharray="6 4"
                dot={{ r: 3.5, fill: color, stroke: "var(--surface)", strokeWidth: 2 }}
                activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }} isAnimationActive={false} connectNulls />
            )}
            <Tooltip cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} content={<Tip />} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-2" aria-label="Leyenda">
        <li className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded" style={{ background: color }} />Casos observados</li>
        {futuros.length > 0 && (
          <li className="flex items-center gap-1.5">
            <span className="relative h-3 w-5 rounded-sm" style={{ background: color, opacity: 0.35 }} />
            Predicción e intervalo 80 %
          </li>
        )}
        {mostrarValidacion && (
          <li className="flex items-center gap-1.5"><span className="w-5 border-t-2 border-dotted border-muted" />Predicho en validación</li>
        )}
        {(["VERDE", "AMARILLO", "NARANJA", "ROJO"] as const).map((n) => (
          <li key={n} className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm" style={{ background: NIVELES[n].color, opacity: 0.45 }} />
            {NIVELES[n].etiqueta}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Fila }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold">{p.etiqueta.replace("-S", " · Semana ")}{p.futuro ? " · predicción" : ""}</p>
      <p className="text-muted">desde {fmtFecha(p.fecha_inicio)}</p>
      {p.futuro ? (
        <>
          <p className="mt-1.5 text-sm font-semibold text-ink tabular">{fmtNum(p.esperado, 1)} casos esperados</p>
          {p.banda && <p className="text-ink-2 tabular">Intervalo 80 %: {fmtNum(p.banda[0], 0)} – {fmtNum(p.banda[1], 0)}</p>}
        </>
      ) : (
        <>
          <p className="mt-1.5 text-sm font-semibold text-ink tabular">{fmtNum(p.casos)} casos</p>
          {p.validacion != null && <p className="text-ink-2 tabular">El modelo predijo {fmtNum(p.validacion, 1)}</p>}
        </>
      )}
      {p.p_rojo != null && (
        <dl className="mt-1 grid grid-cols-[auto_auto] gap-x-3 text-ink-2 tabular">
          <dt>Mediana (P50)</dt><dd className="text-right">{fmtNum(p.p_amarillo, 1)}</dd>
          <dt>P75</dt><dd className="text-right">{fmtNum(p.p_naranja, 1)}</dd>
          <dt>P90</dt><dd className="text-right">{fmtNum(p.p_rojo, 1)}</dd>
        </dl>
      )}
    </div>
  );
}
