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
