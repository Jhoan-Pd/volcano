import type { Escenario, Nivel } from "@/api/tipos";

export type CampoEscenario = "delta_temperatura_c" | "cambio_lluvia_pct" | "cambio_busquedas_pct" | "cambio_farmacias_pct";

export interface Eje {
  campo: CampoEscenario;
  valores: number[];
}

/** Protocolo entre la página del simulador y el worker de la matriz de sensibilidad. */
export interface PedidoMatriz {
  tipo: "calcular";
  id: number;
  url: string;
  base: Omit<Escenario, "id">;
  ejeX: Eje;
  ejeY: Eje;
}

export interface Celda {
  total: number;
  nivel: Nivel | null;
  variacion: number;
}

export interface ResultadoMatriz {
  celdas: Celda[][]; // [fila (eje Y)][columna (eje X)]
  minimo: number;
  maximo: number;
  totalBase: number;
  escenarios: number;
  duracionMs: number;
  motorMs: number; // suma del tiempo de cálculo dentro del motor
}

export type MensajeMatriz =
  | { tipo: "avance"; id: number; recibidos: number; total: number }
  | { tipo: "resultado"; id: number; resultado: ResultadoMatriz }
  | { tipo: "error"; id: number; mensaje: string };
