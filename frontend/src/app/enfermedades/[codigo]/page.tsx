// ============================================================================
// FICHA DE UNA ENFERMEDAD — SSG con datos obtenidos en el build
// ----------------------------------------------------------------------------
// - generateStaticParams: un HTML por enfermedad, generado en `next build`.
// - dynamicParams = false: cualquier otro código responde 404 (no se genera bajo demanda).
// - En el build también se piden a la API los umbrales y términos configurados
//   (cache: "force-cache"); si la API no responde, la ficha se genera solo con el contenido editorial.
// ============================================================================
import { AlertTriangle, ShieldCheck, Stethoscope, Users, Waves } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Enfermedad, Pagina } from "@/api/tipos";
import { RenderPanel } from "@/components/render/RenderPanel";
import TituloRevelado from "@/components/TituloRevelado";
import { Card, CardHeader } from "@/components/ui";
import { CODIGOS, FICHAS } from "@/lib/fichas";
import { pedirOpcional } from "@/lib/servidor";

export const dynamic = "force-static";
export const dynamicParams = false;

type Props = { params: Promise<{ codigo: string }> };

export function generateStaticParams() {
  return CODIGOS.map((c) => ({ codigo: c.toLowerCase() }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const ficha = FICHAS[(await params).codigo.toUpperCase()];
  return ficha ? { title: ficha.nombre, description: ficha.resumen } : {};
}

async function configuracion(codigo: string): Promise<Enfermedad | null> {
  const pagina = await pedirOpcional<Pagina<Enfermedad>>("/enfermedades", { limit: 100 }, { cache: "force-cache", timeoutMs: 20_000 });
  return pagina?.items.find((e) => e.codigo === codigo) ?? null;
}

function Lista({ items }: { items: string[] }) {
  return <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{items.map((x) => <li key={x}>{x}</li>)}</ul>;
}

export default async function FichaEnfermedad({ params }: Props) {
  const ficha = FICHAS[(await params).codigo.toUpperCase()];
  if (!ficha) notFound();
  const conf = await configuracion(ficha.codigo);
  const generadoEn = new Date().toISOString();

  return (
    <div className="space-y-6" data-ficha={ficha.codigo}>
      <RenderPanel patron="SSG" generadoEn={generadoEn}
        detalles={[{ etiqueta: "Configuración de la API en el build", valor: conf ? "Incluida" : "No disponible (solo contenido editorial)" }]} />
      <header>
        <Link href="/enfermedades" className="subrayar text-xs text-muted">← Enfermedades vigiladas</Link>
        <TituloRevelado className="titulo-display mt-2 text-4xl sm:text-6xl" texto={ficha.nombre} />
        <p className="mt-3 max-w-3xl text-ink-2">{ficha.resumen}</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card><CardHeader titulo="Síntomas" icono={<Stethoscope size={17} />} /><div className="px-5 pb-5"><Lista items={ficha.sintomas} /></div></Card>
        <Card>
          <CardHeader titulo="Transmisión y grupos de riesgo" icono={<Users size={17} />} />
          <div className="space-y-3 px-5 pb-5"><p className="text-sm text-ink-2">{ficha.transmision}</p><Lista items={ficha.grupos} /></div>
        </Card>
        <Card><CardHeader titulo="Prevención" icono={<ShieldCheck size={17} />} /><div className="px-5 pb-5"><Lista items={ficha.prevencion} /></div></Card>
        <Card><CardHeader titulo="Cuándo consultar de inmediato" icono={<AlertTriangle size={17} />} /><div className="px-5 pb-5"><Lista items={ficha.consultar} /></div></Card>
      </div>

      <Card>
        <CardHeader titulo="Cómo la anticipa el predictor" icono={<Waves size={17} />} subtitulo={ficha.contexto} />
        <div className="grid gap-3 px-5 pb-5 md:grid-cols-2">
          {ficha.senales.map((s) => (
            <div key={s.grupo} className="rounded-lg border border-line p-3 text-sm">
              <p className="font-medium">{s.grupo}</p>
              <p className="mt-1 text-ink-2">{s.detalle}</p>
            </div>
          ))}
        </div>
        {conf && (
          <dl className="grid gap-3 border-t border-line px-5 py-4 text-sm sm:grid-cols-3">
            <div><dt className="text-xs text-muted">Umbrales del semáforo</dt>
              <dd className="tabular">P{conf.umbral_amarillo_pct} · P{conf.umbral_naranja_pct} · P{conf.umbral_rojo_pct}</dd></div>
            <div><dt className="text-xs text-muted">Términos de búsqueda vigilados</dt><dd>{conf.terminos_busqueda || "—"}</dd></div>
            <div><dt className="text-xs text-muted">Código CIE-10</dt><dd>{conf.codigo_cie10 || "—"}</dd></div>
          </dl>
        )}
      </Card>
      <p className="text-xs text-muted">Información general de salud pública. Ante síntomas graves acude al servicio de urgencias más cercano.</p>
    </div>
  );
}
