"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MensajeMatriz, PedidoMatriz, ResultadoMatriz } from "@/workers/sensibilidad/mensajes";

/** Hook del worker de la matriz de sensibilidad (mismo patrón que useAnalizadorCsv). */
export function useMatrizSensibilidad() {
  const worker = useRef<Worker | null>(null);
  const actual = useRef(0);
  const [avance, setAvance] = useState<{ recibidos: number; total: number } | null>(null);
  const [resultado, setResultado] = useState<ResultadoMatriz | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const w = new Worker(new URL("../workers/sensibilidad.worker.ts", import.meta.url), { type: "module", name: "matriz-sensibilidad" });
    w.onmessage = (e: MessageEvent<MensajeMatriz>) => {
      const m = e.data;
      if (m.id !== actual.current) return;
      if (m.tipo === "avance") setAvance({ recibidos: m.recibidos, total: m.total });
      else if (m.tipo === "resultado") { setResultado(m.resultado); setAvance(null); }
      else { setError(m.mensaje); setAvance(null); }
    };
    worker.current = w;
    return () => w.terminate();
  }, []);

  const calcular = useCallback((pedido: Omit<PedidoMatriz, "tipo" | "id">) => {
    const id = ++actual.current;
    setError(null);
    setResultado(null);
    setAvance({ recibidos: 0, total: pedido.ejeX.valores.length * pedido.ejeY.valores.length });
    worker.current?.postMessage({ ...pedido, tipo: "calcular", id } satisfies PedidoMatriz);
  }, []);

  return { calcular, avance, resultado, error, calculando: avance !== null };
}
