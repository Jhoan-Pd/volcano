import { CloudSun, Database, FileUp, RefreshCw, Search, Stethoscope } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { mensajeError } from "../../api/cliente";
import { climaApi, datosApi } from "../../api/servicios";
import type { EstadoFuente, ResultadoImportacion, TipoImportacion } from "../../api/tipos";
import { fmtFecha, fmtNum } from "../../lib/formato";
import { Aviso, Boton, claseInput, Etiqueta, Spinner } from "../ui";

type Mensaje = { tipo: "ok" | "error"; texto: string } | null;

/** Ejecuta una acción del panel y traduce el resultado en un aviso. */
function useAccion() {
  const [cargando, setCargando] = useState(false);
  const [mensaje, setMensaje] = useState<Mensaje>(null);
  const ejecutar = useCallback(async (fn: () => Promise<string>, alTerminar?: () => void) => {
    setCargando(true); setMensaje(null);
    try {
      setMensaje({ tipo: "ok", texto: await fn() });
      alTerminar?.();
    } catch (e) {
      setMensaje({ tipo: "error", texto: mensajeError(e) });
    } finally {
      setCargando(false);
    }
  }, []);
  return { cargando, mensaje, ejecutar };
}

function Fuente({ icono, titulo, descripcion, children, mensaje }: {
  icono: ReactNode; titulo: string; descripcion: string; children: ReactNode; mensaje: Mensaje;
}) {
  return (
    <div className="flex flex-col rounded-xl border border-line p-4">
      <p className="flex items-center gap-2 font-medium"><span className="text-muted">{icono}</span>{titulo}</p>
      <p className="mt-1 flex-1 text-sm text-ink-2">{descripcion}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">{children}</div>
      {mensaje && <div className="mt-3"><Aviso tipo={mensaje.tipo}>{mensaje.texto}</Aviso></div>}
    </div>
  );
}

const PLANTILLAS: Record<TipoImportacion, { etiqueta: string; columnas: string }> = {
  casos: { etiqueta: "Casos semanales", columnas: "cod_divipola, enfermedad, anio, semana_epi, casos" },
  clima: { etiqueta: "Clima diario", columnas: "cod_divipola, fecha, temp_max_c, temp_min_c, temp_media_c, precipitacion_mm, humedad_relativa_pct" },
  eventos: { etiqueta: "Eventos volcánicos", columnas: "tipo, nivel_actividad, fecha_inicio, cod_divipola, intensidad_ceniza, so2_ton_dia, descripcion" },
  tendencias: { etiqueta: "Búsquedas (Trends)", columnas: "termino, fecha_semana, indice" },
};

