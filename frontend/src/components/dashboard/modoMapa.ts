import type { Nivel, RiesgoMunicipio } from "@/api/tipos";

// Separado de MapaRiesgo.tsx: Leaflet usa `window` al importarse, así que ese módulo solo se
// carga en el navegador (next/dynamic con ssr: false); esto en cambio sirve en el servidor.
export type ModoMapa = "actual" | "predicho";

/** Nivel que se pinta para un municipio según el modo y la enfermedad elegida ("" = la peor). */
export function nivelDe(f: RiesgoMunicipio, modo: ModoMapa, codigo: string): Nivel {
  const detalle = modo === "actual" ? f.detalle : f.detalle_predicho;
  if (codigo) return detalle[codigo] ?? "VERDE";
  if (modo === "predicho") return f.nivel_max_predicho ?? "VERDE";
  return f.nivel_max;
}


/** Props comunes de los dos mapas (Google Maps y Leaflet). */
export interface PropsMapa {
  filas: RiesgoMunicipio[]; modo: ModoMapa; codigo: string; enfermedades: { codigo: string; nombre: string }[];
  seleccionado: number | null; onSeleccionar: (id: number) => void;
}
