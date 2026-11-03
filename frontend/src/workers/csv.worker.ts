/// <reference lib="webworker" />
/**
 * Web Worker: lee y valida un CSV en un hilo aparte del navegador.
 *
 * Con un archivo de decenas de miles de filas, parsear y validar en el hilo principal
 * congelaría la página (no responderían los clics ni las animaciones). Aquí el hilo principal
 * solo envía el File y recibe mensajes de avance y el resultado.
 *
 *   principal → worker  { tipo: "analizar", id, archivo, esquema, contexto }
 *   worker → principal  { tipo: "avance", id, filas, fraccion } | { tipo: "resultado", id, resultado }
 *                       | { tipo: "error", id, mensaje }
 */
import { analizarCsv } from "./csv/analizar";
import { decodificar } from "./csv/lector";
import type { MensajeAlWorkerCsv, MensajeDelWorkerCsv } from "./csv/mensajes";

const MAX_BYTES = 20 * 1024 * 1024;
const contexto = self as unknown as DedicatedWorkerGlobalScope;
const enviar = (m: MensajeDelWorkerCsv) => contexto.postMessage(m);

contexto.onmessage = async (e: MessageEvent<MensajeAlWorkerCsv>) => {
  const { id, archivo, esquema, contexto: ctx } = e.data;
  try {
    if (archivo.size > MAX_BYTES) throw new Error("El archivo supera 20 MB");
    const { texto, codificacion } = decodificar(await archivo.arrayBuffer());
    const resultado = analizarCsv(texto, codificacion, esquema, ctx, (filas, fraccion) => enviar({ tipo: "avance", id, filas, fraccion }));
    enviar({ tipo: "resultado", id, resultado });
  } catch (err) {
    enviar({ tipo: "error", id, mensaje: err instanceof Error ? err.message : "No se pudo leer el archivo" });
  }
};
