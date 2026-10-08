import { api } from "./cliente";
import type {
  ClimaActual, ClimaDiario, Pagina, ResumenDashboard, RiesgoMunicipio, SerieEnfermedad, Usuario,
  Municipio, Enfermedad, Categoria, Farmacia, MiFarmacia, ReporteSemanal,
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
