// ============================================================================
// METODOLOGÍA — SSG (Static Site Generation)
// ----------------------------------------------------------------------------
// Texto que solo cambia cuando cambia el código: se genera una vez en el build.
// ============================================================================
import type { Metadata } from "next";
import { RenderPanel } from "@/components/render/RenderPanel";
import TituloRevelado from "@/components/TituloRevelado";
import { Card, CardHeader } from "@/components/ui";
import { ORDEN, PATRONES } from "@/lib/patrones";

export const dynamic = "force-static";
export const metadata: Metadata = {
  title: "Metodología y arquitectura",
  description: "Cómo se construye el dataset, cómo se entrena y valida el modelo y cómo está armada la aplicación web.",
};

const GENERADO_EN = new Date().toISOString();

const RPCS = [
  { tipo: "Unary", metodo: "Estado, Predecir", web: "GET → JSON", uso: "Pronóstico calculado al momento con el modelo en memoria" },
  { tipo: "Server streaming", metodo: "Entrenar, SeguirAlertas", web: "SSE (EventSource / fetch)", uso: "Avance del entrenamiento y alertas en vivo" },
  { tipo: "Client streaming", metodo: "CargarReportesFarmacia", web: "POST de filas → stream", uso: "Carga masiva del histórico de una farmacia" },
  { tipo: "Bidireccional", metodo: "SimularEscenarios", web: "WebSocket ↔ stream", uso: "Simulador «¿qué pasa si…?»" },
];

function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader titulo={titulo} />
      <div className="space-y-3 px-5 pb-5 text-sm leading-relaxed text-ink-2">{children}</div>
    </Card>
  );
}

export default function Metodologia() {
  return (
    <div className="space-y-6">
      <RenderPanel patron="SSG" generadoEn={GENERADO_EN} />
      <header>
        <p className="titulo-seccion text-[13px] text-muted">Cómo funciona</p>
        <TituloRevelado className="titulo-display mt-2 text-5xl sm:text-6xl" texto="Metodología y arquitectura" />
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <Seccion titulo="1. Datos">
          <p>Para cada municipio y semana epidemiológica se reúnen: casos oficiales (SIVIGILA, datos.gov.co), clima observado y
            pronosticado (Open-Meteo), índice de búsquedas de síntomas en Nariño (Google Trends), ventas semanales de farmacias
            participantes por categoría y boletines del Servicio Geológico Colombiano (SO₂ y caída de ceniza).</p>
          <p>Un cron de GitHub Actions actualiza todo cada día a las 6 a. m. y al terminar pide al frontend regenerar los tableros (ISR).</p>
        </Seccion>
        <Seccion titulo="2. Dataset sin fuga de datos">
          <p>Cada fila es «lo que se sabe al cerrar la semana t». Todas las variables usan información de t o anterior; los objetivos
            son los casos de t+1 a t+4. Una prueba automática verifica que cambiar casos futuros no cambia las variables de hoy.</p>
        </Seccion>
        <Seccion titulo="3. Modelos y validación">
          <p>Se comparan la línea base (promedio móvil de 4 semanas), Random Forest y Gradient Boosting, uno por horizonte, con
            validación temporal sobre las últimas 52 semanas (nunca se mezcla futuro con pasado). Gana el de menor MAE y se reentrena
            con todos los datos. El intervalo del 80 % sale de los cuantiles 10 y 90 de los residuos.</p>
        </Seccion>
        <Seccion titulo="4. Semáforo y alertas">
          <p>El canal endémico usa los percentiles 50, 75 y 90 de las semanas S−1, S y S+1 de los 5 años anteriores. Hay alerta cuando
            el nivel observado o el predicho llega a naranja o rojo (con un mínimo de 3 casos). Las alertas se envían por correo y llegan
            en vivo al navegador por el stream del motor.</p>
        </Seccion>
      </div>

      <Card>
        <CardHeader titulo="5. Arquitectura web" subtitulo="Next.js en Vercel · FastAPI y motor gRPC en Render · PostgreSQL en Neon" />
        <div className="space-y-5 px-5 pb-5 text-sm">
          <pre className="overflow-x-auto rounded-lg bg-surface-2 p-4 font-mono text-[12px] leading-relaxed text-ink-2">{`Navegador ──HTML (SSG/ISR/SSR)──► Next.js (Vercel) ──fetch en el servidor──┐
    │                                                                    ▼
    ├── JSON · SSE · WebSocket ──────────────────────────────► FastAPI (Render, público)
    │                                                                    │ gRPC (HTTP/2, 127.0.0.1)
    └── Web Workers (CSV, matriz de sensibilidad)                        ▼
                                                           Motor de predicción (Python)
                                                                         │
                                                                PostgreSQL (Neon)`}</pre>

          <div>
            <h3 className="titulo-seccion text-base">Patrones de rendering</h3>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="border-b border-line text-xs text-muted"><tr><th className="py-2 pr-3">Patrón</th><th className="pr-3">Dónde se genera</th><th className="pr-3">Páginas</th></tr></thead>
                <tbody>
                  {ORDEN.map((p) => (
                    <tr key={p} className="border-b border-line align-top">
                      <td className="py-2 pr-3 font-mono font-bold" style={{ color: `var(--pat-${p.toLowerCase()})` }}>{p}</td>
                      <td className="py-2 pr-3 text-ink-2">{PATRONES[p].donde}</td>
                      <td className="py-2 pr-3 text-ink-2">{PATRONES[p].paginas.map((x) => x.nombre).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="titulo-seccion text-base">Motor gRPC: los cuatro tipos de RPC</h3>
            <p className="mt-1 text-ink-2">El navegador no habla gRPC (no expone HTTP/2 con trailers) y Render solo publica un puerto HTTP. Por eso
              el motor escucha en 127.0.0.1 y FastAPI es su cliente: traduce cada tipo de RPC al mecanismo web equivalente.</p>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="border-b border-line text-xs text-muted"><tr><th className="py-2 pr-3">Tipo</th><th className="pr-3">RPC</th><th className="pr-3">Puente web</th><th>Para qué</th></tr></thead>
                <tbody>
                  {RPCS.map((r) => (
                    <tr key={r.tipo} className="border-b border-line align-top">
                      <td className="py-2 pr-3 font-medium">{r.tipo}</td><td className="py-2 pr-3 font-mono text-xs">{r.metodo}</td>
                      <td className="py-2 pr-3 text-ink-2">{r.web}</td><td className="py-2 text-ink-2">{r.uso}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="titulo-seccion text-base">Web Workers</h3>
            <p className="mt-1 text-ink-2">Dos tareas pesadas corren en hilos aparte del navegador para que la interfaz no se congele:
              leer y validar CSV de miles de filas antes de subirlos (panel de administración y de farmacia) y armar la matriz de
              sensibilidad del simulador, que envía decenas de escenarios por su propio WebSocket y agrega los resultados.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
