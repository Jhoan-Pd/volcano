import { api } from "./cliente";
import type {
  ClimaActual, ClimaDiario, Pagina, ResumenDashboard, RiesgoMunicipio, SerieEnfermedad, Usuario,
  Municipio, Enfermedad, Categoria, Farmacia, MiFarmacia, ReporteSemanal,
  PrediccionEnfermedad, ExplicacionPrediccion, ModeloEntrenado, EstadoEntrenamiento,
  ResultadoTendencias, ResultadoSivigila, ResultadoImportacion, TipoImportacion, EstadoFuente,
  Alerta, ResultadoEvaluacion,
} from "./tipos";

export const authApi = {
  async login(email: string, password: string) {
    const form = new URLSearchParams({ username: email, password });
    const { data } = await api.post<{ access_token: string; usuario: Usuario }>("/auth/login", form);
    return data;
  },
  async me() {
    return (await api.get<Usuario>("/auth/me")).data;
  },
  async registro(datos: { nombre: string; email: string; password: string; municipio_id?: number | null }) {
    return (await api.post<Usuario>("/auth/registro", datos)).data;
  },
};

export const dashboardApi = {
  resumen: async (municipioId?: number) =>
    (await api.get<ResumenDashboard>("/dashboard/resumen", { params: { municipio_id: municipioId } })).data,
  serie: async (municipioId: number, enfermedadId: number, semanas = 104) =>
    (await api.get<SerieEnfermedad>("/dashboard/serie", {
      params: { municipio_id: municipioId, enfermedad_id: enfermedadId, semanas },
    })).data,
  riesgoMunicipios: async () => (await api.get<RiesgoMunicipio[]>("/dashboard/riesgo-municipios")).data,
  prediccion: async (municipioId: number, enfermedadId: number) =>
    (await api.get<PrediccionEnfermedad>("/dashboard/prediccion", {
      params: { municipio_id: municipioId, enfermedad_id: enfermedadId },
    })).data,
  explicacion: async (municipioId: number, enfermedadId: number, horizonte?: number) =>
    (await api.get<ExplicacionPrediccion>("/dashboard/explicacion", {
      params: { municipio_id: municipioId, enfermedad_id: enfermedadId, horizonte },
    })).data,
};

/** Modelo predictivo (Fase 2): reentrenar y estado solo ADMIN; historial público. */
export const modeloApi = {
  reentrenar: async (enfermedadId?: number) =>
    (await api.post<EstadoEntrenamiento>("/modelo/reentrenar", null, { params: { enfermedad_id: enfermedadId } })).data,
  estado: async () => (await api.get<EstadoEntrenamiento>("/modelo/estado")).data,
  predecir: async () => (await api.post<{ predicciones: number }>("/modelo/predecir")).data,
  historial: async (enfermedadId?: number, limite = 50) =>
    (await api.get<ModeloEntrenado[]>("/modelo/historial", { params: { enfermedad_id: enfermedadId, limite } })).data,
};

export const climaApi = {
  actual: async (municipioId: number) => (await api.get<ClimaActual>(`/clima/${municipioId}/actual`)).data,
  pronostico: async (municipioId: number) =>
    (await api.get<ClimaDiario[]>(`/clima/${municipioId}/pronostico`)).data,
  sincronizar: async () =>
    (await api.post<{ municipios: number; registros_guardados: number; errores: string[] }>("/clima/sincronizar")).data,
};

export const catalogoApi = {
  municipios: async () => (await api.get<Pagina<Municipio>>("/municipios", { params: { limit: 500 } })).data.items,
  enfermedades: async () => (await api.get<Pagina<Enfermedad>>("/enfermedades", { params: { limit: 500 } })).data.items,
};

/** CRUD genérico para el panel de administración */
export const crudApi = {
  listar: async <T,>(recurso: string, offset = 0, limit = 20) =>
    (await api.get<Pagina<T>>(`/${recurso}`, { params: { offset, limit } })).data,
  crear: async <T,>(recurso: string, datos: unknown) => (await api.post<T>(`/${recurso}`, datos)).data,
  actualizar: async <T,>(recurso: string, id: number, datos: unknown) =>
    (await api.patch<T>(`/${recurso}/${id}`, datos)).data,
  eliminar: async (recurso: string, id: number) => {
    await api.delete(`/${recurso}/${id}`);
  },
};

/** Panel de farmacia (Fase 2). `farmaciaId` solo lo usa el ADMIN. */
export const farmaciaApi = {
  miFarmacia: async (farmaciaId?: number) =>
    (await api.get<MiFarmacia>("/farmacia/mi-farmacia", { params: { farmacia_id: farmaciaId } })).data,
  historial: async (farmaciaId?: number, semanas = 26) =>
    (await api.get<ReporteSemanal[]>("/farmacia/reportes", { params: { farmacia_id: farmaciaId, semanas } })).data,
  crear: async (datos: { anio: number; semana_epi: number; items: { categoria: Categoria; unidades: number }[] }, farmaciaId?: number) =>
    (await api.post<ReporteSemanal>("/farmacia/reportes", { ...datos, farmacia_id: farmaciaId })).data,
  actualizar: async (anio: number, semana: number, items: { categoria: Categoria; unidades: number }[], farmaciaId?: number) =>
    (await api.put<ReporteSemanal>(`/farmacia/reportes/${anio}/${semana}`, { items }, { params: { farmacia_id: farmaciaId } })).data,
  eliminar: async (anio: number, semana: number, farmaciaId?: number) => {
    await api.delete(`/farmacia/reportes/${anio}/${semana}`, { params: { farmacia_id: farmaciaId } });
  },
  farmacias: async () => (await api.get<Pagina<Farmacia>>("/farmacias", { params: { limit: 500 } })).data.items,
};

/** Fuentes de datos (Fase 2): sincronización e importación, solo ADMIN. */
export const datosApi = {
  estado: async () => (await api.get<{ fuentes: EstadoFuente[] }>("/datos/estado")).data.fuentes,
  sincronizarTendencias: async (forzar = false) =>
    (await api.post<ResultadoTendencias>("/datos/sincronizar/tendencias", null, { params: { forzar }, timeout: 180_000 })).data,
  sincronizarSivigila: async (desdeAnio = 2020) =>
    (await api.post<ResultadoSivigila>("/datos/sincronizar/sivigila", null, {
      params: { desde_anio: desdeAnio }, timeout: 180_000, // datos.gov.co pagina miles de registros
    })).data,
  importar: async (tipo: TipoImportacion, archivo: File) => {
    const form = new FormData();
    form.append("archivo", archivo);
    return (await api.post<ResultadoImportacion>(`/datos/importar/${tipo}`, form)).data;
  },
};

/** Alertas tempranas (Fase 3): activas públicas; gestión solo ADMIN. */
export const alertaApi = {
  activas: async () => (await api.get<Alerta[]>("/alertas/activas")).data,
  listar: async (activa?: boolean, offset = 0, limit = 20) =>
    (await api.get<Pagina<Alerta>>("/alertas", { params: { activa, offset, limit } })).data,
  evaluar: async (enviarCorreo = true) =>
    (await api.post<ResultadoEvaluacion>("/alertas/evaluar", null, { params: { enviar_correo: enviarCorreo } })).data,
  cerrar: async (id: number) => (await api.patch<Alerta>(`/alertas/${id}/cerrar`)).data,
};
