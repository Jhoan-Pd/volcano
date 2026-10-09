import { BellRing, ChevronLeft, ChevronRight, Download, MailCheck, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { mensajeError } from "../../api/cliente";
import { alertaApi, reporteApi } from "../../api/servicios";
import type { Alerta, Pagina } from "../../api/tipos";
import { fmtFecha } from "../../lib/formato";
import { Aviso, Boton, NivelChip, Spinner } from "../ui";

const FILTROS = [
  { valor: true, etiqueta: "Activas" },
  { valor: false, etiqueta: "Cerradas" },
  { valor: undefined, etiqueta: "Todas" },
] as const;
const POR_PAGINA = 15;

export default function PanelAlertas() {
  const [filtro, setFiltro] = useState<boolean | undefined>(true);
  const [pagina, setPagina] = useState(0);
  const [datos, setDatos] = useState<Pagina<Alerta> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [evaluando, setEvaluando] = useState(false);
  const [cerrando, setCerrando] = useState<number | null>(null);

  const cargar = useCallback(() => {
    setError(null);
    alertaApi.listar(filtro, pagina * POR_PAGINA, POR_PAGINA).then(setDatos).catch((e) => setError(mensajeError(e)));
  }, [filtro, pagina]);
  useEffect(cargar, [cargar]);

  async function evaluar() {
    setEvaluando(true); setAviso(null); setError(null);
    try {
      const r = await alertaApi.evaluar();
      setAviso(`${r.activas} alerta(s) activa(s): ${r.nuevas} nueva(s), ${r.actualizadas} actualizada(s), ${r.cerradas} cerrada(s). ` +
        (r.correos_enviados ? `Correo enviado con ${r.correos_enviados} alerta(s).` : "Sin correos nuevos (o Resend no está configurado)."));
      cargar();
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setEvaluando(false);
    }
  }

  async function cerrar(a: Alerta) {
    setCerrando(a.id);
    try {
      await alertaApi.cerrar(a.id);
      cargar();
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setCerrando(null);
    }
  }

  const paginas = datos ? Math.max(1, Math.ceil(datos.total / POR_PAGINA)) : 1;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold"><BellRing size={18} className="text-muted" /> Alertas tempranas</h2>
          <p className="max-w-2xl text-xs text-muted">
            Se generan cuando el riesgo llega a <b>alto</b> o <b>muy alto</b>, por los casos observados o por la predicción de las
            próximas 4 semanas. Se evalúan tras cada reentrenamiento y en la actualización diaria. Una alerta cerrada a mano
            solo se reabre si el riesgo empeora.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-line p-0.5 text-xs" role="group" aria-label="Filtrar alertas">
            {FILTROS.map((f) => (
              <button key={f.etiqueta} onClick={() => { setFiltro(f.valor); setPagina(0); }} aria-pressed={filtro === f.valor}
                className={`rounded-md px-2.5 py-1 font-medium ${filtro === f.valor ? "bg-surface-2 text-ink" : "text-muted hover:text-ink"}`}>
                {f.etiqueta}
              </button>
            ))}
          </div>
          <Boton variante="secundario" onClick={() => reporteApi.alertasCsv().catch((e) => setError(mensajeError(e)))}>
            <Download size={15} /> CSV
          </Boton>
          <Boton onClick={evaluar} cargando={evaluando}><RefreshCw size={15} /> Evaluar ahora</Boton>
        </div>
      </div>

      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}

      {!datos ? <Spinner /> : datos.items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">No hay alertas {filtro === true ? "activas" : filtro === false ? "cerradas" : ""}.</p>
      ) : (
        <div className="relative overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr className="border-b border-line bg-surface-2 text-left text-xs text-muted">
                <th className="px-3 py-2 font-medium">Nivel</th>
                <th className="px-3 py-2 font-medium">Origen</th>
                <th className="px-3 py-2 font-medium">Semana</th>
                <th className="px-3 py-2 font-medium">Detalle</th>
                <th className="px-3 py-2 font-medium">Creada</th>
                <th className="px-3 py-2 font-medium"><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {datos.items.map((a) => (
                <tr key={a.id} className="border-b border-line/70 align-top last:border-0">
                  <td className="px-3 py-2.5"><NivelChip nivel={a.nivel_riesgo} /></td>
                  <td className="px-3 py-2.5 text-xs font-medium uppercase tracking-wide text-ink-2">{a.origen === "OBSERVADO" ? "Observado" : "Predicho"}</td>
                  <td className="whitespace-nowrap px-3 py-2.5 tabular">{a.etiqueta.replace("-S", " · S")}</td>
                  <td className="px-3 py-2.5">
                    <p className="font-medium">{a.enfermedad} · {a.municipio}</p>
                    <p className="text-xs text-ink-2">{a.mensaje}</p>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-xs text-ink-2">
                    {fmtFecha(a.creado_en)}
                    {a.notificada_email && <span className="mt-0.5 flex items-center gap-1 text-muted"><MailCheck size={12} /> correo enviado</span>}
                    {a.cerrada_en && <span className="mt-0.5 block text-muted">cerrada {fmtFecha(a.cerrada_en)}</span>}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {a.activa && <Boton variante="secundario" className="px-2.5 py-1 text-xs" cargando={cerrando === a.id} onClick={() => cerrar(a)}>Cerrar</Boton>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {datos && datos.total > POR_PAGINA && (
        <div className="flex items-center justify-end gap-2 text-xs text-ink-2">
          <span className="tabular">Página {pagina + 1} de {paginas}</span>
          <button className="rounded-md p-1 hover:bg-surface-2 disabled:opacity-40" disabled={pagina === 0} onClick={() => setPagina((p) => p - 1)} aria-label="Anterior"><ChevronLeft size={16} /></button>
          <button className="rounded-md p-1 hover:bg-surface-2 disabled:opacity-40" disabled={pagina + 1 >= paginas} onClick={() => setPagina((p) => p + 1)} aria-label="Siguiente"><ChevronRight size={16} /></button>
        </div>
      )}
    </div>
  );
}
