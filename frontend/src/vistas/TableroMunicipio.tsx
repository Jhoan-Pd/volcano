"use client";

import { Activity, CloudSun, Info, Map as IconoMapa, MapPin } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { PrediccionEnfermedad } from "../api/tipos";
import CanalEndemicoChart from "../components/dashboard/CanalEndemicoChart";
import MapaRiesgo from "../components/dashboard/MapaDinamico";
import MenuReportes from "../components/dashboard/MenuReportes";
import type { ModoMapa } from "../components/dashboard/modoMapa";
import PanelExplicacion from "../components/dashboard/PanelExplicacion";
import { ClimaActualCard, Recomendaciones, RiesgoMunicipiosTabla, VolcanCard } from "../components/dashboard/Paneles";
import PronosticoClima from "../components/dashboard/PronosticoClima";
import SemaforoCard from "../components/dashboard/SemaforoCard";
import Revelar from "../components/Revelar";
import TituloRevelado from "../components/TituloRevelado";
import { Card, CardHeader, claseInput, Segmentado, SimuladoBadge } from "../components/ui";
import { fmtFecha, fmtNum } from "../lib/formato";
import type { DatosTablero } from "../lib/tablero";

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

/**
 * Tablero de un municipio. Los datos llegan como props desde la página ISR (ya vienen en el
 * HTML); este componente de cliente solo agrega la interacción: elegir enfermedad, rango de
 * tiempo o modo del mapa no hace peticiones, y cambiar de municipio navega a OTRA página
 * estática (/municipio/[id]) que Next.js precarga.
 */
export default function TableroMunicipio({ datos }: { datos: DatosTablero }) {
  const { municipio, municipios, resumen, series, predicciones, explicaciones, clima, pronostico, porMunicipio } = datos;
  const router = useRouter();
  const [enfermedadId, setEnfermedadId] = useState<number | null>(resumen.riesgos[0]?.enfermedad_id ?? null);
  const [semanas, setSemanas] = useState<number>(52);
  const [verValidacion, setVerValidacion] = useState(false);
  const [modoMapa, setModoMapa] = useState<ModoMapa>("actual");
  const [codigoMapa, setCodigoMapa] = useState("");

  const seleccionada = resumen.riesgos.find((r) => r.enfermedad_id === enfermedadId);
  const prediccion = enfermedadId != null ? predicciones[enfermedadId] : null;
  const puntos = useMemo(() => (enfermedadId != null ? series[enfermedadId]?.puntos.slice(-semanas) ?? [] : []),
    [series, enfermedadId, semanas]);
  const enfermedades = resumen.riesgos.map((r) => ({ codigo: r.codigo, nombre: r.nombre }));
  const irA = (id: number) => router.push(`/municipio/${id}`, { scroll: true });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="titulo-seccion text-[13px] text-muted">Vigilancia epidemiológica temprana</p>
          <TituloRevelado className="titulo-display mt-2 text-[2.6rem] sm:text-6xl lg:text-7xl"
            texto={`Riesgo de brotes en ${municipio.nombre}`} />
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-2">
            Semana epidemiológica <b className="tabular">{resumen.semana_referencia.replace("-S", " · S")}</b>
            <span className="text-muted">· {fmtNum(municipio.poblacion)} hab. · {fmtNum(municipio.altitud_m)} m s. n. m.</span>
            {resumen.hay_datos_simulados && <SimuladoBadge />}
          </p>
        </div>
        <div className="flex w-full items-end gap-2 md:w-auto">
          <label className="min-w-0 flex-1 md:w-64 md:flex-none">
            <span className="mb-1 flex items-center gap-1 text-xs font-medium text-ink-2"><MapPin size={13} /> Municipio</span>
            <select className={claseInput} value={municipio.id} onChange={(e) => irA(Number(e.target.value))}>
              {municipios.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
          </label>
          <MenuReportes municipioId={municipio.id} municipio={municipio.nombre} enfermedadId={enfermedadId} />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {resumen.riesgos.map((r, i) => (
          <Revelar key={r.codigo} retraso={i * 80} className="flex">
            <SemaforoCard r={r} activo={r.enfermedad_id === enfermedadId} onClick={() => setEnfermedadId(r.enfermedad_id)} />
          </Revelar>
        ))}
      </div>

      <Revelar>
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
              {seleccionada && (
                <CanalEndemicoChart puntos={puntos} color={seleccionada.color} prediccion={prediccion ?? null}
                  mostrarValidacion={verValidacion} />
              )}
              <ResumenModelo prediccion={prediccion ?? null} />
            </div>
          </Card>
          <div className="min-w-0 space-y-6">
            <VolcanCard v={resumen.volcan} />
            <ClimaActualCard c={clima} municipio={municipio.nombre} />
          </div>
        </div>
      </Revelar>

      <Revelar>
        <div className="grid gap-6 lg:grid-cols-2">
          <PanelExplicacion exp={enfermedadId != null ? explicaciones[enfermedadId] ?? null : null} />
          <Card className="min-w-0">
            <CardHeader titulo="Recomendaciones de prevención" subtitulo="Ordenadas según el nivel de riesgo actual" />
            <Recomendaciones riesgos={resumen.riesgos} />
          </Card>
        </div>
      </Revelar>

      <Revelar>
        <Card className="min-w-0">
          <CardHeader titulo="Mapa de riesgo · zona de influencia del Galeras" icono={<IconoMapa size={17} />}
            subtitulo="Haz clic en un municipio para abrir su tablero. El mapa con alertas en vivo está en «Mapa en vivo»."
            accion={
              <div className="flex flex-wrap items-center gap-2">
                <select className="rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink focus:border-accent focus:outline-none"
                  value={codigoMapa} onChange={(e) => setCodigoMapa(e.target.value)} aria-label="Enfermedad del mapa">
                  <option value="">Todas (la de mayor riesgo)</option>
                  {enfermedades.map((r) => <option key={r.codigo} value={r.codigo}>{r.nombre}</option>)}
                </select>
                <Segmentado etiqueta="Periodo del mapa" opciones={MODOS_MAPA} valor={modoMapa} onCambiar={setModoMapa} />
              </div>
            } />
          <div className="grid grid-cols-1 gap-4 px-5 pb-5 lg:grid-cols-5">
            <div className="min-w-0 lg:col-span-3">
              <MapaRiesgo filas={porMunicipio} modo={modoMapa} codigo={codigoMapa} seleccionado={municipio.id}
                enfermedades={enfermedades} onSeleccionar={irA} />
            </div>
            <div className="-mx-5 min-w-0 lg:col-span-2 lg:mx-0">
              <RiesgoMunicipiosTabla filas={porMunicipio} seleccionado={municipio.id} predicho={modoMapa === "predicho"}
                enfermedades={enfermedades} onSeleccionar={irA} />
            </div>
          </div>
        </Card>
      </Revelar>

      <Revelar>
        <Card>
          <CardHeader titulo="Pronóstico del clima · próximos 16 días" icono={<CloudSun size={17} />}
            subtitulo={pronostico.some((d) => d.es_simulado) ? "Clima simulado (Open-Meteo no estaba disponible al cargar la semilla)" : "Fuente: Open-Meteo"} />
          <div className="px-3 pb-5 sm:px-5">
            {pronostico.length === 0
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
