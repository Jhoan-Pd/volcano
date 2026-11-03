"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ResultadoCsv } from "@/workers/csv/analizar";
import type { Contexto, TipoCsv } from "@/workers/csv/esquemas";
import type { MensajeAlWorkerCsv, MensajeDelWorkerCsv } from "@/workers/csv/mensajes";

export interface AvanceCsv {
  filas: number;
  fraccion: number;
}

/**
 * Hook que encapsula el Web Worker de CSV: lo crea al montar, lo termina al desmontar y
 * convierte su protocolo de mensajes en una promesa (`analizar(archivo)`), con el avance en
 * el estado. `cancelar()` termina el worker a la fuerza (no hay forma más rápida de detener
 * un cálculo en otro hilo) y crea uno nuevo.
 */
export function useAnalizadorCsv() {
  const worker = useRef<Worker | null>(null);
  const pendiente = useRef<{ id: number; resolver: (r: ResultadoCsv) => void; rechazar: (e: Error) => void } | null>(null);
  const siguienteId = useRef(1);
  const [avance, setAvance] = useState<AvanceCsv | null>(null);

  const crear = useCallback(() => {
    // `new URL(..., import.meta.url)` le indica a Next.js que empaquete el worker como un archivo aparte
    const w = new Worker(new URL("../workers/csv.worker.ts", import.meta.url), { type: "module", name: "analizador-csv" });
    w.onmessage = (e: MessageEvent<MensajeDelWorkerCsv>) => {
      const m = e.data;
      const p = pendiente.current;
      if (!p || m.id !== p.id) return; // respuesta de un análisis ya cancelado
      if (m.tipo === "avance") setAvance({ filas: m.filas, fraccion: m.fraccion });
      else {
        pendiente.current = null;
        setAvance(null);
        if (m.tipo === "resultado") p.resolver(m.resultado);
        else p.rechazar(new Error(m.mensaje));
      }
    };
    w.onerror = (e) => {
      pendiente.current?.rechazar(new Error(e.message || "El worker falló"));
      pendiente.current = null;
      setAvance(null);
    };
    worker.current = w;
  }, []);

  useEffect(() => {
    crear();
    return () => worker.current?.terminate();
  }, [crear]);

  const analizar = useCallback((archivo: File, esquema: TipoCsv, contexto: Contexto) =>
    new Promise<ResultadoCsv>((resolver, rechazar) => {
      if (!worker.current) return rechazar(new Error("El navegador no pudo iniciar el worker"));
      const id = siguienteId.current++;
      pendiente.current = { id, resolver, rechazar };
      setAvance({ filas: 0, fraccion: 0 });
      const mensaje: MensajeAlWorkerCsv = { tipo: "analizar", id, archivo, esquema, contexto };
      worker.current.postMessage(mensaje);
    }), []);

  const cancelar = useCallback(() => {
    worker.current?.terminate();
    pendiente.current?.rechazar(new Error("Análisis cancelado"));
    pendiente.current = null;
    setAvance(null);
    crear();
  }, [crear]);

  return { analizar, cancelar, avance, analizando: avance !== null };
}