export default function PanelDatos() {
  const [estado, setEstado] = useState<EstadoFuente[] | null>(null);
  const [errorEstado, setErrorEstado] = useState<string | null>(null);
  const clima = useAccion();
  const trends = useAccion();
  const sivigila = useAccion();
  const [desdeAnio, setDesdeAnio] = useState(2020);

  const cargarEstado = useCallback(() => {
    datosApi.estado().then(setEstado).catch((e) => setErrorEstado(mensajeError(e)));
  }, []);
  useEffect(cargarEstado, [cargarEstado]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Fuentes de datos</h2>
        <p className="text-xs text-muted">
          GitHub Actions ejecuta estas sincronizaciones una vez al día. Aquí puedes lanzarlas a mano o cargar archivos.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Fuente icono={<CloudSun size={16} />} titulo="Clima · Open-Meteo" mensaje={clima.mensaje}
          descripcion="Pronóstico de 16 días y últimos 14 días observados de cada municipio. Sin API key.">
          <Boton cargando={clima.cargando} onClick={() => clima.ejecutar(async () => {
            const r = await climaApi.sincronizar();
            return `${fmtNum(r.registros_guardados)} días guardados para ${r.municipios} municipios.` +
              (r.errores.length ? ` Errores: ${r.errores.join("; ")}` : "");
          }, cargarEstado)}><RefreshCw size={15} /> Sincronizar clima</Boton>
        </Fuente>
        <Fuente icono={<Search size={16} />} titulo="Búsquedas · Google Trends" mensaje={trends.mensaje}
          descripcion="Índice semanal de búsquedas de síntomas en Nariño (CO-NAR). Si pytrends falla se usa la caché en BD o el CSV de respaldo.">
          <Boton cargando={trends.cargando} onClick={() => trends.ejecutar(async () => {
            const r = await datosApi.sincronizarTendencias();
            return `Fuente: ${r.fuente}. ${fmtNum(r.registros_guardados)} semanas guardadas` +
              (r.desde_cache.length ? `; al día en caché: ${r.desde_cache.join(", ")}` : "") +
              (r.errores.length ? `. Avisos: ${r.errores.join("; ")}` : ".");
          }, cargarEstado)}><RefreshCw size={15} /> Sincronizar búsquedas</Boton>
        </Fuente>
        <Fuente icono={<Stethoscope size={16} />} titulo="Casos · SIVIGILA (datos.gov.co)" mensaje={sivigila.mensaje}
          descripcion="Casos oficiales del INS por semana epidemiológica. Reemplazan a los simulados de las mismas semanas.">
          <label className="flex items-center gap-1.5 text-xs text-ink-2">
            Desde
            <input type="number" min={2007} max={2100} value={desdeAnio} onChange={(e) => setDesdeAnio(Number(e.target.value))}
              className="w-20 rounded-lg border border-line bg-surface px-2 py-1.5 text-sm text-ink focus:border-accent focus:outline-none" aria-label="Año inicial" />
          </label>
          <Boton cargando={sivigila.cargando} onClick={() => sivigila.ejecutar(async () => {
            const r = await datosApi.sincronizarSivigila(desdeAnio);
            return r.registros_guardados
              ? `${fmtNum(r.registros_guardados)} semanas guardadas (${r.enfermedades.join(", ")}; años ${r.anios_cubiertos.join(", ")}).`
              : `No se encontraron registros nuevos.${r.errores.length ? ` ${r.errores.join("; ")}` : ""}`;
          }, cargarEstado)}><RefreshCw size={15} /> Sincronizar casos</Boton>
        </Fuente>
      </div>

      <CargaCsv alTerminar={cargarEstado} />

      <div>
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Database size={15} className="text-muted" /> Estado de las tablas</h3>
        {errorEstado ? <Aviso tipo="error">{errorEstado}</Aviso> : !estado ? <Spinner /> : (
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="border-b border-line bg-surface-2 text-left text-xs text-muted">
                  <th className="px-3 py-2 font-medium">Fuente</th>
                  <th className="px-3 py-2 text-right font-medium">Registros</th>
                  <th className="px-3 py-2 text-right font-medium">Simulados</th>
                  <th className="px-3 py-2 font-medium">Última semana</th>
                  <th className="px-3 py-2 font-medium">Actualizado</th>
                </tr>
              </thead>
              <tbody>
                {estado.map((f) => (
                  <tr key={f.tabla} className="border-b border-line/70 last:border-0">
                    <td className="px-3 py-2"><p className="font-medium">{f.fuente}</p><p className="text-[11px] text-muted">{f.tabla}</p></td>
                    <td className="px-3 py-2 text-right tabular">{fmtNum(f.registros)}</td>
                    <td className="px-3 py-2 text-right tabular">
                      {f.registros ? `${fmtNum((100 * f.simulados) / f.registros, 0)} %` : "—"}
                    </td>
                    <td className="px-3 py-2 tabular">{f.ultima_semana?.replace("-S", " · S") ?? "—"}</td>
                    <td className="px-3 py-2 text-xs text-ink-2">
                      {f.ultima_actualizacion ? fmtFecha(f.ultima_actualizacion, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function CargaCsv({ alTerminar }: { alTerminar: () => void }) {
  const [tipo, setTipo] = useState<TipoImportacion>("casos");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [resultado, setResultado] = useState<ResultadoImportacion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  async function subir() {
    if (!archivo) return;
    setCargando(true); setResultado(null); setError(null);
    try {
      setResultado(await datosApi.importar(tipo, archivo));
      setArchivo(null);
      if (input.current) input.current.value = "";
      alTerminar();
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="rounded-xl border border-line p-4">
      <p className="flex items-center gap-2 font-medium"><FileUp size={16} className="text-muted" /> Carga de CSV</p>
      <p className="mt-1 text-sm text-ink-2">
        Inserta o actualiza registros (subir el mismo archivo dos veces no duplica). Separador coma o punto y coma; máximo 5 MB.
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-[14rem_1fr_auto] md:items-end">
        <Etiqueta texto="Tipo de archivo">
          <select className={claseInput} value={tipo} onChange={(e) => { setTipo(e.target.value as TipoImportacion); setResultado(null); }}>
            {Object.entries(PLANTILLAS).map(([k, v]) => <option key={k} value={k}>{v.etiqueta}</option>)}
          </select>
        </Etiqueta>
        <Etiqueta texto="Archivo" ayuda={`Columnas: ${PLANTILLAS[tipo].columnas}`}>
          <input ref={input} type="file" accept=".csv,text/csv" className={`${claseInput} py-1.5 file:mr-3 file:rounded-md file:border-0 file:bg-surface-2 file:px-2 file:py-1 file:text-xs file:font-medium file:text-ink`}
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
        </Etiqueta>
        <Boton onClick={subir} cargando={cargando} disabled={!archivo} className="md:mb-5"><FileUp size={15} /> Importar</Boton>
      </div>
      {error && <div className="mt-3"><Aviso tipo="error">{error}</Aviso></div>}
      {resultado && (
        <div className="mt-3 space-y-2">
          <Aviso tipo={resultado.errores.length ? "info" : "ok"}>
            {fmtNum(resultado.filas_leidas)} filas leídas · {fmtNum(resultado.insertadas)} nuevas · {fmtNum(resultado.actualizadas)} actualizadas
            {resultado.errores.length > 0 && ` · ${resultado.errores.length} con errores`}
          </Aviso>
          {resultado.errores.length > 0 && (
            <ul className="max-h-40 space-y-0.5 overflow-y-auto rounded-lg bg-surface-2 px-3 py-2 text-xs text-ink-2">
              {resultado.errores.map((e) => <li key={e.fila}><b className="tabular">Fila {e.fila}:</b> {e.mensaje}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
