// ============================================================================
// INICIO — ISR (Incremental Static Regeneration)
// ----------------------------------------------------------------------------
// Es la página más visitada y sus datos cambian una vez al día: se sirve como HTML estático
// desde la CDN y se regenera como máximo cada hora o cuando el backend avisa (/api/revalidar).
// Todo este archivo es un componente de SERVIDOR: no envía JavaScript propio al navegador.
// ============================================================================
import { ArrowRight, CalendarDays, Cpu, Radio, Siren, TrendingUp, Users, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import { PHASE_PRODUCTION_BUILD } from "next/constants";
import Link from "next/link";
import { VolcanCard } from "@/components/dashboard/Paneles";
import { AutoRevalidar } from "@/components/render/AutoRevalidar";
import { RenderPanel } from "@/components/render/RenderPanel";
import TituloRevelado from "@/components/TituloRevelado";
import { Card, CardHeader, NivelChip } from "@/components/ui";
import { fmtNum, NIVELES, rangoNivel } from "@/lib/formato";
import { ORDEN, PATRONES } from "@/lib/patrones";
import { ahoraIso } from "@/lib/servidor";
import type { Nivel } from "@/api/tipos";
import { cargarInicio, type DatosInicio } from "@/lib/tablero";

export const revalidate = 3600;

/** Nombre corto de cada enfermedad para las fichas de municipio. */
const ENFERMEDAD_CORTA: Record<string, string> = { IRA: "IRA", EDA: "EDA", DENGUE: "Dengue", RESP_CENIZA: "Ceniza" };
const esAlta = (n: Nivel | null | undefined) => n != null && rangoNivel(n) >= 2;

function Indicador({ icono, valor, etiqueta, detalle, destacado = false }: {
  icono: ReactNode; valor: string; etiqueta: string; detalle?: string; destacado?: boolean;
}) {
  return (
    <div className={`rounded-lg border p-4 ${destacado ? "border-[color-mix(in_srgb,var(--st-naranja)_45%,transparent)] bg-[color-mix(in_srgb,var(--st-naranja)_7%,var(--surface))]" : "border-line bg-surface"}`}>
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted">{icono}{etiqueta}</p>
      <p className="cifra mt-1.5 text-3xl leading-none text-ink">{valor}</p>
      {detalle && <p className="mt-1.5 text-xs text-ink-2">{detalle}</p>}
    </div>
  );
}

export default async function Inicio() {
  let datos: DatosInicio;
  try {
    datos = await cargarInicio();
  } catch (e) {
    // Al regenerar (ISR) un error conserva la versión anterior en caché: se relanza.
    // Solo en el build (Render dormido) se genera una versión de respaldo que se auto-revalida.
    if (process.env.NEXT_PHASE !== PHASE_PRODUCTION_BUILD) throw e;
    return (
      <div className="space-y-6">
        <RenderPanel patron="ISR" generadoEn={ahoraIso()} ruta="/" detalles={[{ etiqueta: "Versión", valor: "Respaldo: la API no respondió" }]} />
        <AutoRevalidar ruta="/" />
        <h1 className="titulo-display text-5xl sm:text-6xl">Riesgo de brotes en la zona del Galeras</h1>
        <p className="max-w-2xl text-ink-2">Los datos se están actualizando. Recarga en unos segundos o abre el{" "}
          <Link href="/mapa" className="subrayar font-medium">mapa en vivo</Link>.</p>
      </div>
    );
  }
  const { municipios, porMunicipio, volcan, alertas, semanaReferencia, generadoEn } = datos;
  const poblacion = new Map(municipios.map((m) => [m.id, m.poblacion]));
  const filas = [...porMunicipio].sort((a, b) => rangoNivel(b.nivel_max) - rangoNivel(a.nivel_max)
    || (poblacion.get(b.municipio_id) ?? 0) - (poblacion.get(a.municipio_id) ?? 0));
  const enAlerta = filas.filter((f) => esAlta(f.nivel_max) || esAlta(f.nivel_max_predicho));
  const altosHoy = filas.filter((f) => esAlta(f.nivel_max));
  const altosPredichos = filas.filter((f) => esAlta(f.nivel_max_predicho));
  const poblacionTotal = municipios.reduce((suma, m) => suma + m.poblacion, 0);

  return (
    <div className="space-y-8">
      <RenderPanel patron="ISR" generadoEn={generadoEn} ruta="/"
        detalles={[{ etiqueta: "Municipios en el HTML", valor: String(filas.length) }]} />

      <section>
        <p className="titulo-seccion text-[13px] text-muted">Vigilancia epidemiológica temprana</p>
        <TituloRevelado className="titulo-display mt-2 text-[2.6rem] sm:text-6xl lg:text-7xl"
          texto="Riesgo de brotes en la zona del Galeras" />
        <p className="mt-3 max-w-3xl text-ink-2">
          Cruzamos casos oficiales (SIVIGILA), clima (Open-Meteo), búsquedas de síntomas en internet, ventas de farmacias
          y la actividad del volcán para anticipar brotes de IRA, EDA, dengue y enfermedades respiratorias por ceniza.
          {enAlerta.length > 0
            ? ` Hoy hay ${enAlerta.length} municipio${enAlerta.length > 1 ? "s" : ""} con riesgo alto o muy alto (observado o predicho).`
            : " Hoy ningún municipio tiene riesgo alto."}
        </p>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Resumen de la semana">
        <Indicador icono={<CalendarDays size={14} aria-hidden />} etiqueta="Semana epidemiológica"
          valor={semanaReferencia ? semanaReferencia.replace("-S", " · S") : "—"} detalle="Última semana con casos" />
        <Indicador icono={<Users size={14} aria-hidden />} etiqueta="Municipios vigilados" valor={String(filas.length)}
          detalle={`${fmtNum(poblacionTotal)} habitantes`} />
        <Indicador icono={<Siren size={14} aria-hidden />} etiqueta="Alertas activas" valor={String(alertas.length)}
          detalle={altosHoy.length ? `Riesgo alto hoy en ${altosHoy.map((f) => f.municipio).join(", ")}` : "Ningún municipio en riesgo alto hoy"}
          destacado={alertas.length > 0} />
        <Indicador icono={<TrendingUp size={14} aria-hidden />} etiqueta="Próximas 4 semanas" valor={String(altosPredichos.length)}
          detalle={altosPredichos.length ? "municipio(s) con riesgo alto predicho" : "Sin riesgo alto predicho"}
          destacado={altosPredichos.length > 0} />
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="grid gap-4 sm:grid-cols-2 lg:col-span-2" aria-label="Municipios">
          {filas.map((f) => (
            <Link key={f.municipio_id} href={`/municipio/${f.municipio_id}`} data-municipio={f.municipio_id}
              className="group rounded-lg border border-line bg-surface p-4 transition-colors duration-[520ms] hover:bg-surface-2"
              style={{ borderLeft: `4px solid ${NIVELES[f.nivel_max].color}` }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="titulo-seccion text-lg">{f.municipio}</h2>
                  <p className="text-xs text-muted">{fmtNum(poblacion.get(f.municipio_id))} hab.</p>
                </div>
                <ArrowRight size={16} className="mt-1 text-muted transition group-hover:translate-x-0.5" aria-hidden />
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="text-muted">Esta semana</span> <NivelChip nivel={f.nivel_max} />
                {f.nivel_max_predicho && <><span className="text-muted">· 4 semanas</span> <NivelChip nivel={f.nivel_max_predicho} /></>}
              </div>
              <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t border-line pt-2.5 text-[11px] text-ink-2" aria-label="Riesgo por enfermedad esta semana">
                {Object.entries(f.detalle).map(([codigo, nivel]) => (
                  <li key={codigo} className="inline-flex items-center gap-1" title={`${codigo}: ${NIVELES[nivel].etiqueta}`}>
                    <span className="h-2 w-2 rounded-full" style={{ background: NIVELES[nivel].color }} aria-hidden />
                    {ENFERMEDAD_CORTA[codigo] ?? codigo}
                    <span className="sr-only">: {NIVELES[nivel].etiqueta}</span>
                  </li>
                ))}
              </ul>
            </Link>
          ))}
        </section>
        <VolcanCard v={volcan} />
      </div>

      <Card>
        <CardHeader titulo="Cómo está construido" subtitulo="Cada sección usa la técnica web que mejor le sirve; el panel de arriba de cada página lo explica." />
        <div className="grid gap-4 px-5 pb-5 md:grid-cols-2 xl:grid-cols-4">
          {ORDEN.map((p) => (
            <div key={p} className="rounded-lg border border-line p-4">
              <span className="rounded-md px-2 py-0.5 font-mono text-xs font-bold text-white" style={{ background: `var(--pat-${p.toLowerCase()})` }}>{p}</span>
              <p className="mt-2 text-sm font-medium">{PATRONES[p].nombre}</p>
              <ul className="mt-2 space-y-1 text-sm">
                {PATRONES[p].paginas.map((pg) => (
                  <li key={pg.ruta}>
                    {pg.ruta.includes("[") ? <span className="text-ink-2">{pg.nombre}</span>
                      : <Link href={pg.ruta} className="subrayar text-ink-2">{pg.nombre}</Link>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="grid gap-4 border-t border-line px-5 py-4 text-sm text-ink-2 md:grid-cols-3">
          <p className="flex gap-2"><Cpu size={16} className="mt-0.5 shrink-0 text-muted" />
            <span><b className="font-medium text-ink">Motor gRPC.</b> Un servidor Python con el modelo en memoria; la API lo usa con los 4 tipos de RPC.</span></p>
          <p className="flex gap-2"><Radio size={16} className="mt-0.5 shrink-0 text-muted" />
            <span><b className="font-medium text-ink">Streams.</b> Alertas y entrenamiento llegan por SSE; el simulador conversa por WebSocket.</span></p>
          <p className="flex gap-2"><Workflow size={16} className="mt-0.5 shrink-0 text-muted" />
            <span><b className="font-medium text-ink">Web Workers.</b> Los CSV grandes y la matriz de sensibilidad se procesan fuera del hilo principal.</span></p>
        </div>
        <p className="px-5 pb-5 text-sm"><Link href="/metodologia" className="subrayar font-medium">Ver la metodología y la arquitectura →</Link></p>
      </Card>
    </div>
  );
}
