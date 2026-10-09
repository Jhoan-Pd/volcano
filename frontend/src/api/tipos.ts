// Tipos que reflejan los esquemas Pydantic del backend

export type Rol = "ADMIN" | "FARMACIA" | "CIUDADANO";
export type Nivel = "VERDE" | "AMARILLO" | "NARANJA" | "ROJO";

export interface Usuario {
  id: number;
  nombre: string;
  email: string;
  rol: Rol;
  municipio_id: number | null;
  activo: boolean;
  creado_en: string;
}

export interface Pagina<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface Municipio {
  id: number;
  codigo_divipola: string;
  nombre: string;
  departamento: string;
  latitud: number;
  longitud: number;
  altitud_m: number | null;
  poblacion: number;
  distancia_crater_km: number | null;
  activo: boolean;
}

export interface Enfermedad {
  id: number;
  codigo: string;
  nombre: string;
  descripcion: string | null;
  codigo_cie10: string | null;
  recomendaciones: string | null;
  terminos_busqueda: string | null;
  color: string;
  umbral_amarillo_pct: number;
  umbral_naranja_pct: number;
  umbral_rojo_pct: number;
  activo: boolean;
}

export interface RiesgoEnfermedad {
  enfermedad_id: number;
  codigo: string;
  nombre: string;
  color: string;
  anio: number;
  semana_epi: number;
  casos: number;
  casos_semana_anterior: number | null;
  variacion_pct: number | null;
  tasa_x_100k: number;
  umbrales: { amarillo: number; naranja: number; rojo: number };
  nivel: Nivel;
  es_simulado: boolean;
  recomendaciones: string[];
  prediccion: ResumenPrediccion | null;
}

export interface EventoCeniza {
  fecha: string;
  municipio: string | null;
  intensidad: number;
  descripcion: string | null;
  es_simulado: boolean;
}

export interface EstadoVolcan {
  nivel_actividad: string;
  fecha: string | null;
  descripcion: string | null;
  url_boletin: string | null;
  es_simulado: boolean;
  so2_ton_dia: number | null;
  ceniza_reciente: EventoCeniza[];
}

export interface ResumenDashboard {
  municipio_id: number;
  municipio: string;
  poblacion: number;
  semana_referencia: string;
  riesgos: RiesgoEnfermedad[];
  volcan: EstadoVolcan;
  hay_datos_simulados: boolean;
}

export interface PuntoSerie {
  anio: number;
  semana_epi: number;
  etiqueta: string;
  fecha_inicio: string;
  casos: number | null;
  p_amarillo: number | null;
  p_naranja: number | null;
  p_rojo: number | null;
}

export interface SerieEnfermedad {
  municipio_id: number;
  enfermedad_id: number;
  enfermedad: string;
  puntos: PuntoSerie[];
}

export interface RiesgoMunicipio {
  municipio_id: number;
  municipio: string;
  codigo_divipola: string;
  latitud: number;
  longitud: number;
  nivel_max: Nivel;
  detalle: Record<string, Nivel>;
  nivel_max_predicho: Nivel | null;
  detalle_predicho: Record<string, Nivel>;
}

export interface ClimaActual {
  municipio_id: number;
  municipio: string;
  hora: string | null;
  temperatura_c: number | null;
  humedad_relativa_pct: number | null;
  precipitacion_mm: number | null;
  viento_kmh: number | null;
  codigo_tiempo: number | null;
  descripcion: string;
  fuente: string;
}

export interface ClimaDiario {
  fecha: string;
  temp_max_c: number | null;
  temp_min_c: number | null;
  temp_media_c: number | null;
  precipitacion_mm: number | null;
  humedad_relativa_pct: number | null;
  es_pronostico: boolean;
  es_simulado: boolean;
  fuente: string;
}

export interface Farmacia {
  id: number;
  nombre: string;
  nit: string;
  direccion: string | null;
  telefono: string | null;
  municipio_id: number;
  usuario_id: number | null;
  latitud: number | null;
  longitud: number | null;
  activa: boolean;
}

export interface EventoVolcanico {
  id: number;
  tipo: "BOLETIN" | "CAIDA_CENIZA" | "EMISION_GASES" | "SISMO";
  nivel_actividad: Nivel;
  fecha_inicio: string;
  fecha_fin: string | null;
  municipio_id: number | null;
  intensidad_ceniza: number;
  so2_ton_dia: number | null;
  descripcion: string | null;
  url_boletin: string | null;
  es_simulado: boolean;
  creado_en: string;
}

// ── Fase 2: farmacias ─────────────────────────────────────────────────────────
export type Categoria =
  | "ANTIGRIPALES" | "ANTIPIRETICOS" | "SALES_REHIDRATACION" | "INHALADORES" | "TAPABOCAS" | "REPELENTES";

