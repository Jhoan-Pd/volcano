/**
 * Datos del tablero de un municipio, pedidos desde el SERVIDOR de Next.js (ISR).
 *
 * Se piden todas las enfermedades y el rango más largo de una vez: el tablero se genera como
 * página estática y el navegador solo filtra lo que ya tiene (cambiar de enfermedad o de rango
 * no hace peticiones). Las peticiones salen en paralelo con Promise.all.
 */
import type {
  ClimaActual, ClimaDiario, EstadoVolcan, ExplicacionPrediccion, Municipio, Pagina, PrediccionEnfermedad,
  ResumenDashboard, RiesgoMunicipio, SerieEnfermedad,
} from "@/api/tipos";
import { REVALIDAR_TABLEROS } from "./patrones";
import { ahoraIso, ErrorApi, pedir, pedirOpcional } from "./servidor";

export const SEMANAS_MAXIMAS = 260;

const isr = (...etiquetas: string[]) => ({ revalidar: REVALIDAR_TABLEROS, etiquetas: ["tableros", ...etiquetas] });

export async function municipiosActivos(): Promise<Municipio[]> {
  const pagina = await pedir<Pagina<Municipio>>("/municipios", { limit: 500 }, isr("municipios"));
  return pagina.items.filter((m) => m.activo);
}

export interface DatosTablero {
  municipio: Municipio;
  municipios: Municipio[];
  resumen: ResumenDashboard;
  series: Record<number, SerieEnfermedad>;
  predicciones: Record<number, PrediccionEnfermedad | null>;
  explicaciones: Record<number, ExplicacionPrediccion | null>;
  clima: ClimaActual | null;
  pronostico: ClimaDiario[];
  porMunicipio: RiesgoMunicipio[];
  generadoEn: string;
  peticiones: number;
}

export async function cargarTablero(municipioId: number): Promise<DatosTablero | null> {
  const etiqueta = `municipio-${municipioId}`;
  let resumen: ResumenDashboard;
  try {
    resumen = await pedir<ResumenDashboard>("/dashboard/resumen", { municipio_id: municipioId }, isr(etiqueta));
  } catch (e) {
    if (e instanceof ErrorApi && e.estado === 404) return null;
    throw e; // ISR: si la API falla al regenerar, Next.js sigue sirviendo la versión anterior
  }
  const ids = resumen.riesgos.map((r) => r.enfermedad_id);
  const params = (enfermedadId: number) => ({ municipio_id: municipioId, enfermedad_id: enfermedadId });
  const [municipios, porMunicipio, clima, pronostico, series, predicciones, explicaciones] = await Promise.all([
    municipiosActivos(),
    pedir<RiesgoMunicipio[]>("/dashboard/riesgo-municipios", {}, isr()),
    pedirOpcional<ClimaActual>(`/clima/${municipioId}/actual`, {}, isr(etiqueta)),
    pedirOpcional<ClimaDiario[]>(`/clima/${municipioId}/pronostico`, {}, isr(etiqueta)),
    Promise.all(ids.map((id) => pedir<SerieEnfermedad>("/dashboard/serie", { ...params(id), semanas: SEMANAS_MAXIMAS }, isr(etiqueta)))),
    Promise.all(ids.map((id) => pedirOpcional<PrediccionEnfermedad>("/dashboard/prediccion", params(id), isr(etiqueta)))),
    Promise.all(ids.map((id) => pedirOpcional<ExplicacionPrediccion>("/dashboard/explicacion", params(id), isr(etiqueta)))),
  ]);
  const municipio = municipios.find((m) => m.id === municipioId);
  if (!municipio) return null;
  const porId = <T,>(xs: T[]) => Object.fromEntries(ids.map((id, i) => [id, xs[i]]));
  return {
    municipio, municipios, resumen, porMunicipio, clima, pronostico: pronostico ?? [],
    series: porId(series), predicciones: porId(predicciones), explicaciones: porId(explicaciones),
    generadoEn: ahoraIso(), peticiones: 5 + ids.length * 3,
  };
}

export interface DatosInicio {
  municipios: Municipio[];
  porMunicipio: RiesgoMunicipio[];
  volcan: EstadoVolcan;
  generadoEn: string;
}

export async function cargarInicio(): Promise<DatosInicio> {
  const [municipios, porMunicipio, volcan] = await Promise.all([
    municipiosActivos(),
    pedir<RiesgoMunicipio[]>("/dashboard/riesgo-municipios", {}, isr()),
    pedir<EstadoVolcan>("/dashboard/volcan", {}, isr()),
  ]);
  return { municipios, porMunicipio, volcan, generadoEn: ahoraIso() };
}
