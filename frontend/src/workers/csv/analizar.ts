/**
 * Análisis completo de un CSV: columnas, validación fila por fila, vista previa, resumen y un
 * CSV limpio solo con las filas válidas. Es una función pura (no sabe que corre en un worker):
 * recibe el texto y un callback de avance.
 */
import { celda, detectarDelimitador, filasCsv } from "./lector";
import { ESQUEMAS, FilaInvalida, type Contexto, type TipoCsv } from "./esquemas";

export const MAX_ERRORES = 200;
const FILAS_VISTA_PREVIA = 8;

export interface ResultadoCsv {
  tipo: TipoCsv;
  esquema: string;
  delimitador: string;
  codificacion: string;
  columnas: string[];
  faltan: string[];
  sobran: string[];
  filasLeidas: number;
  filasValidas: number;
  errores: { fila: number; mensaje: string }[];
  erroresOmitidos: number;
  vistaPrevia: Record<string, string>[];
  periodo: { desde: string; hasta: string } | null;
  total: { etiqueta: string; valor: number } | null;
  grupos: { etiqueta: string; valores: [string, number][] } | null;
  duplicadas: number;
  /** Filas válidas ya convertidas (las usa la carga por client streaming de farmacias). */
  normalizadas: Record<string, string | number | null>[];
  /** CSV con encabezado y solo las filas válidas, listo para subir. */
  csvValido: string;
  duracionMs: number;
}

export function analizarCsv(texto: string, codificacion: string, tipo: TipoCsv, ctx: Contexto,
  avance: (filas: number, fraccion: number) => void = () => {}): ResultadoCsv {
  const inicio = performance.now();
  const esquema = ESQUEMAS[tipo];
  const delimitador = detectarDelimitador(texto.slice(0, texto.search(/\r?\n|$/)));
  const filas = filasCsv(texto, delimitador);
  const encabezado = filas.next();
  const vacio = encabezado.done;
  const columnas = vacio ? [] : encabezado.value.campos.map((c) => c.trim().toLowerCase());
  const faltan = esquema.columnas.filter((c) => !columnas.includes(c) && !esquema.opcionales.includes(c));
  const sobran = columnas.filter((c) => c && !esquema.columnas.includes(c));

  const r: ResultadoCsv = {
    tipo, esquema: esquema.nombre, delimitador, codificacion, columnas, faltan, sobran, filasLeidas: 0, filasValidas: 0,
    errores: [], erroresOmitidos: 0, vistaPrevia: [], periodo: null, total: null, grupos: null, duplicadas: 0,
    normalizadas: [], csvValido: "", duracionMs: 0,
  };
  if (vacio || faltan.length) {
    r.duracionMs = performance.now() - inicio;
    return r;
  }

  const lineasValidas = [columnas.map(celda).join(",")];
  const grupos = new Map<string, number>();
  const vistas = new Set<string>();
  let total = 0;
  let desde: string | null = null;
  let hasta: string | null = null;
  let numero = 1; // el encabezado es la fila 1
  for (const { campos, fin } of filas) {
    numero++;
    r.filasLeidas++;
    const fila: Record<string, string> = {};
    columnas.forEach((c, i) => { if (c) fila[c] = campos[i] ?? ""; });
    if (r.vistaPrevia.length < FILAS_VISTA_PREVIA) r.vistaPrevia.push(fila);
    try {
      const n = esquema.convertir(fila, ctx);
      const clave = JSON.stringify(n);
      if (vistas.has(clave)) r.duplicadas++;
      vistas.add(clave);
      r.filasValidas++;
      r.normalizadas.push({ fila: numero, ...n });
      lineasValidas.push(columnas.map((c) => celda(fila[c] ?? "")).join(","));
      const p = esquema.periodo(n);
      if (desde === null || p < desde) desde = p;
      if (hasta === null || p > hasta) hasta = p;
      if (esquema.total) total += Number(n[esquema.total.columna] ?? 0);
      if (esquema.grupo) { const g = String(n[esquema.grupo.columna]); grupos.set(g, (grupos.get(g) ?? 0) + 1); }
    } catch (e) {
      if (!(e instanceof FilaInvalida)) throw e;
      if (r.errores.length < MAX_ERRORES) r.errores.push({ fila: numero, mensaje: e.message });
      else r.erroresOmitidos++;
    }
    if (r.filasLeidas % 2000 === 0) avance(r.filasLeidas, fin / texto.length);
  }
  avance(r.filasLeidas, 1);
  r.periodo = desde && hasta ? { desde, hasta } : null;
  r.total = esquema.total ? { etiqueta: esquema.total.etiqueta, valor: Math.round(total * 10) / 10 } : null;
  r.grupos = esquema.grupo ? { etiqueta: esquema.grupo.etiqueta, valores: [...grupos].sort((a, b) => b[1] - a[1]) } : null;
  r.csvValido = lineasValidas.join("\n") + "\n";
  r.duracionMs = performance.now() - inicio;
  return r;
}
