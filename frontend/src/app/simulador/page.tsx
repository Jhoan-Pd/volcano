// ============================================================================
// SIMULADOR «¿QUÉ PASA SI…?» — CSR (Client-Side Rendering)
// ----------------------------------------------------------------------------
// Conversación en vivo con el motor: el navegador abre un WebSocket y la API lo conecta con el
// stream BIDIRECCIONAL de gRPC SimularEscenarios. La matriz de sensibilidad la calcula un
// Web Worker con su propio WebSocket. También muestra una llamada unary (Predecir).
// ============================================================================
import type { Metadata } from "next";
import Simulador from "@/vistas/Simulador";

export const metadata: Metadata = { title: "Simulador de escenarios", description: "¿Qué pasa si llueve más o suben las búsquedas? El modelo responde en vivo." };

export default function PaginaSimulador() {
  return <Simulador />;
}
