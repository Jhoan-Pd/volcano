// ============================================================================
// MAPA EN VIVO — CSR (Client-Side Rendering)
// ----------------------------------------------------------------------------
// El servidor entrega solo el cascarón. <MapaEnVivo /> se ejecuta en el navegador: carga
// Leaflet con next/dynamic (ssr: false), pide el riesgo por fetch y escucha las alertas por
// Server-Sent Events, que la API alimenta con el stream gRPC SeguirAlertas del motor.
// ============================================================================
import type { Metadata } from "next";
import MapaEnVivo from "@/vistas/MapaEnVivo";

export const metadata: Metadata = { title: "Mapa de riesgo en vivo" };

export default function PaginaMapa() {
  return (
    <MapaEnVivo encabezado={
      <header>
        <p className="titulo-seccion text-[13px] text-muted">Zona de influencia del Volcán Galeras</p>
        <h1 className="titulo-display mt-2 text-5xl sm:text-6xl">Mapa en vivo</h1>
        <p className="mt-2 max-w-2xl text-ink-2">Todo lo que ves abajo lo dibuja tu navegador. Las alertas llegan solas, sin recargar.</p>
      </header>
    } />
  );
}
