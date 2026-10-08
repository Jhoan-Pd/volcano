import type { Nivel } from "../api/tipos";

export const fmtNum = (n: number | null | undefined, dec = 0) =>
  n == null ? "—" : n.toLocaleString("es-CO", { minimumFractionDigits: dec, maximumFractionDigits: dec });

export const fmtFecha = (iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) =>
  iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString("es-CO", opts) : "—";

export const fmtDia = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { weekday: "short", day: "numeric" });

export const NIVELES: Record<Nivel, { etiqueta: string; descripcion: string; color: string; tinta: string }> = {
  VERDE: { etiqueta: "Bajo", descripcion: "Dentro de lo esperado", color: "var(--st-verde)", tinta: "var(--st-verde-ink)" },
  AMARILLO: { etiqueta: "Moderado", descripcion: "Por encima de la mediana histórica", color: "var(--st-amarillo)", tinta: "var(--st-amarillo-ink)" },
  NARANJA: { etiqueta: "Alto", descripcion: "Zona de epidemia (> percentil 75)", color: "var(--st-naranja)", tinta: "var(--st-naranja-ink)" },
  ROJO: { etiqueta: "Muy alto", descripcion: "Brote probable (> percentil 90)", color: "var(--st-rojo)", tinta: "var(--st-rojo-ink)" },
};

export const NIVELES_VOLCAN: Record<string, { etiqueta: string; descripcion: string; nivel: Nivel }> = {
  VERDE: { etiqueta: "Alerta Verde", descripcion: "Volcán activo con comportamiento estable", nivel: "VERDE" },
  AMARILLO: { etiqueta: "Alerta Amarilla", descripcion: "Cambios en el comportamiento de la actividad volcánica", nivel: "AMARILLO" },
  NARANJA: { etiqueta: "Alerta Naranja", descripcion: "Erupción probable en días o semanas", nivel: "NARANJA" },
  ROJO: { etiqueta: "Alerta Roja", descripcion: "Erupción inminente o en curso", nivel: "ROJO" },
};

export const CATEGORIAS: Record<string, { etiqueta: string; ayuda: string }> = {
  ANTIGRIPALES: { etiqueta: "Antigripales", ayuda: "Gripa, congestión, tos" },
  ANTIPIRETICOS: { etiqueta: "Antipiréticos", ayuda: "Acetaminofén y similares para la fiebre" },
  SALES_REHIDRATACION: { etiqueta: "Sales de rehidratación", ayuda: "Sobres o soluciones de SRO" },
  INHALADORES: { etiqueta: "Inhaladores", ayuda: "Salbutamol, beclometasona…" },
  TAPABOCAS: { etiqueta: "Tapabocas", ayuda: "Quirúrgicos y N95 (unidades)" },
  REPELENTES: { etiqueta: "Repelentes", ayuda: "Repelentes de insectos" },
};
