import { Activity, CloudSun, Info, Map as IconoMapa, MapPin } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { catalogoApi, climaApi, dashboardApi } from "../api/servicios";
import type { PrediccionEnfermedad } from "../api/tipos";
import CanalEndemicoChart from "../components/dashboard/CanalEndemicoChart";
import type { ModoMapa } from "../components/dashboard/MapaRiesgo";
import MenuReportes from "../components/dashboard/MenuReportes";
import PanelExplicacion from "../components/dashboard/PanelExplicacion";
import Revelar from "../components/Revelar";
import TituloRevelado from "../components/TituloRevelado";
import { ClimaActualCard, Recomendaciones, RiesgoMunicipiosTabla, VolcanCard } from "../components/dashboard/Paneles";
import PronosticoClima from "../components/dashboard/PronosticoClima";
import SemaforoCard from "../components/dashboard/SemaforoCard";
import { Aviso, Card, CardHeader, claseInput, Segmentado, SimuladoBadge, Spinner } from "../components/ui";
import { fmtFecha, fmtNum } from "../lib/formato";
import { useDatos } from "../lib/useDatos";

// Leaflet pesa ~150 kB: el mapa se descarga aparte, después del resto del dashboard
const MapaRiesgo = lazy(() => import("../components/dashboard/MapaRiesgo"));

const RANGOS = [
  { valor: 26, etiqueta: "6 meses" },
  { valor: 52, etiqueta: "1 año" },
  { valor: 104, etiqueta: "2 años" },
  { valor: 260, etiqueta: "5 años" },
] as const;

const MODOS_MAPA = [
  { valor: "actual", etiqueta: "Semana actual" },
  { valor: "predicho", etiqueta: "Próximas 4 semanas" },
] as const satisfies readonly { valor: ModoMapa; etiqueta: string }[];

