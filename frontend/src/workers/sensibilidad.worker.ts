/// <reference lib="webworker" />
/**
 * Web Worker: matriz de sensibilidad del simulador.
 *
 * Para dos variables (p. ej. lluvia × búsquedas) arma una grilla de escenarios, abre SU PROPIO
 * WebSocket al simulador (stream bidireccional del motor gRPC), envía todos los escenarios de
 * una vez y va recibiendo los resultados identificados por su id. Agrega cada respuesta en la
 * matriz y al final calcula mínimo y máximo.
 *
 * Todo eso (decenas de mensajes, JSON.parse, agregación) ocurre fuera del hilo principal: la
 * página solo recibe el avance y la matriz terminada para pintarla.
 */
import type { ResultadoEscenario } from "@/api/tipos";
import type { Celda, MensajeMatriz, PedidoMatriz } from "./sensibilidad/mensajes";

const contexto = self as unknown as DedicatedWorkerGlobalScope;
const enviar = (m: MensajeMatriz) => contexto.postMessage(m);
const TIEMPO_MAXIMO_MS = 90_000;

contexto.onmessage = (e: MessageEvent<PedidoMatriz>) => {
  const { id, url, base, ejeX, ejeY } = e.data;
  const total = ejeX.valores.length * ejeY.valores.length;
  const celdas: (Celda | null)[][] = ejeY.valores.map(() => ejeX.valores.map(() => null));
  const inicio = performance.now();
  let recibidos = 0;
  let motorMs = 0;
  let totalBase = 0;
  let terminado = false;

  const ws = new WebSocket(url);
  const reloj = setTimeout(() => fallar("El motor tardó demasiado en responder"), TIEMPO_MAXIMO_MS);
  function fallar(mensaje: string) {
    if (terminado) return;
    terminado = true;
    clearTimeout(reloj);
    ws.close();
    enviar({ tipo: "error", id, mensaje });
  }

  ws.onopen = () => {
    ejeY.valores.forEach((y, fila) => ejeX.valores.forEach((x, col) => {
      ws.send(JSON.stringify({ ...base, [ejeX.campo]: x, [ejeY.campo]: y, id: `m${id}:${fila}:${col}` }));
    }));
  };
  ws.onerror = () => fallar("No se pudo conectar con el simulador");
  ws.onclose = () => fallar("La conexión con el simulador se cerró antes de terminar");
  ws.onmessage = (ev) => {
    const r = JSON.parse(ev.data as string) as ResultadoEscenario;
    if (r.fatal) return fallar(r.error ?? "El motor no está disponible");
    const [, fila, col] = (r.id ?? "").split(":").map(Number);
    if (!Number.isInteger(fila) || !Number.isInteger(col)) return;
    if (r.error) return fallar(r.error);
    const casos = (r.escenario ?? []).reduce((s, p) => s + p.casos_esperados, 0);
    totalBase = (r.base ?? []).reduce((s, p) => s + p.casos_esperados, 0);
    motorMs += r.duracion_ms ?? 0;
    celdas[fila][col] = { total: Math.round(casos * 10) / 10, nivel: r.nivel_max ?? null, variacion: r.variacion_pct ?? 0 };
    recibidos++;
    enviar({ tipo: "avance", id, recibidos, total });
    if (recibidos === total) {
      terminado = true;
      clearTimeout(reloj);
      ws.close();
      const valores = celdas.flat().map((c) => c!.total);
      enviar({
        tipo: "resultado", id, resultado: {
          celdas: celdas as Celda[][], minimo: Math.min(...valores), maximo: Math.max(...valores),
          totalBase: Math.round(totalBase * 10) / 10, escenarios: total, duracionMs: performance.now() - inicio,
          motorMs: Math.round(motorMs),
        },
      });
    }
  };
};
