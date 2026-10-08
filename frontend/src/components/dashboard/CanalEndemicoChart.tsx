import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PuntoSerie } from "../../api/tipos";
import { fmtFecha, fmtNum, NIVELES } from "../../lib/formato";

interface Fila extends PuntoSerie {
  z1: number; z2: number; z3: number; z4: number;
}

/**
 * Canal endémico: las franjas son las zonas de riesgo calculadas con percentiles de los
 * 5 años anteriores para cada semana; la línea son los casos observados.
 * Una sola escala Y (casos), franjas apiladas como diferencias entre percentiles.
 */
export default function CanalEndemicoChart({ puntos, color }: { puntos: PuntoSerie[]; color: string }) {
  const maxCasos = Math.max(1, ...puntos.map((p) => Math.max(p.casos ?? 0, p.p_rojo ?? 0)));
  const tope = Math.ceil(maxCasos * 1.15);
  const datos: Fila[] = puntos.map((p) => {
    const a = p.p_amarillo ?? 0, n = p.p_naranja ?? a, r = p.p_rojo ?? n;
    return { ...p, z1: a, z2: Math.max(0, n - a), z3: Math.max(0, r - n), z4: Math.max(0, tope - r) };
  });

  return (
    <div>
      <div className="h-72 w-full sm:h-[22rem]">
        <ResponsiveContainer>
          <ComposedChart data={datos} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="etiqueta" tickLine={false} axisLine={{ stroke: "var(--axis)" }} minTickGap={36}
              tickFormatter={(e: string) => e.replace("-S", " · S")} />
            <YAxis tickLine={false} axisLine={false} width={44} domain={[0, tope]} allowDecimals={false} />
            {(["z1", "z2", "z3", "z4"] as const).map((z, i) => (
              <Area key={z} dataKey={z} stackId="canal" type="stepAfter" stroke="none" isAnimationActive={false}
                fill={[NIVELES.VERDE.color, NIVELES.AMARILLO.color, NIVELES.NARANJA.color, NIVELES.ROJO.color][i]}
                fillOpacity={0.16} activeDot={false} />
            ))}
            <Line dataKey="casos" type="monotone" stroke={color} strokeWidth={2} dot={false}
              activeDot={{ r: 4.5, stroke: "var(--surface)", strokeWidth: 2 }} isAnimationActive={false} connectNulls />
            <Tooltip cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} content={<Tip />} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-2" aria-label="Leyenda">
        <li className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded" style={{ background: color }} />Casos observados</li>
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
    <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold">{p.etiqueta.replace("-S", " · Semana ")}</p>
      <p className="text-muted">desde {fmtFecha(p.fecha_inicio)}</p>
      <p className="mt-1.5 text-sm font-semibold text-ink tabular">{fmtNum(p.casos)} casos</p>
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
