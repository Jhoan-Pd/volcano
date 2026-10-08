import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ClimaDiario } from "../../api/tipos";
import { fmtDia, fmtFecha, fmtNum } from "../../lib/formato";

/** Dos gráficas separadas (temperatura y lluvia): nunca dos escalas Y en una misma gráfica. */
export default function PronosticoClima({ dias }: { dias: ClimaDiario[] }) {
  const datos = dias.map((d) => ({ ...d, dia: fmtDia(d.fecha) }));
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-medium text-ink-2">Temperatura (°C)</p>
          <ul className="flex gap-3 text-[11px] text-ink-2">
            <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-[var(--series-2)]" />Máxima</li>
            <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-[var(--series-1)]" />Mínima</li>
          </ul>
        </div>
        <div className="h-48">
          <ResponsiveContainer>
            <LineChart data={datos} margin={{ top: 8, right: 34, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="dia" tickLine={false} axisLine={{ stroke: "var(--axis)" }} minTickGap={18} />
              <YAxis tickLine={false} axisLine={false} domain={["dataMin - 2", "dataMax + 2"]} allowDecimals={false} />
              <Tooltip cursor={{ stroke: "var(--axis)" }} content={<TipTemp />} />
              <Line dataKey="temp_max_c" stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false}
                activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
                label={(p: PropsEtiqueta) => <EtiquetaFinal {...p} total={datos.length} />} />
              <Line dataKey="temp_min_c" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false}
                activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
                label={(p: PropsEtiqueta) => <EtiquetaFinal {...p} total={datos.length} />} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div>
        <p className="mb-2 text-xs font-medium text-ink-2">Precipitación diaria (mm)</p>
        <div className="h-48">
          <ResponsiveContainer>
            <BarChart data={datos} margin={{ top: 8, right: 8, left: -18, bottom: 0 }} barCategoryGap={3}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis dataKey="dia" tickLine={false} axisLine={{ stroke: "var(--axis)" }} minTickGap={18} />
              <YAxis tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<TipLluvia />} />
              <Bar dataKey="precipitacion_mm" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={18} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

interface PropsEtiqueta { index?: number; x?: number | string; y?: number | string; value?: unknown }

/** Etiqueta directa solo en el último punto de cada línea (identidad sin depender del color). */
function EtiquetaFinal({ index, x, y, value, total }: PropsEtiqueta & { total: number }) {
  if (index !== total - 1 || typeof value !== "number") return <g />;
  return <text x={Number(x ?? 0) + 6} y={Number(y ?? 0) + 4} fontSize={11} fill="var(--ink-2)">{fmtNum(value, 0)}°</text>;
}

type P = { payload: ClimaDiario };
function TipTemp({ active, payload }: { active?: boolean; payload?: P[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-lg tabular">
      <p className="font-semibold">{fmtFecha(d.fecha, { weekday: "long", day: "numeric", month: "long" })}</p>
      <p className="mt-1 text-ink-2">Máx. <b className="text-ink">{fmtNum(d.temp_max_c, 1)} °C</b> · Mín. <b className="text-ink">{fmtNum(d.temp_min_c, 1)} °C</b></p>
      <p className="text-ink-2">Humedad {fmtNum(d.humedad_relativa_pct, 0)} %</p>
    </div>
  );
}
function TipLluvia({ active, payload }: { active?: boolean; payload?: P[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-lg tabular">
      <p className="font-semibold">{fmtFecha(d.fecha, { weekday: "long", day: "numeric", month: "long" })}</p>
      <p className="mt-1 text-ink-2">Lluvia <b className="text-ink">{fmtNum(d.precipitacion_mm, 1)} mm</b></p>
    </div>
  );
}
