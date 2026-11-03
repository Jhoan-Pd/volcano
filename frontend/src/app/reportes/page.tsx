// ============================================================================
// REPORTES — SSR (Server-Side Rendering)
// ----------------------------------------------------------------------------
// La vista previa del reporte se arma en el servidor en cada petición con los parámetros de la
// URL (?municipio=&semanas=). Los enlaces de descarga apuntan directo a la API (PDF y CSV):
// la página funciona completa sin JavaScript y se puede imprimir o compartir tal cual.
// ============================================================================
import { Download, FileSpreadsheet, FileText } from "lucide-react";
import type { Metadata } from "next";
import { API_V1 } from "@/api/cliente";
import type { Municipio, Pagina, PrediccionEnfermedad, ResumenDashboard, SerieEnfermedad } from "@/api/tipos";
import { RenderPanel } from "@/components/render/RenderPanel";
import { Card, CardHeader, claseInput, NivelChip } from "@/components/ui";
import { fmtNum } from "@/lib/formato";
import { datosDePeticion, entero, type Busqueda } from "@/lib/peticion";
import { ahoraIso, pedir, pedirOpcional } from "@/lib/servidor";

export const dynamic = "force-dynamic";
export const maxDuration = 60;
export const metadata: Metadata = { title: "Reportes", description: "Vista previa e impresión del reporte de riesgo por municipio; descargas en PDF y CSV." };

const RANGOS = [8, 12, 26, 52];

