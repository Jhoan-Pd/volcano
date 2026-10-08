import type { ReactNode } from "react";
import { CloudRain, Droplets, ExternalLink, Lightbulb, Mountain, Thermometer, Wind } from "lucide-react";
import type { ClimaActual, EstadoVolcan, Nivel, RiesgoEnfermedad, RiesgoMunicipio } from "../../api/tipos";
import { fmtFecha, fmtNum, NIVELES_VOLCAN } from "../../lib/formato";
import { Card, CardHeader, NivelChip, SimuladoBadge, Spinner } from "../ui";

export function VolcanCard({ v }: { v: EstadoVolcan }) {
  const info = NIVELES_VOLCAN[v.nivel_actividad];
  return (
    <Card>
      <CardHeader titulo="Volcán Galeras" icono={<Mountain size={17} />}
        subtitulo={v.fecha ? `Boletín SGC del ${fmtFecha(v.fecha)}` : "Sin boletín registrado"}
        accion={info && <NivelChip nivel={info.nivel} texto={info.etiqueta} />} />
      <div className="space-y-3 px-5 pb-5 text-sm">
        {info && <p className="font-medium">{info.descripcion}</p>}
        {v.descripcion && <p className="text-ink-2">{v.descripcion}</p>}
        <div className="flex flex-wrap items-center gap-2">
          {v.url_boletin && (
            <a href={v.url_boletin} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">
              Ver boletín oficial <ExternalLink size={12} />
            </a>
          )}
          {v.es_simulado && <SimuladoBadge />}
        </div>
        <div className="border-t border-line pt-3">
          <p className="mb-1.5 text-xs font-medium text-ink-2">Caída de ceniza (últimos 12 meses)</p>
          {v.ceniza_reciente.length === 0 ? (
            <p className="text-xs text-muted">Sin reportes.</p>
          ) : (
            <ul className="space-y-1">
              {v.ceniza_reciente.map((c, i) => (
                <li key={i} className="flex items-center justify-between gap-2 text-xs">
                  <span>{c.municipio ?? "—"} · {["", "leve", "moderada", "fuerte"][c.intensidad]}</span>
                  <span className="text-muted tabular">{fmtFecha(c.fecha)}{c.es_simulado ? " · simulado" : ""}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}

function Dato({ icono, etiqueta, valor }: { icono: ReactNode; etiqueta: string; valor: string }) {
  return (
    <div className="rounded-xl bg-surface-2 px-3 py-2.5">
      <p className="flex items-center gap-1.5 text-[11px] text-muted">{icono}{etiqueta}</p>
      <p className="mt-0.5 text-base font-semibold tabular">{valor}</p>
    </div>
  );
}

export function ClimaActualCard({ c, municipio }: { c: ClimaActual | null; municipio: string }) {
  return (
    <Card>
      <CardHeader titulo={`Clima ahora en ${municipio}`} icono={<Thermometer size={17} />}
        subtitulo={c ? (c.fuente === "open-meteo" ? `Open-Meteo en vivo · ${c.descripcion}` : c.descripcion) : undefined} />
      {!c ? <Spinner /> : (
        <div className="grid grid-cols-2 gap-2 px-5 pb-5">
          <Dato icono={<Thermometer size={12} />} etiqueta="Temperatura" valor={`${fmtNum(c.temperatura_c, 1)} °C`} />
          <Dato icono={<Droplets size={12} />} etiqueta="Humedad" valor={`${fmtNum(c.humedad_relativa_pct, 0)} %`} />
          <Dato icono={<CloudRain size={12} />} etiqueta="Lluvia" valor={`${fmtNum(c.precipitacion_mm, 1)} mm`} />
          <Dato icono={<Wind size={12} />} etiqueta="Viento" valor={c.viento_kmh == null ? "—" : `${fmtNum(c.viento_kmh, 0)} km/h`} />
        </div>
      )}
    </Card>
  );
}

export function RiesgoMunicipiosTabla({ filas, enfermedades, onSeleccionar, seleccionado }: {
  filas: RiesgoMunicipio[]; enfermedades: { codigo: string; nombre: string }[];
  onSeleccionar: (id: number) => void; seleccionado: number | null;
}) {
  const corto: Record<string, string> = { IRA: "IRA", EDA: "EDA", DENGUE: "Dengue", RESP_CENIZA: "Ceniza" };
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[440px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="px-4 py-2 font-medium">Municipio</th>
            {enfermedades.map((e) => <th key={e.codigo} className="px-1.5 py-2 font-medium" title={e.nombre}>{corto[e.codigo] ?? e.codigo}</th>)}
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.municipio_id} onClick={() => onSeleccionar(f.municipio_id)}
              className={`cursor-pointer border-b border-line/70 last:border-0 hover:bg-surface-2 ${seleccionado === f.municipio_id ? "bg-surface-2" : ""}`}>
              <td className="px-4 py-2.5 font-medium">{f.municipio}</td>
              {enfermedades.map((e) => (
                <td key={e.codigo} className="px-1.5 py-2.5"><NivelChip nivel={(f.detalle[e.codigo] ?? "VERDE") as Nivel} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Recomendaciones({ riesgos }: { riesgos: RiesgoEnfermedad[] }) {
  // Primero las enfermedades con mayor riesgo
  const orden = { ROJO: 0, NARANJA: 1, AMARILLO: 2, VERDE: 3 } as const;
  const lista = [...riesgos].sort((a, b) => orden[a.nivel] - orden[b.nivel]);
  return (
    <div className="grid gap-3 px-5 pb-5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
      {lista.map((r) => (
        <div key={r.codigo} className="rounded-xl border border-line p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-semibold">
              <Lightbulb size={15} className="text-muted" aria-hidden />{r.nombre}
            </p>
            <NivelChip nivel={r.nivel} />
          </div>
          <ul className="list-disc space-y-1 pl-5 text-[13px] text-ink-2 marker:text-muted">
            {r.recomendaciones.slice(0, r.nivel === "VERDE" ? 3 : 5).map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}
