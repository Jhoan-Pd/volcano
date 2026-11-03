// ============================================================================
// INICIO — ISR (Incremental Static Regeneration)
// ----------------------------------------------------------------------------
// Es la página más visitada y sus datos cambian una vez al día: se sirve como HTML estático
// desde la CDN y se regenera como máximo cada hora o cuando el backend avisa (/api/revalidar).
// Todo este archivo es un componente de SERVIDOR: no envía JavaScript propio al navegador.
// ============================================================================
import { ArrowRight, Cpu, Radio, Workflow } from "lucide-react";
import Link from "next/link";
import { VolcanCard } from "@/components/dashboard/Paneles";
import { RenderPanel } from "@/components/render/RenderPanel";
import TituloRevelado from "@/components/TituloRevelado";
import { Card, CardHeader, NivelChip } from "@/components/ui";
import { fmtNum, NIVELES, rangoNivel } from "@/lib/formato";
import { ORDEN, PATRONES } from "@/lib/patrones";
import { cargarInicio } from "@/lib/tablero";

export const revalidate = 3600;

export default async function Inicio() {
  const { municipios, porMunicipio, volcan, generadoEn } = await cargarInicio();
  const poblacion = new Map(municipios.map((m) => [m.id, m.poblacion]));
  const filas = [...porMunicipio].sort((a, b) => rangoNivel(b.nivel_max) - rangoNivel(a.nivel_max)
    || (poblacion.get(b.municipio_id) ?? 0) - (poblacion.get(a.municipio_id) ?? 0));
  const enAlerta = filas.filter((f) => rangoNivel(f.nivel_max) >= 2 || rangoNivel(f.nivel_max_predicho ?? "VERDE") >= 2);

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
              <p className="mt-2 text-[11px] text-muted">
                {Object.entries(f.detalle).map(([codigo, nivel]) => `${codigo}: ${NIVELES[nivel].etiqueta.toLowerCase()}`).join(" · ")}
              </p>
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
