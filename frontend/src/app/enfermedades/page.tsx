// ============================================================================
// FICHAS DE ENFERMEDADES (índice) — SSG (Static Site Generation)
// ----------------------------------------------------------------------------
// force-static: la página se genera una sola vez en `next build` y se sirve como archivo.
// ============================================================================
import type { Metadata } from "next";
import Link from "next/link";
import { RenderPanel } from "@/components/render/RenderPanel";
import TituloRevelado from "@/components/TituloRevelado";
import { FICHAS } from "@/lib/fichas";

export const dynamic = "force-static";
export const metadata: Metadata = {
  title: "Enfermedades vigiladas",
  description: "IRA, EDA, dengue y afecciones por ceniza volcánica: síntomas, transmisión, prevención y señales que usa el predictor.",
};

const GENERADO_EN = new Date().toISOString(); // se evalúa una vez, al construir

export default function Enfermedades() {
  return (
    <div className="space-y-6">
      <RenderPanel patron="SSG" generadoEn={GENERADO_EN} />
      <header>
        <p className="titulo-seccion text-[13px] text-muted">Fichas informativas</p>
        <TituloRevelado className="titulo-display mt-2 text-5xl sm:text-6xl" texto="Enfermedades vigiladas" />
        <p className="mt-3 max-w-2xl text-ink-2">
          Qué son, cómo se previenen y qué señales usa el modelo para anticipar cada una. La información es general y no
          reemplaza la consulta médica.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.values(FICHAS).map((f) => (
          <Link key={f.codigo} href={`/enfermedades/${f.codigo.toLowerCase()}`} data-ficha={f.codigo}
            className="rounded-lg border border-line bg-surface p-5 transition-colors duration-[520ms] hover:bg-surface-2">
            <p className="font-mono text-xs text-muted">{f.codigo}</p>
            <h2 className="titulo-seccion mt-1 text-xl">{f.nombre}</h2>
            <p className="mt-2 line-clamp-3 text-sm text-ink-2">{f.resumen}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
