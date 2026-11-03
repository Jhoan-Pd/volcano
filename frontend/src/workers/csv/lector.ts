/**
 * Lector de CSV sin dependencias (RFC 4180): comillas, comillas dobles escapadas ("") y saltos
 * de línea dentro de un campo entre comillas. Es un generador: entrega fila por fila para que
 * quien lo usa pueda informar el avance sin esperar a leer todo el archivo.
 */
export function detectarDelimitador(primeraLinea: string): "," | ";" {
  const contar = (c: string) => primeraLinea.split(c).length - 1;
  return contar(";") > contar(",") ? ";" : ",";
}

/** Decodifica como UTF-8 y, si no es válido, como Windows-1252 (Excel en español guarda en «ANSI»). */
export function decodificar(bytes: ArrayBuffer): { texto: string; codificacion: string } {
  try {
    return { texto: new TextDecoder("utf-8", { fatal: true }).decode(bytes).replace(/^﻿/, ""), codificacion: "UTF-8" };
  } catch {
    return { texto: new TextDecoder("windows-1252").decode(bytes), codificacion: "Windows-1252 (ANSI)" };
  }
}

export function* filasCsv(texto: string, delimitador: string): Generator<{ campos: string[]; fin: number }> {
  let campo = "";
  let fila: string[] = [];
  let comillas = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (comillas) {
      if (c === '"') {
        if (texto[i + 1] === '"') { campo += '"'; i++; } else comillas = false;
      } else campo += c;
    } else if (c === '"') comillas = true;
    else if (c === delimitador) { fila.push(campo); campo = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && texto[i + 1] === "\n") i++;
      fila.push(campo);
      if (fila.some((x) => x.trim() !== "")) yield { campos: fila, fin: i + 1 };
      fila = []; campo = "";
    } else campo += c;
  }
  fila.push(campo);
  if (fila.some((x) => x.trim() !== "")) yield { campos: fila, fin: texto.length };
}

/** Escapa un valor para volver a escribirlo en CSV. */
export const celda = (v: string) => (/[",;\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
