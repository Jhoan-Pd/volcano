"use client";

import { useEffect, useState } from "react";
import { RenderPanel } from "./RenderPanel";

/**
 * Panel para páginas CSR: la "hora de generación" es el momento en que el navegador montó la
 * página y empezó a pedir sus datos (en el HTML del servidor queda vacío).
 */
export function PanelCSR({ porQue, detalles }: { porQue?: string; detalles?: { etiqueta: string; valor: string }[] }) {
  const [montado, setMontado] = useState<string | null>(null);
  useEffect(() => setMontado(new Date().toISOString()), []);
  return <RenderPanel patron="CSR" generadoEn={montado} porQue={porQue} detalles={detalles} />;
}