export default function DashboardPage() {
  const [municipioId, setMunicipioId] = useState<number | null>(null);
  const [enfermedadId, setEnfermedadId] = useState<number | null>(null);
  const [semanas, setSemanas] = useState<number>(52);
  const [verValidacion, setVerValidacion] = useState(false);
  const [modoMapa, setModoMapa] = useState<ModoMapa>("actual");
  const [codigoMapa, setCodigoMapa] = useState("");

  // Cada fuente de datos declara de qué depende; useDatos descarta respuestas viejas
  const municipiosQ = useDatos(() => catalogoApi.municipios().then((ms) => ms.filter((m) => m.activo)), []);
  const porMunicipioQ = useDatos(() => dashboardApi.riesgoMunicipios(), []);
  const resumenQ = useDatos(municipioId == null ? null : () => dashboardApi.resumen(municipioId), [municipioId]);
  const climaQ = useDatos(municipioId == null ? null : () => climaApi.actual(municipioId), [municipioId]);
  const pronosticoQ = useDatos(municipioId == null ? null : () => climaApi.pronostico(municipioId), [municipioId]);
  const hayEleccion = municipioId != null && enfermedadId != null;
  const serieQ = useDatos(hayEleccion ? () => dashboardApi.serie(municipioId, enfermedadId, semanas) : null,
    [municipioId, enfermedadId, semanas]);
  const prediccionQ = useDatos(hayEleccion ? () => dashboardApi.prediccion(municipioId, enfermedadId) : null,
    [municipioId, enfermedadId]);

  const municipios = useMemo(() => municipiosQ.datos ?? [], [municipiosQ.datos]);
  const resumen = resumenQ.datos;
  const serie = serieQ.datos;
  const prediccion = prediccionQ.datos;
  const climaActual = climaQ.datos;
  const pronostico = pronosticoQ.error ? [] : pronosticoQ.datos;
  const porMunicipio = porMunicipioQ.datos ?? [];
  const error = municipiosQ.error ?? resumenQ.error ?? serieQ.error;

  // Primer municipio por defecto
  useEffect(() => {
    if (municipioId == null && municipios.length > 0) setMunicipioId(municipios[0].id);
  }, [municipios, municipioId]);

  // Al cambiar de municipio se conserva la enfermedad elegida si existe allí
  useEffect(() => {
    if (!resumen) return;
    setEnfermedadId((id) => (id && resumen.riesgos.some((x) => x.enfermedad_id === id) ? id : resumen.riesgos[0]?.enfermedad_id ?? null));
  }, [resumen]);

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
          <p className="titulo-seccion text-[13px] text-muted">Vigilancia epidemiológica temprana</p>
          <TituloRevelado className="titulo-display mt-2 text-[2.6rem] sm:text-6xl lg:text-7xl"
            texto={`Riesgo de brotes en ${resumen?.municipio ?? municipio?.nombre ?? "…"}`} />
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-2">
            {resumen ? <>Semana epidemiológica <b className="tabular">{resumen.semana_referencia.replace("-S", " · S")}</b></> : "Cargando…"}
            {municipio && <span className="text-muted">· {fmtNum(municipio.poblacion)} hab. · {fmtNum(municipio.altitud_m)} m s. n. m.</span>}
            {resumen?.hay_datos_simulados && <SimuladoBadge />}
          </p>
        </div>
        <div className="flex w-full items-end gap-2 md:w-auto">
          <label className="min-w-0 flex-1 md:w-64 md:flex-none">
            <span className="mb-1 flex items-center gap-1 text-xs font-medium text-ink-2"><MapPin size={13} /> Municipio</span>
            <select className={claseInput} value={municipioId ?? ""} onChange={(e) => setMunicipioId(Number(e.target.value))}>
              {municipios.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
          </label>
          {municipioId != null && <MenuReportes municipioId={municipioId} municipio={municipio?.nombre ?? ""} enfermedadId={enfermedadId} />}
        </div>
      </div>

      {/* Semáforo */}
      {!resumen ? <Spinner texto="Calculando riesgo…" /> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {resumen.riesgos.map((r, i) => (
            <Revelar key={r.codigo} retraso={i * 80} className="flex">
              <SemaforoCard r={r} activo={r.enfermedad_id === enfermedadId} onClick={() => setEnfermedadId(r.enfermedad_id)} />
            </Revelar>
          ))}
        </div>
      )}

      <Revelar>
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
                <Segmentado etiqueta="Rango de tiempo" opciones={RANGOS} valor={semanas} onCambiar={setSemanas} />
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

      </Revelar>

      <Revelar>
      {/* Explicabilidad + recomendaciones */}
      <div className="grid gap-6 lg:grid-cols-2">
        {municipioId != null && enfermedadId != null
          ? <PanelExplicacion municipioId={municipioId} enfermedadId={enfermedadId} />
          : <Card><Spinner /></Card>}
        <Card className="min-w-0">
          <CardHeader titulo="Recomendaciones de prevención" subtitulo="Ordenadas según el nivel de riesgo actual" />
          {resumen ? <Recomendaciones riesgos={resumen.riesgos} /> : <Spinner />}
        </Card>
      </div>

      </Revelar>

      <Revelar>
      {/* Mapa + tabla por municipio */}
      <Card className="min-w-0">
        <CardHeader titulo="Mapa de riesgo · zona de influencia del Galeras" icono={<IconoMapa size={17} />}
          subtitulo="Haz clic en un municipio para ver su detalle arriba."
          accion={
            <div className="flex flex-wrap items-center gap-2">
              <select className="rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink focus:border-accent focus:outline-none" value={codigoMapa} onChange={(e) => setCodigoMapa(e.target.value)}
                aria-label="Enfermedad del mapa">
                <option value="">Todas (la de mayor riesgo)</option>
                {resumen?.riesgos.map((r) => <option key={r.codigo} value={r.codigo}>{r.nombre}</option>)}
              </select>
              <Segmentado etiqueta="Periodo del mapa" opciones={MODOS_MAPA} valor={modoMapa} onCambiar={setModoMapa} />
            </div>
          } />
        {porMunicipio.length === 0 ? <Spinner /> : (
          <div className="grid grid-cols-1 gap-4 px-5 pb-5 lg:grid-cols-5">
            <div className="min-w-0 lg:col-span-3">
              <Suspense fallback={<Spinner texto="Cargando mapa…" />}>
                <MapaRiesgo filas={porMunicipio} modo={modoMapa} codigo={codigoMapa} seleccionado={municipioId}
                  enfermedades={resumen?.riesgos.map((r) => ({ codigo: r.codigo, nombre: r.nombre })) ?? []}
                  onSeleccionar={(id) => { setMunicipioId(id); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
              </Suspense>
            </div>
            <div className="-mx-5 min-w-0 lg:col-span-2 lg:mx-0">
              <RiesgoMunicipiosTabla filas={porMunicipio} seleccionado={municipioId} predicho={modoMapa === "predicho"}
                enfermedades={resumen?.riesgos.map((r) => ({ codigo: r.codigo, nombre: r.nombre })) ?? []}
                onSeleccionar={(id) => { setMunicipioId(id); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
            </div>
          </div>
        )}
      </Card>

      </Revelar>

      <Revelar>
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
      </Revelar>
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
