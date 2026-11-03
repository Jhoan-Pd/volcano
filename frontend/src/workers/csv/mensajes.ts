import type { ResultadoCsv } from "./analizar";
import type { Contexto, TipoCsv } from "./esquemas";

/** Protocolo de mensajes entre la página y el worker de CSV (tipado en los dos lados). */
export interface MensajeAlWorkerCsv {
  tipo: "analizar";
  id: number;
  archivo: File;
  esquema: TipoCsv;
  contexto: Contexto;
}

export type MensajeDelWorkerCsv =
  | { tipo: "avance"; id: number; filas: number; fraccion: number }
  | { tipo: "resultado"; id: number; resultado: ResultadoCsv }
  | { tipo: "error"; id: number; mensaje: string };