export default async function Reportes({ searchParams }: { searchParams: Promise<Busqueda> }) {
  const sp = await searchParams;
  const [municipios, peticion] = await Promise.all([
    pedir<Pagina<Municipio>>("/municipios", { limit: 500 }, { revalidar: 3600 }).then((p) => p.items.filter((m) => m.activo)),
    datosDePeticion(),
  ]);
  const municipio = municipios.find((m) => m.id === entero(sp.municipio)) ?? municipios[0];
  const semanas = RANGOS.includes(entero(sp.semanas) ?? 0) ? entero(sp.semanas)! : 12;

  const resumen = await pedir<ResumenDashboard>("/dashboard/resumen", { municipio_id: municipio.id }, { cache: "no-store" });
  const ids = resumen.riesgos.map((r) => r.enfermedad_id);
  const [series, predicciones] = await Promise.all([
    Promise.all(ids.map((id) => pedir<SerieEnfermedad>("/dashboard/serie", { municipio_id: municipio.id, enfermedad_id: id, semanas: Math.max(8, semanas) }, { cache: "no-store" }))),
    Promise.all(ids.map((id) => pedirOpcional<PrediccionEnfermedad>("/dashboard/prediccion", { municipio_id: municipio.id, enfermedad_id: id }, { cache: "no-store" }))),
  ]);
  const etiquetas = series[0]?.puntos.slice(-semanas).map((p) => p.etiqueta) ?? [];
  const descargas = [
    { href: `${API_V1}/reportes/resumen.pdf?municipio_id=${municipio.id}`, texto: "Reporte PDF del municipio", icono: FileText },
    { href: `${API_V1}/reportes/casos.csv?municipio_id=${municipio.id}`, texto: "Casos semanales (CSV)", icono: FileSpreadsheet },
    { href: `${API_V1}/reportes/predicciones.csv?municipio_id=${municipio.id}`, texto: "Predicciones (CSV)", icono: FileSpreadsheet },
    { href: `${API_V1}/reportes/alertas.csv`, texto: "Historial de alertas (CSV)", icono: FileSpreadsheet },
  ];

  return (
    <div className="space-y-5">
      <RenderPanel patron="SSR" generadoEn={ahoraIso()}
        porQue="El reporte combina el municipio y el rango que elige cada persona y debe reflejar la base de datos en ese instante, listo para imprimir."
        detalles={[
          { etiqueta: "Peticiones a la API en esta visita", valor: String(2 + ids.length * 2) },
          { etiqueta: "Renderizado para", valor: `${peticion.navegador} · ${peticion.idioma}` },
        ]} />

      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="titulo-seccion text-[13px] text-muted">Reporte de riesgo · semana {resumen.semana_referencia}</p>
          <h1 className="titulo-display mt-2 text-5xl sm:text-6xl">{municipio.nombre}</h1>
        </div>
        <form method="get" action="/reportes" className="flex flex-wrap items-end gap-2 print:hidden">
          <label><span className="mb-1 block text-xs font-medium text-ink-2">Municipio</span>
            <select name="municipio" defaultValue={municipio.id} className={claseInput}>
              {municipios.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select></label>
          <label><span className="mb-1 block text-xs font-medium text-ink-2">Semanas</span>
            <select name="semanas" defaultValue={semanas} className={claseInput}>
              {RANGOS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select></label>
          <button className="rounded-lg bg-ink px-3.5 py-2 text-sm font-medium text-page hover:opacity-90">Generar</button>
        </form>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {resumen.riesgos.map((r, i) => (
          <Card key={r.codigo} className="p-4">
            <p className="text-xs text-muted">{r.nombre}</p>
            <div className="mt-2 flex items-center justify-between gap-2">
              <p className="cifra text-3xl tabular">{fmtNum(r.casos)}</p>
              <NivelChip nivel={r.nivel} />
            </div>
            <p className="mt-1 text-xs text-muted">casos esta semana · {fmtNum(r.tasa_x_100k, 1)} por 100 mil</p>
            {predicciones[i]?.nivel_max && (
              <p className="mt-2 text-xs text-ink-2">Próximas 4 semanas: <NivelChip nivel={predicciones[i]!.nivel_max!} /></p>
            )}
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader titulo={`Casos de las últimas ${semanas} semanas`} subtitulo="Número de casos semanales por enfermedad" />
        <div className="overflow-x-auto px-5 pb-5">
          <table className="w-full min-w-[640px] text-right text-xs tabular">
            <thead className="border-b border-line text-muted">
              <tr><th className="py-2 pr-3 text-left">Semana</th>{resumen.riesgos.map((r) => <th key={r.codigo} className="pr-3">{r.codigo}</th>)}</tr>
            </thead>
            <tbody>
              {etiquetas.map((et, fila) => (
                <tr key={et} className="border-b border-line">
                  <td className="py-1.5 pr-3 text-left">{et}</td>
                  {series.map((s) => {
                    const p = s.puntos.slice(-semanas)[fila];
                    const alto = p?.casos != null && p.p_naranja != null && p.casos > p.p_naranja;
                    return <td key={s.enfermedad_id} className={`pr-3 ${alto ? "font-semibold text-[var(--st-naranja-ink)]" : ""}`}>{fmtNum(p?.casos)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11px] text-muted">En naranja, las semanas por encima del percentil 75 del canal endémico.</p>
        </div>
      </Card>

      <Card>
        <CardHeader titulo="Predicción de las próximas 4 semanas" subtitulo="Casos esperados (intervalo del 80 %)" />
        <div className="overflow-x-auto px-5 pb-5">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-line text-xs text-muted"><tr><th className="py-2 pr-3">Enfermedad</th><th className="pr-3">Modelo</th>
              {[1, 2, 3, 4].map((h) => <th key={h} className="pr-3">t+{h}</th>)}</tr></thead>
            <tbody>
              {resumen.riesgos.map((r, i) => {
                const pr = predicciones[i];
                return (
                  <tr key={r.codigo} className="border-b border-line align-top">
                    <td className="py-2 pr-3 font-medium">{r.nombre}</td>
                    <td className="py-2 pr-3 text-xs text-ink-2">{pr?.modelo?.algoritmo ?? "Sin modelo"}</td>
                    {[0, 1, 2, 3].map((k) => {
                      const p = pr?.puntos[k];
                      return <td key={k} className="py-2 pr-3 tabular text-xs">{p ? <>{fmtNum(p.casos_esperados, 1)} <span className="text-muted">({fmtNum(p.limite_inferior, 0)}–{fmtNum(p.limite_superior, 0)})</span></> : "—"}</td>;
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="print:hidden">
        <CardHeader titulo="Descargas" icono={<Download size={17} />} subtitulo="Archivos generados por la API en el momento de la descarga" />
        <ul className="grid gap-2 px-5 pb-5 sm:grid-cols-2">
          {descargas.map((d) => (
            <li key={d.href}>
              <a href={d.href} className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm hover:bg-surface-2">
                <d.icono size={16} className="text-muted" aria-hidden /> {d.texto}
              </a>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