export interface SemanaReportable {
  anio: number;
  semana_epi: number;
  etiqueta: string;
  fecha_inicio: string;
  fecha_fin: string;
  reportada: boolean;
}

export interface MiFarmacia {
  id: number;
  nombre: string;
  nit: string;
  direccion: string | null;
  municipio_id: number;
  municipio: string;
  activa: boolean;
  semanas_reportables: SemanaReportable[];
  categorias: Categoria[];
}

export interface ReporteSemanal {
  farmacia_id: number;
  farmacia: string;
  anio: number;
  semana_epi: number;
  etiqueta: string;
  fecha_inicio: string;
  fecha_fin: string;
  items: { categoria: Categoria; unidades: number }[];
  total_unidades: number;
  es_simulado: boolean;
  actualizado_en: string | null;
  reportado_por: string | null;
  editable: boolean;
}

// ── Fase 2: modelo predictivo ─────────────────────────────────────────────────
export interface Umbrales { amarillo: number; naranja: number; rojo: number }

/** Lo que dice el modelo para las próximas 4 semanas (semáforo predictivo). */
export interface ResumenPrediccion {
  nivel_max: Nivel;
  semana_pico: string;
  casos_esperados_h1: number;
  limite_inferior_h1: number;
  limite_superior_h1: number;
  algoritmo: string;
}

export interface PuntoPrediccion {
  anio: number;
  semana_epi: number;
  etiqueta: string;
  fecha_inicio: string;
  horizonte: number;
  casos_esperados: number;
  limite_inferior: number;
  limite_superior: number;
  nivel: Nivel;
  umbrales: Umbrales | null;
}

export interface PuntoBacktest {
  anio: number;
  semana_epi: number;
  etiqueta: string;
  real: number;
  predicho: number;
}

export interface ModeloResumen {
  id: number;
  algoritmo: string;
  fecha_entrenamiento: string;
  mae_base: number | null;
  mae_modelo: number | null;
  rmse_base: number | null;
  rmse_modelo: number | null;
}

export interface PrediccionEnfermedad {
  municipio_id: number;
  enfermedad_id: number;
  enfermedad: string;
  semana_base: string | null;
  modelo: ModeloResumen | null;
  nivel_max: Nivel | null;
  puntos: PuntoPrediccion[];
  backtest: PuntoBacktest[];
}

export interface ImportanciasModelo {
  metodo: string;
  grupos: Record<string, number>;
  variables: Record<string, { importancia: number; grupo: string }>;
}

export interface MetricasModelo {
  resumen: Record<string, { mae: number; rmse: number }>;
  por_horizonte: Record<string, Record<string, { mae: number; rmse: number }>>;
  semanas_prueba: number;
}

export interface ModeloEntrenado {
  id: number;
  enfermedad_id: number;
  enfermedad: string;
  algoritmo: string;
  version: string;
  fecha_entrenamiento: string;
  mae_base: number | null;
  rmse_base: number | null;
  mae_modelo: number | null;
  rmse_modelo: number | null;
  mejora_mae_pct: number | null;
  n_muestras: number | null;
  activo: boolean;
  importancias: ImportanciasModelo | null;
  metricas: MetricasModelo | null;
}

export interface EstadoEntrenamiento {
  en_curso: boolean;
  inicio: string | null;
  fin: string | null;
  mensaje: string | null;
  errores: string[];
}

export interface FactorExplicacion {
  grupo: string;
  contribucion: number;
  direccion: "sube" | "baja" | "neutral";
  mensaje: string | null;
}

export interface ExplicacionPrediccion {
  municipio_id: number;
  municipio: string;
  enfermedad_id: number;
  enfermedad: string;
  etiqueta: string;
  horizonte: number;
  nivel: Nivel;
  casos_esperados: number;
  metodo: string;
  resumen: string;
  factores: FactorExplicacion[];
  importancia_global: ImportanciasModelo | null;
}

// ── Fase 2: fuentes de datos ──────────────────────────────────────────────────
export interface ResultadoTendencias {
  fuente: string;
  terminos: string[];
  registros_guardados: number;
  desde_cache: string[];
  errores: string[];
}

export interface ResultadoSivigila {
  enfermedades: string[];
  anios_cubiertos: number[];
  registros_guardados: number;
  semanas_con_casos: number;
  errores: string[];
}

export type TipoImportacion = "casos" | "clima" | "eventos" | "tendencias";

export interface ResultadoImportacion {
  tipo: TipoImportacion;
  filas_leidas: number;
  insertadas: number;
  actualizadas: number;
  errores: { fila: number; mensaje: string }[];
}

export interface EstadoFuente {
  fuente: string;
  tabla: string;
  registros: number;
  simulados: number;
  ultima_semana: string | null;
  ultima_actualizacion: string | null;
}
