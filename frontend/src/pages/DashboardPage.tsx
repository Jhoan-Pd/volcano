import { Activity, CloudSun, Info, MapPin } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { mensajeError } from "../api/cliente";
import { catalogoApi, climaApi, dashboardApi } from "../api/servicios";
import type {
  ClimaActual, ClimaDiario, Municipio, PrediccionEnfermedad, ResumenDashboard, RiesgoMunicipio, SerieEnfermedad,
} from "../api/tipos";
import CanalEndemicoChart from "../components/dashboard/CanalEndemicoChart";
import { ClimaActualCard, Recomendaciones, RiesgoMunicipiosTabla, VolcanCard } from "../components/dashboard/Paneles";
import PronosticoClima from "../components/dashboard/PronosticoClima";
import SemaforoCard from "../components/dashboard/SemaforoCard";
import { Aviso, Card, CardHeader, claseInput, SimuladoBadge, Spinner } from "../components/ui";
import { fmtFecha, fmtNum } from "../lib/formato";

const RANGOS = [
  { semanas: 26, etiqueta: "6 meses" },
  { semanas: 52, etiqueta: "1 año" },
  { semanas: 104, etiqueta: "2 años" },
  { semanas: 260, etiqueta: "5 años" },
];

export default function DashboardPage() {
  const [municipios, setMunicipios] = useState<Municipio[]>([]);
  const [municipioId, setMunicipioId] = useState<number | null>(null);
  const [resumen, setResumen] = useState<ResumenDashboard | null>(null);
  const [enfermedadId, setEnfermedadId] = useState<number | null>(null);
  const [semanas, setSemanas] = useState(52);
  const [serie, setSerie] = useState<SerieEnfermedad | null>(null);
  const [prediccion, setPrediccion] = useState<PrediccionEnfermedad | null>(null);
  const [verValidacion, setVerValidacion] = useState(false);
  const [climaActual, setClimaActual] = useState<ClimaActual | null>(null);
  const [pronostico, setPronostico] = useState<ClimaDiario[] | null>(null);
  const [porMunicipio, setPorMunicipio] = useState<RiesgoMunicipio[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Carga inicial: municipios y tabla general de riesgo
  useEffect(() => {
    catalogoApi.municipios()
      .then((ms) => {
        const activos = ms.filter((m) => m.activo);
        setMunicipios(activos);
        setMunicipioId((id) => id ?? activos[0]?.id ?? null);
      })
      .catch((e) => setError(mensajeError(e)));
    dashboardApi.riesgoMunicipios().then(setPorMunicipio).catch(() => undefined);
  }, []);

  // Al cambiar de municipio: semáforo + clima
  useEffect(() => {
    if (municipioId == null) return;
    setResumen(null); setClimaActual(null); setPronostico(null);
    dashboardApi.resumen(municipioId)
      .then((r) => {
        setResumen(r);
        setEnfermedadId((id) => (id && r.riesgos.some((x) => x.enfermedad_id === id) ? id : r.riesgos[0]?.enfermedad_id ?? null));
      })
      .catch((e) => setError(mensajeError(e)));
    climaApi.actual(municipioId).then(setClimaActual).catch(() => undefined);
    climaApi.pronostico(municipioId).then(setPronostico).catch(() => setPronostico([]));
  }, [municipioId]);

  useEffect(() => {
    if (municipioId == null || enfermedadId == null) return;
    setSerie(null);
    dashboardApi.serie(municipioId, enfermedadId, semanas).then(setSerie).catch((e) => setError(mensajeError(e)));
  }, [municipioId, enfermedadId, semanas]);

  useEffect(() => {
    if (municipioId == null || enfermedadId == null) return;
    setPrediccion(null);
    dashboardApi.prediccion(municipioId, enfermedadId).then(setPrediccion).catch(() => setPrediccion(null));
  }, [municipioId, enfermedadId]);

  const seleccionada = useMemo(() => resumen?.riesgos.find((r) => r.enfermedad_id === enfermedadId), [resumen, enfermedadId]);
  const municipio = municipios.find((m) => m.id === municipioId);

  if (error && !resumen) {
    return (
      <Aviso tipo="error">
        <p className="font-medium">No se pudo cargar el dashboard</p>
        <p className="mt-1">{error}</p>
        <p className="mt-2 text-xs opacity-80">Si el backend está en Render (plan gratuito), puede tardar ~1 minuto en despertar. Recarga la página.</p>
      </Aviso>
    );
  }

  return (
    <div className="space-y-6">
      {/* Encabezado y filtro */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-accent">Vigilancia epidemiológica temprana</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
            Riesgo de brotes en {resumen?.municipio ?? municipio?.nombre ?? "…"}
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-2">
            {resumen ? <>Semana epidemiológica <b className="tabular">{resumen.semana_referencia.replace("-S", " · S")}</b></> : "Cargando…"}
            {municipio && <span className="text-muted">· {fmtNum(municipio.poblacion)} hab. · {fmtNum(municipio.altitud_m)} m s. n. m.</span>}
            {resumen?.hay_datos_simulados && <SimuladoBadge />}
          </p>
        </div>
        <label className="w-full md:w-64">
          <span className="mb-1 flex items-center gap-1 text-xs font-medium text-ink-2"><MapPin size={13} /> Municipio</span>
          <select className={claseInput} value={municipioId ?? ""} onChange={(e) => setMunicipioId(Number(e.target.value))}>
            {municipios.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
          </select>
        </label>
      </div>

      {/* Semáforo */}
      {!resumen ? <Spinner texto="Calculando riesgo…" /> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {resumen.riesgos.map((r) => (
            <SemaforoCard key={r.codigo} r={r} activo={r.enfermedad_id === enfermedadId} onClick={() => setEnfermedadId(r.enfermedad_id)} />
          ))}
        </div>
      )}

      {/* Histórico + volcán/clima */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="min-w-0 lg:col-span-2">
          <CardHeader titulo={`Histórico vs. predicción · ${seleccionada?.nombre ?? ""}`} icono={<Activity size={17} />}
            subtitulo="Casos semanales sobre el canal endémico (percentiles de los 5 años anteriores) y casos esperados de las próximas 4 semanas."
            accion={
              <div className="flex flex-wrap items-center gap-2">
                {prediccion && prediccion.backtest.length > 0 && (
                  <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-ink-2">
                    <input type="checkbox" className="accent-[var(--accent)]" checked={verValidacion}
                      onChange={(e) => setVerValidacion(e.target.checked)} />
                    Validación
                  </label>
                )}
                <div className="flex rounded-lg border border-line p-0.5 text-xs" role="group" aria-label="Rango de tiempo">
                  {RANGOS.map((r) => (
                    <button key={r.semanas} onClick={() => setSemanas(r.semanas)} aria-pressed={semanas === r.semanas}
                      className={`rounded-md px-2.5 py-1 font-medium ${semanas === r.semanas ? "bg-surface-2 text-ink" : "text-muted hover:text-ink"}`}>
                      {r.etiqueta}
                    </button>
                  ))}
                </div>
              </div>
            } />
          <div className="px-3 pb-4 sm:px-5">
            {serie && seleccionada
              ? <CanalEndemicoChart puntos={serie.puntos} color={seleccionada.color} prediccion={prediccion} mostrarValidacion={verValidacion} />
              : <Spinner />}
            <ResumenModelo prediccion={prediccion} />
          </div>
        </Card>
        <div className="min-w-0 space-y-6">
          {resumen && <VolcanCard v={resumen.volcan} />}
          <ClimaActualCard c={climaActual} municipio={municipio?.nombre ?? ""} />
        </div>
      </div>

      {/* Pronóstico */}
      <Card>
        <CardHeader titulo="Pronóstico del clima · próximos 16 días" icono={<CloudSun size={17} />}
          subtitulo={pronostico?.some((d) => d.es_simulado) ? "Clima simulado (Open-Meteo no estaba disponible al cargar la semilla)" : "Fuente: Open-Meteo"} />
        <div className="px-3 pb-5 sm:px-5">
          {pronostico == null ? <Spinner /> : pronostico.length === 0
            ? <p className="py-6 text-center text-sm text-muted">Sin pronóstico disponible. Un administrador puede sincronizar el clima.</p>
            : <PronosticoClima dias={pronostico} />}
        </div>
      </Card>

      {/* Municipios + recomendaciones */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader titulo="Riesgo por municipio" icono={<MapPin size={17} />}
            subtitulo="Haz clic en un municipio para ver su detalle. El mapa llega en la Fase 3." />
          {porMunicipio.length === 0 ? <Spinner /> : (
            <RiesgoMunicipiosTabla filas={porMunicipio} seleccionado={municipioId}
              enfermedades={resumen?.riesgos.map((r) => ({ codigo: r.codigo, nombre: r.nombre })) ?? []}
              onSeleccionar={(id) => { setMunicipioId(id); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
          )}
        </Card>
        <Card className="min-w-0">
          <CardHeader titulo="Recomendaciones de prevención" subtitulo="Ordenadas según el nivel de riesgo actual" />
          {resumen ? <Recomendaciones riesgos={resumen.riesgos} /> : <Spinner />}
        </Card>
      </div>
    </div>
  );
}

/** Línea de métricas del modelo: así el ciudadano ve qué tan confiable es la predicción. */
function ResumenModelo({ prediccion }: { prediccion: PrediccionEnfermedad | null }) {
  const m = prediccion?.modelo;
  if (!m) {
    return (
      <p className="mt-3 flex items-start gap-1.5 text-xs text-muted">
        <Info size={13} className="mt-0.5 shrink-0" />
        Aún no hay un modelo entrenado para esta enfermedad. Un administrador puede entrenarlo desde el panel.
      </p>
    );
  }
  const mejora = m.mae_base && m.mae_modelo != null ? (1 - m.mae_modelo / m.mae_base) * 100 : null;
  return (
    <p className="mt-3 flex items-start gap-1.5 text-xs text-muted">
      <Info size={13} className="mt-0.5 shrink-0" />
      <span>
        Modelo <b className="font-medium text-ink-2">{m.algoritmo}</b> entrenado el {fmtFecha(m.fecha_entrenamiento)}.
        Error medio (MAE) <span className="tabular">{fmtNum(m.mae_modelo, 2)}</span> casos/semana frente a{" "}
        <span className="tabular">{fmtNum(m.mae_base, 2)}</span> del promedio móvil
        {mejora != null && <> ({mejora >= 0 ? "−" : "+"}{fmtNum(Math.abs(mejora), 0)} %)</>}.
        El intervalo cubre el 80 % de los errores observados en validación.
      </span>
    </p>
  );
}
