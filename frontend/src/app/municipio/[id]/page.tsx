// ============================================================================
// TABLERO DE UN MUNICIPIO — ISR (Incremental Static Regeneration)
// ----------------------------------------------------------------------------
// - generateStaticParams: en el build se genera un HTML por cada municipio activo.
// - revalidate: la versión en caché vale como máximo 1 hora; la siguiente visita después de
//   eso recibe la versión vieja y dispara la regeneración en segundo plano.
// - Revalidación bajo demanda: el backend llama a /api/revalidar al terminar el cron diario
//   o un reentrenamiento, así el tablero se regenera apenas hay datos nuevos.
// - dynamicParams: un municipio creado después del build se genera en su primera visita.
// ============================================================================
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RenderPanel } from "@/components/render/RenderPanel";
import { cargarTablero, municipiosActivos, SEMANAS_MAXIMAS } from "@/lib/tablero";
import TableroMunicipio from "@/vistas/TableroMunicipio";

export const revalidate = 3600; // = REVALIDAR_TABLEROS (Next.js exige un literal aquí)
export const dynamicParams = true;

type Props = { params: Promise<{ id: string }> };

export async function generateStaticParams() {
  try {
    return (await municipiosActivos()).map((m) => ({ id: String(m.id) }));
  } catch {
    // La API (Render, plan gratis) puede estar dormida durante el build: entonces cada
    // tablero se genera en su primera visita y desde ahí queda en caché igual.
    return [];
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const municipio = (await municipiosActivos().catch(() => [])).find((m) => String(m.id) === id);
  return {
    title: municipio ? `Riesgo de brotes en ${municipio.nombre}` : "Tablero municipal",
    description: municipio
      ? `Semáforo epidemiológico, predicción a 4 semanas y clima de ${municipio.nombre} (zona del Volcán Galeras).`
      : undefined,
  };
}

export default async function PaginaMunicipio({ params }: Props) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const datos = await cargarTablero(Number(id));
  if (!datos) notFound();

  return (
    <div className="space-y-5">
      <RenderPanel patron="ISR" generadoEn={datos.generadoEn} ruta={`/municipio/${id}`}
        detalles={[
          { etiqueta: "Peticiones a la API al generar", valor: `${datos.peticiones} (en paralelo)` },
          { etiqueta: "Datos incluidos en el HTML", valor: `${datos.resumen.riesgos.length} enfermedades × ${SEMANAS_MAXIMAS} semanas` },
        ]} />
      <TableroMunicipio datos={datos} />
    </div>
  );
}
