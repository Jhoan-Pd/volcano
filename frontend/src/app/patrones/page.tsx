// ============================================================================
// COMPARATIVA DE PATRONES — SSG + una isla de cliente
// ----------------------------------------------------------------------------
// La teoría es estática (se genera en el build) y el <Medidor /> es un componente de cliente
// que corre en el navegador y mide las cuatro páginas representativas.
// ============================================================================
import type { Metadata } from "next";
import { RenderPanel } from "@/components/render/RenderPanel";
import TituloRevelado from "@/components/TituloRevelado";
import { Card, CardHeader } from "@/components/ui";
import { ORDEN, PATRONES, type InfoPatron } from "@/lib/patrones";
import { Medidor } from "./Medidor";

export const dynamic = "force-static";
export const metadata: Metadata = { title: "Patrones de rendering", description: "SSG, ISR, SSR y CSR en el predictor de brotes, medidos en vivo." };

const GENERADO_EN = new Date().toISOString();

const FILAS: { etiqueta: string; campo: keyof Pick<InfoPatron, "donde" | "cuando" | "seo" | "frescura" | "costo"> }[] = [
  { etiqueta: "¿Dónde se genera el HTML?", campo: "donde" },
  { etiqueta: "¿Cuándo?", campo: "cuando" },
  { etiqueta: "SEO", campo: "seo" },
  { etiqueta: "Frescura de los datos", campo: "frescura" },
  { etiqueta: "Costo en el servidor", campo: "costo" },
];

export default function Patrones() {
  return (
    <div className="space-y-6">
      <RenderPanel patron="SSG" generadoEn={GENERADO_EN}
        porQue="La explicación no cambia con los datos: se genera en el build. Solo el medidor de abajo se ejecuta en tu navegador." />
      <header>
        <p className="titulo-seccion text-[13px] text-muted">Programación orientada a la web</p>
        <TituloRevelado className="titulo-display mt-2 text-5xl sm:text-6xl" texto="Patrones de rendering" />
        <p className="mt-3 max-w-3xl text-ink-2">Cada sección del predictor usa el patrón que mejor se ajusta a qué tan seguido cambian sus
          datos, si necesita SEO y si depende del usuario. Arriba de cada página hay un panel que muestra cómo se generó.</p>
      </header>

      <Medidor />

      <Card>
        <CardHeader titulo="Resumen" />
        <div className="overflow-x-auto px-5 pb-5">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className="py-2 pr-3 text-xs text-muted">Criterio</th>
                {ORDEN.map((p) => (
                  <th key={p} className="py-2 pr-3">
                    <span className="font-mono font-bold" style={{ color: `var(--pat-${p.toLowerCase()})` }}>{p}</span>
                    <span className="block text-xs font-normal text-muted">{PATRONES[p].nombre}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {FILAS.map((f) => (
                <tr key={f.campo} className="border-b border-line align-top">
                  <th className="py-2 pr-3 text-xs font-medium text-ink-2">{f.etiqueta}</th>
                  {ORDEN.map((p) => <td key={p} className="py-2 pr-3 text-ink-2">{PATRONES[p][f.campo]}</td>)}
                </tr>
              ))}
              <tr className="align-top">
                <th className="py-2 pr-3 text-xs font-medium text-ink-2">En el predictor</th>
                {ORDEN.map((p) => <td key={p} className="py-2 pr-3 text-ink-2">{PATRONES[p].paginas.map((x) => x.nombre).join(", ")}</td>)}
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {ORDEN.map((p) => (
          <Card key={p}>
            <CardHeader titulo={`¿Por qué ${p}?`} />
            <p className="px-5 pb-5 text-sm text-ink-2">{PATRONES[p].porQue}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
