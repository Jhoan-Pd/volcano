"use client";

import { Cpu, FileSearch, X } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { catalogoApi } from "@/api/servicios";
import { CATEGORIAS, fmtNum } from "@/lib/formato";
import { useAnalizadorCsv } from "@/lib/useAnalizadorCsv";
import { useDatos } from "@/lib/useDatos";
import { useFps } from "@/lib/useFps";
import type { ResultadoCsv } from "@/workers/csv/analizar";
import { ESQUEMAS, type TipoCsv } from "@/workers/csv/esquemas";
import { Aviso, claseCabeceraTabla } from "./ui";

/**
 * Revisión de un CSV en el navegador ANTES de subirlo, con un Web Worker.
 * Muestra el avance, los fps del hilo principal (siguen altos: la página no se congela), los
 * errores por fila, una vista previa y un resumen. `accion` recibe el resultado para que cada
 * pantalla decida qué hacer (subir el archivo limpio, enviarlo por streaming…).
 */
export default function RevisionCsv({ tipo, accion }: {
  tipo: TipoCsv;
  accion: (r: ResultadoCsv, archivo: File) => ReactNode;
}) {
  const { analizar, cancelar, avance, analizando } = useAnalizadorCsv();
  const fps = useFps(analizando);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [resultado, setResultado] = useState<ResultadoCsv | null>(null);
  const [error, setError] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement>(null);
  const contexto = useDatos(async () => {
    const [municipios, enfermedades] = await Promise.all([catalogoApi.municipios(), catalogoApi.enfermedades()]);
    return { municipios: municipios.map((m) => m.codigo_divipola), enfermedades: enfermedades.map((e) => e.codigo), categorias: Object.keys(CATEGORIAS) };
  }, []);
  const esquema = ESQUEMAS[tipo];

  async function revisar(f: File) {
    setArchivo(f); setResultado(null); setError(null);
    if (!contexto.datos) { setError("Aún no se cargan los catálogos; intenta de nuevo en un momento."); return; }
    try {
      setResultado(await analizar(f, tipo, contexto.datos));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo revisar el archivo");
    }
  }

  function limpiar() {
    if (analizando) cancelar();
    setArchivo(null); setResultado(null); setError(null);
    if (entrada.current) entrada.current.value = "";
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface px-3.5 py-2 text-sm font-medium hover:bg-surface-2">
          <FileSearch size={15} aria-hidden /> {archivo ? "Elegir otro archivo" : "Elegir CSV"}
          <input ref={entrada} type="file" accept=".csv,text/csv" className="sr-only"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void revisar(f); }} />
        </label>
        {archivo && <span className="text-xs text-ink-2">{archivo.name} · {fmtNum(archivo.size / 1024, 0)} KB</span>}
        {archivo && <button type="button" onClick={limpiar} className="rounded-md p-1 text-muted hover:bg-surface-2" aria-label="Quitar archivo"><X size={15} /></button>}
      </div>
      <p className="text-[11px] text-muted">Columnas: {esquema.columnas.map((c) => esquema.opcionales.includes(c) ? `${c} (opcional)` : c).join(", ")}. Separador «,» o «;».</p>

      {avance && (
        <div className="rounded-lg border border-line p-3 text-xs" aria-live="polite">
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 font-medium"><Cpu size={14} aria-hidden /> Revisando en un Web Worker… {fmtNum(avance.filas)} filas</span>
            <span className="tabular text-muted">Hilo principal: {fps ?? "—"} fps</span>
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-surface-2">
            <div className="h-1.5 rounded-full bg-ink transition-[width]" style={{ width: `${Math.round(avance.fraccion * 100)}%` }} />
          </div>
          <button type="button" onClick={limpiar} className="mt-2 text-[11px] text-ink-2 underline">Cancelar (termina el worker)</button>
        </div>
      )}
      {error && <Aviso tipo="error">{error}</Aviso>}

      {resultado && archivo && (
        <div className="space-y-3 rounded-lg border border-line p-4 text-sm">
          {resultado.faltan.length > 0 ? (
            <Aviso tipo="error">Faltan columnas: {resultado.faltan.join(", ")}. Llegaron: {resultado.columnas.join(", ") || "ninguna"}.</Aviso>
          ) : (
            <>
              <dl className="grid gap-3 sm:grid-cols-4">
                <Dato etiqueta="Filas leídas" valor={fmtNum(resultado.filasLeidas)} />
                <Dato etiqueta="Válidas" valor={fmtNum(resultado.filasValidas)} />
                <Dato etiqueta="Con error" valor={fmtNum(resultado.filasLeidas - resultado.filasValidas)} />
                <Dato etiqueta="Revisado en" valor={`${fmtNum(resultado.duracionMs, 0)} ms`} />
                {resultado.periodo && <Dato etiqueta="Periodo" valor={`${resultado.periodo.desde} → ${resultado.periodo.hasta}`} />}
                {resultado.total && <Dato etiqueta="Total" valor={`${fmtNum(resultado.total.valor)} ${resultado.total.etiqueta}`} />}
                <Dato etiqueta="Formato" valor={`«${resultado.delimitador}» · ${resultado.codificacion}`} />
                {resultado.duplicadas > 0 && <Dato etiqueta="Repetidas" valor={fmtNum(resultado.duplicadas)} />}
              </dl>
              {resultado.grupos && resultado.grupos.valores.length > 0 && (
                <p className="text-xs text-ink-2"><b className="font-medium">{resultado.grupos.etiqueta}:</b>{" "}
                  {resultado.grupos.valores.slice(0, 8).map(([g, n]) => `${g} (${fmtNum(n)})`).join(" · ")}</p>
              )}
              {resultado.sobran.length > 0 && <p className="text-xs text-muted">Columnas que se ignorarán: {resultado.sobran.join(", ")}.</p>}
              {resultado.errores.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer font-medium text-[var(--st-rojo-ink)]">
                    {resultado.errores.length + resultado.erroresOmitidos} fila(s) con error — ver detalle
                  </summary>
                  <ul className="mt-2 max-h-40 space-y-0.5 overflow-y-auto">
                    {resultado.errores.map((e) => <li key={e.fila}>Fila {e.fila}: {e.mensaje}</li>)}
                    {resultado.erroresOmitidos > 0 && <li className="text-muted">… y {resultado.erroresOmitidos} más</li>}
                  </ul>
                </details>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className={claseCabeceraTabla}>{resultado.columnas.map((c) => <th key={c} className="px-2 py-1.5 font-medium">{c}</th>)}</tr></thead>
                  <tbody>
                    {resultado.vistaPrevia.map((f, i) => (
                      <tr key={i} className="border-b border-line">{resultado.columnas.map((c) => <td key={c} className="px-2 py-1 tabular">{f[c]}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-1 text-[11px] text-muted">Vista previa de las primeras {resultado.vistaPrevia.length} filas.</p>
              </div>
              {accion(resultado, archivo)}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return <div><dt className="text-[11px] text-muted">{etiqueta}</dt><dd className="tabular font-medium">{valor}</dd></div>;
}

