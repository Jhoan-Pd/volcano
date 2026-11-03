/**
 * Reglas de cada tipo de CSV. Son las mismas que aplica el backend (importacion_service.py y
 * el servicio de farmacias): revisarlas en el navegador permite mostrar los errores ANTES de
 * subir el archivo. El backend las vuelve a aplicar (nunca se confía solo en el cliente).
 */
export type TipoCsv = "casos" | "clima" | "eventos" | "tendencias" | "farmacia";

export interface Contexto {
  municipios: string[]; // códigos DIVIPOLA válidos
  enfermedades: string[]; // códigos de enfermedad (IRA, EDA…)
  categorias: string[]; // categorías de farmacia
}

type Fila = Record<string, string>;
type Normalizada = Record<string, string | number | null>;
export class FilaInvalida extends Error {}

const DIA = 86_400_000;
/** Semanas epidemiológicas del año (sistema MMWR/CDC, el mismo de la librería epiweeks del backend). */
export function semanasDelAnio(anio: number): number {
  const inicio = (a: number) => { const d = Date.UTC(a, 0, 4); return d - new Date(d).getUTCDay() * DIA; };
  return Math.round((inicio(anio + 1) - inicio(anio)) / (7 * DIA));
}

function entero(v: string, campo: string, min?: number, max?: number): number {
  const n = Number(v.trim().replace(",", "."));
  if (v.trim() === "" || !Number.isFinite(n)) throw new FilaInvalida(`«${campo}» debe ser un número entero (llegó «${v}»)`);
  const e = Math.trunc(n);
  if ((min !== undefined && e < min) || (max !== undefined && e > max)) throw new FilaInvalida(`«${campo}» fuera de rango (${e})`);
  return e;
}
function decimal(v: string | undefined, campo: string): number | null {
  if (v === undefined || v.trim() === "") return null;
  const n = Number(v.trim().replace(",", "."));
  if (!Number.isFinite(n)) throw new FilaInvalida(`«${campo}» debe ser numérico (llegó «${v}»)`);
  return n;
}
function fecha(v: string, campo: string): string {
  const t = v.trim();
  const d = new Date(`${t}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t) || Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== t) {
    throw new FilaInvalida(`«${campo}» debe tener formato AAAA-MM-DD (llegó «${v}»)`);
  }
  return t;
}
function municipio(v: string | undefined, ctx: Contexto): string {
  const c = (v ?? "").trim();
  if (!ctx.municipios.includes(c)) throw new FilaInvalida(`Municipio «${c}» no existe (código DIVIPOLA)`);
  return c;
}
function semana(f: Fila): { anio: number; semana_epi: number } {
  const anio = entero(f.anio, "anio", 2000, 2100);
  return { anio, semana_epi: entero(f.semana_epi, "semana_epi", 1, semanasDelAnio(anio)) };
}

export interface Esquema {
  nombre: string;
  columnas: string[];
  opcionales: string[];
  /** Columna que identifica la «semana» o la fecha de la fila, para el resumen. */
  periodo: (n: Normalizada) => string;
  total?: { columna: string; etiqueta: string };
  grupo?: { columna: string; etiqueta: string };
  convertir: (f: Fila, ctx: Contexto) => Normalizada;
}

const etiquetaSemana = (n: Normalizada) => `${n.anio}-S${String(n.semana_epi).padStart(2, "0")}`;

export const ESQUEMAS: Record<TipoCsv, Esquema> = {
  casos: {
    nombre: "Casos oficiales", columnas: ["cod_divipola", "enfermedad", "anio", "semana_epi", "casos"], opcionales: [],
    periodo: etiquetaSemana, total: { columna: "casos", etiqueta: "casos" }, grupo: { columna: "enfermedad", etiqueta: "Por enfermedad" },
    convertir: (f, ctx) => {
      const enf = f.enfermedad.trim().toUpperCase();
      if (!ctx.enfermedades.includes(enf)) throw new FilaInvalida(`Enfermedad «${f.enfermedad}» no existe`);
      return { cod_divipola: municipio(f.cod_divipola, ctx), enfermedad: enf, ...semana(f), casos: entero(f.casos, "casos", 0) };
    },
  },
  clima: {
    nombre: "Clima diario", columnas: ["cod_divipola", "fecha", "temp_max_c", "temp_min_c", "temp_media_c", "precipitacion_mm", "humedad_relativa_pct"],
    opcionales: ["temp_max_c", "temp_min_c", "temp_media_c", "precipitacion_mm", "humedad_relativa_pct"],
    periodo: (n) => String(n.fecha), total: { columna: "precipitacion_mm", etiqueta: "mm de lluvia" },
    convertir: (f, ctx) => {
      const n: Normalizada = { cod_divipola: municipio(f.cod_divipola, ctx), fecha: fecha(f.fecha, "fecha") };
      for (const c of ["temp_max_c", "temp_min_c", "temp_media_c", "precipitacion_mm", "humedad_relativa_pct"]) n[c] = decimal(f[c], c);
      const h = n.humedad_relativa_pct as number | null;
      if (h !== null && (h < 0 || h > 100)) throw new FilaInvalida("La humedad debe estar entre 0 y 100");
      return n;
    },
  },
  eventos: {
    nombre: "Eventos volcánicos", columnas: ["tipo", "nivel_actividad", "fecha_inicio", "cod_divipola", "intensidad_ceniza", "so2_ton_dia", "descripcion"],
    opcionales: ["cod_divipola", "intensidad_ceniza", "so2_ton_dia", "descripcion"],
    periodo: (n) => String(n.fecha_inicio), grupo: { columna: "tipo", etiqueta: "Por tipo" },
    convertir: (f, ctx) => {
      const tipo = f.tipo.trim().toUpperCase();
      const nivel = f.nivel_actividad.trim().toUpperCase();
      if (!["BOLETIN", "CAIDA_CENIZA", "EMISION_GASES", "SISMO"].includes(tipo)) throw new FilaInvalida(`Tipo «${f.tipo}» no válido`);
      if (!["VERDE", "AMARILLO", "NARANJA", "ROJO"].includes(nivel)) throw new FilaInvalida(`Nivel «${f.nivel_actividad}» no válido (VERDE, AMARILLO, NARANJA o ROJO)`);
      const cod = (f.cod_divipola ?? "").trim();
      const intensidad = entero(f.intensidad_ceniza?.trim() ? f.intensidad_ceniza : "0", "intensidad_ceniza", 0, 3);
      if (tipo === "CAIDA_CENIZA" && (!cod || intensidad === 0)) throw new FilaInvalida("Una caída de ceniza necesita municipio e intensidad entre 1 y 3");
      return { tipo, nivel_actividad: nivel, fecha_inicio: fecha(f.fecha_inicio, "fecha_inicio"),
        cod_divipola: cod ? municipio(cod, ctx) : null, intensidad_ceniza: intensidad, so2_ton_dia: decimal(f.so2_ton_dia, "so2_ton_dia") };
    },
  },
  tendencias: {
    nombre: "Búsquedas (Google Trends)", columnas: ["termino", "fecha_semana", "indice"], opcionales: [],
    periodo: (n) => String(n.fecha_semana), grupo: { columna: "termino", etiqueta: "Por término" },
    convertir: (f) => {
      const termino = f.termino.trim().toLowerCase();
      if (!termino) throw new FilaInvalida("Falta el término");
      const indice = decimal(f.indice, "indice");
      if (indice === null || indice < 0 || indice > 100) throw new FilaInvalida("El índice debe estar entre 0 y 100");
      return { termino, fecha_semana: fecha(f.fecha_semana, "fecha_semana"), indice };
    },
  },
  farmacia: {
    nombre: "Reportes de farmacia", columnas: ["anio", "semana_epi", "categoria", "unidades", "farmacia_id"], opcionales: ["farmacia_id"],
    periodo: etiquetaSemana, total: { columna: "unidades", etiqueta: "unidades" }, grupo: { columna: "categoria", etiqueta: "Por categoría" },
    convertir: (f, ctx) => {
      const categoria = f.categoria.trim().toUpperCase();
      if (!ctx.categorias.includes(categoria)) throw new FilaInvalida(`Categoría «${f.categoria}» no existe (${ctx.categorias.join(", ")})`);
      return { ...semana(f), categoria, unidades: entero(f.unidades, "unidades", 0, 100_000),
        farmacia_id: f.farmacia_id?.trim() ? entero(f.farmacia_id, "farmacia_id", 1) : null };
    },
  },
};
